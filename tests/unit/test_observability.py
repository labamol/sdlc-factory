import json
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from factory.models.enums import FactoryState
from factory.models.execution import AgentExecution, StateTransition
from factory.models.feature import FeatureState
from factory.observability.api import create_app
from factory.observability.metrics import compute_engineering_metrics
from factory.observability.reader import ProjectReader
from factory.orchestrator.events import EventBus, FactoryEvent, JsonlEventSink
from factory.orchestrator.store import FileStateStore

PROJECT = "PRJ-OBS"


def seed_project(base_dir: Path) -> None:
    store = FileStateStore(base_dir / "projects")
    feature = FeatureState(
        feature_id="FEAT-001",
        project_id=PROJECT,
        title="Observable feature",
        acceptance_criteria=["AC-001-01"],
        pull_request=7,
        coverage=91.0,
        current_state=FactoryState.STORY_COMPLETED,
    )
    store.save_feature(feature)
    store.record_transition(
        StateTransition(
            transition_id="TRN-1",
            feature_id="FEAT-001",
            project_id=PROJECT,
            from_state=FactoryState.BRD_RECEIVED,
            to_state=FactoryState.INTAKE,
            agent="requirements-agent",
        )
    )
    store.record_execution(
        AgentExecution(
            execution_id="EX-1",
            feature_id="FEAT-001",
            project_id=PROJECT,
            stage=FactoryState.INTAKE,
            agent="requirements-agent",
            skill="brd-analysis",
            status="SUCCESS",
            duration_seconds=1.5,
        )
    )
    events = EventBus(
        [JsonlEventSink(base_dir / "projects" / PROJECT / "execution" / "events.jsonl")]
    )
    events.emit(
        FactoryEvent(
            event_type="AGENT_EXECUTION_COMPLETED",
            project_id=PROJECT,
            feature_id="FEAT-001",
            execution_id="EX-1",
            stage="INTAKE",
            agent="requirements-agent",
            status="SUCCESS",
        )
    )
    project_dir = base_dir / "projects" / PROJECT
    (project_dir / "governance").mkdir(parents=True)
    (project_dir / "governance" / "merge-decision.yaml").write_text(
        yaml.safe_dump({"feature_id": "FEAT-001", "decision": "PASS", "checks": []}),
        encoding="utf-8",
    )
    (project_dir / "validation").mkdir(parents=True)
    (project_dir / "validation" / "validation-report.yaml").write_text(
        yaml.safe_dump(
            {
                "feature_id": "FEAT-001",
                "decision": "PASS",
                "results": [
                    {
                        "ac_id": "AC-001-01",
                        "mandatory": True,
                        "test_outcome": "PASSED",
                        "passed": True,
                    },
                    {
                        "ac_id": "AC-001-02",
                        "mandatory": False,
                        "test_outcome": "MISSING",
                        "passed": False,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (project_dir / "learning").mkdir(parents=True)
    (project_dir / "learning" / "episodes.yaml").write_text(
        yaml.safe_dump(
            [
                {
                    "episode_id": "EPI-1",
                    "failure_class": "FACTORY_TEMPLATE_DEFECT",
                    "outcome": "REPAIRED",
                },
                {
                    "episode_id": "EPI-2",
                    "failure_class": "CODE_DEFECT",
                    "outcome": "ESCALATED",
                },
            ]
        ),
        encoding="utf-8",
    )


class TestProjectReader:
    def test_lists_projects_and_features(self, tmp_path):
        seed_project(tmp_path)
        reader = ProjectReader(tmp_path)
        assert reader.project_ids() == [PROJECT]
        features = reader.features(PROJECT)
        assert [f.feature_id for f in features] == ["FEAT-001"]
        assert reader.feature(PROJECT, "FEAT-001") is not None
        assert reader.feature(PROJECT, "FEAT-404") is None

    def test_reads_transitions_executions_events(self, tmp_path):
        seed_project(tmp_path)
        reader = ProjectReader(tmp_path)
        assert len(reader.transitions(PROJECT, "FEAT-001")) == 1
        assert reader.executions(PROJECT)[0].execution_id == "EX-1"
        events = reader.events(PROJECT)
        assert events[0].event_type == "AGENT_EXECUTION_COMPLETED"

    def test_reads_durable_artifacts(self, tmp_path):
        seed_project(tmp_path)
        reader = ProjectReader(tmp_path)
        assert reader.merge_decision(PROJECT)["decision"] == "PASS"
        assert reader.validation_report(PROJECT)["decision"] == "PASS"
        assert len(reader.episodes(PROJECT)) == 2

    def test_empty_base_dir(self, tmp_path):
        reader = ProjectReader(tmp_path)
        assert reader.project_ids() == []
        assert reader.features("NOPE") == []
        assert reader.merge_decision("NOPE") is None


class TestEngineeringMetrics:
    def test_kpis_from_immutable_records(self, tmp_path):
        seed_project(tmp_path)
        metrics = compute_engineering_metrics(ProjectReader(tmp_path))
        assert metrics.projects == 1
        assert metrics.features_total == 1
        assert metrics.features_completed == 1
        assert metrics.autonomous_completion_pct == 100.0
        assert metrics.ac_total == 2
        assert metrics.ac_with_tests == 1
        assert metrics.ac_to_test_coverage_pct == 50.0
        assert metrics.pr_first_pass_pct == 100.0
        assert metrics.self_heal_episodes == 2
        assert metrics.self_heal_success_pct == 50.0
        assert metrics.failures_by_class == {
            "CODE_DEFECT": 1,
            "FACTORY_TEMPLATE_DEFECT": 1,
        }

    def test_empty_metrics_have_null_percentages(self, tmp_path):
        metrics = compute_engineering_metrics(ProjectReader(tmp_path))
        assert metrics.autonomous_completion_pct is None
        assert metrics.pr_first_pass_pct is None
        assert metrics.self_heal_success_pct is None


class TestObservabilityApi:
    def client(self, base_dir: Path) -> TestClient:
        return TestClient(create_app(base_dir))

    def test_projects_and_overview(self, tmp_path):
        seed_project(tmp_path)
        client = self.client(tmp_path)
        projects = client.get("/api/v1/projects").json()
        assert projects[0]["project_id"] == PROJECT
        overview = client.get(f"/api/v1/projects/{PROJECT}/overview").json()
        assert overview["features"][0]["current_state"] == "STORY_COMPLETED"
        assert overview["executions"] == 1

    def test_feature_detail_and_timeline(self, tmp_path):
        seed_project(tmp_path)
        client = self.client(tmp_path)
        detail = client.get(f"/api/v1/projects/{PROJECT}/features/FEAT-001").json()
        assert detail["pull_request"] == 7
        timeline = client.get(
            f"/api/v1/projects/{PROJECT}/features/FEAT-001/timeline"
        ).json()
        assert timeline[0]["to_state"] == "INTAKE"
        assert timeline[0]["execution_id"] == "EX-1"
        assert timeline[0]["skill"] == "brd-analysis"

    def test_executions_events_and_filters(self, tmp_path):
        seed_project(tmp_path)
        client = self.client(tmp_path)
        assert (
            client.get(f"/api/v1/projects/{PROJECT}/executions/EX-1").json()["agent"]
            == "requirements-agent"
        )
        events = client.get(
            f"/api/v1/projects/{PROJECT}/events", params={"execution_id": "EX-1"}
        ).json()
        assert len(events) == 1
        assert (
            client.get(
                f"/api/v1/projects/{PROJECT}/events",
                params={"execution_id": "EX-404"},
            ).json()
            == []
        )

    def test_metrics_quality_and_healing_endpoints(self, tmp_path):
        seed_project(tmp_path)
        client = self.client(tmp_path)
        metrics = client.get("/api/v1/metrics/engineering").json()
        assert metrics["features_total"] == 1
        quality = client.get(f"/api/v1/projects/{PROJECT}/quality").json()
        assert quality["merge_decision"]["decision"] == "PASS"
        healing = client.get(f"/api/v1/projects/{PROJECT}/healing").json()
        assert len(healing["episodes"]) == 2

    def test_unknown_ids_return_404(self, tmp_path):
        seed_project(tmp_path)
        client = self.client(tmp_path)
        assert client.get("/api/v1/projects/NOPE/overview").status_code == 404
        assert (
            client.get(f"/api/v1/projects/{PROJECT}/features/NOPE").status_code == 404
        )
        assert (
            client.get(f"/api/v1/projects/{PROJECT}/executions/NOPE").status_code
            == 404
        )

    def test_sse_stream_emits_existing_events(self, tmp_path):
        seed_project(tmp_path)
        client = self.client(tmp_path)
        with client.stream(
            "GET", f"/api/v1/stream/projects/{PROJECT}", params={"follow": "false"}
        ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            payloads = [
                json.loads(line[len("data: "):])
                for line in response.iter_lines()
                if line.startswith("data: ")
            ]
        assert payloads[0]["event_type"] == "AGENT_EXECUTION_COMPLETED"
