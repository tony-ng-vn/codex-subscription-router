# Spec: maintained Codex Subscription Router

## Objective

Publish Tony Nguyen's maintained fork with the implementation currently running on ChatGPT `26.818.41509` build `6962`.
The patcher must treat a source hash as provenance rather than the only compatibility decision.
It must accept an unrecorded source only when a complete staged patch validates, and it must leave the installed application unchanged when validation fails.

## Tech stack

- Go for the local multiplexer and control service.
- Python for ASAR patch orchestration, validation, signing, backup, and installation.
- JavaScript for ChatGPT renderer additions and helper tests.
- Shell for the one-command installer.

## Commands

- Focused Python tests: `python3 -m unittest scripts.patch_app_test`
- Focused JavaScript tests: `node --test test/*.test.cjs`
- Required suite: `npm run check`
- Release validation: `npm run release:check`
- Dependency audit: `npm audit --omit=optional`

## Project structure

- `scripts/patch_app.py` contains compatibility detection and the staged patch transaction.
- `scripts/patch_app_test.py` covers compatibility, signing, token permissions, and managed-primary behavior.
- `internal/` and `cmd/` contain the Go multiplexer.
- `ui/` contains renderer additions.
- `test/` contains JavaScript helper tests.
- `docs/` contains compatibility, architecture, security, smoke-test, and release documentation.

## Code style

Compatibility checks must name the capability they failed to locate.
They must validate exact replacement counts and reject partial patches.

```python
profile = detect_renderer_profile(bundle)
if profile is None:
    raise RuntimeError("no supported renderer layout matched the source bundle")
```

## Testing strategy

Pure compatibility decisions receive small unit tests.
The patch transaction must be tested against the verified build `6962` source structure when a pristine source bundle is available.
The final application requires syntax checks, signature verification, a health check, and a smoke test of account selection and routing.

## Threat model and boundaries

The official ChatGPT bundle, extracted ASAR contents, account metadata, and network responses are untrusted inputs.
The assets at risk are ChatGPT credentials, account-isolated Codex homes, the loopback control token, Apple signing identity continuity, and the installed application.

- Always: stage changes outside the installed app, require complete structural validation, preserve a recoverable backup, keep the control service loopback-only, and reject insecure token permissions.
- Ask first: change account isolation, credential handling, loopback authentication, or signing-team continuity.
- Never: commit credentials or the control token, silently patch only part of a build, weaken replacement counts to force a build through, or overwrite the installed app before validation and signing succeed.

## Success criteria

- Build `6962` is recorded with its verified pristine ASAR hash and patch-layout metadata.
- A version or hash mismatch does not fail before structural validation begins.
- An unrecorded source installs only when every required patch, JavaScript syntax check, integrity check, and signature check succeeds.
- Any failed capability leaves the installed app unchanged.
- Managed-primary and independent-copy modes remain available.
- The current subscription selector behavior and tests are preserved.
- The required suite and release checks pass.
- The PR is merged into `tony-ng-vn/codex-subscription-router` main.

## Open questions

None.
