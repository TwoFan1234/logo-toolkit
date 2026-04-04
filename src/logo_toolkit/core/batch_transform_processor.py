from __future__ import annotations

from pathlib import Path
from typing import Callable

from PIL import Image, ImageOps

from logo_toolkit.core.models import (
    BatchSummary,
    BatchTransformConfig,
    CompressionLevel,
    ExportMode,
    ExportResult,
    ResizeConfig,
    ResizeMode,
    SUPPORTED_EXTENSIONS,
    TransformFormat,
)


class BatchTransformProcessor:
    """Pure processing service for generic batch image transformations."""

    def get_image_size(self, image_path: Path) -> tuple[int, int]:
        with Image.open(image_path) as image:
            return image.size

    def validate_image(self, image_path: Path) -> None:
        if image_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"不支持的图片格式: {image_path.suffix}")

    def render_preview(self, image_path: Path, config: BatchTransformConfig, max_size: tuple[int, int]) -> Image.Image:
        self.validate_image(image_path)
        with Image.open(image_path) as source:
            transformed = self._transform_image(ImageOps.exif_transpose(source), config)
        transformed.thumbnail(max_size, Image.Resampling.LANCZOS)
        return transformed

    def estimate_output_size(self, image_size: tuple[int, int], resize_config: ResizeConfig) -> tuple[int, int]:
        return self._resolved_size(image_size, resize_config)

    def process_batch(
        self,
        config: BatchTransformConfig,
        progress_callback: Callable[[int, int, ExportResult], None] | None = None,
        only_files: list[Path] | None = None,
    ) -> BatchSummary:
        files = only_files or config.input_files
        summary = BatchSummary(total=len(files))
        output_directory = self.resolve_output_directory(config)

        for index, image_path in enumerate(files, start=1):
            try:
                self.validate_image(image_path)
                result_path = self.export_image(
                    image_path=image_path,
                    config=config,
                    output_directory=output_directory,
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
        config: BatchTransformConfig,
        output_directory: Path | None,
        source_root: Path | None = None,
    ) -> Path:
        target_suffix = self._target_suffix(image_path, config.transform_format)
        output_path = self.build_output_path(
            image_path=image_path,
            target_suffix=target_suffix,
            export_mode=config.export_mode,
            output_directory=output_directory,
            preserve_structure=config.preserve_structure,
            source_root=source_root,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with Image.open(image_path) as source:
            transformed = self._transform_image(ImageOps.exif_transpose(source), config)

        target_format = self._target_format(output_path.suffix)
        save_image = self._prepare_for_save(transformed, target_format)
        save_kwargs = self._build_save_kwargs(target_format, config.compression_level)
        save_image.save(output_path, format=target_format, **save_kwargs)
        return output_path

    def resolve_output_directory(self, config: BatchTransformConfig) -> Path | None:
        if config.export_mode == ExportMode.OVERWRITE:
            return None
        if config.output_directory:
            return config.output_directory
        if not config.input_files:
            raise ValueError("没有可处理的输入图片")
        parent = config.input_files[0].parent
        base_name = "batch_output"
        candidate = parent / base_name
        counter = 1
        while candidate.exists():
            candidate = parent / f"{base_name}_{counter}"
            counter += 1
        return candidate

    def build_output_path(
        self,
        image_path: Path,
        target_suffix: str,
        export_mode: ExportMode,
        output_directory: Path | None,
        preserve_structure: bool,
        source_root: Path | None,
    ) -> Path:
        if export_mode == ExportMode.OVERWRITE:
            if image_path.suffix.lower() != target_suffix.lower():
                raise ValueError("覆盖原图模式下不能同时转换格式，请改用导出到新文件夹。")
            return image_path.with_suffix(target_suffix)
        if output_directory is None:
            raise ValueError("导出到新文件夹时必须提供输出目录")
        relative_path = self._build_relative_output_path(
            image_path=image_path,
            target_suffix=target_suffix,
            preserve_structure=preserve_structure,
            source_root=source_root,
        )
        return self._ensure_unique_output_path(output_directory / relative_path)

    def _build_relative_output_path(
        self,
        image_path: Path,
        target_suffix: str,
        preserve_structure: bool,
        source_root: Path | None,
    ) -> Path:
        file_name = f"{image_path.stem}{target_suffix}"
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

    def _transform_image(self, image: Image.Image, config: BatchTransformConfig) -> Image.Image:
        return self._apply_resize(image.copy(), config.resize_config)

    def _apply_resize(self, image: Image.Image, resize_config: ResizeConfig) -> Image.Image:
        target_size = self._resolved_size(image.size, resize_config)
        if target_size == image.size:
            return image
        return image.resize(target_size, Image.Resampling.LANCZOS)

    def _resolved_size(self, image_size: tuple[int, int], resize_config: ResizeConfig) -> tuple[int, int]:
        mode = resize_config.mode
        width, height = image_size
        if mode == ResizeMode.NONE:
            return image_size
        if mode == ResizeMode.SCALE_PERCENT:
            scale = max(resize_config.scale_percent, 1) / 100.0
            target_size = (max(1, round(width * scale)), max(1, round(height * scale)))
        elif mode == ResizeMode.LONGEST_EDGE:
            longest_edge = max(resize_config.longest_edge, 1)
            current_longest = max(width, height)
            scale = longest_edge / max(current_longest, 1)
            target_size = (max(1, round(width * scale)), max(1, round(height * scale)))
        else:
            target_width = max(resize_config.target_width, 1)
            target_height = max(resize_config.target_height, 1)
            if resize_config.keep_aspect_ratio:
                scale = min(target_width / max(width, 1), target_height / max(height, 1))
                target_size = (max(1, round(width * scale)), max(1, round(height * scale)))
            else:
                target_size = (target_width, target_height)
        return target_size

    def _target_suffix(self, image_path: Path, transform_format: TransformFormat) -> str:
        if transform_format == TransformFormat.KEEP:
            return image_path.suffix.lower()
        if transform_format == TransformFormat.JPEG:
            return ".jpg"
        if transform_format == TransformFormat.PNG:
            return ".png"
        return ".webp"

    def _target_format(self, suffix: str) -> str:
        normalized = suffix.lower()
        if normalized in {".jpg", ".jpeg"}:
            return "JPEG"
        if normalized == ".png":
            return "PNG"
        if normalized == ".webp":
            return "WEBP"
        raise ValueError(f"不支持的输出格式: {suffix}")

    def _prepare_for_save(self, image: Image.Image, target_format: str) -> Image.Image:
        if target_format == "JPEG":
            rgba = image.convert("RGBA")
            background = Image.new("RGB", rgba.size, (255, 255, 255))
            background.paste(rgba, mask=rgba.getchannel("A"))
            return background
        if target_format == "PNG":
            return image.convert("RGBA") if "A" in image.getbands() else image.convert("RGB")
        return image.convert("RGBA") if "A" in image.getbands() else image.convert("RGB")

    def _build_save_kwargs(self, target_format: str, compression_level: CompressionLevel) -> dict[str, object]:
        if target_format == "JPEG":
            quality_map = {
                CompressionLevel.NONE: 95,
                CompressionLevel.LIGHT: 88,
                CompressionLevel.MEDIUM: 78,
                CompressionLevel.HIGH: 65,
            }
            return {"quality": quality_map[compression_level], "optimize": compression_level != CompressionLevel.NONE}

        if target_format == "WEBP":
            quality_map = {
                CompressionLevel.NONE: 95,
                CompressionLevel.LIGHT: 86,
                CompressionLevel.MEDIUM: 76,
                CompressionLevel.HIGH: 60,
            }
            return {"quality": quality_map[compression_level], "method": 6}

        compress_map = {
            CompressionLevel.NONE: 0,
            CompressionLevel.LIGHT: 3,
            CompressionLevel.MEDIUM: 6,
            CompressionLevel.HIGH: 9,
        }
        return {
            "optimize": compression_level != CompressionLevel.NONE,
            "compress_level": compress_map[compression_level],
        }
