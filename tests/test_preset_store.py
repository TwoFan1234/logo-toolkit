from __future__ import annotations

from pathlib import Path

from logo_toolkit.core.models import ExportMode, LogoPlacement, TemplatePreset
from logo_toolkit.core.preset_store import TemplatePresetStore


def test_preset_store_round_trip(tmp_path: Path) -> None:
    store = TemplatePresetStore(storage_path=tmp_path / "presets.json")
    preset = TemplatePreset(
        name="默认模板",
        logo_path=tmp_path / "logo.png",
        output_directory=tmp_path / "output",
        margin_ratio=0.1,
        export_mode=ExportMode.NEW_FOLDER,
        preserve_structure=True,
        placement=LogoPlacement(x_ratio=0.2, y_ratio=0.3, width_ratio=0.25),
    )

    store.save_preset(preset)
    presets = store.load_presets()

    assert len(presets) == 1
    loaded = presets[0]
    assert loaded.name == "默认模板"
    assert loaded.logo_path == tmp_path / "logo.png"
    assert loaded.output_directory == tmp_path / "output"
    assert loaded.margin_ratio == 0.1
    assert loaded.export_mode == ExportMode.NEW_FOLDER
    assert loaded.preserve_structure is True
    assert loaded.placement.x_ratio == 0.2


def test_preset_store_replaces_same_name(tmp_path: Path) -> None:
    store = TemplatePresetStore(storage_path=tmp_path / "presets.json")
    first = TemplatePreset(
        name="重复模板",
        placement=LogoPlacement(x_ratio=0.1, y_ratio=0.1, width_ratio=0.2),
        margin_ratio=0.0,
        export_mode=ExportMode.NEW_FOLDER,
        preserve_structure=False,
    )
    second = TemplatePreset(
        name="重复模板",
        placement=LogoPlacement(x_ratio=0.3, y_ratio=0.4, width_ratio=0.5),
        margin_ratio=0.2,
        export_mode=ExportMode.OVERWRITE,
        preserve_structure=True,
    )

    store.save_preset(first)
    store.save_preset(second)
    presets = store.load_presets()

    assert len(presets) == 1
    assert presets[0].placement.x_ratio == 0.3
    assert presets[0].export_mode == ExportMode.OVERWRITE


def test_preset_store_delete(tmp_path: Path) -> None:
    store = TemplatePresetStore(storage_path=tmp_path / "presets.json")
    preset = TemplatePreset(
        name="待删除模板",
        placement=LogoPlacement(),
        margin_ratio=0.0,
        export_mode=ExportMode.NEW_FOLDER,
        preserve_structure=False,
    )

    store.save_preset(preset)
    store.delete_preset("待删除模板")

    assert store.load_presets() == []
