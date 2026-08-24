# Skill: factory-telemetry

## Purpose
Expose the factory's execution history and live progress from immutable
durable records — transitions, executions, JSONL events and stage artifacts —
never from agent-generated summaries.

## Method
1. Read project state through `factory.observability.reader.ProjectReader`;
   it is the single owner of the on-disk layout under `projects/<id>/`.
2. Compute engineering KPIs with
   `factory.observability.metrics.compute_engineering_metrics`:
   - Autonomous Completion % = completed features without human intervention
     / completed features.
   - AC-to-Test Coverage % = acceptance criteria with a validating test
     / total acceptance criteria in the validation report.
   - PR First-Pass % = PRs whose merge decision is PASS / PRs raised.
   - Self-Heal Success % = episodes with outcome REPAIRED / episodes.
   Every percentage is `null` (never 0) when the denominator is zero.
3. Serve REST queries and the SSE live stream with
   `factory.observability.api.create_app`; the stream tails
   `execution/events.jsonl` so the browser sees the same records the audit
   log contains.
4. Quality-gate views must always show threshold, actual value, evidence
   reference and the final policy decision together.

## Constraints
- Observability is read-only: no endpoint mutates factory state.
- Correlation identifiers (project, feature, story, execution, trace) come
  from the stored records and must be passed through unchanged.
- Do not include secret material in events; sinks persist events verbatim.
