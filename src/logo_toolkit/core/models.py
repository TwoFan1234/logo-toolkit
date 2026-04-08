from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
LOGO_ANCHORS = ("top_left", "top_right", "bottom_left", "bottom_right")
LOGO_ANCHOR_LABELS = {
    "top_left": "左上角",
    "top_right": "右上角",
    "bottom_left": "左下角",
    "bottom_right": "右下角",
}
LOGO_REFERENCE_MODES = ("frame_axis", "frame_width", "short_side")
LOGO_REFERENCE_MODE_LABELS = {
    "frame_axis": "按画面宽高",
    "frame_width": "横屏优化（16:9 推荐）",
    "short_side": "按短边适配",
}


def resolve_logo_reference_axes(
    frame_width: float,
    frame_height: float,
    reference_mode: str,
) -> tuple[float, float, float]:
    safe_frame_width = max(frame_width, 1.0)
    safe_frame_height = max(frame_height, 1.0)
    short_side = min(safe_frame_width, safe_frame_height)
    landscape_safe = min(safe_frame_width, safe_frame_height * (4.0 / 3.0))

    if reference_mode == "frame_width":
        return landscape_safe, landscape_safe, landscape_safe
    if reference_mode == "short_side":
        return short_side, short_side, short_side
    return safe_frame_width, safe_frame_width, safe_frame_height


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
    ADD_LOGO = "add_logo"
    ADD_ENDCARD = "add_endcard"


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


class VideoEndCardAlphaMode(str, Enum):
    PREMIERE_COMPAT = "premiere_compat"
    DIRECT = "direct"


@dataclass(slots=True)
class LogoPlacement:
    x_ratio: float = 0.05
    y_ratio: float = 0.05
    width_ratio: float = 0.2
    anchor: str = "top_left"

    def normalized(self) -> "LogoPlacement":
        return LogoPlacement(
            x_ratio=max(self.x_ratio, 0.0),
            y_ratio=max(self.y_ratio, 0.0),
            width_ratio=min(max(self.width_ratio, 0.01), 1.0),
            anchor=self.anchor if self.anchor in LOGO_ANCHORS else "top_left",
        )

    def to_overlay_box(
        self,
        frame_width: float,
        frame_height: float,
        logo_width: float,
        logo_height: float,
        keep_aspect_ratio: bool = True,
        reference_mode: str = "frame_axis",
    ) -> tuple[float, float, float, float]:
        placement = self.normalized()
        width_reference, position_x_reference, position_y_reference = resolve_logo_reference_axes(
            frame_width=frame_width,
            frame_height=frame_height,
            reference_mode=reference_mode,
        )

        overlay_width = max(1.0, width_reference * placement.width_ratio)
        if keep_aspect_ratio:
            overlay_height = max(1.0, overlay_width * logo_height / max(logo_width, 1.0))
        else:
            overlay_height = overlay_width

        margin_x = placement.x_ratio * position_x_reference
        margin_y = placement.y_ratio * position_y_reference
        if placement.anchor in {"top_right", "bottom_right"}:
            left = frame_width - overlay_width - margin_x
        else:
            left = margin_x
        if placement.anchor in {"bottom_left", "bottom_right"}:
            top = frame_height - overlay_height - margin_y
        else:
            top = margin_y

        left = min(max(left, 0.0), max(0.0, frame_width - overlay_width))
        top = min(max(top, 0.0), max(0.0, frame_height - overlay_height))
        return left, top, overlay_width, overlay_height

    @classmethod
    def from_overlay_box(
        cls,
        left: float,
        top: float,
        overlay_width: float,
        overlay_height: float,
        frame_width: float,
        frame_height: float,
        anchor: str = "top_left",
        reference_mode: str = "frame_axis",
    ) -> "LogoPlacement":
        safe_frame_width = max(frame_width, 1.0)
        safe_frame_height = max(frame_height, 1.0)
        safe_overlay_width = max(overlay_width, 1.0)
        safe_overlay_height = max(overlay_height, 1.0)

        clamped_left = min(max(left, 0.0), max(0.0, safe_frame_width - safe_overlay_width))
        clamped_top = min(max(top, 0.0), max(0.0, safe_frame_height - safe_overlay_height))

        if anchor in {"top_right", "bottom_right"}:
            margin_x = safe_frame_width - safe_overlay_width - clamped_left
        else:
            margin_x = clamped_left
        if anchor in {"bottom_left", "bottom_right"}:
            margin_y = safe_frame_height - safe_overlay_height - clamped_top
        else:
            margin_y = clamped_top

        width_reference, position_x_reference, position_y_reference = resolve_logo_reference_axes(
            frame_width=safe_frame_width,
            frame_height=safe_frame_height,
            reference_mode=reference_mode,
        )

        return cls(
            x_ratio=margin_x / position_x_reference,
            y_ratio=margin_y / position_y_reference,
            width_ratio=safe_overlay_width / width_reference,
            anchor=anchor,
        ).normalized()

    def resolve_top_left(self, overlay_width_ratio: float, overlay_height_ratio: float) -> tuple[float, float]:
        placement = self.normalized()
        max_x = max(0.0, 1.0 - overlay_width_ratio)
        max_y = max(0.0, 1.0 - overlay_height_ratio)

        if placement.anchor in {"top_right", "bottom_right"}:
            x_ratio = max_x - placement.x_ratio
        else:
            x_ratio = placement.x_ratio

        if placement.anchor in {"bottom_left", "bottom_right"}:
            y_ratio = max_y - placement.y_ratio
        else:
            y_ratio = placement.y_ratio

        return (
            min(max(x_ratio, 0.0), max_x),
            min(max(y_ratio, 0.0), max_y),
        )

    @classmethod
    def from_top_left(
        cls,
        x_ratio: float,
        y_ratio: float,
        width_ratio: float,
        height_ratio: float,
        anchor: str = "top_left",
    ) -> "LogoPlacement":
        max_x = max(0.0, 1.0 - width_ratio)
        max_y = max(0.0, 1.0 - height_ratio)
        top_left_x = min(max(x_ratio, 0.0), max_x)
        top_left_y = min(max(y_ratio, 0.0), max_y)

        if anchor in {"top_right", "bottom_right"}:
            stored_x = max_x - top_left_x
        else:
            stored_x = top_left_x

        if anchor in {"bottom_left", "bottom_right"}:
            stored_y = max_y - top_left_y
        else:
            stored_y = top_left_y

        return cls(
            x_ratio=stored_x,
            y_ratio=stored_y,
            width_ratio=width_ratio,
            anchor=anchor,
        ).normalized()


