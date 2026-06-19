from pathlib import Path

from lab.infrastructure.database.duckdb_adapter import DuckDBAdapter
from lab.infrastructure.database.migrations import apply_migrations


def _write(dir: Path, name: str, sql: str) -> None:
    (dir / name).write_text(sql, encoding="utf-8")


def test_applies_pending_and_is_idempotent(tmp_path: Path):
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    _write(migrations, "001_a.sql", "CREATE TABLE a (i INTEGER);")
    _write(migrations, "002_b.sql", "CREATE TABLE b (i INTEGER); CREATE TABLE c (i INTEGER);")
    db = DuckDBAdapter()  # in-memory

    first = apply_migrations(db, migrations)
    assert first == ["001_a", "002_b"]

    tables = set(db.query("SHOW TABLES")["name"])
    assert {"a", "b", "c"} <= tables  # multi-statement file applied

    # second run applies nothing
    assert apply_migrations(db, migrations) == []


def test_only_new_migration_runs(tmp_path: Path):
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    _write(migrations, "001_a.sql", "CREATE TABLE a (i INTEGER);")
    db = DuckDBAdapter()
    apply_migrations(db, migrations)

    _write(migrations, "002_b.sql", "CREATE TABLE b (i INTEGER);")
    assert apply_migrations(db, migrations) == ["002_b"]


def test_real_migration_creates_morador(tmp_path: Path):
    # the shipped migrations dir must at least create the morador table
    db = DuckDBAdapter()
    apply_migrations(db)
    cols = set(db.query("DESCRIBE morador")["column_name"])
    assert {"fonte", "ano", "uf", "peso", "sexo", "idade", "n_comodos"} <= cols
