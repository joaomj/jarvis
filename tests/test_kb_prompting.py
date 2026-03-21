"""Tests for grounded KB prompt and source formatting."""

from __future__ import annotations

from jarvis.kb_prompting import build_grounded_prompt, format_source_list
from jarvis.kb_retrieval import RetrievedChunk


def _chunk(doc_id: int, chunk_index: int, title: str, source: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=doc_id * 1000 + chunk_index,
        document_id=doc_id,
        chunk_index=chunk_index,
        heading="Intro",
        line_start=1,
        line_end=3,
        chunk_text="Deterministic indexing and retrieval.",
        title=title,
        url_original=source,
        markdown_path=f".jarvis/url-saves/{doc_id}.md",
        score=-1.0,
    )


def test_grounded_prompt_contains_citation_rules() -> None:
    prompt = build_grounded_prompt(
        "What did I save about indexing?",
        [_chunk(1, 0, "Doc 1", "https://example.com/1")],
    )

    assert "Do not use outside knowledge" in prompt
    assert "[doc:<id> chunk:<index>]" in prompt
    assert "[doc:1 chunk:0]" in prompt


def test_source_list_is_compact_and_unique() -> None:
    source_list = format_source_list(
        [
            _chunk(1, 0, "Doc 1", "https://example.com/1"),
            _chunk(1, 1, "Doc 1", "https://example.com/1"),
            _chunk(2, 0, "Doc 2", "https://example.com/2"),
        ]
    )

    assert source_list.count("Doc 1") == 1
    assert source_list.count("Doc 2") == 1
