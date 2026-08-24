from factory.models.story import AcceptanceCriterion, Story
from factory.quality.prepr import run_pre_pr_checks
from factory.tools.shell import ShellTool


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


def _workspace(tmp_path, src: str, tests: str):
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "feat_01.py").write_text(src)
    (tmp_path / "tests" / "test_feat_01.py").write_text(tests)
    (tmp_path / "conftest.py").write_text(
        "import sys\nfrom pathlib import Path\n"
        'sys.path.insert(0, str(Path(__file__).parent / "src"))\n'
    )
    return tmp_path


GOOD_SRC = (
    "def story_01_01(record):\n"
    '    """AC-01.01.01 AC-01.01.02"""\n'
    "    if not record:\n"
    "        raise ValueError('empty')\n"
    "    return dict(record)\n"
)
GOOD_TESTS = (
    "import feat_01\n\n\n"
    "def test_story():\n"
    "    assert feat_01.story_01_01({'a': 1}) == {'a': 1}\n"
)


def test_pre_pr_checks_pass_on_clean_workspace(tmp_path):
    workspace = _workspace(tmp_path, GOOD_SRC, GOOD_TESTS)
    report = run_pre_pr_checks(workspace, [_story()])
    by_name = {c.name: c for c in report.checks}
    assert report.passed, [c.model_dump() for c in report.checks if not c.passed]
    assert by_name["security_critical_findings"].actual == "0"
    assert by_name["spec_compliance"].actual == "100.0%"
    assert by_name["coverage"].actual == "100.0%"


def test_security_scan_flags_dangerous_patterns(tmp_path):
    bad_src = GOOD_SRC + '\npassword = "hunter2"\nresult = eval("1+1")\n'
    workspace = _workspace(tmp_path, bad_src, GOOD_TESTS)
    report = run_pre_pr_checks(workspace, [_story()])
    check = next(c for c in report.checks if c.name == "security_critical_findings")
    assert not check.passed
    assert int(check.actual) >= 2
    assert not report.passed


def test_build_check_fails_on_syntax_error(tmp_path):
    workspace = _workspace(tmp_path, "def broken(:\n", "")
    report = run_pre_pr_checks(workspace, [_story()])
    check = next(c for c in report.checks if c.name == "build")
    assert not check.passed


def test_spec_compliance_detects_missing_story_function(tmp_path):
    workspace = _workspace(tmp_path, "def unrelated():\n    return 1\n", "")
    report = run_pre_pr_checks(workspace, [_story()])
    check = next(c for c in report.checks if c.name == "spec_compliance")
    assert not check.passed


def test_shell_tool_rejects_unlisted_executables(tmp_path):
    shell = ShellTool(tmp_path)
    try:
        shell.run(["rm", "-rf", "/"])
        raise AssertionError("expected PermissionError")
    except PermissionError:
        pass
