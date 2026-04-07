from __future__ import annotations

from pathlib import Path
from typing import Callable

from PIL import Image, ImageOps

from logo_toolkit.core.models import (
    BatchJobConfig,
    BatchSummary,
    ExportMode,
    ExportResult,
    LogoPlacement,
    PixelLogoPlacement,
    RenderOptions,
    SUPPORTED_EXTENSIONS,
)


class ImageProcessor:
    """Pure processing service that can be reused by UI or automation."""

    def get_image_size(self, image_path: Path) -> tuple[int, int]:
        with Image.open(image_path) as image:
            return image.size

    def validate_image(self, image_path: Path) -> None:
        if image_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"不支持的图片格式: {image_path.suffix}")

    def render_preview(
        self,
        image_path: Path,
        logo_path: Path,
        placement: LogoPlacement,
        render_options: RenderOptions,
        pixel_placement: PixelLogoPlacement | None = None,
        use_pixel_positioning: bool = False,
        max_size: tuple[int, int] | None = None,
    ) -> Image.Image:
        placement = placement.normalized()
        pixel_placement = (pixel_placement or PixelLogoPlacement()).normalized()
        with Image.open(image_path) as base_image, Image.open(logo_path) as logo_image:
            rendered = self._compose(
                base_image,
                logo_image,
                placement,
                render_options,
                pixel_placement=pixel_placement,
                use_pixel_positioning=use_pixel_positioning,
            )
        if max_size:
            rendered.thumbnail(max_size, self._resample(render_options.smoothing))
        return rendered

    def process_batch(
        self,
        config: BatchJobConfig,
        progress_callback: Callable[[int, int, ExportResult], None] | None = None,
        only_files: list[Path] | None = None,
    ) -> BatchSummary:
        files = only_files or config.input_files
        summary = BatchSummary(total=len(files))
        output_directory = self.resolve_output_directory(config)
        logo_path = config.logo_file

        for index, image_path in enumerate(files, start=1):
            try:
                self.validate_image(image_path)
                result_path = self.export_image(
                    image_path=image_path,
                    logo_path=logo_path,
                    placement=config.placement,
                    render_options=config.render_options,
                    pixel_placement=config.pixel_placement,
                    use_pixel_positioning=config.use_pixel_positioning,
                    export_mode=config.export_mode,
                    output_directory=output_directory,
                    output_suffix=config.output_suffix,
                    preserve_structure=config.preserve_structure,
                    source_root=config.source_roots.get(image_path),
                )
                result = ExportResult(source_path=image_path, success=True, output_path=result_path)
                summary.succeeded += 1
            except Exception as exc:  # noqa: BLE001
                result = ExportResult(source_path=image_path, success=False, error=str(exc))
                summary.failed += 1

            summary.results.append(result)
            if progress_callback:
                progress_callback(index, summary.total, result)

        return summary

    def export_image(
        self,
        image_path: Path,
        logo_path: Path,
        placement: LogoPlacement,
        render_options: RenderOptions,
        export_mode: ExportMode,
        output_directory: Path | None,
        pixel_placement: PixelLogoPlacement | None = None,
        use_pixel_positioning: bool = False,
        output_suffix: str = "",
        preserve_structure: bool = False,
        source_root: Path | None = None,
    ) -> Path:
        self.validate_image(image_path)
        placement = placement.normalized()
        pixel_placement = (pixel_placement or PixelLogoPlacement()).normalized()
        output_path = self.build_output_path(
            image_path=image_path,
            export_mode=export_mode,
            output_directory=output_directory,
            output_suffix=output_suffix,
            preserve_structure=preserve_structure,
            source_root=source_root,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with Image.open(image_path) as base_image, Image.open(logo_path) as logo_image:
            rendered = self._compose(
                base_image,
                logo_image,
                placement,
                render_options,
                pixel_placement=pixel_placement,
                use_pixel_positioning=use_pixel_positioning,
            )

        save_kwargs = {}
        if output_path.suffix.lower() in {".jpg", ".jpeg"}:
            rendered = rendered.convert("RGB")
            save_kwargs["quality"] = 95
        rendered.save(output_path, **save_kwargs)
        return output_path

    def resolve_output_directory(self, config: BatchJobConfig) -> Path | None:
        if config.export_mode == ExportMode.OVERWRITE:
            return None
        if config.output_directory:
            return config.output_directory
        if not config.input_files:
            raise ValueError("没有可处理的输入图片")
        parent = config.input_files[0].parent
        base_name = "logo_output"
        candidate = parent / base_name
        counter = 1
        while candidate.exists():
            candidate = parent / f"{base_name}_{counter}"
            counter += 1
        return candidate

    def build_output_path(
        self,
        image_path: Path,
        export_mode: ExportMode,
        output_directory: Path | None,
        output_suffix: str = "",
        preserve_structure: bool = False,
        source_root: Path | None = None,
    ) -> Path:
        if export_mode == ExportMode.OVERWRITE:
            return image_path
        if output_directory is None:
            raise ValueError("导出到新文件夹时必须提供输出目录")
        relative_path = self._build_relative_output_path(
            image_path=image_path,
            output_suffix=output_suffix,
            preserve_structure=preserve_structure,
            source_root=source_root,
        )
        return self._ensure_unique_output_path(output_directory / relative_path)

    def _build_relative_output_path(
        self,
        image_path: Path,
        output_suffix: str,
        preserve_structure: bool,
        source_root: Path | None,
    ) -> Path:
        file_name = f"{image_path.stem}{output_suffix}{image_path.suffix}" if output_suffix else image_path.name
        if not preserve_structure or source_root is None:
            return Path(file_name)
        try:
            relative_path = image_path.relative_to(source_root)
        except ValueError:
            return Path(file_name)
        return Path(source_root.name) / relative_path.parent / file_name

    def _ensure_unique_output_path(self, path: Path) -> Path:
        if not path.exists():
            return path
        counter = 1
        while True:
            candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
            if not candidate.exists():
                return candidate
            counter += 1

    def _compose(
        self,
        base_image: Image.Image,
        logo_image: Image.Image,
        placement: LogoPlacement,
        render_options: RenderOptions,
        pixel_placement: PixelLogoPlacement | None = None,
        use_pixel_positioning: bool = False,
    ) -> Image.Image:
        base = ImageOps.exif_transpose(base_image).convert("RGBA")
        logo = logo_image.convert("RGBA")
        if use_pixel_positioning:
            active_pixel_placement = (pixel_placement or PixelLogoPlacement()).normalized()
            x, y, target_width, target_height = active_pixel_placement.to_overlay_box(
                frame_width=base.width,
                frame_height=base.height,
                logo_width=logo.width,
                logo_height=logo.height,
                keep_aspect_ratio=render_options.keep_aspect_ratio,
            )
            resized_logo = logo.resize(
                (max(1, int(round(target_width))), max(1, int(round(target_height)))),
                self._resample(render_options.smoothing),
            )
        else:
            target_width = max(1, int(round(base.width * placement.width_ratio)))
            if render_options.keep_aspect_ratio:
                scale_ratio = target_width / max(logo.width, 1)
                target_height = max(1, int(round(logo.height * scale_ratio)))
            else:
                target_height = target_width
            resized_logo = logo.resize((target_width, target_height), self._resample(render_options.smoothing))
            x, y, _, _ = placement.to_overlay_box(
                frame_width=base.width,
                frame_height=base.height,
                logo_width=logo.width,
                logo_height=logo.height,
                keep_aspect_ratio=render_options.keep_aspect_ratio,
                reference_mode=render_options.reference_mode,
            )
        base.alpha_composite(resized_logo, (int(round(x)), int(round(y))))
        return base

    @staticmethod
    def _resample(smoothing: bool) -> int:
        return Image.Resampling.LANCZOS if smoothing else Image.Resampling.NEAREST
