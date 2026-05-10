from typing import Optional


# ══════════════════════════════════════════════════════════════════════
# System prompt — teaches Gemini the ReAct loop
# ══════════════════════════════════════════════════════════════════════

REACT_SYSTEM = """\
You are a ReAct agent. You MUST follow this exact output format on every single response.
No exceptions. Do not answer directly. Do not use any other language except English.

## MANDATORY FORMAT

Either this (when you need a tool):

Thought: <your reasoning>
Action: <tool_name>
Action Input: <json or plain string>

Or this (only when you have the final answer):

Thought: <your reasoning>
Final Answer: <your complete answer>

## RULES

1. ALWAYS start with "Thought:" — never skip it.
2. NEVER answer directly without the Thought/Action or Thought/Final Answer structure.
3. NEVER use any language other than English.
4. NEVER write "Observation:" yourself — that is injected by the system.
5. ONE action per response. Do not chain multiple actions.
6. If a tool errors, adjust your approach and try again.
7. You MUST eventually write "Final Answer:" — never leave a task unfinished.

## AVAILABLE TOOLS

{tool_descriptions}

## EXAMPLE

Thought: I need to calculate the square root of 144.
Action: calculator
Action Input: sqrt(144)
"""

# ══════════════════════════════════════════════════════════════════════
# Just-in-time skill injection
# Loaded only when the task needs it — saves tokens on unrelated tasks
# ══════════════════════════════════════════════════════════════════════

SKILL_BLOCK = """\

## Skill: {skill_name}

{skill_content}
"""

# ══════════════════════════════════════════════════════════════════════
# User prompt — wraps the task, optionally injects a skill
# ══════════════════════════════════════════════════════════════════════

USER_PROMPT = """\
{skill_block}Task: {task}

Begin your ReAct loop now.
"""


# ══════════════════════════════════════════════════════════════════════
# Builder functions
# ══════════════════════════════════════════════════════════════════════

def build_system_prompt(tool_descriptions: str) -> str:
    return REACT_SYSTEM.format(tool_descriptions=tool_descriptions)


def build_user_prompt(task: str) -> str:
    return f"Task: {task}\n\nBegin your ReAct loop now."


def load_skill(path: str) -> str:
    """
    Read a skill.md file from disk and return its contents.
    Call this only when you've decided the task needs this skill.

    Usage:
        content = load_skill("skills/web_search.md")
        prompt  = build_user_prompt(task, skill_name="web_search", skill_content=content)
    """
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
