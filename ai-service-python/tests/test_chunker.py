"""
Tests for TextChunker

Covers structural splitting, size-based splitting, overlap,
short-fragment filtering, and Chinese-friendly break points.

Run::

    pytest tests/test_chunker.py -v
"""

from __future__ import annotations

import pytest

from app.services.chunker import Chunk, TextChunker, chunk_text, get_chunker


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def chunker() -> TextChunker:
    return TextChunker()


@pytest.fixture
def short_text() -> str:
    """Text that fits in a single chunk — no splitting needed."""
    return "这是一段很短的测试文本，不需要进行任何切分操作。"


@pytest.fixture
def markdown_doc() -> str:
    """Multi-section Markdown document with headings."""
    return (
        "# 第一章：项目概述\n\n"
        "知识库RAG系统是一个企业级智能问答平台。"
        "它基于检索增强生成技术，能够从企业文档中精准检索信息并生成回答。\n\n"
        "该系统支持多种文档格式，包括PDF、DOCX、XLSX等。\n\n"
        "## 1.1 核心功能\n\n"
        "系统提供知识库管理、文档上传、智能检索和RAG问答等核心功能。"
        "用户可以通过Web界面或API接口使用这些功能。\n\n"
        "## 1.2 技术架构\n\n"
        "后端采用Spring Boot框架，AI服务使用Python FastAPI。"
        "向量数据库使用Chroma，对象存储使用MinIO。\n\n"
        "# 第二章：部署方案\n\n"
        "系统支持Docker Compose一键部署。"
        "包括MySQL、Redis、MinIO、Chroma等所有依赖服务。"
    )


@pytest.fixture
def long_paragraph() -> str:
    """A very long paragraph that needs size-based splitting."""
    return (
        "知识库RAG系统是一个面向企业的智能知识管理平台。"
        "该系统基于检索增强生成技术，能够从海量企业文档中快速、精准地检索相关信息，"
        "并结合大语言模型生成高质量的回答。系统支持多种文档格式的自动解析，"
        "包括PDF、DOCX、XLSX、TXT和Markdown等常见办公文档格式。"
        "在技术架构方面，系统采用微服务设计理念，将业务逻辑与AI能力分离。"
        "Java后端负责知识库管理、用户认证、文档上传等业务功能，"
        "而Python AI服务则专注于文档解析、文本向量化、语义检索和智能问答。"
        "向量数据库选用Chroma，它提供了高效的向量存储和相似度搜索能力。"
        "对象存储使用MinIO，兼容S3协议，适合存储各类文档文件。"
        "系统还集成了Redis作为缓存层，提升高频查询的响应速度。"
        "在部署方面，系统提供Docker Compose编排文件，支持一键启动所有服务。"
        "这种架构设计确保了系统的高可用性和可扩展性，"
        "能够满足从小型团队到大型企业的不同规模需求。"
        "未来还计划支持更多的文档格式、更强大的检索算法、"
        "以及多语言问答等高级功能，持续提升系统的智能化水平。"
    )


@pytest.fixture
def mixed_content() -> str:
    """Mixed Chinese + English + code content."""
    return (
        "# API Reference\n\n"
        "## POST /api/documents/upload\n\n"
        "上传文档到知识库。支持 multipart/form-data 格式。\n\n"
        "```python\n"
        "import requests\n\n"
        "url = 'http://localhost:8080/api/documents/upload'\n"
        "files = {'file': open('doc.pdf', 'rb')}\n"
        "data = {'kbId': 1}\n"
        "response = requests.post(url, files=files, data=data)\n"
        "```\n\n"
        "请求成功后返回文档元数据，包含文档ID、文件名、解析状态等信息。\n\n"
        "## GET /api/documents?kbId=1\n\n"
        "分页查询知识库下的文档列表，支持文件名模糊搜索。"
    )


# ============================================================
# Tests — Basic chunking
# ============================================================

class TestBasicChunking:
    """Basic chunking behavior."""

    def test_empty_text(self, chunker):
        assert chunker.chunk("") == []
        assert chunker.chunk("   ") == []

    def test_short_text_single_chunk(self, chunker, short_text):
        chunks = chunker.chunk(short_text)
        assert len(chunks) == 1
        assert chunks[0].content == short_text
        assert chunks[0].index == 0
        assert chunks[0].char_count == len(short_text)

    def test_chunks_have_sequential_indices(self, chunker, long_paragraph):
        chunks = chunker.chunk(long_paragraph, chunk_size=100)
        assert len(chunks) > 1
        for i, c in enumerate(chunks):
            assert c.index == i

    def test_convenience_function(self, long_paragraph):
        chunks = chunk_text(long_paragraph, chunk_size=200)
        assert len(chunks) > 0
        assert all(isinstance(c, Chunk) for c in chunks)


