"""GitHub forge tests.

Git operations run against a local bare repository standing in for the remote,
and every API call is served by a stub transport, so the suite needs neither
network access nor credentials.
"""

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from factory.tools.forge import ForgeError
from factory.tools.forge_config import forge_from_env
from factory.tools.git import GitTool, _redact
from factory.tools.github import GitHubForge
from factory.tools.pr import PrTool, PullRequestRecord


@dataclass
class StubResponse:
    status_code: int
    text: str


@dataclass
class StubApi:
    """Records requests and replays canned responses keyed by `METHOD path`."""

    responses: dict[str, StubResponse]
    calls: list[tuple[str, str, dict, dict]] = field(default_factory=list)

    def __call__(self, method, url, *, headers, json, timeout):  # noqa: A002
        path = url.split("api", 1)[-1]
        self.calls.append((method, url, headers, json or {}))
        for key, response in self.responses.items():
            key_method, key_path = key.split(" ", 1)
            if key_method == method and path.endswith(key_path):
                return response
        raise AssertionError(f"unexpected request: {method} {url}")


@pytest.fixture()
def remote(tmp_path: Path) -> Path:
    """A bare repo with one commit on main, playing the part of GitHub."""
    bare = tmp_path / "remote" / "owner" / "app.git"
    bare.mkdir(parents=True)
    subprocess.run(["git", "init", "--bare", "-b", "main", str(bare)], check=True,
                   capture_output=True)
    seed = tmp_path / "seed"
    seed.mkdir()
    git = GitTool(seed)
    git.init()
    git.configure_identity("seed", "seed@localhost")
    (seed / "README.md").write_text("app\n", encoding="utf-8")
    git.add("README.md")
    git.commit("seed")
    git.run_raw("remote", "add", "origin", str(bare))
    git.run_raw("push", "origin", "main")
    return bare


@pytest.fixture()
def empty_remote(tmp_path: Path) -> Path:
    bare = tmp_path / "empty" / "owner" / "app.git"
    bare.mkdir(parents=True)
    subprocess.run(["git", "init", "--bare", "-b", "main", str(bare)], check=True,
                   capture_output=True)
    return bare


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "project" / "workspace"
    (workspace / "src").mkdir(parents=True)
    (workspace / "src" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    return workspace


def _forge(tmp_path: Path, git_root: Path) -> GitHubForge:
    return GitHubForge(
        repo="owner/app",
        token="test-token",
        project_dir=tmp_path / "project",
        api_url="https://api.example.test",
        git_base_url=str(git_root),
    )


def test_publish_pushes_workspace_to_remote_branch(tmp_path: Path, remote: Path) -> None:
    workspace = _workspace(tmp_path)
    forge = _forge(tmp_path, remote.parent.parent)

    commit = forge.publish("feature/x", workspace, base="main", message="FEAT-1: work")

    assert len(commit) == 40
    pushed = subprocess.run(
        ["git", "show", "feature/x:src/app.py"], cwd=remote,
        capture_output=True, text=True, check=True,
    )
    assert pushed.stdout == "VALUE = 1\n"


def test_publish_replaces_previous_tree_and_keeps_history(
    tmp_path: Path, remote: Path
) -> None:
    workspace = _workspace(tmp_path)
    forge = _forge(tmp_path, remote.parent.parent)
    forge.publish("feature/x", workspace, base="main", message="first")

    (workspace / "src" / "app.py").unlink()
    (workspace / "src" / "renamed.py").write_text("VALUE = 2\n", encoding="utf-8")
    forge.publish("feature/x", workspace, base="main", message="second")

    listing = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "feature/x"], cwd=remote,
        capture_output=True, text=True, check=True,
    ).stdout.split()
    assert listing == ["src/renamed.py"]


