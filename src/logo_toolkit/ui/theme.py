from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QSizePolicy, QSplitter, QWidget


def apply_shadow(widget: QWidget, blur_radius: int = 38, y_offset: int = 12, alpha: int = 16) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur_radius)
    effect.setOffset(0, y_offset)
    effect.setColor(QColor(15, 23, 42, alpha))
    widget.setGraphicsEffect(effect)


def configure_resizable_splitter(
    splitter: QSplitter,
    panels: list[QWidget],
    *,
    stretches: list[int],
    minimum_widths: list[int],
    initial_sizes: list[int],
) -> None:
    splitter.setChildrenCollapsible(False)
    splitter.setOpaqueResize(True)
    splitter.setHandleWidth(max(splitter.handleWidth(), 14))
    for index, panel in enumerate(panels):
        panel.setMinimumWidth(minimum_widths[index])
        panel.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        splitter.setCollapsible(index, False)
        splitter.setStretchFactor(index, stretches[index])
    splitter.setSizes(initial_sizes)


def main_window_stylesheet() -> str:
    return """
        QMainWindow {
            background: #f3f4f6;
            font-family: "Segoe UI Variable", "Segoe UI", "Microsoft YaHei UI";
            color: #1d1d1f;
        }
        #sidebarFrame {
            background: rgba(255, 255, 255, 0.92);
            border-radius: 30px;
            border: 1px solid rgba(15, 23, 42, 0.05);
        }
        #sidebarTitleLabel {
            color: #1d1d1f;
            font-size: 18px;
            font-weight: 720;
            letter-spacing: 0.15px;
        }
        #sidebarCopyLabel,
        #toolDescriptionLabel {
            color: #6e6e73;
            font-size: 12px;
            line-height: 1.45em;
        }
        #toolList {
            background: #f8f9fb;
            border: 1px solid rgba(15, 23, 42, 0.04);
            border-radius: 24px;
            padding: 12px;
            color: #1d1d1f;
            outline: none;
        }
        #toolList::item {
            background: transparent;
            padding: 14px 15px;
            border-radius: 18px;
            margin: 4px 0;
            border: 1px solid transparent;
        }
        #toolList::item:hover {
            background: rgba(0, 113, 227, 0.07);
            border: 1px solid rgba(0, 113, 227, 0.08);
        }
        #toolList::item:selected {
            background: #ffffff;
            color: #0071e3;
            border: 1px solid rgba(0, 113, 227, 0.14);
            font-weight: 720;
        }
        #helperCard {
            background: rgba(255, 255, 255, 0.94);
            border-radius: 24px;
            border: 1px solid rgba(15, 23, 42, 0.05);
        }
        #helperTitleLabel {
            color: #1d1d1f;
            font-size: 13px;
            font-weight: 720;
        }
        #helperCopyLabel {
            color: #6e6e73;
            font-size: 12px;
            line-height: 1.45em;
        }
        #contentFrame {
            background: rgba(255, 255, 255, 0.94);
            border-radius: 32px;
            border: 1px solid rgba(15, 23, 42, 0.05);
        }
        #toolStack {
            background: transparent;
        }
    """


