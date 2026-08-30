# Codex Subscription Router

Use multiple ChatGPT subscriptions from one macOS ChatGPT interface.

This maintained fork can build either a separate Codex Subscription Router app or a managed ChatGPT app that preserves the normal ChatGPT name, profile, bundle identity, URL scheme, and embedded Computer Use service.
It balances new chats across connected subscriptions, keeps follow-up turns with their thread owner, and fails over when an account runs out of quota.
This repository contains source and build tools only.
It does not distribute OpenAI binaries.

Warning: This is an unofficial project and is not supported by OpenAI.
Review the source and the terms that apply to every connected subscription before using it.

![Multi-subscription account menu](screenshots/account-menu.png)

## What it does

- New chats use quota urgency, reset timing, short-window pressure, and a user-selected preferred subscription.
- Follow-up turns stay with the persisted thread owner unless that account is depleted.
- Each secondary account has its own Codex home and credential files.
- The profile menu shows pooled usage, subscription identity, reset availability, and account-specific actions.
- Profile statistics, Apps, MCP connections, and reset consumption can target one subscription.
- The loopback control service uses a random token and never returns OAuth credentials.

## How it works

The desktop opens one app-server connection to a Go multiplexer.
The multiplexer starts one official Codex child for each enabled subscription.

```text
ChatGPT or Codex Subscription Router
        |
        v
    codex-mux
    |-- Primary        -> ~/.codex
    |-- Subscription 2 -> isolated Codex home
    `-- Subscription 3 -> isolated Codex home
             |
             `-- thread ID -> persistent account owner
```

The patcher extracts `app.asar` into a staging directory, detects a reviewed renderer layout, applies every required patch, parses the resulting JavaScript, updates ASAR integrity, signs the complete app, and verifies the signatures.
Only then can it replace an installed destination.

Read [Architecture](docs/ARCHITECTURE.md) and [Security model](docs/SECURITY-MODEL.md) for the detailed request and trust boundaries.

## Compatibility

| Component | Supported value |
| --- | --- |
| Platform | macOS on Apple silicon |
| ChatGPT versions | `26.803.61601`, `26.814.41407`, `26.818.31338`, `26.818.41509`, `26.825.51511` |
| ChatGPT builds | `6396`, `6720`, `6892`, `6962`, `7377` |
| Current verified build | `26.825.51511`, build `7377` |
| Go | 1.26 or newer |
| Node.js | 22.12 or newer |

Known hashes record the exact official source used for a release.
An unrecorded official update may proceed without a code change when its OpenAI signature is valid and every reviewed structural capability still matches.
Any missing capability, new replacement count, JavaScript syntax error, integrity failure, or signing failure stops the build before installation.

Read [Compatibility](docs/COMPATIBILITY.md) for the recorded hashes and validation policy.

## Requirements

- The official ChatGPT app at `/Applications/ChatGPT.app`.
- Xcode Command Line Tools.
- Go 1.26 or newer.
- Node.js 22.12 or newer and npm.
- An Apple Development or Developer ID Application signing identity.

A team-backed signing identity is required for reliable Appshots and Computer Use permissions.
Reuse the same Apple team for every rebuild so macOS can preserve privacy grants.

## Install a separate app

This is the default and safest mode because it leaves the official ChatGPT app unchanged.

```sh
curl -fsSL https://raw.githubusercontent.com/tony-ng-vn/codex-subscription-router/main/install.sh | /bin/bash
```

The installer creates:

- `~/Applications/Codex Subscription Router.app`
- `~/Applications/Codex Subscription Router Computer Use.app`
- `~/Library/Application Support/Codex Subscription Router`

## Install as managed ChatGPT

Managed-primary mode preserves the normal ChatGPT identity and profile while replacing `/Applications/ChatGPT.app` with a signed router build.
The installer creates a recoverable backup before replacement.

```sh
curl -fsSL https://raw.githubusercontent.com/tony-ng-vn/codex-subscription-router/main/install.sh | /bin/bash -s -- --managed-primary
```

The patched app disables its updater because an automatic official update would remove the router changes.
Run the same command again to update an already patched app.
The installer downloads the newest full Apple silicon archive from OpenAI's appcast, verifies the byte count, official OpenAI Apple signature, bundle identity, version, build, and Gatekeeper assessment, and then applies the router in staging.
Account credentials, preferences, and thread ownership remain in `~/.codex-mux` and are not stored in the app bundle.

## Install from a clone

```sh
git clone https://github.com/tony-ng-vn/codex-subscription-router.git
cd codex-subscription-router
npm ci --ignore-scripts
python3 scripts/patch_app.py
```

Use the managed mode manually only when the source and destination are different app bundles.

```sh
python3 scripts/patch_app.py \
  --source /path/to/fresh/ChatGPT.app \
  --destination /Applications/ChatGPT.app \
  --managed-primary \
  --force
```

The `--allow-untested-source` option now bypasses official source-signature verification only.
It does not bypass structural checks, replacement counts, syntax validation, integrity validation, or signing checks.

## Add and select subscriptions

1. Open the profile menu at the bottom of the sidebar.
2. Select `Add another subscription`.
3. Complete the device-code sign-in in the browser.
4. Return to the app and wait for the connected subscription row.

Select `Use now` to prefer one subscription for new chats while it has quota.
Automatic failover remains active when the preferred subscription is unavailable or depleted.

## Reset and usage behavior

Each connected subscription shows its remaining quota and reset-credit status.
The `Apply` action opens the native reset flow with one read-only target subscription.
A reset can never silently apply to a different account.

## macOS permissions

Independent mode needs Accessibility for Codex Subscription Router and Screen and System Audio Recording for its separate Computer Use helper.
Managed-primary mode keeps the ChatGPT identity but still uses the signing team selected during the build.
Changing that team can invalidate existing privacy grants.

## Local data

| Path | Purpose |
| --- | --- |
| `~/.codex` | Primary credentials, conversations, and cache |
| `~/.codex-mux/state.json` | Account metadata, preference, and thread ownership |
| `~/.codex-mux/accounts/<id>/codex-home` | Isolated secondary account data |
| `~/.codex-mux/control-token` | Token for the loopback control service |
| `~/.codex-mux/backups` | Recoverable app and helper backups |

OAuth credentials stay inside each account's Codex home.
The control service binds to `127.0.0.1` and requires the random 256-bit control token for private routes.

## Development and verification

```sh
npm ci --ignore-scripts
npm run check
npm run release:check
npm audit --omit=optional
```

The signed-app procedure is in [Smoke test](docs/SMOKE-TEST.md).

## Known limitations

- A fundamentally new ChatGPT renderer layout still needs a reviewed compatibility profile.
- Managed updates stop before installation when a new renderer layout has not been reviewed.
- Generated applications are tied to one macOS user and signing team.
- The initial merged history fetch is limited to 500 threads per account.
- Releases are source-only and never include patched OpenAI binaries.

## License

The project source is available under the [MIT License](LICENSE).
ChatGPT, Codex, and the official macOS app are OpenAI products and are not covered by this license.
