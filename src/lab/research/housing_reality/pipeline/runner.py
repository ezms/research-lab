import logging
import os
from pathlib import Path

from lab.research.housing_reality.domain.ports import HousingDataSource
from lab.research.housing_reality.params import HousingRealityParams
from lab.research.housing_reality.sources.census_2010 import Census2010DataSource
from lab.research.housing_reality.sources.pnadc_visita1 import PNADCVisita1DataSource

_log = logging.getLogger(__name__)

_SOURCES: list[type[HousingDataSource]] = [
    Census2010DataSource,
    PNADCVisita1DataSource,
]


def _work_dir() -> Path:
    return Path(os.environ.get("RESEARCH_LAB_DATA_DIR", "data"))


def find_local_results(params: HousingRealityParams) -> dict[str, dict[str, Path]] | None:
    results: dict[str, dict[str, Path]] = {}
    for SourceClass in _SOURCES:
        local = SourceClass(_work_dir()).find_local(params)
        if local:
            for uf, files in local.items():
                results.setdefault(uf, {}).update(files)
    return results or None


def run(params: HousingRealityParams) -> dict[str, dict[str, Path]]:
    results: dict[str, dict[str, Path]] = {}
    for SourceClass in _SOURCES:
        try:
            source_results = SourceClass(_work_dir()).collect(params)
            for uf, files in source_results.items():
                results.setdefault(uf, {}).update(files)
        except Exception as exc:
            _log.error("%s falhou: %s", SourceClass.__name__, exc)
    return results
