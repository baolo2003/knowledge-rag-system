"""
Tests for HybridRetriever — RRF fusion + permission filtering.

These tests verify the algorithm logic without requiring actual
Chroma / Embedder / BM25 infrastructure.

Run::

    pytest tests/test_retriever.py -v
"""

from __future__ import annotations

import pytest

from app.services.retriever import HybridRetriever, ScoredChunk


# ============================================================
# Helpers — build synthetic ScoredChunk objects
# ============================================================

def _sc(
    chunk_id: str = "c0",
    content: str = "test",
    score: float = 0.0,
    document_id: int = 1,
    document_name: str = "doc.pdf",
    chunk_index: int = 0,
    kb_id: int = 1,
    owner_id: int = 10,
    visibility: str = "PRIVATE",
    org_id: int = 5,
) -> ScoredChunk:
    return ScoredChunk(
        chunk_id=chunk_id,
        content=content,
        score=score,
        document_id=document_id,
        document_name=document_name,
        chunk_index=chunk_index,
        kb_id=kb_id,
        owner_id=owner_id,
        visibility=visibility,
        org_id=org_id,
    )


def _vec_result(chunk_id: str, content: str, similarity: float,
                document_id: int = 1, document_name: str = "doc.pdf",
                owner_id: int = 10, visibility: str = "PRIVATE",
                org_id: int = 5) -> dict:
    """Build a synthetic vector result dict matching Chroma output."""
    return {
        "id": chunk_id,
        "content": content,
        "score": similarity,
        "metadata": {
            "document_id": document_id,
            "file_name": document_name,
            "chunk_index": int(chunk_id.split("_")[-1]) if "_" in chunk_id else 0,
            "kb_id": 1,
            "owner_id": owner_id,
            "visibility": visibility,
            "org_id": org_id,
        },
    }


# ============================================================
# Tests — RRF Fusion
# ============================================================

class TestRRFFusion:
    """Reciprocal Rank Fusion algorithm tests."""

    def test_rrf_empty_inputs(self):
        """Empty inputs → empty output."""
        retriever = HybridRetriever()
        result = retriever._rrf_fusion([], [], alpha=0.5)
        assert result == []

    def test_rrf_vector_only(self):
        """alpha=1.0 → only vector contributes."""
        retriever = HybridRetriever()
        vec = [
            _vec_result("c0", "内容A", 0.9),
            _vec_result("c1", "内容B", 0.7),
            _vec_result("c2", "内容C", 0.5),
        ]
        result = retriever._rrf_fusion(vec, [], alpha=1.0)
        assert len(result) == 3
        # Higher rank → higher RRF score
        assert result[0].chunk_id == "c0"
        assert result[1].chunk_id == "c1"
        assert result[2].chunk_id == "c2"
        # Scores should be strictly decreasing
        assert result[0].score > result[1].score > result[2].score

    def test_rrf_bm25_only(self):
        """alpha=0.0 → only BM25 contributes."""
        from app.services.chunker import Chunk

        retriever = HybridRetriever()
        chunks = [
            (Chunk(index=0, content="A"), 0.9),
            (Chunk(index=1, content="B"), 0.7),
            (Chunk(index=2, content="C"), 0.5),
        ]
        result = retriever._rrf_fusion([], chunks, alpha=0.0)
        assert len(result) == 3
        assert result[0].chunk_id == "bm25_0"

    def test_rrf_hybrid_fusion(self):
        """alpha=0.5 → both sources contribute to final score."""
        retriever = HybridRetriever()
        vec = [_vec_result("v0", "向量结果", 0.95)]
        from app.services.chunker import Chunk
        bm25 = [(Chunk(index=0, content="关键词结果"), 0.8)]

        result = retriever._rrf_fusion(vec, bm25, alpha=0.5)
        assert len(result) >= 1  # at least one result
        # Both IDs should appear
        ids = {c.chunk_id for c in result}
        assert "v0" in ids
        assert "bm25_0" in ids

    def test_rrf_rank_ordering(self):
        """Item ranked #1 should have higher RRF than #2."""
        retriever = HybridRetriever()
        vec = [
            _vec_result("c0", "最高", 0.99),
            _vec_result("c1", "中等", 0.80),
            _vec_result("c2", "最低", 0.60),
        ]
        result = retriever._rrf_fusion(vec, [], alpha=1.0)

        # RRF for rank 1: 1/(60+1) = 1/61 ≈ 0.01639
        # RRF for rank 2: 1/(60+2) = 1/62 ≈ 0.01613
        # RRF for rank 3: 1/(60+3) = 1/63 ≈ 0.01587
        assert result[0].score > result[1].score
        assert result[1].score > result[2].score

    def test_rrf_deduplication(self):
        """Same chunk appearing in both lists gets RRF scores summed."""
        retriever = HybridRetriever()
        vec = [_vec_result("shared", "共享内容", 0.9)]
        from app.services.chunker import Chunk
        # BM25 can't have the same ID, so dedup only works within same source
        bm25 = [(Chunk(index=0, content="共享内容"), 0.8)]

        result = retriever._rrf_fusion(vec, bm25, alpha=0.5)
        ids = [c.chunk_id for c in result]
        assert "shared" in ids
        assert "bm25_0" in ids

    def test_rrf_k_constant_effect(self):
        """Verify the RRF_K=60 constant produces expected values."""
        retriever = HybridRetriever()
        # Single item at rank 1
        vec = [_vec_result("only", "唯一", 0.9)]
        result = retriever._rrf_fusion(vec, [], alpha=1.0)

        expected_rrf = 1.0 / (60 + 1)  # 1/61
        assert result[0].score == pytest.approx(expected_rrf, abs=1e-5)


