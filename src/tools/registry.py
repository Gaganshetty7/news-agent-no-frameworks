# This defines the base class every tool must follow, and the registry that holds them all.

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    name: str = ""
    description: str = ""
    skill_path: str = ""
    inject_skill_before: bool = False
    
    @abstractmethod
    def run(self, tool_input: Any) -> str:
        """Execute the tool. Always returns a string (becomes the Observation)."""
        ...

    def load_skill(self) -> str | None:
        """Return skill content if this tool has one, else None."""
        if not self.skill_path:
            return None
        try:
            with open(self.skill_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            logger.warning(f"[Tool:{self.name}] Skill file not found: {self.skill_path}")
            return None
            
    def format_description(self) -> str:
        return f"### {self.name}\n{self.description}"


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> "ToolRegistry":
        if not tool.name:
            raise ValueError(f"{type(tool).__name__} must have a name.")
        if tool.name in self._tools:
            logger.warning(f"Overwriting existing tool: {tool.name!r}")
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name!r}")
        return self  # allows chaining: registry.register(A()).register(B())

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def list_names(self) -> list[str]:
        return list(self._tools.keys())

    def descriptions(self) -> str:
        if not self._tools:
            return "No tools available."
        return "\n\n".join(t.format_description() for t in self._tools.values())

    def __len__(self):
        return len(self._tools)
