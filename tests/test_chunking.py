"""Tests for markdown chunking with overlap."""

from jarvis.kb_chunking import chunk_markdown


def test_chunking_basic() -> None:
    body = "# Heading\n\nLine one.\nLine two.\nLine three."
    chunks = chunk_markdown(body, max_chunk_size=100)
    assert len(chunks) >= 1
    assert chunks[0].heading == "Heading"
    assert "Line one" in chunks[0].chunk_text


def test_chunking_with_overlap() -> None:
    lines = [f"Line {i} of content here." for i in range(20)]
    body = "\n".join(lines)
    chunks = chunk_markdown(body, max_chunk_size=60, overlap_lines=2)

    assert len(chunks) >= 2, "Should produce multiple chunks with this size"

    for i in range(1, len(chunks)):
        prev_lines = chunks[i - 1].chunk_text.splitlines()
        curr_lines = chunks[i].chunk_text.splitlines()
        if not prev_lines or not curr_lines:
            continue
        overlap = set(prev_lines) & set(curr_lines)
        assert len(overlap) > 0, f"No overlap between chunk {i - 1} and {i}"


def test_chunking_single_chunk_fits() -> None:
    body = "# Short\n\nBrief content."
    chunks = chunk_markdown(body, max_chunk_size=1000)
    assert len(chunks) == 1
    assert "Brief content." in chunks[0].chunk_text


def test_chunking_empty_body() -> None:
    chunks = chunk_markdown("", max_chunk_size=100)
    assert chunks == []


def test_chunking_heading_boundaries() -> None:
    body = "# Section A\nContent for A.\n\n# Section B\nContent for B."
    chunks = chunk_markdown(body, max_chunk_size=100)
    assert len(chunks) >= 2

    headings = [c.heading for c in chunks]
    assert "Section A" in headings
    assert "Section B" in headings


def test_chunking_oversized_line_split() -> None:
    body = "A" * 200
    chunks = chunk_markdown(body, max_chunk_size=100)
    assert len(chunks) == 2
    assert chunks[0].chunk_text == "A" * 100
    assert chunks[1].chunk_text == "A" * 100


def test_chunking_no_overlap_mode() -> None:
    body = "\n".join(f"Line {i} of content." for i in range(20))
    chunks = chunk_markdown(body, max_chunk_size=50, overlap_lines=0)

    for i in range(1, len(chunks)):
        prev_last = chunks[i - 1].chunk_text.splitlines()[-1].strip()
        curr_first = chunks[i].chunk_text.splitlines()[0].strip()
        assert prev_last != curr_first, f"Unexpected overlap at chunk {i}"
