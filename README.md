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

# Increment 2: run a real BRD through requirements -> clarification -> spec
python -m factory.cli intake --brd examples/brd/sample-brd.md            # pauses at HUMAN_INPUT
python -m factory.cli intake --brd examples/brd/sample-brd.md \
  --meeting examples/meetings/kickoff-transcript.md                      # reaches KNOWLEDGE_MINED

# Increment 5: continue into design, implementation and unit testing
python -m factory.cli deliver --brd examples/brd/sample-brd.md \
  --meeting examples/meetings/kickoff-transcript.md                      # reaches UNIT_TESTED

# Increment 6: continue through PR, review, policy gate and merge
python -m factory.cli ship --brd examples/brd/sample-brd.md \
  --meeting examples/meetings/kickoff-transcript.md                      # reaches MERGED

# Increment 7: continue through packaging, deploy, validation and closure
python -m factory.cli release --brd examples/brd/sample-brd.md \
  --meeting examples/meetings/kickoff-transcript.md                      # reaches STORY_COMPLETED
```

The intake pipeline extracts stable `BR-xx` requirements from the BRD,
classifies ambiguity (blocking / material-but-assumable / implementation
detail), records explicit assumptions, normalizes meeting transcripts into
decision records with provenance, pauses on blocking ambiguity for human
input, decomposes into features/stories/acceptance criteria with a full
traceability map, and runs the Spec Kit lifecycle (specify -> clarify ->
plan -> tasks -> analyze) with Git-versioned spec artifacts per feature.
Knowledge mining then ingests all project artifacts into the knowledge store
(SQLite by default, PostgreSQL + pgvector via `pip install "sdlc-factory[postgres]"`),
and builds a versioned context pack: vector + exact retrieval, superseded-version
exclusion, authority-based conflict resolution, reranking and token budgeting,
with per-item provenance (source, authority, version, repo commit).

The delivery pipeline (Increment 5) designs the technical solution, assigns
each feature to a specialized worker profile (Python service / React frontend /
data), generates task breakdowns, designs tests before implementation (one
pytest test per acceptance criterion, seeded synthetic fixtures — never real
data), generates the implementation on a feature branch, and runs pre-PR
quality checks (formatting, build, security scan, tests, spec compliance,
coverage) plus the full unit-test suite with durable evidence reports.

The shipping pipeline (Increment 6) commits the implementation on its feature
branch and opens a PR record, runs a four-dimensional review (code quality,
security, spec compliance, coverage) with explainable findings and an
APPROVED / CHANGES_REQUESTED verdict, then evaluates the merge policy gate —
the quality gate thresholds plus review/PR requirements from
`policies/merge.yaml`, all measured from immutable evidence — and only on a
PASS decision merges the feature branch into the protected branch with the
decision file as durable audit evidence.

The release pipeline (Increment 7) packages the merged workspace into a
reproducible artifact (deterministic tar.gz with a sha256 MANIFEST and the
source commit), publishes it to an immutable local artifact repository under
an `artifact://` URI, deploys it to the target environment with a deployment
descriptor and import smoke tests, runs the packaged functional test suite
against the deployed artifact, validates every acceptance criterion against
its test outcome (mandatory pass percentage from `policies/deployment.yaml`),
and closes stories and requirements in the tracker with full evidence links.

## Implementation increments

1. **Control plane** — typed state, state machine, Git/file tools, policy skeleton, audit events.
2. **Requirements + SDD** — intake, clarification/assumption/decision, decomposition, Spec Kit.
3. **Context intelligence** — ingestion, PostgreSQL, pgvector, code search, context builder.
4. **Knowledge graph** — ontology, provenance, graph ingestion/traversal, lineage/impact.
5. **Implementation + test** — workers, pytest/API/Playwright, synthetic data, pre-PR quality.
6. **PR + merge** — PR creation, code/spec/security/coverage review, merge policy.
7. **Release + validation** — package, artifact repo, deploy, smoke/functional/regression.
8. **Self-heal + learning** — failure taxonomy, bounded repair, episodic memory, promotion.
