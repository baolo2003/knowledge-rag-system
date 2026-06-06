"""
RAG Prompt Builder

Assembles the full prompt sent to the LLM:
  1. System prompt  — role, rules, citation requirements
  2. Contexts       — retrieved chunks formatted as references
  3. Chat history   — previous user/assistant turns
  4. Current question

The output is a list of message dicts suitable for OpenAI-compatible APIs.
"""

from __future__ import annotations

from app.core.config import settings
from app.services.retriever import ScoredChunk

# ============================================================
# System Prompt
# ============================================================

SYSTEM_PROMPT = """你是一个专业的企业知识库问答助手。你的回答必须严格遵循以下规则：

## 核心规则
1. **基于资料回答**：只能根据下方「参考资料」中的内容回答问题。不要使用任何外部知识或训练数据中的信息。
2. **信息不足时明确说明**：如果参考资料中没有相关信息，请直接说"根据现有资料，我无法回答这个问题"，绝对不要猜测或编造。
3. **禁止编造**：不要添加参考资料中没有的事实、数据、日期、人名或任何具体信息。
4. **引用来源**：每个关键信息点必须标注引用来源，格式为 `[来源N]`，其中N是参考资料的编号。

## 回答格式
1. 先给出简洁直接的回答。
2. 如有必要，用分点或编号补充说明细节。
3. 在回答末尾列出使用的参考资料来源。

## 示例
用户提问："公司2024年的营收目标是多少？"
回答（若有相关资料）："根据公司2024年战略规划，营收目标为5亿元。[来源1][来源3]"
回答（若无相关资料）："根据现有资料，我无法回答这个问题。参考资料中未提及2024年的营收目标。"

记住：准确性比完整性更重要。宁可说不知道，也不能编造。"""


# ============================================================
# PromptBuilder
# ============================================================

class PromptBuilder:
    """
    Builds OpenAI-compatible message lists for RAG Q&A.

    Usage::

        builder = PromptBuilder()
        messages = builder.build(
            question="公司战略目标是什么？",
            contexts=retrieved_chunks,
            history=[{"role": "user", "content": "你好"}],
        )
        # → [{"role": "system", ...}, {"role": "user", ...}]
    """

    # Max total characters for all contexts (avoids exceeding context window)
    MAX_CONTEXT_CHARS: int = 8000

    def build(
        self,
        question: str,
        contexts: list[ScoredChunk],
        history: list[dict[str, str]] | None = None,
    ) -> list[dict[str, str]]:
        """
        Build the full message list for the LLM.

        Args:
            question:  The current user question.
            contexts:  Retrieved ScoredChunk objects sorted by relevance.
            history:   Previous conversation turns (optional).
                        Format: [{"role": "user", "content": "..."},
                                 {"role": "assistant", "content": "..."}]

        Returns:
            List of message dicts: system + history + user_prompt.
        """
        messages: list[dict[str, str]] = []

        # ---- 1. System prompt ----
        messages.append({
            "role": "system",
            "content": SYSTEM_PROMPT,
        })

        # ---- 2. Chat history (if any) ----
        if history:
            for turn in history:
                role = turn.get("role", "user")
                content = turn.get("content", "")
                if content.strip():
                    messages.append({
                        "role": "user" if role == "user" else "assistant",
                        "content": content.strip(),
                    })

        # ---- 3. Build user prompt with contexts ----
        user_prompt = self._build_user_prompt(question, contexts)
        messages.append({
            "role": "user",
            "content": user_prompt,
        })

        return messages

    # ============================================================
    # Private — User prompt assembly
    # ============================================================

    def _build_user_prompt(
        self, question: str, contexts: list[ScoredChunk],
    ) -> str:
        """Build the user-facing prompt that includes contexts and question."""
        parts: list[str] = []

        # References section
        if contexts:
            parts.append("## 参考资料\n")
            context_text = self._format_contexts(contexts)
            parts.append(context_text)
        else:
            parts.append("## 参考资料\n")
            parts.append("（无相关资料）\n")

        # Question section
        parts.append("## 用户提问\n")
        parts.append(question)

        parts.append(
            "\n请基于以上参考资料回答问题。如果资料中确实没有相关信息，"
            "请明确说明'根据现有资料，我无法回答这个问题'，不要编造任何内容。"
        )

        return "\n".join(parts)

    def _format_contexts(self, contexts: list[ScoredChunk]) -> str:
        """
        Format retrieved chunks as numbered reference blocks.

        Each reference includes:
        - Source number [来源N]
        - Document name
        - Relevance score
        - Content (truncated if needed)

        Total length is capped at MAX_CONTEXT_CHARS with even distribution.
        """
        if not contexts:
            return "（无相关资料）"

        # Calculate per-chunk budget
        chars_per_chunk = self.MAX_CONTEXT_CHARS // len(contexts)

        lines: list[str] = []
        total_chars = 0

        for i, chunk in enumerate(contexts, start=1):
            source_label = f"[来源{i}]"
            doc_label = chunk.document_name or f"文档#{chunk.document_id}"
            score_pct = f"相关度: {chunk.score:.0%}" if chunk.score else ""

            header = f"### {source_label} — {doc_label}"
            if score_pct:
                header += f" ({score_pct})"

            # Truncate content if needed
            content = chunk.content.strip()
            if len(content) > chars_per_chunk:
                content = content[:chars_per_chunk] + "..."

            lines.append(header)
            lines.append(content)
            lines.append("")  # blank line between references

            total_chars += len(content)
            if total_chars >= self.MAX_CONTEXT_CHARS:
                remaining = len(contexts) - i
                if remaining > 0:
                    lines.append(f"（...还有 {remaining} 条参考资料因长度限制被省略）")
                break

        return "\n".join(lines)

    def build_simple(
        self, question: str, contexts: list[ScoredChunk],
    ) -> tuple[str, str]:
        """
        Build a simplified prompt for debugging / testing.

        Returns:
            Tuple of (system_prompt, user_prompt) as plain strings.
        """
        user_prompt = self._build_user_prompt(question, contexts)
        return SYSTEM_PROMPT, user_prompt


# ============================================================
# Module-level convenience
# ============================================================

_prompt_builder: PromptBuilder | None = None


def get_prompt_builder() -> PromptBuilder:
    """Return a cached PromptBuilder instance."""
    global _prompt_builder
    if _prompt_builder is None:
        _prompt_builder = PromptBuilder()
    return _prompt_builder


def build_rag_prompt(
    question: str,
    contexts: list[ScoredChunk],
    history: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """Convenience: build RAG prompt messages."""
    return get_prompt_builder().build(question, contexts, history)
