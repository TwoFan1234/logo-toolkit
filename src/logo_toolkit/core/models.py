from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


class ExportMode(str, Enum):
    NEW_FOLDER = "new_folder"
    OVERWRITE = "overwrite"


class TransformFormat(str, Enum):
    KEEP = "keep"
    JPEG = "jpeg"
    PNG = "png"
    WEBP = "webp"


class CompressionLevel(str, Enum):
    NONE = "none"
    LIGHT = "light"
    MEDIUM = "medium"
    HIGH = "high"


class ResizeMode(str, Enum):
    NONE = "none"
    SCALE_PERCENT = "scale_percent"
    LONGEST_EDGE = "longest_edge"
    EXACT_DIMENSIONS = "exact_dimensions"


class VideoOperationType(str, Enum):
    COMPRESS = "compress"
    CONVERT = "convert"
    TRIM = "trim"
    RESIZE = "resize"
    EXTRACT_AUDIO = "extract_audio"


class VideoCompressionPreset(str, Enum):
    HIGH_QUALITY = "high_quality"
    BALANCED = "balanced"
    HIGH_COMPRESSION = "high_compression"


class VideoContainerFormat(str, Enum):
    MP4 = "mp4"
    MOV = "mov"
    MKV = "mkv"
    AVI = "avi"
    WEBM = "webm"


class AudioExportFormat(str, Enum):
    MP3 = "mp3"
    WAV = "wav"
    AAC = "aac"


@dataclass(slots=True)
class LogoPlacement:
    x_ratio: float = 0.05
    y_ratio: float = 0.05
    width_ratio: float = 0.2
    anchor: str = "top_left"

    def normalized(self) -> "LogoPlacement":
        return LogoPlacement(
            x_ratio=min(max(self.x_ratio, 0.0), 1.0),
            y_ratio=min(max(self.y_ratio, 0.0), 1.0),
            width_ratio=min(max(self.width_ratio, 0.01), 1.0),
            anchor=self.anchor or "top_left",
        )


@dataclass(slots=True)
class RenderOptions:
    keep_aspect_ratio: bool = True
    smoothing: bool = True


@dataclass(slots=True)
class ImageItem:
    source_path: Path
    import_root: Path | None = None
    width: int | None = None
    height: int | None = None
    status: str = "待处理"
    message: str = ""
    output_path: Path | None = None

    @property
    def display_name(self) -> str:
        return self.source_path.name

    @property
    def resolution_text(self) -> str:
        if self.width and self.height:
            return f"{self.width} x {self.height}"
        return "-"


@dataclass(slots=True)
class VideoCompressionSettings:
    preset: VideoCompressionPreset = VideoCompressionPreset.BALANCED
    target_format: VideoContainerFormat = VideoContainerFormat.MP4


@dataclass(slots=True)
class VideoConversionSettings:
    target_format: VideoContainerFormat = VideoContainerFormat.MP4


@dataclass(slots=True)
class VideoTrimSettings:
    start_time: str = ""
    end_time: str = ""


@dataclass(slots=True)
class VideoResizeSettings:
    width: int = 1280
    height: int = 720
    keep_aspect_ratio: bool = True


@dataclass(slots=True)
class AudioExtractSettings:
    target_format: AudioExportFormat = AudioExportFormat.MP3


@dataclass(slots=True)
class VideoItem:
    source_path: Path
    import_root: Path | None = None
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    status: str = "待处理"
    message: str = ""
    output_path: Path | None = None

    @property
    def display_name(self) -> str:
        return self.source_path.name

    @property
    def resolution_text(self) -> str:
        if self.width and self.height:
            return f"{self.width} x {self.height}"
        return "-"

    @property
    def duration_text(self) -> str:
        if self.duration_seconds is None:
            return "-"
        total_seconds = max(0, int(round(self.duration_seconds)))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


@dataclass(slots=True)
class BatchJobConfig:
    input_files: list[Path]
    logo_file: Path
    placement: LogoPlacement
    render_options: RenderOptions
    export_mode: ExportMode = ExportMode.NEW_FOLDER
    output_directory: Path | None = None
    output_suffix: str = ""
    preserve_structure: bool = False
    source_roots: dict[Path, Path | None] = field(default_factory=dict)


