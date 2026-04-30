"""
FastAPI application entry point.
Mounts static files, includes API routes, configures CORS.
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables before anything else
load_dotenv()

from app.api.routes import router

app = FastAPI(
    title="AI Log Analyzer & Debugger",
    description="AI-powered log analysis tool that detects anomalies, classifies error patterns, and suggests root-cause fixes using LLM tool-calling.",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include API routes
app.include_router(router)
