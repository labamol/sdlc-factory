# Skill: data/synthetic-data-generation

## Purpose
Produce deterministic, privacy-safe synthetic fixtures seeded from stable
story IDs so tests are reproducible everywhere.

## Entry criteria
- Story IDs known; field shapes known from the spec.

## Required context
- Field constraints (formats, categories, boundaries) from the spec.

## Allowed tools
- filesystem

## Steps
1. Seed all randomness from the story ID (hash-based); no wall-clock or RNG
   state.
2. Never copy production data; generate plausible values per field type.
3. Include boundary rows (empty optionals, max lengths) for negative tests.
4. Persist as `workspace/data/synthetic.json` keyed by story ID.

## Output schema
JSON mapping story ID -> list of records.

## Validation
- Same seed always yields identical records.

## Failure modes
- Unknown field constraints -> SPEC_AMBIGUITY.
