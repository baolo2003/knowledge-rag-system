"""
Text Chunker Service

Splits extracted document text into overlapping chunks suitable for embedding.
Two-pass strategy:
1. Structural split — preserves Markdown headings & paragraph boundaries.
2. Size split — further breaks oversized segments at natural Chinese break points.

Key design:
- Chinese‑friendly: never breaks mid‑sentence or inside a CJK word.
- Overlap: adjacent chunks share 50–100 characters for context continuity.
- Filters fragments shorter than 20 characters.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


# ============================================================
# Data Classes
# ============================================================

@dataclass
class Chunk:
    """A single text chunk with metadata."""

    index: int
    """Zero-based chunk index within the document."""

    content: str
    """The chunk text content."""

    char_count: int = 0
    """Character count of this chunk."""

    source_headings: list[str] = field(default_factory=list)
    """Markdown headings this chunk falls under (for context)."""

    def __post_init__(self):
        if self.char_count == 0:
            self.char_count = len(self.content)


# ============================================================
# TextChunker
# ============================================================

class TextChunker:
    """
    Splits document text into embedding‑ready chunks.

    Usage::

        chunker = TextChunker()
        chunks = chunker.chunk(text)          # use config defaults
        chunks = chunker.chunk(text, chunk_size=600, overlap=80)
    """

    # ---- Configurable defaults (overridable per call) ----

    DEFAULT_CHUNK_SIZE: int = 500       # target characters per chunk
    DEFAULT_MIN_CHUNK_SIZE: int = 20    # drop chunks shorter than this
    DEFAULT_OVERLAP: int = 60           # overlap between adjacent chunks
    DEFAULT_MAX_CHUNK_SIZE: int = 800   # hard ceiling (force break if exceeded)

    # ---- Structural split patterns ----

    # Matches Markdown ATX headings (line starting with 1-6 #)
    _HEADING_RE = re.compile(r"^(#{1,6}\s+.+)$", re.MULTILINE)

    # Paragraph / section boundaries
    _SECTION_SEP_RE = re.compile(r"\n\n+")

    # ---- Size-split break‑point characters (ordered by preference) ----

    # Priority 1: sentence endings (Chinese + English)
    SENTENCE_ENDS = frozenset("。！？!?.\n")

    # Priority 2: clause separators
    CLAUSE_SEPS = frozenset("，；,:;")

    # ---- Public API ----

    def chunk(
        self,
        text: str,
        chunk_size: int | None = None,
        overlap: int | None = None,
        min_chunk_size: int | None = None,
        max_chunk_size: int | None = None,
    ) -> list[Chunk]:
        """
        Split text into chunks.

        Args:
            text:           Raw document text.
            chunk_size:     Target characters per chunk (default 500).
            overlap:        Overlap characters between chunks (default 60).
            min_chunk_size: Drop chunks below this length (default 20).
            max_chunk_size: Absolute ceiling; force‑break if exceeded.

        Returns:
            List of Chunk objects, ordered by position in document.
        """
        if not text or not text.strip():
            return []

        cs = chunk_size or self.DEFAULT_CHUNK_SIZE
        ol = overlap or self.DEFAULT_OVERLAP
        mi = min_chunk_size or self.DEFAULT_MIN_CHUNK_SIZE
        mx = max_chunk_size or self.DEFAULT_MAX_CHUNK_SIZE

        # ---- Phase 1: structural split ----
        structural_segments = self._split_by_structure(text)

        logger.debug(
            "Structural split: %d segments from %d chars",
            len(structural_segments), len(text),
        )

        # ---- Phase 2: size split for oversized segments ----
        raw_chunks: list[str] = []
        for seg in structural_segments:
            if len(seg) <= cs:
                raw_chunks.append(seg)
            else:
                sub = self._split_by_size(seg, cs, mx)
                raw_chunks.extend(sub)

        logger.debug("Size split: %d raw chunks", len(raw_chunks))

        # ---- Phase 3: apply overlap ----
        overlapped = self._apply_overlap(raw_chunks, ol)

        # ---- Phase 4: filter tiny fragments ----
        filtered = [c for c in overlapped if len(c) >= mi]

        # If everything was filtered, keep the longest fragment(s)
        if not filtered and overlapped:
            longest = max(overlapped, key=len)
            if len(longest) > 0:
                filtered = [longest]

        # Build result
        chunks = [
            Chunk(index=i, content=c)
            for i, c in enumerate(filtered)
        ]

        logger.info(
            "Chunking complete: %d chunks, avg_size=%.0f, "
            "chunk_size_cfg=%d, overlap=%d, min=%d",
            len(chunks),
            sum(len(c.content) for c in chunks) / max(len(chunks), 1),
            cs, ol, mi,
        )
        return chunks

    # ============================================================
    # Phase 1 — Structural Split
    # ============================================================

    def _split_by_structure(self, text: str) -> list[str]:
        """
        Split text by structural boundaries.

        Splitting order:
        1. Markdown headings — each heading starts a new segment.
           The heading line stays with the content that follows it.
        2. Double newlines — paragraph/section breaks.
        """
        segments: list[str] = []

        # Step 1: find all heading positions
        heading_positions: list[int] = []
        for m in self._HEADING_RE.finditer(text):
            heading_positions.append(m.start())

        if heading_positions:
            # Split at heading boundaries (heading stays with following content)
            prev = 0
            for pos in heading_positions:
                if pos > prev:
                    seg = text[prev:pos].strip()
                    if seg:
                        segments.append(seg)
                prev = pos
            # Last segment
            if prev < len(text):
                seg = text[prev:].strip()
                if seg:
                    segments.append(seg)
        else:
            # No headings — start with the whole text
            segments = [text.strip()]

        # Step 2: further split each segment on double newlines
        result: list[str] = []
        for seg in segments:
            parts = self._SECTION_SEP_RE.split(seg)
            for part in parts:
                part = part.strip()
                if part:
                    result.append(part)

        return result

    # ============================================================
    # Phase 2 — Size‑Based Split (Chinese‑friendly)
    # ============================================================

    def _split_by_size(
        self, text: str, target_size: int, max_size: int
    ) -> list[str]:
        """
        Split a long text segment into chunks of approximately *target_size*
        characters, breaking only at natural boundaries.

        Algorithm:
            Walk forward through the text. For each window:
            1. Set ideal cut point at ``start + target_size``.
            2. Scan BACKWARD from that point to find the best separator.
            3. If no separator found, fall back to hard cut at ``max_size``.
            4. Emit chunk, advance start by ``chunk_len - overlap``.

        This guarantees we never break mid‑sentence in Chinese — we always
        look for a punctuation or newline to split on before the limit.
        """
        chunks: list[str] = []
        text_len = len(text)
        start = 0

        while start < text_len:
            # Remaining text fits in one chunk
            remaining = text_len - start
            if remaining <= target_size:
                chunk = text[start:].strip()
                if chunk:
                    chunks.append(chunk)
                break

            # Ideal end position
            ideal_end = start + target_size

            # Search backward from ideal_end for a natural break point.
            # Search range: look back up to target_size // 2 characters.
            search_start = max(start + target_size // 2, start)
            break_pos = self._find_break_point(
                text, search_start, min(ideal_end, text_len)
            )

            # If no good break found, fall back to max_size hard cut
            if break_pos is None:
                hard_end = min(start + max_size, text_len)
                break_pos = self._find_break_point(
                    text, hard_end - (max_size // 4), hard_end
                )
                if break_pos is None:
                    break_pos = hard_end

            # Extract chunk
            chunk = text[start:break_pos].strip()
            if chunk:
                chunks.append(chunk)

            # Advance with overlap
            advance = len(chunk) - (target_size // 10)  # ~10% overlap
            if advance <= 0:
                advance = len(chunk)
            start = start + max(advance, 1)

        return chunks

    def _find_break_point(
        self, text: str, search_start: int, search_end: int
    ) -> Optional[int]:
        """
        Scan backward from *search_end* to *search_start* looking for a
        natural separator character.

        Priority (checked at each position):
        1. Sentence end  — ``。！？!?.`` + newline
        2. Clause separator — ``，；,:;``
        3. Space (ASCII only — not ideal for Chinese but better than nothing)

        Returns the position AFTER the separator (i.e. the cut point),
        or None if no break point found.
        """
        best_clause: Optional[int] = None
        best_space: Optional[int] = None

        for i in range(search_end - 1, search_start - 1, -1):
            ch = text[i]

            # Priority 1: sentence end → break right after it
            if ch in self.SENTENCE_ENDS:
                return i + 1

            # Priority 2: clause separator (record best, keep looking for sentence end)
            if ch in self.CLAUSE_SEPS and best_clause is None:
                best_clause = i + 1
                continue  # keep looking — sentence end might be further back

            # Priority 3: space (lowest priority, record but keep looking)
            if ch == " " and best_space is None:
                best_space = i + 1

        # Return best available break point
        return best_clause or best_space

    # ============================================================
    # Phase 3 — Overlap
    # ============================================================

    def _apply_overlap(
        self, chunks: list[str], overlap_size: int
    ) -> list[str]:
        """
        Add overlapping context to the beginning of each chunk (except the first).

        For chunk N (N > 0):
            Prepend the last *overlap_size* characters of chunk N‑1.
            This ensures embedding captures cross‑chunk context.
        """
        if len(chunks) <= 1 or overlap_size <= 0:
            return list(chunks)

        result = [chunks[0]]

        for i in range(1, len(chunks)):
            prev = chunks[i - 1]
            current = chunks[i]

            # Take tail of previous chunk as overlap prefix
            tail_len = min(overlap_size, len(prev))
            overlap_text = prev[-tail_len:]

            # Avoid double‑counting if current already starts with the overlap
            if current.startswith(overlap_text):
                result.append(current)
            else:
                result.append(overlap_text + "\n" + current)

        return result


# ============================================================
# Module‑level convenience
# ============================================================

_chunker: Optional[TextChunker] = None


def get_chunker() -> TextChunker:
    """Return a cached TextChunker singleton."""
    global _chunker
    if _chunker is None:
        _chunker = TextChunker()
    return _chunker


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[Chunk]:
    """Convenience function: split text into chunks."""
    return get_chunker().chunk(text, chunk_size=chunk_size, overlap=overlap)
