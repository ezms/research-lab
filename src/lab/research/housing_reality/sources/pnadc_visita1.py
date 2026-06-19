import re
import unicodedata
import zipfile
from pathlib import Path

import httpx
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from lab.research.housing_reality.domain.ports import HousingDataSource
from lab.research.housing_reality.sources._utils import _is_valid_zip

_BASE_URL = (
    "https://ftp.ibge.gov.br/Trabalho_e_Rendimento"
    "/Pesquisa_Nacional_por_Amostra_de_Domicilios_continua"
    "/Anual/Microdados/Visita/Visita_1/Dados"
)
_LAYOUT_DIR = Path(__file__).parent / "pnadc_layout"

_UF_CODE_TO_ABBR: dict[int, str] = {
    11: "RO", 12: "AC", 13: "AM", 14: "RR", 15: "PA", 16: "AP", 17: "TO",
    21: "MA", 22: "PI", 23: "CE", 24: "RN", 25: "PB", 26: "PE",
    27: "AL", 28: "SE", 29: "BA",
    31: "MG", 32: "ES", 33: "RJ", 35: "SP",
    41: "PR", 42: "SC", 43: "RS",
    50: "MS", 51: "MT", 52: "GO", 53: "DF",
}


def _to_snake(text: object) -> str:
    if not text or isinstance(text, float):
        return ""
    normalized = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", normalized.lower()).strip("_")



def _fwf_params(layout: pd.DataFrame) -> tuple[list, list, dict]:
    colspecs = [(int(row["start"]) - 1, int(row["end"])) for _, row in layout.iterrows()]
    var_names = list(layout["variable"])
    dtypes: dict[str, str] = {}
    for _, row in layout.iterrows():
        if row["variable"] == "UF":
            continue
        is_numeric = str(row["type"]).strip().upper() == "N"
        length = int(row["length"])
        if is_numeric and length >= 8:
            dtypes[row["variable"]] = "Float64"
        elif length <= 2:
            dtypes[row["variable"]] = "Int8"
        elif length <= 4:
            dtypes[row["variable"]] = "Int16"
        else:
            dtypes[row["variable"]] = "Int32"
    return colspecs, var_names, dtypes


def _find_zip_filename(year: int) -> str:
    resp = httpx.get(_BASE_URL + "/", timeout=60, follow_redirects=True)
    resp.raise_for_status()
    pattern = re.compile(rf"PNADC_{year}_visita1_\d+\.zip", re.IGNORECASE)
    matches = pattern.findall(resp.text)
    if not matches:
        raise FileNotFoundError(f"PNADC Visita 1 {year} not found at IBGE FTP")
    return matches[0]


