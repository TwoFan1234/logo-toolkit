from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtWidgets import QApplication

from logo_toolkit.core.models import VideoItem
from logo_toolkit.core.video_frame_processor import FrameImageItem
from logo_toolkit.tools.video_frame_tool import BatchVideoFrameToolWidget


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def get_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_video_frame_widget_current_config_only_uses_checked_items(tmp_path: Path) -> None:
    get_app()
    widget = BatchVideoFrameToolWidget()
    wide_video = VideoItem(source_path=tmp_path / "wide.mp4", width=1920, height=1080)
    square_video = VideoItem(
        source_path=tmp_path / "square.mp4",
        width=1080,
        height=1080,
        selected_for_batch=False,
    )
    square_frame = FrameImageItem(source_path=tmp_path / "square.png", width=1080, height=1080)
    portrait_frame = FrameImageItem(
        source_path=tmp_path / "portrait.png",
        width=1080,
        height=1920,
        selected_for_batch=False,
    )
    widget.video_items = [wide_video, square_video]
    widget.frame_items = [square_frame, portrait_frame]
    widget._rebuild_video_table()
    widget._rebuild_frame_table()

    config = widget._current_config()

    assert config.input_files == [wide_video.source_path]
    assert config.frame_files == [square_frame.source_path]
    assert config.source_roots == {}
    widget.close()


def test_video_frame_widget_ratio_filter_and_remove_selected_rows(tmp_path: Path) -> None:
    get_app()
    widget = BatchVideoFrameToolWidget()
    wide_video = VideoItem(source_path=tmp_path / "wide.mp4", width=1920, height=1080)
    square_video = VideoItem(source_path=tmp_path / "square.mp4", width=1080, height=1080)
    portrait_video = VideoItem(source_path=tmp_path / "portrait.mp4", width=1080, height=1920)
    square_frame = FrameImageItem(source_path=tmp_path / "square.png", width=1080, height=1080)
    wide_frame = FrameImageItem(source_path=tmp_path / "wide.png", width=1920, height=1080)
    widget.video_items = [wide_video, square_video, portrait_video]
    widget.frame_items = [square_frame, wide_frame]
    widget._rebuild_video_table()
    widget._rebuild_frame_table()

    widget.video_ratio_filter_combo.setCurrentIndex(widget.video_ratio_filter_combo.findData("16:9"))
    widget._apply_video_ratio_filter_selection()
    assert [item.source_path for item in widget._checked_video_items()] == [wide_video.source_path]

    widget.frame_ratio_filter_combo.setCurrentIndex(widget.frame_ratio_filter_combo.findData("1:1"))
    widget._apply_frame_ratio_filter_selection()
    assert [item.source_path for item in widget._checked_frame_items()] == [square_frame.source_path]

    widget.video_table.selectRow(1)
    widget._remove_selected_video_rows()
    assert [item.source_path for item in widget.video_items] == [wide_video.source_path, portrait_video.source_path]

    widget.frame_table.selectRow(1)
    widget._remove_selected_frame_rows()
    assert [item.source_path for item in widget.frame_items] == [square_frame.source_path]
    widget.close()
