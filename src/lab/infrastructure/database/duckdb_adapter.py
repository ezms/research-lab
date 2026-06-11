from pathlib import Path

import duckdb
import pandas as pd

from lab.platform.database.port import DatabasePort


class DuckDBAdapter(DatabasePort):
    def __init__(self, db_path: Path | None = None) -> None:
        self._conn = duckdb.connect(str(db_path) if db_path else ":memory:")

    def query(self, sql: str) -> pd.DataFrame:
        return self._conn.execute(sql).df()

    def execute(self, sql: str) -> None:
        self._conn.execute(sql)
