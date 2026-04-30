"""
Regex-based pattern detector for common error signatures.
"""

import re
from app.models import PatternMatch, Severity

PATTERN_LIBRARY = [
    {"name": "Connection Refused", "category": "network",
     "regex": re.compile(r"connection\s+refused|ECONNREFUSED|connect\(\)\s+failed", re.I),
     "severity": Severity.HIGH,
     "description": "Remote service not accepting connections — may be down or firewalled."},
    {"name": "Connection Timeout", "category": "network",
     "regex": re.compile(r"connection\s+timed?\s*out|ETIMEDOUT|read\s+timed?\s*out", re.I),
     "severity": Severity.HIGH,
     "description": "Network request exceeded timeout — possible congestion or slow upstream."},
    {"name": "DNS Resolution Failure", "category": "network",
     "regex": re.compile(r"name\s+or\s+service\s+not\s+known|ENOTFOUND|could\s+not\s+resolve", re.I),
     "severity": Severity.HIGH,
     "description": "DNS lookup failed — hostname incorrect or DNS unreachable."},
    {"name": "Connection Reset", "category": "network",
     "regex": re.compile(r"connection\s+reset\s+by\s+peer|ECONNRESET|broken\s+pipe", re.I),
     "severity": Severity.MEDIUM,
     "description": "Connection forcibly closed by remote host."},
    {"name": "Out of Memory", "category": "memory",
     "regex": re.compile(r"out\s+of\s+memory|OOM|MemoryError|cannot\s+allocate\s+memory", re.I),
     "severity": Severity.CRITICAL,
     "description": "Process ran out of memory — needs limit increase or leak fix."},
    {"name": "Disk Space Exhausted", "category": "disk",
     "regex": re.compile(r"no\s+space\s+left\s+on\s+device|ENOSPC|disk\s+(?:full|quota)", re.I),
     "severity": Severity.CRITICAL,
     "description": "Disk full — cleanup temp files, logs, or old data."},
    {"name": "Permission Denied", "category": "disk",
     "regex": re.compile(r"permission\s+denied|EACCES|access\s+denied", re.I),
     "severity": Severity.HIGH,
     "description": "File/directory access denied — check ownership and permissions."},
    {"name": "File Not Found", "category": "disk",
     "regex": re.compile(r"file\s+not\s+found|No\s+such\s+file|ENOENT|FileNotFoundError", re.I),
     "severity": Severity.MEDIUM,
     "description": "Referenced file or path does not exist."},
    {"name": "Authentication Failure", "category": "auth",
     "regex": re.compile(r"authentication\s+fail|invalid\s+(?:credentials|password|token)|401\s+Unauthorized", re.I),
     "severity": Severity.HIGH,
     "description": "Auth attempt failed — brute force or misconfigured credentials."},
    {"name": "SSL/TLS Error", "category": "auth",
     "regex": re.compile(r"SSL\s+(?:error|handshake)|certificate\s+(?:expired|verify\s+failed)|TLS\s+error", re.I),
     "severity": Severity.HIGH,
     "description": "SSL/TLS handshake or certificate validation failed."},
    {"name": "Database Connection Error", "category": "database",
     "regex": re.compile(r"(?:database|db)\s+connection\s+(?:failed|refused|lost)|could\s+not\s+connect\s+to\s+(?:database|postgres|mysql)", re.I),
     "severity": Severity.CRITICAL,
     "description": "Failed to connect to database — service down or bad credentials."},
    {"name": "Query Error", "category": "database",
     "regex": re.compile(r"SQL\s+(?:error|syntax)|deadlock|duplicate\s+(?:key|entry)|IntegrityError", re.I),
     "severity": Severity.HIGH,
     "description": "Database query failed — syntax error, deadlock, or constraint violation."},
    {"name": "HTTP 5xx Server Error", "category": "http",
     "regex": re.compile(r"\b(?:500|502|503|504)\b.*(?:error|Internal\s+Server|Bad\s+Gateway|Service\s+Unavailable)", re.I),
     "severity": Severity.HIGH,
     "description": "Server-side HTTP error — upstream failure or application crash."},
    {"name": "HTTP 4xx Client Error", "category": "http",
     "regex": re.compile(r"\b(?:400|403|404|429)\b.*(?:error|Bad\s+Request|Forbidden|Not\s+Found|Too\s+Many)", re.I),
     "severity": Severity.MEDIUM,
     "description": "Client-side HTTP error — bad request or rate limit."},
    {"name": "Python Traceback", "category": "application",
     "regex": re.compile(r"Traceback\s+\(most\s+recent\s+call\s+last\)", re.I),
     "severity": Severity.HIGH,
     "description": "Python exception traceback — unhandled exception."},
    {"name": "Segmentation Fault", "category": "application",
     "regex": re.compile(r"segmentation\s+fault|SIGSEGV|core\s+dumped", re.I),
     "severity": Severity.CRITICAL,
     "description": "Process crashed with segfault — memory corruption."},
    {"name": "Process Crash", "category": "application",
     "regex": re.compile(r"process\s+(?:crashed|killed|terminated|died)|SIGKILL|worker\s+(?:exited|failed)", re.I),
     "severity": Severity.HIGH,
     "description": "Process terminated unexpectedly — may be OOM-killed."},
]


def detect_patterns(log_text: str) -> list[PatternMatch]:
    """Scan log text for all known error patterns."""
    lines = log_text.strip().split("\n")
    results: list[PatternMatch] = []

    for pdef in PATTERN_LIBRARY:
        matching = [l.strip() for l in lines if pdef["regex"].search(l)]
        if matching:
            results.append(PatternMatch(
                pattern_name=pdef["name"],
                pattern_category=pdef["category"],
                count=len(matching),
                severity=pdef["severity"],
                sample_lines=matching[:3],
                description=pdef["description"],
            ))

    severity_order = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3}
    results.sort(key=lambda p: (severity_order.get(p.severity, 4), -p.count))
    return results


def get_pattern_summary(patterns: list[PatternMatch]) -> dict:
    """Summarize detected patterns by category."""
    cats: dict[str, int] = {}
    for p in patterns:
        cats[p.pattern_category] = cats.get(p.pattern_category, 0) + p.count
    return {
        "total_patterns": len(patterns),
        "total_matches": sum(p.count for p in patterns),
        "by_category": cats,
        "critical_count": sum(1 for p in patterns if p.severity == Severity.CRITICAL),
        "high_count": sum(1 for p in patterns if p.severity == Severity.HIGH),
    }
