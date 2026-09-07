"""LLM runtime adapter, configuration and LLM-assisted requirements analysis."""

import json

import httpx
import pytest
import yaml

from factory.agents.llm_analysis import (
    AmbiguityJudgement,
    ClassificationResult,
    ExtractionResult,
    RequirementDraft,
    classify_requirements,
    extract_requirements,
)
from factory.agents.requirements import RequirementsAgent
from factory.models.enums import AmbiguityClass, FactoryState
from factory.models.feature import FeatureState
from factory.models.requirement import Requirement
from factory.runtime.config import llm_enabled, runtime_from_env
from factory.runtime.llm import LLMError, LLMUsage
from factory.runtime.openai import OpenAIRuntime, _strict_schema, estimate_cost_usd


class FakeRuntime:
    """Returns queued schema instances; records the prompts it was given."""

    name = "fake"
    model = "fake-model"

    def __init__(self, *responses: object, error: Exception | None = None) -> None:
        self._responses = list(responses)
        self._error = error
        self.calls: list[tuple[str, str]] = []

    async def complete_structured(self, system, user, schema, max_output_tokens=2048):
        self.calls.append((system, user))
        if self._error is not None:
            raise self._error
        return self._responses.pop(0), LLMUsage(
            model=self.model, prompt_tokens=100, completion_tokens=20, total_tokens=120
        )


def _openai_runtime(handler) -> OpenAIRuntime:
    return OpenAIRuntime(
        api_key="test-key",
        max_attempts=2,
        backoff_base_seconds=0.0,
        transport=httpx.MockTransport(handler),
    )


def _chat_response(content: object, model: str = "gpt-4o-mini") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "model": model,
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(content)}}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500},
        },
    )


def _feature() -> FeatureState:
    return FeatureState(feature_id="FEAT-000", project_id="PRJ-LLM")


def _write_brd(tmp_path, text: str) -> None:
    (tmp_path / "intake").mkdir(parents=True, exist_ok=True)
    (tmp_path / "intake" / "brd.md").write_text(text, encoding="utf-8")


SAMPLE_BRD = "# Portal\n\n- The system shall let users reset a password.\n- It should be fast.\n"


def test_strict_schema_marks_objects_closed_and_all_fields_required():
    document = _strict_schema(ExtractionResult)
    assert document["additionalProperties"] is False
    assert document["required"] == ["requirements", "title"]
    draft = document["$defs"]["RequirementDraft"]
    assert draft["additionalProperties"] is False
    assert draft["required"] == ["actors", "section", "statement"]


def test_estimate_cost_uses_pricing_table_and_returns_none_for_unknown_models():
    assert estimate_cost_usd("gpt-4o-mini", 1_000_000, 1_000_000) == 0.75
    assert estimate_cost_usd("some-future-model", 1000, 1000) is None


def test_openai_runtime_rejects_empty_api_key():
    with pytest.raises(LLMError):
        OpenAIRuntime(api_key="")


async def test_openai_runtime_parses_structured_response_and_accounts_usage():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["response_format"]["json_schema"]["strict"] is True
        assert request.headers["Authorization"] == "Bearer test-key"
        return _chat_response({"title": "Portal", "requirements": []})

    runtime = _openai_runtime(handler)
    result, usage = await runtime.complete_structured("sys", "user", ExtractionResult)

    assert result.title == "Portal"
    assert (usage.prompt_tokens, usage.completion_tokens, usage.attempts) == (1000, 500, 1)
    assert usage.cost_usd == pytest.approx(0.00045)


async def test_openai_runtime_retries_retryable_status_then_succeeds():
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(429, text="rate limited")
        return _chat_response({"title": "Portal", "requirements": []})

    runtime = _openai_runtime(handler)
    _, usage = await runtime.complete_structured("sys", "user", ExtractionResult)

    assert attempts["count"] == 2
    assert usage.attempts == 2


async def test_openai_runtime_does_not_retry_non_retryable_status():
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(401, text="unauthorized")

    runtime = _openai_runtime(handler)
    with pytest.raises(LLMError, match="401"):
        await runtime.complete_structured("sys", "user", ExtractionResult)
    assert attempts["count"] == 1


async def test_openai_runtime_raises_on_schema_violation_and_truncation():
    runtime = _openai_runtime(lambda request: _chat_response({"requirements": "not-a-list"}))
    with pytest.raises(LLMError, match="did not match"):
        await runtime.complete_structured("sys", "user", ExtractionResult)

    def truncated(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "gpt-4o-mini",
                "choices": [{"finish_reason": "length", "message": {"content": "{"}}],
                "usage": {},
            },
        )

    runtime = _openai_runtime(truncated)
    with pytest.raises(LLMError, match="truncated"):
        await runtime.complete_structured("sys", "user", ExtractionResult)


