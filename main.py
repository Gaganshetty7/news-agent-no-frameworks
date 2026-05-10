"""
ReAct Agent — entry point

Usage:
    uv run main.py                        # mock demo, no API key needed
    uv run main.py --real                 # real Gemini, single built-in task
    uv run main.py --task "your question" # real Gemini, your own task
    uv run main.py --interactive          # real Gemini, chat loop
    uv run main.py --save trace.json      # save trajectory after run
"""

import os
import sys
import argparse
from dotenv import load_dotenv

from src import (
    ReActAgent, AgentConfig, AgentStatus,
    create_llm_client, MockLLMClient,
    ToolRegistry,
    CalculatorTool, PythonREPLTool, DateTimeTool, MemoryTool, CompanyNewsTool,
    setup_logging,
)

load_dotenv()

# ══════════════════════════════════════════════════════════════════════
# Shared setup
# ══════════════════════════════════════════════════════════════════════

def build_registry() -> ToolRegistry:
    return (
        ToolRegistry()
        .register(CalculatorTool())
        .register(PythonREPLTool())
        .register(DateTimeTool())
        .register(MemoryTool())
        .register(CompanyNewsTool())
    )


def build_agent(real: bool, verbose: bool = True) -> ReActAgent:
    registry = build_registry()
    config   = AgentConfig(max_iterations=5, verbose=verbose, temperature=0.0)

    if real:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            print("ERROR: GEMINI_API_KEY not found. Add it to your .env file.")
            sys.exit(1)
        llm = create_llm_client("gemini", api_key=api_key)
    else:
        llm = MockLLMClient(MOCK_RESPONSES)

    return ReActAgent(registry, llm, config)


# ══════════════════════════════════════════════════════════════════════
# Mock responses (no API key needed)
# ══════════════════════════════════════════════════════════════════════

MOCK_RESPONSES = [
    (
        "Thought: I need to find the square root of 1991. Let me use the calculator.\n"
        "Action: calculator\n"
        "Action Input: sqrt(1991)"
    ),
    (
        "Thought: The square root of 1991 is approximately 44.62.\n"
        "Final Answer: The square root of 1991 is approximately 44.62."
    ),
]


# ══════════════════════════════════════════════════════════════════════
# Run modes
# ══════════════════════════════════════════════════════════════════════

def run_mock():
    print("\n" + "="*60)
    print("  ReAct Agent — Mock Demo (no API key needed)")
    print("="*60)

    agent  = build_agent(real=False)
    result = agent.run("What is the square root of 1991?")
    _print_result(result)


def run_real(task: str, save_path: str = ""):
    print("\n" + "="*60)
    print("  ReAct Agent — Gemini")
    print("="*60)

    agent  = build_agent(real=True)
    result = agent.run(task)
    _print_result(result)

    if save_path:
        result.trajectory.save(save_path)
        print(f"\nTrajectory saved to: {save_path}")


def run_interactive():
    agent = build_agent(real=True)

    print("\n" + "="*60)
    print("  ReAct Agent — Interactive Mode")
    print(f"  Tools: {agent.tools.list_names()}")
    print("  Type 'quit' to exit.")
    print("="*60 + "\n")

    while True:
        try:
            task = input("Task> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not task:
            continue
        if task.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        result = agent.run(task)
        _print_result(result, task)
        print()


# ══════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════

LOG_DIR = "src/logs"

def _print_result(result, task: str):
    import time

    # ── Write full details to file ─────────────────────────────────
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    safe_task = task[:40].replace(" ", "_").replace("/", "-")
    filepath = os.path.join(LOG_DIR, f"{timestamp}_{safe_task}.txt")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"TASK: {task}\n")
        f.write(f"Status     : {result.status.value}\n")
        f.write(f"Iterations : {result.iterations}\n")
        f.write(f"Time       : {result.total_time:.2f}s\n\n")
        f.write("=" * 60 + "\n")
        f.write("FULL ANSWER\n")
        f.write("=" * 60 + "\n")
        f.write(result.answer + "\n\n")
        f.write("=" * 60 + "\n")
        f.write("TRAJECTORY\n")
        f.write("=" * 60 + "\n")
        f.write(result.trajectory.pretty_print() + "\n\n")
        f.write("=" * 60 + "\n")
        f.write("RAW TURNS\n")
        f.write("=" * 60 + "\n")
        for turn in result.trajectory.raw_turns:
            f.write(f"\n--- Iteration {turn['iteration']} ---\n")
            f.write(turn["text"] + "\n")
        if result.error:
            f.write(f"\nERROR: {result.error}\n")

    # ── Print only what matters to terminal ────────────────────────
    print(f"\nStatus : {result.status.value}  |  Iterations : {result.iterations}  |  Time : {result.total_time:.2f}s")
    if result.answer:
        print(f"\n✅  {result.answer}")
    if result.error:
        print(f"\n❌  {result.error}")
    print(f"\n📄  Full run saved to: {filepath}\n")


# ══════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="ReAct Agent")
    parser.add_argument("--interactive", action="store_true", help="Interactive chat loop")
    parser.add_argument("--task",        type=str,            help="Single task to run")
    parser.add_argument("--save",        type=str, default="",help="Save trajectory to this path")
    parser.add_argument("--log",         type=str, default="INFO", help="Log level")
    args = parser.parse_args()

    setup_logging(args.log)

    if args.interactive:
        run_interactive()
    elif args.task:
        task = args.task
        run_real(task, save_path=args.save)
    else:
        run_mock()


if __name__ == "__main__":
    main()