@dataclass(slots=True)
class PixelLogoPlacement:
    margin_x_px: int = 40
    margin_y_px: int = 40
    width_px: int = 220
    anchor: str = "bottom_right"

    def normalized(self) -> "PixelLogoPlacement":
        return PixelLogoPlacement(
            margin_x_px=max(int(round(self.margin_x_px)), 0),
            margin_y_px=max(int(round(self.margin_y_px)), 0),
            width_px=max(int(round(self.width_px)), 1),
            anchor=self.anchor if self.anchor in LOGO_ANCHORS else "bottom_right",
        )

    def to_overlay_box(
        self,
        frame_width: float,
        frame_height: float,
        logo_width: float,
        logo_height: float,
        keep_aspect_ratio: bool = True,
    ) -> tuple[float, float, float, float]:
        placement = self.normalized()
        safe_frame_width = max(frame_width, 1.0)
        safe_frame_height = max(frame_height, 1.0)
        safe_logo_width = max(logo_width, 1.0)
        safe_logo_height = max(logo_height, 1.0)

        overlay_width = float(placement.width_px)
        overlay_height = overlay_width if not keep_aspect_ratio else overlay_width * safe_logo_height / safe_logo_width
        if overlay_width > safe_frame_width:
            scale = safe_frame_width / overlay_width
            overlay_width = safe_frame_width
            overlay_height *= scale
        if overlay_height > safe_frame_height:
            scale = safe_frame_height / overlay_height
            overlay_height = safe_frame_height
            overlay_width *= scale

        max_margin_x = max(0.0, safe_frame_width - overlay_width)
        max_margin_y = max(0.0, safe_frame_height - overlay_height)
        margin_x = min(float(placement.margin_x_px), max_margin_x)
        margin_y = min(float(placement.margin_y_px), max_margin_y)

        if placement.anchor in {"top_right", "bottom_right"}:
            left = safe_frame_width - overlay_width - margin_x
        else:
            left = margin_x
        if placement.anchor in {"bottom_left", "bottom_right"}:
            top = safe_frame_height - overlay_height - margin_y
        else:
            top = margin_y

        left = min(max(left, 0.0), max(0.0, safe_frame_width - overlay_width))
        top = min(max(top, 0.0), max(0.0, safe_frame_height - overlay_height))
        return left, top, overlay_width, overlay_height

    @classmethod
    def auto_from_overlay_box(
        cls,
        left: float,
        top: float,
        overlay_width: float,
        overlay_height: float,
        frame_width: float,
        frame_height: float,
    ) -> "PixelLogoPlacement":
        safe_frame_width = max(frame_width, 1.0)
        safe_frame_height = max(frame_height, 1.0)
        safe_overlay_width = min(max(overlay_width, 1.0), safe_frame_width)
        safe_overlay_height = min(max(overlay_height, 1.0), safe_frame_height)

        clamped_left = min(max(left, 0.0), max(0.0, safe_frame_width - safe_overlay_width))
        clamped_top = min(max(top, 0.0), max(0.0, safe_frame_height - safe_overlay_height))
        right_margin = max(0.0, safe_frame_width - safe_overlay_width - clamped_left)
        bottom_margin = max(0.0, safe_frame_height - safe_overlay_height - clamped_top)

        horizontal = "left" if clamped_left <= right_margin else "right"
        vertical = "top" if clamped_top <= bottom_margin else "bottom"
        anchor = f"{vertical}_{horizontal}"
        margin_x = clamped_left if horizontal == "left" else right_margin
        margin_y = clamped_top if vertical == "top" else bottom_margin

        return cls(
            margin_x_px=int(round(margin_x)),
            margin_y_px=int(round(margin_y)),
            width_px=int(round(safe_overlay_width)),
            anchor=anchor,
        ).normalized()


