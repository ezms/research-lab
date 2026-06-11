import os
from pathlib import Path

from lab.enums.uf import UF
from lab.research.housing_reality.params import HousingRealityParams
from lab.research.housing_reality.sources.census_2010 import Census2010DataSource


def find_local_results(params: HousingRealityParams) -> dict[str, dict[str, Path]] | None:
    """Returns mapped parquet paths for whichever requested UFs exist locally.
    Returns None only if no UF has local data at all."""
    work_dir = Path(os.environ.get("RESEARCH_LAB_DATA_DIR", "data")) / "census_2010"
    ufs = params.ufs or list(UF)
    results: dict[str, dict[str, Path]] = {}
    for uf in ufs:
        mapped_dir = work_dir / uf.value / "mapped"
        if not mapped_dir.exists():
            continue
        files = {p.stem: p for p in mapped_dir.glob("*.parquet")}
        if files:
            results[uf.value] = files
    return results or None


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
