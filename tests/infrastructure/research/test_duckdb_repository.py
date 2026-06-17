from pathlib import Path

import pandas as pd
import pytest

from lab.infrastructure.database.duckdb_adapter import DuckDBAdapter
from lab.infrastructure.research.duckdb_repository import (
    _BATCH_SIZE,
    DuckDBResearchRepository,
    _table,
)
from lab.platform.research.repository import ResearchRepository


@pytest.fixture()
def repo() -> DuckDBResearchRepository:
    return DuckDBResearchRepository(DuckDBAdapter())  # in-memory


@pytest.fixture()
def parquet_file(tmp_path: Path) -> Path:
    path = tmp_path / "test.parquet"
    pd.DataFrame({"a": [1, 2], "b": ["x", "y"]}).to_parquet(path)
    return path


@pytest.fixture()
def large_parquet_file(tmp_path: Path) -> Path:
    n = _BATCH_SIZE + 1  # forces at least 2 batches
    path = tmp_path / "large.parquet"
    pd.DataFrame({"id": range(n), "v": ["x"] * n}).to_parquet(path)
    return path


def test_is_research_repository():
    assert issubclass(DuckDBResearchRepository, ResearchRepository)


def test_table_name_format():
    assert _table("housing_reality", "SP", "domicilios") == "housing_reality_sp_domicilios"


def test_table_name_lowercases_uf():
    assert _table("my_research", "AC", "pessoas") == "my_research_ac_pessoas"


def test_is_saved_returns_false_when_not_saved(repo: DuckDBResearchRepository):
    assert repo.is_saved("housing_reality", "AC", "domicilios") is False


def test_save_creates_table(repo: DuckDBResearchRepository, parquet_file: Path):
    repo.save("housing_reality", "AC", "domicilios", parquet_file)
    assert repo.is_saved("housing_reality", "AC", "domicilios") is True


def test_save_persists_data(repo: DuckDBResearchRepository, parquet_file: Path):
    repo.save("housing_reality", "AC", "domicilios", parquet_file)
    df = repo._db.query("SELECT * FROM housing_reality_ac_domicilios ORDER BY a")
    assert len(df) == 2
    assert list(df.columns) == ["a", "b"]


def test_save_is_idempotent(repo: DuckDBResearchRepository, parquet_file: Path):
    repo.save("housing_reality", "AC", "domicilios", parquet_file)
    repo.save("housing_reality", "AC", "domicilios", parquet_file)  # count matches — skipped
    df = repo._db.query("SELECT * FROM housing_reality_ac_domicilios")
    assert len(df) == 2  # no duplicate rows


def test_different_ufs_are_independent(repo: DuckDBResearchRepository, parquet_file: Path):
    repo.save("housing_reality", "AC", "domicilios", parquet_file)
    assert repo.is_saved("housing_reality", "AC", "domicilios") is True
    assert repo.is_saved("housing_reality", "SP", "domicilios") is False


def test_save_batches_large_parquet(repo: DuckDBResearchRepository, large_parquet_file: Path):
    repo.save("housing_reality", "SP", "pessoas", large_parquet_file)
    count = int(repo._db.query("SELECT COUNT(*) FROM housing_reality_sp_pessoas").iloc[0, 0])
    assert count == _BATCH_SIZE + 1


def test_save_recovers_from_partial_write(repo: DuckDBResearchRepository, parquet_file: Path):
    table = _table("housing_reality", "AC", "domicilios")
    # Simulate a partial save: table exists but has only 1 of 2 rows
    repo._db.execute(
        f"CREATE TABLE {table} AS SELECT * FROM read_parquet('{parquet_file}') LIMIT 1"
    )
    repo.save("housing_reality", "AC", "domicilios", parquet_file)
    count = int(repo._db.query(f"SELECT COUNT(*) FROM {table}").iloc[0, 0])
    assert count == 2
