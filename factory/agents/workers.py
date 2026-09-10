"""Implementation worker profiles.

A worker is one specialized implementation-agent instance: a skill profile
plus the tools it may use. The orchestrator selects a worker per story based
on the technology hint; the worker's skills know HOW, tools perform ACTION.
"""

from pydantic import BaseModel, Field


class WorkerProfile(BaseModel):
    worker_id: str
    title: str
    skills: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    tech_hints: list[str] = Field(default_factory=list)


WORKER_PROFILES: list[WorkerProfile] = [
    WorkerProfile(
        worker_id="python-service-worker",
        title="Python service implementation worker",
        skills=["implementation/python-fastapi", "testing/pytest-unit"],
        allowed_tools=["filesystem", "git", "terminal", "pytest"],
        tech_hints=["python", "fastapi", "service", "api"],
    ),
    WorkerProfile(
        worker_id="react-frontend-worker",
        title="React frontend implementation worker",
        skills=["implementation/react-frontend", "testing/api-contract-playwright"],
        allowed_tools=["filesystem", "git", "terminal", "playwright"],
        tech_hints=["react", "frontend", "ui", "form", "dashboard"],
    ),
    WorkerProfile(
        worker_id="data-worker",
        title="Data engineering worker (pandas/SQL)",
        skills=["implementation/data-pandas-sql", "testing/pytest-unit"],
        allowed_tools=["filesystem", "git", "terminal", "pytest", "sql"],
        tech_hints=["pandas", "sql", "report", "summary", "data"],
    ),
]


def select_worker(text: str) -> WorkerProfile:
    """Pick the worker whose tech hints best match the story text."""
    lowered = text.lower()
    best = WORKER_PROFILES[0]
    best_score = 0
    for profile in WORKER_PROFILES:
        score = sum(1 for hint in profile.tech_hints if hint in lowered)
        if score > best_score:
            best, best_score = profile, score
    return best
