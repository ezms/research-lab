from abc import ABC, abstractmethod
from pathlib import Path

from lab.research.housing_reality.params import HousingRealityParams


class HousingDataSource(ABC):
    @abstractmethod
    def collect(self, params: HousingRealityParams) -> dict[str, dict[str, Path]]:
        """Collect data. Returns {uf_abbr: {file_type: parquet_path}}."""

    @abstractmethod
    def find_local(self, params: HousingRealityParams) -> dict[str, dict[str, Path]] | None:
        """Return already-collected local results, or None if nothing collected yet."""
