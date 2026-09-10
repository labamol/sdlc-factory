# Skill: release/package-deploy

## Purpose
Turn a merged feature into a reproducible, checksum-verified release:
package, publish, deploy and smoke-test with durable evidence at each step.

## Entry criteria
- Feature MERGED into the protected branch; workspace src/tests/data present.

## Required context
- Merge commit, spec version, target environment, `policies/deployment.yaml`.

## Allowed tools
- docker/terminal (scoped shell), artifact-repo, filesystem

## Steps
1. Package: build a deterministic tar.gz (zeroed mtimes/uids, sorted members)
   with a MANIFEST recording sha256 per file, version and source commit —
   identical inputs must produce byte-identical artifacts.
2. Publish: copy into the artifact repository under an immutable
   `artifact://<project>/<name>` URI; re-publishing a different checksum
   under the same name is an error.
3. Deploy: resolve the URI, verify the checksum, extract into the target
   environment directory and write `deployment.yaml` (environment, URI,
   sha256, modules). Production requires human approval per policy.
4. Smoke: import every deployed module in a fresh interpreter and call its
   reset(); any failure fails the deployment.
5. Persist `release/release.yaml` and `release/smoke-report.yaml`.

## Output schema
`dist/<name>-<version>.tar.gz`, artifact registry entry,
`deployments/<env>/`, release + smoke evidence.

## Validation
- Published checksum equals packaged checksum; smoke report all-pass.

## Failure modes
- Checksum conflict or smoke failure -> stage fails, no progression.
