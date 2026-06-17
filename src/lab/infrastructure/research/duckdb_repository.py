import os
from pathlib import Path

import duckdb

from lab.infrastructure.database.duckdb_adapter import DuckDBAdapter
from lab.platform.research.repository import ResearchRepository

_BATCH_SIZE = 50_000


def _table(manifest_id: str, uf: str, file_type: str) -> str:
    return f"{manifest_id}_{uf.lower()}_{file_type}".replace("-", "_")


class DuckDBResearchRepository(ResearchRepository):
    def __init__(self, db: DuckDBAdapter) -> None:
        self._db = db

    def save(self, manifest_id: str, uf: str, file_type: str, parquet_path: Path) -> None:
        table = _table(manifest_id, uf, file_type)
        # Create table with correct schema but no rows — avoids UPLOAD_BRIDGE_DATA timeout
        self._db.execute(
            f"CREATE TABLE IF NOT EXISTS {table} "
            f"AS SELECT * FROM read_parquet('{parquet_path}') LIMIT 0"
        )
        expected = int(
            self._db.query(f"SELECT COUNT(*) FROM read_parquet('{parquet_path}')").iloc[0, 0]
        )
        actual = int(self._db.query(f"SELECT COUNT(*) FROM {table}").iloc[0, 0])
        if actual == expected:
            return
        if actual > 0:
            # Partial save from a previous interrupted attempt — reset
            self._db.execute(f"DELETE FROM {table}")
        for offset in range(0, expected, _BATCH_SIZE):
            self._db.execute(
                f"INSERT INTO {table} "
                f"SELECT * FROM read_parquet('{parquet_path}') "
                f"LIMIT {_BATCH_SIZE} OFFSET {offset}"
            )

    def is_saved(self, manifest_id: str, uf: str, file_type: str) -> bool:
        table = _table(manifest_id, uf, file_type)
        result = self._db.query(
            f"SELECT COUNT(0) FROM information_schema.tables "
            f"WHERE table_name = '{table}'"
        )
        return int(result.iloc[0, 0]) > 0


def make_repository() -> DuckDBResearchRepository:
    token = os.environ.get("MOTHERDUCK_TOKEN")
    if token:
        bootstrap = duckdb.connect(f"md:?motherduck_token={token}")
        bootstrap.execute("CREATE DATABASE IF NOT EXISTS research")
        bootstrap.close()
        db = DuckDBAdapter(connection_string=f"md:research?motherduck_token={token}")
    else:
        db_path = Path(os.environ.get("RESEARCH_LAB_DATA_DIR", "data")) / "research.duckdb"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db = DuckDBAdapter(db_path=db_path)
    return DuckDBResearchRepository(db)
