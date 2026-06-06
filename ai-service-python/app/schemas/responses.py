"""
Pydantic Response Schemas

Defines the shape of API responses for:
- ParseResult
- SearchResult
- ChatResult
- ErrorResult
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ============================================================
# Common / Shared
# ============================================================

class ChunkInfo(BaseModel):
    """Metadata for a single document chunk."""

    chunk_id: int = Field(..., description="切片 ID（document_chunk 表主键）")
    document_id: int = Field(..., description="所属文档 ID")
    chunk_index: int = Field(..., description="切片序号（从 0 开始）")
    content: str = Field(..., description="切片文本内容")
    token_count: int = Field(default=0, description="估算 token 数")


# ============================================================
# Parse
# ============================================================

class ParseResult(BaseModel):
    """
    Response returned after a document is parsed.

    Example::

        {
          "doc_id": 42,
          "status": "SUCCESS",
          "chunk_count": 0,
          "message": "文档解析完成 | 类型: PDF | 字符数: 15240",
          "text": "第一章 概述\\n1.1 项目背景...",
          "error": null
        }
    """

    doc_id: int = Field(..., description="文档 ID")
    status: str = Field(
        ...,
        description="解析状态: SUCCESS / FAILED",
        examples=["SUCCESS"],
    )
    chunk_count: int = Field(
        default=0,
        ge=0,
        description="生成的切片数量（含解析→切分→向量化→写入 Chroma 全流程）",
        examples=[25],
    )
    message: str = Field(
        default="",
        description="状态描述信息（含统计摘要）",
        examples=["文档解析完成 | 类型: PDF | 字符数: 15240 | 行数: 320 | 耗时: 42ms"],
    )
    text: str = Field(
        default="",
        description="提取的原始文本内容（后续章节会基于此进行切片和向量化）",
        examples=["第一章 概述\n1.1 项目背景\n..."],
    )
    error: Optional[str] = Field(
        default=None,
        description="失败时的错误详情（SUCCESS 时为 null）",
        examples=[None],
    )


# ============================================================
# Search
# ============================================================

class SearchChunk(BaseModel):
    """A single search result chunk with relevance metadata."""

    chunk: ChunkInfo = Field(..., description="切片信息")
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="相似度分数（0~1，越高越相关）",
    )
    document_name: str = Field(
        ...,
        description="所属文档文件名",
        examples=["产品手册_v2.0.pdf"],
    )
    document_id: int = Field(..., description="所属文档 ID")


class SearchResult(BaseModel):
    """
    Response returned for a semantic / hybrid search query.

    Example::

        {
          "query": "什么是 RAG？",
          "kb_id": 1,
          "total_hits": 25,
          "top_k": 5,
          "chunks": [ ... ],
          "search_time_ms": 42.5
        }
    """

    query: str = Field(..., description="原始搜索查询")
    kb_id: int = Field(..., description="搜索的知识库 ID")
    total_hits: int = Field(
        default=0,
        ge=0,
        description="符合相似度阈值的总命中数",
    )
    top_k: int = Field(..., description="请求的 top-k 值")
    chunks: list[SearchChunk] = Field(
        default_factory=list,
        description="排序后的 top-k 结果",
    )
    search_time_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="搜索耗时（毫秒）",
    )


# ============================================================
# Chat
# ============================================================

class ReferenceSource(BaseModel):
    """A source document cited in the LLM answer."""

    document_id: int = Field(..., description="文档 ID")
    document_name: str = Field(..., description="文档文件名")
    chunk_index: int = Field(..., description="引用片段序号")
    content_snippet: str = Field(
        ...,
        max_length=500,
        description="引用内容片段（截取前 500 字符）",
    )
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="该片段与问题的相似度",
    )


class ChatResult(BaseModel):
    """
    Response returned for a RAG conversational chat.

    Example::

        {
          "answer": "根据公司文档，今年的战略目标是...",
          "kb_id": 1,
          "conversation_id": 100,
          "sources": [ ... ],
          "token_usage": { "prompt_tokens": 512, "completion_tokens": 128 },
          "search_time_ms": 35.2,
          "generation_time_ms": 1200.5
        }
    """

    answer: str = Field(
        ...,
        description="LLM 生成的回答",
    )
    kb_id: int = Field(..., description="使用的知识库 ID")
    conversation_id: Optional[int] = Field(
        default=None,
        description="会话 ID",
    )
    sources: list[ReferenceSource] = Field(
        default_factory=list,
        description="引用的知识库来源列表",
    )
    token_usage: dict[str, int] = Field(
        default_factory=dict,
        description="Token 消耗统计: {prompt_tokens, completion_tokens, total_tokens}",
    )
    search_time_ms: float = Field(
        default=0.0,
        description="检索耗时（毫秒）",
    )
    generation_time_ms: float = Field(
        default=0.0,
        description="LLM 生成耗时（毫秒）",
    )


# ============================================================
# Error
# ============================================================

class ErrorResult(BaseModel):
    """Standard error response."""

    error: str = Field(..., description="错误类型")
    message: str = Field(..., description="错误详情")
    detail: Optional[Any] = Field(
        default=None,
        description="额外调试信息（仅 dev 环境返回）",
    )


# ============================================================
# Health
# ============================================================

class HealthResult(BaseModel):
    """Health check response."""

    status: str = Field(default="ok", description="服务状态")
    service: str = Field(..., description="服务名称")
    version: str = Field(..., description="服务版本")


# ============================================================
# Models (for /ai/models)
# ============================================================

class ModelInfo(BaseModel):
    """Model metadata."""

    name: str = Field(..., description="模型名称")
    provider: Optional[str] = Field(default=None, description="模型提供商")
    dimension: Optional[int] = Field(default=None, description="向量维度（Embedding 模型）")


class ModelsResult(BaseModel):
    """Available models listing."""

    embedding_models: list[ModelInfo] = Field(default_factory=list)
    llm_models: list[ModelInfo] = Field(default_factory=list)
