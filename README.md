# SDLC Factory

A portable, Python-based, spec-driven engineering factory for autonomous
BRD-to-deployment delivery using orchestrated agents, reusable skills,
deterministic tools, policy gates, traceability, a knowledge graph,
contextual memory and controlled learning.

## Core principle

> Workflow decides WHEN; Agent decides WHAT; Skill knows HOW;
> Tool performs ACTION; Policy decides whether execution can PROCEED.

## Architecture planes

| Plane | Responsibility |
|---|---|
| Control plane | Orchestrator, typed state, policy gates, HITL, audit, traceability |
| Agent plane | Requirements, Product, Specification, Knowledge, Design, Implementation, Test, Review, Release, Validation |
| Context intelligence | SQL + search + vector + knowledge graph + authority filtering + token budgeting |
| Skill plane | Portable, versioned engineering skills (`skills/`) |
| MCP / tool plane | Deterministic tools that mutate systems (Git, Jira, filesystem, shell, Docker, artifact repo) |

## Repository layout

```
factory/
  orchestrator/   engine, state machine, router, retry, events
  agents/         one module per reasoning agent
  skills/         registry, loader, executor
  tools/          deterministic system-mutation tools
  speckit/        Spec Kit adapter and lifecycle
  policy/         policy engine, quality/merge/deployment gates
  knowledge/      ingestion, semantic, graph, context, learning
  traceability/   lineage graph and evidence
  runtime/        agent runtime adapters (portable across products)
  models/         typed Pydantic domain state
skills/           portable skill catalogue (SKILL.md + templates + scripts + validation)
templates/        artifact templates
policies/         quality.yaml, security.yaml, merge.yaml, deployment.yaml
projects/         per-project intake, decisions, specs, evidence, execution state
tests/            unit, integration, agent, factory
```

## State machine

```
BRD_RECEIVED -> INTAKE -> CLARIFICATION
   blocking -> HUMAN_INPUT -> CLARIFICATION
   otherwise -> REQUIREMENTS_READY -> DECOMPOSED -> SPECIFIED
-> KNOWLEDGE_MINED -> DESIGNED -> TASKS_READY
-> [TEST_DESIGNED || IMPLEMENTING] -> BUILT -> UNIT_TESTED
   failure -> DIAGNOSE -> repair route -> RETEST
   success -> PR_CREATED -> REVIEWED
   issues -> IMPLEMENTING
   pass -> MERGE_READY -> POLICY_GATE -> MERGED
-> PACKAGED -> PUBLISHED -> DEPLOYED -> FUNCTIONAL_TESTED
-> AC_VALIDATED -> STORY_COMPLETED -> LEARNED
```

Every transition defines entry criteria, responsible agent, allowed tools,
expected artifacts, validation rule, retry route, maximum autonomous attempts
and human escalation condition.

## Quick start

```bash
uv venv && uv pip install -e ".[dev]"
pytest
python -m factory.cli demo   # traverse one mocked feature end-to-end with evidence
```

## Implementation increments

1. **Control plane** — typed state, state machine, Git/file tools, policy skeleton, audit events.
2. **Requirements + SDD** — intake, clarification/assumption/decision, decomposition, Spec Kit.
3. **Context intelligence** — ingestion, PostgreSQL, pgvector, code search, context builder.
4. **Knowledge graph** — ontology, provenance, graph ingestion/traversal, lineage/impact.
5. **Implementation + test** — workers, pytest/API/Playwright, synthetic data, pre-PR quality.
6. **PR + merge** — PR creation, code/spec/security/coverage review, merge policy.
7. **Release + validation** — package, artifact repo, deploy, smoke/functional/regression.
8. **Self-heal + learning** — failure taxonomy, bounded repair, episodic memory, promotion.
