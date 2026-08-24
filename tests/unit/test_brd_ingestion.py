from pathlib import Path

from factory.knowledge.ingestion.brd import parse_brd, render_requirements_md

SAMPLE_BRD = (
    Path(__file__).resolve().parents[2] / "examples" / "brd" / "sample-brd.md"
).read_text()


def test_parse_extracts_normative_statements_with_stable_ids():
    parsed = parse_brd(SAMPLE_BRD, source="sample-brd.md")
    assert parsed.title == "Customer Feedback Portal — Business Requirements"
    assert [r.req_id for r in parsed.requirements] == [
        f"BR-{i:02d}" for i in range(1, len(parsed.requirements) + 1)
    ]
    assert len(parsed.requirements) == 8


def test_parse_is_reproducible():
    first = parse_brd(SAMPLE_BRD, source="sample-brd.md")
    second = parse_brd(SAMPLE_BRD, source="sample-brd.md")
    assert [r.model_dump() for r in first.requirements] == [
        r.model_dump() for r in second.requirements
    ]


def test_requirements_carry_section_provenance():
    parsed = parse_brd(SAMPLE_BRD, source="sample-brd.md")
    sections = {r.section for r in parsed.requirements}
    assert sections == {"Feedback Submission", "Feedback Review", "Reporting"}
    assert all(r.source == "sample-brd.md" for r in parsed.requirements)


def test_non_normative_text_is_ignored():
    parsed = parse_brd("# Title\n\nThis is just narrative context.\n")
    assert parsed.requirements == []


def test_render_requirements_md_lists_every_requirement():
    parsed = parse_brd(SAMPLE_BRD, source="sample-brd.md")
    rendered = render_requirements_md(parsed)
    for req in parsed.requirements:
        assert req.req_id in rendered
