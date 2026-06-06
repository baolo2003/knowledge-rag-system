"""
Pydantic Request Schemas

Defines the shape of incoming API requests for:
- Parse  — document parsing trigger
- Search — semantic / hybrid search
- Chat   — RAG conversational Q&A
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ============================================================
# Parse
# ============================================================

class ParseRequest(BaseModel):
    """
    Request to parse a document that has been uploaded to MinIO.

    Example::

        {
          "doc_id": 42,
          "minio_path": "1/pdf/a1b2c3d4.pdf",
          "file_type": "pdf",
          "kb_id": 1
        }
    """

    doc_id: int = Field(
        ...,
        ge=1,
        description="文档 ID（document 表主键）",
        examples=[42],
    )
    minio_path: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="MinIO 对象存储路径",
        examples=["1/pdf/a1b2c3d4e5f6.pdf"],
    )
    file_type: str = Field(
        ...,
        pattern=r"^(pdf|docx|xlsx|txt|md)$",
        description="文件类型",
        examples=["pdf"],
    )
    kb_id: int = Field(
        ...,
        ge=1,
        description="所属知识库 ID",
        examples=[1],
    )


# ============================================================
# Search
# ============================================================

class SearchRequest(BaseModel):
    """
    Semantic / hybrid search request.

    Example::

        {
          "query": "什么是 RAG 系统？",
          "kb_id": 1,
          "top_k": 5,
          "similarity_threshold": 0.35,
          "hybrid_alpha": 0.5
        }
    """

    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="搜索查询文本",
        examples=["什么是 RAG 系统？"],
    )
    kb_id: int = Field(
        ...,
        ge=1,
        description="目标知识库 ID",
        examples=[1],
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=100,
        description="返回最相关的 top-k 个片段",
        examples=[5],
    )
    similarity_threshold: float = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
        description="相似度阈值（低于此值的结果被丢弃）",
        examples=[0.35],
    )
    hybrid_alpha: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description=(
            "混合检索权重。0 = 纯 BM25 关键词检索，"
            "0.5 = 向量 + BM25 均等混合，1 = 纯向量语义检索"
        ),
        examples=[0.5],
    )


# ============================================================
# Chat
# ============================================================

class ChatRequest(BaseModel):
    """
    RAG conversational chat request.

    Example::

        {
          "kb_id": 1,
          "question": "公司今年的战略目标是什么？",
          "conversation_id": 100,
          "history": [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好！有什么可以帮助你的？"}
          ],
          "top_k": 5,
          "temperature": 0.7
        }
    """

    class ChatMessage(BaseModel):
        """A single message in the conversation history."""
        role: str = Field(
            ...,
            pattern=r"^(user|assistant)$",
            description="消息角色",
        )
        content: str = Field(
            ...,
            min_length=1,
            description="消息内容",
        )

    kb_id: int = Field(
        ...,
        ge=1,
        description="目标知识库 ID",
        examples=[1],
    )
    question: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="当前用户提问",
        examples=["公司今年的战略目标是什么？"],
    )
    conversation_id: Optional[int] = Field(
        default=None,
        ge=1,
        description="会话 ID（可选，用于关联上下文）",
        examples=[100],
    )
    history: list[ChatMessage] = Field(
        default_factory=list,
        max_length=50,
        description="历史对话消息列表（最多 50 条）",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="检索相关片段数",
        examples=[5],
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="LLM 生成温度",
        examples=[0.7],
    )


# ============================================================
# Vector Delete (internal)
# ============================================================

class VectorDeleteRequest(BaseModel):
    """
    Request to delete all vectors for a document.
    Used internally by the Java backend after soft-delete.

    Example::

        {
          "doc_id": 42,
          "kb_id": 1
        }
    """

    doc_id: int = Field(..., ge=1, description="文档 ID")
    kb_id: int = Field(..., ge=1, description="知识库 ID")
