"""
API Route Definitions

REST endpoints for the AI service.
Chapter 14: Hybrid search (vector + BM25 → RRF fusion → permission filter).
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
    ChunkInfo,
    ErrorResult,
    HealthResult,
    ModelsResult,
    ParseResult,
    ReferenceSource,
    SearchChunk,
    SearchResult,
)
from app.services.bm25_index import get_bm25_manager
from app.services.chunker import chunk_text
from app.services.parser import (
    EmptyDocumentError,
    ParserError,
    UnsupportedFormatError,
    parse_document,
)
from app.services.retriever import get_retriever
from app.services.llm_client import get_llm_client
from app.services.prompt_builder import build_rag_prompt
from app.services.vector_store import get_vector_store
from app.utils.minio_client import MinioClient

logger = logging.getLogger(__name__)

# ============================================================
# Router instances
# ============================================================

ai_router = APIRouter(prefix="/ai", tags=["AI"])
documents_router = APIRouter(prefix="/ai/documents", tags=["Documents"])


# ============================================================
# Health Check
# ============================================================

def create_health_router() -> APIRouter:
    """Create a health-check router mounted at the app root."""
    router = APIRouter(tags=["System"])

    @router.get("/health", response_model=HealthResult)
    async def health_check():
        return HealthResult(
            status="ok",
            service="knowledge-rag-ai-service",
            version="1.0.0",
        )

    return router


# ============================================================
# Document Parsing — Full Pipeline (Chapter 13 + BM25 rebuild)
# ============================================================

@documents_router.post(
    "/parse",
    response_model=ParseResult,
    summary="解析文档（完整流水线 + BM25 索引）",
    description="""
    **完整处理流水线：**

    1. **MinIO 下载**
    2. **文本提取** (PDF/DOCX/XLSX/TXT/MD)
    3. **文本切分** (TextChunker)
    4. **向量化 + 写入 Chroma** (BGE-large-zh → kb_{id})
    5. **重建 BM25 索引** (jieba 分词 → BM25Okapi)

    每解析一个文档后自动重建该 KB 的 BM25 全文索引，
    确保混合检索始终使用最新数据。
    """,
    responses={
        200: {"description": "解析 + 向量化 + BM25 索引完成"},
        400: {"model": ErrorResult},
        404: {"model": ErrorResult},
        500: {"model": ErrorResult},
    },
)
async def parse_document(request: ParseRequest):
    """
    Full document parsing pipeline.

    parse → chunk → embed → Chroma → BM25 rebuild
    """
    t_total = time.perf_counter()

    logger.info(
        "解析请求: doc_id=%d, kb_id=%d, type=%s, file=%s",
        request.doc_id, request.kb_id, request.file_type, request.file_name,
    )

    # ---- Step 1: Download from MinIO ----
    t_step = time.perf_counter()
    minio = MinioClient.get_client()

    try:
        file_bytes = minio.download_file(request.minio_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404,
                            detail=f"文件不存在于 MinIO: {request.minio_path}")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=f"MinIO 下载失败: {e}")

    t_download = (time.perf_counter() - t_step) * 1000

    # ---- Step 2: Parse text ----
    t_step = time.perf_counter()

    try:
        raw_text = parse_document(file_bytes, request.file_type)
    except UnsupportedFormatError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except EmptyDocumentError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ParserError as e:
        raise HTTPException(status_code=500, detail=str(e))

    t_parse = (time.perf_counter() - t_step) * 1000
    text_length = len(raw_text)

    # ---- Step 3: Chunk ----
    t_step = time.perf_counter()
    chunks = chunk_text(raw_text)
    t_chunk = (time.perf_counter() - t_step) * 1000

    # ---- Step 4: Embed + Write to Chroma ----
    t_step = time.perf_counter()

    store = get_vector_store()
    written = store.add_chunks_full(
        kb_id=request.kb_id,
        document_id=request.doc_id,
        chunks=chunks,
        file_name=request.file_name or "unknown",
        owner_id=request.owner_id,
        visibility=request.visibility,
        org_id=request.org_id,
    )

    t_vector = (time.perf_counter() - t_step) * 1000

    # ---- Step 5: Rebuild BM25 index for this KB ----
    t_step = time.perf_counter()

    # Load ALL chunks for this KB and rebuild index
    bm25_mgr = get_bm25_manager()
    bm25_mgr.rebuild_for_kb(request.kb_id, chunks)
    # NOTE: In production, this should aggregate chunks from ALL documents
    # in the KB.  For now, we track chunks per-kb incrementally.
    # Future enhancement: store.fetch_all_chunks_for_kb(kb_id) → rebuild.

    t_bm25 = (time.perf_counter() - t_step) * 1000

    # ---- Step 6: Summary ----
    t_total_elapsed = (time.perf_counter() - t_total) * 1000

    logger.info(
        "全流水线完成: doc_id=%d, chunks=%d, "
        "download=%.0fms parse=%.0fms chunk=%.0fms vector=%.0fms bm25=%.0fms total=%.0fms",
        request.doc_id, written,
        t_download, t_parse, t_chunk, t_vector, t_bm25, t_total_elapsed,
    )

    return ParseResult(
        doc_id=request.doc_id,
        status="SUCCESS",
        chunk_count=written,
        message=(
            f"全流水线完成 | "
            f"类型: {request.file_type.upper()} | "
            f"文本: {text_length} 字符 | "
            f"切片: {len(chunks)} → {written} 写入 | "
            f"BM25: {len(chunks)} 条索引 | "
            f"下载: {t_download:.0f}ms | "
            f"解析: {t_parse:.0f}ms | "
            f"切分: {t_chunk:.0f}ms | "
            f"向量化: {t_vector:.0f}ms | "
            f"总耗时: {t_total_elapsed:.0f}ms"
        ),
        text="",
    )


# ============================================================
# Vector Deletion
# ============================================================

@documents_router.post(
    "/vectors/delete",
    response_model=dict,
    summary="删除文档向量",
    description="删除指定文档在 Chroma 向量库中的所有向量数据。",
    responses={
        200: {"description": "删除成功"},
        400: {"model": ErrorResult},
    },
)
async def delete_vectors(request: VectorDeleteRequest):
    """Delete all vectors for a document from Chroma."""
    logger.info("删除向量: doc_id=%d, kb_id=%d", request.doc_id, request.kb_id)

    store = get_vector_store()
    deleted = store.delete_by_document_id(
        kb_id=request.kb_id, document_id=request.doc_id,
    )

    return {
        "status": "ok",
        "doc_id": request.doc_id,
        "kb_id": request.kb_id,
        "deleted_count": deleted,
    }


# ============================================================
# Hybrid Search (Chapter 14 — IMPLEMENTED)
# ============================================================

@ai_router.post(
    "/search",
    response_model=SearchResult,
    summary="混合检索（向量 + BM25 → RRF 融合）",
    description="""
    **混合检索流水线：**

    1. **向量语义检索** — Embed query → Chroma similarity search
    2. **BM25 关键词检索** — jieba 分词 → BM25Okapi 索引查询
    3. **RRF 融合** — Reciprocal Rank Fusion (k=60)
       - `score = alpha * vec_rrf + (1-alpha) * bm25_rrf`
       - alpha=0 → 纯 BM25, alpha=1 → 纯向量
    4. **权限过滤** — 基于 owner_id / visibility / org_id
       - ADMIN → 查看全部
       - owner → 查看自己上传的
       - PUBLIC → 任何人可见
       - ORG → 同组织可见
    5. **Top-K + 阈值过滤**

    **返回结果** 按 RRF 融合分数降序排列。
    """,
    responses={
        200: {"description": "检索完成"},
        400: {"model": ErrorResult},
    },
)
async def search(request: SearchRequest):
    """Hybrid search: vector + BM25 → RRF fusion → permission filter."""
    t_start = time.perf_counter()

    logger.info(
        "混合检索: query='%s', kb_id=%d, top_k=%d, alpha=%.2f, user=%d, role=%s",
        request.query[:50], request.kb_id, request.top_k,
        request.hybrid_alpha, request.user_id, request.role,
    )

    retriever = get_retriever()
    results = retriever.search(
        kb_id=request.kb_id,
        query=request.query,
        top_k=request.top_k,
        alpha=request.hybrid_alpha,
        similarity_threshold=request.similarity_threshold,
        user_id=request.user_id,
        role=request.role,
        org_id=request.org_id,
    )

    elapsed_ms = (time.perf_counter() - t_start) * 1000

    # Convert to response DTOs
    chunks = [
        SearchChunk(
            chunk=ChunkInfo(
                chunk_id=i,
                document_id=r.document_id,
                chunk_index=r.chunk_index,
                content=r.content[:500],  # snippet (first 500 chars)
                token_count=len(r.content),
            ),
            score=r.score,
            document_name=r.document_name,
            document_id=r.document_id,
        )
        for i, r in enumerate(results)
    ]

    logger.info(
        "混合检索完成: query='%s', results=%d, elapsed=%.1fms",
        request.query[:30], len(chunks), elapsed_ms,
    )

    return SearchResult(
        query=request.query,
        kb_id=request.kb_id,
        total_hits=len(chunks),
        top_k=request.top_k,
        chunks=chunks,
        search_time_ms=round(elapsed_ms, 2),
    )


# ============================================================
# RAG Chat (Chapter 15 — IMPLEMENTED)
# ============================================================

@ai_router.post(
    "/chat",
    response_model=ChatResult,
    summary="RAG 智能问答",
    description="""
    **完整 RAG 对话流水线：**

    1. **混合检索** — HybridRetriever (向量 + BM25 → RRF → 权限过滤)
    2. **Prompt 组装** — PromptBuilder
       - System Prompt: 角色定义 + 规则约束 + 引用格式
       - 参考资料: 检索到的相关片段（编号 + 来源 + 相关度）
       - 对话历史: 前几轮 user/assistant 消息
       - 用户提问: 当前问题
    3. **LLM 生成** — DeepSeek (OpenAI 兼容)
       - temperature=0.3（知识问答场景低温度）
       - 返回 answer + token_usage

    **System Prompt 核心规则：**
    - 严格基于参考资料回答
    - 信息不足时明确说明
    - 禁止编造任何内容
    - 引用来源格式: `[来源N]`
    """,
    responses={
        200: {"description": "对话完成"},
        400: {"model": ErrorResult, "description": "参数错误"},
        500: {"model": ErrorResult, "description": "LLM 调用失败"},
    },
)
async def chat(request: ChatRequest):
    """
    RAG Chat — full implementation.

    retrieve → build prompt → LLM generate → return answer + sources
    """
    t_total = time.perf_counter()

    logger.info(
        "RAG 对话: kb_id=%d, question='%s', history=%d turns, user=%d",
        request.kb_id, request.question[:50], len(request.history),
        request.user_id,
    )

    # ---- Step 1: Retrieve relevant chunks ----
    t_search = time.perf_counter()

    retriever = get_retriever()
    retrieved = retriever.search(
        kb_id=request.kb_id,
        query=request.question,
        top_k=request.top_k,
        user_id=request.user_id,
        role=request.role,
        org_id=request.org_id,
    )

    t_search_ms = (time.perf_counter() - t_search) * 1000
    logger.info("检索完成: %d chunks, %.0fms", len(retrieved), t_search_ms)

    if not retrieved:
        return ChatResult(
            answer="根据现有资料，我无法回答这个问题。知识库中未检索到相关信息。",
            kb_id=request.kb_id,
            conversation_id=request.conversation_id,
            sources=[],
            token_usage={},
            search_time_ms=round(t_search_ms, 2),
            generation_time_ms=0,
        )

    # ---- Step 2: Build RAG prompt ----
    history_dicts = [
        {"role": h.role, "content": h.content}
        for h in request.history
    ] if request.history else None

    messages = build_rag_prompt(
        question=request.question,
        contexts=retrieved,
        history=history_dicts,
    )

    # ---- Step 3: Call LLM ----
    t_gen = time.perf_counter()

    try:
        llm = get_llm_client()
        answer, token_usage = llm.chat(
            messages=messages,
            temperature=request.temperature,
        )
    except Exception as e:
        logger.error("LLM 调用失败: %s", e)
        raise HTTPException(status_code=500, detail=f"LLM 调用失败: {e}")

    t_gen_ms = (time.perf_counter() - t_gen) * 1000

    # ---- Step 4: Build sources list ----
    sources = [
        ReferenceSource(
            document_id=r.document_id,
            document_name=r.document_name or f"文档#{r.document_id}",
            chunk_index=r.chunk_index,
            content_snippet=r.content[:500],
            score=r.score,
        )
        for r in retrieved
    ]

    t_total_ms = (time.perf_counter() - t_total) * 1000

    logger.info(
        "RAG 对话完成: answer_len=%d, sources=%d, "
        "search=%.0fms, gen=%.0fms, total=%.0fms, tokens=%s",
        len(answer), len(sources),
        t_search_ms, t_gen_ms, t_total_ms, token_usage,
    )

    return ChatResult(
        answer=answer,
        kb_id=request.kb_id,
        conversation_id=request.conversation_id,
        sources=sources,
        token_usage=token_usage,
        search_time_ms=round(t_search_ms, 2),
        generation_time_ms=round(t_gen_ms, 2),
    )


# ============================================================
# Models Info
# ============================================================

@ai_router.get(
    "/models",
    response_model=ModelsResult,
    summary="获取可用模型列表",
)
async def list_models():
    """List available embedding and LLM models."""
    from app.schemas.responses import ModelInfo

    return ModelsResult(
        embedding_models=[
            ModelInfo(name="bge-large-zh-v1.5", provider="BAAI", dimension=1024),
            ModelInfo(name="text2vec-large-chinese", provider="shibing624", dimension=1024),
        ],
        llm_models=[
            ModelInfo(name="deepseek-chat", provider="DeepSeek"),
            ModelInfo(name="qwen-turbo", provider="Alibaba"),
            ModelInfo(name="gpt-4o", provider="OpenAI"),
        ],
    )
