from __future__ import annotations

from logo_toolkit.core.models import VideoOperationType
from logo_toolkit.tools.base import ToolDefinition
from logo_toolkit.tools.batch_transform_tool import BatchTransformToolWidget
from logo_toolkit.tools.logo_tool import BatchLogoToolWidget
from logo_toolkit.tools.video_frame_tool import BatchVideoFrameToolWidget
from logo_toolkit.tools.video_tool import BatchVideoToolWidget


VIDEO_WORKFLOW_OPERATIONS = [
    VideoOperationType.COMPRESS,
    VideoOperationType.CONVERT,
    VideoOperationType.TRIM,
    VideoOperationType.RESIZE,
    VideoOperationType.EXTRACT_AUDIO,
]


def build_tool_registry() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            tool_id="batch_transform",
            title="批量处理图片",
            description="批量完成转格式、压缩和改尺寸，适合做基础图片整理。",
            factory=BatchTransformToolWidget,
        ),
        ToolDefinition(
            tool_id="batch_logo",
            title="批量加 Logo",
            description="给整批图片统一叠加一个可交互定位的 Logo。",
            factory=BatchLogoToolWidget,
        ),
        ToolDefinition(
            tool_id="batch_video",
            title="批量视频处理",
            description="批量压缩、转格式、裁剪、改尺寸并提取音频。",
            factory=lambda: BatchVideoToolWidget(available_operations=VIDEO_WORKFLOW_OPERATIONS),
        ),
        ToolDefinition(
            tool_id="batch_video_logo",
            title="批量视频加 Logo",
            description="给整批视频统一叠加一个可交互定位的 Logo。",
            factory=lambda: BatchVideoToolWidget(available_operations=[VideoOperationType.ADD_LOGO]),
        ),
        ToolDefinition(
            tool_id="batch_video_endcard",
            title="批量加 EC",
            description="给整批视频统一叠加透明 MOV 结尾视频，并自动处理尾部重叠和音频过渡。",
            factory=lambda: BatchVideoToolWidget(available_operations=[VideoOperationType.ADD_ENDCARD]),
        ),
        ToolDefinition(
            tool_id="batch_video_frame",
            title="视频套边框",
            description="把视频叠到边框图片上，批量生成 16:9、1:1、9:16 等尺寸版本。",
            factory=BatchVideoFrameToolWidget,
        ),
    ]
