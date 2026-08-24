# ADR-004: Exact-artifact promotion

Status: Accepted for 1.0.4.2

## Decision

The frozen release commit produces one signed candidate AAB without uploading
it. Promotion downloads that existing artifact by candidate run ID and verifies
its commit, provenance, artifact name, package, version, upload certificate and
SHA-256 before uploading the same bytes to Internal Testing. Promotion contains
no Gradle, compile or bundle step.

## Consequences

- A pre-artifact build failure does not consume a Play version.
- Configuration-only upload failures retry the same candidate.
- Only a demonstrated code defect permits a new version and AAB.
- GitHub Environment approval and the commit-bound TEAM gate are external
  authorization controls, not facts inferred from workflow source.

Operational steps and verification levels are defined by the
[exact-artifact Play runbook](../PLAY_RELEASE_RUNBOOK.md) and
[Android signing and release contract](../../../ANDROID_SIGNING_AND_RELEASE.md).

