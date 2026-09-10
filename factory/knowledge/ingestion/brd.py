"""BRD ingestion: parse a markdown/plain-text BRD into stable requirements.

Deterministic extraction: requirement-bearing sentences are identified by
normative keywords (shall/must/should/needs to/will). Stable BR-xx IDs are
assigned in document order so re-parsing an unchanged BRD is reproducible.
"""

import re

from pydantic import BaseModel, Field

from factory.models.requirement import Requirement

NORMATIVE = re.compile(
    r"\b(shall|must|should|needs? to|is required to|will be able to|can)\b", re.IGNORECASE
)
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$")


class ParsedBRD(BaseModel):
    title: str = ""
    requirements: list[Requirement] = Field(default_factory=list)
    sections: list[str] = Field(default_factory=list)


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def parse_brd(text: str, source: str = "brd.md") -> ParsedBRD:
    title = ""
    section = ""
    sections: list[str] = []
    requirements: list[Requirement] = []
    counter = 0

    for line in text.splitlines():
        heading = HEADING.match(line)
        if heading:
            level, heading_text = heading.groups()
            if len(level) == 1 and not title:
                title = heading_text.strip()
            else:
                section = heading_text.strip()
                sections.append(section)
            continue

        bullet = BULLET.match(line)
        candidates = [bullet.group(1)] if bullet else _sentences(line)
        for candidate in candidates:
            if NORMATIVE.search(candidate):
                counter += 1
                requirements.append(
                    Requirement(
                        req_id=f"BR-{counter:02d}",
                        statement=candidate.strip(),
                        source=source,
                        section=section,
                    )
                )
    return ParsedBRD(title=title, requirements=requirements, sections=sections)


def render_requirements_md(parsed: ParsedBRD) -> str:
    lines = [f"# Requirements — {parsed.title or 'Untitled BRD'}", ""]
    for req in parsed.requirements:
        lines += [
            f"## {req.req_id}",
            f"- statement: {req.statement}",
            f"- source: {req.source}" + (f" ({req.section})" if req.section else ""),
            "",
        ]
    return "\n".join(lines)
