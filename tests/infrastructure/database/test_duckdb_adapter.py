from pathlib import Path

import pytest

from lab.infrastructure.database.duckdb_adapter import DuckDBAdapter
from lab.platform.database.port import DatabasePort


def test_is_database_port():
    assert issubclass(DuckDBAdapter, DatabasePort)


def test_query_returns_dataframe():
    db = DuckDBAdapter()
    df = db.query("SELECT 42 AS answer")
    assert df.iloc[0]["answer"] == 42


def test_execute_creates_table():
    db = DuckDBAdapter()
    db.execute("CREATE TABLE t AS SELECT 1 AS x, 2 AS y")
    df = db.query("SELECT * FROM t")
    assert list(df.columns) == ["x", "y"]
    assert df.iloc[0]["x"] == 1


def test_in_memory_is_default():
    db = DuckDBAdapter()
    db.execute("CREATE TABLE mem AS SELECT 'ok' AS v")
    assert db.query("SELECT v FROM mem").iloc[0]["v"] == "ok"


def test_file_based_persists_across_connections(tmp_path: Path):
    db_path = tmp_path / "test.duckdb"
    db1 = DuckDBAdapter(db_path=db_path)
    db1.execute("CREATE TABLE t AS SELECT 99 AS n")

    db2 = DuckDBAdapter(db_path=db_path)
    assert db2.query("SELECT n FROM t").iloc[0]["n"] == 99
