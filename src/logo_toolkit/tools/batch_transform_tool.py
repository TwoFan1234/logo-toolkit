from __future__ import annotations

import os
from pathlib import Path

from PIL.ImageQt import ImageQt
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
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
    QMessageBox,
    QProgressBar,
    QProgressDialog,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidgetItem,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from logo_toolkit.core.batch_transform_processor import BatchTransformProcessor
from logo_toolkit.core.file_utils import collect_images
from logo_toolkit.core.models import (
    BatchTransformConfig,
    CompressionLevel,
    ExportMode,
    ImageItem,
    ResizeConfig,
    ResizeMode,
    TransformFormat,
)
from logo_toolkit.tools.logo_tool import ImageTableWidget, ImportGroupBox
from logo_toolkit.ui.selection_helpers import build_check_item, populate_ratio_filter_combo, ratio_matches
from logo_toolkit.ui.theme import configure_resizable_splitter, toolkit_tool_stylesheet


class BatchTransformToolWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.processor = BatchTransformProcessor()
        self.items: list[ImageItem] = []
        self.output_directory: Path | None = None
        self.thumbnail_size = QSize(72, 72)
        self._preview_pixmap = QPixmap()
        self._table_syncing = False
        self._build_ui()

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
        settings_layout.addWidget(self._build_transform_group())
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
        self._update_resize_ui()
        self._update_export_mode_ui()
        self._refresh_preview()

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
        self.image_table.itemSelectionChanged.connect(self._refresh_preview)
        self.image_table.itemChanged.connect(self._handle_table_item_changed)
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

    def _build_transform_group(self) -> QGroupBox:
        group = QGroupBox("2. 处理选项")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)

        self.format_combo = QComboBox()
        self.format_combo.addItem("原格式", TransformFormat.KEEP)
        self.format_combo.addItem("JPG", TransformFormat.JPEG)
        self.format_combo.addItem("PNG", TransformFormat.PNG)
        self.format_combo.addItem("WEBP", TransformFormat.WEBP)

        self.compression_combo = QComboBox()
        self.compression_combo.addItem("关闭", CompressionLevel.NONE)
        self.compression_combo.addItem("轻度", CompressionLevel.LIGHT)
        self.compression_combo.addItem("中等", CompressionLevel.MEDIUM)
        self.compression_combo.addItem("高压缩", CompressionLevel.HIGH)

        self.resize_mode_combo = QComboBox()
        self.resize_mode_combo.addItem("不改尺寸", ResizeMode.NONE)
        self.resize_mode_combo.addItem("按百分比", ResizeMode.SCALE_PERCENT)
        self.resize_mode_combo.addItem("按最长边", ResizeMode.LONGEST_EDGE)
        self.resize_mode_combo.addItem("按宽高", ResizeMode.EXACT_DIMENSIONS)
        self.resize_mode_combo.currentIndexChanged.connect(self._update_resize_ui)

        self.scale_percent_spin = self._create_spinbox(100, 1, 500, " %")
        self.longest_edge_spin = self._create_spinbox(1600, 16, 10000, " px")
        self.target_width_spin = self._create_spinbox(1600, 16, 10000, " px")
        self.target_height_spin = self._create_spinbox(1600, 16, 10000, " px")

        self.keep_aspect_checkbox = QCheckBox("按宽高模式下保持比例")
        self.keep_aspect_checkbox.setChecked(True)

        for widget in (
            self.format_combo,
            self.compression_combo,
            self.resize_mode_combo,
            self.scale_percent_spin,
            self.longest_edge_spin,
            self.target_width_spin,
            self.target_height_spin,
            self.keep_aspect_checkbox,
        ):
            if hasattr(widget, "currentIndexChanged"):
                widget.currentIndexChanged.connect(self._refresh_preview)
            elif hasattr(widget, "valueChanged"):
                widget.valueChanged.connect(self._refresh_preview)
            else:
                widget.toggled.connect(self._refresh_preview)
        self.format_combo.currentIndexChanged.connect(self._update_export_mode_ui)

        form.addRow("输出格式", self.format_combo)
        form.addRow("压缩级别", self.compression_combo)
        form.addRow("改尺寸方式", self.resize_mode_combo)
        form.addRow("缩放比例", self.scale_percent_spin)
        form.addRow("最长边", self.longest_edge_spin)
        form.addRow("目标宽度", self.target_width_spin)
        form.addRow("目标高度", self.target_height_spin)
        form.addRow("尺寸约束", self.keep_aspect_checkbox)

        help_text = QLabel("处理顺序固定为：先改尺寸，再按目标格式和压缩方式导出。")
        help_text.setWordWrap(True)
        help_text.setObjectName("supportingLabel")

        layout.addLayout(form)
        layout.addWidget(help_text)
        return group

    def _build_export_group(self) -> QGroupBox:
        group = QGroupBox("3. 导出设置")
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

        self.export_hint_label = QLabel()
        self.export_hint_label.setWordWrap(True)
        self.export_hint_label.setObjectName("supportingLabel")

        self.run_button = QPushButton("开始批量处理")
        self.run_button.setObjectName("primaryRunButton")
        self.run_button.clicked.connect(self._run_batch)

        layout.addWidget(QLabel("输出模式"), 0, 0)
        layout.addWidget(self.export_mode_combo, 0, 1, 1, 2)
        layout.addWidget(QLabel("导出目录"), 1, 0)
        layout.addWidget(self.output_dir_edit, 1, 1)
        layout.addWidget(self.output_dir_button, 1, 2)
        layout.addWidget(self.preserve_structure_checkbox, 2, 0, 1, 3)
        layout.addWidget(self.export_hint_label, 3, 0, 1, 3)
        layout.addWidget(self.run_button, 4, 0, 1, 3)
        return group

    def _build_progress_group(self) -> QGroupBox:
        group = QGroupBox("4. 处理结果")
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

        preview_title = QLabel("处理预览")
        preview_title.setObjectName("previewTitle")

        preview_badge = QLabel("结果预览")
        preview_badge.setObjectName("previewBadge")

        title_row.addWidget(preview_title)
        title_row.addWidget(preview_badge)
        title_row.addStretch(1)

        tips = QLabel("选中一张图片后，这里会显示处理后的预览结果和关键参数摘要。")
        tips.setWordWrap(True)
        tips.setObjectName("previewTips")

        self.preview_meta_label = QLabel("当前未选择图片")
        self.preview_meta_label.setWordWrap(True)
        self.preview_meta_label.setObjectName("supportingLabel")

        self.preview_image_label = QLabel("导入图片后在这里预览")
        self.preview_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_image_label.setMinimumSize(220, 220)
        self.preview_image_label.setObjectName("previewImageLabel")

        layout.addLayout(title_row)
        layout.addWidget(tips)
        layout.addWidget(self.preview_meta_label)
        layout.addWidget(self.preview_image_label, stretch=1)
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
            QLineEdit, QComboBox, QSpinBox, QTableWidget {
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
            #previewImageLabel {
                background: white;
                border: 1px solid #ddceb3;
                border-radius: 14px;
                color: #6f6554;
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

    def _create_spinbox(self, value: int, minimum: int, maximum: int, suffix: str) -> QSpinBox:
        spinbox = QSpinBox()
        spinbox.setRange(minimum, maximum)
        spinbox.setValue(value)
        spinbox.setSuffix(suffix)
        return spinbox

    def _current_config(self) -> BatchTransformConfig:
        resize_config = ResizeConfig(
            mode=self.current_resize_mode(),
            scale_percent=self.scale_percent_spin.value(),
            longest_edge=self.longest_edge_spin.value(),
            target_width=self.target_width_spin.value(),
            target_height=self.target_height_spin.value(),
            keep_aspect_ratio=self.keep_aspect_checkbox.isChecked(),
        )
        selected_items = self._checked_items()
        return BatchTransformConfig(
            input_files=[item.source_path for item in selected_items],
            transform_format=self.current_transform_format(),
            compression_level=self.current_compression_level(),
            resize_config=resize_config,
            export_mode=self.current_export_mode(),
            output_directory=self.output_directory,
            preserve_structure=self.preserve_structure_checkbox.isChecked(),
            source_roots={item.source_path: item.import_root for item in selected_items},
        )

    def _update_resize_ui(self) -> None:
        mode = self.current_resize_mode()
        is_scale = mode == ResizeMode.SCALE_PERCENT
        is_longest = mode == ResizeMode.LONGEST_EDGE
        is_exact = mode == ResizeMode.EXACT_DIMENSIONS

        self.scale_percent_spin.setEnabled(is_scale)
        self.longest_edge_spin.setEnabled(is_longest)
        self.target_width_spin.setEnabled(is_exact)
        self.target_height_spin.setEnabled(is_exact)
        self.keep_aspect_checkbox.setEnabled(is_exact)
        if not is_exact:
            self.keep_aspect_checkbox.setChecked(True)
        self._refresh_preview()

    def _update_export_mode_ui(self) -> None:
        mode = self.current_export_mode()
        needs_directory = mode == ExportMode.NEW_FOLDER
        self.output_dir_edit.setEnabled(needs_directory)
        self.output_dir_button.setEnabled(needs_directory)
        self.preserve_structure_checkbox.setEnabled(needs_directory)

        if mode == ExportMode.OVERWRITE and self.current_transform_format() != TransformFormat.KEEP:
            self.export_hint_label.setText("覆盖原图模式不支持转格式，请改用导出到新文件夹。")
        elif mode == ExportMode.OVERWRITE:
            self.export_hint_label.setText("将直接覆盖原图，请谨慎操作。")
        else:
            self.export_hint_label.setText("导出完成后会自动打开输出文件夹。")

    def _choose_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "选择图片", "", "Images (*.jpg *.jpeg *.png *.webp)")
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
        self._refresh_preview()

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
        self.summary_label.setText(f"已按 {self.ratio_filter_combo.currentText()} 勾选 {len(self._checked_items())} 张图片")

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

    def _refresh_preview(self) -> None:
        image_path = self._selected_image_path()
        if image_path is None:
            self._update_export_mode_ui()
            self.preview_meta_label.setText("当前未选择图片")
            self.preview_image_label.setText("导入图片后在这里预览")
            self.preview_image_label.setPixmap(QPixmap())
            return

        config = self._current_config()
        try:
            preview_image = self.processor.render_preview(image_path, config, max_size=(900, 700))
            self._preview_pixmap = QPixmap.fromImage(ImageQt(preview_image))
            display = self._preview_pixmap.scaled(
                self.preview_image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.preview_image_label.setPixmap(display)
            self.preview_image_label.setText("")
            self.preview_meta_label.setText(self._build_preview_summary(image_path, config))
        except Exception as exc:  # noqa: BLE001
            self.preview_image_label.setPixmap(QPixmap())
            self.preview_image_label.setText("预览生成失败")
            self.preview_meta_label.setText(str(exc))

        self._update_export_mode_ui()

    def _build_preview_summary(self, image_path: Path, config: BatchTransformConfig) -> str:
        original_size = self.processor.get_image_size(image_path)
        target_size = self.processor.estimate_output_size(original_size, config.resize_config)
        source_format = image_path.suffix.lower().lstrip(".")
        target_format = source_format if config.transform_format == TransformFormat.KEEP else config.transform_format.value
        return (
            f"原始尺寸: {original_size[0]} x {original_size[1]}    "
            f"处理后: {target_size[0]} x {target_size[1]}\n"
            f"输出格式: {target_format.upper()}    压缩: {self._compression_text(config.compression_level)}"
        )

    def _compression_text(self, level: CompressionLevel) -> str:
        mapping = {
            CompressionLevel.NONE: "关闭",
            CompressionLevel.LIGHT: "轻度",
            CompressionLevel.MEDIUM: "中等",
            CompressionLevel.HIGH: "高压缩",
        }
        return mapping[level]

    def _selected_image_path(self) -> Path | None:
        row = self.image_table.currentRow()
        if 0 <= row < len(self.items):
            return self.items[row].source_path
        if self.items:
            return self.items[0].source_path
        return None

    def current_export_mode(self) -> ExportMode:
        current = self.export_mode_combo.currentData()
        if isinstance(current, ExportMode):
            return current
        return ExportMode(str(current or ExportMode.NEW_FOLDER.value))

    def current_transform_format(self) -> TransformFormat:
        current = self.format_combo.currentData()
        if isinstance(current, TransformFormat):
            return current
        return TransformFormat(str(current or TransformFormat.KEEP.value))

    def current_compression_level(self) -> CompressionLevel:
        current = self.compression_combo.currentData()
        if isinstance(current, CompressionLevel):
            return current
        return CompressionLevel(str(current or CompressionLevel.NONE.value))

    def current_resize_mode(self) -> ResizeMode:
        current = self.resize_mode_combo.currentData()
        if isinstance(current, ResizeMode):
            return current
        return ResizeMode(str(current or ResizeMode.NONE.value))

    def _run_batch(self) -> None:
        if not self.items:
            QMessageBox.warning(self, "缺少图片", "请先导入图片。")
            return
        if not self._checked_items():
            QMessageBox.warning(self, "未勾选素材", "请先勾选需要处理的图片。")
            return

        config = self._current_config()
        if not config.has_operations():
            QMessageBox.information(self, "未选择处理操作", "请至少启用一种处理操作。")
            return
        if config.export_mode == ExportMode.OVERWRITE and config.transform_format != TransformFormat.KEEP:
            QMessageBox.warning(self, "不支持的组合", "覆盖原图模式下不能同时转换格式，请改用导出到新文件夹。")
            return
        if config.export_mode == ExportMode.OVERWRITE:
            reply = QMessageBox.warning(
                self,
                "确认覆盖原图",
                "覆盖原图无法自动恢复，确定继续吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        if config.export_mode == ExportMode.NEW_FOLDER and self.output_directory is None:
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

        output_hint = self._build_output_summary_text(config)
        self.summary_label.setText(
            f"处理完成: 共 {summary.total} 张，成功 {summary.succeeded}，失败 {summary.failed}。{output_hint}"
        )
        self._rebuild_table()
        self._open_output_directory_after_export(config)

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

    def _build_output_summary_text(self, config: BatchTransformConfig) -> str:
        if config.export_mode == ExportMode.OVERWRITE:
            return "输出位置: 已直接覆盖原图所在文件夹。"
        output_directory = config.output_directory or self.processor.resolve_output_directory(config)
        return f"输出文件夹: {output_directory}"

    def _open_output_directory_after_export(self, config: BatchTransformConfig) -> None:
        if config.export_mode != ExportMode.NEW_FOLDER:
            return
        output_directory = config.output_directory or self.processor.resolve_output_directory(config)
        if output_directory is None or not output_directory.exists():
            return
        try:
            os.startfile(str(output_directory))
        except OSError:
            pass