class PNADCVisita1DataSource(HousingDataSource):
    def __init__(self, work_dir: Path) -> None:
        self._work_dir = work_dir / "pnadc"

    def collect(self, params) -> dict[str, dict[str, Path]]:
        year_dir = self._work_dir / str(params.pnadc_year)
        year_dir.mkdir(parents=True, exist_ok=True)
        zip_path = self._download(params.pnadc_year, year_dir)
        parsed = self._parse(params.pnadc_year, zip_path, year_dir)
        return self._map_variables(parsed, year_dir)

    def find_local(self, params) -> dict[str, dict[str, Path]] | None:
        mapped_dir = self._work_dir / str(params.pnadc_year) / "mapped"
        if not mapped_dir.exists():
            return None
        results: dict[str, dict[str, Path]] = {}
        for path in sorted(mapped_dir.glob("*.parquet")):
            if path.name.endswith(".tmp.parquet"):
                continue
            parts = path.stem.split("_", 1)
            if len(parts) != 2:
                continue
            uf_abbr, file_type = parts
            results.setdefault(uf_abbr, {})[file_type] = path
        return results or None

    def _download(self, year: int, year_dir: Path) -> Path:
        filename = _find_zip_filename(year)
        zip_path = year_dir / filename
        if zip_path.exists() and _is_valid_zip(zip_path):
            return zip_path
        url = f"{_BASE_URL}/{filename}"
        with httpx.stream("GET", url, follow_redirects=True, timeout=600) as resp:
            resp.raise_for_status()
            with open(zip_path, "wb") as f:
                for chunk in resp.iter_bytes(65_536):
                    f.write(chunk)
        return zip_path

    def _parse(self, year: int, zip_path: Path, year_dir: Path) -> dict[str, dict[str, Path]]:
        layout = pd.read_csv(_LAYOUT_DIR / "moradores.csv")
        colspecs, var_names, dtypes = _fwf_params(layout)

        parsed_dir = year_dir / "parsed"
        parsed_dir.mkdir(parents=True, exist_ok=True)

        existing = {
            p.stem: p
            for p in sorted(parsed_dir.glob("*.parquet"))
            if not p.stem.endswith(".tmp")
        }
        if len(existing) == len(_UF_CODE_TO_ABBR):
            return {abbr: {"moradores": path} for abbr, path in existing.items()}

        txt_path = self._extract_txt(zip_path, year_dir)

        writers: dict[str, pq.ParquetWriter] = {}
        tmp_paths: dict[str, Path] = {}
        try:
            reader = pd.read_fwf(
                txt_path,
                colspecs=colspecs,
                names=var_names,
                header=None,
                encoding="latin-1",
                chunksize=100_000,
            )
            for chunk in reader:
                chunk = chunk.astype({k: v for k, v in dtypes.items() if k in chunk.columns})
                chunk["UF"] = pd.to_numeric(chunk["UF"], errors="coerce")
                for uf_num, uf_group in chunk.groupby("UF", dropna=True):
                    uf_abbr = _UF_CODE_TO_ABBR.get(int(uf_num))
                    if not uf_abbr:
                        continue
                    uf_group = uf_group.copy()
                    uf_group["UF"] = uf_abbr
                    table = pa.Table.from_pandas(uf_group, preserve_index=False)
                    tmp_path = parsed_dir / f"{uf_abbr}.tmp.parquet"
                    if uf_abbr not in writers:
                        writers[uf_abbr] = pq.ParquetWriter(
                            tmp_path, table.schema, compression="snappy"
                        )
                        tmp_paths[uf_abbr] = tmp_path
                    writers[uf_abbr].write_table(table)
        finally:
            for w in writers.values():
                w.close()

        result: dict[str, dict[str, Path]] = {}
        for uf_abbr, tmp in tmp_paths.items():
            final = parsed_dir / f"{uf_abbr}.parquet"
            tmp.rename(final)
            result[uf_abbr] = {"moradores": final}
        return result

    def _map_variables(
        self, parsed: dict[str, dict[str, Path]], year_dir: Path
    ) -> dict[str, dict[str, Path]]:
        layout = pd.read_csv(_LAYOUT_DIR / "moradores.csv")
        rename_map = {row["variable"]: _to_snake(row["description"]) for _, row in layout.iterrows()}
        rename_map["UF"] = "uf"

        mapped_dir = year_dir / "mapped"
        mapped_dir.mkdir(parents=True, exist_ok=True)

        result: dict[str, dict[str, Path]] = {}
        for uf_abbr, files in parsed.items():
            result[uf_abbr] = {}
            for file_type, parsed_path in files.items():
                out_path = mapped_dir / f"{uf_abbr}_{file_type}.parquet"
                if out_path.exists():
                    result[uf_abbr][file_type] = out_path
                    continue
                df = pd.read_parquet(parsed_path)
                df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
                tmp_path = out_path.with_suffix(".tmp.parquet")
                df.to_parquet(tmp_path, compression="snappy", index=False)
                tmp_path.rename(out_path)  # atomic: readers never see a partial file
                result[uf_abbr][file_type] = out_path
        return result

    def _extract_txt(self, zip_path: Path, year_dir: Path) -> Path:
        with zipfile.ZipFile(zip_path) as zf:
            txt_entries = [n for n in zf.namelist() if n.lower().endswith(".txt")]
            if not txt_entries:
                raise ValueError(f"No .txt file in {zip_path.name}")
            entry = txt_entries[0]
            out_path = year_dir / Path(entry).name
            if not out_path.exists():
                zf.extract(entry, year_dir)
                extracted = year_dir / entry
                if str(extracted) != str(out_path):
                    extracted.rename(out_path)
        return out_path
