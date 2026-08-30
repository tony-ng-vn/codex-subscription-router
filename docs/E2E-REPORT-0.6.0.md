# v0.6.0 verification report

Recorded on 30 August 2026 for ChatGPT build 7377 compatibility and managed updates.

Release status: complete.

## Physical baseline

| Item | Tested value |
| --- | --- |
| macOS | `26.6` (`25G5057c`) |
| Architecture | Apple silicon (`arm64`) |
| Official ChatGPT version | `26.825.51511` |
| Official bundle build | `7377` |
| Pristine `app.asar` SHA-256 | `f56ac8d5254a10fc4a04e7417fa787d135c3bbca49bad7d668d4ae65833d40c7` |
| Installed patched `app.asar` SHA-256 | `8c1bb6af49500b537ffcd069ab1655b9c689eb1dde33440f96e14720cad126cd` |
| Renderer profile | `build_7377` |
| Router signing team | `WYMJ4KK3T2` |

## Passed

- The exact official build 7377 source passed OpenAI signature, bundle identity, and structural compatibility checks.
- The live OpenAI appcast selected version `26.825.51511`, build `7377`, from the required full Apple silicon archive path.
- The downloaded archive matched its advertised byte count and passed OpenAI code-signature and Gatekeeper checks before patching.
- The updater rejects a redirected feed, a redirected archive, an unsafe byte count, a hostile download host, a missing Apple silicon release, and a build older than the installed app.
- The final managed app passed strict nested signature checks before installation.
- The desktop app, `codex`, `codex.real`, Computer Use helper, Node runtimes, and native peer-authorizer addon use the router signing team.
- A direct native authorization probe accepted a signed `node` peer and its signed parent chain.
- The account menu rendered the router controls on build 7377.
- The Plugins page rendered account-scoped controls for the selected subscription.
- The router health endpoint passed before installation with all 9 saved account records, 1 active controller, and 1 preferred account intact.
- The supported installer replaced `/Applications/ChatGPT.app`, reopened it, and the current process loaded its executable from that path.
- The live router listens on `127.0.0.1:48123`, and the live app-tools bridge handles requests without a peer-signing rejection.
- The installer created a private rollback directory with mode `700` at `~/.codex-mux/backups/20260830-160536`.
- The rollback app reports version `26.825.51511`, build `7377`, and retains the exact pristine `app.asar` hash above.
- The repository Go, JavaScript, Python, shell, release, and dependency-audit checks pass with 40 Python tests and 6 interface-helper tests.

## Recorded limits

- The restarted task sandbox cannot read the user's signing certificate chain, so post-install `codesign --verify` reports `CSSMERR_TP_NOT_TRUSTED` even though the same installed artifact passed strict verification before the atomic move.
- Computer Use reached its application-approval gate, but this Mac has not approved ChatGPT or Finder as a target.
- No Computer Use click was performed and no macOS permission was changed during this verification.
- The rollback bundle and restore location were verified, but the live app was not swapped back because that would undo the completed installation.
