import shutil
from pathlib import Path

import pandas as pd
import pytest

from lab.enums.uf import UF
from lab.research.housing_reality.sources.census_2010 import Census2010DataSource

_FIXTURES = Path(__file__).parent.parent.parent.parent / "fixtures" / "census_2010"
_FIXTURE_ROWS = 50


@pytest.fixture()
def work_dir(tmp_path: Path) -> Path:
    shutil.copytree(_FIXTURES / "AC", tmp_path / "AC")
    return tmp_path


@pytest.fixture()
def source(work_dir: Path) -> Census2010DataSource:
    return Census2010DataSource(uf=UF.AC, work_dir=work_dir)


@pytest.fixture()
def parsed(source: Census2010DataSource, work_dir: Path) -> dict[str, Path]:
    return source.parse(work_dir / "AC.zip")  # zip absent — txt files already present


class TestParse:
    def test_returns_domicilios_and_pessoas(self, parsed: dict[str, Path]):
        assert "domicilios" in parsed
        assert "pessoas" in parsed

    def test_parquets_exist_on_disk(self, parsed: dict[str, Path]):
        for path in parsed.values():
            assert path.exists()

    def test_domicilios_row_count(self, parsed: dict[str, Path]):
        df = pd.read_parquet(parsed["domicilios"])
        assert len(df) == _FIXTURE_ROWS

    def test_domicilios_column_count(self, parsed: dict[str, Path]):
        df = pd.read_parquet(parsed["domicilios"])
        assert len(df.columns) == 76

    def test_pessoas_column_count(self, parsed: dict[str, Path]):
        df = pd.read_parquet(parsed["pessoas"])
        assert len(df.columns) == 244

    def test_decimal_scaling_applied_to_weight(self, parsed: dict[str, Path]):
        df = pd.read_parquet(parsed["domicilios"])
        # V0010 (peso amostral) must be < 1000 after dividing by 10^13
        assert float(df["V0010"].max()) < 1000

    def test_is_idempotent(self, source: Census2010DataSource, work_dir: Path, parsed: dict[str, Path]):
        result2 = source.parse(work_dir / "AC.zip")
        assert result2 == parsed


class TestMapVariables:
    def test_returns_same_keys(self, source: Census2010DataSource, parsed: dict[str, Path]):
        mapped = source.map_variables(parsed)
        assert set(mapped.keys()) == set(parsed.keys())

    def test_columns_renamed(self, source: Census2010DataSource, parsed: dict[str, Path]):
        mapped = source.map_variables(parsed)
        df = pd.read_parquet(mapped["domicilios"])
        assert "unidade_da_federacao" in df.columns
        assert "V0001" not in df.columns

    def test_row_count_unchanged(self, source: Census2010DataSource, parsed: dict[str, Path]):
        mapped = source.map_variables(parsed)
        df = pd.read_parquet(mapped["domicilios"])
        assert len(df) == _FIXTURE_ROWS

    def test_is_idempotent(self, source: Census2010DataSource, parsed: dict[str, Path]):
        mapped1 = source.map_variables(parsed)
        mapped2 = source.map_variables(parsed)
        assert mapped1 == mapped2
