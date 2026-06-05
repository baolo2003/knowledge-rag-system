"""
Enterprise Knowledge Base RAG Q&A System - AI Service (FastAPI)
"""

import os
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables
load_dotenv()

APP_PORT = int(os.getenv("AI_SERVICE_PORT", "8000"))


# ============================================================
# Lifespan (startup / shutdown events)
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"[AI Service] Starting on port {APP_PORT} ...")
    print(f"[AI Service] Environment: {os.getenv('ENV', 'dev')}")
    yield
    # Shutdown
    print("[AI Service] Shutting down ...")


# ============================================================
# FastAPI Application
# ============================================================
app = FastAPI(
    title="Knowledge RAG AI Service",
    description="AI service for document parsing, embedding, and RAG-based Q&A",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Health Check
# ============================================================
@app.get("/health", tags=["System"])
async def health_check():
    """
    Health check endpoint.
    Returns service status and basic information.
    """
    return {
        "status": "ok",
        "service": "knowledge-rag-ai-service",
        "version": "1.0.0",
    }


# ============================================================
# Placeholder Routes (to be implemented)
# ============================================================
@app.get("/api/v1/ai/models", tags=["AI"])
async def list_models():
    """List available embedding / LLM models."""
    return {
        "embedding_models": [
            {"name": "bge-large-zh-v1.5", "dimension": 1024},
            {"name": "text2vec-large-chinese", "dimension": 1024},
        ],
        "llm_models": [
            {"name": "deepseek-chat", "provider": "deepseek"},
            {"name": "qwen-turbo", "provider": "alibaba"},
        ],
    }


# ============================================================
# Entry Point
# ============================================================
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=APP_PORT,
        reload=os.getenv("ENV", "dev") == "dev",
        log_level="info",
    )
