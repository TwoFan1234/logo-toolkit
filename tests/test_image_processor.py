from __future__ import annotations

from pathlib import Path

from PIL import Image

from logo_toolkit.core.image_processor import ImageProcessor
from logo_toolkit.core.models import BatchJobConfig, ExportMode, LogoPlacement, PixelLogoPlacement, RenderOptions


def create_image(path: Path, size: tuple[int, int], color: tuple[int, int, int, int]) -> None:
    image = Image.new("RGBA", size, color)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def test_same_placement_scales_across_resolutions(tmp_path: Path) -> None:
    processor = ImageProcessor()
    base_small = tmp_path / "small.png"
    base_large = tmp_path / "large.png"
    logo_path = tmp_path / "logo.png"
    create_image(base_small, (400, 200), (255, 255, 255, 255))
    create_image(base_large, (800, 400), (255, 255, 255, 255))
    create_image(logo_path, (100, 40), (255, 0, 0, 180))

    placement = LogoPlacement(x_ratio=0.1, y_ratio=0.2, width_ratio=0.25)
    render_options = RenderOptions()

    output_dir = tmp_path / "output"
    output_small = processor.export_image(
        base_small, logo_path, placement, render_options, ExportMode.NEW_FOLDER, output_dir
    )
    output_large = processor.export_image(
        base_large, logo_path, placement, render_options, ExportMode.NEW_FOLDER, output_dir
    )

    with Image.open(output_small) as small_image, Image.open(output_large) as large_image:
        assert small_image.size == (400, 200)
        assert large_image.size == (800, 400)


def test_export_to_new_folder_keeps_original_name(tmp_path: Path) -> None:
    processor = ImageProcessor()
    image_path = tmp_path / "base.png"
    logo_path = tmp_path / "logo.png"
    create_image(image_path, (100, 100), (255, 255, 255, 255))
    create_image(logo_path, (20, 20), (0, 0, 0, 255))
    output_dir = tmp_path / "output"

    output_path = processor.export_image(
        image_path=image_path,
        logo_path=logo_path,
        placement=LogoPlacement(),
        render_options=RenderOptions(),
        export_mode=ExportMode.NEW_FOLDER,
        output_directory=output_dir,
    )

    assert output_path.name == "base.png"
    assert output_path.exists()
    assert image_path.exists()


def test_preserve_structure_creates_nested_folders(tmp_path: Path) -> None:
    processor = ImageProcessor()
    source_root = tmp_path / "source_a"
    image_path = source_root / "nested" / "base.png"
    logo_path = tmp_path / "logo.png"
    create_image(image_path, (100, 100), (255, 255, 255, 255))
    create_image(logo_path, (20, 20), (0, 0, 0, 255))
    output_dir = tmp_path / "output"

    output_path = processor.export_image(
        image_path=image_path,
        logo_path=logo_path,
        placement=LogoPlacement(),
        render_options=RenderOptions(),
        export_mode=ExportMode.NEW_FOLDER,
        output_directory=output_dir,
        preserve_structure=True,
        source_root=source_root,
    )

    assert output_path == output_dir / "source_a" / "nested" / "base.png"
    assert output_path.exists()


def test_resolve_output_directory_avoids_collisions(tmp_path: Path) -> None:
    processor = ImageProcessor()
    first = tmp_path / "a.png"
    logo = tmp_path / "logo.png"
    create_image(first, (50, 50), (255, 255, 255, 255))
    create_image(logo, (10, 10), (0, 0, 0, 255))
    (tmp_path / "logo_output").mkdir()

    config = BatchJobConfig(
        input_files=[first],
        logo_file=logo,
        placement=LogoPlacement(),
        render_options=RenderOptions(),
    )
    resolved = processor.resolve_output_directory(config)

    assert resolved == tmp_path / "logo_output_1"


def test_process_batch_reports_failures_without_stopping(tmp_path: Path) -> None:
    processor = ImageProcessor()
    valid = tmp_path / "ok.png"
    invalid = tmp_path / "broken.png"
    logo = tmp_path / "logo.png"
    create_image(valid, (80, 80), (255, 255, 255, 255))
    create_image(logo, (16, 16), (255, 0, 0, 255))
    invalid.write_bytes(b"not-a-real-image")

    config = BatchJobConfig(
        input_files=[valid, invalid],
        logo_file=logo,
        placement=LogoPlacement(),
        render_options=RenderOptions(),
        output_directory=tmp_path / "exports",
    )
    summary = processor.process_batch(config)

    assert summary.total == 2
    assert summary.succeeded == 1
    assert summary.failed == 1


def test_export_image_supports_pixel_logo_positioning(tmp_path: Path) -> None:
    processor = ImageProcessor()
    image_path = tmp_path / "base.png"
    logo_path = tmp_path / "logo.png"
    output_dir = tmp_path / "output"
    create_image(image_path, (400, 200), (255, 255, 255, 255))
    create_image(logo_path, (100, 40), (255, 0, 0, 255))

    output_path = processor.export_image(
        image_path=image_path,
        logo_path=logo_path,
        placement=LogoPlacement(),
        render_options=RenderOptions(),
        export_mode=ExportMode.NEW_FOLDER,
        output_directory=output_dir,
        pixel_placement=PixelLogoPlacement(margin_x_px=24, margin_y_px=32, width_px=120, anchor="bottom_right"),
        use_pixel_positioning=True,
    )

    with Image.open(output_path) as output:
        assert output.size == (400, 200)
        assert output.getpixel((316, 144))[:3] == (255, 0, 0)
        assert output.getpixel((20, 20))[:3] == (255, 255, 255)


def test_process_batch_uses_pixel_logo_positioning_when_enabled(tmp_path: Path) -> None:
    processor = ImageProcessor()
    image_path = tmp_path / "base.png"
    logo_path = tmp_path / "logo.png"
    create_image(image_path, (320, 180), (255, 255, 255, 255))
    create_image(logo_path, (100, 50), (0, 0, 255, 255))

    config = BatchJobConfig(
        input_files=[image_path],
        logo_file=logo_path,
        placement=LogoPlacement(),
        render_options=RenderOptions(),
        pixel_placement=PixelLogoPlacement(margin_x_px=18, margin_y_px=20, width_px=90, anchor="top_left"),
        use_pixel_positioning=True,
        output_directory=tmp_path / "exports",
    )
    summary = processor.process_batch(config)

    assert summary.succeeded == 1
    assert summary.results[0].output_path is not None
    with Image.open(summary.results[0].output_path) as output:
        assert output.getpixel((40, 40))[:3] == (0, 0, 255)
        assert output.getpixel((150, 120))[:3] == (255, 255, 255)
