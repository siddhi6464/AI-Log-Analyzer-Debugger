"""
Statistical anomaly detector for log data.
Detects error rate spikes, frequency bursts, time gaps, and repeated errors.
Pure Python — no ML libraries needed.
"""

import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Optional
from app.models import Anomaly, AnomalyType, Severity, LogEntry, LogLevel


def _parse_timestamp(ts_str: str) -> Optional[datetime]:
    """Try multiple timestamp formats."""
    formats = [
        "%Y-%m-%d %H:%M:%S,%f",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S%z",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(ts_str.strip(), fmt)
        except (ValueError, TypeError):
            continue
    return None


def detect_anomalies(entries: list[LogEntry]) -> list[Anomaly]:
    """Run all anomaly detectors on parsed log entries."""
    anomalies: list[Anomaly] = []
    anomalies.extend(_detect_error_spikes(entries))
    anomalies.extend(_detect_frequency_bursts(entries))
    anomalies.extend(_detect_time_gaps(entries))
    anomalies.extend(_detect_repeated_errors(entries))
    anomalies.extend(_detect_resource_exhaustion(entries))
    return anomalies


def _detect_error_spikes(entries: list[LogEntry]) -> list[Anomaly]:
    """Detect sudden spikes in error rate using a sliding window."""
    anomalies = []
    timed = [(e, _parse_timestamp(e.timestamp)) for e in entries if e.timestamp]
    timed = [(e, t) for e, t in timed if t is not None]

    if len(timed) < 10:
        return anomalies

    # Count errors in 1-minute buckets
    buckets: dict[str, dict] = defaultdict(lambda: {"total": 0, "errors": 0})
    for entry, ts in timed:
        key = ts.strftime("%Y-%m-%d %H:%M")
        buckets[key]["total"] += 1
        if entry.level in (LogLevel.ERROR, LogLevel.CRITICAL):
            buckets[key]["errors"] += 1

    if not buckets:
        return anomalies

    # Calculate average error rate
    error_rates = []
    for k, v in buckets.items():
        rate = v["errors"] / max(v["total"], 1)
        error_rates.append((k, rate, v["errors"], v["total"]))

    if len(error_rates) < 2:
        return anomalies

    avg_rate = sum(r[1] for r in error_rates) / len(error_rates)

    # Flag buckets with error rate > 3x average (z-score-like)
    for minute, rate, err_count, total in error_rates:
        if avg_rate > 0 and rate > avg_rate * 3 and err_count >= 3:
            anomalies.append(Anomaly(
                anomaly_type=AnomalyType.ERROR_SPIKE,
                severity=Severity.HIGH if rate > 0.5 else Severity.MEDIUM,
                title=f"Error spike at {minute}",
                description=f"Error rate jumped to {rate:.0%} ({err_count}/{total} entries) — {rate/max(avg_rate,0.01):.1f}x above average ({avg_rate:.0%}).",
                evidence=[f"{minute}: {err_count} errors out of {total} log entries"],
                time_range=minute,
            ))

    return anomalies


def _detect_frequency_bursts(entries: list[LogEntry]) -> list[Anomaly]:
    """Detect unusual log volume bursts."""
    anomalies = []
    timed = [(e, _parse_timestamp(e.timestamp)) for e in entries if e.timestamp]
    timed = [(e, t) for e, t in timed if t is not None]

    if len(timed) < 20:
        return anomalies

    buckets: dict[str, int] = defaultdict(int)
    for _, ts in timed:
        buckets[ts.strftime("%Y-%m-%d %H:%M")] += 1

    if len(buckets) < 3:
        return anomalies

    counts = list(buckets.values())
    avg = sum(counts) / len(counts)

    for minute, count in buckets.items():
        if avg > 0 and count > avg * 5 and count >= 10:
            anomalies.append(Anomaly(
                anomaly_type=AnomalyType.FREQUENCY_BURST,
                severity=Severity.MEDIUM,
                title=f"Log volume burst at {minute}",
                description=f"{count} log entries in one minute — {count/avg:.1f}x the average ({avg:.0f}/min).",
                evidence=[f"{minute}: {count} entries (avg: {avg:.0f})"],
                time_range=minute,
            ))

    return anomalies


def _detect_time_gaps(entries: list[LogEntry]) -> list[Anomaly]:
    """Detect unusual silence periods in logs."""
    anomalies = []
    timestamps = []
    for e in entries:
        if e.timestamp:
            ts = _parse_timestamp(e.timestamp)
            if ts:
                timestamps.append(ts)

    if len(timestamps) < 5:
        return anomalies

    timestamps.sort()
    gaps = [(timestamps[i+1] - timestamps[i], timestamps[i], timestamps[i+1])
            for i in range(len(timestamps)-1)]

    if not gaps:
        return anomalies

    avg_gap = sum((g[0].total_seconds() for g in gaps)) / len(gaps)

    for gap_dur, start, end in gaps:
        secs = gap_dur.total_seconds()
        if avg_gap > 0 and secs > max(avg_gap * 10, 300) and secs > 60:
            anomalies.append(Anomaly(
                anomaly_type=AnomalyType.TIME_GAP,
                severity=Severity.MEDIUM,
                title=f"Log silence for {_fmt_duration(secs)}",
                description=f"No log entries for {_fmt_duration(secs)} between {start} and {end}. Average gap is {_fmt_duration(avg_gap)}.",
                evidence=[f"Gap: {start} → {end} ({_fmt_duration(secs)})"],
                time_range=f"{start} - {end}",
            ))

    return anomalies


def _detect_repeated_errors(entries: list[LogEntry]) -> list[Anomaly]:
    """Detect the same error message repeating excessively."""
    anomalies = []
    error_entries = [e for e in entries if e.level in (LogLevel.ERROR, LogLevel.CRITICAL)]

    if not error_entries:
        return anomalies

    # Normalize messages (remove numbers/timestamps for grouping)
    def normalize(msg: str) -> str:
        msg = re.sub(r"\d{4}[-/]\d{2}[-/]\d{2}[\sT]\d{2}:\d{2}:\d{2}[^\s]*", "<TS>", msg)
        msg = re.sub(r"\b\d+\.\d+\.\d+\.\d+\b", "<IP>", msg)
        msg = re.sub(r"\b\d{4,}\b", "<NUM>", msg)
        return msg.strip()

    counts = Counter(normalize(e.message.split("\n")[0]) for e in error_entries)

    for msg, count in counts.most_common(5):
        if count >= 5:
            samples = [e.raw.split("\n")[0] for e in error_entries
                       if normalize(e.message.split("\n")[0]) == msg][:3]
            anomalies.append(Anomaly(
                anomaly_type=AnomalyType.REPEATED_ERROR,
                severity=Severity.HIGH if count >= 10 else Severity.MEDIUM,
                title=f"Repeated error ({count}x)",
                description=f"The same error appeared {count} times: \"{msg[:100]}...\"",
                evidence=samples,
                time_range=None,
            ))

    return anomalies


def _detect_resource_exhaustion(entries: list[LogEntry]) -> list[Anomaly]:
    """Detect resource exhaustion patterns (OOM, disk full, etc.)."""
    anomalies = []
    resource_keywords = {
        "memory": (r"out\s+of\s+memory|OOM|MemoryError", "Memory exhaustion detected"),
        "disk": (r"no\s+space\s+left|ENOSPC|disk\s+full", "Disk space exhaustion detected"),
        "connections": (r"too\s+many\s+(?:connections|open\s+files)|EMFILE", "Connection/file descriptor exhaustion"),
    }

    for resource, (pattern, desc) in resource_keywords.items():
        matching = [e for e in entries if re.search(pattern, e.message, re.I)]
        if matching:
            anomalies.append(Anomaly(
                anomaly_type=AnomalyType.RESOURCE_EXHAUSTION,
                severity=Severity.CRITICAL,
                title=f"{resource.title()} exhaustion",
                description=f"{desc}. Found {len(matching)} related entries.",
                evidence=[m.raw.split("\n")[0] for m in matching[:3]],
                time_range=None,
            ))

    return anomalies


def _fmt_duration(seconds: float) -> str:
    """Format seconds into human-readable duration."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{seconds/60:.0f}m {seconds%60:.0f}s"
    return f"{seconds/3600:.0f}h {(seconds%3600)/60:.0f}m"
