from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListView,
    QMenu,
    QMessageBox,
    QProgressBar,
    QProgressDialog,
    QPushButton,
    QSplitter,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from logo_toolkit.core.file_utils import collect_images
from logo_toolkit.core.image_processor import ImageProcessor
from logo_toolkit.core.models import (
    BatchJobConfig,
    ExportMode,
    ImageItem,
    LogoPlacement,
    PixelLogoPlacement,
    RenderOptions,
    TemplatePreset,
)
from logo_toolkit.core.preset_store import TemplatePresetStore
from logo_toolkit.ui.selection_helpers import build_check_item, populate_ratio_filter_combo, ratio_matches
from logo_toolkit.ui.theme import configure_resizable_splitter, toolkit_tool_stylesheet
from logo_toolkit.ui.video_logo_preview_canvas import VideoLogoPreviewCanvas


class ImportGroupBox(QGroupBox):
    paths_dropped = Signal(list)

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(title, parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event) -> None:  # noqa: ANN001
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # noqa: ANN001
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: ANN001
        if event.mimeData().hasUrls():
            self.paths_dropped.emit([url.toLocalFile() for url in event.mimeData().urls()])
            event.acceptProposedAction()
            return
        super().dropEvent(event)


class ImageTableWidget(QTableWidget):
    paths_dropped = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event) -> None:  # noqa: ANN001
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # noqa: ANN001
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: ANN001
        if event.mimeData().hasUrls():
            self.paths_dropped.emit([url.toLocalFile() for url in event.mimeData().urls()])
            event.acceptProposedAction()
            return
        super().dropEvent(event)


class BatchLogoToolWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.processor = ImageProcessor()
        self.preset_store = TemplatePresetStore()
        self.items: list[ImageItem] = []
        self.presets: list[TemplatePreset] = []
        self.logo_path: Path | None = None
        self.output_directory: Path | None = None
        self.placement = LogoPlacement()
        self.pixel_placement = PixelLogoPlacement(margin_x_px=40, margin_y_px=40, width_px=220, anchor="top_left")
        self.render_options = RenderOptions()
        self.thumbnail_size = QSize(72, 72)
        self._table_syncing = False
        self._build_ui()
        self._load_presets()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(12)
        root_layout.addWidget(splitter)

        image_panel = QWidget()
        image_layout = QVBoxLayout(image_panel)
        image_layout.setContentsMargins(0, 0, 0, 0)
        image_layout.addWidget(self._build_image_group())

        preview_panel = self._build_preview_panel()

        settings_panel = QWidget()
        settings_layout = QVBoxLayout(settings_panel)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setSpacing(10)
        settings_layout.addWidget(self._build_preset_group())
        settings_layout.addWidget(self._build_logo_group())
        settings_layout.addWidget(self._build_export_group())
        settings_layout.addWidget(self._build_progress_group())
        settings_layout.addStretch(1)

        splitter.addWidget(image_panel)
        splitter.addWidget(preview_panel)
        splitter.addWidget(settings_panel)
        configure_resizable_splitter(
            splitter,
            [image_panel, preview_panel, settings_panel],
            stretches=[2, 3, 2],
            minimum_widths=[220, 240, 220],
            initial_sizes=[560, 720, 300],
        )

        self._apply_styles()
        self._update_export_mode_ui()

    def _build_image_group(self) -> QGroupBox:
        group = ImportGroupBox("1. 图片导入")
        group.paths_dropped.connect(self._load_images)
        layout = QVBoxLayout(group)

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        add_files_button = QPushButton("添加图片")
        add_files_button.clicked.connect(self._choose_files)
        add_folder_button = QPushButton("导入文件夹")
        add_folder_button.clicked.connect(self._choose_folders)
        clear_button = QPushButton("清空")
        clear_button.clicked.connect(self._clear_images)
        buttons_layout.addWidget(add_files_button)
        buttons_layout.addWidget(add_folder_button)
        buttons_layout.addWidget(clear_button)

        ratio_layout = QHBoxLayout()
        ratio_layout.setSpacing(8)
        ratio_label = QLabel("比例筛选")
        ratio_label.setObjectName("filterLabel")
        self.ratio_filter_combo = QComboBox()
        populate_ratio_filter_combo(self.ratio_filter_combo)
        self.apply_ratio_button = QPushButton("应用")
        self.apply_ratio_button.setObjectName("compactButton")
        self.apply_ratio_button.clicked.connect(self._apply_ratio_filter_selection)
        ratio_layout.addWidget(ratio_label)
        ratio_layout.addWidget(self.ratio_filter_combo, stretch=1)
        ratio_layout.addWidget(self.apply_ratio_button)

        action_layout = QHBoxLayout()
        action_layout.setSpacing(8)
        self.check_all_button = QPushButton("全选")
        self.check_all_button.setObjectName("compactButton")
        self.check_all_button.clicked.connect(lambda: self._set_all_items_checked(True))
        self.clear_check_button = QPushButton("清空选择")
        self.clear_check_button.setObjectName("compactButton")
        self.clear_check_button.clicked.connect(lambda: self._set_all_items_checked(False))
        self.remove_selected_button = QPushButton("移除选中")
        self.remove_selected_button.setObjectName("compactButton")
        self.remove_selected_button.clicked.connect(self._remove_selected_rows)
        action_layout.addWidget(self.check_all_button)
        action_layout.addWidget(self.clear_check_button)
        action_layout.addStretch(1)
        action_layout.addWidget(self.remove_selected_button)

        self.image_table = ImageTableWidget()
        self.image_table.setColumnCount(7)
        self.image_table.setHorizontalHeaderLabels(["执行", "预览", "文件名", "导入根目录", "分辨率", "状态", "说明"])
        self.image_table.setIconSize(self.thumbnail_size)
        self.image_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.image_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.image_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.image_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.image_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.image_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.image_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.image_table.verticalHeader().setVisible(False)
        self.image_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.image_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.image_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.image_table.itemSelectionChanged.connect(self._sync_preview_from_selection)
        self.image_table.itemChanged.connect(self._handle_table_item_changed)
        self.image_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.image_table.customContextMenuRequested.connect(self._show_image_menu)
        self.image_table.paths_dropped.connect(self._load_images)
        self.image_table.setMinimumHeight(420)
        self.image_table.setWordWrap(False)
        self.image_table.setAlternatingRowColors(True)
        self.image_table.setObjectName("imageTable")

        drop_hint = QLabel("支持一次拖入多个文件夹或文件，工具会自动递归读取每个文件夹下的图片。")
        drop_hint.setWordWrap(True)
        drop_hint.setObjectName("supportingLabel")

        layout.addLayout(buttons_layout)
        layout.addLayout(ratio_layout)
        layout.addLayout(action_layout)
        layout.addWidget(drop_hint)
        layout.addWidget(self.image_table, stretch=1)
        return group

    def _build_preset_group(self) -> QGroupBox:
        group = QGroupBox("2. 模板预设")
        layout = QVBoxLayout(group)

        self.preset_combo = QComboBox()
        self.preset_combo.setPlaceholderText("选择已保存模板")

        name_row = QHBoxLayout()
        self.preset_name_edit = QLineEdit()
        self.preset_name_edit.setPlaceholderText("输入模板名称后点保存当前")
        self.save_preset_button = QPushButton("保存当前")
        self.save_preset_button.clicked.connect(self._save_current_template)
        name_row.addWidget(self.preset_name_edit)
        name_row.addWidget(self.save_preset_button)

        action_row = QHBoxLayout()
        self.apply_preset_button = QPushButton("套用模板")
        self.apply_preset_button.clicked.connect(self._apply_selected_template)
        self.delete_preset_button = QPushButton("删除模板")
        self.delete_preset_button.clicked.connect(self._delete_selected_template)
        action_row.addWidget(self.apply_preset_button)
        action_row.addWidget(self.delete_preset_button)

        tip = QLabel("模板会保存 logo 路径、位置大小、边距和导出设置，下次打开工具仍可直接复用。")
        tip.setWordWrap(True)
        tip.setObjectName("supportingLabel")

        layout.addWidget(self.preset_combo)
        layout.addLayout(name_row)
        layout.addLayout(action_row)
        layout.addWidget(tip)
        return group

    def _build_logo_group(self) -> QGroupBox:
        group = QGroupBox("3. Logo 设置")
        layout = QVBoxLayout(group)

        button_row = QHBoxLayout()
        choose_logo_button = QPushButton("选择 Logo")
        choose_logo_button.clicked.connect(self._choose_logo)
        self.logo_path_edit = QLineEdit()
        self.logo_path_edit.setReadOnly(True)
        button_row.addWidget(choose_logo_button)
        button_row.addWidget(self.logo_path_edit)

        form = QFormLayout()
        self.corner_label = QLabel("左上角")
        self.x_spin = QSpinBox()
        self.x_spin.setRange(0, 8192)
        self.x_spin.setSuffix(" px")
        self.y_spin = QSpinBox()
        self.y_spin.setRange(0, 8192)
        self.y_spin.setSuffix(" px")
        self.size_spin = QSpinBox()
        self.size_spin.setRange(1, 8192)
        self.size_spin.setSuffix(" px")
        self.keep_ratio_checkbox = QCheckBox("保持 Logo 原比例")
        self.keep_ratio_checkbox.setChecked(True)
        self.keep_ratio_checkbox.setEnabled(False)
        self.keep_ratio_checkbox.setToolTip("v1 固定保持原比例，避免 logo 变形")

        self.x_spin.valueChanged.connect(self._pixel_spinbox_changed)
        self.y_spin.valueChanged.connect(self._pixel_spinbox_changed)
        self.size_spin.valueChanged.connect(self._pixel_spinbox_changed)

        form.addRow("自动靠近角", self.corner_label)
        form.addRow("水平边距", self.x_spin)
        form.addRow("垂直边距", self.y_spin)
        form.addRow("Logo 宽度", self.size_spin)
        form.addRow("渲染方式", self.keep_ratio_checkbox)

        layout.addLayout(button_row)
        layout.addLayout(form)
        return group

    def _build_export_group(self) -> QGroupBox:
        group = QGroupBox("4. 导出设置")
        layout = QGridLayout(group)

        self.export_mode_combo = QComboBox()
        self.export_mode_combo.addItem("导出到新文件夹", ExportMode.NEW_FOLDER)
        self.export_mode_combo.addItem("覆盖原图", ExportMode.OVERWRITE)
        self.export_mode_combo.currentIndexChanged.connect(self._update_export_mode_ui)

        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setReadOnly(True)
        self.output_dir_button = QPushButton("选择导出目录")
        self.output_dir_button.clicked.connect(self._choose_output_dir)
        self.preserve_structure_checkbox = QCheckBox("导出时保持原文件夹结构")
        self.preserve_structure_checkbox.setChecked(False)

        self.run_button = QPushButton("开始批量导出")
        self.run_button.setObjectName("primaryRunButton")
        self.run_button.clicked.connect(self._run_batch)

        layout.addWidget(QLabel("输出模式"), 0, 0)
        layout.addWidget(self.export_mode_combo, 0, 1, 1, 2)
        layout.addWidget(QLabel("导出目录"), 1, 0)
        layout.addWidget(self.output_dir_edit, 1, 1)
        layout.addWidget(self.output_dir_button, 1, 2)
        layout.addWidget(self.preserve_structure_checkbox, 2, 0, 1, 3)
        layout.addWidget(self.run_button, 3, 0, 1, 3)
        return group

    def _build_progress_group(self) -> QGroupBox:
        group = QGroupBox("5. 处理结果")
        layout = QVBoxLayout(group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.summary_label = QLabel("尚未开始处理")
        self.summary_label.setObjectName("statusSummary")

        layout.addWidget(self.progress_bar)
        layout.addWidget(self.summary_label)
        return group

    def _build_preview_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("previewCard")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        preview_title = QLabel("实时预览")
        preview_title.setObjectName("previewTitle")

        preview_badge = QLabel("拖拽校准")
        preview_badge.setObjectName("previewBadge")

        title_row.addWidget(preview_title)
        title_row.addWidget(preview_badge)
        title_row.addStretch(1)

        tips = QLabel("拖动 Logo 调整位置，拖动右下角控制点缩放大小。像素输入与画布会双向同步。")
        tips.setWordWrap(True)
        tips.setObjectName("previewTips")

        self.preview_canvas = VideoLogoPreviewCanvas()
        self.preview_canvas.placement_changed.connect(self._handle_canvas_pixel_change)

        layout.addLayout(title_row)
        layout.addWidget(tips)
        layout.addWidget(self.preview_canvas, stretch=1)
        return panel

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QGroupBox {
                background: #fffaf1;
                border: 1px solid #dcc9a8;
                border-radius: 16px;
                margin-top: 12px;
                font-weight: 600;
                padding-top: 12px;
                color: #2e322b;
            }
            QGroupBox::title {
                left: 16px;
                padding: 0 6px 0 6px;
                color: #4f4638;
            }
            QPushButton {
                background: #27483f;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 8px 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #33584e;
            }
            QPushButton#primaryRunButton {
                background: #b85b24;
                font-size: 15px;
                font-weight: 700;
                padding: 12px 16px;
            }
            QPushButton#primaryRunButton:hover {
                background: #cf6c2e;
            }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTableWidget {
                background: white;
                border: 1px solid #d8c7aa;
                border-radius: 9px;
                padding: 6px;
            }
            QLabel {
                color: #473d2e;
            }
            #supportingLabel {
                color: #6c604d;
            }
            #previewCard {
                background: #f6efe0;
                border: 1px solid #dbc7a5;
                border-radius: 16px;
            }
            #previewTitle {
                color: #24332e;
                font-size: 16px;
                font-weight: 700;
            }
            #previewBadge {
                background: #ebdfc6;
                color: #5e523f;
                border-radius: 999px;
                padding: 3px 8px;
                font-size: 11px;
                font-weight: 600;
            }
            #previewTips {
                background: rgba(255, 255, 255, 0.68);
                border: 1px solid #e0d2b7;
                border-radius: 12px;
                padding: 8px 10px;
                color: #625645;
                font-size: 12px;
            }
            #imageTable {
                gridline-color: #eadcc1;
                selection-background-color: #efe1c7;
                selection-color: #2f2a20;
                alternate-background-color: #fcf8f0;
            }
            QHeaderView::section {
                background: #f1e4cb;
                color: #554a3d;
                border: none;
                border-right: 1px solid #e1d2b5;
                border-bottom: 1px solid #e1d2b5;
                padding: 8px 6px;
                font-weight: 700;
            }
            QProgressBar {
                background: #f0e5d0;
                border: 1px solid #decdb2;
                border-radius: 10px;
                text-align: center;
                min-height: 18px;
            }
            QProgressBar::chunk {
                background: #47695f;
                border-radius: 8px;
            }
            #statusSummary {
                color: #5d513f;
                font-weight: 600;
            }
            QSplitter::handle {
                background: transparent;
            }
            """
        )
        self.setStyleSheet(toolkit_tool_stylesheet())

    def _load_presets(self) -> None:
        self.presets = self.preset_store.load_presets()
        self._refresh_preset_combo()

    def _refresh_preset_combo(self, selected_name: str | None = None) -> None:
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self.preset_combo.addItem("请选择模板", None)
        for preset in self.presets:
            self.preset_combo.addItem(preset.name, preset.name)
        if selected_name:
            index = self.preset_combo.findData(selected_name)
            if index >= 0:
                self.preset_combo.setCurrentIndex(index)
        self.preset_combo.blockSignals(False)

    def _current_preset(self, name: str) -> TemplatePreset:
        legacy_placement = self._legacy_ratio_placement_from_pixel()
        return TemplatePreset(
            name=name,
            logo_path=self.logo_path,
            output_directory=self.output_directory,
            margin_ratio=0.0,
            export_mode=self.current_export_mode(),
            preserve_structure=self.preserve_structure_checkbox.isChecked(),
            placement=legacy_placement,
            pixel_placement=self.pixel_placement,
            use_pixel_positioning=True,
        )

    def _save_current_template(self) -> None:
        preset_name = self.preset_name_edit.text().strip()
        if not preset_name:
            QMessageBox.information(self, "缺少模板名", "请先输入模板名称，再点击保存当前。")
            return
        try:
            preset = self._current_preset(preset_name)
            self.presets = self.preset_store.save_preset(preset)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "保存失败", str(exc))
            return
        self._refresh_preset_combo(selected_name=preset.name)
        self.summary_label.setText(f"模板已保存: {preset.name}")

    def _find_preset_by_name(self, preset_name: str) -> TemplatePreset | None:
        for preset in self.presets:
            if preset.name == preset_name:
                return preset
        return None

    def _apply_selected_template(self) -> None:
        preset_name = self.preset_combo.currentData()
        if not preset_name:
            QMessageBox.information(self, "未选择模板", "请先选择一个模板。")
            return
        preset = self._find_preset_by_name(str(preset_name))
        if preset is None:
            QMessageBox.warning(self, "模板不存在", "没有找到选中的模板。")
            return

        self.preset_name_edit.setText(preset.name)
        if preset.use_pixel_positioning:
            self.pixel_placement = preset.pixel_placement.normalized()
        else:
            self.pixel_placement = self._pixel_placement_from_ratio(preset.placement)
        self.placement = preset.placement.normalized()
        self.export_mode_combo.setCurrentIndex(self.export_mode_combo.findData(preset.export_mode))
        self.preserve_structure_checkbox.setChecked(preset.preserve_structure)
        self.output_directory = preset.output_directory
        self.output_dir_edit.setText(str(preset.output_directory) if preset.output_directory else "")

        if preset.logo_path and preset.logo_path.exists():
            self.logo_path = preset.logo_path
            self.logo_path_edit.setText(str(preset.logo_path))
        elif preset.logo_path:
            self.logo_path = None
            self.logo_path_edit.clear()
            QMessageBox.information(self, "Logo 路径不存在", f"模板中的 logo 文件不存在: {preset.logo_path}")

        self.pixel_placement = self._bounded_pixel_placement(self.pixel_placement)
        self._sync_legacy_ratio_from_pixel()
        self._update_spinboxes_from_pixel()
        self._refresh_preview()
        self.summary_label.setText(f"已套用模板: {preset.name}")

    def _delete_selected_template(self) -> None:
        preset_name = self.preset_combo.currentData()
        if not preset_name:
            QMessageBox.information(self, "未选择模板", "请先选择一个模板。")
            return
        self.presets = self.preset_store.delete_preset(str(preset_name))
        self._refresh_preset_combo()
        if self.preset_name_edit.text().strip() == str(preset_name):
            self.preset_name_edit.clear()
        self.summary_label.setText(f"模板已删除: {preset_name}")

    def _choose_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择图片",
            "",
            "Images (*.jpg *.jpeg *.png *.webp)",
        )
        if files:
            self._load_images(files)

    def _choose_folders(self) -> None:
        dialog = QFileDialog(self, "选择一个或多个图片文件夹")
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setOption(QFileDialog.Option.ShowDirsOnly, True)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        for view in dialog.findChildren((QListView, QTreeView)):
            view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        if dialog.exec():
            folders = dialog.selectedFiles()
            if folders:
                self._load_images(folders)

    def _clear_images(self) -> None:
        self.items.clear()
        self.image_table.setRowCount(0)
        self.progress_bar.setValue(0)
        self.summary_label.setText("已清空图片列表")
        self.preview_canvas.set_images(
            None,
            self.logo_path,
            self.pixel_placement,
            keep_aspect_ratio=self.render_options.keep_aspect_ratio,
        )

    def _choose_logo(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 Logo 图片",
            "",
            "Images (*.png *.jpg *.jpeg *.webp)",
        )
        if not file_path:
            return
        self.logo_path = Path(file_path)
        self.logo_path_edit.setText(str(self.logo_path))
        self.pixel_placement = self._bounded_pixel_placement(self.pixel_placement)
        self._sync_legacy_ratio_from_pixel()
        self._update_spinboxes_from_pixel()
        self._refresh_preview()

    def _choose_output_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择导出目录")
        if folder:
            self.output_directory = Path(folder)
            self.output_dir_edit.setText(folder)

    def _load_images(self, raw_paths: list[str]) -> None:
        collected_images = collect_images(raw_paths)
        if not collected_images:
            QMessageBox.warning(self, "没有可用图片", "未找到支持的图片文件。")
            return

        existing = {item.source_path for item in self.items}
        new_items = [item for item in collected_images if item.source_path not in existing]
        if not new_items:
            QMessageBox.information(self, "重复导入", "这些图片已经在列表中了。")
            return

        for collected in new_items:
            image_item = ImageItem(source_path=collected.source_path, import_root=collected.import_root)
            try:
                width, height = self.processor.get_image_size(collected.source_path)
                image_item.width = width
                image_item.height = height
            except Exception as exc:  # noqa: BLE001
                image_item.status = "读取失败"
                image_item.message = str(exc)
            self.items.append(image_item)

        self._rebuild_table()
        self.summary_label.setText(f"已载入 {len(self.items)} 张图片，当前勾选 {len(self._checked_items())} 张")
        if self.image_table.rowCount() > 0 and self.image_table.currentRow() < 0:
            self.image_table.selectRow(0)
        self.pixel_placement = self._bounded_pixel_placement(self.pixel_placement)
        self._sync_legacy_ratio_from_pixel()
        self._update_spinboxes_from_pixel()
        self._refresh_preview()

    def _create_thumbnail_item(self, image_path: Path) -> QTableWidgetItem:
        pixmap = QPixmap(str(image_path))
        item = QTableWidgetItem()
        if pixmap.isNull():
            item.setText("-")
            return item
        scaled = pixmap.scaled(
            self.thumbnail_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        item.setIcon(QIcon(scaled))
        item.setText("")
        return item

    def _rebuild_table(self) -> None:
        self._table_syncing = True
        self.image_table.setRowCount(len(self.items))
        for row, item in enumerate(self.items):
            self.image_table.setItem(row, 0, build_check_item(item.selected_for_batch))
            preview_item = self._create_thumbnail_item(item.source_path)
            preview_item.setToolTip(str(item.source_path))
            self.image_table.setItem(row, 1, preview_item)
            self.image_table.setRowHeight(row, self.thumbnail_size.height() + 12)

            name_item = QTableWidgetItem(item.display_name)
            name_item.setToolTip(str(item.source_path))
            self.image_table.setItem(row, 2, name_item)

            root_text = str(item.import_root or item.source_path.parent)
            root_item = QTableWidgetItem(root_text)
            root_item.setToolTip(root_text)
            self.image_table.setItem(row, 3, root_item)
            self.image_table.setItem(row, 4, QTableWidgetItem(item.resolution_text))
            self.image_table.setItem(row, 5, QTableWidgetItem(item.status))
            message_item = QTableWidgetItem(item.message)
            message_item.setToolTip(item.message)
            self.image_table.setItem(row, 6, message_item)
        self._table_syncing = False

    def _handle_table_item_changed(self, table_item: QTableWidgetItem) -> None:
        if self._table_syncing or table_item.column() != 0:
            return
        row = table_item.row()
        if 0 <= row < len(self.items):
            self.items[row].selected_for_batch = table_item.checkState() == Qt.CheckState.Checked

    def _checked_items(self) -> list[ImageItem]:
        return [item for item in self.items if item.selected_for_batch]

    def _set_all_items_checked(self, checked: bool) -> None:
        for item in self.items:
            item.selected_for_batch = checked
        self._rebuild_table()
        self.summary_label.setText(f"已勾选 {len(self._checked_items())}/{len(self.items)} 张图片")

    def _apply_ratio_filter_selection(self) -> None:
        ratio_filter = str(self.ratio_filter_combo.currentData() or "all")
        for item in self.items:
            item.selected_for_batch = ratio_matches(item.width, item.height, ratio_filter)
        self._rebuild_table()
        ratio_label = self.ratio_filter_combo.currentText()
        self.summary_label.setText(f"已按 {ratio_label} 勾选 {len(self._checked_items())} 张图片")

    def _sync_preview_from_selection(self) -> None:
        self.pixel_placement = self._bounded_pixel_placement(self.pixel_placement)
        self._sync_legacy_ratio_from_pixel()
        self._update_spinboxes_from_pixel()
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        image_path = self._selected_image_path()
        self.preview_canvas.set_images(
            image_path,
            self.logo_path,
            self.pixel_placement,
            keep_aspect_ratio=self.render_options.keep_aspect_ratio,
        )

    def _pixel_spinbox_changed(self) -> None:
        self.pixel_placement = self._bounded_pixel_placement(
            PixelLogoPlacement(
                margin_x_px=self.x_spin.value(),
                margin_y_px=self.y_spin.value(),
                width_px=self.size_spin.value(),
                anchor=self.pixel_placement.anchor,
            )
        )
        self._sync_legacy_ratio_from_pixel()
        self._update_spinboxes_from_pixel()
        self.preview_canvas.set_placement(self.pixel_placement)

    def _handle_canvas_pixel_change(self, margin_x_px: int, margin_y_px: int, width_px: int, anchor: str) -> None:
        self.pixel_placement = self._bounded_pixel_placement(
            PixelLogoPlacement(
                margin_x_px=margin_x_px,
                margin_y_px=margin_y_px,
                width_px=width_px,
                anchor=anchor,
            )
        )
        self._sync_legacy_ratio_from_pixel()
        self._update_spinboxes_from_pixel()
        self.preview_canvas.set_placement(self.pixel_placement)

    def _update_spinboxes_from_pixel(self) -> None:
        self.x_spin.blockSignals(True)
        self.y_spin.blockSignals(True)
        self.size_spin.blockSignals(True)
        self.x_spin.setValue(self.pixel_placement.margin_x_px)
        self.y_spin.setValue(self.pixel_placement.margin_y_px)
        self.size_spin.setValue(self.pixel_placement.width_px)
        self.corner_label.setText(
            {
                "top_left": "左上角",
                "top_right": "右上角",
                "bottom_left": "左下角",
                "bottom_right": "右下角",
            }.get(self.pixel_placement.anchor, "左上角")
        )
        self.x_spin.blockSignals(False)
        self.y_spin.blockSignals(False)
        self.size_spin.blockSignals(False)

    def _update_export_mode_ui(self) -> None:
        mode = self.current_export_mode()
        needs_directory = mode == ExportMode.NEW_FOLDER
        self.output_dir_edit.setEnabled(needs_directory)
        self.output_dir_button.setEnabled(needs_directory)
        self.preserve_structure_checkbox.setEnabled(needs_directory)

    def current_export_mode(self) -> ExportMode:
        current = self.export_mode_combo.currentData()
        if isinstance(current, ExportMode):
            return current
        return ExportMode(str(current or ExportMode.NEW_FOLDER.value))

    def _run_batch(self) -> None:
        if not self.items:
            QMessageBox.warning(self, "缺少图片", "请先导入图片。")
            return
        selected_items = self._checked_items()
        if not selected_items:
            QMessageBox.warning(self, "未勾选素材", "请先勾选需要处理的图片。")
            return
        if not self.logo_path:
            QMessageBox.warning(self, "缺少 Logo", "请先选择一张 logo 图片。")
            return
        export_mode = self.current_export_mode()
        if export_mode == ExportMode.OVERWRITE:
            reply = QMessageBox.warning(
                self,
                "确认覆盖原图",
                "覆盖原图无法自动恢复，确定继续吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        config = BatchJobConfig(
            input_files=[item.source_path for item in selected_items],
            logo_file=self.logo_path,
            placement=self.placement,
            render_options=self.render_options,
            pixel_placement=self.pixel_placement,
            use_pixel_positioning=True,
            export_mode=export_mode,
            output_directory=self.output_directory if export_mode == ExportMode.NEW_FOLDER else None,
            output_suffix="",
            preserve_structure=self.preserve_structure_checkbox.isChecked(),
            source_roots={item.source_path: item.import_root for item in selected_items},
        )
        if export_mode == ExportMode.NEW_FOLDER and self.output_directory is None:
            suggested = self.processor.resolve_output_directory(config)
            self.output_directory = suggested
            self.output_dir_edit.setText(str(suggested))
            config.output_directory = suggested

        progress = QProgressDialog("正在处理图片...", "取消", 0, len(config.input_files), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)

        def on_progress(current: int, total: int, result) -> None:  # noqa: ANN001
            progress.setMaximum(total)
            progress.setValue(current)
            progress.setLabelText(f"已处理 {current}/{total}: {result.source_path.name}")
            self._apply_result(result)
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
            if progress.wasCanceled():
                raise RuntimeError("用户取消了批处理")

        try:
            summary = self.processor.process_batch(config, progress_callback=on_progress)
        except RuntimeError as exc:
            self.summary_label.setText(str(exc))
            return
        finally:
            progress.close()

        output_hint = self._build_output_summary_text(export_mode, config)
        self.summary_label.setText(
            f"处理完成: 共 {summary.total} 张，成功 {summary.succeeded}，失败 {summary.failed}。{output_hint}"
        )
        self._rebuild_table()
        self._open_output_directory_after_export(export_mode, config)

    def _apply_result(self, result) -> None:  # noqa: ANN001
        for item in self.items:
            if item.source_path != result.source_path:
                continue
            if result.success:
                item.status = "成功"
                item.message = str(result.output_path) if result.output_path else ""
                item.output_path = result.output_path
            else:
                item.status = "失败"
                item.message = result.error
            break
        self._rebuild_table()

    def _show_image_menu(self, pos) -> None:  # noqa: ANN001
        row = self.image_table.indexAt(pos).row()
        if row < 0:
            return
        menu = QMenu(self)
        remove_action = QAction("移除选中图片", self)
        remove_action.triggered.connect(lambda: self._remove_row(row))
        menu.addAction(remove_action)
        menu.exec(self.image_table.viewport().mapToGlobal(pos))

    def _remove_selected_rows(self) -> None:
        rows = sorted({index.row() for index in self.image_table.selectionModel().selectedRows()}, reverse=True)
        if not rows:
            QMessageBox.information(self, "未选择素材", "请先在列表里选中要移除的图片。")
            return
        for row in rows:
            if 0 <= row < len(self.items):
                self.items.pop(row)
        self._rebuild_table()
        if self.items:
            self.image_table.selectRow(min(rows[-1], len(self.items) - 1))
            self.summary_label.setText(f"已移除 {len(rows)} 张图片，剩余 {len(self.items)} 张")
        else:
            self._refresh_preview()
            self.summary_label.setText("图片列表已清空")

    def _remove_row(self, row: int) -> None:
        if 0 <= row < len(self.items):
            self.items.pop(row)
            self._rebuild_table()
            if self.items:
                self.image_table.selectRow(min(row, len(self.items) - 1))
            else:
                self._refresh_preview()
                self.summary_label.setText("图片列表已清空")

    def _selected_image_path(self) -> Path | None:
        row = self.image_table.currentRow()
        if 0 <= row < len(self.items):
            return self.items[row].source_path
        if self.items:
            return self.items[0].source_path
        return None

    def _selected_dimensions(self) -> tuple[int, int] | None:
        row = self.image_table.currentRow()
        if 0 <= row < len(self.items):
            item = self.items[row]
            if item.width and item.height:
                return item.width, item.height
        for item in self.items:
            if item.width and item.height:
                return item.width, item.height
        return None

    def _logo_dimensions(self) -> tuple[int, int] | None:
        if not self.logo_path:
            return None
        try:
            return self.processor.get_image_size(self.logo_path)
        except Exception:  # noqa: BLE001
            return None

    def _bounded_pixel_placement(self, placement: PixelLogoPlacement) -> PixelLogoPlacement:
        normalized = placement.normalized()
        image_size = self._selected_dimensions()
        logo_size = self._logo_dimensions()
        if not image_size or not logo_size:
            return normalized

        frame_width, frame_height = image_size
        logo_width, logo_height = logo_size
        left, top, overlay_width, overlay_height = normalized.to_overlay_box(
            frame_width=frame_width,
            frame_height=frame_height,
            logo_width=logo_width,
            logo_height=logo_height,
            keep_aspect_ratio=self.render_options.keep_aspect_ratio,
        )
        return PixelLogoPlacement.auto_from_overlay_box(
            left=left,
            top=top,
            overlay_width=overlay_width,
            overlay_height=overlay_height,
            frame_width=frame_width,
            frame_height=frame_height,
        )

    def _legacy_ratio_placement_from_pixel(self) -> LogoPlacement:
        image_size = self._selected_dimensions()
        logo_size = self._logo_dimensions()
        if not image_size or not logo_size:
            return self.placement.normalized()

        frame_width, frame_height = image_size
        logo_width, logo_height = logo_size
        left, top, overlay_width, overlay_height = self.pixel_placement.to_overlay_box(
            frame_width=frame_width,
            frame_height=frame_height,
            logo_width=logo_width,
            logo_height=logo_height,
            keep_aspect_ratio=self.render_options.keep_aspect_ratio,
        )
        return LogoPlacement.from_overlay_box(
            left=left,
            top=top,
            overlay_width=overlay_width,
            overlay_height=overlay_height,
            frame_width=frame_width,
            frame_height=frame_height,
            anchor=self.pixel_placement.anchor,
            reference_mode=self.render_options.reference_mode,
        )

    def _sync_legacy_ratio_from_pixel(self) -> None:
        self.placement = self._legacy_ratio_placement_from_pixel()

    def _pixel_placement_from_ratio(self, placement: LogoPlacement) -> PixelLogoPlacement:
        image_size = self._selected_dimensions()
        logo_size = self._logo_dimensions()
        if not image_size or not logo_size:
            return self.pixel_placement.normalized()

        frame_width, frame_height = image_size
        logo_width, logo_height = logo_size
        left, top, overlay_width, overlay_height = placement.normalized().to_overlay_box(
            frame_width=frame_width,
            frame_height=frame_height,
            logo_width=logo_width,
            logo_height=logo_height,
            keep_aspect_ratio=self.render_options.keep_aspect_ratio,
            reference_mode=self.render_options.reference_mode,
        )
        return PixelLogoPlacement.auto_from_overlay_box(
            left=left,
            top=top,
            overlay_width=overlay_width,
            overlay_height=overlay_height,
            frame_width=frame_width,
            frame_height=frame_height,
        )

    def _build_output_summary_text(self, export_mode: ExportMode, config: BatchJobConfig) -> str:
        if export_mode == ExportMode.OVERWRITE:
            return "输出位置: 已直接覆盖原图所在文件夹。"

        output_directory = config.output_directory or self.processor.resolve_output_directory(config)
        return f"输出文件夹: {output_directory}"

    def _open_output_directory_after_export(self, export_mode: ExportMode, config: BatchJobConfig) -> None:
        if export_mode != ExportMode.NEW_FOLDER:
            return

        output_directory = config.output_directory or self.processor.resolve_output_directory(config)
        if output_directory is None or not output_directory.exists():
            return

        try:
            os.startfile(str(output_directory))
        except OSError:
            # 导出已经成功，打开资源管理器失败不应影响结果提示。
            pass
