# Additional Test Modalities

Assertiva should recognize relevant evidence without requiring every project to use every modality.

## Snapshot / golden

Track update provenance. Bulk-regenerating snapshots/goldens after a failure is not evidence of correctness. Review semantic diffs and authoritative source.

## Async / concurrency / race

Preserve scheduler/runtime, timing controls, seeds, repeat count and race-detector/instrumentation evidence where applicable. Sleeps and repeated passes are not substitutes for a concurrency oracle.

## Migration / schema / recovery

Validate upgrade, downgrade/rollback where supported, data preservation, idempotency, partial-failure recovery and compatibility across supported versions.

## Contract / compatibility

Check producer-consumer/API/schema compatibility at the boundary actually claimed. Mock-only evidence does not become real contract evidence by naming.

## Performance / resource

Record workload, environment, warmup, sample size/distribution and thresholds. One timing result is not a stable performance claim.

## Security

Security tests need threat/control scope and authorized environment. A generic unit pass is not proof of security posture.
