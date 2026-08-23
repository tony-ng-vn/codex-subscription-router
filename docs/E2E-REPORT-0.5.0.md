# v0.5.0 verification report

Recorded on 23 August 2026 for the maintained-router merge candidate.

Release status: incomplete until the final tagged commit is rebuilt from a fresh official ChatGPT bundle and the manual checks below are repeated.

## Physical baseline

| Item | Tested value |
| --- | --- |
| macOS | 26.6 (`25G5057c`) |
| Architecture | Apple silicon (`arm64`) |
| Installed ChatGPT version | `26.818.41509` |
| Installed bundle build | `6962` |
| Installed patched `app.asar` SHA-256 | `3cb5ea8a4fe780c6f278b92e8201dba295f697744ffaea572c533d3f0491fc8c` |
| Signing team | `WYMJ4KK3T2` |

## Passed

- The installed managed ChatGPT app and nested `codex.real` executable passed strict code-signature verification.
- The installed app retained identifier `com.openai.codex` under signing team `WYMJ4KK3T2`.
- The local router health endpoint returned `{"ok":true}`.
- The build 6962 renderer was extracted separately and matched the reviewed `latest` structural profile.
- The pristine build 6962 ASAR hash is recorded in `docs/COMPATIBILITY.md`.
- The repository Go, JavaScript, Python, shell, release, and dependency checks passed for the merge candidate.

## Remaining release checks

- Rebuild the final tagged commit from a fresh official build 6962 or later bundle.
- Exercise account rendering, account preference, account-specific reset, quota failover, Plugins, Appshots, and Computer Use against that exact build.
- Record the final commit and repeat the signature and backup-restore checks before publishing a tag.

The physical baseline proves the managed architecture works on build 6962, but it is not a substitute for testing the exact release commit.
