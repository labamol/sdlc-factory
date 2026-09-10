"""Notification tool plane.

Human gates are only useful if a human hears about them. `LocalNotifier`
appends to `notifications/outbox.yaml` so the offline lifecycle keeps its
evidence trail; `TeamsNotifier` posts the same payload to a Microsoft Teams
incoming webhook or Workflows URL.
"""

from pathlib import Path
from typing import Protocol

import httpx
import yaml

TEAMS_CARD_TYPE = "MessageCard"


class NotifyError(Exception):
    """Raised when a notification cannot be delivered."""


class Notifier(Protocol):
    name: str

    def send(self, title: str, text: str, facts: dict[str, str]) -> str:
        """Deliver a notification and return a reference for the evidence trail."""
        ...


class LocalNotifier:
    """Writes notifications to the project outbox instead of a chat channel."""

    name = "local-notifier"

    def __init__(self, project_dir: Path) -> None:
        self.path = project_dir / "notifications" / "outbox.yaml"

    def send(self, title: str, text: str, facts: dict[str, str]) -> str:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existing = []
        if self.path.exists():
            existing = yaml.safe_load(self.path.read_text(encoding="utf-8")) or []
        existing.append({"title": title, "text": text, "facts": facts})
        self.path.write_text(yaml.safe_dump(existing, sort_keys=False), encoding="utf-8")
        return str(self.path)


class TeamsNotifier:
    """Posts a MessageCard to a Teams incoming webhook."""

    name = "microsoft-teams"

    def __init__(self, webhook_url: str, *, timeout_seconds: float = 30.0) -> None:
        if not webhook_url:
            raise NotifyError("A Teams webhook URL is required")
        self._url = webhook_url
        self._timeout = timeout_seconds

    def send(self, title: str, text: str, facts: dict[str, str]) -> str:
        payload = {
            "@type": TEAMS_CARD_TYPE,
            "@context": "https://schema.org/extensions",
            "themeColor": "0F62FE",
            "summary": title,
            "title": title,
            "text": text,
            "sections": [
                {"facts": [{"name": k, "value": v} for k, v in facts.items()]}
            ],
        }
        try:
            response = httpx.post(self._url, json=payload, timeout=self._timeout)
        except httpx.HTTPError as exc:
            raise NotifyError(f"Teams webhook failed: {exc}") from exc
        if response.status_code >= 400:
            raise NotifyError(
                f"Teams webhook returned {response.status_code}: {response.text[:300]}"
            )
        return self.name
