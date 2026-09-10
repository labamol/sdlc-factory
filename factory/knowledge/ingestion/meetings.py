"""Meeting transcript ingestion.

Transcripts are never dumped into coding context. Useful statements are
normalized into structured decisions with provenance, authority, status and
supersession, following the decision-record contract.
"""

import re
from datetime import date

from factory.models.requirement import Decision

SPEAKER_LINE = re.compile(r"^\s*([A-Za-z][\w .'-]*)\s*(?:\(([^)]+)\))?\s*:\s*(.+)$")
DECISION_CUES = re.compile(
    r"\b(we (?:have )?decided|decision:|agreed(?: that)?|confirmed(?: that)?|"
    r"let's go with|the answer is|approved)\b",
    re.IGNORECASE,
)
QUESTION_CUE = re.compile(r"\?\s*$")
FEATURE_REF = re.compile(r"\b(FEAT-\d+)\b")
REQ_REF = re.compile(r"\b(BR-\d+)\b")


def extract_decisions(
    transcript: str,
    source: str,
    *,
    effective_from: date | None = None,
    start_index: int = 1,
) -> list[Decision]:
    decisions: list[Decision] = []
    last_question = ""
    counter = start_index

    for line in transcript.splitlines():
        match = SPEAKER_LINE.match(line)
        if not match:
            continue
        speaker, role, statement = match.groups()
        statement = statement.strip()

        if QUESTION_CUE.search(statement):
            last_question = statement
            continue

        if DECISION_CUES.search(statement):
            feature_match = FEATURE_REF.search(statement)
            req_match = REQ_REF.search(statement)
            decisions.append(
                Decision(
                    decision_id=f"DEC-{counter:03d}",
                    source=source,
                    feature=feature_match.group(1) if feature_match else None,
                    requirement=req_match.group(1) if req_match else None,
                    type="clarification" if last_question else "decision",
                    question=last_question,
                    decision=statement,
                    decided_by=f"{speaker.strip()}" + (f" ({role})" if role else ""),
                    confidence="confirmed",
                    status="APPROVED",
                    effective_from=effective_from,
                    source_version="transcript-v1",
                )
            )
            counter += 1
            last_question = ""
    return decisions
