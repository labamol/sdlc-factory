# Skill: implementation/data-pandas-sql

## Purpose
Implement data stories (aggregation, reporting, persistence): deterministic
pandas transforms and reviewed SQL.

## Entry criteria
- Tasks READY tagged data/report/summary; schema known from the spec.

## Required context
- Context pack (source schemas, retention/PII decisions).

## Allowed tools
- filesystem, git, terminal, pytest, sql

## Steps
1. Express transforms as pure functions taking/returning DataFrames; no
   hidden I/O inside transforms.
2. SQL is parameterized; never interpolate values into statements.
3. Apply retention and PII decisions from binding decision records.
4. Test with deterministic synthetic frames seeded from story IDs.

## Output schema
`src/<feature>_pipeline.py` and parameterized `sql/*.sql`.

## Validation
- Round-trip tests on synthetic data pass; no unparameterized SQL.

## Failure modes
- Ambiguous schema -> SPEC_AMBIGUITY; PII without decision -> policy block.
