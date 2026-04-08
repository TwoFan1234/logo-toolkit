from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
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

from logo_toolkit.app_info import APP_DISPLAY_NAME
from logo_toolkit.tools.registry import build_tool_registry
from logo_toolkit.ui.theme import apply_shadow, main_window_stylesheet


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_DISPLAY_NAME)
        self.resize(1320, 820)
        self._tool_widgets: dict[str, QWidget] = {}
        self._tool_descriptions: dict[str, str] = {}
        self._tool_fade_animation: QPropertyAnimation | None = None
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
        helper_copy = QLabel("先在左侧选择工具，再导入文件、设置参数并开始批量处理。")
        helper_copy.setObjectName("helperCopyLabel")
        helper_copy.setWordWrap(True)
        helper_layout.addWidget(helper_title)
        helper_layout.addWidget(helper_copy)
        apply_shadow(helper_card, blur_radius=22, y_offset=8, alpha=18)

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
        apply_shadow(sidebar, blur_radius=36, y_offset=14, alpha=20)
        apply_shadow(content_frame, blur_radius=44, y_offset=16, alpha=18)

        self.setCentralWidget(root)
        self.tool_list.setCurrentRow(0)
        self._apply_styles()

    def _handle_tool_change(self, row: int) -> None:
        if row >= 0:
            self.stack.setCurrentIndex(row)
            tool_id = self.tool_list.item(row).data(Qt.ItemDataRole.UserRole)
            self.tool_description.setText(self._tool_descriptions.get(str(tool_id), ""))
            self._fade_in_widget(self.stack.currentWidget())

    def _apply_styles(self) -> None:
        self.setStyleSheet(main_window_stylesheet())

    def _fade_in_widget(self, widget: QWidget | None) -> None:
        if widget is None:
            return
        if self._tool_fade_animation is not None:
            self._tool_fade_animation.stop()
        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(0.0)
        widget.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(180)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(lambda: widget.setGraphicsEffect(None))
        self._tool_fade_animation = animation
        animation.start()
