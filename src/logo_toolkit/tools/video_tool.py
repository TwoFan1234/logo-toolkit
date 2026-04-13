from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
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
from logo_toolkit.core.image_processor import ImageProcessor
from logo_toolkit.core.models import (
    AudioExportFormat,
    AudioExtractSettings,
    LOGO_ANCHOR_LABELS,
    PixelLogoPlacement,
    RenderOptions,
    VideoBatchConfig,
    VideoCompressionPreset,
    VideoCompressionSettings,
    VideoContainerFormat,
    VideoConversionSettings,
    VideoItem,
    VideoLogoSettings,
    VideoOperationType,
    VideoResizeSettings,
    VideoTrimSettings,
)
from logo_toolkit.core.video_processor import VideoProcessor
from logo_toolkit.ui.selection_helpers import build_check_item, populate_ratio_filter_combo, ratio_matches
from logo_toolkit.ui.theme import configure_resizable_splitter, toolkit_tool_stylesheet
from logo_toolkit.ui.video_logo_preview_canvas import VideoLogoPreviewCanvas


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


class VideoLogoPreviewDialog(QDialog):
    def __init__(
        self,
        frame_path: Path,
        logo_path: Path,
        placement: PixelLogoPlacement,
        keep_aspect_ratio: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("视频 Logo 预览校准")
        self.resize(920, 680)
        self.placement = placement.normalized()
        self.keep_aspect_ratio = keep_aspect_ratio

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        tip = QLabel("拖动 Logo 调整位置，拖动右下角控制点缩放大小。工具会自动识别它更靠近哪个角，并记录对应的像素边距。")
        tip.setWordWrap(True)

        self.preview_canvas = VideoLogoPreviewCanvas()
        self.preview_canvas.set_images(
            frame_path,
            logo_path,
            self.placement,
            keep_aspect_ratio=self.keep_aspect_ratio,
        )
        self.preview_canvas.placement_changed.connect(self._handle_placement_change)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(tip)
        layout.addWidget(self.preview_canvas, stretch=1)
        layout.addWidget(buttons)

    def _handle_placement_change(self, margin_x_px: int, margin_y_px: int, width_px: int, anchor: str) -> None:
        self.placement = PixelLogoPlacement(
            margin_x_px=margin_x_px,
            margin_y_px=margin_y_px,
            width_px=width_px,
            anchor=anchor,
        ).normalized()


class BatchVideoToolWidget(QWidget):
    DEFAULT_OPERATIONS = [
        VideoOperationType.COMPRESS,
        VideoOperationType.CONVERT,
        VideoOperationType.TRIM,
        VideoOperationType.RESIZE,
        VideoOperationType.EXTRACT_AUDIO,
    ]

    def __init__(
        self,
        parent: QWidget | None = None,
        available_operations: list[VideoOperationType] | None = None,
    ) -> None:
        super().__init__(parent)
        self.processor = VideoProcessor()
        self.image_processor = ImageProcessor()
        self.items: list[VideoItem] = []
        self.output_directory: Path | None = None
        self.logo_path: Path | None = None
        self.logo_pixel_placement = PixelLogoPlacement(margin_x_px=40, margin_y_px=40, width_px=220, anchor="bottom_right")
        self.logo_render_options = RenderOptions()
        self.available_operations = list(available_operations or self.DEFAULT_OPERATIONS)
        self._table_syncing = False
        if not self.available_operations:
            raise ValueError("至少需要提供一个视频处理模式。")
        self.logo_only_mode = self.available_operations == [VideoOperationType.ADD_LOGO]
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

        output_panel = QWidget()
        output_layout = QVBoxLayout(output_panel)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.setSpacing(10)

        if self.logo_only_mode:
            operation_layout.addWidget(self._build_operation_group(), stretch=1)
            output_layout.addWidget(self._build_logo_settings_group())
            output_layout.addWidget(self._build_metadata_group())
            output_layout.addWidget(self._build_output_group())
            output_layout.addWidget(self._build_progress_group())
            output_layout.addStretch(1)
        else:
            operation_layout.addWidget(self._build_operation_group())
            operation_layout.addWidget(self._build_metadata_group())
            operation_layout.addStretch(1)
            output_layout.addWidget(self._build_output_group())
            output_layout.addWidget(self._build_progress_group())
            output_layout.addStretch(1)

        splitter.addWidget(import_panel)
        splitter.addWidget(operation_panel)
        splitter.addWidget(output_panel)
        if self.logo_only_mode:
            configure_resizable_splitter(
                splitter,
                [import_panel, operation_panel, output_panel],
                stretches=[2, 3, 2],
                minimum_widths=[220, 260, 220],
                initial_sizes=[520, 720, 280],
            )
        else:
            configure_resizable_splitter(
                splitter,
                [import_panel, operation_panel, output_panel],
                stretches=[3, 2, 2],
                minimum_widths=[240, 220, 220],
                initial_sizes=[700, 380, 260],
            )

        self._apply_styles()
        self._handle_operation_change(0)
        self._refresh_selected_metadata()
        self._update_logo_pixel_controls()

    def _build_import_group(self) -> QGroupBox:
        group = VideoImportGroupBox("1. 视频导入")
        group.paths_dropped.connect(self._load_videos)
        layout = QVBoxLayout(group)

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        add_files_button = QPushButton("添加视频")
        add_files_button.clicked.connect(self._choose_files)
        add_folder_button = QPushButton("导入文件夹")
        add_folder_button.clicked.connect(self._choose_folders)
        clear_button = QPushButton("清空")
        clear_button.clicked.connect(self._clear_videos)
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

        self.video_table = VideoTableWidget()
        self.video_table.setColumnCount(8)
        self.video_table.setHorizontalHeaderLabels(["执行", "文件名", "导入根目录", "时长", "分辨率", "比例", "状态", "说明"])
        self.video_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.video_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.video_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.video_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.video_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.video_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.video_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.video_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        self.video_table.verticalHeader().setVisible(False)
        self.video_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.video_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.video_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.video_table.setAlternatingRowColors(True)
        self.video_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.video_table.customContextMenuRequested.connect(self._show_video_menu)
        self.video_table.itemSelectionChanged.connect(self._refresh_selected_metadata)
        self.video_table.itemChanged.connect(self._handle_table_item_changed)
        self.video_table.paths_dropped.connect(self._load_videos)
        self.video_table.setMinimumHeight(420)
        self.video_table.setObjectName("videoTable")

        hint = QLabel("支持拖入多个视频文件或文件夹，工具会自动递归读取视频文件。")
        hint.setWordWrap(True)
        hint.setObjectName("supportingLabel")

        layout.addLayout(buttons_layout)
        layout.addLayout(ratio_layout)
        layout.addLayout(action_layout)
        layout.addWidget(hint)
        layout.addWidget(self.video_table, stretch=1)
        return group

    def _build_operation_group(self) -> QGroupBox:
        group_title = "3. 预览校准" if self.logo_only_mode else "2. 处理模式"
        group = QGroupBox(group_title)
        layout = QVBoxLayout(group)

        self.operation_combo = QComboBox()
        page_builders = {
            VideoOperationType.COMPRESS: self._build_compress_page,
            VideoOperationType.CONVERT: self._build_convert_page,
            VideoOperationType.TRIM: self._build_trim_page,
            VideoOperationType.RESIZE: self._build_resize_page,
            VideoOperationType.EXTRACT_AUDIO: self._build_audio_page,
            VideoOperationType.ADD_LOGO: self._build_logo_page,
        }
        for operation in self.available_operations:
            self.operation_combo.addItem(self._operation_label(operation), operation)
        self.operation_combo.currentIndexChanged.connect(self._handle_operation_change)

        self.operation_stack = QStackedWidget()
        for operation in self.available_operations:
            self.operation_stack.addWidget(page_builders[operation]())

        self.operation_tip_label = QLabel()
        self.operation_tip_label.setWordWrap(True)
        self.operation_tip_label.setObjectName("supportingLabel")

        if self.logo_only_mode:
            layout.addWidget(self.operation_stack, stretch=1)
        else:
            top_form = QFormLayout()
            if len(self.available_operations) == 1:
                top_form.addRow("功能", QLabel(self._operation_label(self.available_operations[0])))
            else:
                top_form.addRow("功能", self.operation_combo)
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

    def _build_logo_controls_layout(self, layout: QVBoxLayout) -> None:
        button_row = QHBoxLayout()
        choose_logo_button = QPushButton("选择 Logo")
        choose_logo_button.clicked.connect(self._choose_logo)
        self.logo_path_edit = QLineEdit()
        self.logo_path_edit.setReadOnly(True)
        button_row.addWidget(choose_logo_button)
        button_row.addWidget(self.logo_path_edit)

        form = QFormLayout()
        self.logo_corner_label = QLabel(LOGO_ANCHOR_LABELS[self.logo_pixel_placement.anchor])
        self.logo_x_spin = QSpinBox()
        self.logo_x_spin.setRange(0, 8192)
        self.logo_x_spin.setSuffix(" px")
        self.logo_y_spin = QSpinBox()
        self.logo_y_spin.setRange(0, 8192)
        self.logo_y_spin.setSuffix(" px")
        self.logo_size_spin = QSpinBox()
        self.logo_size_spin.setRange(1, 8192)
        self.logo_size_spin.setSuffix(" px")
        self.logo_keep_ratio_checkbox = QCheckBox("保持 Logo 原比例")
        self.logo_keep_ratio_checkbox.setChecked(True)
        self.logo_keep_ratio_checkbox.setEnabled(False)
        self.logo_keep_ratio_checkbox.setToolTip("v1 固定保持原比例，避免 logo 变形")

        self.logo_x_spin.valueChanged.connect(self._logo_pixel_spinbox_changed)
        self.logo_y_spin.valueChanged.connect(self._logo_pixel_spinbox_changed)
        self.logo_size_spin.valueChanged.connect(self._logo_pixel_spinbox_changed)

        form.addRow("自动靠近角", self.logo_corner_label)
        form.addRow("水平边距", self.logo_x_spin)
        form.addRow("垂直边距", self.logo_y_spin)
        form.addRow("Logo 宽度", self.logo_size_spin)
        form.addRow("渲染方式", self.logo_keep_ratio_checkbox)

        layout.addLayout(button_row)
        layout.addLayout(form)

    def _build_logo_preview_layout(self, layout: QVBoxLayout) -> None:
        self.logo_preview_status_label = QLabel("请选择一条视频和一张 Logo，即可直接在下方预览区校准。")
        self.logo_preview_status_label.setWordWrap(True)
        self.logo_preview_status_label.setObjectName("supportingLabel")

        self.logo_preview_canvas = VideoLogoPreviewCanvas()
        self.logo_preview_canvas.setMinimumHeight(300)
        self.logo_preview_canvas.placement_changed.connect(self._handle_logo_canvas_change)

        layout.addWidget(self.logo_preview_status_label)
        layout.addWidget(self.logo_preview_canvas, stretch=1)

    def _build_logo_settings_group(self) -> QGroupBox:
        group = QGroupBox("2. Logo 设置")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)
        self._build_logo_controls_layout(layout)
        return group

    def _build_logo_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self._build_logo_preview_layout(layout)
        return page

    def _build_metadata_group(self) -> QGroupBox:
        title = "当前视频" if self.logo_only_mode else "3. 视频信息"
        group = QGroupBox(title)
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
        self.preserve_structure_checkbox.setChecked(False)
        self.output_note_label = QLabel(
            "如未设置导出目录，会自动生成 video_output 文件夹。"
        )
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

    def _operation_label(self, operation: VideoOperationType) -> str:
        labels = {
            VideoOperationType.COMPRESS: "视频压缩",
            VideoOperationType.CONVERT: "视频转格式",
            VideoOperationType.TRIM: "视频时长裁剪",
            VideoOperationType.RESIZE: "视频改尺寸",
            VideoOperationType.EXTRACT_AUDIO: "视频提取音频",
            VideoOperationType.ADD_LOGO: "批量添加 Logo",
        }
        return labels[operation]

    def _output_note_text(self, operation: VideoOperationType) -> str:
        if operation == VideoOperationType.ADD_LOGO:
            return "如未设置导出目录，会自动生成 video_output 文件夹。批量添加 Logo 默认保持原视频文件名。"
        if operation == VideoOperationType.EXTRACT_AUDIO:
            return "如未设置导出目录，会自动生成 video_output 文件夹。提取音频时会按所选格式导出。"
        return "如未设置导出目录，会自动生成 video_output 文件夹。"

    def _handle_operation_change(self, row: int) -> None:
        self.operation_stack.setCurrentIndex(max(0, row))
        tips = {
            VideoOperationType.COMPRESS: "输出 MP4，提供高质量、平衡和高压缩三档预设。",
            VideoOperationType.CONVERT: "可在 MP4 / MOV / MKV / AVI / WEBM 之间转换格式。",
            VideoOperationType.TRIM: "使用 HH:MM:SS 或 HH:MM:SS.mmm 输入开始和结束时间，至少填写一个。",
            VideoOperationType.RESIZE: "支持常用尺寸预设与自定义宽高，默认保持原始比例。",
            VideoOperationType.EXTRACT_AUDIO: "从视频中提取音频，输出 MP3 / WAV / AAC。",
            VideoOperationType.ADD_LOGO: "先选择一张 Logo，再直接在主界面预览区定位。导出时会批量叠加到所有视频上。",
        }
        operation = self.current_operation_type()
        self.operation_tip_label.setText(tips[operation])
        self.output_note_label.setText(self._output_note_text(operation))

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
        self.setStyleSheet(toolkit_tool_stylesheet())

    def _create_ratio_spinbox(self, value: float, minimum: float = 0.0) -> QDoubleSpinBox:
        spinbox = QDoubleSpinBox()
        spinbox.setDecimals(2)
        spinbox.setRange(minimum, 100.0)
        spinbox.setSuffix(" %")
        spinbox.setValue(value * 100)
        return spinbox

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
        self._update_logo_pixel_controls()
        self._refresh_logo_preview()

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
        self.summary_label.setText(f"已载入 {len(self.items)} 个视频，当前勾选 {len(self._checked_items())} 个")
        if self.video_table.rowCount() > 0 and self.video_table.currentRow() < 0:
            self.video_table.selectRow(0)
        self._refresh_selected_metadata()

    def _rebuild_table(self) -> None:
        self._table_syncing = True
        self.video_table.setRowCount(len(self.items))
        for row, item in enumerate(self.items):
            self.video_table.setItem(row, 0, build_check_item(item.selected_for_batch))
            name_item = QTableWidgetItem(item.display_name)
            name_item.setToolTip(str(item.source_path))
            self.video_table.setItem(row, 1, name_item)

            root_text = str(item.import_root or item.source_path.parent)
            root_item = QTableWidgetItem(root_text)
            root_item.setToolTip(root_text)
            self.video_table.setItem(row, 2, root_item)
            self.video_table.setItem(row, 3, QTableWidgetItem(item.duration_text))
            self.video_table.setItem(row, 4, QTableWidgetItem(item.resolution_text))
            self.video_table.setItem(row, 5, QTableWidgetItem(item.ratio_text))
            self.video_table.setItem(row, 6, QTableWidgetItem(item.status))

            message_item = QTableWidgetItem(item.message)
            message_item.setToolTip(item.message)
            self.video_table.setItem(row, 7, message_item)
        self._table_syncing = False

    def _handle_table_item_changed(self, table_item: QTableWidgetItem) -> None:
        if self._table_syncing or table_item.column() != 0:
            return
        row = table_item.row()
        if 0 <= row < len(self.items):
            self.items[row].selected_for_batch = table_item.checkState() == Qt.CheckState.Checked

    def _checked_items(self) -> list[VideoItem]:
        return [item for item in self.items if item.selected_for_batch]

    def _set_all_items_checked(self, checked: bool) -> None:
        for item in self.items:
            item.selected_for_batch = checked
        self._rebuild_table()
        self.summary_label.setText(f"已勾选 {len(self._checked_items())}/{len(self.items)} 个视频")

    def _apply_ratio_filter_selection(self) -> None:
        ratio_filter = str(self.ratio_filter_combo.currentData() or "all")
        for item in self.items:
            item.selected_for_batch = ratio_matches(item.width, item.height, ratio_filter)
        self._rebuild_table()
        self.summary_label.setText(f"已按 {self.ratio_filter_combo.currentText()} 勾选 {len(self._checked_items())} 个视频")

    def _remove_selected_rows(self) -> None:
        rows = sorted({index.row() for index in self.video_table.selectionModel().selectedRows()}, reverse=True)
        if not rows:
            QMessageBox.information(self, "未选择素材", "请先在列表里选中要移除的视频。")
            return
        for row in rows:
            if 0 <= row < len(self.items):
                self.items.pop(row)
        self._rebuild_table()
        if self.items:
            self.video_table.selectRow(min(rows[-1], len(self.items) - 1))
            self.summary_label.setText(f"已移除 {len(rows)} 个视频，剩余 {len(self.items)} 个")
        else:
            self.summary_label.setText("视频列表已清空")
        self._refresh_selected_metadata()

    def _refresh_selected_metadata(self) -> None:
        item = self._selected_item()
        if item is None:
            self.meta_name_label.setText("-")
            self.meta_duration_label.setText("-")
            self.meta_resolution_label.setText("-")
            self.meta_status_label.setText("请先导入并选择一个视频")
            self._refresh_logo_preview()
            return

        self.meta_name_label.setText(item.display_name)
        self.meta_duration_label.setText(item.duration_text)
        self.meta_resolution_label.setText(item.resolution_text)
        status_text = item.status
        if item.message:
            status_text = f"{status_text} - {item.message}"
        self.meta_status_label.setText(status_text)
        self._update_logo_pixel_controls()
        self._refresh_logo_preview()

    def current_operation_type(self) -> VideoOperationType:
        current = self.operation_combo.currentData()
        if isinstance(current, VideoOperationType):
            return current
        return VideoOperationType(str(current or VideoOperationType.COMPRESS.value))

    def current_config(self, only_checked: bool = False) -> VideoBatchConfig:
        operation_type = self.current_operation_type()
        selected_items = self._checked_items() if only_checked else self.items
        suffix_map = {
            VideoOperationType.COMPRESS: "",
            VideoOperationType.CONVERT: "",
            VideoOperationType.TRIM: "",
            VideoOperationType.RESIZE: "",
            VideoOperationType.EXTRACT_AUDIO: "",
            VideoOperationType.ADD_LOGO: "",
        }
        trim_settings = VideoTrimSettings(
            start_time=self.trim_start_edit.text().strip() if hasattr(self, "trim_start_edit") else "",
            end_time=self.trim_end_edit.text().strip() if hasattr(self, "trim_end_edit") else "",
        )
        resize_settings = VideoResizeSettings(
            width=self.resize_width_spin.value() if hasattr(self, "resize_width_spin") else 1280,
            height=self.resize_height_spin.value() if hasattr(self, "resize_height_spin") else 720,
            keep_aspect_ratio=(
                self.resize_keep_aspect_checkbox.isChecked()
                if hasattr(self, "resize_keep_aspect_checkbox")
                else True
            ),
        )
        return VideoBatchConfig(
            input_files=[item.source_path for item in selected_items],
            operation_type=operation_type,
            output_directory=self.output_directory,
            output_suffix=suffix_map[operation_type],
            preserve_structure=self.preserve_structure_checkbox.isChecked(),
            source_roots={item.source_path: item.import_root for item in selected_items},
            compression=VideoCompressionSettings(
                preset=self.current_compression_preset(),
                target_format=VideoContainerFormat.MP4,
            ),
            conversion=VideoConversionSettings(target_format=self.current_conversion_format()),
            trim=trim_settings,
            resize=resize_settings,
            audio_extract=AudioExtractSettings(target_format=self.current_audio_format()),
            logo_overlay=VideoLogoSettings(
                logo_file=self.logo_path,
                pixel_placement=self.logo_pixel_placement,
                render_options=self.logo_render_options,
                use_pixel_positioning=True,
            ),
        )

    def current_compression_preset(self) -> VideoCompressionPreset:
        if not hasattr(self, "compress_preset_combo"):
            return VideoCompressionPreset.BALANCED
        current = self.compress_preset_combo.currentData()
        if isinstance(current, VideoCompressionPreset):
            return current
        return VideoCompressionPreset(str(current or VideoCompressionPreset.BALANCED.value))

    def current_conversion_format(self) -> VideoContainerFormat:
        if not hasattr(self, "convert_format_combo"):
            return VideoContainerFormat.MP4
        current = self.convert_format_combo.currentData()
        if isinstance(current, VideoContainerFormat):
            return current
        return VideoContainerFormat(str(current or VideoContainerFormat.MP4.value))

    def current_audio_format(self) -> AudioExportFormat:
        if not hasattr(self, "audio_format_combo"):
            return AudioExportFormat.MP3
        current = self.audio_format_combo.currentData()
        if isinstance(current, AudioExportFormat):
            return current
        return AudioExportFormat(str(current or AudioExportFormat.MP3.value))

    def _selected_item(self) -> VideoItem | None:
        row = self.video_table.currentRow()
        if 0 <= row < len(self.items):
            return self.items[row]
        if self.items:
            return self.items[0]
        return None

    def _selected_dimensions(self) -> tuple[int, int] | None:
        item = self._selected_item()
        if item and item.width and item.height:
            return item.width, item.height
        for candidate in self.items:
            if candidate.width and candidate.height:
                return candidate.width, candidate.height
        return None

    def _logo_dimensions(self) -> tuple[int, int] | None:
        if self.logo_path is None:
            return None
        try:
            return self.image_processor.get_image_size(self.logo_path)
        except Exception:  # noqa: BLE001
            return None

    def _logo_pixel_spinbox_changed(self) -> None:
        self.logo_pixel_placement = PixelLogoPlacement(
            margin_x_px=self.logo_x_spin.value(),
            margin_y_px=self.logo_y_spin.value(),
            width_px=self.logo_size_spin.value(),
            anchor=self.logo_pixel_placement.anchor,
        ).normalized()
        self._update_logo_pixel_controls()

    def _update_logo_pixel_controls(self) -> None:
        if not hasattr(self, "logo_x_spin"):
            return
        self.logo_x_spin.blockSignals(True)
        self.logo_y_spin.blockSignals(True)
        self.logo_size_spin.blockSignals(True)
        self.logo_x_spin.setValue(self.logo_pixel_placement.margin_x_px)
        self.logo_y_spin.setValue(self.logo_pixel_placement.margin_y_px)
        self.logo_size_spin.setValue(self.logo_pixel_placement.width_px)
        self.logo_corner_label.setText(LOGO_ANCHOR_LABELS.get(self.logo_pixel_placement.anchor, "右下角"))
        self.logo_x_spin.blockSignals(False)
        self.logo_y_spin.blockSignals(False)
        self.logo_size_spin.blockSignals(False)
        if hasattr(self, "logo_preview_canvas"):
            self.logo_preview_canvas.set_placement(self.logo_pixel_placement)

    def _handle_logo_canvas_change(self, margin_x_px: int, margin_y_px: int, width_px: int, anchor: str) -> None:
        self.logo_pixel_placement = PixelLogoPlacement(
            margin_x_px=margin_x_px,
            margin_y_px=margin_y_px,
            width_px=width_px,
            anchor=anchor,
        ).normalized()
        self._update_logo_pixel_controls()

    def _refresh_logo_preview(self) -> None:
        if not hasattr(self, "logo_preview_canvas"):
            return
        item = self._selected_item()
        if item is None:
            self.logo_preview_status_label.setText("请选择一条视频和一张 Logo，即可直接在下方预览区校准。")
            self.logo_preview_canvas.set_images(
                None,
                self.logo_path,
                self.logo_pixel_placement,
                keep_aspect_ratio=self.logo_render_options.keep_aspect_ratio,
            )
            return

        timestamp_seconds = min(1.0, max(0.0, (item.duration_seconds or 0.0) / 2.0))
        try:
            frame_path = self.processor.extract_preview_frame(item.source_path, timestamp_seconds=timestamp_seconds)
        except Exception as exc:  # noqa: BLE001
            self.logo_preview_status_label.setText(f"预览生成失败: {exc}")
            self.logo_preview_canvas.set_images(
                None,
                self.logo_path,
                self.logo_pixel_placement,
                keep_aspect_ratio=self.logo_render_options.keep_aspect_ratio,
            )
            return

        if self.logo_path is None:
            self.logo_preview_status_label.setText(f"当前预览: {item.display_name}。选择一张 Logo 后即可直接拖动校准。")
        else:
            self.logo_preview_status_label.setText(f"当前预览: {item.display_name}。拖动 Logo 或修改像素值会立即同步。")
        self.logo_preview_canvas.set_images(
            frame_path,
            self.logo_path,
            self.logo_pixel_placement,
            keep_aspect_ratio=self.logo_render_options.keep_aspect_ratio,
        )

    def _open_logo_preview(self) -> None:
        item = self._selected_item()
        if item is None:
            QMessageBox.information(self, "未选择视频", "请先在左侧列表中选中一个视频。")
            return
        if self.logo_path is None:
            QMessageBox.information(self, "缺少 Logo", "请先选择一张 Logo 图片。")
            return

        timestamp_seconds = min(1.0, max(0.0, (item.duration_seconds or 0.0) / 2.0))
        try:
            frame_path = self.processor.extract_preview_frame(item.source_path, timestamp_seconds=timestamp_seconds)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "生成预览失败", str(exc))
            return

        dialog = VideoLogoPreviewDialog(
            frame_path=frame_path,
            logo_path=self.logo_path,
            placement=self.logo_pixel_placement,
            keep_aspect_ratio=self.logo_render_options.keep_aspect_ratio,
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.logo_pixel_placement = dialog.placement.normalized()
            self._update_logo_pixel_controls()
            self.summary_label.setText("已更新视频 Logo 的位置和大小")

    def _run_batch(self) -> None:
        if not self.items:
            QMessageBox.warning(self, "缺少视频", "请先导入视频。")
            return
        if not self._checked_items():
            QMessageBox.warning(self, "未勾选素材", "请先勾选需要处理的视频。")
            return
        if self.current_operation_type() == VideoOperationType.ADD_LOGO and self.logo_path is None:
            QMessageBox.warning(self, "缺少 Logo", "请先选择一张 Logo 图片。")
            return

        config = self.current_config(only_checked=True)
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
                self.summary_label.setText(f"已移除 1 个视频，剩余 {len(self.items)} 个")
            else:
                self.summary_label.setText("视频列表已清空")
            self._refresh_selected_metadata()

    def _open_output_directory(self, output_directory: Path) -> None:
        if not output_directory.exists():
            return
        try:
            os.startfile(str(output_directory))
        except OSError:
            pass



