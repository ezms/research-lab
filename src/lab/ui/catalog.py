from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from lab.platform.research.manifest import ResearchManifest
from lab.platform.research.registry import get_registry

_CARD_STYLE = """
    ResearchCard {
        background: #1e1e2e;
        border: 1px solid #313244;
        border-radius: 8px;
    }
    ResearchCard:hover {
        border: 1px solid #89b4fa;
    }
"""

_BTN_STYLE = """
    QPushButton {
        background: #89b4fa;
        color: #1e1e2e;
        border-radius: 4px;
        padding: 6px 16px;
        font-weight: bold;
    }
    QPushButton:hover { background: #b4d0ff; }
"""


class ResearchCard(QFrame):
    def __init__(self, manifest_cls: type[ResearchManifest], on_click: Callable) -> None:
        super().__init__()
        self.setObjectName("ResearchCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFixedSize(300, 180)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        title = QLabel(manifest_cls.name)
        font = QFont()
        font.setPointSize(13)
        font.setBold(True)
        title.setFont(font)
        title.setWordWrap(True)

        desc = QLabel(manifest_cls.description)
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignTop)

        btn = QPushButton("Executar")
        btn.setStyleSheet(_BTN_STYLE)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda: on_click(manifest_cls))

        layout.addWidget(title)
        layout.addWidget(desc, 1)
        layout.addWidget(btn)
        self.setStyleSheet(_CARD_STYLE)


class CatalogWidget(QWidget):
    def __init__(self, on_select: Callable[[type[ResearchManifest]], None]) -> None:
        super().__init__()
        self._on_select = on_select
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 32)
        layout.setSpacing(16)

        header = QLabel("Catálogo de Pesquisas")
        font = QFont()
        font.setPointSize(20)
        font.setBold(True)
        header.setFont(font)
        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        grid = QGridLayout(container)
        grid.setSpacing(16)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        for idx, manifest_cls in enumerate(get_registry().values()):
            card = ResearchCard(manifest_cls, on_click=self._on_select)
            grid.addWidget(card, idx // 3, idx % 3)

        scroll.setWidget(container)
        layout.addWidget(scroll, 1)
