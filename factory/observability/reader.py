"""Read-only access to durable factory state for observability.

The dashboard derives everything from immutable on-disk records — feature
state, transitions, executions and the JSONL event stream — never from
agent-generated summaries. This reader is the single place that knows the
project directory layout.
"""

import json
from pathlib import Path

import yaml

from factory.models.execution import AgentExecution, StateTransition
from factory.models.feature import FeatureState
from factory.orchestrator.events import FactoryEvent, read_events


class ProjectReader:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.projects_dir = base_dir / "projects"

    def project_ids(self) -> list[str]:
        if not self.projects_dir.exists():
            return []
        return sorted(p.name for p in self.projects_dir.iterdir() if p.is_dir())

    def project_dir(self, project_id: str) -> Path:
        return self.projects_dir / project_id

    def events_path(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "execution" / "events.jsonl"

    def features(self, project_id: str) -> list[FeatureState]:
        execution_dir = self.project_dir(project_id) / "execution"
        if not execution_dir.exists():
            return []
        features = []
        for path in sorted(execution_dir.glob("*.state.json")):
            features.append(
                FeatureState.model_validate(json.loads(path.read_text(encoding="utf-8")))
            )
        return features

    def feature(self, project_id: str, feature_id: str) -> FeatureState | None:
        for feature in self.features(project_id):
            if feature.feature_id == feature_id:
                return feature
        return None

    def _read_jsonl(self, project_id: str, name: str) -> list[dict]:
        path = self.project_dir(project_id) / "execution" / name
        if not path.exists():
            return []
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line
        ]

    def transitions(
        self, project_id: str, feature_id: str | None = None
    ) -> list[StateTransition]:
        records = [
            StateTransition.model_validate(raw)
            for raw in self._read_jsonl(project_id, "transitions.jsonl")
        ]
        if feature_id is not None:
            records = [t for t in records if t.feature_id == feature_id]
        return sorted(records, key=lambda t: t.timestamp)

    def executions(
        self, project_id: str, feature_id: str | None = None
    ) -> list[AgentExecution]:
        records = [
            AgentExecution.model_validate(raw)
            for raw in self._read_jsonl(project_id, "executions.jsonl")
        ]
        if feature_id is not None:
            records = [e for e in records if e.feature_id == feature_id]
        return sorted(records, key=lambda e: e.started_at)

    def events(self, project_id: str) -> list[FactoryEvent]:
        return read_events(self.events_path(project_id))

    def _read_yaml(self, project_id: str, relative: str) -> dict | list | None:
        path = self.project_dir(project_id) / relative
        if not path.exists():
            return None
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    def merge_decision(self, project_id: str) -> dict | None:
        raw = self._read_yaml(project_id, "governance/merge-decision.yaml")
        return raw if isinstance(raw, dict) else None

    def validation_report(self, project_id: str) -> dict | None:
        raw = self._read_yaml(project_id, "validation/validation-report.yaml")
        return raw if isinstance(raw, dict) else None

    def episodes(self, project_id: str) -> list[dict]:
        raw = self._read_yaml(project_id, "learning/episodes.yaml")
        return raw if isinstance(raw, list) else []

    def promotions(self, project_id: str) -> list[dict]:
        raw = self._read_yaml(project_id, "learning/promotions.yaml")
        return raw if isinstance(raw, list) else []

    def learning_record(self, project_id: str) -> dict | None:
        raw = self._read_yaml(project_id, "learning/learning-record.yaml")
        return raw if isinstance(raw, dict) else None
