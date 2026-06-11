import json
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

import pandas as pd
from pydantic import BaseModel
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
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
        self._save_worker: SaveWorker | None = None
        self._results: dict = {}
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

        self._status = QLabel("Executando pesquisa…")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._root.addWidget(self._status, 1)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # indeterminate
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(4)
        self._progress.setStyleSheet(
            "QProgressBar { background: #313244; border: none; border-radius: 2px; }"
            "QProgressBar::chunk { background: #89b4fa; border-radius: 2px; }"
        )
        self._root.addWidget(self._progress)

        self._cancel_btn = QPushButton("Interromper")
        self._cancel_btn.setStyleSheet(_BTN_CANCEL_STYLE)
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.clicked.connect(self._cancel)
        self._root.addWidget(self._cancel_btn, 0, Qt.AlignmentFlag.AlignCenter)

    def _start(self, params: BaseModel) -> None:
        self._worker = ResearchWorker(self._manifest_cls, params)
        self._worker.finished.connect(self._on_finished)
        self._worker.errored.connect(self._on_error)
        self._worker.start()

    def _cancel(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
        self._progress.setVisible(False)
        self._cancel_btn.setVisible(False)
        self._status.setText("Processo interrompido.")

    def _on_finished(self, results: dict) -> None:
        self._results = results
        self._progress.setVisible(False)
        self._cancel_btn.setVisible(False)

        if self._output_type == OutputType.NOTEBOOK:
            self._open_notebook(results)
            return

        self._root.removeWidget(self._status)
        self._status.deleteLater()

        if self._output_type == OutputType.TABLE:
            self._root.addWidget(self._build_table(results), 1)
        elif self._output_type == OutputType.CHART:
            self._root.addWidget(self._build_chart(results), 1)
        else:
            self._root.addWidget(QLabel("Tipo de saída não suportado."), 1)

        self._add_save_row()

    def _on_error(self, message: str) -> None:
        self._progress.setVisible(False)
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

    def _build_table(self, results: dict[str, dict[str, Path]]) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(12)

        for uf, files in results.items():
            for file_type, path in files.items():
                label = QLabel(f"{uf} — {file_type}")
                label.setStyleSheet("font-weight: bold; color: #89b4fa;")
                layout.addWidget(label)

                df = pd.read_parquet(path)
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

    def _build_chart(self, results: dict[str, dict[str, Path]]) -> QWidget:
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        ufs: list[str] = []
        counts: list[int] = []
        for uf, files in results.items():
            if "domicilios" in files:
                ufs.append(uf)
                counts.append(len(pd.read_parquet(files["domicilios"])))

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
