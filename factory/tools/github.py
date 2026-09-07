"""GitHub forge adapter.

Publishes the generated workspace to a real repository and drives real pull
requests. The factory keeps its own immutable record of every PR (same
`prs/PR-<n>.yaml` shape the local forge writes, plus the remote number and
URL), so evidence, traceability and the observability dashboard are identical
whether the forge is local or remote.

The working clone lives under `<project>/forge/<repo>` and is never reused
across repositories. Credentials are passed to git as a per-invocation
`http.extraheader` and are never written into the remote URL, so no token ends
up in `.git/config`, in the reflog, or in an error message.
"""

import base64
import json
import shutil
from pathlib import Path

import httpx

from factory.tools.forge import ForgeError
from factory.tools.git import GitError, GitTool
from factory.tools.pr import PrTool, PullRequestRecord

DEFAULT_API_URL = "https://api.github.com"
DEFAULT_GIT_BASE_URL = "https://github.com"
DEFAULT_BASE_BRANCH = "main"
COMMITTER_NAME = "sdlc-factory"
COMMITTER_EMAIL = "factory@localhost"
API_VERSION = "2022-11-28"


class GitHubForge:
    """Forge backed by a GitHub repository."""

    name = "github-remote"

    def __init__(
        self,
        repo: str,
        token: str,
        project_dir: Path,
        *,
        api_url: str = DEFAULT_API_URL,
        git_base_url: str = DEFAULT_GIT_BASE_URL,
        base_branch: str = DEFAULT_BASE_BRANCH,
        timeout_seconds: float = 30.0,
        merge_method: str = "squash",
    ) -> None:
        if "/" not in repo:
            raise ForgeError(f"Target repo must be 'owner/name', got {repo!r}")
        if not token:
            raise ForgeError("A GitHub token is required")
        self.repo = repo
        self.base_branch = base_branch
        self.merge_method = merge_method
        self.checkout_dir = project_dir / "forge" / repo.replace("/", "__")
        self.registry = PrTool(project_dir)
        self._token = token
        self._api_url = api_url.rstrip("/")
        self._git_base_url = git_base_url.rstrip("/")
        self._timeout = timeout_seconds

    # ---- git -------------------------------------------------------------

    def _auth_args(self) -> list[str]:
        """Basic-auth header for git, mirroring how CI checkouts authenticate."""
        credential = base64.b64encode(f"x-access-token:{self._token}".encode()).decode()
        return ["-c", f"http.extraheader=AUTHORIZATION: basic {credential}"]

    def _clone_url(self) -> str:
        return f"{self._git_base_url}/{self.repo}.git"

    def _ensure_checkout(self) -> GitTool:
        git = GitTool(self.checkout_dir)
        if not git.is_repo():
            self.checkout_dir.mkdir(parents=True, exist_ok=True)
            GitTool(self.checkout_dir.parent).run_raw(
                *self._auth_args(), "clone", self._clone_url(), self.checkout_dir.name
            )
            git.configure_identity(COMMITTER_NAME, COMMITTER_EMAIL)
        return git

    def _checkout_branch(self, git: GitTool, branch: str) -> None:
        """Start the feature branch from the remote base, creating the base if empty."""
        try:
            git.run_raw(*self._auth_args(), "fetch", "origin")
        except GitError as exc:
            raise ForgeError(f"Cannot fetch {self.repo}: {exc}") from exc
        if git.has_commits():
            git.run_raw("checkout", "-B", branch, f"origin/{self.base_branch}")
            return
        # Empty repository: the base branch does not exist yet.
        git.run_raw("checkout", "-B", self.base_branch)
        git.run_raw("commit", "--allow-empty", "-m", "Initialize repository")
        git.run_raw(*self._auth_args(), "push", "origin", self.base_branch)
        git.run_raw("checkout", "-B", branch)

    def publish(self, branch: str, source_dir: Path, *, base: str, message: str) -> str:
        self.base_branch = base or self.base_branch
        git = self._ensure_checkout()
        self._checkout_branch(git, branch)
        _mirror_tree(source_dir, self.checkout_dir)
        git.add("--all")
        if git.status_porcelain():
            git.commit(message)
        commit = git.current_commit()
        git.run_raw(*self._auth_args(), "push", "--force-with-lease", "origin", branch)
        return commit

    # ---- API -------------------------------------------------------------

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": API_VERSION,
        }
        try:
            response = httpx.request(
                method,
                f"{self._api_url}{path}",
                headers=headers,
                json=payload,
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise ForgeError(f"GitHub {method} {path} failed: {exc}") from exc
        if response.status_code >= 400:
            raise ForgeError(
                f"GitHub {method} {path} returned {response.status_code}: {response.text[:300]}"
            )
        return json.loads(response.text) if response.text else {}

    def create(
        self,
        title: str,
        branch: str,
        *,
        base: str = DEFAULT_BASE_BRANCH,
        commit: str = "",
        files: list[str] | None = None,
        body: str = "",
    ) -> PullRequestRecord:
        payload = self._request(
            "POST",
            f"/repos/{self.repo}/pulls",
            {"title": title, "head": branch, "base": base or self.base_branch, "body": body},
        )
        record = PullRequestRecord(
            number=int(payload["number"]),
            title=title,
            branch=branch,
            base=base or self.base_branch,
            commit=commit,
            files=files or [],
            url=str(payload.get("html_url", "")),
        )
        return self.registry.update(record)

    def get(self, number: int) -> PullRequestRecord:
        return self.registry.get(number)

    def update(self, record: PullRequestRecord) -> PullRequestRecord:
        return self.registry.update(record)

    def merge(self, record: PullRequestRecord, *, message: str) -> PullRequestRecord:
        payload = self._request(
            "PUT",
            f"/repos/{self.repo}/pulls/{record.number}/merge",
            {"commit_title": message, "merge_method": self.merge_method},
        )
        if not payload.get("merged"):
            raise ForgeError(f"GitHub refused to merge PR #{record.number}: {payload}")
        record.merged_commit = str(payload.get("sha", ""))
        record.status = "MERGED"
        return self.registry.update(record)


def _mirror_tree(source_dir: Path, destination: Path) -> None:
    """Replace the tracked tree with `source_dir`, leaving `.git` untouched."""
    for entry in destination.iterdir():
        if entry.name == ".git":
            continue
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()
    if not source_dir.exists():
        return
    for entry in source_dir.iterdir():
        target = destination / entry.name
        if entry.is_dir():
            shutil.copytree(entry, target)
        else:
            shutil.copy2(entry, target)
