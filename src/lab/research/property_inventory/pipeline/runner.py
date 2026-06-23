import logging
import os
from pathlib import Path

from lab.research.property_inventory.domain.ports import PropertyDataSource
from lab.research.property_inventory.params import PropertyInventoryParams
from lab.research.property_inventory.sources.ml_imoveis import MLImoveisDataSource

_log = logging.getLogger(__name__)

_SOURCES: dict[str, type[PropertyDataSource]] = {
    "ml_imoveis": MLImoveisDataSource,
}


def _work_dir() -> Path:
    return Path(os.environ.get("RESEARCH_LAB_DATA_DIR", "data"))


def find_local_results(params: PropertyInventoryParams) -> dict[str, Path] | None:
    return _SOURCES[params.source](_work_dir()).find_local(params)


def run(params: PropertyInventoryParams) -> dict[str, Path]:
    return _SOURCES[params.source](_work_dir()).collect(params)
