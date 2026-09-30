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

## Retry discipline
Retry only when transient behavior is plausible or the retry itself is diagnostic, and always preserve the first failure.

## After fix
~~~text
minimal reproducer
-> affected branch
-> original failing composition
-> broader gate if required
~~~
