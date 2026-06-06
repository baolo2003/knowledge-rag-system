"""
API Route Definitions

REST endpoints for the AI service.
Routes are registered as skeletons — implementations will be filled in
over subsequent chapters.
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException

from app.schemas.requests import (
    ChatRequest,
    ParseRequest,
    SearchRequest,
    VectorDeleteRequest,
)
from app.schemas.responses import (
    ChatResult,
    ErrorResult,
    HealthResult,
    ModelsResult,
    ParseResult,
    SearchResult,
)

logger = logging.getLogger(__name__)

# ============================================================
# Router instances
# ============================================================

# Main AI router (mounted at /ai)
ai_router = APIRouter(prefix="/ai", tags=["AI"])

# Document parsing sub-router
documents_router = APIRouter(prefix="/ai/documents", tags=["Documents"])


# ============================================================
# Health Check
# ============================================================

def create_health_router() -> APIRouter:
    """Create a health-check router that can be mounted at the app root."""
    router = APIRouter(tags=["System"])

    @router.get("/health", response_model=HealthResult)
    async def health_check():
        """Health check endpoint. Returns service status."""
        return HealthResult(
            status="ok",
            service="knowledge-rag-ai-service",
            version="1.0.0",
        )

    return router


# ============================================================
# Document Parsing
# ============================================================

@documents_router.post(
    "/parse",
    response_model=ParseResult,
    summary="解析文档",
    description="""
    解析已上传到 MinIO 的文档。

    处理流程（即将实现）:
    1. 从 MinIO 下载文件
    2. 根据 file_type 选择解析器提取文本
    3. 文本切片（按 CHUNK_SIZE / CHUNK_OVERLAP）
    4. 向量化（Embedding）
    5. 写入 Chroma 向量库
    6. 写入 document_chunk 表（MySQL）
    7. 回写 chunk_count 到 document 表
    """,
    responses={
        200: {"description": "解析成功"},
        400: {"model": ErrorResult, "description": "参数错误"},
        500: {"model": ErrorResult, "description": "解析失败"},
    },
)
async def parse_document(request: ParseRequest):
    """
    Parse an uploaded document.

    TODO: Chapter 12 — Implement document parser
    - PDF parser (pypdf)
    - DOCX parser (python-docx)
    - XLSX parser (openpyxl)
    - TXT / MD parser (plain text)
    """
    logger.info(
        "[SKELETON] parse_document: doc_id=%d, kb_id=%d, type=%s, path=%s",
        request.doc_id, request.kb_id, request.file_type, request.minio_path,
    )

    # Placeholder — will be implemented in Chapter 12
    _ = request  # suppress "unused" warning
    raise HTTPException(
        status_code=501,
        detail="Document parsing not yet implemented (Chapter 12)",
    )


@documents_router.post(
    "/vectors/delete",
    response_model=dict,
    summary="删除文档向量",
    description="删除指定文档在向量库中的所有向量数据。由 Java 后端在软删除文档时调用。",
    responses={
        200: {"description": "删除成功"},
        400: {"model": ErrorResult, "description": "参数错误"},
    },
)
async def delete_vectors(request: VectorDeleteRequest):
    """
    Delete all vectors for a document from the vector store.

    TODO: Chapter 14 — Implement vector deletion
    """
    logger.info(
        "[SKELETON] delete_vectors: doc_id=%d, kb_id=%d",
        request.doc_id, request.kb_id,
    )

    _ = request
    raise HTTPException(
        status_code=501,
        detail="Vector deletion not yet implemented (Chapter 14)",
    )


# ============================================================
# Semantic Search
# ============================================================

@ai_router.post(
    "/search",
    response_model=SearchResult,
    summary="语义 / 混合检索",
    description="""
    在指定知识库中执行语义搜索。

    支持两种检索模式（通过 hybrid_alpha 控制）:
    - alpha = 1.0: 纯向量语义检索
    - alpha = 0.0: 纯 BM25 关键词检索
    - alpha = 0.5: 混合检索（推荐）

    结果按相似度降序排列，低于 similarity_threshold 的被过滤。
    """,
    responses={
        200: {"description": "搜索完成"},
        400: {"model": ErrorResult, "description": "参数错误"},
    },
)
async def search(request: SearchRequest):
    """
    Execute semantic / hybrid search against the vector store.

    TODO: Chapter 13 — Implement search
    - Embed query text
    - Chroma similarity search
    - BM25 keyword search (optional, hybrid)
    - Merge & rerank results
    """
    logger.info(
        "[SKELETON] search: query='%s', kb_id=%d, top_k=%d, alpha=%.2f",
        request.query[:50], request.kb_id, request.top_k, request.hybrid_alpha,
    )

    _ = request
    raise HTTPException(
        status_code=501,
        detail="Search not yet implemented (Chapter 13)",
    )


# ============================================================
# RAG Chat
# ============================================================

@ai_router.post(
    "/chat",
    response_model=ChatResult,
    summary="RAG 对话",
    description="""
    基于知识库的 RAG 问答。

    处理流程（即将实现）:
    1. 将 question 向量化
    2. 在知识库中检索 top_k 个相关片段
    3. 构建 prompt（system_prompt + 检索上下文 + 对话历史 + 当前提问）
    4. 调用 LLM 生成回答
    5. 返回回答 + 引用来源 + token 统计
    """,
    responses={
        200: {"description": "对话完成"},
        400: {"model": ErrorResult, "description": "参数错误"},
        500: {"model": ErrorResult, "description": "LLM 调用失败"},
    },
)
async def chat(request: ChatRequest):
    """
    RAG conversational chat with LLM.

    TODO: Chapter 15 — Implement RAG chat
    - Embed question
    - Retrieve relevant chunks
    - Build RAG prompt
    - Call LLM
    - Return answer + sources
    """
    logger.info(
        "[SKELETON] chat: question='%s', kb_id=%d, history_len=%d",
        request.question[:50], request.kb_id, len(request.history),
    )

    _ = request
    raise HTTPException(
        status_code=501,
        detail="RAG chat not yet implemented (Chapter 15)",
    )


# ============================================================
# Models Info
# ============================================================

@ai_router.get(
    "/models",
    response_model=ModelsResult,
    summary="获取可用模型列表",
    description="返回当前配置的 Embedding 模型和 LLM 模型列表。",
)
async def list_models():
    """List available embedding and LLM models."""
    from app.schemas.responses import ModelInfo

    return ModelsResult(
        embedding_models=[
            ModelInfo(
                name="bge-large-zh-v1.5",
                provider="BAAI",
                dimension=1024,
            ),
            ModelInfo(
                name="text2vec-large-chinese",
                provider="shibing624",
                dimension=1024,
            ),
        ],
        llm_models=[
            ModelInfo(
                name="deepseek-chat",
                provider="DeepSeek",
            ),
            ModelInfo(
                name="qwen-turbo",
                provider="Alibaba",
            ),
            ModelInfo(
                name="gpt-4o",
                provider="OpenAI",
            ),
        ],
    )
