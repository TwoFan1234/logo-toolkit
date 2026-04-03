from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class VideoBackendError(RuntimeError):
    """Raised when ffmpeg or ffprobe cannot be found or executed."""


@dataclass(frozen=True, slots=True)
class VideoToolPaths:
    ffmpeg: Path
    ffprobe: Path


class VideoBackend:
    def __init__(self) -> None:
        self._cached_paths: VideoToolPaths | None = None

    def ensure_tools(self) -> VideoToolPaths:
        if self._cached_paths is None:
            self._cached_paths = self._resolve_tool_paths()
        return self._cached_paths

    def probe(self, source_path: Path) -> dict[str, Any]:
        tools = self.ensure_tools()
        command = [
            str(tools.ffprobe),
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(source_path),
        ]
        completed = self._run(command)
        try:
            return json.loads(completed.stdout or "{}")
        except json.JSONDecodeError as exc:  # noqa: PERF203
            raise VideoBackendError("ffprobe 返回了无法解析的元数据。") from exc

    def run_ffmpeg(self, arguments: list[str]) -> None:
        tools = self.ensure_tools()
        command = [str(tools.ffmpeg), *arguments]
        self._run(command)

    def _run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(command, check=True, capture_output=True, text=True)
        except FileNotFoundError as exc:
            raise VideoBackendError("未找到 ffmpeg/ffprobe，请先安装或重新打包资源。") from exc
        except subprocess.CalledProcessError as exc:
            message = (exc.stderr or exc.stdout or "").strip() or "视频处理命令执行失败。"
            raise VideoBackendError(message) from exc

    def _resolve_tool_paths(self) -> VideoToolPaths:
        for directory in self._candidate_directories():
            ffmpeg = directory / "ffmpeg.exe"
            ffprobe = directory / "ffprobe.exe"
            if ffmpeg.exists() and ffprobe.exists():
                return VideoToolPaths(ffmpeg=ffmpeg, ffprobe=ffprobe)
        raise VideoBackendError("未找到 ffmpeg/ffprobe，请先安装或重新打包资源。")

    def _candidate_directories(self) -> list[Path]:
        candidates: list[Path] = []
        if hasattr(sys, "_MEIPASS"):
            candidates.append(Path(getattr(sys, "_MEIPASS")) / "vendor" / "bin")
        candidates.append(Path(__file__).resolve().parents[3] / "resources" / "vendor" / "bin")
        return candidates
