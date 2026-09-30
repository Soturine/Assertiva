# Derivanta Integration

Assertiva is independent from Derivanta.

~~~text
Derivanta
  -> derives project context/risk/workflow
  -> activates Assertiva when test assurance is material
Assertiva
  -> audits/selects/diagnoses/verifies test evidence
  -> returns evidence/findings/limitations
Derivanta
  -> composes result with architecture/security/release/etc.
~~~

## Ownership boundary
Derivanta owns broad engineering context and cross-domain audit. Assertiva owns test-suite quality, adaptive test execution, test impact evidence, failure localization, diagnostic escalation, evidence compression and Test Evidence Graph semantics.

Assertiva must work without Derivanta, and Derivanta must remain useful if Assertiva is unavailable.
