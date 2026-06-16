from abc import ABC, abstractmethod
from pathlib import Path


class ResearchRepository(ABC):
    @abstractmethod
    def save(self, manifest_id: str, uf: str, file_type: str, parquet_path: Path) -> None:
        """Persist a parquet file as a table in the database."""

    @abstractmethod
    def is_saved(self, manifest_id: str, uf: str, file_type: str) -> bool:
        """Return True if the table for this manifest/UF/file_type already exists."""
