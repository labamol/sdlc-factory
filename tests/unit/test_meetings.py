from pathlib import Path

from factory.knowledge.ingestion.meetings import extract_decisions

TRANSCRIPT = (
    Path(__file__).resolve().parents[2]
    / "examples"
    / "meetings"
    / "kickoff-transcript.md"
).read_text()


def test_decisions_extracted_with_provenance():
    decisions = extract_decisions(TRANSCRIPT, source="kickoff-transcript.md")
    assert len(decisions) >= 2
    assert all(d.source == "kickoff-transcript.md" for d in decisions)
    assert all(d.decided_by for d in decisions)
    assert all(d.status == "APPROVED" for d in decisions)


def test_decisions_link_to_requirements():
    decisions = extract_decisions(TRANSCRIPT, source="kickoff-transcript.md")
    linked = {d.requirement for d in decisions if d.requirement}
    assert {"BR-06", "BR-08"} <= linked


def test_question_answer_pairing():
    decisions = extract_decisions(TRANSCRIPT, source="kickoff-transcript.md")
    retention = next(d for d in decisions if d.requirement == "BR-06")
    assert retention.type == "clarification"
    assert "retention" in retention.question.lower()


def test_stable_sequential_ids():
    decisions = extract_decisions(TRANSCRIPT, source="kickoff-transcript.md")
    assert [d.decision_id for d in decisions] == [
        f"DEC-{i:03d}" for i in range(1, len(decisions) + 1)
    ]


def test_transcript_without_decisions_yields_nothing():
    assert extract_decisions("Alice: any updates?\nBob: still working on it.", "x") == []
