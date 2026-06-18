import logging
import os
from pathlib import Path

from lab.research.housing_reality.domain.ports import HousingDataSource
from lab.research.housing_reality.params import HousingRealityParams
from lab.research.housing_reality.sources.census_2010 import Census2010DataSource
from lab.research.housing_reality.sources.pnadc_visita1 import PNADCVisita1DataSource

_log = logging.getLogger(__name__)

_SOURCES: dict[str, type[HousingDataSource]] = {
    "census_2010": Census2010DataSource,
    "pnadc_visita1": PNADCVisita1DataSource,
}


def _work_dir() -> Path:
    return Path(os.environ.get("RESEARCH_LAB_DATA_DIR", "data"))


def find_local_results(params: HousingRealityParams) -> dict[str, dict[str, Path]] | None:
    if params.source is None:
        raise ValueError("params.source required")
    return _SOURCES[params.source](_work_dir()).find_local(params)


def run(params: HousingRealityParams) -> dict[str, dict[str, Path]]:
    if params.source is None:
        raise ValueError("params.source required")
    return _SOURCES[params.source](_work_dir()).collect(params)
