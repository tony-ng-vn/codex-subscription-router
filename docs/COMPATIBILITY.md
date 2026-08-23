# Compatibility

The source hash records provenance.
The staged structural checks decide whether a source can be patched.

## Release 0.5.0

| Component | Tested value |
| --- | --- |
| Official ChatGPT version | `26.818.41509` |
| Official bundle build | `6962` |
| Pristine `app.asar` SHA-256 | `8eb91bd9efbf9a4dd04b9b0afdbfcb4e0bab5da18c1919ad74ca327c00c7e791` |
| Renderer layout | `latest` |
| Architecture | Apple silicon `arm64` |

This release includes the managed-primary installation currently used on build `6962`, persistent account preference, account-specific resets, subscription display helpers, and structural compatibility validation.

## Recorded official sources

| Version | Build | Pristine `app.asar` SHA-256 | Renderer layout |
| --- | --- | --- | --- |
| `26.803.61601` | `6396` | `d5a44ed9e2f1db5f81dbbe85408aed256f3203c5b16f00817bb9d7cd941343cf` | `legacy` |
| `26.814.41407` | `6720` | `8fba32f8baa6d984b0f0f4149d3da46221e3adb3b52836f85fe65e31e655a8c0` | `direct` |
| `26.818.31338` | `6892` | `7db5508d4acd2c324cc572cd6f8d6d07900d185831bd6d54005a573e7186de54` | `current` |
| `26.818.41509` | `6962` | `8eb91bd9efbf9a4dd04b9b0afdbfcb4e0bab5da18c1919ad74ca327c00c7e791` | `latest` |

## Structural validation

An exact recorded hash uses its exact reviewed Computer Use replacement counts.
An unrecorded source must first have an intact `com.openai.codex` signature from a recorded OpenAI team.
The patcher then requires one reviewed renderer layout and one match for every required renderer, main-process, request-bridge, profile, plugin, reset, thread, and Computer Use change.
Unrecorded Computer Use counts must match a previously reviewed count.
The patcher parses every changed JavaScript bundle using Node.js before repacking the ASAR.
It updates `ElectronAsarIntegrity`, signs nested code deepest-first, signs the outer app, and verifies the final identifiers and teams.
Installation happens only after every staged check succeeds.

This policy allows a version or hash change to pass when the actual patch layout is unchanged.
It does not attempt a partial patch when OpenAI changes a required layout.

## Diagnostic override

`--allow-untested-source` bypasses the official source-signature requirement.
It does not bypass renderer-layout detection, replacement-count validation, JavaScript parsing, ASAR integrity, or code-signing verification.
Use it only for local diagnostics with a source you control.

Never add a new renderer fingerprint or replacement count without reviewing the extracted upstream code and completing the signed-app smoke test.
