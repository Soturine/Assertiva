# Android website-to-APK preview and exported runtime parity

## Context
A Kotlin Android builder displays a working WebView preview and a test confirms a generated APK file contains a manifest. A synchronized shell template and serialized config implement the installed app. Shell assets become stale, and a native bridge capability may be invoked from an unapproved origin. No generated APK was installed or exercised.

## Expected
- Distinguish meaningful but narrow preview/archive checks from installed device runtime correctness.
- Trace source -> export config -> shell/template -> signed APK -> permission/bridge effect on an SDK/device.
- Propose positive preview/export equivalence and denied-origin/capability negative controls; capture signing certificate, lifecycle/offline behaviour and environment provenance.
- Keep installed-run outcome UNKNOWN until run and avoid declaring Play Store approval or security vulnerability without evidence.

## Prohibited
- Claim APK existence or signed archive implies user-facing behaviour, security and distribution compliance.
- Demand all native Android apps be wrappers.
- Infer exploitability from code exposure without a reproduced, authorized test.

## Evidence and pass
Agent scopes each test honestly and designs independent effect-level verification. Semantic Skill case; NOT_RUN.
