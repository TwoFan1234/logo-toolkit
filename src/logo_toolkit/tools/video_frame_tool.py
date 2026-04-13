from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
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
    QTableWidget,
    QTableWidgetItem,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from logo_toolkit.core.file_utils import collect_images, collect_videos
from logo_toolkit.core.models import VideoItem
from logo_toolkit.core.video_frame_processor import (
    OUTPUT_SIZE_AUTO_STANDARD,
    OUTPUT_SIZE_CUSTOM,
    OUTPUT_SIZE_FOLLOW_FRAME,
    FrameImageItem,
    VideoFrameJobConfig,
    VideoFrameProcessor,
)
from logo_toolkit.ui.selection_helpers import build_check_item, populate_ratio_filter_combo, ratio_matches
from logo_toolkit.ui.theme import configure_resizable_splitter, toolkit_tool_stylesheet


class DropTableWidget(QTableWidget):
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


class BatchVideoFrameToolWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.processor = VideoFrameProcessor()
        self.video_items: list[VideoItem] = []
        self.frame_items: list[FrameImageItem] = []
        self.output_directory: Path | None = None
        self._table_syncing = False
        self._build_ui()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(12)
        root_layout.addWidget(splitter)

        video_panel = QWidget()
        video_layout = QVBoxLayout(video_panel)
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.addWidget(self._build_video_group())

        frame_panel = QWidget()
        frame_layout = QVBoxLayout(frame_panel)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.addWidget(self._build_frame_group())

        settings_panel = QWidget()
        settings_layout = QVBoxLayout(settings_panel)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setSpacing(10)
        settings_layout.addWidget(self._build_output_group())
        settings_layout.addWidget(self._build_progress_group())
        settings_layout.addStretch(1)

        splitter.addWidget(video_panel)
        splitter.addWidget(frame_panel)
        splitter.addWidget(settings_panel)
        configure_resizable_splitter(
            splitter,
            [video_panel, frame_panel, settings_panel],
            stretches=[2, 2, 2],
            minimum_widths=[220, 220, 220],
            initial_sizes=[500, 500, 260],
        )

        self._apply_styles()
        self._refresh_output_size_options()

    def _build_video_group(self) -> QGroupBox:
        group = QGroupBox("1. 视频导入")
        layout = QVBoxLayout(group)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        add_files_button = QPushButton("添加视频")
        add_files_button.clicked.connect(self._choose_video_files)
        add_folder_button = QPushButton("导入文件夹")
        add_folder_button.clicked.connect(self._choose_video_folders)
        clear_button = QPushButton("清空")
        clear_button.clicked.connect(self._clear_videos)
        button_row.addWidget(add_files_button)
        button_row.addWidget(add_folder_button)
        button_row.addWidget(clear_button)

        ratio_row = QHBoxLayout()
        ratio_row.setSpacing(8)
        ratio_label = QLabel("比例筛选")
        ratio_label.setObjectName("filterLabel")
        self.video_ratio_filter_combo = QComboBox()
        populate_ratio_filter_combo(self.video_ratio_filter_combo)
        video_apply_ratio_button = QPushButton("应用")
        video_apply_ratio_button.setObjectName("compactButton")
        video_apply_ratio_button.clicked.connect(self._apply_video_ratio_filter_selection)
        ratio_row.addWidget(ratio_label)
        ratio_row.addWidget(self.video_ratio_filter_combo, stretch=1)
        ratio_row.addWidget(video_apply_ratio_button)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        video_check_all_button = QPushButton("全选")
        video_check_all_button.setObjectName("compactButton")
        video_check_all_button.clicked.connect(lambda: self._set_all_video_items_checked(True))
        video_uncheck_all_button = QPushButton("清空选择")
        video_uncheck_all_button.setObjectName("compactButton")
        video_uncheck_all_button.clicked.connect(lambda: self._set_all_video_items_checked(False))
        video_remove_button = QPushButton("移除选中")
        video_remove_button.setObjectName("compactButton")
        video_remove_button.clicked.connect(self._remove_selected_video_rows)
        action_row.addWidget(video_check_all_button)
        action_row.addWidget(video_uncheck_all_button)
        action_row.addStretch(1)
        action_row.addWidget(video_remove_button)

        self.video_table = DropTableWidget()
        self.video_table.setColumnCount(7)
        self.video_table.setHorizontalHeaderLabels(["执行", "文件名", "时长", "分辨率", "比例", "状态", "说明"])
        self.video_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.video_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.video_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.video_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.video_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.video_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.video_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.video_table.verticalHeader().setVisible(False)
        self.video_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.video_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.video_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.video_table.setAlternatingRowColors(True)
        self.video_table.paths_dropped.connect(self._load_videos)
        self.video_table.itemChanged.connect(self._handle_video_table_item_changed)
        self.video_table.setObjectName("videoFrameTable")

        hint = QLabel("支持多个视频或文件夹。工具会自动读取分辨率并识别 16:9、1:1、9:16 等比例。")
        hint.setWordWrap(True)
        hint.setObjectName("supportingLabel")

        layout.addLayout(button_row)
        layout.addLayout(ratio_row)
        layout.addLayout(action_row)
        layout.addWidget(hint)
        layout.addWidget(self.video_table, stretch=1)
        return group

    def _build_frame_group(self) -> QGroupBox:
        group = QGroupBox("2. 边框图片")
        layout = QVBoxLayout(group)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        add_files_button = QPushButton("添加边框")
        add_files_button.clicked.connect(self._choose_frame_files)
        add_folder_button = QPushButton("导入文件夹")
        add_folder_button.clicked.connect(self._choose_frame_folders)
        clear_button = QPushButton("清空")
        clear_button.clicked.connect(self._clear_frames)
        button_row.addWidget(add_files_button)
        button_row.addWidget(add_folder_button)
        button_row.addWidget(clear_button)

        ratio_row = QHBoxLayout()
        ratio_row.setSpacing(8)
        ratio_label = QLabel("比例筛选")
        ratio_label.setObjectName("filterLabel")
        self.frame_ratio_filter_combo = QComboBox()
        populate_ratio_filter_combo(self.frame_ratio_filter_combo)
        frame_apply_ratio_button = QPushButton("应用")
        frame_apply_ratio_button.setObjectName("compactButton")
        frame_apply_ratio_button.clicked.connect(self._apply_frame_ratio_filter_selection)
        ratio_row.addWidget(ratio_label)
        ratio_row.addWidget(self.frame_ratio_filter_combo, stretch=1)
        ratio_row.addWidget(frame_apply_ratio_button)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        frame_check_all_button = QPushButton("全选")
        frame_check_all_button.setObjectName("compactButton")
        frame_check_all_button.clicked.connect(lambda: self._set_all_frame_items_checked(True))
        frame_uncheck_all_button = QPushButton("清空选择")
        frame_uncheck_all_button.setObjectName("compactButton")
        frame_uncheck_all_button.clicked.connect(lambda: self._set_all_frame_items_checked(False))
        frame_remove_button = QPushButton("移除选中")
        frame_remove_button.setObjectName("compactButton")
        frame_remove_button.clicked.connect(self._remove_selected_frame_rows)
        action_row.addWidget(frame_check_all_button)
        action_row.addWidget(frame_uncheck_all_button)
        action_row.addStretch(1)
        action_row.addWidget(frame_remove_button)

        self.frame_table = DropTableWidget()
        self.frame_table.setColumnCount(6)
        self.frame_table.setHorizontalHeaderLabels(["执行", "文件名", "分辨率", "比例", "状态", "说明"])
        self.frame_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.frame_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.frame_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.frame_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.frame_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.frame_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.frame_table.verticalHeader().setVisible(False)
        self.frame_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.frame_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.frame_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.frame_table.setAlternatingRowColors(True)
        self.frame_table.itemSelectionChanged.connect(self._refresh_output_size_options)
        self.frame_table.paths_dropped.connect(self._load_frames)
        self.frame_table.itemChanged.connect(self._handle_frame_table_item_changed)
        self.frame_table.setObjectName("videoFrameTable")

        hint = QLabel("可以一次导入多张边框图。默认每张图按自己的尺寸输出，也可选择自动标准尺寸。")
        hint.setWordWrap(True)
        hint.setObjectName("supportingLabel")

        layout.addLayout(button_row)
        layout.addLayout(ratio_row)
        layout.addLayout(action_row)
        layout.addWidget(hint)
        layout.addWidget(self.frame_table, stretch=1)
        return group

    def _build_output_group(self) -> QGroupBox:
        group = QGroupBox("3. 输出设置")
        layout = QGridLayout(group)

        self.output_size_combo = QComboBox()
        self.output_size_combo.currentIndexChanged.connect(self._handle_output_size_change)
        self.custom_width_spin = QSpinBox()
        self.custom_width_spin.setRange(2, 8192)
        self.custom_width_spin.setSingleStep(2)
        self.custom_width_spin.setValue(1920)
        self.custom_height_spin = QSpinBox()
        self.custom_height_spin.setRange(2, 8192)
        self.custom_height_spin.setSingleStep(2)
        self.custom_height_spin.setValue(1080)

        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setReadOnly(True)
        self.output_dir_button = QPushButton("选择导出目录")
        self.output_dir_button.clicked.connect(self._choose_output_dir)
        self.preserve_structure_checkbox = QCheckBox("导出时保持原视频文件夹结构")
        self.preserve_structure_checkbox.setChecked(False)

        self.run_button = QPushButton("开始批量套边框")
        self.run_button.setObjectName("primaryRunButton")
        self.run_button.clicked.connect(self._run_batch)

        note = QLabel("视频会按最长边适配到边框画布中间，边框图作为底图，视频保留音频。")
        note.setWordWrap(True)
        note.setObjectName("supportingLabel")

        layout.addWidget(QLabel("输出尺寸"), 0, 0)
        layout.addWidget(self.output_size_combo, 0, 1, 1, 2)
        layout.addWidget(QLabel("自定义宽高"), 1, 0)
        layout.addWidget(self.custom_width_spin, 1, 1)
        layout.addWidget(self.custom_height_spin, 1, 2)
        layout.addWidget(QLabel("导出目录"), 2, 0)
        layout.addWidget(self.output_dir_edit, 2, 1)
        layout.addWidget(self.output_dir_button, 2, 2)
        layout.addWidget(self.preserve_structure_checkbox, 3, 0, 1, 3)
        layout.addWidget(note, 4, 0, 1, 3)
        layout.addWidget(self.run_button, 5, 0, 1, 3)
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

    def _choose_video_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "选择视频", "", "Videos (*.mp4 *.mov *.mkv *.avi *.webm *.m4v)")
        if files:
            self._load_videos(files)

    def _choose_video_folders(self) -> None:
        folders = self._choose_folders("选择一个或多个视频文件夹")
        if folders:
            self._load_videos(folders)

    def _choose_frame_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "选择边框图片", "", "Images (*.jpg *.jpeg *.png *.webp)")
        if files:
            self._load_frames(files)

    def _choose_frame_folders(self) -> None:
        folders = self._choose_folders("选择一个或多个边框图片文件夹")
        if folders:
            self._load_frames(folders)

    def _choose_folders(self, title: str) -> list[str]:
        dialog = QFileDialog(self, title)
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setOption(QFileDialog.Option.ShowDirsOnly, True)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        for view in dialog.findChildren((QListView, QTreeView)):
            view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        if dialog.exec():
            return dialog.selectedFiles()
        return []

    def _load_videos(self, raw_paths: list[str]) -> None:
        collected_videos = collect_videos(raw_paths)
        if not collected_videos:
            QMessageBox.warning(self, "没有可用视频", "未找到支持的视频文件。")
            return
        existing = {item.source_path for item in self.video_items}
        for collected in collected_videos:
            if collected.source_path in existing:
                continue
            try:
                item = self.processor.get_video_metadata(collected.source_path)
                item.import_root = collected.import_root
            except Exception as exc:  # noqa: BLE001
                item = VideoItem(source_path=collected.source_path, import_root=collected.import_root)
                item.status = "读取失败"
                item.message = str(exc)
            self.video_items.append(item)
        self._rebuild_video_table()
        self.summary_label.setText(f"已载入 {len(self.video_items)} 个视频，当前勾选 {len(self._checked_video_items())} 个")

    def _load_frames(self, raw_paths: list[str]) -> None:
        collected_frames = collect_images(raw_paths)
        if not collected_frames:
            QMessageBox.warning(self, "没有可用边框", "未找到支持的图片文件。")
            return
        existing = {item.source_path for item in self.frame_items}
        for collected in collected_frames:
            if collected.source_path in existing:
                continue
            try:
                item = self.processor.get_frame_metadata(collected.source_path)
            except Exception as exc:  # noqa: BLE001
                item = FrameImageItem(source_path=collected.source_path, status="读取失败", message=str(exc))
            self.frame_items.append(item)
        self._rebuild_frame_table()
        if self.frame_table.rowCount() > 0 and self.frame_table.currentRow() < 0:
            self.frame_table.selectRow(0)
        self._refresh_output_size_options()
        self.summary_label.setText(f"已载入 {len(self.frame_items)} 张边框图，当前勾选 {len(self._checked_frame_items())} 张")

    def _clear_videos(self) -> None:
        self.video_items.clear()
        self.video_table.setRowCount(0)
        self.summary_label.setText("视频列表已清空")

    def _clear_frames(self) -> None:
        self.frame_items.clear()
        self.frame_table.setRowCount(0)
        self._refresh_output_size_options()
        self.summary_label.setText("边框图片列表已清空")

    def _rebuild_video_table(self) -> None:
        self._table_syncing = True
        self.video_table.setRowCount(len(self.video_items))
        for row, item in enumerate(self.video_items):
            self.video_table.setItem(row, 0, build_check_item(item.selected_for_batch))
            self.video_table.setItem(row, 1, self._table_item(item.display_name, str(item.source_path)))
            self.video_table.setItem(row, 2, QTableWidgetItem(item.duration_text))
            self.video_table.setItem(row, 3, QTableWidgetItem(item.resolution_text))
            ratio = VideoFrameProcessor.ratio_label(item.width, item.height) if item.width and item.height else "-"
            self.video_table.setItem(row, 4, QTableWidgetItem(ratio))
            self.video_table.setItem(row, 5, QTableWidgetItem(item.status))
            self.video_table.setItem(row, 6, self._table_item(item.message, item.message))
        self._table_syncing = False

    def _rebuild_frame_table(self) -> None:
        self._table_syncing = True
        self.frame_table.setRowCount(len(self.frame_items))
        for row, item in enumerate(self.frame_items):
            self.frame_table.setItem(row, 0, build_check_item(item.selected_for_batch))
            self.frame_table.setItem(row, 1, self._table_item(item.display_name, str(item.source_path)))
            self.frame_table.setItem(row, 2, QTableWidgetItem(item.resolution_text))
            self.frame_table.setItem(row, 3, QTableWidgetItem(item.ratio_text))
            self.frame_table.setItem(row, 4, QTableWidgetItem(item.status))
            self.frame_table.setItem(row, 5, self._table_item(item.message, item.message))
        self._table_syncing = False

    def _table_item(self, text: str, tooltip: str = "") -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        if tooltip:
            item.setToolTip(tooltip)
        return item

    def _handle_video_table_item_changed(self, table_item: QTableWidgetItem) -> None:
        if self._table_syncing or table_item.column() != 0:
            return
        row = table_item.row()
        if 0 <= row < len(self.video_items):
            self.video_items[row].selected_for_batch = table_item.checkState() == Qt.CheckState.Checked

    def _handle_frame_table_item_changed(self, table_item: QTableWidgetItem) -> None:
        if self._table_syncing or table_item.column() != 0:
            return
        row = table_item.row()
        if 0 <= row < len(self.frame_items):
            self.frame_items[row].selected_for_batch = table_item.checkState() == Qt.CheckState.Checked

    def _checked_video_items(self) -> list[VideoItem]:
        return [item for item in self.video_items if item.selected_for_batch]

    def _checked_frame_items(self) -> list[FrameImageItem]:
        return [item for item in self.frame_items if item.selected_for_batch]

    def _set_all_video_items_checked(self, checked: bool) -> None:
        for item in self.video_items:
            item.selected_for_batch = checked
        self._rebuild_video_table()
        self.summary_label.setText(f"已勾选 {len(self._checked_video_items())}/{len(self.video_items)} 个视频")

    def _set_all_frame_items_checked(self, checked: bool) -> None:
        for item in self.frame_items:
            item.selected_for_batch = checked
        self._rebuild_frame_table()
        self.summary_label.setText(f"已勾选 {len(self._checked_frame_items())}/{len(self.frame_items)} 张边框图")
        self._refresh_output_size_options()

    def _apply_video_ratio_filter_selection(self) -> None:
        ratio_filter = str(self.video_ratio_filter_combo.currentData() or "all")
        for item in self.video_items:
            item.selected_for_batch = ratio_matches(item.width, item.height, ratio_filter)
        self._rebuild_video_table()
        self.summary_label.setText(
            f"已按 {self.video_ratio_filter_combo.currentText()} 勾选 {len(self._checked_video_items())} 个视频"
        )

    def _apply_frame_ratio_filter_selection(self) -> None:
        ratio_filter = str(self.frame_ratio_filter_combo.currentData() or "all")
        for item in self.frame_items:
            item.selected_for_batch = ratio_matches(item.width, item.height, ratio_filter)
        self._rebuild_frame_table()
        self.summary_label.setText(
            f"已按 {self.frame_ratio_filter_combo.currentText()} 勾选 {len(self._checked_frame_items())} 张边框图"
        )
        self._refresh_output_size_options()

    def _remove_selected_video_rows(self) -> None:
        rows = sorted({index.row() for index in self.video_table.selectionModel().selectedRows()}, reverse=True)
        if not rows:
            QMessageBox.information(self, "未选择素材", "请先在列表里选中要移除的视频。")
            return
        for row in rows:
            if 0 <= row < len(self.video_items):
                self.video_items.pop(row)
        self._rebuild_video_table()
        if self.video_items:
            self.video_table.selectRow(min(rows[-1], len(self.video_items) - 1))
            self.summary_label.setText(f"已移除 {len(rows)} 个视频，剩余 {len(self.video_items)} 个")
        else:
            self.summary_label.setText("视频列表已清空")

    def _remove_selected_frame_rows(self) -> None:
        rows = sorted({index.row() for index in self.frame_table.selectionModel().selectedRows()}, reverse=True)
        if not rows:
            QMessageBox.information(self, "未选择素材", "请先在列表里选中要移除的边框图。")
            return
        for row in rows:
            if 0 <= row < len(self.frame_items):
                self.frame_items.pop(row)
        self._rebuild_frame_table()
        if self.frame_items:
            self.frame_table.selectRow(min(rows[-1], len(self.frame_items) - 1))
            self.summary_label.setText(f"已移除 {len(rows)} 张边框图，剩余 {len(self.frame_items)} 张")
        else:
            self.summary_label.setText("边框图片列表已清空")
        self._refresh_output_size_options()

    def _selected_frame_item(self) -> FrameImageItem | None:
        row = self.frame_table.currentRow()
        if 0 <= row < len(self.frame_items):
            return self.frame_items[row]
        if self.frame_items:
            return self.frame_items[0]
        return None

    def _refresh_output_size_options(self) -> None:
        if not hasattr(self, "output_size_combo"):
            return
        self.output_size_combo.blockSignals(True)
        self.output_size_combo.clear()
        self.output_size_combo.addItem("跟随每张边框原尺寸", (OUTPUT_SIZE_FOLLOW_FRAME, None))
        self.output_size_combo.addItem("自动标准尺寸（按边框比例）", (OUTPUT_SIZE_AUTO_STANDARD, None))
        frame = self._selected_frame_item()
        if frame and frame.width and frame.height:
            standard = VideoFrameProcessor.standard_size_for_ratio(frame.width, frame.height)
            self.output_size_combo.addItem(
                f"当前边框同比例: {standard[0]} x {standard[1]}",
                (OUTPUT_SIZE_CUSTOM, standard),
            )
            self.custom_width_spin.setValue(standard[0])
            self.custom_height_spin.setValue(standard[1])
        self.output_size_combo.addItem("自定义尺寸", (OUTPUT_SIZE_CUSTOM, "manual"))
        self.output_size_combo.setCurrentIndex(0)
        self.output_size_combo.blockSignals(False)
        self._handle_output_size_change()

    def _handle_output_size_change(self, *_args) -> None:  # noqa: ANN002
        mode, payload = self.output_size_combo.currentData() or (OUTPUT_SIZE_FOLLOW_FRAME, None)
        manual = mode == OUTPUT_SIZE_CUSTOM and payload == "manual"
        self.custom_width_spin.setEnabled(manual)
        self.custom_height_spin.setEnabled(manual)
        if mode == OUTPUT_SIZE_CUSTOM and isinstance(payload, tuple):
            self.custom_width_spin.setValue(payload[0])
            self.custom_height_spin.setValue(payload[1])

    def _choose_output_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择导出目录")
        if folder:
            self.output_directory = Path(folder)
            self.output_dir_edit.setText(folder)

    def _current_config(self) -> VideoFrameJobConfig:
        mode, payload = self.output_size_combo.currentData() or (OUTPUT_SIZE_FOLLOW_FRAME, None)
        custom_size = None
        if mode == OUTPUT_SIZE_CUSTOM:
            custom_size = payload if isinstance(payload, tuple) else (self.custom_width_spin.value(), self.custom_height_spin.value())
        selected_videos = self._checked_video_items()
        selected_frames = self._checked_frame_items()
        return VideoFrameJobConfig(
            input_files=[item.source_path for item in selected_videos],
            frame_files=[item.source_path for item in selected_frames],
            output_directory=self.output_directory,
            output_size_mode=mode,
            custom_output_size=custom_size,
            source_roots={item.source_path: item.import_root for item in selected_videos}
            if self.preserve_structure_checkbox.isChecked()
            else {},
        )

    def _run_batch(self) -> None:
        if not self.video_items:
            QMessageBox.warning(self, "缺少视频", "请先导入视频。")
            return
        if not self.frame_items:
            QMessageBox.warning(self, "缺少边框", "请先导入边框图片。")
            return
        if not self._checked_video_items():
            QMessageBox.warning(self, "未勾选视频", "请至少勾选一个要处理的视频。")
            return
        if not self._checked_frame_items():
            QMessageBox.warning(self, "未勾选边框", "请至少勾选一张要使用的边框图。")
            return
        config = self._current_config()
        if self.output_directory is None:
            self.output_directory = self.processor.resolve_output_directory(config)
            self.output_dir_edit.setText(str(self.output_directory))
            config.output_directory = self.output_directory

        progress = QProgressDialog("正在套边框...", "取消", 0, len(config.input_files) * len(config.frame_files), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)

        def on_progress(current: int, total: int, result) -> None:  # noqa: ANN001
            progress.setMaximum(total)
            progress.setValue(current)
            progress.setLabelText(f"已处理 {current}/{total}: {result.source_path.name}")
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
            if progress.wasCanceled():
                raise RuntimeError("用户取消了批处理")

        try:
            summary = self.processor.process_batch(config, progress_callback=on_progress)
        except RuntimeError as exc:
            self.summary_label.setText(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "处理失败", str(exc))
            self.summary_label.setText(str(exc))
            return
        finally:
            progress.close()

        output_directory = config.output_directory or self.processor.resolve_output_directory(config)
        self.summary_label.setText(
            f"处理完成: 共 {summary.total} 个，成功 {summary.succeeded}，失败 {summary.failed}。输出文件夹: {output_directory}"
        )
        self._open_output_directory(output_directory)

    def _open_output_directory(self, output_directory: Path) -> None:
        if not output_directory.exists():
            return
        try:
            os.startfile(str(output_directory))
        except OSError:
            pass

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
            #videoFrameTable {
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
            """
        )
        self.setStyleSheet(toolkit_tool_stylesheet())