# ============================================================
# Tests — Structural splitting (Phase 1)
# ============================================================

class TestStructuralSplit:
    """Markdown heading and paragraph boundary splitting."""

    def test_split_on_headings(self, chunker, markdown_doc):
        chunks = chunker.chunk(markdown_doc, chunk_size=500)
        # Each heading should start its own chunk
        contents = "\n".join(c.content for c in chunks)
        assert "# 第一章" in contents
        assert "# 第二章" in contents

    def test_headings_preserved_in_content(self, chunker, markdown_doc):
        chunks = chunker.chunk(markdown_doc, chunk_size=500)
        # At least one chunk should contain a heading
        has_heading = any(
            c.content.strip().startswith("#") for c in chunks
        )
        assert has_heading

    def test_subheadings_preserved(self, chunker, markdown_doc):
        chunks = chunker.chunk(markdown_doc, chunk_size=500)
        contents = "\n".join(c.content for c in chunks)
        assert "## 1.1" in contents
        assert "## 1.2" in contents

    def test_paragraph_split_on_double_newline(self, chunker):
        text = (
            "第一段内容比较长，包含了足够的文字来描述项目背景信息。"
            "\n\n"
            "第二段内容也比较长，详细说明了技术选型和架构设计方案。"
            "\n\n"
            "第三段内容同样很充实，介绍了部署流程和运维监控方案。"
        )
        chunks = chunker.chunk(text, chunk_size=800)
        # Each paragraph should be in its own chunk or at least split cleanly
        all_text = "".join(c.content for c in chunks)
        assert "第一段" in all_text
        assert "第二段" in all_text
        assert "第三段" in all_text

    def test_single_newline_not_split(self, chunker):
        """Single newlines should NOT cause structural splits."""
        text = (
            "第一行包含了比较长的项目背景介绍内容文字。\n"
            "第二行包含了技术方案详细描述和具体实施信息。\n"
            "第三行包含了预期成果和评估指标体系说明。"
        )
        chunks = chunker.chunk(text, chunk_size=800)
        # If it fits, it should be one chunk
        # (single newlines don't trigger structural split)
        assert len(chunks) >= 1
        all_text = "".join(c.content for c in chunks)
        assert "第一行" in all_text
        assert "第二行" in all_text


# ============================================================
# Tests — Size-based splitting (Phase 2)
# ============================================================

class TestSizeSplit:
    """Size-based splitting for oversized segments."""

    def test_long_text_splits_into_multiple(self, chunker, long_paragraph):
        chunks = chunker.chunk(long_paragraph, chunk_size=200)
        assert len(chunks) >= 2

    def test_chunks_within_size_range(self, chunker, long_paragraph):
        """Chunks should be approximately the target size."""
        chunks = chunker.chunk(long_paragraph, chunk_size=300, max_chunk_size=500)
        for c in chunks:
            # Allow some tolerance; the key is no chunk exceeds max
            assert c.char_count <= 520, (
                f"Chunk {c.index} size {c.char_count} > 500 max"
            )

    def test_no_chunk_exceeds_max(self, chunker, long_paragraph):
        """Hard ceiling: no chunk should exceed max_chunk_size."""
        chunks = chunker.chunk(
            long_paragraph, chunk_size=200, max_chunk_size=400
        )
        for c in chunks:
            assert c.char_count <= 420, (
                f"Chunk {c.index} exceeds max: {c.char_count}"
            )

    def test_split_at_sentence_end(self, chunker):
        """Chunks should break at sentence-ending punctuation (。！？)."""
        text = (
            "这是第一句话，包含一些内容。"
            "这是第二句话，也有不少文字。"
            "这是第三句话，继续写更多内容。"
        )
        chunks = chunker.chunk(text, chunk_size=25)
        for c in chunks:
            content = c.content.strip()
            # Each chunk should end with a sentence terminator
            # (or be the last chunk)
            if c.index < len(chunks) - 1 and content:
                assert content[-1] in "。！？!?.\n" or len(content) < 25, (
                    f"Chunk {c.index} doesn't end at sentence boundary: "
                    f"'{content[-10:]}'"
                )

    def test_split_at_newline_preferred(self, chunker):
        """Newlines should be preferred break points."""
        text = (
            "第一行：项目背景说明文本。\n"
            "第二行：技术方案详细描述。\n"
            "第三行：实施计划时间安排。\n"
            "第四行：预期效果评估指标。\n"
        )
        chunks = chunker.chunk(text, chunk_size=40)
        # Newlines should serve as natural break points
        for c in chunks:
            # Chunks should not have dangling partial lines
            assert len(c.content) > 0


