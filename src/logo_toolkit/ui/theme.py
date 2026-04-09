from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QWidget


def apply_shadow(widget: QWidget, blur_radius: int = 32, y_offset: int = 10, alpha: int = 22) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur_radius)
    effect.setOffset(0, y_offset)
    effect.setColor(QColor(15, 23, 42, alpha))
    widget.setGraphicsEffect(effect)


def main_window_stylesheet() -> str:
    return """
        QMainWindow {
            background: #f5f5f7;
            font-family: "Segoe UI Variable", "Segoe UI", "Microsoft YaHei UI";
            color: #1d1d1f;
        }
        #sidebarFrame {
            background: rgba(255, 255, 255, 0.78);
            border-radius: 28px;
            border: 1px solid rgba(0, 0, 0, 0.08);
        }
        #sidebarTitleLabel {
            color: #1d1d1f;
            font-size: 17px;
            font-weight: 700;
            letter-spacing: 0.2px;
        }
        #sidebarCopyLabel,
        #toolDescriptionLabel {
            color: #6e6e73;
            font-size: 12px;
            line-height: 1.45em;
        }
        #toolList {
            background: rgba(248, 248, 250, 0.72);
            border: 1px solid rgba(0, 0, 0, 0.06);
            border-radius: 22px;
            padding: 10px;
            color: #1d1d1f;
            outline: none;
        }
        #toolList::item {
            background: transparent;
            padding: 13px 14px;
            border-radius: 16px;
            margin: 3px 0;
            border: 1px solid transparent;
        }
        #toolList::item:hover {
            background: rgba(0, 113, 227, 0.08);
            border: 1px solid rgba(0, 113, 227, 0.10);
        }
        #toolList::item:selected {
            background: #ffffff;
            color: #0071e3;
            border: 1px solid rgba(0, 113, 227, 0.18);
            font-weight: 700;
        }
        #helperCard {
            background: rgba(255, 255, 255, 0.86);
            border-radius: 22px;
            border: 1px solid rgba(0, 0, 0, 0.07);
        }
        #helperTitleLabel {
            color: #1d1d1f;
            font-size: 13px;
            font-weight: 700;
        }
        #helperCopyLabel {
            color: #6e6e73;
            font-size: 12px;
            line-height: 1.45em;
        }
        #contentFrame {
            background: rgba(255, 255, 255, 0.72);
            border-radius: 30px;
            border: 1px solid rgba(0, 0, 0, 0.08);
        }
        #toolStack {
            background: transparent;
        }
    """


def toolkit_tool_stylesheet() -> str:
    return """
        QWidget {
            font-family: "Segoe UI Variable", "Segoe UI", "Microsoft YaHei UI";
            color: #1d1d1f;
            font-size: 13px;
        }
        QGroupBox {
            background: rgba(255, 255, 255, 0.84);
            border: 1px solid rgba(0, 0, 0, 0.08);
            border-radius: 18px;
            margin-top: 14px;
            padding-top: 14px;
            font-weight: 650;
            color: #1d1d1f;
        }
        QGroupBox::title {
            left: 18px;
            padding: 0 8px;
            color: #3a3a3c;
            background: transparent;
        }
        QPushButton {
            background: #1d1d1f;
            color: #ffffff;
            border: 1px solid rgba(0, 0, 0, 0.08);
            border-radius: 12px;
            padding: 9px 14px;
            font-weight: 650;
            min-height: 20px;
        }
        QPushButton:hover {
            background: #2c2c2e;
        }
        QPushButton:pressed {
            background: #111113;
            padding-top: 10px;
            padding-bottom: 8px;
        }
        QPushButton:disabled {
            background: #d1d1d6;
            color: #8e8e93;
            border-color: rgba(0, 0, 0, 0.04);
        }
        QPushButton#primaryRunButton {
            background: #0071e3;
            border: 1px solid rgba(0, 113, 227, 0.18);
            border-radius: 15px;
            font-size: 15px;
            font-weight: 750;
            padding: 13px 18px;
        }
        QPushButton#primaryRunButton:hover {
            background: #147ce5;
        }
        QPushButton#primaryRunButton:pressed {
            background: #005bb5;
        }
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
            background: rgba(255, 255, 255, 0.96);
            border: 1px solid rgba(0, 0, 0, 0.13);
            border-radius: 11px;
            padding: 7px 9px;
            min-height: 20px;
            selection-background-color: #0071e3;
        }
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
            border: 1px solid #0071e3;
            background: #ffffff;
        }
        QComboBox::drop-down {
            border: none;
            width: 28px;
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
            background: rgba(255, 255, 255, 0.82);
            border: 1px solid rgba(0, 0, 0, 0.08);
            border-radius: 22px;
        }
        #previewTitle {
            color: #1d1d1f;
            font-size: 17px;
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
            background: rgba(245, 245, 247, 0.92);
            border: 1px solid rgba(0, 0, 0, 0.06);
            border-radius: 14px;
            padding: 9px 11px;
            color: #6e6e73;
            font-size: 12px;
            line-height: 1.45em;
        }
        #previewImageLabel {
            background: #ffffff;
            border: 1px solid rgba(0, 0, 0, 0.08);
            border-radius: 18px;
            color: #86868b;
        }
        QTableWidget {
            background: rgba(255, 255, 255, 0.92);
            alternate-background-color: #f8f8fa;
            border: 1px solid rgba(0, 0, 0, 0.08);
            border-radius: 14px;
            padding: 2px;
            gridline-color: rgba(0, 0, 0, 0.06);
            selection-background-color: rgba(0, 113, 227, 0.12);
            selection-color: #1d1d1f;
        }
        QHeaderView::section {
            background: #f5f5f7;
            color: #6e6e73;
            border: none;
            border-right: 1px solid rgba(0, 0, 0, 0.06);
            border-bottom: 1px solid rgba(0, 0, 0, 0.07);
            padding: 9px 7px;
            font-weight: 700;
        }
        QProgressBar {
            background: #e8e8ed;
            border: none;
            border-radius: 10px;
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
    """
