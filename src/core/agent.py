import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .llm import LLMClient
from .parser import ReActParser, StepType
from .prompt import build_system_prompt, build_user_prompt, load_skill
from ..memory.trajectory import Trajectory
from ..tools.registry import ToolRegistry
from ..utils.exceptions import AgentMaxIterationsError, ToolExecutionError

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    IDLE     = "idle"
    RUNNING  = "running"
    FINISHED = "finished"
    FAILED   = "failed"


@dataclass
class AgentConfig:
    max_iterations: int   = 10
    max_retries:    int   = 3
    retry_delay:    float = 1.0
    temperature:    float = 0.0
    verbose:        bool  = True


@dataclass
class AgentResult:
    answer:     str
    trajectory: Trajectory
    iterations: int
    total_time: float
    status:     AgentStatus
    error:      Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "answer":        self.answer,
            "iterations":    self.iterations,
            "total_time":    round(self.total_time, 3),
            "status":        self.status.value,
            "error":         self.error,
            "steps":         [self.trajectory._step_to_dict(s) for s in self.trajectory.steps],
        }


class ReActAgent:
    """
    The ReAct loop:
      1. Build system prompt (tools) + user prompt (task)
      2. Call LLM → parse Thought + Action
      3. Execute tool → get Observation
      4. Append Observation to messages, go to 2
      5. Until LLM writes Final Answer or max_iterations hit
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        llm_client: LLMClient,
        config: Optional[AgentConfig] = None,
    ):
        self.tools  = tool_registry
        self.llm    = llm_client
        self.config = config or AgentConfig()
        self.parser = ReActParser()
        self.status = AgentStatus.IDLE

    # ══════════════════════════════════════════════════════════════════
    # Public API
    # ══════════════════════════════════════════════════════════════════

    def run(self, task: str) -> AgentResult:
        self.status = AgentStatus.RUNNING
        trajectory  = Trajectory(task=task)
        start_time  = time.time()

        self._log(f"\n{'='*60}\nTASK: {task}\n{'='*60}")

        system_prompt   = build_system_prompt(self.tools.descriptions())

        # Inject skills for tools that require it before the loop starts
        upfront_skills = []

        for tool in self.tools._tools.values():
            if tool.inject_skill_before and tool.skill_path:
                content = tool.load_skill()

                if content:
                    upfront_skills.append(
                        f"[Skill: {tool.name}]\n{content}"
                    )

        if upfront_skills:
            system_prompt += (
                "\n\n## Tool Skills\n\n"
                + "\n\n".join(upfront_skills)
            )

        user_prompt     = build_user_prompt(task)
        messages        = [{"role": "user", "content": user_prompt}]
        injected_skills = set()   # track which skills already injected — no duplicates

        no_op_count = 0

        try:
            for iteration in range(1, self.config.max_iterations + 1):
                self._log(f"\n--- Iteration {iteration}/{self.config.max_iterations} ---")

                raw = self._call_llm(messages, system_prompt)
                trajectory.add_raw(iteration, raw)

                steps = self.parser.parse(raw)
                final_answer = None

                for step in steps:
                    trajectory.add_step(step)

                    if step.type == StepType.THOUGHT:
                        self._log(f"\n💭  {step.content}")

                    elif step.type == StepType.ACTION:
                        self._log(f"\n⚡  {step.tool}({step.tool_input})")
                        observation = self._execute(step)
                        obs_step = self.parser.make_observation(observation)
                        trajectory.add_step(obs_step)
                        self._log(f"\n👁️   {observation}")

                        tool_obj = self.tools.get(step.tool)
                        # Inject skills AFTER execution only for tools that are NOT configured for upfront injection
                        if (
                            tool_obj
                            and not tool_obj.inject_skill_before
                            and step.tool not in injected_skills
                        ):
                            skill_content = tool_obj.load_skill()

                            if skill_content:
                                self._log(f"\n📖  Injecting skill for: {step.tool}")

                                observation = (
                                    f"{observation}\n\n"
                                    f"[Skill guidance for {step.tool}]\n"
                                    f"{skill_content}"
                                )

                                injected_skills.add(step.tool)

                        messages.append({"role": "assistant", "content": raw})
                        messages.append({"role": "user", "content": f"Observation: {observation}"})

                    elif step.type == StepType.FINAL_ANSWER:
                        final_answer = step.content
                        self._log(f"\n✅  {final_answer}")

                if final_answer is not None:
                    self.status = AgentStatus.FINISHED
                    return AgentResult(
                        answer=final_answer,
                        trajectory=trajectory,
                        iterations=iteration,
                        total_time=time.time() - start_time,
                        status=AgentStatus.FINISHED,
                    )

                if not any(s.type == StepType.ACTION for s in steps):
                    no_op_count += 1
                    if no_op_count >= 3:
                        raise AgentMaxIterationsError(
                            "LLM repeatedly ignored the ReAct format."
                        )
                    messages.append({"role": "assistant", "content": raw})
                    messages.append({
                        "role": "user",
                        "content": (
                            "You MUST follow the ReAct format.\n"
                            "Thought: <reasoning>\n"
                            "Action: <tool_name>\n"
                            "Action Input: <input>\n\n"
                            "OR:\n"
                            "Thought: <reasoning>\n"
                            "Final Answer: <answer>"
                        ),
                    })
                else:
                    no_op_count = 0

            raise AgentMaxIterationsError(
                f"No Final Answer within {self.config.max_iterations} iterations."
            )

        except AgentMaxIterationsError as e:
            self.status = AgentStatus.FAILED
            return AgentResult(
                answer="", trajectory=trajectory,
                iterations=self.config.max_iterations,
                total_time=time.time() - start_time,
                status=AgentStatus.FAILED, error=str(e),
            )
        except Exception as e:
            self.status = AgentStatus.FAILED
            logger.error(f"[Agent] Unexpected error: {e}", exc_info=True)
            return AgentResult(
                answer="", trajectory=trajectory, iterations=0,
                total_time=time.time() - start_time,
                status=AgentStatus.FAILED, error=str(e),
            )

    # ══════════════════════════════════════════════════════════════════
    # Private helpers
    # ══════════════════════════════════════════════════════════════════

    def _call_llm(self, messages: list[dict], system: str) -> str:
        import time as _time
        import json as _json

        for attempt in range(1, self.config.max_retries + 1):
            try:
                return self.llm.complete(
                    messages=messages,
                    system=system,
                    temperature=self.config.temperature,
                )
            except RuntimeError as e:
                error_msg = str(e)

                # Parse retry delay from Gemini's 429 response if present
                wait = self.config.retry_delay * (2 ** (attempt - 1))
                if "429" in error_msg:
                    try:
                        # Extract JSON from the error message
                        json_start = error_msg.index("{")
                        data = _json.loads(error_msg[json_start:])
                        details = data.get("error", {}).get("details", [])
                        for d in details:
                            if "retryDelay" in d:
                                delay_str = d["retryDelay"].replace("s", "")
                                wait = float(delay_str) + 2  # small buffer
                                break
                    except Exception:
                        pass  # fall back to exponential backoff

                if attempt == self.config.max_retries:
                    raise
                logger.warning(f"[LLM] Attempt {attempt} failed. Retrying in {wait:.0f}s")
                _time.sleep(wait)

    def _execute(self, step) -> str:
        """Look up the tool and run it. Errors become observations."""
        tool = self.tools.get(step.tool)
        if tool is None:
            available = ", ".join(self.tools.list_names())
            return f"Error: tool '{step.tool}' not found. Available: {available}"
        try:
            return str(tool.run(step.tool_input))
        except ToolExecutionError as e:
            return f"Error running '{step.tool}': {e}"
        except Exception as e:
            return f"Unexpected error in '{step.tool}': {type(e).__name__}: {e}"

    def _log(self, msg: str) -> None:
        if self.config.verbose:
            print(msg)
        logger.debug(msg)