def test_runtime_from_env_requires_key_and_honours_opt_out(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("FACTORY_LLM", raising=False)
    assert runtime_from_env() is None
    assert llm_enabled() is True

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("FACTORY_MODEL", "gpt-4o")
    runtime = runtime_from_env()
    assert runtime is not None and runtime.model == "gpt-4o"

    monkeypatch.setenv("FACTORY_LLM", "off")
    assert llm_enabled() is False
    assert runtime_from_env() is None


async def test_extract_requirements_assigns_stable_ids_and_skips_blanks():
    runtime = FakeRuntime(
        ExtractionResult(
            title="Portal",
            requirements=[
                RequirementDraft(statement="Users can reset a password.", section="Auth"),
                RequirementDraft(statement="   "),
                RequirementDraft(statement="Sessions expire after inactivity."),
            ],
        )
    )
    title, requirements, usage = await extract_requirements(runtime, SAMPLE_BRD, "intake/brd.md")

    assert title == "Portal"
    assert [r.req_id for r in requirements] == ["BR-01", "BR-02"]
    assert requirements[0].section == "Auth"
    assert all(r.source == "intake/brd.md" for r in requirements)
    assert usage.total_tokens == 120


async def test_classify_requirements_orders_by_requirement_and_drops_unknown_ids():
    requirements = [
        Requirement(req_id="BR-01", statement="Reset password", source="brd"),
        Requirement(req_id="BR-02", statement="Be fast", source="brd"),
        Requirement(req_id="BR-03", statement="Log format", source="brd"),
    ]
    runtime = FakeRuntime(
        ClassificationResult(
            judgements=[
                AmbiguityJudgement(
                    req_id="BR-03", ambiguity_class=AmbiguityClass.IMPLEMENTATION_DETAIL
                ),
                AmbiguityJudgement(
                    req_id="BR-99", ambiguity_class=AmbiguityClass.BLOCKING, question="ghost"
                ),
                AmbiguityJudgement(
                    req_id="BR-02",
                    ambiguity_class=AmbiguityClass.MATERIAL_ASSUMABLE,
                    trigger="fast",
                    suggested_assumption="p95 under 500ms",
                    risk="low",
                ),
            ]
        )
    )
    clarifications, assumptions, _ = await classify_requirements(runtime, requirements)

    assert [c.req_id for c in clarifications] == ["BR-02", "BR-03"]
    assert [c.clr_id for c in clarifications] == ["CLR-001", "CLR-002"]
    assert all(c.status == "ASSUMED" for c in clarifications)
    assert [(a.asm_id, a.req_id, a.statement, a.risk) for a in assumptions] == [
        ("ASM-001", "BR-02", "p95 under 500ms", "low")
    ]


async def test_agent_uses_runtime_and_records_token_usage(tmp_path):
    _write_brd(tmp_path, SAMPLE_BRD)
    runtime = FakeRuntime(
        ExtractionResult(
            title="Portal",
            requirements=[RequirementDraft(statement="Users can reset a password.")],
        ),
        ClassificationResult(
            judgements=[
                AmbiguityJudgement(
                    req_id="BR-01",
                    ambiguity_class=AmbiguityClass.BLOCKING,
                    question="Which identity provider?",
                )
            ]
        ),
    )
    agent = RequirementsAgent(tmp_path, runtime=runtime)

    intake = await agent.execute(_feature(), FactoryState.INTAKE)
    assert "fake analysis" in intake.summary
    assert intake.state_updates["requirements"] == ["BR-01"]

    clarify = await agent.execute(_feature(), FactoryState.CLARIFICATION)
    assert "human input required" in clarify.summary

    usage = yaml.safe_load((tmp_path / "requirements" / "llm-usage.yaml").read_text())
    assert [entry["operation"] for entry in usage] == [
        "extract-requirements",
        "classify-ambiguity",
    ]
    assert sum(entry["total_tokens"] for entry in usage) == 240


async def test_agent_falls_back_to_deterministic_analysis_when_runtime_fails(tmp_path):
    _write_brd(tmp_path, SAMPLE_BRD)
    agent = RequirementsAgent(tmp_path, runtime=FakeRuntime(error=LLMError("boom")))

    intake = await agent.execute(_feature(), FactoryState.INTAKE)
    clarify = await agent.execute(_feature(), FactoryState.CLARIFICATION)

    assert "deterministic-fallback analysis" in intake.summary
    assert intake.state_updates["requirements"] == ["BR-01", "BR-02"]
    assert "assumed" in clarify.summary
    assert not (tmp_path / "requirements" / "llm-usage.yaml").exists()


async def test_agent_without_runtime_is_unchanged(tmp_path):
    _write_brd(tmp_path, SAMPLE_BRD)
    agent = RequirementsAgent(tmp_path)

    intake = await agent.execute(_feature(), FactoryState.INTAKE)

    assert "deterministic analysis" in intake.summary
    assert intake.state_updates["requirements"] == ["BR-01", "BR-02"]
