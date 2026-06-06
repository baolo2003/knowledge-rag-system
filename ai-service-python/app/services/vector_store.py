"""
Chroma Vector Store Service

Encapsulates Chroma operations for storing and querying document chunk embeddings.

Collection naming:  ``kb_{kb_id}``
HNSW index space:   cosine (compatible with L2-normalized embeddings from Embedder)

Metadata schema per chunk:
    document_id   (int)    — source document primary key
    kb_id         (int)    — knowledge base primary key
    file_name     (str)    — original filename
    chunk_index   (int)    — 0‑based position within document
    owner_id      (int)    — uploader user ID
    visibility    (str)    — PRIVATE | PUBLIC | ORG
    org_id        (int)    — organization ID (0 if not applicable)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import chromadb
from chromadb.api.types import Embedding, Metadata

from app.core.config import settings
from app.services.chunker import Chunk

logger = logging.getLogger(__name__)


class VectorStore:
    """
    Chroma vector store wrapper.

    Usage::

        store = VectorStore.get_instance()
        store.add_chunks(kb_id=1, chunks=chunks, metadatas=[...])
        store.delete_by_document_id(kb_id=1, doc_id=42)
    """

    _instance: Optional["VectorStore"] = None

    def __init__(self) -> None:
        self._client: Optional[chromadb.HttpClient] = None
        self._collection_prefix: str = settings.CHROMA_COLLECTION_PREFIX

    # ---- Singleton ----

    @classmethod
    def get_instance(cls) -> "VectorStore":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ---- Public API ----

    def add_chunks(
        self,
        kb_id: int,
        chunks: list[Chunk],
        file_name: str,
        owner_id: int,
        visibility: str,
        org_id: int,
    ) -> int:
        """
        Embed chunks and insert them into the Chroma collection for *kb_id*.

        Args:
            kb_id:      Knowledge base ID.
            chunks:     List of Chunk objects (carries content + chunk.index).
            file_name:  Original document filename.
            owner_id:   Uploader user ID.
            visibility: PRIVATE | PUBLIC | ORG.
            org_id:     Organization ID (0 if not applicable).

        Returns:
            Number of chunks inserted.
        """
        if not chunks:
            return 0

        collection = self._get_or_create_collection(kb_id)
        from app.services.embedder import get_embedder

        embedder = get_embedder()

        # Embed all chunk contents in one batch
        texts = [c.content for c in chunks]
        vectors: list[Embedding] = [
            vec.tolist() for vec in embedder.embed(texts)
        ]

        # Build Chroma IDs and metadatas
        ids: list[str] = []
        metadatas: list[Metadata] = []

        for chunk in chunks:
            chunk_id = f"doc_{chunk.index}"  # doc_{doc_id} or chunk-level ID
            ids.append(chunk_id)
            metadatas.append(
                _sanitize_metadata({
                    "document_id": chunk.index,  # will be overridden below
                    "kb_id": kb_id,
                    "file_name": file_name,
                    "chunk_index": chunk.index,
                    "owner_id": owner_id,
                    "visibility": visibility,
                    "org_id": org_id,
                })
            )

        # Note: Chroma's `add` takes a single `ids` list.
        # We use chunk.index directly in the ID but the real document_id
        # comes from the caller context.  Let's patch: the chunk_id should
        # incorporate the document ID for uniqueness across documents.
        # This is done in _build_ids when document_id is available.
        # For now, we use a caller-supplied document_id approach.
        # Actually, the cleanest way is to pass document_id to add_chunks.

        raise NotImplementedError(
            "Use add_chunks_full() which includes document_id"
        )

    def add_chunks_full(
        self,
        kb_id: int,
        document_id: int,
        chunks: list[Chunk],
        file_name: str,
        owner_id: int,
        visibility: str,
        org_id: int,
    ) -> int:
        """
        Full version of add_chunks — includes document_id for ID uniqueness.

        Args:
            kb_id:       Knowledge base ID.
            document_id: Document primary key.
            chunks:      Chunk objects with content and index.
            file_name:   Original filename.
            owner_id:    Uploader user ID.
            visibility:  PRIVATE | PUBLIC | ORG.
            org_id:      Organization ID (0 if not applicable).

        Returns:
            Number of chunks inserted.
        """
        if not chunks:
            return 0

        collection = self._get_or_create_collection(kb_id)
        from app.services.embedder import get_embedder

        embedder = get_embedder()
        texts = [c.content for c in chunks]
        vectors: list[Embedding] = [
            vec.tolist() for vec in embedder.embed(texts)
        ]

        ids: list[str] = []
        metadatas: list[Metadata] = []

        for chunk in chunks:
            # Globally unique ID: doc_{docId}_chunk_{chunkIndex}
            chunk_id = f"doc_{document_id}_chunk_{chunk.index}"
            ids.append(chunk_id)

            metadatas.append(
                _sanitize_metadata({
                    "document_id": document_id,
                    "kb_id": kb_id,
                    "file_name": file_name,
                    "chunk_index": chunk.index,
                    "owner_id": owner_id,
                    "visibility": visibility,
                    "org_id": org_id,
                })
            )

        logger.info(
            "Adding %d chunks to collection kb_%d (doc_id=%d)",
            len(chunks), kb_id, document_id,
        )

        collection.add(
            ids=ids,
            embeddings=vectors,
            documents=texts,
            metadatas=metadatas,
        )

        logger.info(
            "Chunks inserted: kb_id=%d, doc_id=%d, count=%d",
            kb_id, document_id, len(chunks),
        )
        return len(chunks)

    def delete_by_document_id(self, kb_id: int, document_id: int) -> int:
        """
        Delete all chunks belonging to *document_id* from the collection.

        Args:
            kb_id:       Knowledge base ID.
            document_id: Document primary key.

        Returns:
            Number of records deleted (estimated).
        """
        collection = self._get_collection(kb_id)
        if collection is None:
            logger.warning(
                "Collection kb_%d not found — nothing to delete", kb_id
            )
            return 0

        # Count before deletion
        try:
            before = collection.count()
        except Exception:
            before = 0

        collection.delete(
            where={"document_id": document_id},
        )

        try:
            after = collection.count()
        except Exception:
            after = 0

        deleted = before - after
        logger.info(
            "Deleted vectors: kb_id=%d, doc_id=%d, estimated_count=%d",
            kb_id, document_id, deleted,
        )
        return max(deleted, 0)

    def count(self, kb_id: int) -> int:
        """Return the number of chunks in a collection."""
        collection = self._get_collection(kb_id)
        if collection is None:
            return 0
        return collection.count()

    def query(
        self,
        kb_id: int,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> dict[str, Any]:
        """
        Query the vector store for similar chunks.

        Args:
            kb_id:           Knowledge base ID.
            query_embedding: Query vector (list of floats).
            top_k:           Number of results to return.

        Returns:
            Chroma query result dict with keys: ids, embeddings,
            documents, metadatas, distances.
        """
        collection = self._get_or_create_collection(kb_id)
        return collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

    # ----  Private ----

    def _get_or_create_collection(self, kb_id: int):
        """Get or create a Chroma collection for *kb_id*."""
        client = self._get_client()
        name = f"{self._collection_prefix}{kb_id}"

        collection = client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.debug("Collection ready: %s (count=%d)", name, collection.count())
        return collection

    def _get_collection(self, kb_id: int):
        """Get an existing collection, or None if it doesn't exist."""
        client = self._get_client()
        name = f"{self._collection_prefix}{kb_id}"

        try:
            return client.get_collection(name)
        except Exception:
            return None

    def _get_client(self) -> chromadb.HttpClient:
        """Lazy-init the Chroma HTTP client."""
        if self._client is None:
            self._client = chromadb.HttpClient(
                host=settings.CHROMA_HOST,
                port=settings.CHROMA_PORT,
            )
            logger.info(
                "Chroma client connected: %s:%d",
                settings.CHROMA_HOST, settings.CHROMA_PORT,
            )
        return self._client


# ============================================================
# Helpers
# ============================================================

def _sanitize_metadata(meta: dict[str, Any]) -> Metadata:
    """
    Ensure all metadata values are Chroma-compatible types:
    str | int | float | bool.

    Converts None to '' (empty string) and drops unsupported types.
    """
    clean: dict[str, Any] = {}
    for k, v in meta.items():
        if isinstance(v, (str, int, float, bool)):
            clean[k] = v
        elif v is None:
            clean[k] = ""
        else:
            clean[k] = str(v)
    return clean  # type: ignore[return-value]


# ============================================================
# Module-level convenience
# ============================================================

def get_vector_store() -> VectorStore:
    """Return the singleton VectorStore instance."""
    return VectorStore.get_instance()
