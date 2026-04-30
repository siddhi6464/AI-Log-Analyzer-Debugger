"""
LangChain agent orchestrator.
Creates a ReAct-style agent with custom tools for log analysis.
Supports batch and streaming modes.
"""

import json
from typing import AsyncGenerator
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from app.config import get_settings
from app.models import (
    AnalysisReport, AnalysisSummary, RootCauseSuggestion,
    Severity, LogEntry, LogLevel
)
from app.core.log_parser import parse_logs, get_log_summary, get_error_entries
from app.core.pattern_detector import detect_patterns
from app.core.anomaly_detector import detect_anomalies
from app.tools.parse_tool import parse_log_text
from app.tools.pattern_tool import detect_error_patterns
from app.tools.anomaly_tool import detect_log_anomalies
from app.tools.debug_tool import suggest_debug_actions


SYSTEM_PROMPT = """You are an expert DevOps/SRE log analyst AI. You analyze server and application logs to identify issues, detect anomalies, and suggest fixes.

You have access to these tools:
1. **parse_log_text** — Parse raw logs into structured entries and get summary stats
2. **detect_error_patterns** — Scan for known error patterns (network, memory, disk, auth, DB, HTTP, app)
3. **detect_log_anomalies** — Find statistical anomalies (error spikes, frequency bursts, time gaps, repeated errors)
4. **suggest_debug_actions** — Generate root-cause analysis and fix suggestions

## Analysis Workflow:
1. First, use parse_log_text to understand the log structure and content
2. Then, use detect_error_patterns to find known error signatures
3. Next, use detect_log_anomalies to spot statistical anomalies
4. Finally, use suggest_debug_actions with all the context gathered to provide root-cause analysis

## Output Requirements:
After using all tools, provide a comprehensive analysis that includes:
- Summary of findings
- Critical issues that need immediate attention
- Root cause analysis for each major error pattern
- Specific, actionable fix recommendations with priority
- Confidence levels for each suggestion

Be specific, technical, and actionable. Reference actual log lines when possible."""


def _get_llm():
    """Get the configured LLM instance."""
    settings = get_settings()
    if settings.llm_provider == "groq":
        return ChatGroq(
            model=settings.llm_model,
            api_key=settings.groq_api_key,
            temperature=0,
            max_tokens=4096,
        )
    else:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            temperature=0,
            max_tokens=4096,
        )


def _get_tools():
    """Get list of all available tools."""
    return [parse_log_text, detect_error_patterns, detect_log_anomalies, suggest_debug_actions]


async def analyze_logs_batch(log_text: str) -> AnalysisReport:
    """
    Run complete log analysis pipeline and return structured report.
    Uses LangChain agent with tool calling for AI-powered analysis.
    """
    # Step 1: Parse logs (direct, no LLM needed)
    entries, fmt = parse_logs(log_text)
    summary_data = get_log_summary(entries)
    error_entries = get_error_entries(entries)

    # Step 2: Detect patterns (direct)
    patterns = detect_patterns(log_text)

    # Step 3: Detect anomalies (direct)
    anomalies = detect_anomalies(entries)

    # Step 4: Get AI analysis via LLM with tool calling
    llm = _get_llm()
    tools = _get_tools()
    llm_with_tools = llm.bind_tools(tools)

    # Build context for the AI
    context = _build_analysis_context(summary_data, fmt, error_entries, patterns, anomalies)

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"""Analyze these logs and provide root-cause analysis with fix suggestions.

{context}

Based on all the findings above, provide:
1. Classification of each major error
2. Root cause analysis
3. Specific actionable fix for each issue
4. Confidence level and priority for each suggestion

Format your response as a detailed analysis report."""),
    ]

    # Invoke the LLM
    response = await llm_with_tools.ainvoke(messages)
    raw_analysis = response.content

    # Build suggestions from AI analysis
    suggestions = await _extract_suggestions(raw_analysis, patterns, llm)

    # Determine time span
    timestamps = [e.timestamp for e in entries if e.timestamp]
    time_span = None
    if timestamps:
        time_span = f"{timestamps[0]} → {timestamps[-1]}"

    return AnalysisReport(
        summary=AnalysisSummary(
            total_lines=len(entries),
            error_count=summary_data.get("error_count", 0),
            warning_count=summary_data.get("warning_count", 0),
            critical_count=summary_data.get("critical_count", 0),
            time_span=time_span,
            log_format=fmt,
        ),
        log_entries=error_entries[:50],
        patterns=patterns,
        anomalies=anomalies,
        suggestions=suggestions,
        raw_ai_analysis=raw_analysis,
    )


