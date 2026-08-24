"""FastAPI observability service.

REST endpoints expose historical, queryable factory state derived from
immutable on-disk records; an SSE endpoint streams live events by tailing
the project's JSONL event log. When a built dashboard exists under
`ui/dist`, it is served at the root so the API and UI ship as one service.

Run with: `python -m factory.cli dashboard --base-dir <dir>`
(requires `pip install "sdlc-factory[observability]"`).
"""

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from factory.observability.metrics import compute_engineering_metrics
from factory.observability.reader import ProjectReader

UI_DIST = Path(__file__).resolve().parents[2] / "ui" / "dist"
STREAM_POLL_SECONDS = 0.5


def create_app(base_dir: Path) -> FastAPI:
    reader = ProjectReader(base_dir)
    app = FastAPI(title="sdlc-factory observability", version="1")

    @app.get("/api/v1/projects")
    def projects() -> list[dict]:
        result = []
        for project_id in reader.project_ids():
            features = reader.features(project_id)
            result.append(
                {
                    "project_id": project_id,
                    "features": len(features),
                    "states": sorted({f.current_state.value for f in features}),
                }
            )
        return result

    def _require_project(project_id: str) -> None:
        if project_id not in reader.project_ids():
            raise HTTPException(status_code=404, detail=f"Unknown project {project_id}")

    @app.get("/api/v1/projects/{project_id}/overview")
    def project_overview(project_id: str) -> dict:
        _require_project(project_id)
        features = reader.features(project_id)
        executions = reader.executions(project_id)
        return {
            "project_id": project_id,
            "features": [
                {
                    "feature_id": f.feature_id,
                    "title": f.title,
                    "current_state": f.current_state.value,
                    "pull_request": f.pull_request,
                    "coverage": f.coverage,
                    "unit_test_status": f.unit_test_status.value,
                    "functional_test_status": f.functional_test_status.value,
                    "deployment_environment": f.deployment_environment,
                    "evidence_count": len(f.evidence),
                }
                for f in features
            ],
            "executions": len(executions),
            "failed_executions": len([e for e in executions if e.status == "FAILURE"]),
        }

    @app.get("/api/v1/projects/{project_id}/features/{feature_id}")
    def feature_detail(project_id: str, feature_id: str) -> dict:
        _require_project(project_id)
        feature = reader.feature(project_id, feature_id)
        if feature is None:
            raise HTTPException(status_code=404, detail=f"Unknown feature {feature_id}")
        return feature.model_dump(mode="json")

    @app.get("/api/v1/projects/{project_id}/features/{feature_id}/timeline")
    def feature_timeline(project_id: str, feature_id: str) -> list[dict]:
        _require_project(project_id)
        executions = {
            (e.stage.value, e.retry_number): e
            for e in reader.executions(project_id, feature_id)
        }
        timeline = []
        for t in reader.transitions(project_id, feature_id):
            execution = executions.get((t.to_state.value, t.retry_number))
            timeline.append(
                {
                    "from_state": t.from_state.value,
                    "to_state": t.to_state.value,
                    "agent": t.agent,
                    "timestamp": t.timestamp.isoformat(),
                    "retry_number": t.retry_number,
                    "human_intervention": t.human_intervention,
                    "execution_id": execution.execution_id if execution else None,
                    "skill": execution.skill if execution else None,
                    "duration_seconds": (
                        execution.duration_seconds if execution else None
                    ),
                    "evidence_refs": t.evidence_refs,
                }
            )
        return timeline

    @app.get("/api/v1/projects/{project_id}/executions")
    def executions(project_id: str) -> list[dict]:
        _require_project(project_id)
        return [e.model_dump(mode="json") for e in reader.executions(project_id)]

    @app.get("/api/v1/projects/{project_id}/executions/{execution_id}")
    def execution_detail(project_id: str, execution_id: str) -> dict:
        _require_project(project_id)
        for execution in reader.executions(project_id):
            if execution.execution_id == execution_id:
                return execution.model_dump(mode="json")
        raise HTTPException(status_code=404, detail=f"Unknown execution {execution_id}")

    @app.get("/api/v1/projects/{project_id}/events")
    def events(project_id: str, execution_id: str | None = None) -> list[dict]:
        _require_project(project_id)
        records = reader.events(project_id)
        if execution_id is not None:
            records = [e for e in records if e.execution_id == execution_id]
        return [e.model_dump(mode="json") for e in records]

    @app.get("/api/v1/metrics/engineering")
    def engineering_metrics() -> dict:
        return compute_engineering_metrics(reader).model_dump(mode="json")

    @app.get("/api/v1/projects/{project_id}/quality")
    def quality(project_id: str) -> dict:
        _require_project(project_id)
        return {
            "merge_decision": reader.merge_decision(project_id),
            "validation_report": reader.validation_report(project_id),
        }

    @app.get("/api/v1/projects/{project_id}/healing")
    def healing(project_id: str) -> dict:
        _require_project(project_id)
        return {
            "episodes": reader.episodes(project_id),
            "promotions": reader.promotions(project_id),
            "learning_record": reader.learning_record(project_id),
        }

    @app.get("/api/v1/stream/projects/{project_id}")
    async def stream_project(
        project_id: str, request: Request, follow: bool = True
    ) -> StreamingResponse:
        _require_project(project_id)
        path = reader.events_path(project_id)

        async def event_source():
            offset = 0
            while True:
                if path.exists():
                    text = path.read_text(encoding="utf-8")
                    lines = [line for line in text.splitlines() if line]
                    for line in lines[offset:]:
                        payload = json.dumps(json.loads(line))
                        yield f"data: {payload}\n\n"
                    offset = len(lines)
                if not follow or await request.is_disconnected():
                    return
                await asyncio.sleep(STREAM_POLL_SECONDS)

        return StreamingResponse(event_source(), media_type="text/event-stream")

    if UI_DIST.exists():
        app.mount("/", StaticFiles(directory=UI_DIST, html=True), name="ui")

    return app
