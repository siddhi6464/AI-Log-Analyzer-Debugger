"""LangChain tool: Regex pattern detection."""

from langchain_core.tools import tool
from app.core.pattern_detector import detect_patterns, get_pattern_summary


@tool
def detect_error_patterns(log_text: str) -> str:
    """
    Scan log text for known error patterns using regex matching.
    Detects: connection errors, memory issues, disk problems, auth failures,
    database errors, HTTP errors, application crashes, and more.

    Returns matched patterns with frequency counts, severity, and sample lines.

    Args:
        log_text: Raw log text to scan for patterns.
    """
    patterns = detect_patterns(log_text)
    summary = get_pattern_summary(patterns)

    return str({
        "summary": summary,
        "patterns": [p.model_dump() for p in patterns],
    })
