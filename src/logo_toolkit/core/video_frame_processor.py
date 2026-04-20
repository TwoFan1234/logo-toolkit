from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from PIL import Image

from logo_toolkit.core.models import (
    BatchSummary,
    ExportResult,
    SUPPORTED_EXTENSIONS,
    VideoItem,
    common_aspect_ratio_label,
)
from logo_toolkit.core.video_backend import VideoBackend
from logo_toolkit.core.video_processor import VideoProcessor


OUTPUT_SIZE_FOLLOW_FRAME = "follow_frame"
OUTPUT_SIZE_AUTO_STANDARD = "auto_standard"
OUTPUT_SIZE_CUSTOM = "custom"
DEFAULT_VIDEO_FRAME_SCALE_FACTOR = 1.005


@dataclass(slots=True)
class FrameImageItem:
    source_path: Path
    width: int | None = None
    height: int | None = None
    selected_for_batch: bool = True
    status: str = "待处理"
    message: str = ""

    @property
    def display_name(self) -> str:
        return self.source_path.name

    @property
    def resolution_text(self) -> str:
        if self.width and self.height:
            return f"{self.width} x {self.height}"
        return "-"

    @property
    def ratio_text(self) -> str:
        if not self.width or not self.height:
            return "-"
        return VideoFrameProcessor.ratio_label(self.width, self.height)


@dataclass(slots=True)
class VideoFrameJobConfig:
    input_files: list[Path]
    frame_files: list[Path]
    output_directory: Path | None = None
    output_size_mode: str = OUTPUT_SIZE_FOLLOW_FRAME
    custom_output_size: tuple[int, int] | None = None
    source_roots: dict[Path, Path | None] = field(default_factory=dict)


