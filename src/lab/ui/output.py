import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

import pandas as pd
from pydantic import BaseModel
from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from lab.platform.research.manifest import OutputType, ResearchManifest
from lab.ui._pandas_model import PandasTableModel
from lab.ui._save_worker import SaveWorker
from lab.ui._worker import ResearchWorker


class _RenderWorker(QThread):
    table_ready: Signal = Signal(object)   # dict[str, dict[str, pd.DataFrame]]
    chart_ready: Signal = Signal(list, list)  # ufs, counts
    errored: Signal = Signal(str)

    def __init__(
        self,
        results: dict[str, dict[str, Path]],
        output_type: OutputType,
    ) -> None:
        super().__init__()
        self._results = results
        self._output_type = output_type

    def run(self) -> None:
        import duckdb

        try:
            if self._output_type == OutputType.TABLE:
                data: dict = {}
                for uf, files in self._results.items():
                    data[uf] = {}
                    for ft, path in files.items():
                        data[uf][ft] = duckdb.execute(
                            f"SELECT * FROM read_parquet('{path}') LIMIT 500"
                        ).df()
                self.table_ready.emit(data)
            elif self._output_type == OutputType.CHART:
                ufs, counts = [], []
                for uf, files in self._results.items():
                    if "domicilios" in files:
                        path = files["domicilios"]
                        count = duckdb.execute(
                            f"SELECT COUNT(*) FROM read_parquet('{path}')"
                        ).fetchone()[0]
                        ufs.append(uf)
                        counts.append(count)
                self.chart_ready.emit(ufs, counts)
        except Exception as exc:
            self.errored.emit(str(exc))

class _CheckSavedWorker(QThread):
    result: Signal = Signal(bool)

    def __init__(self, manifest_id: str, results: dict[str, dict[str, Path]]) -> None:
        super().__init__()
        self._manifest_id = manifest_id
        self._results = results

    def run(self) -> None:
        import os
        import duckdb

        try:
            token = os.environ.get("MOTHERDUCK_TOKEN")
            if token:
                conn = duckdb.connect(f"md:research?motherduck_token={token}")
            else:
                db_path = Path(os.environ.get("RESEARCH_LAB_DATA_DIR", "data")) / "research.duckdb"
                if not db_path.exists():
                    self.result.emit(False)
                    return
                conn = duckdb.connect(str(db_path), read_only=True)
            for uf, files in self._results.items():
                for file_type in files:
                    table = f"{self._manifest_id}_{uf.lower()}_{file_type}"
                    count = conn.execute(
                        "SELECT COUNT(*) FROM information_schema.tables "
                        f"WHERE table_name = '{table}'"
                    ).fetchone()[0]
                    if count == 0:
                        conn.close()
                        self.result.emit(False)
                        return
            conn.close()
            self.result.emit(True)
        except Exception:
            self.result.emit(False)


_BTN_BACK_STYLE = """
    QPushButton {
        background: transparent;
        color: #89b4fa;
        border: none;
        font-size: 14px;
    }
    QPushButton:hover { color: #b4d0ff; }
"""

_BTN_CANCEL_STYLE = """
    QPushButton {
        background: #f38ba8;
        color: #1e1e2e;
        border-radius: 4px;
        padding: 6px 20px;
        font-weight: bold;
    }
    QPushButton:hover { background: #f5a0b8; }
"""

_BTN_SAVE_STYLE = """
    QPushButton {
        background: #a6e3a1;
        color: #1e1e2e;
        border-radius: 4px;
        padding: 8px 24px;
        font-weight: bold;
    }
    QPushButton:hover { background: #c3f0be; }
    QPushButton:disabled { background: #45475a; color: #6c7086; }
"""

_BTN_DONE_STYLE = """
    QPushButton {
        background: #89b4fa;
        color: #1e1e2e;
        border-radius: 4px;
        padding: 12px 40px;
        font-weight: bold;
        font-size: 14px;
    }
    QPushButton:hover { background: #b4d0ff; }
"""


