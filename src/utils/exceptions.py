class AgentError(Exception):
    """Base class for all agent errors."""

class AgentMaxIterationsError(AgentError):
    """Agent hit the iteration limit without finishing."""

class AgentParseError(AgentError):
    """LLM output couldn't be parsed into ReAct steps."""

class ToolExecutionError(AgentError):
    """A tool failed during execution."""

class ToolNotFoundError(AgentError):
    """Action referenced a tool that isn't registered."""

class LLMError(AgentError):
    """LLM API call failed."""
