"""
Enterprise Knowledge Base RAG Q&A System — AI Service (FastAPI)

Entry point for the Python AI microservice.
Provides document parsing, embedding, vector search, and RAG chat.

Usage::

    python main.py              # start with .env defaults
    uvicorn main:app --reload   # dev mode
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    ai_router,
    create_health_router,
    documents_router,
)
from app.core.config import settings

# ============================================================
# Environment
# ============================================================

load_dotenv()

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="[%(asctime)s] %(levelname)s %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ============================================================
# Lifespan (startup / shutdown events)
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # ---- Startup ----
    logger.info("=" * 60)
    logger.info("[AI Service] Starting up ...")
    logger.info("[AI Service] Environment : %s", settings.ENV)
    logger.info("[AI Service] Port        : %s", settings.AI_SERVICE_PORT)
    logger.info("[AI Service] Embedding   : %s (dim=%d, device=%s)",
                settings.EMBEDDING_MODEL_NAME,
                settings.EMBEDDING_DIMENSION,
                settings.EMBEDDING_DEVICE)
    logger.info("[AI Service] LLM         : %s @ %s",
                settings.LLM_MODEL_NAME, settings.LLM_PROVIDER)
    logger.info("[AI Service] Chroma      : %s",
                settings.chroma_http_url)
    logger.info("[AI Service] MinIO       : %s (bucket=%s)",
                settings.MINIO_ENDPOINT, settings.MINIO_BUCKET)
    logger.info("=" * 60)

    # Initialize services (lazy, on first use)
    # - Embedding model will be loaded on first /ai/search or /ai/chat call
    # - Chroma client will be connected on first vector operation
    # - LLM client will be configured on first /ai/chat call

    yield

    # ---- Shutdown ----
    logger.info("[AI Service] Shutting down ...")


# ============================================================
# FastAPI Application
# ============================================================

app = FastAPI(
    title="Knowledge RAG AI Service",
    description=(
        "AI microservice for the Enterprise Knowledge Base RAG Q&A System. "
        "Provides document parsing, text chunking, embedding, "
        "vector search, and LLM-powered RAG chat."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.is_dev else None,
    redoc_url="/redoc" if settings.is_dev else None,
)

# ============================================================
# CORS Middleware
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id"],
)

# ============================================================
# Register Routers
# ============================================================

# Health check at root level
app.include_router(create_health_router())

# AI document parsing routes: /ai/documents/*
app.include_router(documents_router)

# AI routes: /ai/search, /ai/chat, /ai/models
app.include_router(ai_router)

# ============================================================
# Root Redirect
# ============================================================

@app.get("/", include_in_schema=False)
async def root():
    """Redirect root to docs in dev, or return service info in prod."""
    if settings.is_dev:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/docs")
    return {
        "service": "knowledge-rag-ai-service",
        "version": "1.0.0",
        "status": "running",
    }

# ============================================================
# Entry Point
# ============================================================

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.AI_SERVICE_PORT,
        reload=settings.is_dev,
        log_level=settings.LOG_LEVEL.lower(),
    )
