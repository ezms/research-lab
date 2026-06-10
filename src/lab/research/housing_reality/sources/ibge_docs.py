from pathlib import Path

import httpx

from lab.platform.data_source.contract import Downloadable, Identifiable, SourceIdentity


class IBGEDocsDataSource(Identifiable, Downloadable):
    MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB

    def __init__(self, base_url: str, research_name: str, download_dir: Path) -> None:
        self._base_url = base_url
        self._research_name = research_name
        self._download_dir = download_dir

    def identify(self) -> SourceIdentity:
        return SourceIdentity(
            name=f"Documentação - {self._research_name}",
            version="N/A",
            provider="IBGE",
            description=f"Documentação e dicionário de variáveis de {self._research_name}",
        )

    def download(self) -> Path:
        self._download_dir.mkdir(parents=True, exist_ok=True)

        output_path = self._download_dir / "Documentacao.zip"
        if output_path.exists():
            return output_path

        url = f"{self._base_url}/Documentacao.zip"
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