def test_publish_initializes_an_empty_repository(tmp_path: Path, empty_remote: Path) -> None:
    """The target repo starts empty, so the base branch has to be created first."""
    workspace = _workspace(tmp_path)
    forge = _forge(tmp_path, empty_remote.parent.parent)

    forge.publish("feature/x", workspace, base="main", message="FEAT-1: work")

    branches = subprocess.run(
        ["git", "branch", "--format=%(refname:short)"], cwd=empty_remote,
        capture_output=True, text=True, check=True,
    ).stdout.split()
    assert sorted(branches) == ["feature/x", "main"]


def test_create_records_remote_number_and_url(tmp_path: Path, monkeypatch) -> None:
    api = StubApi({"POST /repos/owner/app/pulls": StubResponse(
        201, '{"number": 42, "html_url": "https://github.com/owner/app/pull/42"}'
    )})
    monkeypatch.setattr("factory.tools.github.httpx.request", api)
    forge = _forge(tmp_path, tmp_path)

    record = forge.create("FEAT-1: title", "feature/x", base="main", commit="abc", files=["a"])

    assert record.number == 42
    assert record.url == "https://github.com/owner/app/pull/42"
    assert PrTool(tmp_path / "project").get(42).branch == "feature/x"
    payload = api.calls[0][3]
    assert payload["head"] == "feature/x" and payload["base"] == "main"


def test_api_errors_surface_as_forge_errors(tmp_path: Path, monkeypatch) -> None:
    api = StubApi({"POST /repos/owner/app/pulls": StubResponse(422, '{"message":"exists"}')})
    monkeypatch.setattr("factory.tools.github.httpx.request", api)
    forge = _forge(tmp_path, tmp_path)

    with pytest.raises(ForgeError) as excinfo:
        forge.create("FEAT-1: title", "feature/x")
    assert "422" in str(excinfo.value)


def test_merge_records_squash_commit(tmp_path: Path, monkeypatch) -> None:
    api = StubApi({"PUT /repos/owner/app/pulls/42/merge": StubResponse(
        200, '{"merged": true, "sha": "deadbeef"}'
    )})
    monkeypatch.setattr("factory.tools.github.httpx.request", api)
    forge = _forge(tmp_path, tmp_path)
    record = forge.registry.update(
        PullRequestRecord(number=42, title="t", branch="feature/x", status="APPROVED")
    )

    merged = forge.merge(record, message="Merge feature/x")

    assert merged.status == "MERGED"
    assert merged.merged_commit == "deadbeef"
    assert forge.get(42).status == "MERGED"
    assert api.calls[0][3]["merge_method"] == "squash"


def test_merge_refusal_is_an_error(tmp_path: Path, monkeypatch) -> None:
    api = StubApi({"PUT /repos/owner/app/pulls/42/merge": StubResponse(
        200, '{"merged": false, "message": "not mergeable"}'
    )})
    monkeypatch.setattr("factory.tools.github.httpx.request", api)
    forge = _forge(tmp_path, tmp_path)
    record = PullRequestRecord(number=42, title="t", branch="feature/x")

    with pytest.raises(ForgeError):
        forge.merge(record, message="Merge feature/x")


def test_token_never_appears_in_git_errors() -> None:
    args = ("-c", "http.extraheader=AUTHORIZATION: basic c2VjcmV0", "push")
    assert "c2VjcmV0" not in _redact(args)


def test_rejects_malformed_repo(tmp_path: Path) -> None:
    with pytest.raises(ForgeError):
        GitHubForge(repo="app", token="t", project_dir=tmp_path)
    with pytest.raises(ForgeError):
        GitHubForge(repo="owner/app", token="", project_dir=tmp_path)


def test_forge_from_env_defaults_to_local_registry(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert isinstance(forge_from_env(tmp_path), PrTool)


def test_forge_from_env_selects_github_when_configured(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FACTORY_FORGE", "on")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setenv("FACTORY_TARGET_REPO", "owner/app")

    forge = forge_from_env(tmp_path)

    assert isinstance(forge, GitHubForge)
    assert forge.repo == "owner/app"


def test_forge_from_env_respects_the_off_switch(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FACTORY_FORGE", "off")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setenv("FACTORY_TARGET_REPO", "owner/app")

    assert isinstance(forge_from_env(tmp_path), PrTool)
