from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from logo_toolkit.core.models import SUPPORTED_EXTENSIONS, SUPPORTED_VIDEO_EXTENSIONS


@dataclass(slots=True)
class CollectedImage:
    source_path: Path
    import_root: Path | None


@dataclass(slots=True)
class CollectedVideo:
    source_path: Path
    import_root: Path | None


def collect_images(paths: list[str]) -> list[CollectedImage]:
    files: list[CollectedImage] = []
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            files.extend(_collect_from_directory(path.resolve()))
        elif path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            resolved = path.resolve()
            files.append(CollectedImage(source_path=resolved, import_root=resolved.parent))
    unique_files: list[CollectedImage] = []
    seen: set[Path] = set()
    for item in sorted(files, key=lambda current: str(current.source_path)):
        if item.source_path not in seen:
            unique_files.append(item)
            seen.add(item.source_path)
    return unique_files


def collect_videos(paths: list[str]) -> list[CollectedVideo]:
    files: list[CollectedVideo] = []
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            files.extend(_collect_videos_from_directory(path.resolve()))
        elif path.is_file() and path.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS:
            resolved = path.resolve()
            files.append(CollectedVideo(source_path=resolved, import_root=resolved.parent))
    unique_files: list[CollectedVideo] = []
    seen: set[Path] = set()
    for item in sorted(files, key=lambda current: str(current.source_path)):
        if item.source_path not in seen:
            unique_files.append(item)
            seen.add(item.source_path)
    return unique_files


def _collect_from_directory(directory: Path) -> list[CollectedImage]:
    return [
        CollectedImage(source_path=item.resolve(), import_root=directory)
        for item in directory.rglob("*")
        if item.is_file() and item.suffix.lower() in SUPPORTED_EXTENSIONS
    ]


def _collect_videos_from_directory(directory: Path) -> list[CollectedVideo]:
    return [
        CollectedVideo(source_path=item.resolve(), import_root=directory)
        for item in directory.rglob("*")
        if item.is_file() and item.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS
    ]
