"""
Hybrid Retriever

Combines vector semantic search (Chroma) with keyword search (BM25)
via Reciprocal Rank Fusion (RRF), then applies permission filtering.

Pipeline::

    query
      ├─→ Embedder.embed_query() → Chroma.query()        (vector results)
      ├─→ BM25IndexManager.search()                       (keyword results)
      ├─→ _rrf_fusion(vec_results, bm25_results, k=60)   (merged ranking)
      └─→ _apply_permission_filter(merged, user, role)    (access control)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.services.bm25_index import BM25IndexManager, get_bm25_manager
from app.services.chunker import Chunk
from app.services.embedder import Embedder, get_embedder
from app.services.vector_store import VectorStore, get_vector_store

logger = logging.getLogger(__name__)


# ============================================================
# Result DTO
# ============================================================

class ScoredChunk:
    """A single search result after fusion."""

    __slots__ = (
        "chunk_id", "content", "score", "document_id", "document_name",
        "chunk_index", "kb_id", "owner_id", "visibility", "org_id",
    )

    def __init__(
        self,
        chunk_id: str,
        content: str,
        score: float,
        document_id: int,
        document_name: str,
        chunk_index: int,
        kb_id: int,
        owner_id: int,
        visibility: str,
        org_id: int,
    ) -> None:
        self.chunk_id = chunk_id
        self.content = content
        self.score = score
        self.document_id = document_id
        self.document_name = document_name
        self.chunk_index = chunk_index
        self.kb_id = kb_id
        self.owner_id = owner_id
        self.visibility = visibility
        self.org_id = org_id


# ============================================================
# HybridRetriever
# ============================================================

class HybridRetriever:
    """
    Hybrid retrieval combining vector + keyword search with RRF fusion.

    Usage::

        retriever = HybridRetriever()
        results = retriever.search(
            kb_id=1, query="知识库系统", top_k=5,
            user_id=10, role="USER", org_id=5,
        )
    """

    # RRF constant (standard value from literature)
    RRF_K: int = 60

    def __init__(
        self,
        embedder: Embedder | None = None,
        vector_store: VectorStore | None = None,
        bm25: BM25IndexManager | None = None,
    ) -> None:
        self._embedder = embedder or get_embedder()
        self._vector_store = vector_store or get_vector_store()
        self._bm25 = bm25 or get_bm25_manager()

    # ---- Public API ----

    def search(
        self,
        kb_id: int,
        query: str,
        top_k: int = 5,
        alpha: float = 0.5,
        similarity_threshold: float = 0.35,
        user_id: int = 0,
        role: str = "USER",
        org_id: int = 0,
    ) -> list[ScoredChunk]:
        """
        Execute hybrid search.

        Args:
            kb_id:                Knowledge base ID.
            query:                Search query text.
            top_k:                Number of results to return.
            alpha:                0=pure BM25, 0.5=hybrid, 1=pure vector.
            similarity_threshold: Minimum RRF score to include.
            user_id:              Current user ID (0 = anonymous).
            role:                 USER or ADMIN.
            org_id:               User's org ID.

        Returns:
            List of ScoredChunk sorted by relevance descending.
        """
        # ---- 1. Vector search ----
        vec_results: list[dict[str, Any]] = []
        if alpha > 0.0:  # vector contributes
            vec_results = self._vector_search(kb_id, query, top_k * 3)

        # ---- 2. BM25 keyword search ----
        bm25_results: list[tuple[Chunk, float]] = []
        if alpha < 1.0:  # BM25 contributes
            bm25_results = self._bm25_search(kb_id, query, top_k * 3)

        # ---- 3. RRF fusion ----
        fused = self._rrf_fusion(vec_results, bm25_results, alpha)

        # ---- 4. Permission filter ----
        filtered = self._apply_permission_filter(fused, user_id, role, org_id)

        # ---- 5. Threshold + top_k ----
        results = [
            c for c in filtered if c.score >= similarity_threshold
        ]
        results = results[:top_k]

        logger.info(
            "Hybrid search: kb_id=%d, query='%s', alpha=%.2f, "
            "vec=%d, bm25=%d, fused=%d, filtered=%d, final=%d",
            kb_id, query[:40], alpha,
            len(vec_results), len(bm25_results), len(fused),
            len(filtered), len(results),
        )

        return results

    # ============================================================
    # Private — Search
    # ============================================================

    def _vector_search(
        self, kb_id: int, query: str, top_k: int,
    ) -> list[dict[str, Any]]:
        """
        Execute vector similarity search via Chroma.

        Returns list of dicts with keys: id, content, distance, metadata.
        Distance from Chroma with cosine space is 1 - similarity,
        so we convert: similarity = 1 - distance.
        """
        try:
            q_vec = self._embedder.embed_query(query)
            chroma_result = self._vector_store.query(
                kb_id=kb_id,
                query_embedding=q_vec.tolist(),
                top_k=top_k,
            )
        except Exception as e:
            logger.warning("Vector search failed: %s", e)
            return []

        # Chroma returns nested lists (one per query)
        ids = chroma_result.get("ids", [[]])[0]
        documents = chroma_result.get("documents", [[]])[0]
        metadatas = chroma_result.get("metadatas", [[]])[0]
        distances = chroma_result.get("distances", [[]])[0]

        results: list[dict[str, Any]] = []
        for i in range(len(ids)):
            # cosine distance → similarity
            distance = distances[i] if i < len(distances) else 1.0
            similarity = 1.0 - float(distance)
            meta = metadatas[i] if i < len(metadatas) else {}

            results.append({
                "id": ids[i],
                "content": documents[i] if i < len(documents) else "",
                "score": max(0.0, min(1.0, similarity)),
                "metadata": meta,
            })

        return results

    def _bm25_search(
        self, kb_id: int, query: str, top_k: int,
    ) -> list[tuple[Chunk, float]]:
        """Execute BM25 keyword search."""
        try:
            return self._bm25.search(kb_id, query, top_k=top_k)
        except Exception as e:
            logger.warning("BM25 search failed: %s", e)
            return []

    # ============================================================
    # Private — RRF Fusion
    # ============================================================

    def _rrf_fusion(
        self,
        vec_results: list[dict[str, Any]],
        bm25_results: list[tuple[Chunk, float]],
        alpha: float,
    ) -> list[ScoredChunk]:
        """
        Reciprocal Rank Fusion.

        For each unique document, compute:
            score = alpha * vec_rrf + (1-alpha) * bm25_rrf
        where:
            rrf = 1 / (RRF_K + rank)

        Args:
            vec_results:  Vector search results (ranked).
            bm25_results: BM25 keyword results (ranked).
            alpha:        Weight: 0=pure BM25, 0.5=hybrid, 1=pure vector.

        Returns:
            List of ScoredChunk sorted by fused score descending.
        """
        from collections import defaultdict

        rrf_scores: dict[str, float] = defaultdict(float)
        chunk_map: dict[str, ScoredChunk] = {}

        # --- Vector RRF ---
        for rank, item in enumerate(vec_results, start=1):
            rrf = 1.0 / (self.RRF_K + rank)
            chunk_id = item["id"]
            meta = item.get("metadata", {})
            rrf_scores[chunk_id] += alpha * rrf

            if chunk_id not in chunk_map:
                chunk_map[chunk_id] = ScoredChunk(
                    chunk_id=chunk_id,
                    content=item.get("content", ""),
                    score=0.0,
                    document_id=int(meta.get("document_id", 0)),
                    document_name=str(meta.get("file_name", "")),
                    chunk_index=int(meta.get("chunk_index", 0)),
                    kb_id=int(meta.get("kb_id", 0)),
                    owner_id=int(meta.get("owner_id", 0)),
                    visibility=str(meta.get("visibility", "PRIVATE")),
                    org_id=int(meta.get("org_id", 0)),
                )

        # --- BM25 RRF ---
        for rank, (chunk, bm25_score) in enumerate(bm25_results, start=1):
            rrf = 1.0 / (self.RRF_K + rank)
            # Generate a stable chunk_id for BM25 results
            # Since BM25 chunks don't have document IDs embedded, we use index
            chunk_id = f"bm25_{chunk.index}"
            rrf_scores[chunk_id] += (1.0 - alpha) * rrf

            if chunk_id not in chunk_map:
                chunk_map[chunk_id] = ScoredChunk(
                    chunk_id=chunk_id,
                    content=chunk.content,
                    score=0.0,
                    document_id=0,
                    document_name="",
                    chunk_index=chunk.index,
                    kb_id=0,
                    owner_id=0,
                    visibility="PRIVATE",
                    org_id=0,
                )

        # --- Merge scores ---
        results: list[ScoredChunk] = []
        for chunk_id, fused_score in rrf_scores.items():
            c = chunk_map[chunk_id]
            c.score = round(fused_score, 6)
            results.append(c)

        results.sort(key=lambda x: x.score, reverse=True)
        return results

    # ============================================================
    # Private — Permission Filter
    # ============================================================

    def _apply_permission_filter(
        self,
        chunks: list[ScoredChunk],
        user_id: int,
        role: str,
        org_id: int,
    ) -> list[ScoredChunk]:
        """
        Filter chunks by visibility permissions.

        Rules:
        - ADMIN → see all
        - owner_id == user_id → allowed
        - visibility == PUBLIC → allowed
        - visibility == ORG AND org_id == user's org_id → allowed
        - Otherwise → blocked
        """
        # Admin bypass
        if role and role.upper() == "ADMIN":
            return chunks

        filtered: list[ScoredChunk] = []
        for c in chunks:
            if self._has_permission(c, user_id, org_id):
                filtered.append(c)

        return filtered

    def _has_permission(
        self, chunk: ScoredChunk, user_id: int, org_id: int,
    ) -> bool:
        """Check whether a user can access this chunk."""
        # Owner
        if user_id != 0 and chunk.owner_id == user_id:
            return True
        # Public
        if chunk.visibility == "PUBLIC":
            return True
        # Org
        if chunk.visibility == "ORG" and chunk.org_id != 0 and chunk.org_id == org_id:
            return True
        return False


# ============================================================
# Module-level convenience
# ============================================================

_retriever: Optional[HybridRetriever] = None


def get_retriever() -> HybridRetriever:
    """Return a cached HybridRetriever instance."""
    global _retriever
    if _retriever is None:
        _retriever = HybridRetriever()
    return _retriever
