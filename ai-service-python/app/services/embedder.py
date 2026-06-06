"""
Embedding Service

Loads a sentence-transformers model and provides batch / single-query
embedding with L2 normalization.

After normalization:
    cosine_similarity(a, b) = dot(a, b)
This is Chroma's expected format when ``hnsw:space=cosine`` is set.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.config import settings

logger = logging.getLogger(__name__)


class Embedder:
    """
    Thin wrapper around sentence-transformers.

    Usage::

        embedder = Embedder.get_instance()
        vectors = embedder.embed(["文本1", "文本2"])          # batch
        vec     = embedder.embed_query("单个查询文本")        # single

    The model is loaded lazily on first use to keep startup fast.
    """

    _instance: Optional["Embedder"] = None

    def __init__(self) -> None:
        self._model: Optional[SentenceTransformer] = None
        self._model_name: str = settings.EMBEDDING_MODEL_NAME
        self._device: str = settings.EMBEDDING_DEVICE
        self._normalize: bool = settings.EMBEDDING_NORMALIZE
        self._batch_size: int = settings.EMBEDDING_BATCH_SIZE
        self._dimension: int = settings.EMBEDDING_DIMENSION
        self._loaded: bool = False

    # ---- Singleton ----

    @classmethod
    def get_instance(cls) -> "Embedder":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ---- Public API ----

    @property
    def dimension(self) -> int:
        """Return the embedding vector dimension."""
        return self._dimension

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def embed(self, texts: list[str]) -> np.ndarray:
        """
        Embed a batch of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            np.ndarray of shape ``(len(texts), dimension)``, dtype float32.
        """
        if not texts:
            return np.empty((0, self._dimension), dtype=np.float32)

        self._ensure_loaded()
        t0 = time.perf_counter()

        embeddings = self._model.encode(
            texts,
            batch_size=self._batch_size,
            show_progress_bar=False,
            normalize_embeddings=self._normalize,
            convert_to_numpy=True,
        )

        elapsed = (time.perf_counter() - t0) * 1000
        logger.debug(
            "Embedded %d texts in %.1f ms (%.1f ms/text)",
            len(texts), elapsed, elapsed / len(texts),
        )
        return embeddings  # type: ignore[return-value]

    def embed_query(self, text: str) -> np.ndarray:
        """
        Embed a single query text.

        Returns:
            np.ndarray of shape ``(dimension,)``, dtype float32.
        """
        vec = self.embed([text])
        return vec[0]

    # ---- Private ----

    def _ensure_loaded(self) -> None:
        """Lazy‑load the model on first use."""
        if self._loaded:
            return

        t0 = time.perf_counter()
        logger.info(
            "Loading embedding model: %s (device=%s) ...",
            self._model_name, self._device,
        )

        self._model = SentenceTransformer(
            self._model_name,
            device=self._device,
        )
        self._loaded = True

        # Validate dimension
        test_vec = self._model.encode(["test"], normalize_embeddings=False)
        actual_dim = test_vec.shape[1]
        if actual_dim != self._dimension:
            logger.warning(
                "Configured dimension=%d but model outputs %d — updating config",
                self._dimension, actual_dim,
            )
            self._dimension = actual_dim

        elapsed = (time.perf_counter() - t0) * 1000
        logger.info(
            "Embedding model loaded in %.0f ms | model=%s dim=%d device=%s",
            elapsed, self._model_name, self._dimension, self._device,
        )


# ============================================================
# Module-level convenience
# ============================================================

def get_embedder() -> Embedder:
    """Return the singleton Embedder instance."""
    return Embedder.get_instance()


def embed_texts(texts: list[str]) -> np.ndarray:
    """Convenience: batch embed."""
    return get_embedder().embed(texts)


def embed_query(text: str) -> np.ndarray:
    """Convenience: single query embed."""
    return get_embedder().embed_query(text)