class OutputWidget(QWidget):
    def __init__(
        self,
        manifest_cls: type[ResearchManifest],
        params: BaseModel,
        output_type: OutputType,
        on_back: Callable,
    ) -> None:
        super().__init__()
        self._manifest_cls = manifest_cls
        self._output_type = output_type
        self._on_back = on_back
        self._worker: ResearchWorker | None = None
        self._render_worker: _RenderWorker | None = None
        self._save_worker: SaveWorker | None = None
        self._check_saved_worker: _CheckSavedWorker | None = None
        self._results: dict = {}
        self._anim_value: int = 0
        self._anim_dir: int = 1
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(500)
        self._anim_timer.timeout.connect(self._tick_progress)
        self._collect_proc: subprocess.Popen | None = None
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(1000)
        self._poll_timer.timeout.connect(self._check_collection)
        self._params = params
        self._build()
        self._start(params)

    def _build(self) -> None:
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(40, 24, 40, 24)
        self._root.setSpacing(8)

        top = QHBoxLayout()
        back_btn = QPushButton("← Voltar")
        back_btn.setStyleSheet(_BTN_BACK_STYLE)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.clicked.connect(self._on_back)
        top.addWidget(back_btn)
        top.addStretch()
        self._root.addLayout(top)

        title = QLabel(self._manifest_cls.name)
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        self._root.addWidget(title)

        self._status_base = "Executando pesquisa"
        self._status = QLabel(self._status_base + "…")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._root.addWidget(self._status, 1)

        self._anim_timer.start()

        self._cancel_btn = QPushButton("Interromper")
        self._cancel_btn.setStyleSheet(_BTN_CANCEL_STYLE)
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.clicked.connect(self._cancel)
        self._root.addWidget(self._cancel_btn, 0, Qt.AlignmentFlag.AlignCenter)

    def _tick_progress(self) -> None:
        self._anim_value = (self._anim_value + 1) % 4
        dots = "." * self._anim_value
        self._status.setText(self._status_base + dots)

    def _stop_progress(self) -> None:
        self._anim_timer.stop()

    def _start(self, params: BaseModel) -> None:
        local = self._manifest_cls.local_results(params)
        if local:
            self._stop_progress()
            self._on_finished(local)
        else:
            self._show_collect_prompt()

    def _show_collect_prompt(self) -> None:
        self._stop_progress()
        self._cancel_btn.setVisible(False)
        self._status.setText("Dados não coletados para as UFs selecionadas.")
        collect_btn = QPushButton("Coletar em background")
        collect_btn.setStyleSheet(_BTN_SAVE_STYLE)
        collect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        collect_btn.clicked.connect(lambda: self._start_background_collection(collect_btn))
        self._root.addWidget(collect_btn, 0, Qt.AlignmentFlag.AlignCenter)

    def _start_background_collection(self, collect_btn: QPushButton) -> None:
        collect_btn.setVisible(False)
        payload = json.dumps({
            "manifest": f"{self._manifest_cls.__module__}:{self._manifest_cls.__qualname__}",
            "params": self._params.model_dump(mode="json"),
        }).encode()
        self._collect_proc = subprocess.Popen(
            [sys.executable, "-m", "lab.ui._pipeline_runner"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        self._collect_proc.stdin.write(payload)
        self._collect_proc.stdin.close()
        self._status_base = "Coletando dados em background"
        self._status.setText(self._status_base + "…")
        self._status.setStyleSheet("color: #cdd6f4;")
        hint = QLabel("Você pode navegar livremente — os dados estarão disponíveis ao voltar.")
        hint.setStyleSheet("color: #6c7086; font-size: 11px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._root.addWidget(hint)
        self._anim_timer.start()
        self._poll_timer.start()

    def _check_collection(self) -> None:
        if self._collect_proc is None or self._collect_proc.poll() is None:
            return
        self._poll_timer.stop()
        self._stop_progress()
        if self._collect_proc.returncode == 0:
            local = self._manifest_cls.local_results(self._params)
            if local:
                self._on_finished(local)
            else:
                self._status.setText("Coleta concluída mas dados não encontrados.")
        else:
            err = self._collect_proc.stderr.read().decode()
            self._status.setText(f"Erro na coleta: {err}")
            self._status.setStyleSheet("color: #f38ba8;")

    def _cancel(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
        if self._render_worker and self._render_worker.isRunning():
            self._render_worker.terminate()
        if self._collect_proc and self._collect_proc.poll() is None:
            self._collect_proc.terminate()
        self._poll_timer.stop()
        self._stop_progress()
        self._cancel_btn.setVisible(False)
        self._status.setText("Processo interrompido.")

    def _on_finished(self, results: dict) -> None:
        self._results = results

        if self._output_type == OutputType.NOTEBOOK:
            self._stop_progress()
            self._cancel_btn.setVisible(False)
            self._open_notebook(results)
            return

        self._status_base = "Preparando visualização"
        self._status.setText(self._status_base + "…")
        self._render_worker = _RenderWorker(results, self._output_type)
        self._render_worker.table_ready.connect(self._on_table_ready)
        self._render_worker.chart_ready.connect(self._on_chart_ready)
        self._render_worker.errored.connect(self._on_error)
        self._render_worker.start()

    def _on_table_ready(self, data: object) -> None:
        self._stop_progress()
        self._cancel_btn.setVisible(False)
        self._root.removeWidget(self._status)
        self._status.deleteLater()
        self._root.addWidget(self._build_table(data), 1)  # type: ignore[arg-type]
        self._add_save_row()

    def _on_chart_ready(self, ufs: list, counts: list) -> None:
        self._stop_progress()
        self._cancel_btn.setVisible(False)
        self._root.removeWidget(self._status)
        self._status.deleteLater()
        self._root.addWidget(self._build_chart(ufs, counts), 1)
        self._add_save_row()

    def _on_error(self, message: str) -> None:
        self._stop_progress()
        self._cancel_btn.setVisible(False)
        self._status.setText(f"Erro: {message}")
        self._status.setStyleSheet("color: #f38ba8;")

    # ── SAVE ───────────────────────────────────────────────────────────────

    def _add_save_row(self) -> None:
        self._save_btn = QPushButton("Salvar Dados")
        self._save_btn.setStyleSheet(_BTN_SAVE_STYLE)
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.clicked.connect(self._save_data)
        self._save_label = QLabel("")
        self._save_label.setStyleSheet("color: #a6e3a1; font-size: 12px;")

        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(self._save_label)
        row.addWidget(self._save_btn)
        self._root.addLayout(row)

        self._check_saved_worker = _CheckSavedWorker(
            self._manifest_cls.id, self._results
        )
        self._check_saved_worker.result.connect(self._on_saved_check)
        self._check_saved_worker.start()

    def _on_saved_check(self, already_saved: bool) -> None:
        if already_saved:
            self._save_btn.setVisible(False)
            self._save_label.setText("✓ Dados já persistidos.")

    def _save_data(self) -> None:
        self._save_btn.setEnabled(False)
        self._save_btn.setText("Salvando…")
        self._save_label.setText("")
        self._save_worker = SaveWorker(self._manifest_cls.id, self._results)
        self._save_worker.finished.connect(self._on_saved)
        self._save_worker.errored.connect(self._on_save_error)
        self._save_worker.start()

    def _on_saved(self, message: str) -> None:
        self._save_btn.setVisible(False)
        self._save_label.setText(f"✓ {message}")

    def _on_save_error(self, message: str) -> None:
        self._save_btn.setText("Salvar Dados")
        self._save_btn.setEnabled(True)
        self._save_label.setText(f"Erro: {message}")
        self._save_label.setStyleSheet("color: #f38ba8; font-size: 12px;")

    # ── TABLE ──────────────────────────────────────────────────────────────

    def _build_table(self, data: dict[str, dict[str, pd.DataFrame]]) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(12)

        for uf, files in data.items():
            for file_type, df in files.items():
                label = QLabel(f"{uf} — {file_type}")
                label.setStyleSheet("font-weight: bold; color: #89b4fa;")
                layout.addWidget(label)

                view = QTableView()
                view.setModel(PandasTableModel(df))
                view.setAlternatingRowColors(True)
                view.horizontalHeader().setStretchLastSection(False)
                view.resizeColumnsToContents()
                view.setMinimumHeight(200)
                view.setMaximumHeight(320)
                layout.addWidget(view)

                sep = QFrame()
                sep.setFrameShape(QFrame.Shape.HLine)
                sep.setStyleSheet("color: #313244;")
                layout.addWidget(sep)

        layout.addStretch()
        scroll.setWidget(container)
        return scroll

    # ── CHART ──────────────────────────────────────────────────────────────

    def _build_chart(self, ufs: list[str], counts: list[int]) -> QWidget:
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        fig = Figure(figsize=(10, 5), tight_layout=True)
        fig.patch.set_facecolor("#1e1e2e")
        ax = fig.add_subplot(111)
        ax.set_facecolor("#181825")
        ax.bar(ufs, counts, color="#89b4fa", width=0.4)
        ax.set_xlabel("UF", color="#cdd6f4")
        ax.set_ylabel("Domicílios", color="#cdd6f4")
        ax.set_title("Domicílios por UF", color="#cdd6f4")
        ax.tick_params(colors="#cdd6f4")
        ax.margins(x=0.2)
        for spine in ax.spines.values():
            spine.set_edgecolor("#313244")

        return FigureCanvasQTAgg(fig)

    # ── NOTEBOOK ───────────────────────────────────────────────────────────

    def _open_notebook(self, results: dict[str, dict[str, Path]]) -> None:
        path = self._generate_notebook(results)
        try:
            subprocess.Popen(["jupyter", "lab", str(path)])
            self._status.setText(f"Notebook aberto em Jupyter.\n\nArquivo: {path}")
        except FileNotFoundError:
            self._status.setText(
                f"Jupyter não encontrado. Abra o arquivo manualmente:\n\n{path}"
            )

        done_btn = QPushButton("← Concluir")
        done_btn.setStyleSheet(_BTN_DONE_STYLE)
        done_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        done_btn.clicked.connect(self._on_back)
        self._root.addWidget(done_btn, 0, Qt.AlignmentFlag.AlignCenter)

    def _generate_notebook(self, results: dict[str, dict[str, Path]]) -> Path:
        cells: list[dict] = [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    f"# {self._manifest_cls.name}\n\n",
                    f"{self._manifest_cls.description}",
                ],
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": ["import pandas as pd\nimport duckdb\n"],
            },
        ]

        for uf, files in results.items():
            for file_type, path in files.items():
                varname = f"df_{uf.lower()}_{file_type}"
                cells.append(
                    {
                        "cell_type": "code",
                        "execution_count": None,
                        "metadata": {},
                        "outputs": [],
                        "source": [
                            f'{varname} = pd.read_parquet(r"{path}")\n',
                            f"{varname}.head()",
                        ],
                    }
                )

        notebook = {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {
                "kernelspec": {
                    "display_name": "Python 3",
                    "language": "python",
                    "name": "python3",
                },
                "language_info": {"name": "python", "version": "3.13"},
            },
            "cells": cells,
        }

        out = Path(tempfile.mkdtemp()) / "research_output.ipynb"
        out.write_text(json.dumps(notebook, indent=2, ensure_ascii=False))
        return out
