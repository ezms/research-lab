import re
import unicodedata
import zipfile
from pathlib import Path

import httpx
import pandas as pd

from lab.enums.uf import UF
from lab.platform.data_source.contract import DataSource, SourceIdentity

_LAYOUT_DIR = Path(__file__).parent / "census_2010_layout"

_FILE_TYPES = {
    "domicilios":  "Amostra_Domicilios",
    "pessoas":     "Amostra_Pessoas",
    "emigracao":   "Amostra_Emigracao",
    "mortalidade": "Amostra_Mortalidade",
}


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

    def download(self) -> Path:
        self._work_dir.mkdir(parents=True, exist_ok=True)

        output_path = self._work_dir / f"{self._uf.value}.zip"
        if output_path.exists():
            return output_path

        url = f"{self.BASE_URL}/{self._uf.value}.zip"
        with httpx.Client() as client:
            head_response = client.head(url)
            head_response.raise_for_status()

            content_length = int(head_response.headers.get("content-length", 0))
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

    def parse(self, file_path: Path) -> dict[str, Path]:
        raw_dir = self._work_dir / self._uf.value
        parsed_dir = raw_dir / "parsed"
        parsed_dir.mkdir(parents=True, exist_ok=True)

        if not any(raw_dir.glob("*.txt")):
            with zipfile.ZipFile(file_path) as z:
                z.extractall(self._work_dir)

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

            df = pd.read_fwf(
                matches[0],
                colspecs=colspecs,
                names=var_names,
                header=None,
                encoding="latin-1",
            ).astype(dtypes)

            for _, row in layout.iterrows():
                dec_str = str(row["decimals"]).strip()
                if dec_str and dec_str != "nan":
                    df[row["variable"]] /= 10 ** int(float(dec_str))

            df.to_parquet(parquet_path, index=False, compression="snappy")
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
