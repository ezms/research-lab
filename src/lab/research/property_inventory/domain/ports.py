from abc import ABC, abstractmethod
from pathlib import Path

from lab.research.property_inventory.params import PropertyInventoryParams


class PropertyDataSource(ABC):
    @abstractmethod
    def collect(self, params: PropertyInventoryParams) -> dict[str, Path]:
        """Collect listings. Returns {uf_abbr: parquet_path}."""

    @abstractmethod
    def find_local(self, params: PropertyInventoryParams) -> dict[str, Path] | None:
        """Return already-collected local results, or None if nothing collected yet."""