@dataclass(slots=True)
class RenderOptions:
    keep_aspect_ratio: bool = True
    smoothing: bool = True
    reference_mode: str = "frame_axis"


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
class VideoLogoSettings:
    logo_file: Path | None = None
    placement: LogoPlacement = field(default_factory=LogoPlacement)
    render_options: RenderOptions = field(default_factory=RenderOptions)
    pixel_placement: PixelLogoPlacement = field(default_factory=PixelLogoPlacement)
    use_pixel_positioning: bool = False


@dataclass(slots=True)
class VideoEndCardSettings:
    endcard_file: Path | None = None
    overlap_seconds: float = 1.5
    audio_crossfade_seconds: float = 0.5
    alpha_mode: VideoEndCardAlphaMode = VideoEndCardAlphaMode.PREMIERE_COMPAT


@dataclass(slots=True)
class VideoItem:
    source_path: Path
    import_root: Path | None = None
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    frame_rate: str | None = None
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
    pixel_placement: PixelLogoPlacement = field(default_factory=PixelLogoPlacement)
    use_pixel_positioning: bool = False
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
    logo_overlay: VideoLogoSettings = field(default_factory=VideoLogoSettings)
    endcard: VideoEndCardSettings = field(default_factory=VideoEndCardSettings)


@dataclass(slots=True)
class TemplatePreset:
    name: str
    placement: LogoPlacement
    margin_ratio: float
    export_mode: ExportMode
    preserve_structure: bool
    pixel_placement: PixelLogoPlacement = field(default_factory=PixelLogoPlacement)
    use_pixel_positioning: bool = False
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
            "use_pixel_positioning": self.use_pixel_positioning,
            "placement": {
                "x_ratio": self.placement.x_ratio,
                "y_ratio": self.placement.y_ratio,
                "width_ratio": self.placement.width_ratio,
                "anchor": self.placement.anchor,
            },
            "pixel_placement": {
                "margin_x_px": self.pixel_placement.margin_x_px,
                "margin_y_px": self.pixel_placement.margin_y_px,
                "width_px": self.pixel_placement.width_px,
                "anchor": self.pixel_placement.anchor,
            },
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "TemplatePreset":
        placement_payload = payload.get("placement", {})
        if not isinstance(placement_payload, dict):
            placement_payload = {}
        pixel_payload = payload.get("pixel_placement", {})
        if not isinstance(pixel_payload, dict):
            pixel_payload = {}
        return cls(
            name=str(payload.get("name", "未命名模板")),
            logo_path=Path(payload["logo_path"]) if payload.get("logo_path") else None,
            output_directory=Path(payload["output_directory"]) if payload.get("output_directory") else None,
            margin_ratio=float(payload.get("margin_ratio", 0.0)),
            export_mode=ExportMode(str(payload.get("export_mode", ExportMode.NEW_FOLDER.value))),
            preserve_structure=bool(payload.get("preserve_structure", True)),
            use_pixel_positioning=bool(payload.get("use_pixel_positioning", bool(pixel_payload))),
            placement=LogoPlacement(
                x_ratio=float(placement_payload.get("x_ratio", 0.05)),
                y_ratio=float(placement_payload.get("y_ratio", 0.05)),
                width_ratio=float(placement_payload.get("width_ratio", 0.2)),
                anchor=str(placement_payload.get("anchor", "top_left")),
            ).normalized(),
            pixel_placement=PixelLogoPlacement(
                margin_x_px=int(pixel_payload.get("margin_x_px", 40)),
                margin_y_px=int(pixel_payload.get("margin_y_px", 40)),
                width_px=int(pixel_payload.get("width_px", 220)),
                anchor=str(pixel_payload.get("anchor", "bottom_right")),
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
