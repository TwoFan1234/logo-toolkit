from __future__ import annotations

from PySide6.QtCore import Qt
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
        self.resize(1320, 820)
        self._tool_widgets: dict[str, QWidget] = {}
        self._tool_descriptions: dict[str, str] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(0)

        body_layout = QHBoxLayout()
        body_layout.setSpacing(14)

        sidebar = QFrame()
        sidebar.setObjectName("sidebarFrame")
        sidebar.setFixedWidth(272)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(18, 18, 18, 18)
        sidebar_layout.setSpacing(12)

        section_label = QLabel("工具导航")
        section_label.setObjectName("sidebarTitleLabel")

        section_copy = QLabel("先选任务，再在右侧完成参数设置、预览和导出。")
        section_copy.setObjectName("sidebarCopyLabel")
        section_copy.setWordWrap(True)

        self.tool_list = QListWidget()
        self.tool_list.setObjectName("toolList")
        self.tool_list.setSpacing(6)
        self.tool_list.currentRowChanged.connect(self._handle_tool_change)

        self.tool_description = QLabel()
        self.tool_description.setObjectName("toolDescriptionLabel")
        self.tool_description.setWordWrap(True)

        helper_card = QFrame()
        helper_card.setObjectName("helperCard")
        helper_layout = QVBoxLayout(helper_card)
        helper_layout.setContentsMargins(14, 14, 14, 14)
        helper_layout.setSpacing(6)
        helper_title = QLabel("使用建议")
        helper_title.setObjectName("helperTitleLabel")
        helper_copy = QLabel("先拖入一批图片，再选择 Logo，在预览区调好位置后统一导出。")
        helper_copy.setObjectName("helperCopyLabel")
        helper_copy.setWordWrap(True)
        helper_layout.addWidget(helper_title)
        helper_layout.addWidget(helper_copy)

        sidebar_layout.addWidget(section_label)
        sidebar_layout.addWidget(section_copy)
        sidebar_layout.addWidget(self.tool_list, stretch=1)
        sidebar_layout.addWidget(self.tool_description)
        sidebar_layout.addWidget(helper_card)

        content_frame = QFrame()
        content_frame.setObjectName("contentFrame")
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(14, 14, 14, 14)
        content_layout.setSpacing(0)

        self.stack = QStackedWidget()
        self.stack.setObjectName("toolStack")
        self.stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        content_layout.addWidget(self.stack)

        for definition in build_tool_registry():
            item = QListWidgetItem(definition.title)
            item.setData(Qt.ItemDataRole.UserRole, definition.tool_id)
            item.setToolTip(definition.description)
            self.tool_list.addItem(item)
            self._tool_descriptions[definition.tool_id] = definition.description
            widget = definition.factory()
            self._tool_widgets[definition.tool_id] = widget
            self.stack.addWidget(widget)

        body_layout.addWidget(sidebar)
        body_layout.addWidget(content_frame, stretch=1)
        root_layout.addLayout(body_layout)

        self.setCentralWidget(root)
        self.tool_list.setCurrentRow(0)
        self._apply_styles()

    def _handle_tool_change(self, row: int) -> None:
        if row >= 0:
            self.stack.setCurrentIndex(row)
            tool_id = self.tool_list.item(row).data(Qt.ItemDataRole.UserRole)
            self.tool_description.setText(self._tool_descriptions.get(str(tool_id), ""))

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #f3efe6;
            }
            #sidebarFrame {
                background: #1f312d;
                border-radius: 24px;
                border: 1px solid #314843;
            }
            #sidebarTitleLabel {
                color: #f8efe0;
                font-size: 16px;
                font-weight: 700;
            }
            #sidebarCopyLabel {
                color: #b8c7c1;
                font-size: 12px;
            }
            #toolList {
                background: rgba(255, 255, 255, 0.04);
                border: 1px solid rgba(240, 231, 218, 0.08);
                border-radius: 18px;
                padding: 10px;
                color: #f7f0e4;
                outline: none;
            }
            #toolList::item {
                background: transparent;
                padding: 12px 12px;
                border-radius: 12px;
                margin: 2px 0;
                border: 1px solid transparent;
            }
            #toolList::item:hover {
                background: rgba(255, 255, 255, 0.06);
            }
            #toolList::item:selected {
                background: #f3ead8;
                color: #22312d;
                border: 1px solid #dbc8a3;
                font-weight: 700;
            }
            #toolDescriptionLabel {
                color: #c7d6cf;
                font-size: 12px;
                line-height: 1.4em;
                padding: 2px 2px 0 2px;
            }
            #helperCard {
                background: #f0e3c8;
                border-radius: 18px;
                border: 1px solid #dbc8a5;
            }
            #helperTitleLabel {
                color: #3d3429;
                font-size: 13px;
                font-weight: 700;
            }
            #helperCopyLabel {
                color: #5c5041;
                font-size: 12px;
            }
            #contentFrame {
                background: #fbf8f1;
                border-radius: 26px;
                border: 1px solid #deceb3;
            }
            #toolStack {
                background: transparent;
            }
            """
        )
