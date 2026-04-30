"""
Pydantic models for structured JSON outputs.
These schemas define the contract between the LangChain agent,
FastAPI endpoints, and the frontend dashboard.
"""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime


# ── Enums ──────────────────────────────────────────────────────

class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnomalyType(str, Enum):
    ERROR_SPIKE = "error_spike"
    FREQUENCY_BURST = "frequency_burst"
    TIME_GAP = "time_gap"
    REPEATED_ERROR = "repeated_error"
    RESOURCE_EXHAUSTION = "resource_exhaustion"


# ── Core Models ────────────────────────────────────────────────

class LogEntry(BaseModel):
    """A single parsed log line."""
    line_number: int = Field(description="Original line number in the log file")
    timestamp: Optional[str] = Field(default=None, description="Extracted timestamp string")
    level: LogLevel = Field(default=LogLevel.UNKNOWN, description="Log severity level")
    source: Optional[str] = Field(default=None, description="Source component or module")
    message: str = Field(description="The log message content")
    raw: str = Field(description="Original raw log line")


class PatternMatch(BaseModel):
    """A detected error pattern with frequency data."""
    pattern_name: str = Field(description="Human-readable pattern name")
    pattern_category: str = Field(description="Category: network, memory, disk, auth, database, http, application")
    count: int = Field(description="Number of occurrences")
    severity: Severity = Field(description="Severity of this pattern")
    sample_lines: list[str] = Field(description="Up to 3 sample matching lines")
    description: str = Field(description="Brief description of what this pattern indicates")


class Anomaly(BaseModel):
    """A detected anomaly in log data."""
    anomaly_type: AnomalyType = Field(description="Type of anomaly detected")
    severity: Severity = Field(description="Severity level")
    title: str = Field(description="Short title for the anomaly")
    description: str = Field(description="Detailed description of the anomaly")
    evidence: list[str] = Field(description="Supporting log lines or statistics")
    time_range: Optional[str] = Field(default=None, description="Time window where anomaly was detected")


class RootCauseSuggestion(BaseModel):
    """AI-generated root-cause analysis and fix suggestion."""
    error_class: str = Field(description="Classification of the error type")
    root_cause: str = Field(description="Probable root cause explanation")
    suggested_fix: str = Field(description="Actionable fix recommendation")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0-1")
    related_patterns: list[str] = Field(description="Related pattern names that informed this suggestion")
    priority: Severity = Field(description="Fix priority level")


# ── Composite Report ──────────────────────────────────────────

class AnalysisSummary(BaseModel):
    """High-level summary statistics."""
    total_lines: int = Field(description="Total log lines processed")
    error_count: int = Field(description="Number of ERROR level entries")
    warning_count: int = Field(description="Number of WARNING level entries")
    critical_count: int = Field(description="Number of CRITICAL level entries")
    time_span: Optional[str] = Field(default=None, description="Time range of log data")
    log_format: str = Field(description="Detected log format type")


class AnalysisReport(BaseModel):
    """Complete analysis report combining all analysis results."""
    summary: AnalysisSummary = Field(description="High-level summary")
    log_entries: list[LogEntry] = Field(description="Parsed log entries (errors/warnings only)")
    patterns: list[PatternMatch] = Field(description="Detected error patterns")
    anomalies: list[Anomaly] = Field(description="Detected anomalies")
    suggestions: list[RootCauseSuggestion] = Field(description="AI root-cause suggestions")
    raw_ai_analysis: Optional[str] = Field(default=None, description="Raw AI analysis text")


# ── API Request/Response ──────────────────────────────────────

class LogUploadRequest(BaseModel):
    """Request body for log analysis."""
    log_text: str = Field(description="Raw log text to analyze")
    log_source: Optional[str] = Field(default="unknown", description="Source identifier")


class StreamEvent(BaseModel):
    """Server-Sent Event payload for streaming analysis."""
    event_type: str = Field(description="Event type: status, log_entry, pattern, anomaly, suggestion, complete, error")
    data: dict = Field(description="Event payload data")
    step: Optional[int] = Field(default=None, description="Step number in analysis pipeline")
    total_steps: Optional[int] = Field(default=None, description="Total number of steps")
