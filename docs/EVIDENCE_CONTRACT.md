# Evidence Contract

Agent context should receive enough information to choose the next action without loading every raw artifact.

Preserve when material:
- exact revision/commit and dirty state;
- environment/platform;
- configuration/profile/feature flags;
- data/DB/schema version;
- selected, executed, passed, failed, skipped, not-run, retried;
- runner/version;
- selector method and limitations;
- diagnostic level;
- fidelity;
- raw artifact references;
- redaction state;
- timing/seed;
- residual unknowns.

## Raw artifacts
Compression is not deletion. Raw stdout/stderr, traces, screenshots, videos, coverage reports, profiler output, and structured reports should remain retrievable when practical.

## Secret handling
Never blindly expose all locals or environment values to a coding agent. Prefer relevant/allowlisted values and redaction.
