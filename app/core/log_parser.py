"""
Multi-format log parser.
Supports Nginx, Python, Syslog, and generic log formats.
Auto-detects format and returns structured LogEntry objects.
"""

import re
from typing import Optional
from app.models import LogEntry, LogLevel


# ── Format-specific regex patterns ─────────────────────────────

PATTERNS = {
    "nginx": re.compile(
        r"(?P<timestamp>\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})\s+"
        r"\[(?P<level>\w+)\]\s+"
        r"(?P<pid>\d+)#(?P<tid>\d+):\s+"
        r"(?:\*\d+\s+)?"
        r"(?P<message>.*)"
    ),
    "python": re.compile(
        r"(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}[,\.]\d+)\s+"
        r"[-–]\s+"
        r"(?P<source>[\w\.]+)\s+"
        r"[-–]\s+"
        r"(?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL)\s+"
        r"[-–]\s+"
        r"(?P<message>.*)"
    ),
    "syslog": re.compile(
        r"(?P<timestamp>\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+"
        r"(?P<source>[\w\-\.]+)\s+"
        r"(?P<process>[\w\-\/]+)"
        r"(?:\[(?P<pid>\d+)\])?:\s+"
        r"(?P<message>.*)"
    ),
    "generic_timestamped": re.compile(
        r"(?P<timestamp>\d{4}[-/]\d{2}[-/]\d{2}[T\s]\d{2}:\d{2}:\d{2}[^\s]*)\s+"
        r"(?:(?P<level>DEBUG|INFO|WARN(?:ING)?|ERROR|CRITICAL|FATAL|TRACE)\s+)?"
        r"(?:\[(?P<source>[^\]]+)\]\s*)?"
        r"(?P<message>.*)"
    ),
}

# ── Level normalization ────────────────────────────────────────

LEVEL_MAP = {
    "debug": LogLevel.DEBUG,
    "info": LogLevel.INFO,
    "notice": LogLevel.INFO,
    "warn": LogLevel.WARNING,
    "warning": LogLevel.WARNING,
    "error": LogLevel.ERROR,
    "err": LogLevel.ERROR,
    "crit": LogLevel.CRITICAL,
    "critical": LogLevel.CRITICAL,
    "fatal": LogLevel.CRITICAL,
    "alert": LogLevel.CRITICAL,
    "emerg": LogLevel.CRITICAL,
}


def _normalize_level(raw_level: Optional[str]) -> LogLevel:
    """Normalize a raw level string to a LogLevel enum."""
    if not raw_level:
        return LogLevel.UNKNOWN
    return LEVEL_MAP.get(raw_level.lower().strip(), LogLevel.UNKNOWN)


def _infer_level_from_message(message: str) -> LogLevel:
    """Infer log level from message content if not explicitly stated."""
    msg_lower = message.lower()
    if any(kw in msg_lower for kw in ["critical", "fatal", "panic", "emerg"]):
        return LogLevel.CRITICAL
    if any(kw in msg_lower for kw in ["error", "exception", "traceback", "failed", "failure"]):
        return LogLevel.ERROR
    if any(kw in msg_lower for kw in ["warn", "warning", "deprecated"]):
        return LogLevel.WARNING
    if any(kw in msg_lower for kw in ["debug", "trace"]):
        return LogLevel.DEBUG
    return LogLevel.INFO


# ── Format detection ───────────────────────────────────────────

def detect_format(log_text: str) -> str:
    """
    Auto-detect log format by testing the first few non-empty lines.
    Returns the format name: 'nginx', 'python', 'syslog', or 'generic'.
    """
    lines = [l.strip() for l in log_text.strip().split("\n") if l.strip()][:10]

    format_scores = {fmt: 0 for fmt in PATTERNS}

    for line in lines:
        for fmt, pattern in PATTERNS.items():
            if pattern.match(line):
                format_scores[fmt] += 1

    # Return the format with the highest match count
    best_format = max(format_scores, key=format_scores.get)
    if format_scores[best_format] > 0:
        return best_format if best_format != "generic_timestamped" else "generic"

    return "generic"


# ── Main parser ────────────────────────────────────────────────

def parse_logs(log_text: str) -> tuple[list[LogEntry], str]:
    """
    Parse raw log text into structured LogEntry objects.

    Returns:
        Tuple of (list of LogEntry objects, detected format name)
    """
    lines = log_text.strip().split("\n")
    detected_format = detect_format(log_text)
    entries: list[LogEntry] = []

    # Select the appropriate pattern
    if detected_format == "generic":
        pattern = PATTERNS["generic_timestamped"]
    else:
        pattern = PATTERNS[detected_format]

    current_entry: Optional[LogEntry] = None

    for i, raw_line in enumerate(lines, start=1):
        stripped = raw_line.strip()
        if not stripped:
            continue

        match = pattern.match(stripped)

        if match:
            # Save previous multi-line entry
            if current_entry:
                entries.append(current_entry)

            groups = match.groupdict()

            # Extract level
            level = _normalize_level(groups.get("level"))
            if level == LogLevel.UNKNOWN:
                level = _infer_level_from_message(groups.get("message", ""))

            current_entry = LogEntry(
                line_number=i,
                timestamp=groups.get("timestamp"),
                level=level,
                source=groups.get("source") or groups.get("process"),
                message=groups.get("message", stripped),
                raw=raw_line,
            )
        else:
            # Continuation line (e.g., stack trace) — append to previous entry
            if current_entry:
                current_entry.message += f"\n{stripped}"
                current_entry.raw += f"\n{raw_line}"
            else:
                # Orphan line — create a standalone entry
                level = _infer_level_from_message(stripped)
                current_entry = LogEntry(
                    line_number=i,
                    timestamp=None,
                    level=level,
                    source=None,
                    message=stripped,
                    raw=raw_line,
                )

    # Don't forget the last entry
    if current_entry:
        entries.append(current_entry)

    return entries, detected_format


def get_error_entries(entries: list[LogEntry]) -> list[LogEntry]:
    """Filter entries to only errors, warnings, and criticals."""
    return [
        e for e in entries
        if e.level in (LogLevel.ERROR, LogLevel.WARNING, LogLevel.CRITICAL)
    ]


def get_log_summary(entries: list[LogEntry]) -> dict:
    """Generate summary statistics from parsed entries."""
    level_counts = {}
    for entry in entries:
        level_counts[entry.level.value] = level_counts.get(entry.level.value, 0) + 1

    return {
        "total_lines": len(entries),
        "error_count": level_counts.get("ERROR", 0),
        "warning_count": level_counts.get("WARNING", 0),
        "critical_count": level_counts.get("CRITICAL", 0),
        "info_count": level_counts.get("INFO", 0),
        "debug_count": level_counts.get("DEBUG", 0),
        "level_distribution": level_counts,
    }
