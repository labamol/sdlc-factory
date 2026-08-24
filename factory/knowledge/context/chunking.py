"""Deterministic document chunking.

Markdown/plain text is split on headings, then oversized sections on blank
lines, so re-chunking an unchanged document always yields identical chunks.
"""

import re

HEADING = re.compile(r"^#{1,6}\s+.*$")


def chunk_text(text: str, *, max_chars: int = 1200) -> list[str]:
    sections: list[list[str]] = [[]]
    for line in text.splitlines():
        if HEADING.match(line) and sections[-1]:
            sections.append([])
        sections[-1].append(line)

    chunks: list[str] = []
    for section in sections:
        body = "\n".join(section).strip()
        if not body:
            continue
        if len(body) <= max_chars:
            chunks.append(body)
            continue
        current = ""
        for paragraph in re.split(r"\n{2,}", body):
            candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
            if len(candidate) > max_chars and current:
                chunks.append(current)
                current = paragraph
            else:
                current = candidate
        if current:
            chunks.append(current)
    return chunks
