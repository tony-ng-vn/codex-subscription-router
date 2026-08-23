# Capability map: maintained subscription router

| Module id | Responsibility | Depends on |
| --- | --- | --- |
| compatibility-engine | Record source provenance, select a compatible patch layout, and validate every required change before installation | None |
| managed-primary | Preserve the normal ChatGPT identity and profile while installing the router through a recoverable staged replacement | compatibility-engine |
| subscription-ui | Show account identity, quota, resets, and selection state in the ChatGPT interface | compatibility-engine, managed-primary |
| release-delivery | Publish the maintained fork with accurate installation, compatibility, recovery, and verification documentation | compatibility-engine, managed-primary, subscription-ui |

Build order: compatibility-engine -> managed-primary -> subscription-ui -> release-delivery.
