# Architecture

Codex Subscription Router supports an independent app and a managed-primary ChatGPT app.
Both modes replace the staged bundle's `codex` executable with a small Go multiplexer and keep the original executable beside it as `codex.real`.

## Build transaction

The patcher reads the source version, build, pristine ASAR hash, bundle identity, and signing team.
A recorded hash selects exact replacement counts.
An unrecorded source must have an official OpenAI signature and match a reviewed renderer layout and replacement-count set.

The patcher copies the source into staging, extracts `app.asar`, applies every required patch, parses changed JavaScript, repacks the ASAR, updates its integrity record, signs nested code, signs the outer application, and verifies the final signatures.
The destination is replaced only after the staged application passes all checks.
An existing destination moves to `~/.codex-mux/backups` first.

## Installation modes

Independent mode uses bundle identifier `app.cdxmux.multi`, a separate Chromium profile, a separate URL scheme, and a separate Computer Use app.
It leaves `/Applications/ChatGPT.app` unchanged.

Managed-primary mode preserves the ChatGPT display name, `com.openai.codex` bundle identifier, `codex` URL scheme, standard profile, and embedded Computer Use path.
It replaces `/Applications/ChatGPT.app` only after staging succeeds and keeps a recoverable backup.
The source for this mode must be a fresh official ChatGPT bundle, not an already patched app.

## Request routing

The desktop opens one JSON-RPC app-server connection to the multiplexer.
The multiplexer starts one real app-server child for every enabled account.
Each child has an isolated `CODEX_HOME` and `CODEX_SQLITE_HOME`.

New threads use a quota-urgency score and may honor a persisted preferred account while that account remains eligible.
Weekly reset timing, banked resets, short-window usage, pinned-thread count, and stable account order break routing ties.
Once a thread ID is known, `state.json` persists its owner.
If the owner is depleted, the multiplexer resumes the thread on an account with capacity and updates ownership.

## Account isolation

The Primary account uses `~/.codex`.
Secondary accounts use `~/.codex-mux/accounts/<id>/codex-home`.
Managed configuration is copied from Primary without credential-store settings, project trust, desktop-generated `node_repl` configuration, or legacy router notification commands.
Each isolated account forces file-backed CLI and MCP OAuth credentials.

## Renderer integration

The renderer patch adds the account menu, pooled usage, per-account profile and plugin scope, reset targeting, and thread ownership display.
Compatibility profiles describe reviewed minified layouts rather than ChatGPT version numbers.
The patcher still requires exact cardinality for each patch location and rejects an unknown layout.

## Control API

The renderer talks to a loopback HTTP service on port `48123`.
All private routes require a random 256-bit token.
CORS is limited to the app origin.
The service returns account metadata, quota, profile data, thread ownership, and authenticated events.
It never returns OAuth tokens.
