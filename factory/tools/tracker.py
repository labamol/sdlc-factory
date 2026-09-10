"""Issue tracker tool plane.

Story closure is an evidence-producing mutation, so it lives in the tool
plane behind one contract. `LocalTracker` keeps the offline lifecycle
self-contained by recording issues in `tracker/issues.yaml`; `JiraTracker`
performs the same operations against a real Jira Cloud site.
"""

import base64
from pathlib import Path
from typing import Protocol

import httpx
import yaml
from pydantic import BaseModel

JIRA_API_PATH = "/rest/api/3"
DONE_TRANSITION_NAMES = ("done", "closed", "complete", "resolve", "resolved")


class TrackerError(Exception):
    """Raised when a tracker operation cannot be completed."""


class TrackerIssue(BaseModel):
    key: str
    summary: str
    status: str = "OPEN"
    url: str = ""


class Tracker(Protocol):
    name: str

    def open_issue(self, summary: str, description: str) -> TrackerIssue: ...

    def complete_issue(self, issue: TrackerIssue, comment: str) -> TrackerIssue: ...


class LocalTracker:
    """Project-local tracker: the default, and what the test suite exercises."""

    name = "local-tracker"

    def __init__(self, project_dir: Path) -> None:
        self.path = project_dir / "tracker" / "issues.yaml"

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        return yaml.safe_load(self.path.read_text(encoding="utf-8")) or []

    def _save(self, issues: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(yaml.safe_dump(issues, sort_keys=False), encoding="utf-8")

    def open_issue(self, summary: str, description: str) -> TrackerIssue:
        issues = self._load()
        issue = TrackerIssue(key=f"LOCAL-{len(issues) + 1}", summary=summary)
        issues.append({**issue.model_dump(), "description": description})
        self._save(issues)
        return issue

    def complete_issue(self, issue: TrackerIssue, comment: str) -> TrackerIssue:
        issues = self._load()
        for entry in issues:
            if entry.get("key") == issue.key:
                entry["status"] = "DONE"
                entry["resolution_comment"] = comment
        self._save(issues)
        issue.status = "DONE"
        return issue


class JiraTracker:
    """Jira Cloud tracker using basic auth with an Atlassian API token."""

    name = "jira"

    def __init__(
        self,
        site_url: str,
        email: str,
        token: str,
        project_key: str,
        *,
        issue_type: str = "Task",
        timeout_seconds: float = 30.0,
    ) -> None:
        if not site_url or not email or not token or not project_key:
            raise TrackerError("Jira needs site url, email, API token and project key")
        self.site_url = site_url.rstrip("/")
        self.project_key = project_key
        self.issue_type = issue_type
        self._timeout = timeout_seconds
        credential = base64.b64encode(f"{email}:{token}".encode()).decode()
        self._headers = {
            "Authorization": f"Basic {credential}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        try:
            response = httpx.request(
                method,
                f"{self.site_url}{JIRA_API_PATH}{path}",
                headers=self._headers,
                json=payload,
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise TrackerError(f"Jira {method} {path} failed: {exc}") from exc
        if response.status_code >= 400:
            raise TrackerError(
                f"Jira {method} {path} returned {response.status_code}: {response.text[:300]}"
            )
        if not response.content:
            return {}
        return response.json()

    def open_issue(self, summary: str, description: str) -> TrackerIssue:
        payload = {
            "fields": {
                "project": {"key": self.project_key},
                "summary": summary[:250],
                "issuetype": {"name": self.issue_type},
                "description": _adf(description),
            }
        }
        created = self._request("POST", "/issue", payload)
        key = created.get("key", "")
        return TrackerIssue(key=key, summary=summary, url=f"{self.site_url}/browse/{key}")

    def complete_issue(self, issue: TrackerIssue, comment: str) -> TrackerIssue:
        self._request("POST", f"/issue/{issue.key}/comment", {"body": _adf(comment)})
        transitions = self._request("GET", f"/issue/{issue.key}/transitions").get(
            "transitions", []
        )
        target = next(
            (
                t
                for t in transitions
                if t.get("name", "").strip().lower() in DONE_TRANSITION_NAMES
            ),
            None,
        )
        if target is None:
            raise TrackerError(
                f"No done-like transition available for {issue.key}: "
                f"{[t.get('name') for t in transitions]}"
            )
        self._request(
            "POST", f"/issue/{issue.key}/transitions", {"transition": {"id": target["id"]}}
        )
        issue.status = "DONE"
        return issue


def _adf(text: str) -> dict:
    """Jira Cloud v3 takes Atlassian Document Format, not plain strings."""
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": line or " "}]}
            for line in text.splitlines() or [" "]
        ],
    }
