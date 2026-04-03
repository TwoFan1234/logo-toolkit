from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from logo_toolkit.tools.registry import build_tool_registry


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Logo Toolkit")
        self.resize(1400, 900)
        self._tool_widgets: dict[str, QWidget] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(16)

        header = QFrame()
        header.setObjectName("headerFrame")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(20, 16, 20, 16)

        title = QLabel("Logo Toolkit")
        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title.setFont(title_font)

        subtitle = QLabel("可扩展的图片批处理桌面工具集")
        subtitle.setObjectName("subtitleLabel")

        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        root_layout.addWidget(header)

        body_layout = QHBoxLayout()
        body_layout.setSpacing(16)

        self.tool_list = QListWidget()
        self.tool_list.setFixedWidth(240)
        self.tool_list.setSpacing(6)
        self.tool_list.currentRowChanged.connect(self._handle_tool_change)

        self.stack = QStackedWidget()
        self.stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        for definition in build_tool_registry():
            item = QListWidgetItem(definition.title)
            item.setData(Qt.ItemDataRole.UserRole, definition.tool_id)
            item.setToolTip(definition.description)
            self.tool_list.addItem(item)
            widget = definition.factory()
            self._tool_widgets[definition.tool_id] = widget
            self.stack.addWidget(widget)

        body_layout.addWidget(self.tool_list)
        body_layout.addWidget(self.stack, stretch=1)
        root_layout.addLayout(body_layout)

        self.setCentralWidget(root)
        self.tool_list.setCurrentRow(0)
        self._apply_styles()

    def _handle_tool_change(self, row: int) -> None:
        if row >= 0:
            self.stack.setCurrentIndex(row)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #f5f1e7;
            }
            #headerFrame {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #f6e7cb,
                    stop: 1 #d6e8dd
                );
                border-radius: 18px;
                border: 1px solid #d8c8a8;
            }
            #subtitleLabel {
                color: #5f5748;
            }
            QListWidget {
                background: #fff9ef;
                border: 1px solid #d8c8a8;
                border-radius: 16px;
                padding: 12px;
            }
            QListWidget::item {
                padding: 12px;
                border-radius: 10px;
            }
            QListWidget::item:selected {
                background: #e7dbc3;
                color: #2f2a20;
            }
            """
        )
