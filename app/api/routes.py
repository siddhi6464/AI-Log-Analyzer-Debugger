"""
FastAPI REST API routes.
Provides endpoints for batch analysis, streaming analysis,
sample log access, and health checks.
"""

import json
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from typing import Optional

from app.models import LogUploadRequest, AnalysisReport
from app.core.analyzer import analyze_logs_batch, analyze_logs_stream
from app.api.dependencies import get_llm_info

router = APIRouter()

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples"
STATIC_DIR = Path(__file__).parent.parent.parent / "static"


@router.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Serve the web dashboard."""
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return HTMLResponse(content=index_path.read_text(encoding="utf-8"))


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    llm_info = get_llm_info()
    return {
        "status": "ok",
        "llm": llm_info,
        "version": "1.0.0",
    }


@router.post("/api/analyze")
async def analyze_logs(request: LogUploadRequest):
    """
    Batch log analysis endpoint.
    Accepts raw log text and returns a complete AnalysisReport.
    """
    if not request.log_text.strip():
        raise HTTPException(status_code=400, detail="Log text cannot be empty")

    if len(request.log_text) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=413, detail="Log text exceeds 10MB limit")

    try:
        report = await analyze_logs_batch(request.log_text)
        return report.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/api/analyze/upload")
async def analyze_uploaded_file(file: UploadFile = File(...)):
    """
    Analyze an uploaded log file.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    content = await file.read()
    try:
        log_text = content.decode("utf-8")
    except UnicodeDecodeError:
        log_text = content.decode("latin-1")

    if not log_text.strip():
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    try:
        report = await analyze_logs_batch(log_text)
        return report.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/api/analyze/stream")
async def analyze_logs_streaming(request: LogUploadRequest):
    """
    Streaming log analysis via Server-Sent Events (SSE).
    Streams analysis steps in real-time.
    """
    if not request.log_text.strip():
        raise HTTPException(status_code=400, detail="Log text cannot be empty")

    async def event_generator():
        try:
            async for event in analyze_logs_stream(request.log_text):
                data = json.dumps(event, default=str)
                yield f"data: {data}\n\n"
        except Exception as e:
            error_event = json.dumps({
                "event_type": "error",
                "data": {"message": str(e)},
            })
            yield f"data: {error_event}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/samples")
async def list_samples():
    """List available sample log files."""
    if not SAMPLES_DIR.exists():
        return {"samples": []}

    samples = []
    for f in sorted(SAMPLES_DIR.glob("*.log")):
        stat = f.stat()
        samples.append({
            "name": f.name,
            "size_bytes": stat.st_size,
            "size_display": _fmt_size(stat.st_size),
        })

    return {"samples": samples}


@router.get("/api/samples/{name}")
async def get_sample(name: str):
    """Get the contents of a sample log file."""
    safe_name = Path(name).name  # Prevent path traversal
    file_path = SAMPLES_DIR / safe_name

    if not file_path.exists() or not file_path.suffix == ".log":
        raise HTTPException(status_code=404, detail=f"Sample '{name}' not found")

    content = file_path.read_text(encoding="utf-8")
    return {"name": safe_name, "content": content, "lines": content.count("\n") + 1}


def _fmt_size(size_bytes: int) -> str:
    """Format bytes to human-readable size."""
    for unit in ["B", "KB", "MB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} GB"
