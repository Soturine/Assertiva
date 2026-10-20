# Contract fixtures

Real Pact output, unedited, produced on 2026-10-20 with pact-python 4.1.0 (Pact Rust FFI 0.5.10):

- `generate.py` writes `pacts/orders-web-pricing-api.json` (two interactions with provider states) and
  `pacts/reports-job-pricing-api.json` (no interactions) from consumer tests against Pact's mock server, then
  verifies the first against a local provider that answers correctly (`verification-verified.json`) and one that
  answers a string where the consumer expects an integer (`verification-broken.json`), and the empty contract
  (`verification-empty.json`: the run reports success with nothing checked).
- `generate_pending.py` marks the first interaction pending and verifies it against the broken provider
  (`verification-pending.json`: the run reports success although that interaction failed).
