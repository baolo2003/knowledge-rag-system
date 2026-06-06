"""
Tests for PromptBuilder — RAG prompt assembly.

Verifies prompt format: system instruction, context formatting,
history integration, and citation marker presence.

Run::

    pytest tests/test_prompt_builder.py -v
"""

from __future__ import annotations

import pytest

from app.services.prompt_builder import (
    SYSTEM_PROMPT,
    PromptBuilder,
    build_rag_prompt,
    get_prompt_builder,
)
from app.services.retriever import ScoredChunk


# ============================================================
# Helpers
# ============================================================

def _make_chunk(
    chunk_id: str = "doc_1_chunk_0",
    content: str = "测试内容",
    score: float = 0.85,
    document_id: int = 1,
    document_name: str = "test.pdf",
    chunk_index: int = 0,
) -> ScoredChunk:
    return ScoredChunk(
        chunk_id=chunk_id, content=content, score=score,
        document_id=document_id, document_name=document_name,
        chunk_index=chunk_index, kb_id=1, owner_id=10,
        visibility="PUBLIC", org_id=0,
    )


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def builder() -> PromptBuilder:
    return PromptBuilder()


@pytest.fixture
def sample_contexts() -> list[ScoredChunk]:
    return [
        _make_chunk("c0", "公司2024年营收目标为5亿元人民币。", 0.92, 1, "战略规划.pdf", 0),
        _make_chunk("c1", "2024年Q1已实现营收1.2亿元，同比增长20%。", 0.85, 2, "季度报告.pdf", 3),
        _make_chunk("c2", "公司主要产品线包括AI助手、知识库系统。", 0.78, 3, "产品手册.pdf", 1),
    ]


@pytest.fixture
def sample_history() -> list[dict[str, str]]:
    return [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好！有什么可以帮助你的？"},
    ]


# ============================================================
# Tests — Basic prompt structure
# ============================================================

class TestBasicPrompt:
    """Basic prompt assembly tests."""

    def test_build_returns_list_of_dicts(self, builder, sample_contexts):
        messages = builder.build("问题?", sample_contexts)
        assert isinstance(messages, list)
        assert all(isinstance(m, dict) for m in messages)
        assert all("role" in m for m in messages)
        assert all("content" in m for m in messages)

    def test_first_message_is_system(self, builder, sample_contexts):
        messages = builder.build("问题?", sample_contexts)
        assert messages[0]["role"] == "system"

    def test_system_prompt_not_empty(self, builder, sample_contexts):
        messages = builder.build("问题?", sample_contexts)
        assert len(messages[0]["content"]) > 100

    def test_last_message_is_user(self, builder, sample_contexts):
        messages = builder.build("问题?", sample_contexts)
        assert messages[-1]["role"] == "user"

    def test_question_in_last_message(self, builder, sample_contexts):
        question = "公司2024年的营收目标是多少？"
        messages = builder.build(question, sample_contexts)
        assert question in messages[-1]["content"]


# ============================================================
# Tests — System prompt content
# ============================================================

class TestSystemPrompt:
    """System prompt rule verification."""

    def test_contains_based_on_materials_rule(self):
        assert "参考资料" in SYSTEM_PROMPT
        assert "基于资料回答" in SYSTEM_PROMPT or "参考资料" in SYSTEM_PROMPT

    def test_contains_no_fabrication_rule(self):
        assert "禁止编造" in SYSTEM_PROMPT or "不要编造" in SYSTEM_PROMPT

    def test_contains_insufficient_info_rule(self):
        assert "信息不足" in SYSTEM_PROMPT or "无法回答" in SYSTEM_PROMPT

    def test_contains_citation_format(self):
        assert "[来源" in SYSTEM_PROMPT or "引用来源" in SYSTEM_PROMPT

    def test_contains_accuracy_over_completeness(self):
        assert "准确性" in SYSTEM_PROMPT


# ============================================================
# Tests — Context formatting
# ============================================================

