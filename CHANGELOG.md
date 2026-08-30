# Changelog

## v0.6.0

2026-08-30

**Compatibility**

- Added reviewed renderer mappings and exact source metadata for ChatGPT `26.825.51511`, build `7377`.
- Removed two dependencies on changing internal renderer helpers by owning the usage icon and trusted profile-image validation in the injected UI.

**Managed ChatGPT**

- Changed the managed-primary installer so the same command can update an already patched app.
- Added an official-update preparation step that checks the OpenAI download location, advertised size, app identity, version, build, Apple signature, and Gatekeeper assessment before patching.
- Blocked redirected downloads and managed downgrades before any app replacement.
- Kept router accounts, preferences, thread ownership, backups, and credentials outside the replaceable app bundle.

**Security**

- Updated build 7377 native peer authorization so app tools trust the router signing team without disabling the peer check.
- Required the peer-authorizer addon on current builds and verified its final identifier and signing team.
- Changed the release gate to reject incomplete physical verification evidence.

---

## v0.5.0

2026-08-23

**Compatibility**

- Added recorded ChatGPT `26.818.41509` build `6962` compatibility and current physical verification evidence.
- Changed compatibility decisions from a version-only gate to signed-source provenance and complete structural validation.
- Kept unknown layouts fail-closed while allowing unchanged reviewed layouts to survive a version or hash update.

**Managed ChatGPT**

- Added a managed-primary installer mode that preserves the normal ChatGPT identity and profile.
- Added staged replacement, signing-team continuity checks, and recoverable app backups.
- Added JavaScript parsing, nested signing, Computer Use identity checks, and strict local token permissions.

**Router**

- Added a persistent preferred subscription for new chats while keeping quota failover active.
- Stopped desktop-only runtime settings and legacy notification commands from entering isolated account configs.

**Interface**

- Added account-specific reset actions and explicit reset targets.
- Added subscription identity, quota severity, reset-copy, and reset-expiry helpers with automated tests.

**Delivery**

- Moved repository and Go module ownership to `tony-ng-vn/codex-subscription-router`.
- Added maintained-fork installation, architecture, compatibility, security, and smoke-test documentation.

---

## v0.1.0

2026-08-15

**Router**

- Added multi-subscription routing, account isolation, pooled quota, sticky threads, and failover.

**Interface**

- Added account management, combined profile statistics, account-scoped plugins, and per-account resets.

**Delivery**

- Added source-only build, signing, verification, security, and release tooling.
