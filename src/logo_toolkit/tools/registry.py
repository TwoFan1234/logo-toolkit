from __future__ import annotations

from logo_toolkit.tools.base import ToolDefinition
from logo_toolkit.tools.batch_transform_tool import BatchTransformToolWidget
from logo_toolkit.tools.logo_tool import BatchLogoToolWidget
from logo_toolkit.tools.video_tool import BatchVideoToolWidget


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
            description="给整批图片统一叠加一个可交互定位的 logo。",
            factory=BatchLogoToolWidget,
        ),
        ToolDefinition(
            tool_id="batch_video",
            title="批量视频处理",
            description="批量压缩、转格式、裁剪、改尺寸并提取音频。",
            factory=BatchVideoToolWidget,
        ),
    ]