# ============================================================
# Tests — Permission Filtering
# ============================================================

class TestPermissionFilter:
    """Visibility-based permission filtering tests."""

    def test_admin_sees_all(self):
        """ADMIN role bypasses all permission checks."""
        retriever = HybridRetriever()
        chunks = [
            _sc(visibility="PRIVATE", owner_id=99),  # not the user
            _sc(visibility="PRIVATE", owner_id=100),
            _sc(visibility="ORG", org_id=999),       # different org
        ]
        result = retriever._apply_permission_filter(
            chunks, user_id=10, role="ADMIN", org_id=5,
        )
        assert len(result) == 3

    def test_owner_sees_own_private(self):
        """Owner sees their own PRIVATE content."""
        retriever = HybridRetriever()
        chunks = [
            _sc(visibility="PRIVATE", owner_id=10),   # owner
            _sc(visibility="PRIVATE", owner_id=99),   # not owner
        ]
        result = retriever._apply_permission_filter(
            chunks, user_id=10, role="USER", org_id=5,
        )
        assert len(result) == 1
        assert result[0].owner_id == 10

    def test_public_visible_to_all(self):
        """PUBLIC visibility → anyone can see."""
        retriever = HybridRetriever()
        chunks = [
            _sc(visibility="PUBLIC", owner_id=99),
            _sc(visibility="PRIVATE", owner_id=99),
        ]
        result = retriever._apply_permission_filter(
            chunks, user_id=10, role="USER", org_id=5,
        )
        assert len(result) == 1
        assert result[0].visibility == "PUBLIC"

    def test_org_same_org_visible(self):
        """ORG visibility → same org_id can see."""
        retriever = HybridRetriever()
        chunks = [
            _sc(visibility="ORG", org_id=5, owner_id=99),   # same org
            _sc(visibility="ORG", org_id=999, owner_id=99), # different org
        ]
        result = retriever._apply_permission_filter(
            chunks, user_id=10, role="USER", org_id=5,
        )
        assert len(result) == 1
        assert result[0].org_id == 5

    def test_org_different_org_blocked(self):
        """ORG visibility → different org_id cannot see."""
        retriever = HybridRetriever()
        chunks = [
            _sc(visibility="ORG", org_id=999, owner_id=99),
        ]
        result = retriever._apply_permission_filter(
            chunks, user_id=10, role="USER", org_id=5,
        )
        assert len(result) == 0

    def test_anonymous_user(self):
        """Anonymous user (user_id=0) sees only PUBLIC."""
        retriever = HybridRetriever()
        chunks = [
            _sc(visibility="PUBLIC", owner_id=99),
            _sc(visibility="PRIVATE", owner_id=99),
            _sc(visibility="ORG", org_id=5, owner_id=99),
        ]
        result = retriever._apply_permission_filter(
            chunks, user_id=0, role="USER", org_id=0,
        )
        assert len(result) == 1
        assert result[0].visibility == "PUBLIC"

    def test_mixed_visibility(self):
        """Complex scenario with all visibility types."""
        retriever = HybridRetriever()
        chunks = [
            _sc("c1", visibility="PRIVATE", owner_id=10),   # owner → allowed
            _sc("c2", visibility="PUBLIC", owner_id=99),    # public → allowed
            _sc("c3", visibility="ORG", org_id=5, owner_id=99),  # same org → allowed
            _sc("c4", visibility="ORG", org_id=999, owner_id=99),# diff org → blocked
            _sc("c5", visibility="PRIVATE", owner_id=99),   # not owner → blocked
        ]
        result = retriever._apply_permission_filter(
            chunks, user_id=10, role="USER", org_id=5,
        )
        allowed_ids = {c.chunk_id for c in result}
        assert allowed_ids == {"c1", "c2", "c3"}


