from pathlib import Path

import httpx
import pandas as pd

from lab.enums.uf import UF
from lab.platform.data_source.contract import DataSource, SourceIdentity


class Census2010DataSource(DataSource):
    BASE_URL = (
        "https://ftp.ibge.gov.br/Censos/Censo_Demografico_2010"
        "/Resultados_Gerais_da_Amostra/Microdados"
    )
    MAX_FILE_SIZE_BYTES = 200 * 1024 * 1024

    def __init__(self, uf: UF, download_dir: Path) -> None:
        self._uf = uf
        self._download_dir = download_dir

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
        self._download_dir.mkdir(parents=True, exist_ok=True)

        output_path = self._download_dir / f"{self._uf.value}.zip"
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

    def parse(self, file_path: Path) -> pd.DataFrame:
        raise NotImplementedError

    def map_variables(self, raw_data: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError
