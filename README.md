# 🔍 AI Log Analyzer & Debugger

> AI-powered log analysis tool that ingests server/application logs, detects anomalies, classifies error patterns, and suggests root-cause fixes using LLM tool-calling with structured JSON outputs.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat&logo=fastapi&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-0.3+-1C3C3C?style=flat&logo=chainlink&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-API-F55036?style=flat)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Web Dashboard (HTML/CSS/JS)               │
│          Glassmorphism Dark UI · SSE Streaming               │
└───────────────┬────────────────────────┬────────────────────┘
                │  REST API              │  SSE Stream
┌───────────────▼────────────────────────▼────────────────────┐
│                    FastAPI Server                            │
│         POST /api/analyze  ·  POST /api/analyze/stream      │
└───────────────┬─────────────────────────────────────────────┘
                │
┌───────────────▼─────────────────────────────────────────────┐
│              LangChain Agent (ReAct Pattern)                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │ Parse    │ │ Pattern  │ │ Anomaly  │ │ Debug        │   │
│  │ Tool     │ │ Tool     │ │ Tool     │ │ Suggest Tool │   │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬───────┘   │
└───────┼─────────────┼───────────┼───────────────┼───────────┘
        │             │           │               │
┌───────▼─────────────▼───────────▼───────┐  ┌────▼────────┐
│         Core Processing Engine          │  │  Groq API   │
│  Log Parser · Pattern Detector          │  │  (LLM)      │
│  Anomaly Detector (Statistical)         │  └─────────────┘
└─────────────────────────────────────────┘
```

## Features

- **Multi-format log parsing**: Nginx, Python, Syslog, and generic timestamped logs
- **17+ error pattern signatures**: Network, memory, disk, auth, database, HTTP, application
- **Statistical anomaly detection**: Error spikes, frequency bursts, time gaps, repeated errors
- **AI root-cause analysis**: LLM-powered fix suggestions with confidence scores
- **Real-time SSE streaming**: Watch the AI analyze logs step-by-step
- **Premium dark dashboard**: Glassmorphism UI with neon accents and micro-animations
- **Structured JSON outputs**: All responses typed via Pydantic v2

## Quick Start

### 1. Install dependencies

```bash
cd "AI Log Analyzer & Debugger"
pip install -r requirements.txt
```

### 2. Configure API key

```bash
# Create .env file (or edit existing)
cp .env.example .env
# Add your Groq API key (free at https://console.groq.com)
```

### 3. Run the server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Open the dashboard

Navigate to **http://localhost:8000** in your browser.

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Web dashboard |
| `/health` | GET | Health check |
| `/api/analyze` | POST | Batch log analysis |
| `/api/analyze/stream` | POST | SSE streaming analysis |
| `/api/analyze/upload` | POST | Upload log file for analysis |
| `/api/samples` | GET | List sample log files |
| `/api/samples/{name}` | GET | Get sample log contents |

### Example: Batch Analysis

```bash
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"log_text": "2025-03-15 08:10:34,678 - app.database - ERROR - Connection refused"}'
```

## Tech Stack

- **Python 3.11+** — Core language
- **FastAPI** — Async REST API framework
- **LangChain + LangGraph** — AI agent orchestration
- **Groq API** — Ultra-fast LLM inference (Llama 3.3 70B)
- **Pydantic v2** — Structured JSON schema validation
- **SSE (Server-Sent Events)** — Real-time streaming
- **Vanilla HTML/CSS/JS** — Zero-dependency frontend

## License

MIT
