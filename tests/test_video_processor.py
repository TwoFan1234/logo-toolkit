from __future__ import annotations

from pathlib import Path

from PIL import Image

from logo_toolkit.core.file_utils import collect_videos
from logo_toolkit.core.models import (
    AudioExportFormat,
    AudioExtractSettings,
    LogoPlacement,
    PixelLogoPlacement,
    RenderOptions,
    VideoBatchConfig,
    VideoContainerFormat,
    VideoEndCardAlphaMode,
    VideoConversionSettings,
    VideoEndCardSettings,
    VideoLogoSettings,
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

    def extract_frame(self, source_path: Path, output_path: Path, timestamp_seconds: float = 0.0) -> None:
        self.commands.append(["extract_frame", str(source_path), str(output_path), f"{timestamp_seconds:.3f}"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"frame")


def test_parse_probe_metadata_maps_duration_and_resolution() -> None:
    payload = {
        "format": {"duration": "12.345"},
        "streams": [
            {"codec_type": "audio"},
            {"codec_type": "video", "width": 1920, "height": 1080},
        ],
    }

    payload["streams"][1]["avg_frame_rate"] = "30000/1001"

    duration, width, height, frame_rate = VideoProcessor.parse_probe_metadata(payload)

    assert duration == 12.345
    assert width == 1920
    assert height == 1080
    assert frame_rate == "30000/1001"


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
    output = tmp_path / "sample.webm"

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
        output_suffix="",
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

    assert output_path.name == "sample.mp3"


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


def test_build_add_logo_command_uses_absolute_overlay_geometry(tmp_path: Path) -> None:
    source = tmp_path / "sample.mp4"
    source.write_bytes(b"video")
    logo = tmp_path / "logo.png"
    Image.new("RGBA", (80, 40), (0, 255, 0, 255)).save(logo)
    backend = FakeVideoBackend(
        probe_payloads={
            source: {
                "format": {"duration": "1.0"},
                "streams": [{"codec_type": "video", "width": 320, "height": 240}],
            }
        }
    )
    processor = VideoProcessor(backend=backend)
    output = tmp_path / "sample.mp4"
    config = VideoBatchConfig(
        input_files=[source],
        operation_type=VideoOperationType.ADD_LOGO,
        logo_overlay=VideoLogoSettings(
            logo_file=logo,
            placement=LogoPlacement(x_ratio=0.1, y_ratio=0.2, width_ratio=0.3),
            render_options=RenderOptions(reference_mode="frame_axis"),
        ),
    )

    arguments = processor.build_ffmpeg_arguments(source, output, config)

    assert arguments[:5] == ["-y", "-i", str(source), "-i", str(logo)]
    assert "-filter_complex" in arguments
    filter_text = arguments[arguments.index("-filter_complex") + 1]
    assert filter_text == "[1:v]scale=96:48[logo];[0:v][logo]overlay=32:48[outv]"
    assert "[outv]" in arguments


def test_build_add_logo_command_supports_bottom_right_anchor(tmp_path: Path) -> None:
    source = tmp_path / "sample.mp4"
    source.write_bytes(b"video")
    logo = tmp_path / "logo.png"
    Image.new("RGBA", (80, 40), (0, 255, 0, 255)).save(logo)
    backend = FakeVideoBackend(
        probe_payloads={
            source: {
                "format": {"duration": "1.0"},
                "streams": [{"codec_type": "video", "width": 320, "height": 240}],
            }
        }
    )
    processor = VideoProcessor(backend=backend)
    output = tmp_path / "sample.mp4"
    config = VideoBatchConfig(
        input_files=[source],
        operation_type=VideoOperationType.ADD_LOGO,
        logo_overlay=VideoLogoSettings(
            logo_file=logo,
            placement=LogoPlacement(x_ratio=0.05, y_ratio=0.05, width_ratio=0.2, anchor="bottom_right"),
            render_options=RenderOptions(reference_mode="frame_axis"),
        ),
    )

    arguments = processor.build_ffmpeg_arguments(source, output, config)

    filter_text = arguments[arguments.index("-filter_complex") + 1]
    assert filter_text == "[1:v]scale=64:32[logo];[0:v][logo]overlay=240:196[outv]"


def test_build_add_logo_command_supports_short_side_reference_mode(tmp_path: Path) -> None:
    source = tmp_path / "sample.mp4"
    source.write_bytes(b"video")
    logo = tmp_path / "logo.png"
    Image.new("RGBA", (80, 40), (0, 255, 0, 255)).save(logo)
    backend = FakeVideoBackend(
        probe_payloads={
            source: {
                "format": {"duration": "1.0"},
                "streams": [{"codec_type": "video", "width": 1920, "height": 1080}],
            }
        }
    )
    processor = VideoProcessor(backend=backend)
    output = tmp_path / "sample.mp4"
    config = VideoBatchConfig(
        input_files=[source],
        operation_type=VideoOperationType.ADD_LOGO,
        logo_overlay=VideoLogoSettings(
            logo_file=logo,
            placement=LogoPlacement(x_ratio=0.04, y_ratio=0.04, width_ratio=0.18, anchor="bottom_right"),
            render_options=RenderOptions(reference_mode="short_side"),
        ),
    )

    arguments = processor.build_ffmpeg_arguments(source, output, config)

    filter_text = arguments[arguments.index("-filter_complex") + 1]
    assert filter_text == "[1:v]scale=194:97[logo];[0:v][logo]overlay=1682:940[outv]"


def test_build_add_logo_command_supports_frame_width_reference_mode(tmp_path: Path) -> None:
    source = tmp_path / "sample.mp4"
    source.write_bytes(b"video")
    logo = tmp_path / "logo.png"
    Image.new("RGBA", (80, 40), (0, 255, 0, 255)).save(logo)
    backend = FakeVideoBackend(
        probe_payloads={
            source: {
                "format": {"duration": "1.0"},
                "streams": [{"codec_type": "video", "width": 1920, "height": 1080}],
            }
        }
    )
    processor = VideoProcessor(backend=backend)
    output = tmp_path / "sample.mp4"
    config = VideoBatchConfig(
        input_files=[source],
        operation_type=VideoOperationType.ADD_LOGO,
        logo_overlay=VideoLogoSettings(
            logo_file=logo,
            placement=LogoPlacement(x_ratio=0.04, y_ratio=0.04, width_ratio=0.18, anchor="bottom_right"),
            render_options=RenderOptions(reference_mode="frame_width"),
        ),
    )

    arguments = processor.build_ffmpeg_arguments(source, output, config)

    filter_text = arguments[arguments.index("-filter_complex") + 1]
    assert filter_text == "[1:v]scale=259:130[logo];[0:v][logo]overlay=1603:893[outv]"


def test_pixel_logo_placement_auto_detects_nearest_corner() -> None:
    placement = PixelLogoPlacement.auto_from_overlay_box(
        left=24,
        top=390,
        overlay_width=200,
        overlay_height=100,
        frame_width=1080,
        frame_height=540,
    )

    assert placement.anchor == "bottom_left"
    assert placement.margin_x_px == 24
    assert placement.margin_y_px == 50
    assert placement.width_px == 200


def test_build_add_logo_command_supports_pixel_logo_geometry(tmp_path: Path) -> None:
    source = tmp_path / "sample.mp4"
    source.write_bytes(b"video")
    logo = tmp_path / "logo.png"
    Image.new("RGBA", (80, 40), (0, 255, 0, 255)).save(logo)
    backend = FakeVideoBackend(
        probe_payloads={
            source: {
                "format": {"duration": "1.0"},
                "streams": [{"codec_type": "video", "width": 1920, "height": 1080}],
            }
        }
    )
    processor = VideoProcessor(backend=backend)
    output = tmp_path / "sample.mp4"
    config = VideoBatchConfig(
        input_files=[source],
        operation_type=VideoOperationType.ADD_LOGO,
        logo_overlay=VideoLogoSettings(
            logo_file=logo,
            pixel_placement=PixelLogoPlacement(
                margin_x_px=24,
                margin_y_px=32,
                width_px=280,
                anchor="bottom_right",
            ),
            use_pixel_positioning=True,
        ),
    )

    arguments = processor.build_ffmpeg_arguments(source, output, config)

    filter_text = arguments[arguments.index("-filter_complex") + 1]
    assert filter_text == "[1:v]scale=280:140[logo];[0:v][logo]overlay=1616:908[outv]"


def test_build_add_endcard_command_supports_overlap_and_audio_crossfade(tmp_path: Path) -> None:
    source = tmp_path / "sample.mp4"
    source.write_bytes(b"video")
    endcard = tmp_path / "endcard.mov"
    endcard.write_bytes(b"video")
    backend = FakeVideoBackend(
        probe_payloads={
            source: {
                "format": {"duration": "10.0"},
                "streams": [
                    {"codec_type": "video", "width": 1920, "height": 1080},
                    {"codec_type": "audio"},
                ],
            },
            endcard: {
                "format": {"duration": "3.0"},
                "streams": [
                    {"codec_type": "video", "width": 1080, "height": 1920},
                    {"codec_type": "audio"},
                ],
            },
        }
    )
    processor = VideoProcessor(backend=backend)
    output = tmp_path / "sample.mp4"
    config = VideoBatchConfig(
        input_files=[source],
        operation_type=VideoOperationType.ADD_ENDCARD,
        endcard=VideoEndCardSettings(
            endcard_file=endcard,
            overlap_seconds=1.5,
            audio_crossfade_seconds=0.5,
            alpha_mode=VideoEndCardAlphaMode.PREMIERE_COMPAT,
        ),
    )

    arguments = processor.build_ffmpeg_arguments(source, output, config)

    assert arguments[:5] == ["-y", "-i", str(source), "-i", str(endcard)]
    assert arguments[-1] == str(output)
    assert arguments[arguments.index("-map") + 1] == "[outv]"
    assert "[outa]" in arguments

    filter_text = arguments[arguments.index("-filter_complex") + 1]
    assert "[0:v]setpts=PTS-STARTPTS,format=rgba,tpad=stop_mode=clone:stop_duration=1.500[basev]" in filter_text
    assert (
        "[1:v]format=rgba,geq="
        "r='if(gt(alpha(X,Y),0),min(255,r(X,Y)*255/alpha(X,Y)),0)':"
        "g='if(gt(alpha(X,Y),0),min(255,g(X,Y)*255/alpha(X,Y)),0)':"
        "b='if(gt(alpha(X,Y),0),min(255,b(X,Y)*255/alpha(X,Y)),0)':"
        "a='alpha(X,Y)',scale=1920:1080,setpts=PTS-STARTPTS+8.500/TB[endv]"
    ) in filter_text
    assert "[basev][endv]overlay=0:0:eof_action=pass:format=rgb:alpha=straight[outv]" in filter_text
    assert "[0:a]asetpts=PTS-STARTPTS[sourcea]" in filter_text
    assert "[1:a]adelay=8500:all=1,afade=t=in:st=8.500:d=0.500[endcarda]" in filter_text
    assert "[sourcea][endcarda]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[outa]" in filter_text
    assert "-pix_fmt" in arguments
    assert arguments[arguments.index("-pix_fmt") + 1] == "yuv420p"


def test_build_add_endcard_command_supports_direct_alpha_mode(tmp_path: Path) -> None:
    source = tmp_path / "sample.mp4"
    source.write_bytes(b"video")
    endcard = tmp_path / "endcard.mov"
    endcard.write_bytes(b"video")
    backend = FakeVideoBackend(
        probe_payloads={
            source: {
                "format": {"duration": "10.0"},
                "streams": [{"codec_type": "video", "width": 1920, "height": 1080}],
            },
            endcard: {
                "format": {"duration": "3.0"},
                "streams": [{"codec_type": "video", "width": 1080, "height": 1920}],
            },
        }
    )
    processor = VideoProcessor(backend=backend)
    config = VideoBatchConfig(
        input_files=[source],
        operation_type=VideoOperationType.ADD_ENDCARD,
        endcard=VideoEndCardSettings(
            endcard_file=endcard,
            overlap_seconds=1.5,
            audio_crossfade_seconds=0.5,
            alpha_mode=VideoEndCardAlphaMode.DIRECT,
        ),
    )

    arguments = processor.build_ffmpeg_arguments(source, tmp_path / "output.mp4", config)
    filter_text = arguments[arguments.index("-filter_complex") + 1]

    assert "[1:v]format=rgba,scale=1920:1080,setpts=PTS-STARTPTS+8.500/TB[endv]" in filter_text
    assert "geq=" not in filter_text


def test_build_add_endcard_output_uses_mp4_extension(tmp_path: Path) -> None:
    processor = VideoProcessor(backend=FakeVideoBackend())
    source = tmp_path / "sample.mov"
    config = VideoBatchConfig(
        input_files=[source],
        operation_type=VideoOperationType.ADD_ENDCARD,
        endcard=VideoEndCardSettings(endcard_file=tmp_path / "endcard.mov"),
    )

    output_path = processor.build_output_path(
        source_path=source,
        operation_type=config.operation_type,
        output_directory=tmp_path / "exports",
        output_suffix="",
        preserve_structure=False,
        source_root=None,
        config=config,
    )

    assert output_path.name == "sample.mp4"


def test_build_add_endcard_overlap_clamps_to_source_duration(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    endcard = tmp_path / "endcard.mov"
    endcard.write_bytes(b"video")
    backend = FakeVideoBackend(
        probe_payloads={
            source: {
                "format": {"duration": "2.0"},
                "streams": [{"codec_type": "video", "width": 1280, "height": 720}],
            },
            endcard: {
                "format": {"duration": "4.0"},
                "streams": [{"codec_type": "video", "width": 1280, "height": 720}],
            },
        }
    )
    processor = VideoProcessor(backend=backend)
    config = VideoBatchConfig(
        input_files=[source],
        operation_type=VideoOperationType.ADD_ENDCARD,
        endcard=VideoEndCardSettings(
            endcard_file=endcard,
            overlap_seconds=3.0,
            audio_crossfade_seconds=1.2,
        ),
    )

    arguments = processor.build_ffmpeg_arguments(source, tmp_path / "output.mp4", config)
    filter_text = arguments[arguments.index("-filter_complex") + 1]

    assert "tpad=stop_mode=clone:stop_duration=2.000" in filter_text
    assert "setpts=PTS-STARTPTS+0.000/TB[endv]" in filter_text


def test_build_add_endcard_overlap_clamps_to_endcard_duration(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    endcard = tmp_path / "endcard.mov"
    endcard.write_bytes(b"video")
    backend = FakeVideoBackend(
        probe_payloads={
            source: {
                "format": {"duration": "6.0"},
                "streams": [{"codec_type": "video", "width": 1280, "height": 720}],
            },
            endcard: {
                "format": {"duration": "1.25"},
                "streams": [{"codec_type": "video", "width": 1280, "height": 720}],
            },
        }
    )
    processor = VideoProcessor(backend=backend)
    config = VideoBatchConfig(
        input_files=[source],
        operation_type=VideoOperationType.ADD_ENDCARD,
        endcard=VideoEndCardSettings(
            endcard_file=endcard,
            overlap_seconds=3.0,
            audio_crossfade_seconds=2.0,
        ),
    )

    arguments = processor.build_ffmpeg_arguments(source, tmp_path / "output.mp4", config)
    filter_text = arguments[arguments.index("-filter_complex") + 1]

    assert "tpad=stop_mode=clone:stop_duration=0.000" in filter_text
    assert "setpts=PTS-STARTPTS+4.750/TB[endv]" in filter_text


def test_build_add_endcard_command_supports_source_audio_only(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    endcard = tmp_path / "endcard.mov"
    endcard.write_bytes(b"video")
    backend = FakeVideoBackend(
        probe_payloads={
            source: {
                "format": {"duration": "6.0"},
                "streams": [
                    {"codec_type": "video", "width": 1280, "height": 720},
                    {"codec_type": "audio"},
                ],
            },
            endcard: {
                "format": {"duration": "2.0"},
                "streams": [{"codec_type": "video", "width": 1280, "height": 720}],
            },
        }
    )
    processor = VideoProcessor(backend=backend)
    config = VideoBatchConfig(
        input_files=[source],
        operation_type=VideoOperationType.ADD_ENDCARD,
        endcard=VideoEndCardSettings(endcard_file=endcard, overlap_seconds=1.0, audio_crossfade_seconds=0.4),
    )

    arguments = processor.build_ffmpeg_arguments(source, tmp_path / "output.mp4", config)
    filter_text = arguments[arguments.index("-filter_complex") + 1]

    assert "[0:a]asetpts=PTS-STARTPTS[outa]" in filter_text
    assert "adelay=" not in filter_text
    assert "[outa]" in arguments


def test_build_add_endcard_command_supports_endcard_audio_only(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    endcard = tmp_path / "endcard.mov"
    endcard.write_bytes(b"video")
    backend = FakeVideoBackend(
        probe_payloads={
            source: {
                "format": {"duration": "6.0"},
                "streams": [{"codec_type": "video", "width": 1280, "height": 720}],
            },
            endcard: {
                "format": {"duration": "2.0"},
                "streams": [
                    {"codec_type": "video", "width": 1280, "height": 720},
                    {"codec_type": "audio"},
                ],
            },
        }
    )
    processor = VideoProcessor(backend=backend)
    config = VideoBatchConfig(
        input_files=[source],
        operation_type=VideoOperationType.ADD_ENDCARD,
        endcard=VideoEndCardSettings(endcard_file=endcard, overlap_seconds=1.0, audio_crossfade_seconds=0.4),
    )

    arguments = processor.build_ffmpeg_arguments(source, tmp_path / "output.mp4", config)
    filter_text = arguments[arguments.index("-filter_complex") + 1]

    assert "[1:a]adelay=5000:all=1,afade=t=in:st=5.000:d=0.400[outa]" in filter_text
    assert "[outa]" in arguments


def test_build_add_endcard_command_supports_silent_output(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    endcard = tmp_path / "endcard.mov"
    endcard.write_bytes(b"video")
    backend = FakeVideoBackend(
        probe_payloads={
            source: {
                "format": {"duration": "6.0"},
                "streams": [{"codec_type": "video", "width": 1280, "height": 720}],
            },
            endcard: {
                "format": {"duration": "2.0"},
                "streams": [{"codec_type": "video", "width": 1280, "height": 720}],
            },
        }
    )
    processor = VideoProcessor(backend=backend)
    config = VideoBatchConfig(
        input_files=[source],
        operation_type=VideoOperationType.ADD_ENDCARD,
        endcard=VideoEndCardSettings(endcard_file=endcard, overlap_seconds=1.0, audio_crossfade_seconds=0.4),
    )

    arguments = processor.build_ffmpeg_arguments(source, tmp_path / "output.mp4", config)
    filter_text = arguments[arguments.index("-filter_complex") + 1]

    assert "[outa]" not in filter_text
    assert arguments.count("-map") == 1
    assert "-c:a" not in arguments


def test_extract_preview_frame_uses_backend_cache(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "sample.mp4"
    source.write_bytes(b"video")
    backend = FakeVideoBackend()
    processor = VideoProcessor(backend=backend)
    cache_root = tmp_path / "cache"
    monkeypatch.setattr("logo_toolkit.core.video_processor.tempfile.gettempdir", lambda: str(cache_root))

    first = processor.extract_preview_frame(source, timestamp_seconds=0.5)
    second = processor.extract_preview_frame(source, timestamp_seconds=0.5)

    assert first == second
    assert first.exists()
    assert backend.commands.count(["extract_frame", str(source), str(first), "0.500"]) == 1


def test_process_batch_reports_failures_without_stopping(tmp_path: Path) -> None:
    source_root = tmp_path / "videos"
    source_root.mkdir()
    first = source_root / "ok.mp4"
    second = source_root / "bad.mp4"
    first.write_bytes(b"1")
    second.write_bytes(b"2")
    output_dir = tmp_path / "exports"
    backend = FakeVideoBackend(failing_outputs={"bad.mp4"})
    processor = VideoProcessor(backend=backend)
    config = VideoBatchConfig(
        input_files=[first, second],
        operation_type=VideoOperationType.CONVERT,
        output_directory=output_dir,
        output_suffix="",
        source_roots={first: source_root, second: source_root},
    )

    summary = processor.process_batch(config)

    assert summary.total == 2
    assert summary.succeeded == 1
    assert summary.failed == 1
    assert (output_dir / "videos" / "ok.mp4").exists()
