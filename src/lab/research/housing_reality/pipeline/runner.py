import os
from pathlib import Path

from lab.enums.uf import UF
from lab.research.housing_reality.params import HousingRealityParams
from lab.research.housing_reality.sources.census_2010 import Census2010DataSource


def run(params: HousingRealityParams) -> dict[str, dict[str, Path]]:
    work_dir = Path(os.environ.get("RESEARCH_LAB_DATA_DIR", "data")) / "census_2010"
    ufs = params.ufs or list(UF)
    results: dict[str, dict[str, Path]] = {}

    for uf in ufs:
        source = Census2010DataSource(uf=uf, work_dir=work_dir)
        zip_path = source.download()
        parsed = source.parse(zip_path)
        results[uf.value] = source.map_variables(parsed)

    return results
