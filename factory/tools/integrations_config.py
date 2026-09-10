"""Tracker and notifier selection from the environment.

Both integrations default to their project-local implementations, so demos
and the test suite stay offline. Supplying credentials promotes the same
lifecycle to Jira and Microsoft Teams without touching agents or policies.
"""

import os
from pathlib import Path

from factory.tools.notify import LocalNotifier, Notifier, TeamsNotifier
from factory.tools.tracker import JiraTracker, LocalTracker, Tracker

ENABLED_VALUES = frozenset({"1", "true", "yes", "on"})


def _enabled(name: str) -> bool:
    return os.environ.get(name, "on").strip().lower() in ENABLED_VALUES


def tracker_from_env(project_dir: Path) -> Tracker:
    site = os.environ.get("JIRA_SITE_URL", "").strip()
    email = os.environ.get("JIRA_EMAIL", "").strip()
    token = os.environ.get("JIRA_API_TOKEN", "").strip()
    project_key = os.environ.get("JIRA_PROJECT_KEY", "").strip()
    if not _enabled("FACTORY_TRACKER") or not (site and email and token and project_key):
        return LocalTracker(project_dir)
    return JiraTracker(
        site_url=site,
        email=email,
        token=token,
        project_key=project_key,
        issue_type=os.environ.get("JIRA_ISSUE_TYPE", "").strip() or "Task",
    )


def notifier_from_env(project_dir: Path) -> Notifier:
    webhook = os.environ.get("TEAMS_WEBHOOK_URL", "").strip()
    if not _enabled("FACTORY_NOTIFY") or not webhook:
        return LocalNotifier(project_dir)
    return TeamsNotifier(webhook)
