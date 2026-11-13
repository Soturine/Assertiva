# Android builder: what the green tests prove, and what they do not

## Answer

The current evidence supports one claim: the WebView preview works, and the generated APK contains a manifest. It does not support any claim that the installed app works, that it matches the preview, or that its bridge is restricted to approved origins. The installed app is the product, and nothing in this context exercises it. The shell-asset staleness and the unapproved-origin bridge call are open risks, and the second one is a potential security defect, not a confirmed one.

Basis for this answer: the scenario description only. No run, no build, no APK inspection, no install. The Assertiva engine's output is not part of this context, so there is no engine evidence.

## What the evidence supports

| Claim | Basis | Why |
| --- | --- | --- |
| The WebView preview renders and works. | OBSERVED (per the scenario) | Seen working. It proves the preview path only. |
| The generated APK contains a manifest file. | OBSERVED (a test confirms it) | Proves that one file exists in the artifact. It says nothing about manifest contents (permissions, exported components, launcher activity, package id), the app starting, or the APK being installable. |
| The installed app is implemented by a synchronized shell template and a serialized config. | DECLARED (scenario) | Describes the structure. Whether those files are the ones in the APK is not shown. |

## What the evidence does not support

- **Preview-to-export parity.** The preview and the installed app run through different paths: the preview is served from the working tree, while the installed app runs from the synchronized shell template and the serialized config. Nothing shows they are the same. A green preview test and a green manifest test would both stay green if the shell assets in the APK were stale. This is a false green for parity.
- **The installed app works.** No APK was installed or launched. The manifest test does not start an activity, load the WebView, or call the bridge. Status: UNKNOWN.
- **Shell assets are current.** The scenario says they go stale. Until the shipped assets are compared with the template and the config, staleness is INFERRED as a risk, not observed. It may already be present in the artifact.
- **Bridge access is restricted to approved origins.** The scenario says the bridge "may be invoked" from an unapproved origin. That is a report, not an observation. It is also not shown that an origin allowlist exists in the installed config, or that the bridge checks it. Status: UNKNOWN, with a serious consequence if confirmed, because a native capability reachable from arbitrary web content is an exposure.

## Findings, ranked by consequence

1. **Bridge reachable from an unapproved origin (potential security defect, basis INFERRED from the report).** Consequence: a native capability could be driven by content the app does not trust. Priority: high until disproven. What would settle it: load a page from an unapproved origin in the installed-app WebView and call the bridge. Expected: rejection. Also check the origin allowlist in the serialized config and the code path that enforces it. Do not claim exploitability without that run.
2. **Preview and installed app may diverge (false green for parity, basis INFERRED).** Consequence: the preview test protects the preview, not what users install. What would settle it: extract the APK in a disposable directory and compare the shipped shell assets and config with the template and config hashes at the same revision.
3. **Stale shell assets (basis INFERRED from the scenario).** Consequence: the installed app may ship behavior the source no longer has. What would settle it: the same hash comparison as finding 2, plus a check that the build regenerates the shell from the template before packaging.
4. **Manifest test is too weak for the claim it supports (basis OBSERVED as a test scope, INFERRED as a gap).** Consequence: a manifest that exists but has the wrong permissions, an unexported or missing launcher activity, or a wrong package id would still pass. Strengthen it to assert the specific fields that matter, from the contract, not from the current output.

## What would settle each open claim, and what it needs

- **Installed app behavior:** install the generated APK on an emulator or device and run the same flow the preview covers, plus the bridge origin check. Needs the user's authorization for a device or emulator and an APK build. Without it, UNKNOWN.
- **Artifact parity and staleness:** extract the APK in a disposable directory outside the project, then compare hashes of the shell assets and config with the template at the audited revision. Read-only on the project. Needs no device.
- **Bridge origin enforcement:** a targeted test in the installed-app WebView (or an instrumented test) that loads an unapproved origin and asserts the bridge call is refused, plus a negative control: remove the check in a disposable copy and confirm the test fails. The negative control is my own break and is not engine-executed evidence.
- **Build freshness:** confirm the build regenerates the shell from the template before packaging, and that a CI run is tied to HEAD (its head SHA equals `git rev-parse HEAD`). A CI green on another revision proves nothing about this one.

## Recommendations

1. Do not describe the preview test or the manifest test as evidence that the app works or that the export matches the preview.
2. Treat the bridge origin question as the first thing to settle, before any release. Ask the user whether a device or emulator run is authorized.
3. Add the artifact hash comparison as a delivery check, so parity and staleness are measured on the built APK, not the source tree.
4. Strengthen the manifest assertions to the specific fields the install depends on.
5. Keep the claims in the report apart: preview (observed), artifact manifest (observed, narrow), installed behavior (unknown), bridge origin (unknown, potential defect).

## Unknown

- Whether the installed app launches and renders the same content as the preview.
- Whether the shell assets in any generated APK are current.
- Whether the bridge enforces an origin allowlist, and whether the reported unapproved-origin call succeeds.
- Whether any CI run covers the revision under discussion.

No aggregate score or overall risk rating is given. The protected surface is the preview and the presence of a manifest in the artifact. The unprotected surface is the installed app, its assets, and its bridge boundary.
