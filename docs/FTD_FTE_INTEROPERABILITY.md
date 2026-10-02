# FTD / FTE Interoperability

Assertiva is independent from Functional Test Designer (FTD) and Functional Test Executor (FTE).

FTD is an optional authority-rich Test Case source. When it provides a Test Case, Assertiva should preserve its identity, expected result, provenance, readiness and automation suitability. Assertiva may choose how to execute/diagnose it, but must not silently rewrite the oracle to get green.

FTE is an optional Azure Test Plans execution/publication bridge. Projects using GitHub only, another TMS or no TMS do not need it.

```text
existing tests ─┐
FTD TCs ────────┼→ Assertiva assurance/execution/diagnosis
CI/CD evidence ─┘
                         ↓
                 FTE/Azure (optional)
```

Ownership:
- FTD: design + oracle provenance;
- Assertiva: test intelligence, assurance, adaptive execution and diagnosis;
- FTE: Azure Test Plans fetch/publish bridge;
- Derivanta: broader engineering governance/research/audit.
