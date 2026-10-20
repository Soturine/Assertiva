# Failure Localization and E2E Decomposition

When a large test fails, search for the smallest evidence that reproduces and discriminates the failure.

~~~text
failing journey
 -> step/stage
 -> boundary/component
 -> contract/integration
 -> service/domain
 -> persistence/provider
~~~

The descent is not always unit-first. Use the layer that reproduces the real failure.

## Clustering
Cluster by root exception, first meaningful common frame, component/boundary, shared fixture/setup failure, external dependency, first divergent journey step, or changed owner.

Preserve outliers. A cluster is a diagnostic hypothesis, not proof of one root cause.

### What the engine infers (0.9.0)

From the failure text a runner reports and the local history store (`audit --execute` and `improve`):

- **Origin**, always INFERRED: `INFRASTRUCTURE` (the text names the environment: a refused connection, a missing executable or browser, resources), `TEST` (the test's own code raised something other than an assertion), `PRODUCT` (the code under test raised), or `UNKNOWN`. An assertion that did not hold stays `UNKNOWN` on purpose: the product's behavior or the test's expectation changed, and only reading both decides.
- **Novelty**: `NEW_FAILURE` (it only passed before; `passed_before_at` names the revision when it passed just before: a regression), `RECURRING` (the same failure fingerprint was recorded before), `CHANGED_FAILURE`, `NO_HISTORY`.
- **Clusters**: failures of one run raised at the same place with the same exception type, whatever their messages say (`failure_clusters`). Identical text at different places is not a cluster.
- **Order dependence** (improve): a failure of the full run that passes every time it is rerun alone gets one bounded repeat of the full run (when it took at most 300 s). Failing again the same way gives `ORDER_DEPENDENT_SUSPECT` and fails the stability check; passing keeps the intermittent verdict, with the probe recorded. One probe suggests order dependence; it does not prove it, and it does not find the polluting test.

## Retry discipline
Retry only when transient behavior is plausible or the retry itself is diagnostic, and always preserve the first failure.

## After fix
~~~text
minimal reproducer
-> affected branch
-> original failing composition
-> broader gate if required
~~~
