from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtWidgets import QWidget


@dataclass(slots=True)
class ToolDefinition:
    tool_id: str
    title: str
    description: str
    factory: Callable[[], QWidget]
