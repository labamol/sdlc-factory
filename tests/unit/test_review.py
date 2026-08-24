from factory.models.story import AcceptanceCriterion, Story
from factory.review.review import render_review_md, run_review
from factory.tools.pr import PrTool


def _story() -> Story:
    return Story(
        story_id="STORY-01.01",
        feature_id="FEAT-01",
        title="Submit feedback",
        acceptance_criteria=[
            AcceptanceCriterion(ac_id="AC-01.01.01", description="stored"),
            AcceptanceCriterion(ac_id="AC-01.01.02", description="rejected"),
        ],
    )


CLEAN_SRC = (
    '"""Feature module."""\n\n\n'
    "def story_01_01(record):\n"
    '    """AC-01.01.01 AC-01.01.02"""\n'
    "    if not record:\n"
    "        raise ValueError('empty')\n"
    "    return dict(record)\n"
)
CLEAN_TESTS = (
    "import feat_01\n\n\n"
    "def test_story():\n"
    "    assert feat_01.story_01_01({'a': 1}) == {'a': 1}\n"
)


def _workspace(tmp_path, src: str, tests: str = CLEAN_TESTS):
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "feat_01.py").write_text(src)
    (tmp_path / "tests" / "test_feat_01.py").write_text(tests)
    (tmp_path / "conftest.py").write_text(
        "import sys\nfrom pathlib import Path\n"
        'sys.path.insert(0, str(Path(__file__).parent / "src"))\n'
    )
    return tmp_path


def test_review_approves_clean_workspace(tmp_path):
    report = run_review(_workspace(tmp_path, CLEAN_SRC), [_story()])
    assert report.verdict == "APPROVED"
    assert not report.blocking_findings
    names = {c.name for c in report.checks}
    assert {
        "code_review_blocking_findings", "security_critical_findings",
        "spec_compliance", "coverage", "unit_tests",
    } == names


def test_review_flags_todo_and_bare_except_as_blocking(tmp_path):
    dirty = CLEAN_SRC + (
        "\n\ndef later():\n"
        "    # TODO: finish this\n"
        "    try:\n"
        "        return 1\n"
        "    except:\n"
        "        pass\n"
    )
    report = run_review(_workspace(tmp_path, dirty), [_story()])
    assert report.verdict == "CHANGES_REQUESTED"
    messages = {f.message for f in report.blocking_findings}
    assert any("TODO" in m for m in messages)
    assert any("bare except" in m for m in messages)
    assert all(f.file and f.line for f in report.blocking_findings)


def test_review_marks_security_hits_critical(tmp_path):
    insecure = CLEAN_SRC + '\ntoken = "abc123"\n'
    report = run_review(_workspace(tmp_path, insecure), [_story()])
    critical = [f for f in report.findings if f.severity == "CRITICAL"]
    assert critical and critical[0].category == "security"
    assert report.verdict == "CHANGES_REQUESTED"


def test_render_review_md_contains_checks_and_findings(tmp_path):
    report = run_review(_workspace(tmp_path, CLEAN_SRC), [_story()])
    text = render_review_md(report, "FEAT-01")
    assert "Verdict: **APPROVED**" in text
    assert "| spec_compliance |" in text


def test_pr_tool_creates_and_updates_records(tmp_path):
    tool = PrTool(tmp_path)
    record = tool.create("FEAT-01: Feedback", "feature/feat-01", commit="abc")
    assert record.number == 1 and record.status == "OPEN"
    record.status = "APPROVED"
    tool.update(record)
    assert tool.get(1).status == "APPROVED"
    second = tool.create("FEAT-02", "feature/feat-02")
    assert second.number == 2
