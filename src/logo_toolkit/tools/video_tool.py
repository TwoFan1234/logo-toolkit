from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, Signal
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
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from logo_toolkit.core.file_utils import collect_videos
from logo_toolkit.core.models import (
    AudioExportFormat,
    AudioExtractSettings,
    VideoBatchConfig,
    VideoCompressionPreset,
    VideoContainerFormat,
    VideoConversionSettings,
    VideoCompressionSettings,
    VideoItem,
    VideoOperationType,
    VideoResizeSettings,
    VideoTrimSettings,
)
from logo_toolkit.core.video_processor import VideoProcessor


class VideoImportGroupBox(QGroupBox):
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


class VideoTableWidget(QTableWidget):
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


class BatchVideoToolWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.processor = VideoProcessor()
        self.items: list[VideoItem] = []
        self.output_directory: Path | None = None
        self.resize_presets: dict[str, tuple[int, int]] = {
            "1920 x 1080 (1080p)": (1920, 1080),
            "1280 x 720 (720p)": (1280, 720),
            "1080 x 1920 (竖屏)": (1080, 1920),
            "自定义": (0, 0),
        }
        self._build_ui()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(12)
        root_layout.addWidget(splitter)

        import_panel = QWidget()
        import_layout = QVBoxLayout(import_panel)
        import_layout.setContentsMargins(0, 0, 0, 0)
        import_layout.addWidget(self._build_import_group())

        operation_panel = QWidget()
        operation_layout = QVBoxLayout(operation_panel)
        operation_layout.setContentsMargins(0, 0, 0, 0)
        operation_layout.setSpacing(10)
        operation_layout.addWidget(self._build_operation_group())
        operation_layout.addWidget(self._build_metadata_group())
        operation_layout.addStretch(1)

        output_panel = QWidget()
        output_layout = QVBoxLayout(output_panel)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.setSpacing(10)
        output_layout.addWidget(self._build_output_group())
        output_layout.addWidget(self._build_progress_group())
        output_layout.addStretch(1)

        splitter.addWidget(import_panel)
        splitter.addWidget(operation_panel)
        splitter.addWidget(output_panel)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 1)
        splitter.setSizes([700, 430, 360])

        self._apply_styles()
        self._handle_operation_change(0)
        self._refresh_selected_metadata()

    def _build_import_group(self) -> QGroupBox:
        group = VideoImportGroupBox("1. 视频导入")
        group.paths_dropped.connect(self._load_videos)
        layout = QVBoxLayout(group)

        buttons_layout = QHBoxLayout()
        add_files_button = QPushButton("添加视频")
        add_files_button.clicked.connect(self._choose_files)
        add_folder_button = QPushButton("导入文件夹")
        add_folder_button.clicked.connect(self._choose_folders)
        clear_button = QPushButton("清空")
        clear_button.clicked.connect(self._clear_videos)
        buttons_layout.addWidget(add_files_button)
        buttons_layout.addWidget(add_folder_button)
        buttons_layout.addWidget(clear_button)

        self.video_table = VideoTableWidget()
        self.video_table.setColumnCount(6)
        self.video_table.setHorizontalHeaderLabels(["文件名", "导入根目录", "时长", "分辨率", "状态", "说明"])
        self.video_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.video_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.video_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.video_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.video_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.video_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.video_table.verticalHeader().setVisible(False)
        self.video_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.video_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.video_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.video_table.setAlternatingRowColors(True)
        self.video_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.video_table.customContextMenuRequested.connect(self._show_video_menu)
        self.video_table.itemSelectionChanged.connect(self._refresh_selected_metadata)
        self.video_table.paths_dropped.connect(self._load_videos)
        self.video_table.setMinimumHeight(420)
        self.video_table.setObjectName("videoTable")

        hint = QLabel("支持拖入多个视频文件或文件夹，工具会自动递归读取视频文件。")
        hint.setWordWrap(True)
        hint.setObjectName("supportingLabel")

        layout.addLayout(buttons_layout)
        layout.addWidget(hint)
        layout.addWidget(self.video_table, stretch=1)
        return group

    def _build_operation_group(self) -> QGroupBox:
        group = QGroupBox("2. 处理模式")
        layout = QVBoxLayout(group)

        top_form = QFormLayout()
        self.operation_combo = QComboBox()
        self.operation_combo.addItem("视频压缩", VideoOperationType.COMPRESS)
        self.operation_combo.addItem("视频转格式", VideoOperationType.CONVERT)
        self.operation_combo.addItem("视频时长裁剪", VideoOperationType.TRIM)
        self.operation_combo.addItem("视频改尺寸", VideoOperationType.RESIZE)
        self.operation_combo.addItem("视频提取音频", VideoOperationType.EXTRACT_AUDIO)
        self.operation_combo.currentIndexChanged.connect(self._handle_operation_change)
        top_form.addRow("功能", self.operation_combo)

        self.operation_stack = QStackedWidget()
        self.operation_stack.addWidget(self._build_compress_page())
        self.operation_stack.addWidget(self._build_convert_page())
        self.operation_stack.addWidget(self._build_trim_page())
        self.operation_stack.addWidget(self._build_resize_page())
        self.operation_stack.addWidget(self._build_audio_page())

        self.operation_tip_label = QLabel()
        self.operation_tip_label.setWordWrap(True)
        self.operation_tip_label.setObjectName("supportingLabel")

        layout.addLayout(top_form)
        layout.addWidget(self.operation_stack)
        layout.addWidget(self.operation_tip_label)
        return group

    def _build_compress_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)

        self.compress_preset_combo = QComboBox()
        self.compress_preset_combo.addItem("高质量", VideoCompressionPreset.HIGH_QUALITY)
        self.compress_preset_combo.addItem("平衡", VideoCompressionPreset.BALANCED)
        self.compress_preset_combo.addItem("高压缩", VideoCompressionPreset.HIGH_COMPRESSION)

        form.addRow("压缩预设", self.compress_preset_combo)
        return page

    def _build_convert_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)

        self.convert_format_combo = QComboBox()
        for target in VideoContainerFormat:
            self.convert_format_combo.addItem(target.value.upper(), target)
        form.addRow("目标格式", self.convert_format_combo)
        return page

    def _build_trim_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)

        self.trim_start_edit = QLineEdit()
        self.trim_start_edit.setPlaceholderText("00:00:05")
        self.trim_end_edit = QLineEdit()
        self.trim_end_edit.setPlaceholderText("00:00:30")

        form.addRow("开始时间", self.trim_start_edit)
        form.addRow("结束时间", self.trim_end_edit)
        return page

    def _build_resize_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)

        self.resize_preset_combo = QComboBox()
        for label, size in self.resize_presets.items():
            self.resize_preset_combo.addItem(label, size)
        self.resize_preset_combo.currentIndexChanged.connect(self._apply_resize_preset)

        self.resize_width_spin = QSpinBox()
        self.resize_width_spin.setRange(0, 8192)
        self.resize_width_spin.setValue(1280)
        self.resize_height_spin = QSpinBox()
        self.resize_height_spin.setRange(0, 8192)
        self.resize_height_spin.setValue(720)
        self.resize_keep_aspect_checkbox = QCheckBox("保持原始比例")
        self.resize_keep_aspect_checkbox.setChecked(True)

        form.addRow("尺寸预设", self.resize_preset_combo)
        form.addRow("宽度", self.resize_width_spin)
        form.addRow("高度", self.resize_height_spin)
        form.addRow("比例", self.resize_keep_aspect_checkbox)
        return page

    def _build_audio_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)

        self.audio_format_combo = QComboBox()
        self.audio_format_combo.addItem("MP3", AudioExportFormat.MP3)
        self.audio_format_combo.addItem("WAV", AudioExportFormat.WAV)
        self.audio_format_combo.addItem("AAC", AudioExportFormat.AAC)
        form.addRow("音频格式", self.audio_format_combo)
        return page

    def _build_metadata_group(self) -> QGroupBox:
        group = QGroupBox("3. 视频信息")
        layout = QFormLayout(group)

        self.meta_name_label = QLabel("-")
        self.meta_duration_label = QLabel("-")
        self.meta_resolution_label = QLabel("-")
        self.meta_status_label = QLabel("请先导入视频")
        self.meta_status_label.setWordWrap(True)

        layout.addRow("文件", self.meta_name_label)
        layout.addRow("时长", self.meta_duration_label)
        layout.addRow("分辨率", self.meta_resolution_label)
        layout.addRow("状态", self.meta_status_label)
        return group

    def _build_output_group(self) -> QGroupBox:
        group = QGroupBox("4. 输出与执行")
        layout = QGridLayout(group)

        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setReadOnly(True)
        self.output_dir_button = QPushButton("选择导出目录")
        self.output_dir_button.clicked.connect(self._choose_output_dir)
        self.preserve_structure_checkbox = QCheckBox("导出时保持原文件夹结构")
        self.preserve_structure_checkbox.setChecked(True)
        self.output_note_label = QLabel("如未设置导出目录，会自动生成 video_output 文件夹。")
        self.output_note_label.setWordWrap(True)
        self.output_note_label.setObjectName("supportingLabel")

        self.run_button = QPushButton("开始批量处理")
        self.run_button.setObjectName("primaryRunButton")
        self.run_button.clicked.connect(self._run_batch)

        layout.addWidget(QLabel("导出目录"), 0, 0)
        layout.addWidget(self.output_dir_edit, 0, 1)
        layout.addWidget(self.output_dir_button, 0, 2)
        layout.addWidget(self.preserve_structure_checkbox, 1, 0, 1, 3)
        layout.addWidget(self.output_note_label, 2, 0, 1, 3)
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

    def _handle_operation_change(self, row: int) -> None:
        self.operation_stack.setCurrentIndex(max(0, row))
        tips = {
            VideoOperationType.COMPRESS: "输出 MP4，提供高质量、平衡和高压缩三档预设。",
            VideoOperationType.CONVERT: "可在 MP4 / MOV / MKV / AVI / WEBM 之间转格式。",
            VideoOperationType.TRIM: "使用 HH:MM:SS 或 HH:MM:SS.mmm 输入开始和结束时间，至少填写一个。",
            VideoOperationType.RESIZE: "支持常用尺寸预设与自定义宽高，默认保持原始比例。",
            VideoOperationType.EXTRACT_AUDIO: "从视频中提取音频，输出 MP3 / WAV / AAC。",
        }
        self.operation_tip_label.setText(tips[self.current_operation_type()])

    def _apply_resize_preset(self) -> None:
        width, height = self.resize_preset_combo.currentData()
        if width and height:
            self.resize_width_spin.setValue(width)
            self.resize_height_spin.setValue(height)

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
            #videoTable {
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

    def _choose_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择视频",
            "",
            "Videos (*.mp4 *.mov *.mkv *.avi *.webm *.m4v)",
        )
        if files:
            self._load_videos(files)

    def _choose_folders(self) -> None:
        dialog = QFileDialog(self, "选择一个或多个视频文件夹")
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setOption(QFileDialog.Option.ShowDirsOnly, True)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        for view in dialog.findChildren((QListView, QTreeView)):
            view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        if dialog.exec():
            folders = dialog.selectedFiles()
            if folders:
                self._load_videos(folders)

    def _clear_videos(self) -> None:
        self.items.clear()
        self.video_table.setRowCount(0)
        self.progress_bar.setValue(0)
        self.summary_label.setText("已清空视频列表")
        self._refresh_selected_metadata()

    def _choose_output_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择导出目录")
        if folder:
            self.output_directory = Path(folder)
            self.output_dir_edit.setText(folder)

    def _load_videos(self, raw_paths: list[str]) -> None:
        collected_videos = collect_videos(raw_paths)
        if not collected_videos:
            QMessageBox.warning(self, "没有可用视频", "未找到支持的视频文件。")
            return

        existing = {item.source_path for item in self.items}
        new_items: list[VideoItem] = []
        for collected in collected_videos:
            if collected.source_path in existing:
                continue
            try:
                video_item = self.processor.get_video_metadata(collected.source_path)
                video_item.import_root = collected.import_root
            except Exception as exc:  # noqa: BLE001
                video_item = VideoItem(source_path=collected.source_path, import_root=collected.import_root)
                video_item.status = "读取失败"
                video_item.message = str(exc)
            new_items.append(video_item)

        if not new_items:
            QMessageBox.information(self, "重复导入", "这些视频已经在列表中了。")
            return

        self.items.extend(new_items)
        self._rebuild_table()
        self.summary_label.setText(f"已载入 {len(self.items)} 个视频")
        if self.video_table.rowCount() > 0 and self.video_table.currentRow() < 0:
            self.video_table.selectRow(0)
        self._refresh_selected_metadata()

    def _rebuild_table(self) -> None:
        self.video_table.setRowCount(len(self.items))
        for row, item in enumerate(self.items):
            name_item = QTableWidgetItem(item.display_name)
            name_item.setToolTip(str(item.source_path))
            self.video_table.setItem(row, 0, name_item)

            root_text = str(item.import_root or item.source_path.parent)
            root_item = QTableWidgetItem(root_text)
            root_item.setToolTip(root_text)
            self.video_table.setItem(row, 1, root_item)
            self.video_table.setItem(row, 2, QTableWidgetItem(item.duration_text))
            self.video_table.setItem(row, 3, QTableWidgetItem(item.resolution_text))
            self.video_table.setItem(row, 4, QTableWidgetItem(item.status))

            message_item = QTableWidgetItem(item.message)
            message_item.setToolTip(item.message)
            self.video_table.setItem(row, 5, message_item)

    def _refresh_selected_metadata(self) -> None:
        item = self._selected_item()
        if item is None:
            self.meta_name_label.setText("-")
            self.meta_duration_label.setText("-")
            self.meta_resolution_label.setText("-")
            self.meta_status_label.setText("请先导入并选择一个视频")
            return

        self.meta_name_label.setText(item.display_name)
        self.meta_duration_label.setText(item.duration_text)
        self.meta_resolution_label.setText(item.resolution_text)
        status_text = item.status if item.status != "待处理" or not item.message else "待处理"
        if item.message:
            status_text = f"{status_text} - {item.message}"
        self.meta_status_label.setText(status_text)

    def current_operation_type(self) -> VideoOperationType:
        current = self.operation_combo.currentData()
        if isinstance(current, VideoOperationType):
            return current
        return VideoOperationType(str(current or VideoOperationType.COMPRESS.value))

    def current_config(self) -> VideoBatchConfig:
        operation_type = self.current_operation_type()
        suffix_map = {
            VideoOperationType.COMPRESS: "_compressed",
            VideoOperationType.CONVERT: "_converted",
            VideoOperationType.TRIM: "_trimmed",
            VideoOperationType.RESIZE: "_resized",
            VideoOperationType.EXTRACT_AUDIO: "_audio",
        }
        return VideoBatchConfig(
            input_files=[item.source_path for item in self.items],
            operation_type=operation_type,
            output_directory=self.output_directory,
            output_suffix=suffix_map[operation_type],
            preserve_structure=self.preserve_structure_checkbox.isChecked(),
            source_roots={item.source_path: item.import_root for item in self.items},
            compression=VideoCompressionSettings(
                preset=self.current_compression_preset(),
                target_format=VideoContainerFormat.MP4,
            ),
            conversion=VideoConversionSettings(target_format=self.current_conversion_format()),
            trim=VideoTrimSettings(
                start_time=self.trim_start_edit.text().strip(),
                end_time=self.trim_end_edit.text().strip(),
            ),
            resize=VideoResizeSettings(
                width=self.resize_width_spin.value(),
                height=self.resize_height_spin.value(),
                keep_aspect_ratio=self.resize_keep_aspect_checkbox.isChecked(),
            ),
            audio_extract=AudioExtractSettings(target_format=self.current_audio_format()),
        )

    def current_compression_preset(self) -> VideoCompressionPreset:
        current = self.compress_preset_combo.currentData()
        if isinstance(current, VideoCompressionPreset):
            return current
        return VideoCompressionPreset(str(current or VideoCompressionPreset.BALANCED.value))

    def current_conversion_format(self) -> VideoContainerFormat:
        current = self.convert_format_combo.currentData()
        if isinstance(current, VideoContainerFormat):
            return current
        return VideoContainerFormat(str(current or VideoContainerFormat.MP4.value))

    def current_audio_format(self) -> AudioExportFormat:
        current = self.audio_format_combo.currentData()
        if isinstance(current, AudioExportFormat):
            return current
        return AudioExportFormat(str(current or AudioExportFormat.MP3.value))

    def _run_batch(self) -> None:
        if not self.items:
            QMessageBox.warning(self, "缺少视频", "请先导入视频。")
            return

        config = self.current_config()
        if config.output_directory is None:
            suggested = self.processor.resolve_output_directory(config)
            self.output_directory = suggested
            self.output_dir_edit.setText(str(suggested))
            config.output_directory = suggested
        progress = QProgressDialog("正在处理视频...", "取消", 0, len(config.input_files), self)
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
        self._rebuild_table()
        self._open_output_directory(output_directory)

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
        self._refresh_selected_metadata()

    def _show_video_menu(self, pos) -> None:  # noqa: ANN001
        row = self.video_table.indexAt(pos).row()
        if row < 0:
            return
        menu = QMenu(self)
        remove_action = menu.addAction("移除选中视频")
        remove_action.triggered.connect(lambda: self._remove_row(row))
        menu.exec(self.video_table.viewport().mapToGlobal(pos))

    def _remove_row(self, row: int) -> None:
        if 0 <= row < len(self.items):
            self.items.pop(row)
            self._rebuild_table()
            if self.items:
                self.video_table.selectRow(min(row, len(self.items) - 1))
            else:
                self.summary_label.setText("视频列表已清空")
            self._refresh_selected_metadata()

    def _selected_item(self) -> VideoItem | None:
        row = self.video_table.currentRow()
        if 0 <= row < len(self.items):
            return self.items[row]
        if self.items:
            return self.items[0]
        return None

    def _open_output_directory(self, output_directory: Path) -> None:
        if not output_directory.exists():
            return
        try:
            os.startfile(str(output_directory))
        except OSError:
            pass
