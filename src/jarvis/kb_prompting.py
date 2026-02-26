"""Prompt assembly helpers for grounded KB Q&A."""

from __future__ import annotations

from jarvis.kb_retrieval import RetrievedChunk


def build_grounded_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    """Build strict context-only prompt with citation requirements."""
    context_blocks = []
    for chunk in chunks:
        header = (
            f"[doc:{chunk.document_id} chunk:{chunk.chunk_index}] "
            f"title={chunk.title or 'untitled'} "
            f"source={chunk.url_original or chunk.markdown_path}"
        )
        context_blocks.append(f"{header}\n{chunk.chunk_text}")

    joined_context = "\n\n".join(context_blocks)
    return (
        "You are answering a question using only the provided context snippets.\n"
        "Rules:\n"
        "1) Do not use outside knowledge.\n"
        "2) If context is insufficient, say you do not have enough evidence.\n"
        "3) Every factual claim must include inline citations in the exact format [doc:<id> chunk:<index>].\n"
        "4) Keep the answer concise and directly answer the user question.\n\n"
        f"Question:\n{question}\n\n"
        f"Context:\n{joined_context}"
    )


def format_source_list(chunks: list[RetrievedChunk]) -> str:
    """Format compact unique source list for user display."""
    seen: set[int] = set()
    lines: list[str] = []
    for chunk in chunks:
        if chunk.document_id in seen:
            continue
        seen.add(chunk.document_id)
        source = chunk.url_original or chunk.markdown_path
        title = chunk.title or chunk.markdown_path
        lines.append(f"- {title} ({source})")
    return "\n".join(lines)
