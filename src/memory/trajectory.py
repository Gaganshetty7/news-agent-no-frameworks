import json
import time
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Trajectory:
    """
    Complete record of one agent run.

    Stores every Step the agent took plus the raw LLM output
    per iteration — so you can replay or debug any run exactly.
    """

    task: str
    # default_factory used to create fresh list per instance else the list would be shared across objects.
    steps: list = field(default_factory=list)
    raw_turns: list[dict] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)

    # ── writing ────────────────────────────────────────────────────────

    def add_step(self, step) -> None:
        self.steps.append(step)

    def add_raw(self, iteration: int, text: str) -> None:
        self.raw_turns.append({"iteration": iteration, "text": text})

    # ── reading ────────────────────────────────────────────────────────

    def thoughts(self) -> list:
        from src.core.parser import StepType
        return [s for s in self.steps if s.type == StepType.THOUGHT]

    def actions(self) -> list:
        from src.core.parser import StepType
        return [s for s in self.steps if s.type == StepType.ACTION]

    def observations(self) -> list:
        from src.core.parser import StepType
        return [s for s in self.steps if s.type == StepType.OBSERVATION]

    # ── output ─────────────────────────────────────────────────────────

    def pretty_print(self) -> str:
        from src.core.parser import StepType

        icons = {
            StepType.THOUGHT:      "💭",
            StepType.ACTION:       "⚡",
            StepType.OBSERVATION:  "👁️ ",
            StepType.FINAL_ANSWER: "✅",
        }
        lines = [
            f"{'='*60}",
            f"TRAJECTORY — {self.task}",
            f"{'='*60}",
        ]
        for i, step in enumerate(self.steps, 1):
            icon = icons.get(step.type, "•")
            lines.append(f"\n[{i:02d}] {icon}  {step.type.value.upper()}")
            if step.type.value == "action":
                lines.append(f"      tool  : {step.tool}")
                lines.append(f"      input : {step.tool_input}")
            else:
                content = step.content
                if len(content) > 400:
                    content = content[:400] + "..."
                lines.append(f"      {content}")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "started_at": self.started_at,
            "total_steps": len(self.steps),
            "steps": [self._step_to_dict(s) for s in self.steps],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())
        logger.info(f"Trajectory saved to {path}")

    # ── private ────────────────────────────────────────────────────────

    def _step_to_dict(self, step) -> dict:
        d = {
            "type": step.type.value,
            "content": step.content,
        }
        if step.tool:
            d["tool"] = step.tool
        if step.tool_input is not None:
            d["tool_input"] = step.tool_input
        return d
