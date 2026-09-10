"""Jira tracker and Teams notifier tests.

Every HTTP call is served by a stub transport, so the suite needs neither
network access nor credentials.
"""

from dataclasses import dataclass, field
from pathlib import Path

import pytest
import yaml

from factory.agents.hitl import HitlGateAgent
from factory.agents.validation import ValidationAgent
from factory.models.enums import FactoryState
from factory.models.feature import FeatureState
from factory.tools.integrations_config import notifier_from_env, tracker_from_env
from factory.tools.notify import LocalNotifier, NotifyError, TeamsNotifier
from factory.tools.tracker import (
    JiraTracker,
    LocalTracker,
    TrackerError,
    TrackerIssue,
)


@dataclass
class StubResponse:
    status_code: int
    text: str = ""
    payload: dict | None = None

    @property
    def content(self) -> bytes:
        return b"{}" if self.payload is not None else b""

    def json(self) -> dict:
        return self.payload or {}


@dataclass
class StubHttp:
    """Replays canned responses keyed by `METHOD path-suffix`."""

    responses: dict[str, StubResponse]
    calls: list[tuple[str, str, dict]] = field(default_factory=list)

    def request(self, method, url, *, headers, json, timeout):  # noqa: A002
        self.calls.append((method, url, json or {}))
        for key, response in self.responses.items():
            key_method, key_path = key.split(" ", 1)
            if key_method == method and url.endswith(key_path):
                return response
        raise AssertionError(f"unexpected request: {method} {url}")

    def post(self, url, *, json, timeout):
        self.calls.append(("POST", url, json))
        return next(iter(self.responses.values()))


def _jira(monkeypatch: pytest.MonkeyPatch, stub: StubHttp) -> JiraTracker:
    monkeypatch.setattr("factory.tools.tracker.httpx.request", stub.request)
    return JiraTracker("https://acme.atlassian.net/", "dev@acme.io", "token", "SDLC")


def test_local_tracker_opens_and_closes_issues(tmp_path: Path) -> None:
    tracker = LocalTracker(tmp_path)
    issue = tracker.open_issue("STORY-1: login", "description")
    tracker.complete_issue(issue, "validated")
    stored = yaml.safe_load((tmp_path / "tracker" / "issues.yaml").read_text())
    assert stored[0]["key"] == "LOCAL-1"
    assert stored[0]["status"] == "DONE"


