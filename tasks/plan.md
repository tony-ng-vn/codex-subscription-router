# Implementation plan: maintained subscription router

## Overview

Recover the verified managed-primary implementation, make compatibility depend on structural validation, integrate the current subscription UI work, and ship the result through Tony Nguyen's fork.

## Architecture decisions

- Keep known version and hash records for provenance and regression tests.
- Choose patch behavior from validated source structure instead of the version number alone.
- Run all patching, syntax checks, signing, and integrity checks in staging before replacing an installed app.
- Preserve both managed-primary and independent-copy installation modes.

## Task list

### Phase 1: Foundation

- Port the verified build `6962` patch and managed-primary tests.
- Replace the version gate with structural compatibility validation.

### Checkpoint: foundation

- Focused Python tests pass.
- Unknown but structurally compatible sources reach staged validation.
- Missing capabilities fail before installation.

### Phase 2: Working application

- Port managed-primary installation, signing, backup, and recovery behavior.
- Integrate the current subscription selector and usage display.

### Checkpoint: working application

- Go, Python, JavaScript, and shell checks pass.
- Signed app and helper identities verify.
- The loopback health check and account menu work.

### Phase 3: Delivery

- Update fork URLs, version, changelog, compatibility documentation, and smoke-test instructions.
- Review the final diff, audit dependencies, push, open the PR, monitor checks, and merge.

## Risks and mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Upstream minifier changes a required layout | High | Detect layouts structurally and fail before replacing the app |
| Partial patch creates a broken or unsafe app | High | Require exact capability counts, JavaScript parsing, signing, and integrity verification in staging |
| Re-signing breaks Computer Use or privacy grants | High | Preserve signing-team continuity and verify nested identities |
| A build appears compatible but fails at runtime | Medium | Keep known build records and run the signed-app smoke test before release |

## Open questions

None.