async def analyze_logs_stream(log_text: str) -> AsyncGenerator[dict, None]:
    """
    Stream analysis steps as SSE events.
    Yields dicts with event_type and data.
    """
    # Step 1: Parsing
    yield {"event_type": "status", "data": {"message": "Parsing log entries...", "step": 1, "total": 5}}

    entries, fmt = parse_logs(log_text)
    summary_data = get_log_summary(entries)
    error_entries = get_error_entries(entries)

    yield {"event_type": "parsed", "data": {
        "summary": summary_data,
        "format": fmt,
        "error_count": len(error_entries),
        "total_entries": len(entries),
        "step": 1, "total": 5,
    }}

    # Step 2: Pattern detection
    yield {"event_type": "status", "data": {"message": "Detecting error patterns...", "step": 2, "total": 5}}

    patterns = detect_patterns(log_text)

    yield {"event_type": "patterns", "data": {
        "patterns": [p.model_dump() for p in patterns],
        "count": len(patterns),
        "step": 2, "total": 5,
    }}

    # Step 3: Anomaly detection
    yield {"event_type": "status", "data": {"message": "Scanning for anomalies...", "step": 3, "total": 5}}

    anomalies = detect_anomalies(entries)

    yield {"event_type": "anomalies", "data": {
        "anomalies": [a.model_dump() for a in anomalies],
        "count": len(anomalies),
        "step": 3, "total": 5,
    }}

    # Step 4: AI Analysis
    yield {"event_type": "status", "data": {"message": "AI analyzing root causes...", "step": 4, "total": 5}}

    llm = _get_llm()
    context = _build_analysis_context(summary_data, fmt, error_entries, patterns, anomalies)

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Analyze these logs:\n\n{context}\n\nProvide root-cause analysis and fixes."),
    ]

    # Stream LLM response
    full_response = ""
    async for chunk in llm.astream(messages):
        if chunk.content:
            full_response += chunk.content
            yield {"event_type": "ai_chunk", "data": {"chunk": chunk.content, "step": 4, "total": 5}}

    # Step 5: Extract suggestions
    yield {"event_type": "status", "data": {"message": "Generating fix suggestions...", "step": 5, "total": 5}}

    suggestions = await _extract_suggestions(full_response, patterns, llm)

    timestamps = [e.timestamp for e in entries if e.timestamp]
    time_span = f"{timestamps[0]} → {timestamps[-1]}" if timestamps else None

    # Final complete report
    report = AnalysisReport(
        summary=AnalysisSummary(
            total_lines=len(entries),
            error_count=summary_data.get("error_count", 0),
            warning_count=summary_data.get("warning_count", 0),
            critical_count=summary_data.get("critical_count", 0),
            time_span=time_span,
            log_format=fmt,
        ),
        log_entries=error_entries[:50],
        patterns=patterns,
        anomalies=anomalies,
        suggestions=suggestions,
        raw_ai_analysis=full_response,
    )

    yield {"event_type": "complete", "data": report.model_dump(), "step": 5, "total": 5}


def _build_analysis_context(summary, fmt, errors, patterns, anomalies) -> str:
    """Build a text context for the LLM from analysis results."""
    parts = [f"## Log Summary\n- Format: {fmt}\n- Total lines: {summary['total_lines']}"]
    parts.append(f"- Errors: {summary.get('error_count', 0)}")
    parts.append(f"- Warnings: {summary.get('warning_count', 0)}")
    parts.append(f"- Critical: {summary.get('critical_count', 0)}")

    if patterns:
        parts.append("\n## Detected Patterns")
        for p in patterns:
            parts.append(f"- **{p.pattern_name}** [{p.severity.value}]: {p.count} occurrences")
            parts.append(f"  {p.description}")
            for s in p.sample_lines[:2]:
                parts.append(f"  > {s[:200]}")

    if anomalies:
        parts.append("\n## Detected Anomalies")
        for a in anomalies:
            parts.append(f"- **{a.title}** [{a.severity.value}]: {a.description}")

    if errors:
        parts.append("\n## Sample Error Entries")
        for e in errors[:15]:
            parts.append(f"- [{e.level.value}] {e.message[:200]}")

    return "\n".join(parts)


async def _extract_suggestions(ai_text: str, patterns, llm) -> list[RootCauseSuggestion]:
    """Extract structured suggestions from AI analysis text using structured output."""
    if not patterns and not ai_text.strip():
        return []

    from pydantic import BaseModel, Field
    from typing import List

    class SuggestionList(BaseModel):
        """List of root-cause suggestions."""
        suggestions: List[RootCauseSuggestion] = Field(description="List of root-cause fix suggestions")

    structured_llm = llm.with_structured_output(SuggestionList)

    try:
        result = await structured_llm.ainvoke(
            f"""Based on this log analysis, extract structured root-cause suggestions:

{ai_text[:3000]}

Detected patterns: {', '.join(p.pattern_name for p in patterns[:10])}

For each major issue found, provide:
- error_class: classification of the error
- root_cause: probable cause
- suggested_fix: specific actionable fix
- confidence: 0.0-1.0
- related_patterns: which patterns relate
- priority: low/medium/high/critical"""
        )
        return result.suggestions
    except Exception:
        # Fallback: create basic suggestions from patterns
        suggestions = []
        for p in patterns[:5]:
            suggestions.append(RootCauseSuggestion(
                error_class=p.pattern_category,
                root_cause=p.description,
                suggested_fix=f"Investigate {p.pattern_name}: {p.description}",
                confidence=0.7,
                related_patterns=[p.pattern_name],
                priority=p.severity,
            ))
        return suggestions