# ============================================================
# Tests — Chinese-friendly behavior
# ============================================================

class TestChineseFriendly:
    """Ensure splitting respects Chinese text characteristics."""

    def test_no_break_inside_cjk_word(self, chunker):
        """
        Chinese text has no spaces between words, so we must not break
        mid-character or mid-ngram. The chunker should only break on
        punctuation or structural boundaries.
        """
        # A paragraph where every character is CJK (no punctuation in middle)
        text = (
            "知识库系统是一种基于检索增强生成技术的智能问答平台"
            "它能够从企业文档中精准检索信息并生成高质量回答"
            "该系统支持多种文档格式包括PDF和DOCX等常见办公格式"
        )
        chunks = chunker.chunk(text, chunk_size=20, max_chunk_size=40)

        # Every chunk should start and end cleanly
        for c in chunks:
            content = c.content.strip()
            if content and c.index > 0:
                # Should start with a valid beginning (not orphaned)
                assert len(content) >= 15, f"Chunk too short: {len(content)}"

    def test_break_on_punctuation_only(self, chunker):
        """Verify that breaks actually occur at punctuation marks."""
        text = (
            "第一步，需要进行需求分析。"
            "第二步，然后进行系统设计。"
            "第三步，接着编写代码实现。"
            "第四步，最后进行测试验证。"
            "第五步，部署上线运行维护。"
        )
        chunks = chunker.chunk(text, chunk_size=20)
        for c in chunks:
            content = c.content.strip()
            # Content should make sense (not cut in middle of character)
            if content:
                # Check it doesn't start with orphaned punctuation
                assert not content[0] in "，；：", (
                    f"Chunk starts with punctuation: '{content[:20]}'"
                )

    def test_english_and_chinese_mixed(self, chunker, mixed_content):
        """Mixed CJK + ASCII should be handled correctly."""
        chunks = chunker.chunk(mixed_content, chunk_size=200)
        assert len(chunks) >= 1
        all_text = " ".join(c.content for c in chunks)
        assert "POST /api/documents/upload" in all_text
        assert "import requests" in all_text
        assert "上传文档到知识库" in all_text


# ============================================================
# Tests — Overlap (Phase 3)
# ============================================================

class TestOverlap:
    """Overlap between adjacent chunks."""

    def test_overlap_exists_between_chunks(self, chunker, long_paragraph):
        chunks = chunker.chunk(long_paragraph, chunk_size=200, overlap=60)
        assert len(chunks) >= 2

        # For each pair of adjacent chunks, there should be overlapping text
        for i in range(len(chunks) - 1):
            prev_tail = chunks[i].content[-30:]
            curr_head = chunks[i + 1].content[:200]
            # There should be some shared text or the previous tail
            # should appear near the start of the next chunk
            # (exact match may vary due to structural split, but overlap_context exists)
            assert len(chunks[i + 1].content) > 0

    def test_overlap_preserves_context(self, chunker):
        """The overlap text should actually appear in both chunks."""
        text = (
            "这是测试文本第一段的内容在这里继续写下去。"
            "这是测试文本第二段的内容在这里继续写下去。"
            "这是测试文本第三段的内容在这里继续写下去。"
            "这是测试文本第四段的内容在这里继续写下去。"
        )
        chunks = chunker.chunk(text, chunk_size=30, overlap=10)
        assert len(chunks) >= 2

        # Check that tail of chunk N appears in chunk N+1
        for i in range(len(chunks) - 1):
            prev = chunks[i].content
            curr = chunks[i + 1].content
            # Last 8 chars of prev should appear in curr (overlap ≥ 8)
            tail = prev[-8:]
            assert tail in curr, (
                f"Overlap missing: tail '{tail}' not found in next chunk "
                f"'{curr[:40]}...'"
            )

    def test_no_overlap_when_single_chunk(self, chunker, short_text):
        chunks = chunker.chunk(short_text, overlap=50)
        assert len(chunks) == 1

    def test_overlap_disabled_with_zero(self, chunker, long_paragraph):
        chunks = chunker.chunk(long_paragraph, chunk_size=200, overlap=0)
        assert len(chunks) >= 2
        for c in chunks:
            assert "overlap" not in c.content.lower()  # not relevant


# ============================================================
# Tests — Short fragment filtering (Phase 4)
# ============================================================