@dataclass(slots=True)
class ResizeConfig:
    mode: ResizeMode = ResizeMode.NONE
    scale_percent: int = 100
    longest_edge: int = 1600
    target_width: int = 1600
    target_height: int = 1600
    keep_aspect_ratio: bool = True


@dataclass(slots=True)
class BatchTransformConfig:
    input_files: list[Path]
    transform_format: TransformFormat = TransformFormat.KEEP
    compression_level: CompressionLevel = CompressionLevel.NONE
    resize_config: ResizeConfig = field(default_factory=ResizeConfig)
    export_mode: ExportMode = ExportMode.NEW_FOLDER
    output_directory: Path | None = None
    preserve_structure: bool = True
    source_roots: dict[Path, Path | None] = field(default_factory=dict)

    def has_operations(self) -> bool:
        return any(
            (
                self.transform_format != TransformFormat.KEEP,
                self.compression_level != CompressionLevel.NONE,
                self.resize_config.mode != ResizeMode.NONE,
            )
        )


@dataclass(slots=True)
class VideoBatchConfig:
    input_files: list[Path]
    operation_type: VideoOperationType
    output_directory: Path | None = None
    output_suffix: str = ""
    preserve_structure: bool = True
    source_roots: dict[Path, Path | None] = field(default_factory=dict)
    compression: VideoCompressionSettings = field(default_factory=VideoCompressionSettings)
    conversion: VideoConversionSettings = field(default_factory=VideoConversionSettings)
    trim: VideoTrimSettings = field(default_factory=VideoTrimSettings)
    resize: VideoResizeSettings = field(default_factory=VideoResizeSettings)
    audio_extract: AudioExtractSettings = field(default_factory=AudioExtractSettings)


@dataclass(slots=True)
class TemplatePreset:
    name: str
    placement: LogoPlacement
    margin_ratio: float
    export_mode: ExportMode
    preserve_structure: bool
    logo_path: Path | None = None
    output_directory: Path | None = None

    def normalized_export_mode(self) -> ExportMode:
        if isinstance(self.export_mode, ExportMode):
            return self.export_mode
        return ExportMode(str(self.export_mode))

    def to_dict(self) -> dict[str, object]:
        export_mode = self.normalized_export_mode()
        return {
            "name": self.name,
            "logo_path": str(self.logo_path) if self.logo_path else None,
            "output_directory": str(self.output_directory) if self.output_directory else None,
            "margin_ratio": self.margin_ratio,
            "export_mode": export_mode.value,
            "preserve_structure": self.preserve_structure,
            "placement": {
                "x_ratio": self.placement.x_ratio,
                "y_ratio": self.placement.y_ratio,
                "width_ratio": self.placement.width_ratio,
                "anchor": self.placement.anchor,
            },
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "TemplatePreset":
        placement_payload = payload.get("placement", {})
        if not isinstance(placement_payload, dict):
            placement_payload = {}
        return cls(
            name=str(payload.get("name", "未命名模板")),
            logo_path=Path(payload["logo_path"]) if payload.get("logo_path") else None,
            output_directory=Path(payload["output_directory"]) if payload.get("output_directory") else None,
            margin_ratio=float(payload.get("margin_ratio", 0.0)),
            export_mode=ExportMode(str(payload.get("export_mode", ExportMode.NEW_FOLDER.value))),
            preserve_structure=bool(payload.get("preserve_structure", True)),
            placement=LogoPlacement(
                x_ratio=float(placement_payload.get("x_ratio", 0.05)),
                y_ratio=float(placement_payload.get("y_ratio", 0.05)),
                width_ratio=float(placement_payload.get("width_ratio", 0.2)),
                anchor=str(placement_payload.get("anchor", "top_left")),
            ).normalized(),
        )


@dataclass(slots=True)
class ExportResult:
    source_path: Path
    success: bool
    output_path: Path | None = None
    error: str = ""


@dataclass(slots=True)
class BatchSummary:
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    results: list[ExportResult] = field(default_factory=list)
