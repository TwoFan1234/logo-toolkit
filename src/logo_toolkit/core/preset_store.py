from __future__ import annotations

import json
import os
from pathlib import Path

from logo_toolkit.core.models import TemplatePreset


class TemplatePresetStore:
    def __init__(self, storage_path: Path | None = None) -> None:
        self.storage_path = storage_path or self.default_storage_path()

    @staticmethod
    def default_storage_path() -> Path:
        base_dir = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".logo_toolkit"))
        return base_dir / "LogoToolkit" / "presets.json"

    def load_presets(self) -> list[TemplatePreset]:
        if not self.storage_path.exists():
            return []
        data = json.loads(self.storage_path.read_text(encoding="utf-8"))
        raw_presets = data.get("presets", []) if isinstance(data, dict) else []
        presets = [TemplatePreset.from_dict(item) for item in raw_presets if isinstance(item, dict)]
        return sorted(presets, key=lambda preset: preset.name.lower())

    def save_preset(self, preset: TemplatePreset) -> list[TemplatePreset]:
        presets = [item for item in self.load_presets() if item.name != preset.name]
        presets.append(preset)
        self._write_presets(presets)
        return sorted(presets, key=lambda item: item.name.lower())

    def delete_preset(self, preset_name: str) -> list[TemplatePreset]:
        presets = [item for item in self.load_presets() if item.name != preset_name]
        self._write_presets(presets)
        return sorted(presets, key=lambda item: item.name.lower())

    def _write_presets(self, presets: list[TemplatePreset]) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"presets": [preset.to_dict() for preset in presets]}
        self.storage_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
