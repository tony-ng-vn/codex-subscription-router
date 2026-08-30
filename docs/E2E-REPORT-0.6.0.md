# v0.6.0 verification report

Recorded on 30 August 2026 for ChatGPT build 7377 compatibility and managed updates.

Release status: incomplete until the final commit passes the signed runtime and interface checks below.

## Physical baseline

| Item | Tested value |
| --- | --- |
| macOS | `26.6` (`25G5057c`) |
| Architecture | Apple silicon (`arm64`) |
| Official ChatGPT version | `26.825.51511` |
| Official bundle build | `7377` |
| Pristine `app.asar` SHA-256 | `f56ac8d5254a10fc4a04e7417fa787d135c3bbca49bad7d668d4ae65833d40c7` |
| Renderer profile | `build_7377` |

## Passed

- The exact official build 7377 source passed OpenAI signature, bundle identity, and structural compatibility checks in a disposable staging copy.
- The live OpenAI appcast selected version `26.825.51511`, build `7377`, from the required full Apple silicon archive path.
- Unit tests cover feed selection, hostile download hosts, missing Apple silicon releases, matching bundle metadata, and version mismatch rejection.
- The repository Go, JavaScript, Python, and shell checks pass with 30 Python tests and 6 interface-helper tests.

## Remaining release checks

- Download the full official archive and confirm its advertised byte count, OpenAI signature, and Gatekeeper assessment.
- Build and sign the final managed app from that downloaded source.
- Verify the signed outer app, desktop executable, `codex.real`, and Computer Use helper identities.
- Launch the final app and exercise account rendering, preferred selection, thread ownership, reset targeting, Plugins, Appshots, and Computer Use.
- Confirm backup creation and restore verification before publishing a tag.
