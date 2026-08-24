import pytest

from factory.release.deploy import deploy_artifact, run_smoke_tests
from factory.release.packaging import artifact_sha256, build_artifact
from factory.tools.artifacts import ArtifactRepoTool

MODULE = (
    '"""Feature module."""\n\n'
    "_RECORDS = {}\n\n\n"
    "def reset():\n"
    "    _RECORDS.clear()\n"
)


def _workspace(tmp_path):
    workspace = tmp_path / "workspace"
    (workspace / "src").mkdir(parents=True)
    (workspace / "tests").mkdir()
    (workspace / "src" / "feat_01.py").write_text(MODULE)
    (workspace / "tests" / "test_feat_01.py").write_text(
        "import feat_01\n\n\ndef test_reset():\n    feat_01.reset()\n"
    )
    (workspace / "conftest.py").write_text(
        "import sys\nfrom pathlib import Path\n"
        'sys.path.insert(0, str(Path(__file__).parent / "src"))\n'
    )
    return workspace


def test_packaging_is_deterministic(tmp_path):
    workspace = _workspace(tmp_path)
    first, manifest = build_artifact(
        workspace, tmp_path / "dist-a", name="feat-01", version="v1.0", commit="abc"
    )
    second, _ = build_artifact(
        workspace, tmp_path / "dist-b", name="feat-01", version="v1.0", commit="abc"
    )
    assert first.name == "feat-01-v1.0.tar.gz"
    assert artifact_sha256(first) == artifact_sha256(second)
    assert set(manifest.files) == {
        "conftest.py", "src/feat_01.py", "tests/test_feat_01.py",
    }


def test_artifact_repo_publish_resolve_and_immutability(tmp_path):
    workspace = _workspace(tmp_path)
    artifact, _ = build_artifact(
        workspace, tmp_path / "dist", name="feat-01", version="v1.0"
    )
    repo = ArtifactRepoTool(tmp_path / "repo")
    published = repo.publish(artifact, project_id="PRJ-1")
    assert published.uri == "artifact://PRJ-1/feat-01-v1.0.tar.gz"
    assert repo.resolve(published.uri).exists()

    (workspace / "src" / "feat_01.py").write_text(MODULE + "\nEXTRA = 1\n")
    changed, _ = build_artifact(
        workspace, tmp_path / "dist2", name="feat-01", version="v1.0"
    )
    with pytest.raises(ValueError, match="Immutable artifact conflict"):
        repo.publish(changed, project_id="PRJ-1")
    with pytest.raises(FileNotFoundError):
        repo.resolve("artifact://PRJ-1/missing.tar.gz")


def test_deploy_and_smoke_tests(tmp_path):
    workspace = _workspace(tmp_path)
    artifact, _ = build_artifact(
        workspace, tmp_path / "dist", name="feat-01", version="v1.0"
    )
    target = tmp_path / "deployments" / "local"
    descriptor = deploy_artifact(
        artifact, target, environment="local",
        artifact_uri="artifact://PRJ-1/feat-01-v1.0.tar.gz",
        sha256=artifact_sha256(artifact),
    )
    assert descriptor.modules == ["feat_01"]
    assert (target / "deployment.yaml").exists()
    assert (target / "src" / "feat_01.py").exists()

    report = run_smoke_tests(target, descriptor)
    assert report.passed
    assert any(c["check"] == "import+reset feat_01" for c in report.checks)


def test_smoke_fails_on_broken_module(tmp_path):
    workspace = _workspace(tmp_path)
    (workspace / "src" / "feat_02.py").write_text("raise RuntimeError('boom')\n")
    artifact, _ = build_artifact(
        workspace, tmp_path / "dist", name="feat-01", version="v1.0"
    )
    target = tmp_path / "deployments" / "local"
    descriptor = deploy_artifact(
        artifact, target, environment="local", artifact_uri="artifact://p/a",
        sha256=artifact_sha256(artifact),
    )
    report = run_smoke_tests(target, descriptor)
    assert not report.passed
    failing = [c for c in report.checks if not c["passed"]]
    assert failing and "feat_02" in failing[0]["check"]
