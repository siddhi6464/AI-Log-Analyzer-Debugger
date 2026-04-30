"""LangChain tool: Anomaly detection."""

from langchain_core.tools import tool
from app.core.log_parser import parse_logs
from app.core.anomaly_detector import detect_anomalies


@tool
def detect_log_anomalies(log_text: str) -> str:
    """
    Detect statistical anomalies in log data including:
    - Error rate spikes (sudden increase in errors)
    - Frequency bursts (unusual log volume)
    - Time gaps (unexpected silence periods)
    - Repeated errors (same error recurring many times)
    - Resource exhaustion (OOM, disk full, connection limits)

    Args:
        log_text: Raw log text to analyze for anomalies.
    """
    entries, _ = parse_logs(log_text)
    anomalies = detect_anomalies(entries)

    return str({
        "anomaly_count": len(anomalies),
        "anomalies": [a.model_dump() for a in anomalies],
    })
