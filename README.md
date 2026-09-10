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

# Increment 8: full lifecycle including episodic learning and governed promotion
python -m factory.cli learn --brd examples/brd/sample-brd.md \
  --meeting examples/meetings/kickoff-transcript.md                      # reaches LEARNED

# Increment 8: bounded self-healing from an injected defect
python -m factory.cli heal --brd examples/brd/sample-brd.md \
  --meeting examples/meetings/kickoff-transcript.md                      # DIAGNOSE -> RETEST -> UNIT_TESTED

# Increment 9: observability API + dashboard over the durable records
uv pip install -e ".[dev,observability]"
python -m factory.cli dashboard                                          # http://127.0.0.1:8600

# Increment 10: LLM reasoning (optional; deterministic fallback when unset)
uv pip install -e ".[dev,llm]"
export OPENAI_API_KEY=...            # FACTORY_MODEL selects the model (default gpt-4o-mini)
python -m factory.cli intake --brd examples/brd/sample-brd.md \
  --meeting examples/meetings/kickoff-transcript.md                      # OpenAI-analysed intake
FACTORY_LLM=off python -m factory.cli intake --brd examples/brd/sample-brd.md  # force deterministic

# Increment 11: ship to a real GitHub repository instead of the local PR registry
export GITHUB_TOKEN=...               # contents + pull-requests write on the target repo
export FACTORY_TARGET_REPO=owner/app  # FACTORY_TARGET_BRANCH selects the base (default main)
python -m factory.cli ship --brd examples/brd/sample-brd.md \
  --meeting examples/meetings/kickoff-transcript.md                      # real branch, PR and merge
FACTORY_FORGE=off python -m factory.cli ship --brd examples/brd/sample-brd.md  # stay local

# Increment 12: Jira issues and Teams notifications
export JIRA_SITE_URL=https://acme.atlassian.net JIRA_EMAIL=you@acme.io
export JIRA_API_TOKEN=... JIRA_PROJECT_KEY=SDLC   # JIRA_ISSUE_TYPE defaults to Task
export TEAMS_WEBHOOK_URL=...                      # incoming webhook / Workflows URL
python -m factory.cli release --brd examples/brd/sample-brd.md \
  --meeting examples/meetings/kickoff-transcript.md   # real Jira issues + Teams messages
FACTORY_TRACKER=off FACTORY_NOTIFY=off python -m factory.cli release \
  --brd examples/brd/sample-brd.md                    # stay local
```

With `OPENAI_API_KEY` set, requirements extraction and ambiguity
classification run through OpenAI structured outputs; the factory still owns
the `BR-xx`/`CLR-xxx`/`ASM-xxx` identifiers, artifact shapes and policy gates,
and falls back to the deterministic parsers whenever a call fails. Per-call
token usage and estimated cost are appended to
`projects/<id>/requirements/llm-usage.yaml`.

With `GITHUB_TOKEN` and `FACTORY_TARGET_REPO` set, `PR_CREATED` pushes the
generated workspace to a branch on that repository and opens a real pull
request, and `MERGED` merges it through the GitHub API — only after the same
policy gate that governs the local path. An empty target repository is
initialized with its base branch on the first run. Without those variables the
factory uses its project-local PR registry, so demos and the test suite stay
self-contained. Either way the immutable `prs/PR-<n>.yaml` record is written,
so evidence and the dashboard are unchanged.

With Jira configured, `STORY_COMPLETED` opens one issue per validated story
and transitions it to a done-like status with the acceptance-criteria evidence
as a comment; the issue keys and URLs land in `tracker/completion.yaml`. With
`TEAMS_WEBHOOK_URL` set, the factory posts to Teams when it pauses for a
blocking clarification, when the merge policy gate blocks a merge, when a merge
lands, and when stories close. Both fall back to project-local records
(`tracker/issues.yaml`, `notifications/outbox.yaml`), and a delivery failure is
recorded as evidence rather than failing the lifecycle.

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

Self-healing and learning (Increment 8) classify every test/build failure
into a deterministic taxonomy (code / test / spec / data / environment /
dependency / configuration / factory-template defect) with a stable
normalized signature, route repairs to their owning agent — autonomous
regeneration only for code/test/data/template defects, human escalation for
the rest — bounded by `max_self_heal_attempts` (default 3), and record every
episode in episodic memory. At LEARNED the factory aggregates episodes and
named-author human feedback into a learning record and proposes governed
promotion candidates from recurring successful repairs; candidates stay
PROPOSED until a named human approves them per `policies/learning.yaml` —
skills and templates are never mutated automatically.

Observability (Increment 9) derives everything from the immutable durable
records — feature state files, transition/execution JSONL logs, the audit
event stream and stage artifacts — never from agent-generated summaries. A
FastAPI service exposes projects, feature run timelines, executions, event
logs, engineering KPIs (autonomous completion, AC-to-test coverage, PR
first-pass, self-heal success), quality-gate results (threshold + actual +
evidence + decision) and self-healing episodes, plus a Server-Sent-Events
stream that tails `execution/events.jsonl` for live run monitoring. The
React dashboard under `ui/` (Vite + TypeScript) renders the overview KPIs,
per-project feature/quality/healing views and the per-feature state-machine
timeline with the live event stream; `npm run build` in `ui/` produces
`ui/dist`, which the service serves at the root.

## Implementation increments

1. **Control plane** — typed state, state machine, Git/file tools, policy skeleton, audit events.
2. **Requirements + SDD** — intake, clarification/assumption/decision, decomposition, Spec Kit.
3. **Context intelligence** — ingestion, PostgreSQL, pgvector, code search, context builder.
4. **Knowledge graph** — ontology, provenance, graph ingestion/traversal, lineage/impact.
5. **Implementation + test** — workers, pytest/API/Playwright, synthetic data, pre-PR quality.
6. **PR + merge** — PR creation, code/spec/security/coverage review, merge policy.
7. **Release + validation** — package, artifact repo, deploy, smoke/functional/regression.
8. **Self-heal + learning** — failure taxonomy, bounded repair, episodic memory, promotion.
9. **Observability** — read-only KPI/quality/healing APIs, SSE live stream, React dashboard.
