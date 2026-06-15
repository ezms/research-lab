import re
import unicodedata
import zipfile
from pathlib import Path

import httpx
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from lab.enums.uf import UF
from lab.platform.data_source.contract import DataSource, SourceIdentity

_LAYOUT_DIR = Path(__file__).parent / "census_2010_layout"

_FILE_TYPES = {
    "domicilios":  "Amostra_Domicilios",
    "pessoas":     "Amostra_Pessoas",
    "emigracao":   "Amostra_Emigracao",
    "mortalidade": "Amostra_Mortalidade",
}

# UFs where IBGE splits the zip into multiple parts.
# Each entry lists the zip name stems (without .zip) in download order.
_UF_ZIP_PARTS: dict[str, list[str]] = {
    "SP": ["SP1", "SP2_RM"],
}


def _is_valid_zip(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path):
            return True
    except zipfile.BadZipFile:
        return False


def _to_snake(text: object) -> str:
    if not isinstance(text, str) or not text.strip():
        return ""
    # heading ends at ": " or at the start of a category list (" 1- ", " 1 - ")
    heading = re.split(r":\s*|\s+\d+\s*[-–]\s*", text)[0].strip()
    name = heading.lower()
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", name)).strip("_")


def _fwf_params(
    layout: pd.DataFrame,
) -> tuple[list[tuple[int, int]], list[str], dict[str, str]]:
    colspecs: list[tuple[int, int]] = []
    names: list[str] = []
    dtypes: dict[str, str] = {}

    for _, row in layout.iterrows():
        colspecs.append((int(row["start"]) - 1, int(row["end"])))
        var = row["variable"]
        names.append(var)

        length = int(row["length"])
        has_decimals = str(row["decimals"]).strip() not in ("", "nan")

        if has_decimals:
            dtypes[var] = "Float64"
        elif length <= 2:
            dtypes[var] = "Int8"
        elif length <= 4:
            dtypes[var] = "Int16"
        elif length <= 9:
            dtypes[var] = "Int32"
        else:
            dtypes[var] = "Int64"

    return colspecs, names, dtypes


class Census2010DataSource(DataSource):
    BASE_URL = (
        "https://ftp.ibge.gov.br/Censos/Censo_Demografico_2010"
        "/Resultados_Gerais_da_Amostra/Microdados"
    )
    MAX_FILE_SIZE_BYTES = 200 * 1024 * 1024

    def __init__(self, uf: UF, work_dir: Path) -> None:
        self._uf = uf
        self._work_dir = work_dir

    def identify(self) -> SourceIdentity:
        return SourceIdentity(
            name="Censo Demográfico",
            version="2010",
            provider="IBGE",
            description=(
                f"Microdados da Amostra do Censo Demográfico 2010 para a UF {self._uf.value}"
            ),
        )

    def _download_zip(self, stem: str) -> Path:
        output_path = self._work_dir / f"{stem}.zip"
        if output_path.exists():
            if _is_valid_zip(output_path):
                return output_path
            output_path.unlink()

        url = f"{self.BASE_URL}/{stem}.zip"
        with httpx.Client() as client:
            head = client.head(url)
            head.raise_for_status()
            content_length = int(head.headers.get("content-length", 0))
            if content_length > self.MAX_FILE_SIZE_BYTES:
                raise ValueError(
                    f"File too large: {content_length} bytes "
                    f"exceeds limit of {self.MAX_FILE_SIZE_BYTES} bytes"
                )
            with client.stream("GET", url) as response:
                response.raise_for_status()
                with output_path.open("wb") as f:
                    for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                        f.write(chunk)

        return output_path

    def download(self) -> Path:
        self._work_dir.mkdir(parents=True, exist_ok=True)
        parts = _UF_ZIP_PARTS.get(self._uf.value, [self._uf.value])
        for stem in parts:
            self._download_zip(stem)
        return self._work_dir / f"{parts[0]}.zip"

    def parse(self, file_path: Path) -> dict[str, Path]:
        raw_dir = self._work_dir / self._uf.value
        parsed_dir = raw_dir / "parsed"
        parsed_dir.mkdir(parents=True, exist_ok=True)

        if not any(raw_dir.glob("*.txt")):
            import shutil
            import tempfile

            parts = _UF_ZIP_PARTS.get(self._uf.value, [self._uf.value])
            # Merge txt files from all parts into raw_dir, grouped by file-type prefix
            seen: set[str] = set()
            for stem in parts:
                with tempfile.TemporaryDirectory() as tmp:
                    tmp_path = Path(tmp)
                    with zipfile.ZipFile(self._work_dir / f"{stem}.zip") as z:
                        z.extractall(tmp_path)
                    for txt in sorted(tmp_path.rglob("*.txt")):
                        prefix = next(
                            (p for p in _FILE_TYPES.values() if txt.name.startswith(p)),
                            None,
                        )
                        if prefix is None:
                            continue
                        dest = raw_dir / f"{prefix}_{self._uf.value}.txt"
                        if prefix not in seen:
                            shutil.copy(txt, dest)
                            seen.add(prefix)
                        else:
                            with dest.open("ab") as out:
                                out.write(txt.read_bytes())

        result: dict[str, Path] = {}
        for name, prefix in _FILE_TYPES.items():
            parquet_path = parsed_dir / f"{name}.parquet"
            if parquet_path.exists():
                result[name] = parquet_path
                continue

            matches = list(raw_dir.glob(f"{prefix}_*.txt"))
            if not matches:
                continue

            layout = pd.read_csv(_LAYOUT_DIR / f"{name}.csv")
            colspecs, var_names, dtypes = _fwf_params(layout)
            dec_cols = {
                row["variable"]: 10 ** int(float(row["decimals"]))
                for _, row in layout.iterrows()
                if str(row["decimals"]).strip() not in ("", "nan")
            }

            reader = pd.read_fwf(
                matches[0],
                colspecs=colspecs,
                names=var_names,
                header=None,
                encoding="latin-1",
                chunksize=100_000,
            )
            writer: pq.ParquetWriter | None = None
            tmp_path = parquet_path.with_suffix(".tmp.parquet")
            try:
                for chunk in reader:
                    chunk = chunk.astype(dtypes)
                    for col, divisor in dec_cols.items():
                        chunk[col] /= divisor
                    table = pa.Table.from_pandas(chunk, preserve_index=False)
                    if writer is None:
                        writer = pq.ParquetWriter(tmp_path, table.schema, compression="snappy")
                    writer.write_table(table)
            finally:
                if writer:
                    writer.close()
            tmp_path.rename(parquet_path)
            result[name] = parquet_path

        return result

    def map_variables(self, parsed_data: dict[str, Path]) -> dict[str, Path]:
        mapped_dir = self._work_dir / self._uf.value / "mapped"
        mapped_dir.mkdir(parents=True, exist_ok=True)

        result: dict[str, Path] = {}
        for name, parquet_path in parsed_data.items():
            mapped_path = mapped_dir / f"{name}.parquet"
            if mapped_path.exists():
                result[name] = mapped_path
                continue

            layout = pd.read_csv(_LAYOUT_DIR / f"{name}.csv")
            rename_map = {
                row["variable"]: (_to_snake(row["description"]) or row["variable"].lower())
                for _, row in layout.iterrows()
            }

            df = pd.read_parquet(parquet_path)
            df = df.rename(columns=rename_map)
            df.to_parquet(mapped_path, index=False, compression="snappy")
            result[name] = mapped_path

        return result
