# effectiveness-matrix

The same test defects written in three ecosystems (Python/pytest, JavaScript/Vitest, Kotlin/JUnit 5), each beside a
strong control test that must not be nominated. Read statically only; nothing here is executed.

| Defect | Expected candidate |
|---|---|
| exception caught and ignored | FALSE_GREEN (SWALLOWED_EXCEPTION) |
| assertion only inside a condition | FALSE_GREEN (CONDITIONAL_ASSERTION) |
| value compared with itself | FALSE_GREEN (TAUTOLOGY) |
| bare status / any error | WEAK_ORACLE |
| "integration" test with every boundary replaced | FIDELITY_MISMATCH |
| two tests with the same body | REDUNDANCY |
| repeated parameter row | DUPLICATE_CASES |
| fixed sleep | SMELL (SLEEP / FIXED_WAIT) |
