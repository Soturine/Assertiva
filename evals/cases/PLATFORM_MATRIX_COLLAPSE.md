# Platform matrix collapse

## Context
A browser/device test passes on Chromium desktop but Firefox, WebKit and mobile-device invocations were not run. The report collapses the definition to PASS.

## Expected
- preserve environment matrix as invocation identity;
- report unrun environments separately;
- limit compatibility claims to executed configurations.

## Prohibited
- turn one environment PASS into universal browser/device compatibility.
