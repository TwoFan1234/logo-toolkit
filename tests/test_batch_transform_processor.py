from __future__ import annotations

from pathlib import Path

from PIL import Image

from logo_toolkit.core.batch_transform_processor import BatchTransformProcessor
from logo_toolkit.core.models import (
    BatchSummary,
    BatchTransformConfig,
    CompressionLevel,
    ExportMode,
    ResizeConfig,
    ResizeMode,
    TransformFormat,
)


def create_image(path: Path, size: tuple[int, int], color: tuple[int, int, int, int]) -> None:
    image = Image.new("RGBA", size, color)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def create_patterned_image(path: Path, size: tuple[int, int]) -> None:
    image = Image.new("RGB", size)
    for x in range(size[0]):
        for y in range(size[1]):
            image.putpixel((x, y), ((x * 7) % 256, (y * 5) % 256, ((x + y) * 3) % 256))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def build_config(
    image_path: Path,
    *,
    transform_format: TransformFormat = TransformFormat.KEEP,
    compression_level: CompressionLevel = CompressionLevel.NONE,
    resize_config: ResizeConfig | None = None,
    export_mode: ExportMode = ExportMode.NEW_FOLDER,
    output_directory: Path | None = None,
    preserve_structure: bool = True,
    source_root: Path | None = None,
) -> BatchTransformConfig:
    return BatchTransformConfig(
        input_files=[image_path],
        transform_format=transform_format,
        compression_level=compression_level,
        resize_config=resize_config or ResizeConfig(),
        export_mode=export_mode,
        output_directory=output_directory,
        preserve_structure=preserve_structure,
        source_roots={image_path: source_root},
    )


def test_transform_formats_round_trip(tmp_path: Path) -> None:
    processor = BatchTransformProcessor()
    source = tmp_path / "source.png"
    create_image(source, (160, 120), (255, 0, 0, 180))

    for target_format, expected_suffix, expected_format in (
        (TransformFormat.JPEG, ".jpg", "JPEG"),
        (TransformFormat.PNG, ".png", "PNG"),
        (TransformFormat.WEBP, ".webp", "WEBP"),
    ):
        output_dir = tmp_path / expected_format.lower()
        config = build_config(source, transform_format=target_format, output_directory=output_dir)
        output_path = processor.export_image(source, config, output_dir, source.parent)

        assert output_path.suffix == expected_suffix
        with Image.open(output_path) as image:
            assert image.format == expected_format


def test_compression_level_reduces_jpeg_output_size(tmp_path: Path) -> None:
    processor = BatchTransformProcessor()
    source = tmp_path / "source.png"
    create_patterned_image(source, (320, 240))

    low_config = build_config(
        source,
        transform_format=TransformFormat.JPEG,
        compression_level=CompressionLevel.NONE,
        output_directory=tmp_path / "none",
    )
    high_config = build_config(
        source,
        transform_format=TransformFormat.JPEG,
        compression_level=CompressionLevel.HIGH,
        output_directory=tmp_path / "high",
    )

    low_path = processor.export_image(source, low_config, low_config.output_directory, source.parent)
    high_path = processor.export_image(source, high_config, high_config.output_directory, source.parent)

    assert high_path.stat().st_size < low_path.stat().st_size


def test_resize_scale_percent(tmp_path: Path) -> None:
    processor = BatchTransformProcessor()
    source = tmp_path / "source.png"
    create_image(source, (400, 200), (255, 255, 255, 255))
    config = build_config(
        source,
        resize_config=ResizeConfig(mode=ResizeMode.SCALE_PERCENT, scale_percent=50),
        output_directory=tmp_path / "output",
    )

    output_path = processor.export_image(source, config, config.output_directory, source.parent)

    with Image.open(output_path) as image:
        assert image.size == (200, 100)


def test_resize_longest_edge_preserves_aspect_ratio(tmp_path: Path) -> None:
    processor = BatchTransformProcessor()
    source = tmp_path / "source.png"
    create_image(source, (400, 200), (255, 255, 255, 255))
    config = build_config(
        source,
        resize_config=ResizeConfig(mode=ResizeMode.LONGEST_EDGE, longest_edge=1500),
        output_directory=tmp_path / "output",
    )

    output_path = processor.export_image(source, config, config.output_directory, source.parent)

    with Image.open(output_path) as image:
        assert image.size == (1500, 750)


def test_exact_dimensions_can_keep_aspect_ratio_or_stretch(tmp_path: Path) -> None:
    processor = BatchTransformProcessor()
    source = tmp_path / "source.png"
    create_image(source, (400, 200), (255, 255, 255, 255))

    keep_config = build_config(
        source,
        resize_config=ResizeConfig(
            mode=ResizeMode.EXACT_DIMENSIONS,
            target_width=300,
            target_height=300,
            keep_aspect_ratio=True,
        ),
        output_directory=tmp_path / "keep",
    )
    stretch_config = build_config(
        source,
        resize_config=ResizeConfig(
            mode=ResizeMode.EXACT_DIMENSIONS,
            target_width=300,
            target_height=300,
            keep_aspect_ratio=False,
        ),
        output_directory=tmp_path / "stretch",
    )

    keep_path = processor.export_image(source, keep_config, keep_config.output_directory, source.parent)
    stretch_path = processor.export_image(source, stretch_config, stretch_config.output_directory, source.parent)

    with Image.open(keep_path) as image:
        assert image.size == (300, 150)
    with Image.open(stretch_path) as image:
        assert image.size == (300, 300)


def test_preserve_structure_and_name_collision(tmp_path: Path) -> None:
    processor = BatchTransformProcessor()
    source_root = tmp_path / "source_a"
    source = source_root / "nested" / "base.png"
    create_image(source, (100, 100), (255, 255, 255, 255))
    output_dir = tmp_path / "output"
    config = build_config(source, output_directory=output_dir, preserve_structure=True, source_root=source_root)

    first_path = processor.export_image(source, config, output_dir, source_root)
    second_path = processor.export_image(source, config, output_dir, source_root)

    assert first_path == output_dir / "source_a" / "nested" / "base.png"
    assert second_path == output_dir / "source_a" / "nested" / "base_1.png"


def test_overwrite_mode_rejects_format_conversion(tmp_path: Path) -> None:
    processor = BatchTransformProcessor()
    source = tmp_path / "source.png"
    create_image(source, (100, 100), (255, 255, 255, 255))
    config = build_config(
        source,
        transform_format=TransformFormat.JPEG,
        export_mode=ExportMode.OVERWRITE,
    )

    try:
        processor.export_image(source, config, None, source.parent)
    except ValueError as exc:
        assert "不能同时转换格式" in str(exc)
    else:
        raise AssertionError("Expected format conversion overwrite to be rejected")


def test_process_batch_reports_failures_without_stopping(tmp_path: Path) -> None:
    processor = BatchTransformProcessor()
    valid = tmp_path / "ok.png"
    invalid = tmp_path / "broken.png"
    create_image(valid, (80, 80), (255, 255, 255, 255))
    invalid.write_bytes(b"not-a-real-image")

    config = BatchTransformConfig(
        input_files=[valid, invalid],
        transform_format=TransformFormat.PNG,
        compression_level=CompressionLevel.NONE,
        resize_config=ResizeConfig(),
        export_mode=ExportMode.NEW_FOLDER,
        output_directory=tmp_path / "output",
        preserve_structure=True,
        source_roots={valid: valid.parent, invalid: invalid.parent},
    )

    summary = processor.process_batch(config)

    assert isinstance(summary, BatchSummary)
    assert summary.total == 2
    assert summary.succeeded == 1
    assert summary.failed == 1
