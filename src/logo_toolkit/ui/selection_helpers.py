from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QTableWidgetItem

from logo_toolkit.core.models import matches_common_aspect_ratio


RATIO_FILTER_OPTIONS: list[tuple[str, str]] = [
    ("全部比例", "all"),
    ("16:9", "16:9"),
    ("9:16", "9:16"),
    ("1:1", "1:1"),
    ("4:5", "4:5"),
]


def populate_ratio_filter_combo(combo: QComboBox) -> None:
    combo.clear()
    for label, value in RATIO_FILTER_OPTIONS:
        combo.addItem(label, value)


def build_check_item(checked: bool = True) -> QTableWidgetItem:
    item = QTableWidgetItem()
    item.setFlags(
        Qt.ItemFlag.ItemIsUserCheckable
        | Qt.ItemFlag.ItemIsEnabled
        | Qt.ItemFlag.ItemIsSelectable
    )
    item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
    return item


def ratio_matches(width: int | None, height: int | None, ratio_filter: str) -> bool:
    if ratio_filter == "all":
        return True
    return matches_common_aspect_ratio(width, height, ratio_filter)