class VideoFrameProcessor:
    """Compose videos over still border/background images."""

    def __init__(self, backend: VideoBackend | None = None) -> None:
        self.backend = backend or VideoBackend()
        self.video_processor = VideoProcessor(backend=self.backend)

    def get_video_metadata(self, source_path: Path) -> VideoItem:
        return self.video_processor.get_video_metadata(source_path)

    def get_frame_metadata(self, frame_path: Path) -> FrameImageItem:
        self.validate_frame(frame_path)
        with Image.open(frame_path) as image:
            width, height = image.size
        return FrameImageItem(source_path=frame_path, width=width, height=height)

    def validate_frame(self, frame_path: Path) -> None:
        if frame_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"不支持的边框图片格式: {frame_path.suffix}")

    def process_batch(
        self,
        config: VideoFrameJobConfig,
        progress_callback: Callable[[int, int, ExportResult], None] | None = None,
    ) -> BatchSummary:
        pairs = [(video_path, frame_path) for video_path in config.input_files for frame_path in config.frame_files]
        summary = BatchSummary(total=len(pairs))
        output_directory = self.resolve_output_directory(config)

        for index, (video_path, frame_path) in enumerate(pairs, start=1):
            try:
                result_path = self.export_video(
                    video_path=video_path,
                    frame_path=frame_path,
                    config=config,
                    output_directory=output_directory,
                    source_root=config.source_roots.get(video_path),
                )
                result = ExportResult(source_path=video_path, success=True, output_path=result_path)
                summary.succeeded += 1
            except Exception as exc:  # noqa: BLE001
                result = ExportResult(source_path=video_path, success=False, error=f"{frame_path.name}: {exc}")
                summary.failed += 1

            summary.results.append(result)
            if progress_callback:
                progress_callback(index, summary.total, result)

        return summary

    def export_video(
        self,
        video_path: Path,
        frame_path: Path,
        config: VideoFrameJobConfig,
        output_directory: Path | None,
        source_root: Path | None = None,
    ) -> Path:
        self.video_processor.validate_video(video_path)
        self.validate_frame(frame_path)
        output_path = self.build_output_path(video_path, frame_path, output_directory, source_root)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        arguments = self.build_ffmpeg_arguments(video_path, frame_path, output_path, config)
        self.backend.run_ffmpeg(arguments)
        return output_path

    def build_ffmpeg_arguments(
        self,
        video_path: Path,
        frame_path: Path,
        output_path: Path,
        config: VideoFrameJobConfig,
    ) -> list[str]:
        video_item = self.get_video_metadata(video_path)
        if not video_item.width or not video_item.height:
            raise ValueError("无法读取视频分辨率，不能自动适配边框。")
        frame_item = self.get_frame_metadata(frame_path)
        if not frame_item.width or not frame_item.height:
            raise ValueError("无法读取边框图片尺寸。")

        output_width, output_height = self.output_size_for_frame(
            frame_width=frame_item.width,
            frame_height=frame_item.height,
            mode=config.output_size_mode,
            custom_output_size=config.custom_output_size,
        )
        video_width, video_height = self.scaled_video_size(
            source_width=video_item.width,
            source_height=video_item.height,
            canvas_width=output_width,
            canvas_height=output_height,
        )
        overlay_x = int(round((output_width - video_width) / 2))
        overlay_y = int(round((output_height - video_height) / 2))

        filter_complex = (
            f"[1:v]scale={output_width}:{output_height}[bg];"
            f"[0:v]scale={video_width}:{video_height}[fg];"
            f"[bg][fg]overlay={overlay_x}:{overlay_y}:shortest=1[outv]"
        )
        frame_input_args = ["-loop", "1"]
        if video_item.frame_rate:
            frame_input_args.extend(["-framerate", video_item.frame_rate])

        arguments = [
            "-y",
            "-i",
            str(video_path),
            *frame_input_args,
            "-i",
            str(frame_path),
            "-filter_complex",
            filter_complex,
            "-map",
            "[outv]",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-shortest",
        ]
        if output_path.suffix.lower() in {".mp4", ".mov", ".m4v"}:
            arguments.extend(["-movflags", "+faststart"])
        arguments.append(str(output_path))
        return arguments

    def resolve_output_directory(self, config: VideoFrameJobConfig) -> Path:
        if config.output_directory:
            return config.output_directory
        if not config.input_files:
            raise ValueError("没有可处理的视频文件")
        parent = config.input_files[0].parent
        candidate = parent / "framed_video_output"
        counter = 1
        while candidate.exists():
            candidate = parent / f"framed_video_output_{counter}"
            counter += 1
        return candidate

    def build_output_path(
        self,
        video_path: Path,
        frame_path: Path,
        output_directory: Path | None,
        source_root: Path | None = None,
    ) -> Path:
        if output_directory is None:
            raise ValueError("必须提供输出目录")
        file_name = video_path.name
        frame_folder = frame_path.stem
        if source_root is None:
            return self._ensure_unique_output_path(output_directory / frame_folder / file_name)
        try:
            relative_parent = video_path.relative_to(source_root).parent
        except ValueError:
            relative_parent = Path()
        return self._ensure_unique_output_path(output_directory / frame_folder / source_root.name / relative_parent / file_name)

    @staticmethod
    def output_size_for_frame(
        frame_width: int,
        frame_height: int,
        mode: str = OUTPUT_SIZE_FOLLOW_FRAME,
        custom_output_size: tuple[int, int] | None = None,
    ) -> tuple[int, int]:
        if mode == OUTPUT_SIZE_CUSTOM and custom_output_size:
            return VideoFrameProcessor._even_size(custom_output_size[0], custom_output_size[1])
        if mode == OUTPUT_SIZE_AUTO_STANDARD:
            return VideoFrameProcessor.standard_size_for_ratio(frame_width, frame_height)
        return VideoFrameProcessor._even_size(frame_width, frame_height)

    @staticmethod
    def scaled_video_size(
        source_width: int,
        source_height: int,
        canvas_width: int,
        canvas_height: int,
    ) -> tuple[int, int]:
        if source_width >= source_height:
            target_width = canvas_width
            target_height = int(round(source_height * target_width / max(source_width, 1)))
        else:
            target_height = canvas_height
            target_width = int(round(source_width * target_height / max(source_height, 1)))
        return VideoFrameProcessor._scaled_video_size_with_zoom(target_width, target_height)

    @staticmethod
    def _scaled_video_size_with_zoom(width: int, height: int) -> tuple[int, int]:
        return (
            VideoFrameProcessor._even_dimension_up(width * DEFAULT_VIDEO_FRAME_SCALE_FACTOR),
            VideoFrameProcessor._even_dimension_up(height * DEFAULT_VIDEO_FRAME_SCALE_FACTOR),
        )

    @staticmethod
    def standard_size_for_ratio(width: int, height: int) -> tuple[int, int]:
        ratio = width / max(height, 1)
        if VideoFrameProcessor._close_ratio(ratio, 16 / 9):
            return (1920, 1080)
        if VideoFrameProcessor._close_ratio(ratio, 1.0):
            return (1080, 1080)
        if VideoFrameProcessor._close_ratio(ratio, 9 / 16):
            return (1080, 1920)
        if width >= height:
            return VideoFrameProcessor._even_size(1920, round(1920 / ratio))
        return VideoFrameProcessor._even_size(round(1920 * ratio), 1920)

    @staticmethod
    def ratio_label(width: int, height: int) -> str:
        common_label = common_aspect_ratio_label(width, height)
        if common_label != "其他":
            return common_label
        return f"{width}:{height}"

    @staticmethod
    def _close_ratio(actual: float, expected: float, tolerance: float = 0.015) -> bool:
        return abs(actual - expected) <= tolerance

    @staticmethod
    def _even_size(width: int | float, height: int | float) -> tuple[int, int]:
        return VideoFrameProcessor._even_dimension(width), VideoFrameProcessor._even_dimension(height)

    @staticmethod
    def _even_dimension(value: int | float) -> int:
        integer = max(2, int(round(value)))
        return integer if integer % 2 == 0 else integer - 1

    @staticmethod
    def _even_dimension_up(value: int | float) -> int:
        from math import ceil

        integer = max(2, ceil(value))
        return integer if integer % 2 == 0 else integer + 1

    @staticmethod
    def _ensure_unique_output_path(path: Path) -> Path:
        if not path.exists():
            return path
        counter = 1
        while True:
            candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
            if not candidate.exists():
                return candidate
            counter += 1
