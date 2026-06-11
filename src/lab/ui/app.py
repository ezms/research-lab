import sys

from pydantic import BaseModel
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget

from lab.platform.research.manifest import OutputType, ResearchManifest


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Research Lab")
        self.resize(1200, 800)

        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        from lab.ui.catalog import CatalogWidget

        self._catalog = CatalogWidget(on_select=self._open_form)
        self._stack.addWidget(self._catalog)

    def _open_form(self, manifest_cls: type[ResearchManifest]) -> None:
        from lab.ui.form import FormWidget

        form = FormWidget(
            manifest_cls=manifest_cls,
            on_execute=self._run_research,
            on_back=lambda: self._stack.setCurrentWidget(self._catalog),
        )
        self._push(form)

    def _run_research(
        self,
        manifest_cls: type[ResearchManifest],
        params: BaseModel,
        output_type: OutputType,
    ) -> None:
        from lab.ui.output import OutputWidget

        out = OutputWidget(
            manifest_cls=manifest_cls,
            params=params,
            output_type=output_type,
            on_back=lambda: self._stack.setCurrentWidget(self._catalog),
        )
        self._push(out)

    def _push(self, widget: QStackedWidget) -> None:
        self._stack.addWidget(widget)
        self._stack.setCurrentWidget(widget)


def run() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    _apply_dark_palette(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


def _apply_dark_palette(app: QApplication) -> None:
    palette = QPalette()
    c = palette.setColor
    Cr = QPalette.ColorRole
    c(Cr.Window, QColor(30, 30, 46))
    c(Cr.WindowText, QColor(205, 214, 244))
    c(Cr.Base, QColor(24, 24, 37))
    c(Cr.AlternateBase, QColor(30, 30, 46))
    c(Cr.ToolTipBase, QColor(24, 24, 37))
    c(Cr.ToolTipText, QColor(205, 214, 244))
    c(Cr.Text, QColor(205, 214, 244))
    c(Cr.Button, QColor(49, 50, 68))
    c(Cr.ButtonText, QColor(205, 214, 244))
    c(Cr.BrightText, QColor(235, 160, 172))
    c(Cr.Link, QColor(137, 180, 250))
    c(Cr.Highlight, QColor(137, 180, 250))
    c(Cr.HighlightedText, QColor(24, 24, 37))
    app.setPalette(palette)
