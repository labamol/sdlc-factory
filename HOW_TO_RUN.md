# How to Run the SDLC Factory

A step-by-step guide to installing, running and exploring the factory:
CLI lifecycle demos, the test suite and the observability dashboard.

## 1. Prerequisites

| Requirement | Version | Used for |
|---|---|---|
| Python | 3.11+ | factory core, CLI, API |
| [uv](https://docs.astral.sh/uv/) (or pip) | latest | dependency install |
| Node.js + npm | 20+ | React dashboard build (optional) |

No external services are required. PostgreSQL/pgvector is optional — the
context-intelligence layer falls back to a deterministic local store when
`DATABASE_URL` is not set (see `.env.example`).

## 2. Install

```bash
git clone https://github.com/labamol/sdlc-factory.git
cd sdlc-factory

# create a virtual environment and install with dev + observability extras
uv venv
uv pip install -e ".[dev,observability]"
```

With plain pip instead of uv:

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev,observability]"
```

The `observability` extra (FastAPI + uvicorn) is only needed for the
`dashboard` command; `pip install -e ".[dev]"` is enough for everything else.

## 3. Verify the installation

```bash
.venv/bin/ruff check .      # lint — expect "All checks passed!"
.venv/bin/pytest -q         # test suite — expect all tests passing
```

## 4. CLI lifecycle commands

All commands run through `python -m factory.cli`. Each command drives the
factory state machine further along the lifecycle and writes durable,
auditable records under `<base-dir>/projects/<project-id>/`.

> **Note on `--base-dir`:** it defaults to the current directory and must
> contain a `policies/` folder (quality/security/merge/deployment gates).
> Running from the repo root works out of the box. To use another
> directory, copy `policies/` into it first.

### 4.1 Quick smoke test — `demo`

Traverses one mocked feature end-to-end with evidence:

```bash
.venv/bin/python -m factory.cli demo
```

### 4.2 Staged lifecycle — real BRD input

Each command includes everything the previous one does and goes further:

```bash
BRD=examples/brd/sample-brd.md
MEETING=examples/meetings/kickoff-transcript.md

# BRD -> requirements, clarifications, assumptions, decomposition, specs
.venv/bin/python -m factory.cli intake  --brd $BRD --meeting $MEETING

# + design, context packs, implementation, unit tests
.venv/bin/python -m factory.cli deliver --brd $BRD --meeting $MEETING

# + PR creation, four-dimensional review, policy gate, governed merge
.venv/bin/python -m factory.cli ship    --brd $BRD --meeting $MEETING

# + packaging, artifact publish, deploy, smoke/functional tests, AC validation
.venv/bin/python -m factory.cli release --brd $BRD --meeting $MEETING

# + episodic memory and governed learning (full lifecycle to LEARNED)
.venv/bin/python -m factory.cli learn   --brd $BRD --meeting $MEETING

# bounded self-healing demo (injects a defect, repairs within 3 attempts)
.venv/bin/python -m factory.cli heal    --brd $BRD --meeting $MEETING
```

Useful flags on all of the above:

- `--project-id PRJ-X` — choose the project identifier.
- `--base-dir DIR` — where project state is written (must contain `policies/`).

### 4.3 Inspecting the results

Everything the factory does is recorded on disk:

```
projects/<project-id>/
  intake/          BRD and intake records
  requirements/    requirements, clarifications, assumptions
  decisions/       decision records
  backlog/         epics, features, stories, acceptance criteria
  specs/ design/   versioned specifications and designs
  context/         versioned context packs
  testing/         generated tests and results
  prs/ review/     pull request and four-dimensional review records
  governance/      merge decision and policy evidence
  release/ artifacts/ deployments/  packaging, publish and deploy records
  validation/      AC validation report
  learning/        episodic memory, feedback, promotions
  execution/       feature state, transitions.jsonl, executions.jsonl,
                   events.jsonl (structured audit event stream)
```

## 5. Observability dashboard

### 5.1 Build the UI (one-time, optional)

```bash
cd ui
npm install
npm run build     # outputs ui/dist, served automatically by the API
cd ..
```

Without the UI build, the REST/SSE API still works — only the web pages
are unavailable.

### 5.2 Generate some data and serve

```bash
# produce a fully traversed project to look at
.venv/bin/python -m factory.cli learn \
  --brd examples/brd/sample-brd.md \
  --meeting examples/meetings/kickoff-transcript.md

# serve API + dashboard
.venv/bin/python -m factory.cli dashboard --port 8600
```

Open http://127.0.0.1:8600 — overview page with engineering KPIs
(autonomous completion, AC-to-test coverage, PR first-pass, self-heal
success), project pages with quality-gate and AC-validation detail, and
feature-run pages with the state-machine timeline and live SSE event
stream.

### 5.3 Key API endpoints

```
GET /api/v1/projects
GET /api/v1/projects/{project_id}/overview
GET /api/v1/projects/{project_id}/features/{feature_id}/timeline
GET /api/v1/projects/{project_id}/executions
GET /api/v1/projects/{project_id}/events
GET /api/v1/projects/{project_id}/quality
GET /api/v1/projects/{project_id}/healing
GET /api/v1/metrics/engineering
GET /api/v1/stream/projects/{project_id}        # SSE live stream
```

## 6. Configuration

- `policies/*.yaml` — quality, security, merge and deployment gates
  (thresholds such as 80% coverage, 95% spec compliance, zero critical
  security findings, max 3 self-heal attempts).
- `.env.example` — optional settings, e.g. `DATABASE_URL` for
  PostgreSQL/pgvector-backed context intelligence.

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| `Install observability extras…` when running `dashboard` | `uv pip install -e ".[dev,observability]"` |
| `policies/ not found` style errors | run from the repo root, or copy `policies/` into your `--base-dir` |
| Dashboard shows no projects | run a lifecycle command first (e.g. `learn`) with the same `--base-dir` |
| Blank page at `/` | build the UI: `cd ui && npm install && npm run build` |
