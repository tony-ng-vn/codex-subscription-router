# Signed-app smoke test

Run this checklist on the exact source and commit intended for release.
Use a team-backed signature and the same Apple team as the previous installed build.

## Source and staging

- Record the ChatGPT version, build, pristine ASAR SHA-256, renderer layout, macOS version, and router commit.
- Confirm an unrecorded source has a valid official OpenAI signature.
- Confirm every structural patch and JavaScript parse completes in staging.
- Force one expected anchor to fail in a disposable test and confirm the installed destination remains unchanged.

## Identity and recovery

- Verify the app and every nested Computer Use application with `codesign --verify --deep --strict`.
- Confirm the outer app, `codex.real`, desktop executable, helper, and client report the intended identifiers and signing team.
- Rebuild once and confirm the prior destination moves to `~/.codex-mux/backups`.
- Restore that backup in a disposable location and confirm its signature remains valid.

## Accounts and routing

- Connect at least two subscriptions and confirm identity, plan, quota, reset status, and loading states.
- Select `Use now` on the second subscription and confirm a new chat uses it while it has capacity.
- Confirm follow-up turns stay with the persisted thread owner.
- Deplete the preferred subscription and confirm routing fails over automatically.
- Deplete every subscription and confirm the pooled quota alert.

## Resets, profile, and plugins

- Open an account-specific reset and confirm the target subscription is read-only.
- Consume a reset and confirm only that subscription changes.
- Toggle combined and per-account profile statistics.
- Select each subscription in Settings and confirm Apps, MCP status, and MCP OAuth login use that account while definitions remain shared.

## Appshots and Computer Use

- Grant the required macOS privacy permissions for the selected installation mode.
- Capture an Appshot from the attachment menu and keyboard shortcut.
- Run a Computer Use task and confirm the signed helper performs the action.
- Rebuild with the same signing team and confirm the existing privacy grants still work.

## Release record

- Record all commands and results in the release notes.
- Record any skipped physical Mac verification as incomplete.
- Do not publish a release when a required item is unverified.
