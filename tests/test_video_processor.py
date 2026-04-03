from __future__ import annotations

from pathlib import Path

from logo_toolkit.core.file_utils import collect_videos
from logo_toolkit.core.models import (
    AudioExportFormat,
    AudioExtractSettings,
    VideoBatchConfig,
    VideoContainerFormat,
    VideoConversionSettings,
    VideoOperationType,
    VideoResizeSettings,
    VideoTrimSettings,
)
from logo_toolkit.core.video_processor import VideoProcessor


class FakeVideoBackend:
    def __init__(self, probe_payloads: dict[Path, dict] | None = None, failing_outputs: set[str] | None = None) -> None:
        self.probe_payloads = probe_payloads or {}
        self.failing_outputs = failing_outputs or set()
        self.commands: list[list[str]] = []

    def probe(self, source_path: Path) -> dict:
        return self.probe_payloads[source_path]

    def run_ffmpeg(self, arguments: list[str]) -> None:
        self.commands.append(arguments)
        output_path = Path(arguments[-1])
        if output_path.name in self.failing_outputs:
            raise RuntimeError(f"failed for {output_path.name}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"video")


def test_parse_probe_metadata_maps_duration_and_resolution() -> None:
    payload = {
        "format": {"duration": "12.345"},
        "streams": [
            {"codec_type": "audio"},
            {"codec_type": "video", "width": 1920, "height": 1080},
        ],
    }

    duration, width, height = VideoProcessor.parse_probe_metadata(payload)

    assert duration == 12.345
    assert width == 1920
    assert height == 1080


def test_collect_videos_recurses_and_filters_supported_extensions(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    (source_dir / "nested").mkdir(parents=True)
    (source_dir / "movie.mp4").write_bytes(b"a")
    (source_dir / "nested" / "clip.webm").write_bytes(b"b")
    (source_dir / "nested" / "notes.txt").write_text("ignore", encoding="utf-8")

    collected = collect_videos([str(source_dir)])

    names = sorted(item.source_path.name for item in collected)
    assert names == ["clip.webm", "movie.mp4"]


def test_build_convert_command_uses_target_extension_and_codecs(tmp_path: Path) -> None:
    processor = VideoProcessor(backend=FakeVideoBackend())
    source = tmp_path / "sample.mov"
    config = VideoBatchConfig(
        input_files=[source],
        operation_type=VideoOperationType.CONVERT,
        conversion=VideoConversionSettings(target_format=VideoContainerFormat.WEBM),
    )
    output = tmp_path / "sample_converted.webm"

    arguments = processor.build_ffmpeg_arguments(source, output, config)

    assert arguments[:3] == ["-y", "-i", str(source)]
    assert "libvpx-vp9" in arguments
    assert "libopus" in arguments
    assert arguments[-1] == str(output)


def test_build_extract_audio_output_uses_audio_extension(tmp_path: Path) -> None:
    processor = VideoProcessor(backend=FakeVideoBackend())
    source = tmp_path / "sample.mp4"
    config = VideoBatchConfig(
        input_files=[source],
        operation_type=VideoOperationType.EXTRACT_AUDIO,
        output_suffix="_audio",
        audio_extract=AudioExtractSettings(target_format=AudioExportFormat.MP3),
    )

    output_path = processor.build_output_path(
        source_path=source,
        operation_type=config.operation_type,
        output_directory=tmp_path / "exports",
        output_suffix=config.output_suffix,
        preserve_structure=False,
        source_root=None,
        config=config,
    )

    assert output_path.name == "sample_audio.mp3"


def test_trim_validation_rejects_invalid_ranges() -> None:
    processor = VideoProcessor(backend=FakeVideoBackend())

    try:
        processor.validate_trim_settings(VideoTrimSettings(start_time="00:00:10", end_time="00:00:05"))
    except ValueError as exc:
        assert "开始时间必须早于结束时间" in str(exc)
    else:
        raise AssertionError("Expected trim validation to fail")


def test_resize_filter_supports_single_dimension_with_keep_aspect() -> None:
    processor = VideoProcessor(backend=FakeVideoBackend())

    filter_text = processor._scale_filter(VideoResizeSettings(width=1280, height=0, keep_aspect_ratio=True))

    assert filter_text == "scale=1280:-2"


def test_resolve_output_directory_avoids_video_output_collisions(tmp_path: Path) -> None:
    processor = VideoProcessor(backend=FakeVideoBackend())
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"x")
    (tmp_path / "video_output").mkdir()
    config = VideoBatchConfig(input_files=[source], operation_type=VideoOperationType.COMPRESS)

    resolved = processor.resolve_output_directory(config)

    assert resolved == tmp_path / "video_output_1"


def test_process_batch_reports_failures_without_stopping(tmp_path: Path) -> None:
    source_root = tmp_path / "videos"
    source_root.mkdir()
    first = source_root / "ok.mp4"
    second = source_root / "bad.mp4"
    first.write_bytes(b"1")
    second.write_bytes(b"2")
    output_dir = tmp_path / "exports"
    backend = FakeVideoBackend(failing_outputs={"bad_converted.mp4"})
    processor = VideoProcessor(backend=backend)
    config = VideoBatchConfig(
        input_files=[first, second],
        operation_type=VideoOperationType.CONVERT,
        output_directory=output_dir,
        output_suffix="_converted",
        source_roots={first: source_root, second: source_root},
    )

    summary = processor.process_batch(config)

    assert summary.total == 2
    assert summary.succeeded == 1
    assert summary.failed == 1
    assert (output_dir / "videos" / "ok_converted.mp4").exists()
