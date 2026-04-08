from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PIL import Image

from logo_toolkit.core.models import PixelLogoPlacement, VideoEndCardAlphaMode, VideoOperationType
from logo_toolkit.tools.registry import build_tool_registry
from logo_toolkit.tools.video_tool import BatchVideoToolWidget
from logo_toolkit.ui.video_logo_preview_canvas import VideoLogoPreviewCanvas


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def get_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_video_widget_can_be_configured_as_logo_only_tool() -> None:
    get_app()
    widget = BatchVideoToolWidget(available_operations=[VideoOperationType.ADD_LOGO])

    assert widget.logo_only_mode is True
    assert widget.current_operation_type() == VideoOperationType.ADD_LOGO
    assert widget.operation_combo.count() == 1
    assert widget.operation_combo.itemData(0) == VideoOperationType.ADD_LOGO

    config = widget.current_config()
    assert config.operation_type == VideoOperationType.ADD_LOGO
    assert config.output_suffix == ""
    assert config.logo_overlay.use_pixel_positioning is True
    assert config.logo_overlay.pixel_placement == widget.logo_pixel_placement
    assert config.logo_overlay.pixel_placement.anchor == "bottom_right"

    widget.close()


def test_video_widget_can_be_configured_as_endcard_only_tool() -> None:
    get_app()
    widget = BatchVideoToolWidget(available_operations=[VideoOperationType.ADD_ENDCARD])

    assert widget.endcard_only_mode is True
    assert widget.current_operation_type() == VideoOperationType.ADD_ENDCARD
    assert widget.operation_combo.count() == 1
    assert widget.operation_combo.itemData(0) == VideoOperationType.ADD_ENDCARD

    widget.endcard_path = Path("F:/shared/endcard.mov")
    widget.endcard_overlap_spin.setValue(1.8)
    widget.endcard_crossfade_spin.setValue(0.6)
    widget.endcard_alpha_mode_combo.setCurrentIndex(0)
    config = widget.current_config()

    assert config.operation_type == VideoOperationType.ADD_ENDCARD
    assert config.endcard.endcard_file == Path("F:/shared/endcard.mov")
    assert config.endcard.overlap_seconds == 1.8
    assert config.endcard.audio_crossfade_seconds == 0.6
    assert config.endcard.alpha_mode == VideoEndCardAlphaMode.PREMIERE_COMPAT
    assert "MP4(H.264/AAC)" in widget.output_note_label.text()

    widget.close()


def test_tool_registry_exposes_independent_video_logo_entry() -> None:
    get_app()
    definitions = build_tool_registry()
    tool_ids = [definition.tool_id for definition in definitions]

    assert tool_ids == [
        "batch_transform",
        "batch_logo",
        "batch_video",
        "batch_video_logo",
        "batch_video_endcard",
        "batch_video_frame",
    ]

    batch_video_widget = next(definition.factory() for definition in definitions if definition.tool_id == "batch_video")
    batch_video_operations = [batch_video_widget.operation_combo.itemData(index) for index in range(batch_video_widget.operation_combo.count())]
    assert VideoOperationType.ADD_LOGO not in batch_video_operations
    assert VideoOperationType.ADD_ENDCARD not in batch_video_operations

    batch_video_logo_widget = next(
        definition.factory() for definition in definitions if definition.tool_id == "batch_video_logo"
    )
    batch_video_endcard_widget = next(
        definition.factory() for definition in definitions if definition.tool_id == "batch_video_endcard"
    )
    assert batch_video_logo_widget.current_operation_type() == VideoOperationType.ADD_LOGO
    assert batch_video_endcard_widget.current_operation_type() == VideoOperationType.ADD_ENDCARD

    batch_video_widget.close()
    batch_video_logo_widget.close()
    batch_video_endcard_widget.close()


def test_video_logo_preview_canvas_round_trips_source_pixels(tmp_path: Path) -> None:
    app = get_app()
    frame_path = tmp_path / "frame.png"
    logo_path = tmp_path / "logo.png"
    Image.new("RGBA", (1920, 1080), (255, 255, 255, 255)).save(frame_path)
    Image.new("RGBA", (200, 100), (0, 255, 0, 255)).save(logo_path)

    canvas = VideoLogoPreviewCanvas()
    canvas.resize(960, 640)
    canvas.set_images(
        frame_path,
        logo_path,
        PixelLogoPlacement(margin_x_px=24, margin_y_px=32, width_px=280, anchor="bottom_right"),
    )
    canvas.show()
    app.processEvents()

    emitted: list[tuple[int, int, int, str]] = []
    canvas.placement_changed.connect(lambda x, y, w, anchor: emitted.append((x, y, w, anchor)))

    logo_rect = canvas._logo_rect()
    canvas._update_from_canvas(logo_rect.left(), logo_rect.top(), logo_rect.width())

    assert emitted[-1] == (24, 32, 280, "bottom_right")
    canvas.close()


