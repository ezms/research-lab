from pathlib import Path

import duckdb
import pandas as pd

from lab.platform.database.port import DatabasePort


class DuckDBAdapter(DatabasePort):
    def __init__(
        self,
        db_path: Path | None = None,
        connection_string: str | None = None,
    ) -> None:
        if connection_string:
            self._conn = duckdb.connect(connection_string)
        elif db_path:
            self._conn = duckdb.connect(str(db_path))
        else:
            self._conn = duckdb.connect(":memory:")

    def query(self, sql: str) -> pd.DataFrame:
        return self._conn.execute(sql).df()

    def execute(self, sql: str) -> None:
        self._conn.execute(sql)
