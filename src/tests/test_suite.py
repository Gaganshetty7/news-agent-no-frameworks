"""
Full test suite for the ReAct agent.
Run with: uv run -m pytest src/tests/test_suite.py -v
      or: uv run src/tests/test_suite.py
No API key needed — all tests use MockLLMClient.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.core.parser import ReActParser, StepType
from src.core.llm import MockLLMClient
from src.core.agent import ReActAgent, AgentConfig, AgentStatus
from src.core.prompt import build_system_prompt, build_user_prompt
from src.tools.registry import ToolRegistry
from src.tools.builtin import (
    CalculatorTool, PythonREPLTool, DateTimeTool, MemoryTool
)
from src.memory.trajectory import Trajectory
from src.utils.exceptions import ToolExecutionError


# ══════════════════════════════════════════════════════════════════════
# Parser
# ══════════════════════════════════════════════════════════════════════

class TestParser(unittest.TestCase):

    def setUp(self):
        self.parser = ReActParser()

    def test_parses_thought_and_action(self):
        text = (
            "Thought: I need to calculate.\n"
            "Action: calculator\n"
            "Action Input: {\"expression\": \"2+2\"}"
        )
        steps = self.parser.parse(text)
        types = [s.type for s in steps]
        self.assertIn(StepType.THOUGHT, types)
        self.assertIn(StepType.ACTION, types)

    def test_parses_final_answer(self):
        text = "Thought: I know this.\nFinal Answer: Paris."
        steps = self.parser.parse(text)
        finals = [s for s in steps if s.type == StepType.FINAL_ANSWER]
        self.assertEqual(len(finals), 1)
        self.assertEqual(finals[0].content, "Paris.")

    def test_action_json_input_parsed(self):
        text = (
            "Thought: calculating.\n"
            "Action: calculator\n"
            "Action Input: {\"expression\": \"sqrt(144)\"}"
        )
        steps = self.parser.parse(text)
        action = next(s for s in steps if s.type == StepType.ACTION)
        self.assertEqual(action.tool, "calculator")
        self.assertIsInstance(action.tool_input, dict)
        self.assertEqual(action.tool_input["expression"], "sqrt(144)")

    def test_action_plain_string_input(self):
        text = (
            "Thought: searching.\n"
            "Action: memory\n"
            "Action Input: Python programming language"
        )
        steps = self.parser.parse(text)
        action = next(s for s in steps if s.type == StepType.ACTION)
        self.assertIsInstance(action.tool_input, str)

    def test_thought_without_colon_still_parsed(self):
        text = (
            "Thought I need to think\n"
            "Final Answer: done."
        )
        steps = self.parser.parse(text)
        # should at least get the final answer
        finals = [s for s in steps if s.type == StepType.FINAL_ANSWER]
        self.assertEqual(len(finals), 1)

    def test_empty_text_returns_empty_list(self):
        steps = self.parser.parse("")
        self.assertIsInstance(steps, list)
        self.assertEqual(len(steps), 0)

    def test_only_final_answer_no_thought(self):
        steps = self.parser.parse("Final Answer: 42")
        finals = [s for s in steps if s.type == StepType.FINAL_ANSWER]
        self.assertEqual(len(finals), 1)

    def test_make_observation(self):
        obs = self.parser.make_observation("result: 4")
        self.assertEqual(obs.type, StepType.OBSERVATION)
        self.assertEqual(obs.content, "result: 4")


# ══════════════════════════════════════════════════════════════════════
# Calculator Tool
# ══════════════════════════════════════════════════════════════════════

class TestCalculatorTool(unittest.TestCase):

    def setUp(self):
        self.tool = CalculatorTool()

    def test_addition(self):
        self.assertEqual(self.tool.run("2 + 2"), "4")

    def test_power(self):
        self.assertEqual(self.tool.run("2 ** 10"), "1024")

    def test_sqrt(self):
        self.assertEqual(self.tool.run("sqrt(144)"), "12.0")

    def test_dict_input(self):
        self.assertEqual(self.tool.run({"expression": "10 * 5"}), "50")

    def test_pi(self):
        result = float(self.tool.run("round(pi, 4)"))
        self.assertAlmostEqual(result, 3.1416, places=4)

    def test_division_by_zero_raises(self):
        with self.assertRaises(ToolExecutionError):
            self.tool.run("1 / 0")

    def test_empty_expression_raises(self):
        with self.assertRaises(ToolExecutionError):
            self.tool.run("")

    def test_import_blocked(self):
        # __import__ should not be available — not in safe names
        with self.assertRaises(ToolExecutionError):
            self.tool.run("__import__('os').system('ls')")


# ══════════════════════════════════════════════════════════════════════
# Python REPL Tool
# ══════════════════════════════════════════════════════════════════════

class TestPythonREPLTool(unittest.TestCase):

    def setUp(self):
        self.tool = PythonREPLTool()

    def test_basic_print(self):
        self.assertEqual(self.tool.run({"code": "print('hello')"}), "hello")

    def test_arithmetic(self):
        self.assertEqual(self.tool.run({"code": "print(2 ** 8)"}), "256")

    def test_multiline(self):
        code = "x = 10\ny = 20\nprint(x + y)"
        self.assertEqual(self.tool.run({"code": code}), "30")

    def test_syntax_error_returns_error_string(self):
        result = self.tool.run({"code": "print((')"})
        self.assertIn("Error", result)

    def test_no_print_returns_no_output(self):
        result = self.tool.run({"code": "x = 42"})
        self.assertEqual(result, "(no output)")

    def test_empty_code_raises(self):
        with self.assertRaises(ToolExecutionError):
            self.tool.run({"code": ""})


# ══════════════════════════════════════════════════════════════════════
# DateTime Tool
# ══════════════════════════════════════════════════════════════════════

class TestDateTimeTool(unittest.TestCase):

    def setUp(self):
        self.tool = DateTimeTool()

    def test_now_contains_local(self):
        result = self.tool.run({"action": "now"})
        self.assertIn("Local:", result)

    def test_date_contains_year(self):
        import datetime
        result = self.tool.run({"action": "date"})
        self.assertIn(str(datetime.datetime.now().year), result)

    def test_timestamp_is_numeric(self):
        result = self.tool.run({"action": "timestamp"})
        self.assertTrue(result.isdigit())

    def test_time_is_formatted(self):
        result = self.tool.run({"action": "time"})
        # should be HH:MM:SS
        self.assertRegex(result, r"\d{2}:\d{2}:\d{2}")


# ══════════════════════════════════════════════════════════════════════
# Memory Tool
# ══════════════════════════════════════════════════════════════════════

class TestMemoryTool(unittest.TestCase):

    def setUp(self):
        self.tool = MemoryTool()

    def test_set_and_get(self):
        self.tool.run({"action": "set", "key": "name", "value": "Gagan"})
        result = self.tool.run({"action": "get", "key": "name"})
        self.assertIn("Gagan", result)

    def test_get_missing_key(self):
        result = self.tool.run({"action": "get", "key": "ghost"})
        self.assertIn("No value", result)

    def test_delete(self):
        self.tool.run({"action": "set", "key": "x", "value": "99"})
        self.tool.run({"action": "delete", "key": "x"})
        result = self.tool.run({"action": "get", "key": "x"})
        self.assertIn("No value", result)

    def test_list_shows_all_keys(self):
        self.tool.run({"action": "set", "key": "a", "value": "1"})
        self.tool.run({"action": "set", "key": "b", "value": "2"})
        result = self.tool.run({"action": "list"})
        self.assertIn("a", result)
        self.assertIn("b", result)

    def test_list_empty_memory(self):
        result = self.tool.run({"action": "list"})
        self.assertIn("empty", result.lower())


# ══════════════════════════════════════════════════════════════════════
# Tool Registry
# ══════════════════════════════════════════════════════════════════════

class TestToolRegistry(unittest.TestCase):

    def test_register_and_get(self):
        registry = ToolRegistry()
        calc = CalculatorTool()
        registry.register(calc)
        self.assertIs(registry.get("calculator"), calc)

    def test_get_unknown_returns_none(self):
        self.assertIsNone(ToolRegistry().get("ghost"))

    def test_chaining(self):
        registry = (
            ToolRegistry()
            .register(CalculatorTool())
            .register(DateTimeTool())
            .register(MemoryTool())
        )
        self.assertEqual(len(registry), 3)

    def test_descriptions_includes_tool_names(self):
        registry = ToolRegistry().register(CalculatorTool())
        self.assertIn("calculator", registry.descriptions())

    def test_list_names(self):
        registry = ToolRegistry().register(CalculatorTool()).register(DateTimeTool())
        names = registry.list_names()
        self.assertIn("calculator", names)
        self.assertIn("datetime", names)


# ══════════════════════════════════════════════════════════════════════
# Agent Integration (all mock — no API calls)
# ══════════════════════════════════════════════════════════════════════

def make_agent(responses: list[str], max_iterations: int = 5) -> ReActAgent:
    registry = (
        ToolRegistry()
        .register(CalculatorTool())
        .register(DateTimeTool())
        .register(MemoryTool())
    )
    config = AgentConfig(max_iterations=max_iterations, verbose=False)
    return ReActAgent(registry, MockLLMClient(responses), config)


class TestAgentIntegration(unittest.TestCase):

    def test_single_step_final_answer(self):
        agent = make_agent(["Thought: I know this.\nFinal Answer: Paris."])
        result = agent.run("What is the capital of France?")
        self.assertEqual(result.status, AgentStatus.FINISHED)
        self.assertEqual(result.answer, "Paris.")
        self.assertEqual(result.iterations, 1)

    def test_tool_use_then_final_answer(self):
        agent = make_agent([
            "Thought: I need to calculate.\nAction: calculator\nAction Input: 6 * 7",
            "Thought: Got it.\nFinal Answer: 42.",
        ])
        result = agent.run("What is 6 times 7?")
        self.assertEqual(result.status, AgentStatus.FINISHED)
        self.assertIn("42", result.answer)
        self.assertEqual(result.iterations, 2)

    def test_unknown_tool_becomes_observation(self):
        agent = make_agent([
            "Thought: Let me use a fake tool.\nAction: ghost_tool\nAction Input: hello",
            "Thought: That failed.\nFinal Answer: Could not complete.",
        ])
        result = agent.run("Use a fake tool")
        self.assertEqual(result.status, AgentStatus.FINISHED)

    def test_max_iterations_returns_failed(self):
        agent = make_agent(
            ["Thought: Still thinking.\nAction: calculator\nAction Input: 1+1"] * 10,
            max_iterations=3,
        )
        result = agent.run("never ending task")
        self.assertEqual(result.status, AgentStatus.FAILED)
        self.assertIsNotNone(result.error)

    def test_trajectory_records_all_steps(self):
        agent = make_agent([
            "Thought: Calculating.\nAction: calculator\nAction Input: 10 + 5",
            "Thought: Done.\nFinal Answer: 15.",
        ])
        result = agent.run("What is 10 + 5?")
        traj = result.trajectory
        self.assertTrue(len(traj.thoughts()) >= 1)
        self.assertTrue(len(traj.actions()) >= 1)
        self.assertTrue(len(traj.observations()) >= 1)

    def test_result_serializes_to_dict(self):
        agent = make_agent(["Final Answer: done."])
        result = agent.run("test")
        d = result.to_dict()
        self.assertIn("answer", d)
        self.assertIn("status", d)
        self.assertIn("steps", d)
        self.assertIsInstance(d["steps"], list)

    def test_memory_tool_used_across_steps(self):
        agent = make_agent([
            "Thought: Store this.\nAction: memory\nAction Input: {\"action\": \"set\", \"key\": \"city\", \"value\": \"Bengaluru\"}",
            "Thought: Retrieve it.\nAction: memory\nAction Input: {\"action\": \"get\", \"key\": \"city\"}",
            "Thought: Got it.\nFinal Answer: The city is Bengaluru.",
        ])
        result = agent.run("Remember and recall a city")
        self.assertEqual(result.status, AgentStatus.FINISHED)
        self.assertIn("Bengaluru", result.answer)


# ══════════════════════════════════════════════════════════════════════
# Trajectory
# ══════════════════════════════════════════════════════════════════════

class TestTrajectory(unittest.TestCase):

    def _make_trajectory(self) -> Trajectory:
        parser = ReActParser()
        traj = Trajectory(task="test task")
        for step in parser.parse(
            "Thought: thinking.\nAction: calculator\nAction Input: 1+1"
        ):
            traj.add_step(step)
        traj.add_step(parser.make_observation("2"))
        for step in parser.parse("Thought: done.\nFinal Answer: 2."):
            traj.add_step(step)
        return traj

    def test_thoughts_filtered(self):
        self.assertEqual(len(self._make_trajectory().thoughts()), 2)

    def test_actions_filtered(self):
        self.assertEqual(len(self._make_trajectory().actions()), 1)

    def test_observations_filtered(self):
        self.assertEqual(len(self._make_trajectory().observations()), 1)

    def test_to_dict_structure(self):
        d = self._make_trajectory().to_dict()
        self.assertIn("task", d)
        self.assertIn("steps", d)
        self.assertIsInstance(d["steps"], list)

    def test_save_and_reload(self):
        import json, tempfile, os
        traj = self._make_trajectory()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        try:
            traj.save(path)
            with open(path) as f:
                data = json.load(f)
            self.assertEqual(data["task"], "test task")
            self.assertGreater(len(data["steps"]), 0)
        finally:
            os.unlink(path)


# ══════════════════════════════════════════════════════════════════════
# Prompts
# ══════════════════════════════════════════════════════════════════════

class TestPrompts(unittest.TestCase):

    def test_system_prompt_contains_tools(self):
        prompt = build_system_prompt("### calculator\nDoes math.")
        self.assertIn("calculator", prompt)
        self.assertIn("Thought:", prompt)
        self.assertIn("Final Answer:", prompt)

    def test_user_prompt_contains_task(self):
        prompt = build_user_prompt("What is 2 + 2?")
        self.assertIn("What is 2 + 2?", prompt)

    def test_user_prompt_without_skill_has_no_skill_block(self):
        prompt = build_user_prompt("simple task")
        self.assertNotIn("Skill:", prompt)

    def test_user_prompt_with_skill_injected(self):
        prompt = build_user_prompt(
            task="analyze this csv",
            skill_name="csv_analysis",
            skill_content="## How to read CSVs\ncheck columns first",
        )
        self.assertIn("csv_analysis", prompt)
        self.assertIn("check columns first", prompt)


# ══════════════════════════════════════════════════════════════════════
# Runner
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from src.utils import setup_logging
    setup_logging("WARNING")  # keep test output clean

    loader = unittest.TestLoader()
    suite  = unittest.TestSuite()

    for cls in [
        TestParser,
        TestCalculatorTool,
        TestPythonREPLTool,
        TestDateTimeTool,
        TestMemoryTool,
        TestToolRegistry,
        TestAgentIntegration,
        TestTrajectory,
        TestPrompts,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
