"""
BM25 Index Manager

Provides per-knowledge-base BM25Okapi keyword-search indexes.
Uses jieba for Chinese word segmentation so that queries like
"机器学习" match documents containing "机器学习" as a compound term.

Each KB has its own in‑memory index.  The index is rebuilt on
document parse (Chapter 13 pipeline) and on document delete.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Optional

import jieba
from rank_bm25 import BM25Okapi

from app.services.chunker import Chunk

logger = logging.getLogger(__name__)


class BM25IndexManager:
    """
    Singleton manager for per‑KB BM25 indexes.

    Usage::

        mgr = BM25IndexManager.get_instance()

        # Build / rebuild
        mgr.build_index(kb_id=1, chunks=chunks)

        # Search
        results = mgr.search(kb_id=1, query="知识库系统", top_k=10)
        # → list of (Chunk, score)

        # Delete
        mgr.delete_index(kb_id=1)
    """

    _instance: Optional["BM25IndexManager"] = None

    def __init__(self) -> None:
        # kb_id → {"bm25": BM25Okapi, "chunks": list[Chunk]}
        self._indexes: dict[int, dict[str, Any]] = {}
        self._lock = threading.Lock()

    # ---- Singleton ----

    @classmethod
    def get_instance(cls) -> "BM25IndexManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ---- Public API ----

    def build_index(self, kb_id: int, chunks: list[Chunk]) -> None:
        """
        Build a BM25 index for *kb_id* from *chunks*.

        Replaces any existing index for the same KB.
        """
        if not chunks:
            logger.warning("BM25: no chunks for kb_id=%d — skipping", kb_id)
            return

        tokenized = [_tokenize(c.content) for c in chunks]
        bm25 = BM25Okapi(tokenized)

        with self._lock:
            self._indexes[kb_id] = {
                "bm25": bm25,
                "chunks": chunks,
            }

        logger.info(
            "BM25 index built: kb_id=%d, chunks=%d", kb_id, len(chunks),
        )

    def rebuild_for_kb(self, kb_id: int, chunks: list[Chunk]) -> None:
        """
        Rebuild the BM25 index for *kb_id*.

        Convenience alias for build_index — semantically clearer
        when replacing an existing index.
        """
        self.build_index(kb_id, chunks)

    def search(
        self, kb_id: int, query: str, top_k: int = 10,
    ) -> list[tuple[Chunk, float]]:
        """
        Search the BM25 index for *kb_id*.

        Args:
            kb_id: Knowledge base ID.
            query: Search query string.
            top_k: Max results to return.

        Returns:
            List of (Chunk, score) tuples sorted by relevance descending.
            Empty list if no index exists for this KB.
        """
        with self._lock:
            entry = self._indexes.get(kb_id)

        if entry is None:
            logger.warning("BM25: no index for kb_id=%d", kb_id)
            return []

        bm25: BM25Okapi = entry["bm25"]
        chunks: list[Chunk] = entry["chunks"]

        tokenized_query = _tokenize(query)
        scores = bm25.get_scores(tokenized_query)

        # Pair chunks with scores
        scored = list(zip(chunks, scores))
        scored.sort(key=lambda x: x[1], reverse=True)

        # Return top_k
        top = scored[:top_k]
        logger.debug(
            "BM25 search: kb_id=%d, query='%s', results=%d, top_score=%.4f",
            kb_id, query[:40], len(top), top[0][1] if top else 0.0,
        )
        return top

    def delete_index(self, kb_id: int) -> bool:
        """Remove the BM25 index for *kb_id*. Returns True if existed."""
        with self._lock:
            existed = kb_id in self._indexes
            if existed:
                del self._indexes[kb_id]
                logger.info("BM25 index deleted: kb_id=%d", kb_id)
            return existed

    def has_index(self, kb_id: int) -> bool:
        """Check whether an index exists for *kb_id*."""
        with self._lock:
            return kb_id in self._indexes

    def index_count(self, kb_id: int) -> int:
        """Return the number of chunks in the index for *kb_id*."""
        with self._lock:
            entry = self._indexes.get(kb_id)
            return len(entry["chunks"]) if entry else 0


# ============================================================
# Tokenization
# ============================================================

def _tokenize(text: str) -> list[str]:
    """
    Tokenize Chinese + English text with jieba.

    - Chinese: jieba.lcut (accurate word segmentation)
    - English: words preserved as-is by jieba
    - Punctuation: filtered out
    - Stop words: single characters removed (Chinese stop char heuristic)

    Returns a list of meaningful tokens.
    """
    # jieba.cut with search mode gives finer granularity for short queries
    tokens = jieba.lcut(text)

    # Filter: keep multi-char tokens OR alphanumeric tokens
    result: list[str] = []
    for t in tokens:
        t = t.strip()
        if not t:
            continue
        # Keep English words / numbers
        if t.isascii() and any(c.isalnum() for c in t):
            result.append(t.lower())
            continue
        # Keep Chinese words (2+ characters)
        if len(t) >= 2:
            result.append(t)

    return result or [text]  # fallback: raw text if all filtered


# ============================================================
# Module-level convenience
# ============================================================

def get_bm25_manager() -> BM25IndexManager:
    """Return the singleton BM25IndexManager."""
    return BM25IndexManager.get_instance()
