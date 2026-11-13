# Forbidden-write test against an RLS endpoint: what it proves and what it does not

## Answer

The test shows only that, in this run, the forbidden request returned an error or the visible result set did not change. It does not show that the RLS policy denied the write, that nothing was persisted, that legitimate owner writes still work, or that tenants are separated. Its green is compatible with a policy that denies everything, with a request that failed for an unrelated reason, and with a write that succeeded invisibly. The test should be kept as one part of the evidence, but it cannot carry the claim "the RLS policy enforces owner-only writes and tenant separation" on its own.

## What the evidence rests on

- **OBSERVED (from the scenario description only):** the test asserts that the forbidden write returns an error or changes zero visible rows. There is no persisted-state readback, no audit-event check and no positive-path check.
- **Not observed:** I did not read the test, the policy, the endpoint or the schema, and I ran nothing. The Assertiva engine was not used, so there is no engine run, no mutation result and no CI evidence. Everything below is reasoning from that description.

## What the test can and cannot claim

| Step | Status here |
| --- | --- |
| **Exists** | A forbidden-write test exists. |
| **Selected / executed / outcome** | UNKNOWN from this context: no run or CI evidence. |
| **Proven** | Only the weak form below. |

**Claimable, with limits:** "In this run, the forbidden request did not produce a visible change, and the endpoint returned an error." That is a statement about one request and one visible surface.

**Not claimable:**

1. **That RLS did the denial.** An error can come from validation, a missing row, a wrong id, a routing or middleware check, or a 500. An error-status-only oracle (`ERROR_STATUS_ONLY_SIGNAL` type) cannot tell these apart. A broad error expectation also passes when the endpoint is broken.
2. **That zero visible rows means zero changed rows.** Under RLS, SELECT is filtered by the same policies as writes. A row can be updated, or a new row inserted into another tenant, and the reading role still sees "zero visible rows". The readback goes through the very policy under test, so it cannot distinguish "denied" from "changed but hidden". A filter that matches no row (a wrong id) also gives zero changed rows and proves nothing about the policy.
3. **That nothing was persisted.** Without a readback through a privileged or owner connection, partial writes, triggers, soft-deletes or writes to a related table are invisible to the test.
4. **That owner operations still work.** With no positive path, a policy that denies every write (including the owner's) passes this test green. This is the central gap: the test cannot tell a correct restrictive policy from a broken one.
5. **That tenant separation holds.** Nothing in the description crosses tenants. Whether a second tenant exists in the test data is UNKNOWN.
6. **That the audit trail records the denial.** No audit-event check exists, so UNKNOWN.

## Findings, ranked by consequence

1. **No positive path (high).** The suite cannot detect an over-restrictive policy. Basis: OBSERVED (no positive-path check in the description).
2. **Error and zero-row outcome is a weak oracle (high).** Any error, or any filter that matches nothing, passes. Basis: INFERRED from the assertion described.
3. **Visibility is not persistence (high).** The readback uses the policy under test, so it can hide a changed row. Basis: INFERRED from RLS semantics applied to the described readback.
4. **Tenant separation is untested (medium to high, depending on the product's requirement).** Basis: OBSERVED absence in the description; UNKNOWN whether other tests cover it.

## What I would do next

1. **Add a positive owner path:** the owner's legitimate write succeeds, and the owner reads back the stored values. This makes the forbidden test meaningful, because it shows the policy is restrictive, not broken.
2. **Make the denial specific:** assert the exact error contract (the status and the error code the endpoint is documented to return for RLS denial, for example the Postgres insufficient-privilege code), not "any error".
3. **Read back the stored state through a privileged or owner connection** (not the test role) and compare the full row before and after, so an invisible change is caught.
4. **Add a tenant-separation pair:** tenant A's credentials attempting to write tenant B's row, with tenant B's stored row checked afterwards, and the positive owner case for B.
5. **Check the audit event** if the product records denials, and assert its presence and fields.
6. **Negative control:** in a disposable copy, deliberately weaken the policy (for example make the USING or WITH CHECK clause permissive) and confirm the forbidden test goes red. If it stays green, the test is a false green. This is my own break, not engine-executed evidence, and I would keep its command and output for rerun.
7. **Run against a disposable local database** (a local Postgres or Supabase local stack in a container). Do not point a test at a shared, staging or production Supabase project, and do not use credentials I was not given. Running the suite needs the user's authorization.

## Unknown until those steps are done

- Whether the policy itself is correct, and whether the error comes from RLS rather than from another layer.
- Whether any write persists, invisibly, in the forbidden case.
- Whether owner operations work at all.
- Whether tenant separation holds.
- Whether the test has run in CI, and on which revision.

These stay UNKNOWN because nothing in the context settles them. Running the suite on a disposable local database, with the user's authorization, is the evidence that would settle the executed step; the positive, readback and negative-control steps settle the rest.
