from __future__ import annotations

import json
import subprocess
from pathlib import Path

from logo_toolkit.core.video_backend import VideoBackend, VideoBackendError


def test_decode_output_accepts_utf8_bytes() -> None:
    text = "F:\\花园项目\\视频.mp4"
    payload = text.encode("utf-8")

    decoded = VideoBackend._decode_output(payload)

    assert decoded == text


def test_probe_decodes_utf8_json_from_ffprobe(monkeypatch) -> None:
    backend = VideoBackend()
    payload = json.dumps(
        {
            "format": {"duration": "12.5"},
            "streams": [{"codec_type": "video", "width": 1080, "height": 1920}],
            "source": "F:/花园项目/视频.mp4",
        },
        ensure_ascii=False,
    ).encode("utf-8")

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(command, 0, stdout=payload, stderr=b"")

    monkeypatch.setattr(backend, "ensure_tools", lambda: type("Tools", (), {"ffprobe": Path("ffprobe.exe"), "ffmpeg": Path("ffmpeg.exe")})())
    monkeypatch.setattr(backend, "_run", fake_run)

    parsed = backend.probe(Path("F:/花园项目/视频.mp4"))

    assert parsed["format"]["duration"] == "12.5"
    assert parsed["streams"][0]["width"] == 1080


def test_run_raises_readable_error_from_utf8_stderr(monkeypatch) -> None:
    backend = VideoBackend()
    error = subprocess.CalledProcessError(1, ["ffprobe"], stderr="路径无效：F:/花园项目/视频.mp4".encode("utf-8"))

    def fake_subprocess_run(*args, **kwargs):  # noqa: ANN002, ANN003
        raise error

    monkeypatch.setattr(subprocess, "run", fake_subprocess_run)

    try:
        backend._run(["ffprobe"])
    except VideoBackendError as exc:
        assert "路径无效" in str(exc)
    else:
        raise AssertionError("Expected VideoBackendError")
