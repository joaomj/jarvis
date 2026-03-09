"""Deterministic markdown chunking for KB indexing."""

from __future__ import annotations

import re
from dataclasses import dataclass

HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$")


@dataclass(frozen=True)
class KBChunk:
    """One indexed markdown chunk."""

    chunk_index: int
    heading: str | None
    line_start: int
    line_end: int
    chunk_text: str


def chunk_markdown(body: str, max_chunk_size: int) -> list[KBChunk]:
    """Split markdown content into deterministic, overlap-free chunks."""
    lines = body.splitlines()
    if not lines:
        return []

    sections = _sectionize(lines)
    chunks: list[KBChunk] = []
    chunk_index = 0

    for heading, section_lines in sections:
        current: list[tuple[int, str]] = []
        current_length = 0

        for line_no, line in section_lines:
            line_length = len(line)

            if line_length > max_chunk_size:
                if current:
                    chunks.append(_build_chunk(chunk_index, heading, current))
                    chunk_index += 1
                    current = []
                    current_length = 0

                for start in range(0, line_length, max_chunk_size):
                    part = line[start : start + max_chunk_size]
                    chunks.append(
                        KBChunk(
                            chunk_index=chunk_index,
                            heading=heading,
                            line_start=line_no,
                            line_end=line_no,
                            chunk_text=part,
                        )
                    )
                    chunk_index += 1
                continue

            candidate_len = line_length if not current else line_length + 1
            if current and current_length + candidate_len > max_chunk_size:
                chunks.append(_build_chunk(chunk_index, heading, current))
                chunk_index += 1
                current = []
                current_length = 0

            current.append((line_no, line))
            current_length += line_length if current_length == 0 else candidate_len

        if current:
            chunks.append(_build_chunk(chunk_index, heading, current))
            chunk_index += 1

    return chunks


def _build_chunk(chunk_index: int, heading: str | None, lines: list[tuple[int, str]]) -> KBChunk:
    line_start = lines[0][0]
    line_end = lines[-1][0]
    text = "\n".join(value for _, value in lines).strip()
    return KBChunk(
        chunk_index=chunk_index,
        heading=heading,
        line_start=line_start,
        line_end=line_end,
        chunk_text=text,
    )


def _sectionize(lines: list[str]) -> list[tuple[str | None, list[tuple[int, str]]]]:
    sections: list[tuple[str | None, list[tuple[int, str]]]] = []
    heading: str | None = None
    current: list[tuple[int, str]] = []

    for line_no, line in enumerate(lines, start=1):
        match = HEADING_RE.match(line)
        if match and current:
            sections.append((heading, current))
            heading = match.group(2)
            current = [(line_no, line)]
            continue

        if match and not current:
            heading = match.group(2)
        current.append((line_no, line))

    if current:
        sections.append((heading, current))

    return sections
