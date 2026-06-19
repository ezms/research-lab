"""Minimal forward-only migration runner for DuckDB.

Applies numbered `*.sql` files in order, tracking applied versions in a
`schema_migrations` table. No rollback — just add a new migration to change schema.
"""
import logging
from pathlib import Path

from lab.infrastructure.database.duckdb_adapter import DuckDBAdapter

_log = logging.getLogger(__name__)
_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def apply_migrations(db: DuckDBAdapter, migrations_dir: Path = _MIGRATIONS_DIR) -> list[str]:
    """Apply pending migrations in filename order. Returns the versions applied.

    Each file is run as a whole — DuckDB parses multi-statement scripts natively
    (no hand-rolled SQL splitting).
    """
    db.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version VARCHAR PRIMARY KEY, applied_at TIMESTAMP DEFAULT now())"
    )
    applied = set(db.query("SELECT version FROM schema_migrations")["version"])

    done: list[str] = []
    for path in sorted(migrations_dir.glob("*.sql")):
        version = path.stem
        if version in applied:
            continue
        db.execute(path.read_text(encoding="utf-8"))
        db.execute(f"INSERT INTO schema_migrations (version) VALUES ('{version}')")
        _log.info("applied migration %s", version)
        done.append(version)
    return done


if __name__ == "__main__":
    from lab.infrastructure.research.duckdb_repository import make_db

    logging.basicConfig(level=logging.INFO)
    applied = apply_migrations(make_db())
    print(f"Migrations aplicadas: {applied or 'nenhuma (banco já atualizado)'}")
