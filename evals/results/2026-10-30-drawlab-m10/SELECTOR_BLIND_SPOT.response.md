# Six selected tests, a feature flag and a dynamically loaded plugin

## Answer

A green run of the six selected tests proves **only those six tests, at that revision, in that environment**. It does not prove the change is safe, and it does not show that the rest of the suite is unaffected. The change reaches a feature flag and a dynamically loaded plugin. The dependency graph cannot see either of them, so the selector's mapping has no proven scope there. Whatever the flag and the plugin affect is **UNKNOWN** until the selection is widened to cover them.

## What can be claimed

| Claim | Basis | Evidence |
| --- | --- | --- |
| The selector picked six tests for this diff | OBSERVED | the selector's output |
| Those six have a path to the changed code in the dependency graph | INFERRED by the selector, or DECLARED if it uses a project map | the import or fixture graph the selector used |
| The six pass at this revision | OBSERVED only if their run, with its exit status and revision, was seen; otherwise UNKNOWN | the run's per-test outcomes and exit code |
| The change touches a feature flag and a plugin loaded at runtime, outside the graph | OBSERVED from reading the diff and the loading mechanism (entry points, registry, `importlib`, config) | the diff, the flag definition, the plugin loader |

## What cannot be claimed

- **"Only these six tests are affected."** The graph is incomplete for this change. A heuristic or graph-based selection can exclude tests only inside its proven scope, and dynamic loading and flag-dependent behavior are outside it. Unknown relations widen the selection; they do not shrink it.
- **"The plugin still works."** Nothing ties the six tests to the plugin's code path. Exists, selected and executed are all unknown for the plugin.
- **"Both flag states are safe."** Unless the six tests run with the flag on and off, at most one state was exercised. The other flag state, and any code only it enables, is untested by this run.
- **"Full suite green" or "release-gate green."** A green selected set is never the full suite or the gate.
- **"CI validated this,"** unless a CI run with a head SHA equal to HEAD, on a clean tree, is observed.

## What I would do next

1. **Widen the selection along the blind spots.**
   - Flag: find every read of the flag in the code and config, and the tests that set or depend on it. Include tests for **both** flag states. Note which default each environment uses (local, CI, production), because a flag default that differs between them is a parity gap.
   - Plugin: find how it is discovered (entry points, registry, a config list, a naming convention) and which tests load it, both its own tests and integration tests that go through the loader. Include those tests. If none exist, report that as a gap.
   - Shared fixtures and configuration touched by the diff widen the selection as well.
2. **Use the engine's change analysis.** `assertiva audit <project> --changed-since <REV> --execute` reports proven paths, widening and project-declared maps, and runs the selected set in a disposable copy. Check whether it already widens for config or dynamic imports. Wherever it cannot prove impact, treat the relation as unknown and add the tests manually.
3. **Run the widened set, or the full suite if the widening is large or uncertain,** through the engine. A full run is often cheaper than proving the mapping is complete.
4. **Check for a real crossing.** Make sure at least one test loads the actual plugin through the real loading mechanism with the changed flag state, not a double of the plugin. If no such test exists, propose one. Writing it would go through `assertiva improve` and need the human's approval.
5. **Tie the result to the revision.** Keep the command, the exit code, the revision and the environment, including flag values. If CI is the gate, check for a provider run on HEAD.

## What remains unknown

- **The behavior of the plugin after the change.** No selected test is shown to load it. Running its tests, or the loader's integration tests, settles it.
- **The behavior under the other flag state.** The six tests probably use one default. Running tests in both states settles it.
- **Whether the six actually passed.** Only if their run was not observed. The run with its exit status settles it.
- **Whether the selector missed anything else.** The graph has known blind spots, so its exclusions carry no proof. A widened or full run settles it.
- **Whether CI, with its own flag configuration, runs the relevant tests on this revision.** The workflow files (declared) and a provider run with a matching head SHA (observed) settle it.

What this answer rests on: only the situation described. No selector output, diff or run was observed here.