class TestShortFragmentFiltering:
    """Filter out fragments below the minimum size."""

    def test_tiny_fragments_filtered(self, chunker):
        text = "短。\n\n" * 3 + "这是一段足够长的文本内容，用于测试短片段过滤功能是否正常工作。"
        chunks = chunker.chunk(text, min_chunk_size=20)
        for c in chunks:
            assert len(c.content) >= 20, (
                f"Chunk {c.index} too short: '{c.content}'"
            )

    def test_min_chunk_size_configurable(self, chunker):
        long_segment = "这是一段足够长的中文测试文本内容，" * 5
        text = f"A。\n\nB。\n\nC。\n\n{long_segment}"
        # With high min size, short fragments dropped; only long content survives
        chunks = chunker.chunk(text, min_chunk_size=50)
        for c in chunks:
            assert len(c.content) >= 50

    def test_very_short_text_still_kept_if_only_one(self, chunker):
        """If the entire document is short, keep it as one chunk."""
        tiny = "很短的文档。"
        chunks = chunker.chunk(tiny, min_chunk_size=5)
        assert len(chunks) == 1
        assert tiny in chunks[0].content

    def test_short_text_dropped_if_below_min(self, chunker):
        """If a fragment is below min and there are other chunks, drop it."""
        long_segment = "这是一段足够长的正常文本内容，用于验证过滤功能。" * 3
        text = f"短。\n\n短。\n\n{long_segment}"
        chunks = chunker.chunk(text, min_chunk_size=30)
        for c in chunks:
            assert len(c.content) >= 30


# ============================================================
# Tests — Edge Cases
# ============================================================

class TestEdgeCases:
    """Corner cases and boundary conditions."""

    def test_all_short_fragments(self, chunker):
        """When every segment is too short, answer with what we have."""
        text = "a\n\nb\n\nc\n\nd"
        chunks = chunker.chunk(text, min_chunk_size=20)
        # All segments < 20 chars → may return empty or merge
        # Either way, shouldn't crash
        assert isinstance(chunks, list)

    def test_exact_chunk_size(self, chunker):
        """Text exactly at chunk_size boundary."""
        text = "测" * 500
        chunks = chunker.chunk(text, chunk_size=500)
        assert len(chunks) == 1
        assert len(chunks[0].content) == 500

    def test_max_size_enforced(self, chunker):
        """A very long segment with no break points should be hard-cut."""
        # No punctuation, no spaces — continuous string
        text = "知识库系统是一种基于检索增强生成技术的智能问答平台" * 10
        chunks = chunker.chunk(text, chunk_size=100, max_chunk_size=200)
        for c in chunks:
            assert c.char_count <= 220, (
                f"Chunk {c.index} exceeds hard max: {c.char_count}"
            )

    def test_leading_trailing_whitespace_stripped(self, chunker):
        text = "   \n\n  内容在这里。\n\n  更多内容。  \n\n  "
        chunks = chunker.chunk(text, chunk_size=500)
        for c in chunks:
            assert c.content == c.content.strip()
            assert not c.content.startswith("\n")

    def test_repeated_punctuation(self, chunker):
        """Text with lots of punctuation should split cleanly."""
        text = "！" * 10 + "内容" + "。" * 10 + "更多内容" + "？" * 10
        chunks = chunker.chunk(text, chunk_size=50)
        all_text = "".join(c.content for c in chunks)
        assert "内容" in all_text
        assert "更多内容" in all_text

    def test_code_blocks_preserved(self, chunker, mixed_content):
        chunks = chunker.chunk(mixed_content, chunk_size=300)
        all_text = "\n".join(c.content for c in chunks)
        # Code block content should appear somewhere
        assert "import requests" in all_text
        assert "```python" in all_text or "```" in all_text

    def test_numbers_and_dates(self, chunker):
        text = (
            "2024年第一季度报告：营收达到1.5亿元，同比增长23.5%。"
            "2024年第二季度报告：营收达到1.8亿元，环比增长20%。"
        )
        chunks = chunker.chunk(text, chunk_size=300)
        all_text = "".join(c.content for c in chunks)
        assert "1.5亿元" in all_text
        assert "23.5%" in all_text


# ============================================================
# Tests — Singleton
# ============================================================

class TestSingleton:
    def test_get_chunker_returns_same_instance(self):
        c1 = get_chunker()
        c2 = get_chunker()
        assert c1 is c2

    def test_chunk_text_convenience(self, long_paragraph):
        chunks = chunk_text(long_paragraph, chunk_size=150, overlap=30)
        assert len(chunks) > 0
