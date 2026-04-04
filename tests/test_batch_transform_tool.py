from __future__ import annotations

import os

from PySide6.QtWidgets import QApplication

from logo_toolkit.core.models import CompressionLevel, ResizeMode, TransformFormat
from logo_toolkit.tools.batch_transform_tool import BatchTransformToolWidget


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def get_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_current_config_normalizes_string_backed_combo_data() -> None:
    get_app()
    widget = BatchTransformToolWidget()

    widget.format_combo.setCurrentIndex(widget.format_combo.findData(TransformFormat.JPEG))
    widget.compression_combo.setCurrentIndex(widget.compression_combo.findData(CompressionLevel.HIGH))
    widget.resize_mode_combo.setCurrentIndex(widget.resize_mode_combo.findData(ResizeMode.LONGEST_EDGE))

    config = widget._current_config()

    assert config.transform_format == TransformFormat.JPEG
    assert config.compression_level == CompressionLevel.HIGH
    assert config.resize_config.mode == ResizeMode.LONGEST_EDGE
