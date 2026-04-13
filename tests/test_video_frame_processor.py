from __future__ import annotations

from pathlib import Path

from PIL import Image

from logo_toolkit.core.video_frame_processor import (
    OUTPUT_SIZE_AUTO_STANDARD,
    OUTPUT_SIZE_CUSTOM,
    VideoFrameJobConfig,
    VideoFrameProcessor,
)


class FakeVideoBackend:
    def __init__(self, probe_payloads: dict[Path, dict] | None = None) -> None:
        self.probe_payloads = probe_payloads or {}
        self.commands: list[list[str]] = []

    def probe(self, source_path: Path) -> dict:
        return self.probe_payloads[source_path]

    def run_ffmpeg(self, arguments: list[str]) -> None:
        self.commands.append(arguments)
        output_path = Path(arguments[-1])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"video")

    def extract_frame(self, source_path: Path, output_path: Path, timestamp_seconds: float = 0.0) -> None:
        raise AssertionError("not used")


def create_frame(path: Path, size: tuple[int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, (255, 255, 255, 255)).save(path)


def test_build_frame_command_scales_landscape_video_by_width(tmp_path: Path) -> None:
    video = tmp_path / "video.mp4"
    video.write_bytes(b"video")
    frame = tmp_path / "square.png"
    create_frame(frame, (1080, 1080))
    backend = FakeVideoBackend(
        probe_payloads={
            video: {
                "format": {"duration": "1.0"},
                "streams": [{"codec_type": "video", "width": 1920, "height": 1080}],
            }
        }
    )
    processor = VideoFrameProcessor(backend=backend)
    config = VideoFrameJobConfig(input_files=[video], frame_files=[frame])
    output = tmp_path / "out.mp4"

    arguments = processor.build_ffmpeg_arguments(video, frame, output, config)

    filter_text = arguments[arguments.index("-filter_complex") + 1]
    assert filter_text == (
        "[1:v]scale=1080:1080[bg];"
        "[0:v]scale=1086:612[fg];"
        "[bg][fg]overlay=-3:234:shortest=1[outv]"
    )


def test_build_frame_command_uses_source_frame_rate_for_frame_input(tmp_path: Path) -> None:
    video = tmp_path / "video.mp4"
    video.write_bytes(b"video")
    frame = tmp_path / "square.png"
    create_frame(frame, (1080, 1080))
    backend = FakeVideoBackend(
        probe_payloads={
            video: {
                "format": {"duration": "1.0"},
                "streams": [
                    {
                        "codec_type": "video",
                        "width": 1920,
                        "height": 1080,
                        "avg_frame_rate": "30000/1001",
                    }
                ],
            }
        }
    )
    processor = VideoFrameProcessor(backend=backend)
    config = VideoFrameJobConfig(input_files=[video], frame_files=[frame])
    output = tmp_path / "out.mp4"

    arguments = processor.build_ffmpeg_arguments(video, frame, output, config)

    frame_index = arguments.index(str(frame))
    assert arguments[frame_index - 5 : frame_index + 1] == [
        "-loop",
        "1",
        "-framerate",
        "30000/1001",
        "-i",
        str(frame),
    ]


def test_build_frame_command_supports_auto_standard_output_size(tmp_path: Path) -> None:
    video = tmp_path / "video.mp4"
    video.write_bytes(b"video")
    frame = tmp_path / "portrait.png"
    create_frame(frame, (900, 1600))
    backend = FakeVideoBackend(
        probe_payloads={
            video: {
                "format": {"duration": "1.0"},
                "streams": [{"codec_type": "video", "width": 1920, "height": 1080}],
            }
        }
    )
    processor = VideoFrameProcessor(backend=backend)
    config = VideoFrameJobConfig(
        input_files=[video],
        frame_files=[frame],
        output_size_mode=OUTPUT_SIZE_AUTO_STANDARD,
    )
    output = tmp_path / "out.mp4"

    arguments = processor.build_ffmpeg_arguments(video, frame, output, config)

    filter_text = arguments[arguments.index("-filter_complex") + 1]
    assert filter_text.startswith("[1:v]scale=1080:1920[bg];[0:v]scale=1086:612[fg];")


def test_build_frame_command_supports_custom_output_size(tmp_path: Path) -> None:
    video = tmp_path / "video.mp4"
    video.write_bytes(b"video")
    frame = tmp_path / "landscape.png"
    create_frame(frame, (1920, 1080))
    backend = FakeVideoBackend(
        probe_payloads={
            video: {
                "format": {"duration": "1.0"},
                "streams": [{"codec_type": "video", "width": 1080, "height": 1920}],
            }
        }
    )
    processor = VideoFrameProcessor(backend=backend)
    config = VideoFrameJobConfig(
        input_files=[video],
        frame_files=[frame],
        output_size_mode=OUTPUT_SIZE_CUSTOM,
        custom_output_size=(1280, 720),
    )
    output = tmp_path / "out.mp4"

    arguments = processor.build_ffmpeg_arguments(video, frame, output, config)

    filter_text = arguments[arguments.index("-filter_complex") + 1]
    assert filter_text == (
        "[1:v]scale=1280:720[bg];"
        "[0:v]scale=408:724[fg];"
        "[bg][fg]overlay=436:-2:shortest=1[outv]"
    )


def test_process_batch_outputs_each_video_frame_pair(tmp_path: Path) -> None:
    video = tmp_path / "video.mp4"
    video.write_bytes(b"video")
    first = tmp_path / "square.png"
    second = tmp_path / "wide.png"
    create_frame(first, (1080, 1080))
    create_frame(second, (1920, 1080))
    backend = FakeVideoBackend(
        probe_payloads={
            video: {
                "format": {"duration": "1.0"},
                "streams": [{"codec_type": "video", "width": 1920, "height": 1080}],
            }
        }
    )
    processor = VideoFrameProcessor(backend=backend)
    output_dir = tmp_path / "exports"
    config = VideoFrameJobConfig(input_files=[video], frame_files=[first, second], output_directory=output_dir)

    summary = processor.process_batch(config)

    assert summary.total == 2
    assert summary.succeeded == 2
    assert (output_dir / "square" / "video.mp4").exists()
    assert (output_dir / "wide" / "video.mp4").exists()
