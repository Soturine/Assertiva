# Adaptive tool discovery demo: stacks without an engine adapter

Two synthetic projects with the same rule — orders of 10 items or more get 5% off — and the same weak test (`total < gross` for 20 items; nothing at exactly 10):

- `ruby-pricing/` — Ruby, minitest;
- `dotnet-pricing/` — .NET 10, xUnit 2.9.3, Stryker.NET 5.1.0 as a local tool (`.config/dotnet-tools.json`).

The engine recognizes neither runner (`NO_EXECUTABLE_TEST_ADAPTER_RECOGNIZED`). The agent follows `references/ADAPTIVE_TOOLS.md`: research the current tool, download in one container stage, run tests (and Stryker.NET) in another with `--network none`, a read-only project mount and a non-root user, import the results with `--test-results` / `--mutation-report`, record each run as an external execution receipt, and close with feedback about Assertiva. Both stacks show the same gap: a broken boundary (`>=` → `>`) keeps every test green.

The commands, image digests, artifact hashes and results of the 1.1 runs are in `docs/assurance/V1_1_DOGFOOD.md`. Nothing here is a native adapter.
