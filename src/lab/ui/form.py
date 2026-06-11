import types
import typing
from enum import Enum
from typing import Any, Callable

from pydantic import BaseModel
from pydantic.fields import FieldInfo
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from lab.platform.research.manifest import OutputType, ResearchManifest

_BTN_BACK_STYLE = """
    QPushButton {
        background: transparent;
        color: #89b4fa;
        border: none;
        font-size: 14px;
    }
    QPushButton:hover { color: #b4d0ff; }
"""

_BTN_RUN_STYLE = """
    QPushButton {
        background: #a6e3a1;
        color: #1e1e2e;
        border-radius: 4px;
        padding: 8px 24px;
        font-weight: bold;
        font-size: 14px;
    }
    QPushButton:hover { background: #c3f0be; }
"""

_HINT_STYLE = "color: #6c7086; font-size: 11px;"


def _unwrap_optional(annotation: Any) -> Any:
    origin = typing.get_origin(annotation)
    is_union = origin is typing.Union or isinstance(annotation, types.UnionType)
    if is_union:
        non_none = [a for a in typing.get_args(annotation) if a is not type(None)]
        if len(non_none) == 1:
            return non_none[0]
    return annotation


def _build_field(
    field_name: str, field_info: FieldInfo
) -> tuple[QWidget, Callable[[], Any], str]:
    """Return (widget, value_reader, hint_text)."""
    annotation = field_info.annotation
    inner = _unwrap_optional(annotation)
    origin = typing.get_origin(inner)

    if origin is list:
        args = typing.get_args(inner)
        item_type = args[0] if args else None
        if item_type and isinstance(item_type, type) and issubclass(item_type, Enum):
            return _enum_list_field(item_type)

    if isinstance(inner, type) and issubclass(inner, Enum):
        w = QComboBox()
        for member in inner:
            w.addItem(member.value, member)
        return w, lambda: w.currentData(), ""

    if inner is bool:
        w = QCheckBox()
        default = field_info.default
        if isinstance(default, bool):
            w.setChecked(default)
        return w, lambda: w.isChecked(), ""

    if inner is int:
        w = QSpinBox()
        w.setRange(-999_999, 999_999)
        default = field_info.default
        if isinstance(default, int):
            w.setValue(default)
        return w, lambda: w.value(), ""

    w = QLineEdit()
    default = field_info.default
    if isinstance(default, (str, float)):
        w.setText(str(default))
    return w, lambda: w.text() or None, ""


def _enum_list_field(enum_type: type[Enum]) -> tuple[QListWidget, Callable, str]:
    w = QListWidget()
    w.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
    w.setMaximumHeight(200)
    for member in enum_type:
        w.addItem(member.value)

    def read() -> list | None:
        selected = [item.text() for item in w.selectedItems()]
        return [enum_type(s) for s in selected] if selected else None

    return w, read, "Deixe vazio para selecionar todas."


def _field_label(name: str, field_info: FieldInfo) -> str:
    if field_info.title:
        return field_info.title
    return name.replace("_", " ").title()


class FormWidget(QWidget):
    def __init__(
        self,
        manifest_cls: type[ResearchManifest],
        on_execute: Callable,
        on_back: Callable,
    ) -> None:
        super().__init__()
        self._manifest_cls = manifest_cls
        self._on_execute = on_execute
        self._on_back = on_back
        self._readers: dict[str, Callable] = {}
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 24, 40, 24)
        root.setSpacing(0)

        # ── top bar ──────────────────────────────────────────────────────────
        top = QHBoxLayout()
        back_btn = QPushButton("← Voltar")
        back_btn.setStyleSheet(_BTN_BACK_STYLE)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.clicked.connect(self._on_back)
        top.addWidget(back_btn)
        top.addStretch()
        root.addLayout(top)
        root.addSpacing(8)

        # ── scrollable body ──────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(16)

        title = QLabel(self._manifest_cls.name)
        font = QFont()
        font.setPointSize(18)
        font.setBold(True)
        title.setFont(font)
        body_layout.addWidget(title)

        desc = QLabel(self._manifest_cls.description)
        desc.setWordWrap(True)
        body_layout.addWidget(desc)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #313244;")
        body_layout.addWidget(sep)

        # ── form fields ──────────────────────────────────────────────────────
        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)

        for fname, finfo in self._manifest_cls.params_model.model_fields.items():
            widget, reader, hint = _build_field(fname, finfo)
            self._readers[fname] = reader
            label = _field_label(fname, finfo)
            field_col = QVBoxLayout()
            field_col.setSpacing(4)
            field_col.addWidget(widget)
            if hint:
                hint_lbl = QLabel(hint)
                hint_lbl.setStyleSheet(_HINT_STYLE)
                field_col.addWidget(hint_lbl)
            form_layout.addRow(label, field_col)

        body_layout.addLayout(form_layout)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #313244;")
        body_layout.addWidget(sep2)

        # ── output type ──────────────────────────────────────────────────────
        output_form = QFormLayout()
        self._output_combo = QComboBox()
        for ot in self._manifest_cls.output_types:
            self._output_combo.addItem(ot.value.capitalize(), ot)
        output_form.addRow("Tipo de saída", self._output_combo)
        body_layout.addLayout(output_form)

        body_layout.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        # ── execute button ───────────────────────────────────────────────────
        root.addSpacing(16)
        run_btn = QPushButton("Executar")
        run_btn.setStyleSheet(_BTN_RUN_STYLE)
        run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        run_btn.clicked.connect(self._execute)
        root.addWidget(run_btn, 0, Qt.AlignmentFlag.AlignRight)

    def _execute(self) -> None:
        values = {name: reader() for name, reader in self._readers.items()}
        params = self._manifest_cls.params_model(**values)
        output_type: OutputType = self._output_combo.currentData()
        self._on_execute(self._manifest_cls, params, output_type)
