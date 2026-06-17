import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lab.enums.uf import UF
from lab.research.housing_reality.params import HousingRealityParams
from lab.research.housing_reality.pipeline import runner

_FIXTURES = Path(__file__).parent.parent.parent.parent / "fixtures" / "census_2010"


@pytest.fixture()
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    shutil.copytree(_FIXTURES / "AC", tmp_path / "census_2010" / "AC")
    monkeypatch.setenv("RESEARCH_LAB_DATA_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture(autouse=True)
def no_pnadc_network(monkeypatch: pytest.MonkeyPatch):
    """Prevent PNADC source from making network calls in runner tests."""
    stub = MagicMock()
    stub.return_value.collect.return_value = {}
    stub.return_value.find_local.return_value = None
    monkeypatch.setattr(runner, "_SOURCES", [runner._SOURCES[0], stub])


def test_run_returns_results_per_uf(data_dir: Path):
    result = runner.run(HousingRealityParams(ufs=[UF.AC]))
    assert "AC" in result


def test_run_returns_mapped_parquet_paths(data_dir: Path):
    result = runner.run(HousingRealityParams(ufs=[UF.AC]))
    assert "domicilios" in result["AC"]
    assert result["AC"]["domicilios"].exists()