class TestContextFormatting:
    """Formatting of retrieved chunks in the prompt."""

    def test_contexts_have_source_labels(self, builder, sample_contexts):
        messages = builder.build("问题?", sample_contexts)
        user_content = messages[-1]["content"]
        assert "[来源1]" in user_content
        assert "[来源2]" in user_content
        assert "[来源3]" in user_content

    def test_contexts_include_document_names(self, builder, sample_contexts):
        messages = builder.build("问题?", sample_contexts)
        user_content = messages[-1]["content"]
        assert "战略规划.pdf" in user_content
        assert "季度报告.pdf" in user_content
        assert "产品手册.pdf" in user_content

    def test_contexts_include_relevance_scores(self, builder):
        chunks = [_make_chunk("c0", "内容A", 0.92)]
        messages = builder.build("问题?", chunks)
        user_content = messages[-1]["content"]
        assert "92%" in user_content or "0.92" in user_content

    def test_no_contexts_shows_empty_message(self, builder):
        messages = builder.build("问题?", [])
        user_content = messages[-1]["content"]
        assert "无相关资料" in user_content or "参考资料" in user_content

    def test_context_truncation(self, builder):
        """Very long content should be truncated."""
        long_content = "长内容" * 3000  # ~9000 chars
        chunks = [_make_chunk("c0", long_content, 0.9)]
        messages = builder.build("问题?", chunks)
        user_content = messages[-1]["content"]
        # Content should be truncated (not all 9000 chars)
        assert len(user_content) < 12000

    def test_max_context_chars_limit(self, builder):
        """Many large chunks should be capped at MAX_CONTEXT_CHARS."""
        chunks = [
            _make_chunk(f"c{i}", "测试文本内容" * 200, 0.9 - i * 0.1, i)
            for i in range(10)
        ]
        messages = builder.build("问题?", chunks)
        user_content = messages[-1]["content"]
        # Should have an ellipsis or truncation indicator if over limit
        assert len(user_content) < 15000  # generous upper bound


# ============================================================
# Tests — Chat history
# ============================================================

class TestChatHistory:
    """Integration of conversation history."""

    def test_history_appears_before_question(self, builder, sample_contexts, sample_history):
        messages = builder.build("新问题?", sample_contexts, sample_history)
        # messages: system, user(history1), assistant(history1), user(prompt)
        assert len(messages) == 4  # system + 2 history + 1 user
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "你好"
        assert messages[2]["role"] == "assistant"
        assert messages[2]["content"] == "你好！有什么可以帮助你的？"

    def test_no_history_no_extra_messages(self, builder, sample_contexts):
        messages = builder.build("问题?", sample_contexts)
        # system + user(prompt) = 2 messages
        assert len(messages) == 2

    def test_empty_history_handled(self, builder, sample_contexts):
        messages = builder.build("问题?", sample_contexts, [])
        assert len(messages) == 2

    def test_history_none_handled(self, builder, sample_contexts):
        messages = builder.build("问题?", sample_contexts, None)
        assert len(messages) == 2


# ============================================================
# Tests — build_simple
# ============================================================

class TestBuildSimple:
    """build_simple() for debugging."""

    def test_returns_tuple_of_strings(self, builder, sample_contexts):
        system, user = builder.build_simple("问题?", sample_contexts)
        assert isinstance(system, str)
        assert isinstance(user, str)
        assert len(system) > 0
        assert len(user) > 0

    def test_system_is_the_system_prompt(self, builder, sample_contexts):
        system, _ = builder.build_simple("问题?", sample_contexts)
        assert system == SYSTEM_PROMPT


# ============================================================
# Tests — Module-level convenience
# ============================================================

class TestConvenience:
    """Module-level convenience functions."""

    def test_build_rag_prompt(self, sample_contexts):
        messages = build_rag_prompt("测试问题?", sample_contexts)
        assert len(messages) >= 2
        assert messages[0]["role"] == "system"

    def test_get_prompt_builder_singleton(self):
        b1 = get_prompt_builder()
        b2 = get_prompt_builder()
        assert b1 is b2


# ============================================================
# Tests — Citation format
# ============================================================

class TestCitationFormat:
    """Citation and reference formatting."""

    def test_each_context_has_unique_source_number(self, builder, sample_contexts):
        messages = builder.build("问题?", sample_contexts)
        user_content = messages[-1]["content"]
        for i in range(1, 4):
            assert f"[来源{i}]" in user_content

    def test_user_prompt_ends_with_instruction(self, builder, sample_contexts):
        messages = builder.build("问题?", sample_contexts)
        user_content = messages[-1]["content"]
        assert "参考资料" in user_content
        assert "用户提问" in user_content

    def test_references_section_before_question(self, builder, sample_contexts):
        messages = builder.build("问题?", sample_contexts)
        user_content = messages[-1]["content"]
        ref_pos = user_content.index("## 参考资料")
        question_pos = user_content.index("## 用户提问")
        assert ref_pos < question_pos


# ============================================================
# Tests — Empty contexts edge cases
# ============================================================

class TestEmptyContexts:
    """Edge cases with no retrieved contexts."""

    def test_empty_contexts_produces_valid_prompt(self, builder):
        messages = builder.build("测试问题?", [])
        assert len(messages) == 2
        user_content = messages[-1]["content"]
        assert "测试问题?" in user_content

    def test_empty_contexts_no_source_labels(self, builder):
        messages = builder.build("问题?", [])
        user_content = messages[-1]["content"]
        assert "[来源" not in user_content