def toolkit_tool_stylesheet() -> str:
    arrow_path = (Path(__file__).resolve().parent / "assets" / "chevron-down.svg").as_posix()
    return """
        QWidget {
            font-family: "Segoe UI Variable", "Segoe UI", "Microsoft YaHei UI";
            color: #1d1d1f;
            font-size: 13px;
        }
        QGroupBox {
            background: rgba(255, 255, 255, 0.95);
            border: 1px solid rgba(15, 23, 42, 0.05);
            border-radius: 22px;
            margin-top: 14px;
            padding-top: 16px;
            font-weight: 650;
            color: #1d1d1f;
        }
        QGroupBox::title {
            left: 20px;
            padding: 0 8px;
            color: #3a3a3c;
            font-weight: 700;
            background: transparent;
        }
        QPushButton {
            background: #edf2fa;
            color: #1d1d1f;
            border: 1px solid rgba(154, 170, 194, 0.45);
            border-radius: 14px;
            padding: 9px 14px;
            font-weight: 650;
            min-height: 20px;
            min-width: 72px;
        }
        QPushButton#compactButton {
            min-width: 0;
            padding: 7px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 620;
        }
        QPushButton:hover {
            background: #e3eaf6;
        }
        QPushButton:pressed {
            background: #d9e2f1;
        }
        QPushButton:disabled {
            background: #d1d1d6;
            color: #8e8e93;
            border-color: rgba(0, 0, 0, 0.04);
        }
        QPushButton#primaryRunButton {
            background: #0071e3;
            border: 1px solid rgba(0, 113, 227, 0.18);
            color: #ffffff;
            border-radius: 16px;
            font-size: 15px;
            font-weight: 750;
            padding: 14px 18px;
        }
        QPushButton#primaryRunButton:hover {
            background: #147ce5;
        }
        QPushButton#primaryRunButton:pressed {
            background: #005bb5;
        }
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
            background: #fbfbfd;
            border: 1px solid rgba(15, 23, 42, 0.10);
            border-radius: 12px;
            padding: 8px 10px;
            min-height: 20px;
            selection-background-color: #0071e3;
        }
        QComboBox {
            padding-right: 42px;
            font-weight: 600;
        }
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
            border: 1px solid #0071e3;
            background: #ffffff;
        }
        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 34px;
            margin: 2px;
            border-left: 1px solid rgba(15, 23, 42, 0.08);
            border-top-right-radius: 10px;
            border-bottom-right-radius: 10px;
            background: #f1f4f8;
        }
        QComboBox::down-arrow {
            width: 10px;
            height: 10px;
            image: url(__ARROW_PATH__);
        }
        QComboBox QAbstractItemView {
            background: #ffffff;
            border: 1px solid rgba(15, 23, 42, 0.10);
            border-radius: 12px;
            padding: 6px;
            selection-background-color: rgba(0, 113, 227, 0.12);
            selection-color: #1d1d1f;
        }
        #filterLabel {
            color: #6e6e73;
            font-size: 12px;
            font-weight: 620;
        }
        QCheckBox {
            color: #3a3a3c;
            spacing: 8px;
        }
        QLabel {
            color: #1d1d1f;
        }
        #supportingLabel {
            color: #6e6e73;
        }
        #previewCard {
            background: rgba(255, 255, 255, 0.96);
            border: 1px solid rgba(15, 23, 42, 0.05);
            border-radius: 24px;
        }
        #previewTitle {
            color: #1d1d1f;
            font-size: 18px;
            font-weight: 750;
        }
        #previewBadge {
            background: rgba(0, 113, 227, 0.10);
            color: #0071e3;
            border-radius: 999px;
            padding: 4px 10px;
            font-size: 11px;
            font-weight: 700;
        }
        #previewTips {
            background: #f7f8fa;
            border: 1px solid rgba(15, 23, 42, 0.05);
            border-radius: 16px;
            padding: 10px 12px;
            color: #6e6e73;
            font-size: 12px;
            line-height: 1.45em;
        }
        #previewImageLabel {
            background: #ffffff;
            border: 1px solid rgba(15, 23, 42, 0.05);
            border-radius: 20px;
            color: #86868b;
        }
        QTableWidget {
            background: rgba(255, 255, 255, 0.96);
            alternate-background-color: #fafbfc;
            border: 1px solid rgba(15, 23, 42, 0.05);
            border-radius: 16px;
            padding: 2px;
            gridline-color: rgba(15, 23, 42, 0.04);
            selection-background-color: rgba(0, 113, 227, 0.12);
            selection-color: #1d1d1f;
        }
        QHeaderView::section {
            background: #f7f8fa;
            color: #6e6e73;
            border: none;
            border-right: 1px solid rgba(15, 23, 42, 0.04);
            border-bottom: 1px solid rgba(15, 23, 42, 0.05);
            padding: 10px 8px;
            font-weight: 700;
        }
        QProgressBar {
            background: #e9ebef;
            border: none;
            border-radius: 11px;
            text-align: center;
            min-height: 20px;
            color: #3a3a3c;
            font-weight: 650;
        }
        QProgressBar::chunk {
            background: #0071e3;
            border-radius: 10px;
        }
        #statusSummary {
            color: #3a3a3c;
            font-weight: 650;
        }
        QSplitter::handle {
            background: transparent;
        }
        QSplitter::handle:hover {
            background: rgba(0, 113, 227, 0.06);
            border-radius: 4px;
        }
        QScrollBar:vertical {
            background: transparent;
            width: 10px;
            margin: 4px 2px 4px 2px;
        }
        QScrollBar::handle:vertical {
            background: #c7c7cc;
            border-radius: 5px;
            min-height: 36px;
        }
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {
            height: 0;
        }
    """.replace("__ARROW_PATH__", arrow_path)
