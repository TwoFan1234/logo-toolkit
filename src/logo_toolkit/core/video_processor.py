from __future__ import annotations

import hashlib
import re
import tempfile
from pathlib import Path
from typing import Any, Callable

from PIL import Image

from logo_toolkit.core.models import (
    AudioExportFormat,
    AudioExtractSettings,
    BatchSummary,
    ExportResult,
    SUPPORTED_VIDEO_EXTENSIONS,
    VideoBatchConfig,
    VideoCompressionPreset,
    VideoContainerFormat,
    VideoEndCardAlphaMode,
    VideoItem,
    VideoOperationType,
    VideoResizeSettings,
    VideoTrimSettings,
)
from logo_toolkit.core.video_backend import VideoBackend


TIMECODE_PATTERN = re.compile(r"^\d{1,2}:\d{2}:\d{2}(?:\.\d{1,3})?$")


class VideoProcessor:
    """Pure video processing service backed by ffmpeg/ffprobe."""

    def __init__(self, backend: VideoBackend | None = None) -> None:
        self.backend = backend or VideoBackend()

    def get_video_metadata(self, source_path: Path) -> VideoItem:
        self.validate_video(source_path)
        payload = self.backend.probe(source_path)
        duration, width, height, frame_rate = self.parse_probe_metadata(payload)
        return VideoItem(
            source_path=source_path,
            duration_seconds=duration,
            width=width,
            height=height,
            frame_rate=frame_rate,
        )

    def extract_preview_frame(self, source_path: Path, timestamp_seconds: float = 0.0) -> Path:
        self.validate_video(source_path)
        stat = source_path.stat()
        fingerprint = hashlib.sha1(
            f"{source_path.resolve()}::{stat.st_mtime_ns}::{timestamp_seconds:.3f}".encode("utf-8")
        ).hexdigest()
        cache_dir = Path(tempfile.gettempdir()) / "logo_toolkit" / "video_previews"
        preview_path = cache_dir / f"{fingerprint}.png"
        if not preview_path.exists():
            self.backend.extract_frame(source_path, preview_path, timestamp_seconds=timestamp_seconds)
        return preview_path

    def validate_video(self, source_path: Path) -> None:
        if source_path.suffix.lower() not in SUPPORTED_VIDEO_EXTENSIONS:
            raise ValueError(f"不支持的视频格式: {source_path.suffix}")

    @staticmethod
    def parse_probe_metadata(payload: dict[str, Any]) -> tuple[float | None, int | None, int | None, str | None]:
        streams = payload.get("streams", [])
        if not isinstance(streams, list):
            streams = []
        video_stream = next(
            (
                stream
                for stream in streams
                if isinstance(stream, dict) and str(stream.get("codec_type", "")).lower() == "video"
            ),
            None,
        )
        width = int(video_stream.get("width", 0)) or None if isinstance(video_stream, dict) else None
        height = int(video_stream.get("height", 0)) or None if isinstance(video_stream, dict) else None

        format_payload = payload.get("format", {})
        if not isinstance(format_payload, dict):
            format_payload = {}
        duration = VideoProcessor._float_or_none(format_payload.get("duration"))
        if duration is None and isinstance(video_stream, dict):
            duration = VideoProcessor._float_or_none(video_stream.get("duration"))
        frame_rate = None
        if isinstance(video_stream, dict):
            frame_rate = (
                VideoProcessor._frame_rate_or_none(video_stream.get("avg_frame_rate"))
                or VideoProcessor._frame_rate_or_none(video_stream.get("r_frame_rate"))
            )
        return duration, width, height, frame_rate

    def process_batch(
        self,
        config: VideoBatchConfig,
        progress_callback: Callable[[int, int, ExportResult], None] | None = None,
        only_files: list[Path] | None = None,
    ) -> BatchSummary:
        files = only_files or config.input_files
        summary = BatchSummary(total=len(files))
        output_directory = self.resolve_output_directory(config)

        for index, source_path in enumerate(files, start=1):
            try:
                self.validate_video(source_path)
                result_path = self.export_video(
                    source_path=source_path,
                    config=config,
                    output_directory=output_directory,
                    source_root=config.source_roots.get(source_path),
                )
                result = ExportResult(source_path=source_path, success=True, output_path=result_path)
                summary.succeeded += 1
            except Exception as exc:  # noqa: BLE001
                result = ExportResult(source_path=source_path, success=False, error=str(exc))
                summary.failed += 1

            summary.results.append(result)
            if progress_callback:
                progress_callback(index, summary.total, result)

        return summary

    def export_video(
        self,
        source_path: Path,
        config: VideoBatchConfig,
        output_directory: Path | None,
        source_root: Path | None = None,
    ) -> Path:
        self.validate_video(source_path)
        if config.operation_type == VideoOperationType.ADD_LOGO and config.logo_overlay.logo_file is None:
            raise ValueError("请先选择一张 Logo 图片。")
        if config.operation_type == VideoOperationType.ADD_ENDCARD and config.endcard.endcard_file is None:
            raise ValueError("请先选择一个 EC 视频。")

        output_path = self.build_output_path(
            source_path=source_path,
            operation_type=config.operation_type,
            output_directory=output_directory,
            output_suffix=config.output_suffix,
            preserve_structure=config.preserve_structure,
            source_root=source_root,
            config=config,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        arguments = self.build_ffmpeg_arguments(source_path, output_path, config)
        self.backend.run_ffmpeg(arguments)
        return output_path

    def build_ffmpeg_arguments(self, source_path: Path, output_path: Path, config: VideoBatchConfig) -> list[str]:
        operation = config.operation_type
        if operation == VideoOperationType.COMPRESS:
            return [
                "-y",
                "-i",
                str(source_path),
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                self._compression_crf(config.compression.preset),
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-movflags",
                "+faststart",
                str(output_path),
            ]

        if operation == VideoOperationType.CONVERT:
            codec_args = self._codec_arguments_for_suffix(output_path.suffix.lower())
            return ["-y", "-i", str(source_path), *codec_args, str(output_path)]

        if operation == VideoOperationType.TRIM:
            self.validate_trim_settings(config.trim)
            arguments = ["-y"]
            start_time = config.trim.start_time.strip()
            end_time = config.trim.end_time.strip()
            if start_time:
                arguments.extend(["-ss", start_time])
            arguments.extend(["-i", str(source_path)])
            if end_time:
                arguments.extend(["-to", end_time])
            arguments.extend(self._codec_arguments_for_suffix(output_path.suffix.lower()))
            arguments.append(str(output_path))
            return arguments

        if operation == VideoOperationType.RESIZE:
            scale_filter = self._scale_filter(config.resize)
            codec_args = self._codec_arguments_for_suffix(output_path.suffix.lower())
            return ["-y", "-i", str(source_path), "-vf", scale_filter, *codec_args, str(output_path)]

        if operation == VideoOperationType.EXTRACT_AUDIO:
            codec_args = self._audio_codec_arguments(config.audio_extract)
            return ["-y", "-i", str(source_path), "-vn", *codec_args, str(output_path)]

        if operation == VideoOperationType.ADD_LOGO:
            return self._build_add_logo_arguments(source_path, output_path, config)
        if operation == VideoOperationType.ADD_ENDCARD:
            return self._build_add_endcard_arguments(source_path, output_path, config)

        raise ValueError(f"未知的视频处理类型: {operation}")

    def resolve_output_directory(self, config: VideoBatchConfig) -> Path:
        if config.output_directory:
            return config.output_directory
        if not config.input_files:
            raise ValueError("没有可处理的视频文件")
        parent = config.input_files[0].parent
        candidate = parent / "video_output"
        counter = 1
        while candidate.exists():
            candidate = parent / f"video_output_{counter}"
            counter += 1
        return candidate

    def build_output_path(
        self,
        source_path: Path,
        operation_type: VideoOperationType,
        output_directory: Path | None,
        output_suffix: str,
        preserve_structure: bool,
        source_root: Path | None,
        config: VideoBatchConfig,
    ) -> Path:
        if output_directory is None:
            raise ValueError("视频处理必须提供输出目录")
        relative_path = self._build_relative_output_path(
            source_path=source_path,
            operation_type=operation_type,
            output_suffix=output_suffix,
            preserve_structure=preserve_structure,
            source_root=source_root,
            config=config,
        )
        return self._ensure_unique_output_path(output_directory / relative_path)

    def _build_relative_output_path(
        self,
        source_path: Path,
        operation_type: VideoOperationType,
        output_suffix: str,
        preserve_structure: bool,
        source_root: Path | None,
        config: VideoBatchConfig,
    ) -> Path:
        target_suffix = self._target_extension(source_path, operation_type, config)
        file_name = f"{source_path.stem}{target_suffix}"
        if not preserve_structure or source_root is None:
            return Path(file_name)
        try:
            relative_path = source_path.relative_to(source_root)
        except ValueError:
            return Path(file_name)
        return Path(source_root.name) / relative_path.parent / file_name

    def _target_extension(
        self,
        source_path: Path,
        operation_type: VideoOperationType,
        config: VideoBatchConfig,
    ) -> str:
        if operation_type == VideoOperationType.COMPRESS:
            return ".mp4"
        if operation_type == VideoOperationType.ADD_ENDCARD:
            return ".mp4"
        if operation_type == VideoOperationType.CONVERT:
            return f".{config.conversion.target_format.value}"
        if operation_type == VideoOperationType.EXTRACT_AUDIO:
            return f".{config.audio_extract.target_format.value}"
        return source_path.suffix.lower()

    def _ensure_unique_output_path(self, path: Path) -> Path:
        if not path.exists():
            return path
        counter = 1
        while True:
            candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
            if not candidate.exists():
                return candidate
            counter += 1

    def validate_trim_settings(self, settings: VideoTrimSettings) -> None:
        start = settings.start_time.strip()
        end = settings.end_time.strip()
        if not start and not end:
            raise ValueError("裁剪至少需要填写开始时间或结束时间。")
        if start:
            self._parse_timecode(start)
        if end:
            self._parse_timecode(end)
        if start and end and self._parse_timecode(start) >= self._parse_timecode(end):
            raise ValueError("裁剪开始时间必须早于结束时间。")

    def _scale_filter(self, settings: VideoResizeSettings) -> str:
        width = max(0, int(settings.width))
        height = max(0, int(settings.height))
        if settings.keep_aspect_ratio:
            if width <= 0 and height <= 0:
                raise ValueError("保持比例时至少要填写宽度或高度。")
            if width > 0 and height > 0:
                return f"scale={width}:{height}:force_original_aspect_ratio=decrease"
            if width > 0:
                return f"scale={width}:-2"
            return f"scale=-2:{height}"
        if width <= 0 or height <= 0:
            raise ValueError("关闭保持比例时必须同时填写宽度和高度。")
        return f"scale={width}:{height}"

    def _build_add_logo_arguments(
        self,
        source_path: Path,
        output_path: Path,
        config: VideoBatchConfig,
    ) -> list[str]:
        logo_path = config.logo_overlay.logo_file
        if logo_path is None:
            raise ValueError("请先选择一张 Logo 图片。")
        target_x, target_y, target_width, target_height = self._logo_overlay_geometry(
            source_path=source_path,
            logo_path=logo_path,
            config=config,
        )
        filter_complex = (
            f"[1:v]scale={target_width}:{target_height}[logo];"
            f"[0:v][logo]overlay={target_x}:{target_y}[outv]"
        )
        codec_args = self._codec_arguments_for_suffix(output_path.suffix.lower())
        arguments = [
            "-y",
            "-i",
            str(source_path),
            "-i",
            str(logo_path),
            "-filter_complex",
            filter_complex,
            "-map",
            "[outv]",
            "-map",
            "0:a?",
            *codec_args,
        ]
        if output_path.suffix.lower() in {".mp4", ".mov", ".m4v"}:
            arguments.extend(["-movflags", "+faststart"])
        arguments.append(str(output_path))
        return arguments

    def _build_add_endcard_arguments(
        self,
        source_path: Path,
        output_path: Path,
        config: VideoBatchConfig,
    ) -> list[str]:
        endcard_path = config.endcard.endcard_file
        if endcard_path is None:
            raise ValueError("请先选择一个 EC 视频。")

        self.validate_video(endcard_path)
        source_payload = self.backend.probe(source_path)
        endcard_payload = self.backend.probe(endcard_path)

        source_duration, source_width, source_height, _ = self.parse_probe_metadata(source_payload)
        endcard_duration, _, _, _ = self.parse_probe_metadata(endcard_payload)
        if source_duration is None or endcard_duration is None:
            raise ValueError("无法读取视频时长，不能叠加 EC。")
        if not source_width or not source_height:
            raise ValueError("无法读取素材分辨率，不能叠加 EC。")

        requested_overlap = max(0.0, float(config.endcard.overlap_seconds))
        requested_crossfade = max(0.0, float(config.endcard.audio_crossfade_seconds))
        actual_overlap = min(requested_overlap, source_duration, endcard_duration)
        actual_crossfade = min(requested_crossfade, actual_overlap)
        delay_seconds = max(0.0, source_duration - actual_overlap)
        tail_duration = max(0.0, endcard_duration - actual_overlap)

        endcard_video_chain = ["format=rgba"]
        if config.endcard.alpha_mode == VideoEndCardAlphaMode.PREMIERE_COMPAT:
            endcard_video_chain.append(self._remove_black_matte_filter())
        endcard_video_chain.append(f"scale={source_width}:{source_height}")
        endcard_video_chain.append(f"setpts=PTS-STARTPTS+{delay_seconds:.3f}/TB")

        filter_parts = [
            f"[0:v]setpts=PTS-STARTPTS,format=rgba,tpad=stop_mode=clone:stop_duration={tail_duration:.3f}[basev]",
            f"[1:v]{','.join(endcard_video_chain)}[endv]",
            "[basev][endv]overlay=0:0:eof_action=pass:format=rgb:alpha=straight[outv]",
        ]

        source_has_audio = self._has_stream(source_payload, "audio")
        endcard_has_audio = self._has_stream(endcard_payload, "audio")
        has_output_audio = False

        if source_has_audio and endcard_has_audio:
            filter_parts.append("[0:a]asetpts=PTS-STARTPTS[sourcea]")

            endcard_audio_filters = [f"adelay={self._seconds_to_milliseconds(delay_seconds)}:all=1"]
            if actual_crossfade > 0:
                endcard_audio_filters.append(f"afade=t=in:st={delay_seconds:.3f}:d={actual_crossfade:.3f}")
            filter_parts.append(f"[1:a]{','.join(endcard_audio_filters)}[endcarda]")
            # Keep the source audio during overlap and stack the EC audio on top of it.
            filter_parts.append(
                "[sourcea][endcarda]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[outa]"
            )
            has_output_audio = True
        elif source_has_audio:
            filter_parts.append("[0:a]asetpts=PTS-STARTPTS[outa]")
            has_output_audio = True
        elif endcard_has_audio:
            endcard_audio_filters = [f"adelay={self._seconds_to_milliseconds(delay_seconds)}:all=1"]
            if actual_crossfade > 0:
                endcard_audio_filters.append(f"afade=t=in:st={delay_seconds:.3f}:d={actual_crossfade:.3f}")
            filter_parts.append(f"[1:a]{','.join(endcard_audio_filters)}[outa]")
            has_output_audio = True

        arguments = [
            "-y",
            "-i",
            str(source_path),
            "-i",
            str(endcard_path),
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            "[outv]",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-pix_fmt",
            "yuv420p",
        ]
        if has_output_audio:
            arguments.extend(["-map", "[outa]", "-c:a", "aac", "-b:a", "128k"])
        arguments.extend(["-movflags", "+faststart", str(output_path)])
        return arguments

    def _logo_overlay_geometry(
        self,
        source_path: Path,
        logo_path: Path,
        config: VideoBatchConfig,
    ) -> tuple[int, int, int, int]:
        metadata = self.get_video_metadata(source_path)
        if not metadata.width or not metadata.height:
            raise ValueError("无法读取视频分辨率，不能计算 Logo 位置。")

        with Image.open(logo_path) as image:
            logo_width, logo_height = image.size
        if logo_width <= 0 or logo_height <= 0:
            raise ValueError("Logo 图片尺寸无效。")

        if config.logo_overlay.use_pixel_positioning:
            pixel_placement = config.logo_overlay.pixel_placement.normalized()
            target_x, target_y, target_width, target_height = pixel_placement.to_overlay_box(
                frame_width=metadata.width,
                frame_height=metadata.height,
                logo_width=logo_width,
                logo_height=logo_height,
                keep_aspect_ratio=config.logo_overlay.render_options.keep_aspect_ratio,
            )
        else:
            placement = config.logo_overlay.placement.normalized()
            target_x, target_y, target_width, target_height = placement.to_overlay_box(
                frame_width=metadata.width,
                frame_height=metadata.height,
                logo_width=logo_width,
                logo_height=logo_height,
                keep_aspect_ratio=config.logo_overlay.render_options.keep_aspect_ratio,
                reference_mode=config.logo_overlay.render_options.reference_mode,
            )
        return (
            int(round(target_x)),
            int(round(target_y)),
            int(round(target_width)),
            int(round(target_height)),
        )

    def _compression_crf(self, preset: VideoCompressionPreset) -> str:
        if preset == VideoCompressionPreset.HIGH_QUALITY:
            return "23"
        if preset == VideoCompressionPreset.HIGH_COMPRESSION:
            return "32"
        return "28"

    def _codec_arguments_for_suffix(self, suffix: str) -> list[str]:
        if suffix == ".webm":
            return ["-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "32", "-c:a", "libopus"]
        if suffix == ".avi":
            return ["-c:v", "mpeg4", "-q:v", "5", "-c:a", "libmp3lame", "-q:a", "4"]
        return ["-c:v", "libx264", "-preset", "medium", "-c:a", "aac", "-b:a", "128k"]

    def _audio_codec_arguments(self, settings: AudioExtractSettings) -> list[str]:
        if settings.target_format == AudioExportFormat.WAV:
            return ["-c:a", "pcm_s16le"]
        if settings.target_format == AudioExportFormat.AAC:
            return ["-c:a", "aac", "-b:a", "192k"]
        return ["-c:a", "libmp3lame", "-q:a", "2"]

    @staticmethod
    def _remove_black_matte_filter() -> str:
        # AE/qtrle end cards in this workflow carry dark premultiplied-looking edge pixels.
        # Expand RGB by alpha before compositing so overlap particles don't darken the source.
        return (
            "geq="
            "r='if(gt(alpha(X,Y),0),min(255,r(X,Y)*255/alpha(X,Y)),0)':"
            "g='if(gt(alpha(X,Y),0),min(255,g(X,Y)*255/alpha(X,Y)),0)':"
            "b='if(gt(alpha(X,Y),0),min(255,b(X,Y)*255/alpha(X,Y)),0)':"
            "a='alpha(X,Y)'"
        )

    @staticmethod
    def _has_stream(payload: dict[str, Any], codec_type: str) -> bool:
        streams = payload.get("streams", [])
        if not isinstance(streams, list):
            return False
        target_codec_type = codec_type.lower()
        return any(
            isinstance(stream, dict) and str(stream.get("codec_type", "")).lower() == target_codec_type
            for stream in streams
        )

    @staticmethod
    def _seconds_to_milliseconds(value: float) -> int:
        return max(0, int(round(float(value) * 1000)))

    def _parse_timecode(self, value: str) -> float:
        if not TIMECODE_PATTERN.fullmatch(value):
            raise ValueError(f"无效的时间格式: {value}。请使用 HH:MM:SS 或 HH:MM:SS.mmm")
        hours_text, minutes_text, seconds_text = value.split(":")
        return int(hours_text) * 3600 + int(minutes_text) * 60 + float(seconds_text)

    @staticmethod
    def _float_or_none(value: Any) -> float | None:
        try:
            if value in (None, ""):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _frame_rate_or_none(value: Any) -> str | None:
        text = str(value or "").strip()
        if not text or text == "0/0":
            return None
        if "/" in text:
            numerator_text, denominator_text = text.split("/", 1)
            try:
                numerator = int(numerator_text)
                denominator = int(denominator_text)
            except ValueError:
                return None
            if numerator <= 0 or denominator <= 0:
                return None
            return f"{numerator}/{denominator}"
        try:
            frame_rate = float(text)
        except ValueError:
            return None
        if frame_rate <= 0:
            return None
        return f"{frame_rate:g}"