def test_jira_creates_issue_with_project_and_adf_description(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = StubHttp({"POST /issue": StubResponse(201, payload={"key": "SDLC-7"})})
    issue = _jira(monkeypatch, stub).open_issue("STORY-1: login", "line one\nline two")
    fields = stub.calls[0][2]["fields"]
    assert fields["project"] == {"key": "SDLC"}
    assert fields["description"]["type"] == "doc"
    assert len(fields["description"]["content"]) == 2
    assert issue.url == "https://acme.atlassian.net/browse/SDLC-7"


def test_jira_completes_issue_via_done_transition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = StubHttp(
        {
            "POST /comment": StubResponse(201),
            "GET /transitions": StubResponse(
                200,
                payload={
                    "transitions": [
                        {"id": "11", "name": "In Progress"},
                        {"id": "31", "name": "Done"},
                    ]
                },
            ),
            "POST /transitions": StubResponse(204),
        }
    )
    tracker = _jira(monkeypatch, stub)
    issue = tracker.complete_issue(TrackerIssue(key="SDLC-7", summary="s"), "validated")
    assert issue.status == "DONE"
    assert stub.calls[-1][2] == {"transition": {"id": "31"}}


def test_jira_reports_missing_done_transition(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = StubHttp(
        {
            "POST /comment": StubResponse(201),
            "GET /transitions": StubResponse(
                200, payload={"transitions": [{"id": "11", "name": "In Progress"}]}
            ),
        }
    )
    tracker = _jira(monkeypatch, stub)
    with pytest.raises(TrackerError, match="No done-like transition"):
        tracker.complete_issue(TrackerIssue(key="SDLC-7", summary="s"), "validated")


def test_jira_surfaces_api_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = StubHttp({"POST /issue": StubResponse(403, text="forbidden")})
    with pytest.raises(TrackerError, match="403"):
        _jira(monkeypatch, stub).open_issue("STORY-1", "body")


def test_jira_requires_complete_configuration() -> None:
    with pytest.raises(TrackerError):
        JiraTracker("https://acme.atlassian.net", "dev@acme.io", "", "SDLC")


def test_local_notifier_appends_to_outbox(tmp_path: Path) -> None:
    notifier = LocalNotifier(tmp_path)
    notifier.send("first", "text", {"Feature": "FEAT-000"})
    notifier.send("second", "text", {})
    stored = yaml.safe_load((tmp_path / "notifications" / "outbox.yaml").read_text())
    assert [entry["title"] for entry in stored] == ["first", "second"]


def test_teams_posts_message_card(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = StubHttp({"POST /hook": StubResponse(200)})
    monkeypatch.setattr("factory.tools.notify.httpx.post", stub.post)
    TeamsNotifier("https://outlook.office.com/hook").send(
        "Human input needed", "body", {"Feature": "FEAT-000"}
    )
    payload = stub.calls[0][2]
    assert payload["title"] == "Human input needed"
    assert payload["sections"][0]["facts"] == [
        {"name": "Feature", "value": "FEAT-000"}
    ]


def test_teams_surfaces_delivery_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = StubHttp({"POST /hook": StubResponse(404, text="not found")})
    monkeypatch.setattr("factory.tools.notify.httpx.post", stub.post)
    with pytest.raises(NotifyError, match="404"):
        TeamsNotifier("https://outlook.office.com/hook").send("t", "b", {})


def test_integrations_default_to_local(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FACTORY_TRACKER", raising=False)
    monkeypatch.delenv("FACTORY_NOTIFY", raising=False)
    assert isinstance(tracker_from_env(tmp_path), LocalTracker)
    assert isinstance(notifier_from_env(tmp_path), LocalNotifier)


def test_integrations_selected_from_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FACTORY_TRACKER", raising=False)
    monkeypatch.delenv("FACTORY_NOTIFY", raising=False)
    monkeypatch.setenv("JIRA_SITE_URL", "https://acme.atlassian.net")
    monkeypatch.setenv("JIRA_EMAIL", "dev@acme.io")
    monkeypatch.setenv("JIRA_API_TOKEN", "token")
    monkeypatch.setenv("JIRA_PROJECT_KEY", "SDLC")
    monkeypatch.setenv("TEAMS_WEBHOOK_URL", "https://outlook.office.com/hook")
    assert isinstance(tracker_from_env(tmp_path), JiraTracker)
    assert isinstance(notifier_from_env(tmp_path), TeamsNotifier)

    monkeypatch.setenv("FACTORY_TRACKER", "off")
    monkeypatch.setenv("FACTORY_NOTIFY", "off")
    assert isinstance(tracker_from_env(tmp_path), LocalTracker)
    assert isinstance(notifier_from_env(tmp_path), LocalNotifier)


@dataclass
class RecordingNotifier:
    name: str = "recording"
    sent: list[tuple[str, str, dict]] = field(default_factory=list)
    failure: str = ""

    def send(self, title: str, text: str, facts: dict[str, str]) -> str:
        if self.failure:
            raise NotifyError(self.failure)
        self.sent.append((title, text, facts))
        return f"recorded:{len(self.sent)}"


@pytest.mark.asyncio
async def test_hitl_gate_notifies_humans(tmp_path: Path) -> None:
    (tmp_path / "requirements").mkdir()
    (tmp_path / "requirements" / "clarifications.yaml").write_text(
        yaml.safe_dump(
            [
                {"clr_id": "CLR-1", "req_id": "BR-001", "question": "Which SSO?",
                 "ambiguity_class": "BLOCKING", "status": "OPEN"}
            ]
        ),
        encoding="utf-8",
    )
    notifier = RecordingNotifier()
    agent = HitlGateAgent(tmp_path, notifier=notifier)
    result = await agent.execute(
        FeatureState(feature_id="FEAT-000", project_id="PRJ", title="t"),
        FactoryState.HUMAN_INPUT,
    )
    assert notifier.sent[0][0] == "Human input needed — FEAT-000"
    assert [e.kind for e in result.evidence] == ["hitl-request", "notification"]


@pytest.mark.asyncio
async def test_hitl_gate_records_delivery_failure(tmp_path: Path) -> None:
    agent = HitlGateAgent(tmp_path, notifier=RecordingNotifier(failure="webhook 404"))
    result = await agent.execute(
        FeatureState(feature_id="FEAT-000", project_id="PRJ", title="t"),
        FactoryState.HUMAN_INPUT,
    )
    assert "delivery failed: webhook 404" in result.evidence[1].ref


@pytest.mark.asyncio
async def test_story_completion_closes_tracker_issues(tmp_path: Path) -> None:
    (tmp_path / "validation").mkdir()
    (tmp_path / "validation" / "validation-report.yaml").write_text(
        yaml.safe_dump({"decision": "PASS"}), encoding="utf-8"
    )
    (tmp_path / "backlog").mkdir()
    (tmp_path / "backlog" / "stories.yaml").write_text(
        yaml.safe_dump(
            [
                {
                    "story_id": "STORY-001-01",
                    "feature_id": "FEAT-000",
                    "title": "login",
                    "acceptance_criteria": [
                        {"ac_id": "AC-001-01", "description": "user logs in"}
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )
    notifier = RecordingNotifier()
    agent = ValidationAgent(
        tmp_path, tmp_path / "policies",
        tracker=LocalTracker(tmp_path), notifier=notifier,
    )
    result = await agent.execute(
        FeatureState(feature_id="FEAT-000", project_id="PRJ", title="t",
                     requirements=["BR-001"]),
        FactoryState.STORY_COMPLETED,
    )
    completion = yaml.safe_load(
        (tmp_path / "tracker" / "completion.yaml").read_text(encoding="utf-8")
    )
    assert completion["stories"][0]["issue_key"] == "LOCAL-1"
    assert "notification" in [e.kind for e in result.evidence]
    assert notifier.sent[0][2]["Issues"] == "LOCAL-1"
