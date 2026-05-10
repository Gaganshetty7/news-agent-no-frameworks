import ast
import math
import operator
import subprocess
import datetime
import logging
from typing import Any

from .registry import BaseTool
from ..utils.exceptions import ToolExecutionError

logger = logging.getLogger(__name__)


# ── Tool 1: Calculator (safe — uses AST, never eval()) ────────────────

class CalculatorTool(BaseTool):
    name = "calculator"
    description = (
        "Evaluate math expressions. "
        "Supports: +, -, *, /, **, %, sqrt, sin, cos, log, abs, round, pi, e.\n"
        "Input: a plain math expression string e.g. sqrt(144) or 2 ** 10"
    )

    _SAFE_NAMES = {
        "abs": abs, "round": round,
        "sqrt": math.sqrt, "log": math.log, "log2": math.log2,
        "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "pi": math.pi, "e": math.e,
        "ceil": math.ceil, "floor": math.floor,
    }
    _SAFE_OPS = {
        ast.Add: operator.add, ast.Sub: operator.sub,
        ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.Mod: operator.mod,
        ast.USub: operator.neg,
    }

    def run(self, tool_input: Any) -> str:
        expr = tool_input.get("expression", "") if isinstance(tool_input, dict) else str(tool_input)
        expr = expr.strip()
        if not expr:
            raise ToolExecutionError("Empty expression.")
        try:
            result = self._eval(ast.parse(expr, mode="eval").body)
            return str(result)
        except ToolExecutionError:
            raise
        except Exception as e:
            raise ToolExecutionError(f"Cannot evaluate: {e}")

    def _eval(self, node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in self._SAFE_NAMES:
                return self._SAFE_NAMES[node.id]
            raise ToolExecutionError(f"Unknown name: {node.id!r}")
        if isinstance(node, ast.BinOp):
            fn = self._SAFE_OPS.get(type(node.op))
            if not fn:
                raise ToolExecutionError(f"Unsupported operator: {type(node.op).__name__}")
            return fn(self._eval(node.left), self._eval(node.right))
        if isinstance(node, ast.UnaryOp):
            fn = self._SAFE_OPS.get(type(node.op))
            return fn(self._eval(node.operand))
        if isinstance(node, ast.Call):
            func = self._eval(node.func)
            args = [self._eval(a) for a in node.args]
            return func(*args)
        raise ToolExecutionError(f"Unsupported node: {type(node).__name__}")


# ── Tool 2: Python REPL (sandboxed in subprocess) ─────────────────────

class PythonREPLTool(BaseTool):
    name = "python_repl"
    description = (
        "Execute Python code and return printed output. "
        "Always use print() to show results.\n"
        "Input: {\"code\": \"your code here\"}"
    )

    def run(self, tool_input: Any) -> str:
        code = tool_input.get("code", "") if isinstance(tool_input, dict) else str(tool_input)
        code = code.strip()
        if not code:
            raise ToolExecutionError("No code provided.")
        try:
            result = subprocess.run(
                ["python3", "-c", code],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                return f"Error:\n{result.stderr.strip()}"
            return result.stdout.strip() or "(no output)"
        except subprocess.TimeoutExpired:
            raise ToolExecutionError("Code timed out after 10 seconds.")


# ── Tool 3: DateTime ───────────────────────────────────────────────────

class DateTimeTool(BaseTool):
    name = "datetime"
    description = (
        "Get current date and time.\n"
        "Input: {\"action\": \"now\"} or \"date\" or \"time\" or \"timestamp\""
    )

    def run(self, tool_input: Any) -> str:
        action = tool_input.get("action", "now") if isinstance(tool_input, dict) else str(tool_input)
        now = datetime.datetime.now()
        if action == "date":
            return now.strftime("%Y-%m-%d (%A, %B %d %Y)")
        if action == "time":
            return now.strftime("%H:%M:%S")
        if action == "timestamp":
            return str(int(now.timestamp()))
        return (
            f"Local: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Day:   {now.strftime('%A')}"
        )


# ── Tool 4: Memory (key-value scratchpad) ─────────────────────────────

class MemoryTool(BaseTool):
    name = "memory"
    description = (
        "Store or retrieve information across reasoning steps.\n"
        "Input: {\"action\": \"set\", \"key\": \"x\", \"value\": \"42\"}\n"
        "       {\"action\": \"get\", \"key\": \"x\"}\n"
        "       {\"action\": \"list\"}"
    )

    def __init__(self):
        self._store: dict[str, str] = {}

    def run(self, tool_input: Any) -> str:
        if not isinstance(tool_input, dict):
            raise ToolExecutionError("Memory tool requires a JSON dict input.")
        action = tool_input.get("action", "").lower()
        key = tool_input.get("key", "")
        value = tool_input.get("value", "")

        if action == "set":
            self._store[key] = str(value)
            return f"Stored: {key!r} = {value!r}"
        if action == "get":
            return self._store.get(key) or f"No value for key: {key!r}"
        if action == "list":
            return "\n".join(f"{k}: {v}" for k, v in self._store.items()) or "Memory is empty."
        if action == "delete":
            self._store.pop(key, None)
            return f"Deleted: {key!r}"
        raise ToolExecutionError(f"Unknown action: {action!r}. Use: set, get, list, delete")
