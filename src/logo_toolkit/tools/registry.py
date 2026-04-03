from __future__ import annotations

from logo_toolkit.tools.base import ToolDefinition
from logo_toolkit.tools.logo_tool import BatchLogoToolWidget


def build_tool_registry() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            tool_id="batch_logo",
            title="批量加 Logo",
            description="给整批图片统一叠加一个可交互定位的 logo。",
            factory=BatchLogoToolWidget,
        )
    ]
