# Changelog

## v0.5.0

2026-08-23

**Compatibility**

- Added verified ChatGPT `26.818.41509` build `6962` support.
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
