"""Engineering KPI aggregation.

KPIs are computed from immutable transitions, executions and durable
artifacts (never from agent-generated text), per the PRD formulas:
autonomous completion, AC-to-test coverage, PR first-pass, self-heal
success. Measured values are kept separate from any derived commentary.
"""

from pydantic import BaseModel, Field

from factory.models.enums import FactoryState
from factory.observability.reader import ProjectReader

COMPLETED_STATES = {
    FactoryState.STORY_COMPLETED,
    FactoryState.LEARNED,
}


class EngineeringMetrics(BaseModel):
    projects: int = 0
    features_total: int = 0
    features_completed: int = 0
    features_by_state: dict[str, int] = Field(default_factory=dict)
    autonomous_completion_pct: float | None = None
    ac_total: int = 0
    ac_with_tests: int = 0
    ac_to_test_coverage_pct: float | None = None
    prs_total: int = 0
    prs_first_pass: int = 0
    pr_first_pass_pct: float | None = None
    self_heal_episodes: int = 0
    self_heal_repaired: int = 0
    self_heal_success_pct: float | None = None
    failures_by_class: dict[str, int] = Field(default_factory=dict)
    executions_total: int = 0
    executions_failed: int = 0
    retries_total: int = 0
    human_interventions: int = 0


def _pct(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator * 100, 2)


def compute_engineering_metrics(reader: ProjectReader) -> EngineeringMetrics:
    metrics = EngineeringMetrics()
    completed_autonomously = 0

    for project_id in reader.project_ids():
        metrics.projects += 1
        transitions = reader.transitions(project_id)
        executions = reader.executions(project_id)
        episodes = reader.episodes(project_id)
        validation = reader.validation_report(project_id)
        merge_decision = reader.merge_decision(project_id)

        for feature in reader.features(project_id):
            metrics.features_total += 1
            state = feature.current_state.value
            metrics.features_by_state[state] = metrics.features_by_state.get(state, 0) + 1
            if feature.current_state in COMPLETED_STATES:
                metrics.features_completed += 1
                intervened = any(
                    t.human_intervention
                    for t in transitions
                    if t.feature_id == feature.feature_id
                )
                if not intervened:
                    completed_autonomously += 1
            if feature.pull_request is not None:
                metrics.prs_total += 1
                if merge_decision is not None and merge_decision.get("decision") == "PASS":
                    metrics.prs_first_pass += 1

        if validation is not None:
            results = validation.get("results", [])
            metrics.ac_total += len(results)
            metrics.ac_with_tests += len(
                [r for r in results if r.get("test_outcome") != "MISSING"]
            )

        metrics.self_heal_episodes += len(episodes)
        metrics.self_heal_repaired += len(
            [e for e in episodes if e.get("outcome") == "REPAIRED"]
        )
        for episode in episodes:
            failure_class = episode.get("failure_class", "UNKNOWN")
            metrics.failures_by_class[failure_class] = (
                metrics.failures_by_class.get(failure_class, 0) + 1
            )

        metrics.executions_total += len(executions)
        metrics.executions_failed += len(
            [e for e in executions if e.status == "FAILURE"]
        )
        metrics.retries_total += sum(e.retry_number for e in executions)
        metrics.human_interventions += len(
            [t for t in transitions if t.human_intervention]
        )

    metrics.features_by_state = dict(sorted(metrics.features_by_state.items()))
    metrics.failures_by_class = dict(sorted(metrics.failures_by_class.items()))
    metrics.autonomous_completion_pct = _pct(
        completed_autonomously, metrics.features_completed
    )
    metrics.ac_to_test_coverage_pct = _pct(metrics.ac_with_tests, metrics.ac_total)
    metrics.pr_first_pass_pct = _pct(metrics.prs_first_pass, metrics.prs_total)
    metrics.self_heal_success_pct = _pct(
        metrics.self_heal_repaired, metrics.self_heal_episodes
    )
    return metrics
