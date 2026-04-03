from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


class ExportMode(str, Enum):
    NEW_FOLDER = "new_folder"
    OVERWRITE = "overwrite"


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
class TemplatePreset:
    name: str
    placement: LogoPlacement
    margin_ratio: float
    export_mode: ExportMode
    preserve_structure: bool
    logo_path: Path | None = None
    output_directory: Path | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "logo_path": str(self.logo_path) if self.logo_path else None,
            "output_directory": str(self.output_directory) if self.output_directory else None,
            "margin_ratio": self.margin_ratio,
            "export_mode": self.export_mode.value,
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
            preserve_structure=bool(payload.get("preserve_structure", False)),
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
