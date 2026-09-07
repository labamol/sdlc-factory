"""Durable state stores.

PostgreSQL becomes the primary control/state store in Increment 3; the file
store keeps Increment 1 self-contained while preserving the same interface.
"""

import json
from pathlib import Path
from typing import Protocol

from factory.models.execution import AgentExecution, StateTransition
from factory.models.feature import FeatureState


class StateStore(Protocol):
    def save_feature(self, feature: FeatureState) -> None: ...

    def load_feature(self, project_id: str, feature_id: str) -> FeatureState | None: ...

    def record_transition(self, transition: StateTransition) -> None: ...

    def record_execution(self, execution: AgentExecution) -> None: ...

    def transitions_for(self, feature_id: str) -> list[StateTransition]: ...

    def executions_for(self, feature_id: str) -> list[AgentExecution]: ...


class FileStateStore:
    """JSON-file-backed store under projects/<project-id>/execution/."""

    def __init__(self, projects_dir: Path) -> None:
        self.projects_dir = projects_dir

    def _execution_dir(self, project_id: str) -> Path:
        d = self.projects_dir / project_id / "execution"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_feature(self, feature: FeatureState) -> None:
        path = self._execution_dir(feature.project_id) / f"{feature.feature_id}.state.json"
        path.write_text(feature.model_dump_json(indent=2), encoding="utf-8")

    def load_feature(self, project_id: str, feature_id: str) -> FeatureState | None:
        path = self._execution_dir(project_id) / f"{feature_id}.state.json"
        if not path.exists():
            return None
        return FeatureState.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def _append(self, project_id: str, name: str, record_json: str) -> None:
        path = self._execution_dir(project_id) / name
        with path.open("a", encoding="utf-8") as f:
            f.write(record_json + "\n")

    def record_transition(self, transition: StateTransition) -> None:
        self._append(transition.project_id, "transitions.jsonl", transition.model_dump_json())

    def record_execution(self, execution: AgentExecution) -> None:
        self._append(execution.project_id, "executions.jsonl", execution.model_dump_json())

    def _read_jsonl(self, project_id: str, name: str) -> list[dict]:
        path = self._execution_dir(project_id) / name
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    def _project_dirs(self) -> list[Path]:
        if not self.projects_dir.exists():
            return []
        return sorted(p for p in self.projects_dir.iterdir() if p.is_dir())

    def transitions_for(self, feature_id: str) -> list[StateTransition]:
        records: list[StateTransition] = []
        for project_dir in self._project_dirs():
            for raw in self._read_jsonl(project_dir.name, "transitions.jsonl"):
                t = StateTransition.model_validate(raw)
                if t.feature_id == feature_id:
                    records.append(t)
        return sorted(records, key=lambda t: t.timestamp)

    def executions_for(self, feature_id: str) -> list[AgentExecution]:
        records: list[AgentExecution] = []
        for project_dir in self._project_dirs():
            for raw in self._read_jsonl(project_dir.name, "executions.jsonl"):
                e = AgentExecution.model_validate(raw)
                if e.feature_id == feature_id:
                    records.append(e)
        return sorted(records, key=lambda e: e.started_at)
