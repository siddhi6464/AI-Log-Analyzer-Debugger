"""LangChain tool: Context-aware debugging suggestions."""

from langchain_core.tools import tool


@tool
def suggest_debug_actions(error_context: str) -> str:
    """
    Given a summary of detected errors, patterns, and anomalies,
    generate context-aware debugging suggestions and root-cause analysis.

    This tool uses your AI reasoning to analyze the error context and provide:
    - Root cause classification
    - Actionable fix recommendations
    - Priority ranking

    Args:
        error_context: A text summary of all detected errors, patterns, and
                      anomalies found in the logs. Include pattern names,
                      frequencies, severity levels, and sample error messages.
    """
    # This tool is intentionally a pass-through — the LLM itself IS the tool.
    # The agent will use its reasoning capabilities to generate suggestions
    # based on the context provided. The tool exists to give the agent a
    # structured step in its workflow for "generate fix suggestions."
    return (
        f"Analyze the following error context and provide root-cause analysis "
        f"with actionable fix suggestions:\n\n{error_context}"
    )