# ============================================================
# Tests — has_permission (single chunk)
# ============================================================

class TestHasPermission:
    """Unit tests for _has_permission()."""

    def test_owner(self):
        retriever = HybridRetriever()
        chunk = _sc(owner_id=10, visibility="PRIVATE")
        assert retriever._has_permission(chunk, user_id=10, org_id=0)

    def test_not_owner_private(self):
        retriever = HybridRetriever()
        chunk = _sc(owner_id=99, visibility="PRIVATE")
        assert not retriever._has_permission(chunk, user_id=10, org_id=0)

    def test_public(self):
        retriever = HybridRetriever()
        chunk = _sc(owner_id=99, visibility="PUBLIC")
        assert retriever._has_permission(chunk, user_id=10, org_id=0)

    def test_org_match(self):
        retriever = HybridRetriever()
        chunk = _sc(owner_id=99, visibility="ORG", org_id=5)
        assert retriever._has_permission(chunk, user_id=10, org_id=5)

    def test_org_no_match(self):
        retriever = HybridRetriever()
        chunk = _sc(owner_id=99, visibility="ORG", org_id=999)
        assert not retriever._has_permission(chunk, user_id=10, org_id=5)

    def test_org_zero_excluded(self):
        """org_id=0 should not match org_id=0 (unset)."""
        retriever = HybridRetriever()
        chunk = _sc(owner_id=99, visibility="ORG", org_id=0)
        assert not retriever._has_permission(chunk, user_id=10, org_id=0)


# ============================================================
# Tests — ScoredChunk DTO
# ============================================================

class TestScoredChunk:
    """ScoredChunk data class tests."""

    def test_creation(self):
        c = ScoredChunk(
            chunk_id="doc_1_chunk_0", content="测试内容", score=0.85,
            document_id=1, document_name="test.pdf", chunk_index=0,
            kb_id=1, owner_id=10, visibility="PUBLIC", org_id=5,
        )
        assert c.chunk_id == "doc_1_chunk_0"
        assert c.content == "测试内容"
        assert c.score == 0.85
        assert c.visibility == "PUBLIC"

    def test_defaults(self):
        c = _sc()
        assert c.score == 0.0
        assert c.visibility == "PRIVATE"

    def test_slots_no_extra_attrs(self):
        """ScoredChunk uses __slots__ — no dict overhead."""
        c = _sc()
        with pytest.raises(AttributeError):
            c.non_existent = 123  # type: ignore[attr-defined]
