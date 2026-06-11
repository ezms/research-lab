import os
from pathlib import Path

from PySide6.QtCore import QThread, Signal


class SaveWorker(QThread):
    finished: Signal = Signal(str)
    errored: Signal = Signal(str)

    def __init__(self, manifest_id: str, results: dict[str, dict[str, Path]]) -> None:
        super().__init__()
        self._manifest_id = manifest_id
        self._results = results

    def run(self) -> None:
        try:
            self._persist_duckdb()
            try:
                self._upload_r2()
                self.finished.emit("Dados salvos no DuckDB e enviados ao R2.")
            except KeyError as exc:
                self.finished.emit(f"DuckDB: OK. R2 ignorado (credencial ausente: {exc}).")
            except Exception as exc:
                self.finished.emit(f"DuckDB: OK. R2 falhou: {exc}")
        except Exception as exc:
            self.errored.emit(str(exc))

    def _persist_duckdb(self) -> None:
        import duckdb

        from lab.infrastructure.database.duckdb_adapter import DuckDBAdapter

        token = os.environ.get("MOTHERDUCK_TOKEN")
        try:
            if token:
                bootstrap = duckdb.connect(f"md:?motherduck_token={token}")
                bootstrap.execute("CREATE DATABASE IF NOT EXISTS research")
                bootstrap.close()
                db = DuckDBAdapter(connection_string=f"md:research?motherduck_token={token}")
            else:
                db_path = Path(os.environ.get("RESEARCH_LAB_DATA_DIR", "data")) / "research.duckdb"
                db_path.parent.mkdir(parents=True, exist_ok=True)
                db = DuckDBAdapter(db_path=db_path)
        except duckdb.IOException:
            raise RuntimeError(
                "O banco está aberto em outro processo (ex: DBeaver). "
                "Feche a conexão e tente novamente."
            )
        for uf, files in self._results.items():
            for file_type, path in files.items():
                table = f"{self._manifest_id}_{uf.lower()}_{file_type}"
                db.execute(
                    f"CREATE OR REPLACE TABLE {table} AS "
                    f"SELECT * FROM read_parquet('{path}')"
                )

    def _upload_r2(self) -> None:
        from lab.infrastructure.storage.r2_adapter import R2Adapter

        r2 = R2Adapter()
        for uf, files in self._results.items():
            for file_type, path in files.items():
                key = f"{self._manifest_id}/{uf}/{file_type}.parquet"
                r2.upload(path, key)
