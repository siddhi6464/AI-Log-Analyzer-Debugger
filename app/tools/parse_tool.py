"""LangChain tool: Log parsing."""

from langchain_core.tools import tool
from app.core.log_parser import parse_logs, get_log_summary


@tool
def parse_log_text(log_text: str) -> str:
    """
    Parse raw log text into structured entries. Auto-detects log format
    (nginx, python, syslog, generic). Returns summary statistics and
    error/warning entries as JSON.

    Use this tool first to understand the log data structure and content.

    Args:
        log_text: Raw log text content to parse.
    """
    entries, fmt = parse_logs(log_text)
    summary = get_log_summary(entries)
    summary["detected_format"] = fmt

    # Include only error/warning/critical entries in detail
    important = [e.model_dump() for e in entries
                 if e.level.value in ("ERROR", "WARNING", "CRITICAL")]

    return str({
        "summary": summary,
        "format": fmt,
        "important_entries": important[:30],  # Cap to avoid token overflow
        "total_parsed": len(entries),
    })
