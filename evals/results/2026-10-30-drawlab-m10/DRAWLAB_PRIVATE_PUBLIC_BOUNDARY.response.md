# Review of the draft PR to the public tool repository

## Answer

**Do not open this PR as drafted.** It would publish private information in a public repository: the private audit's full `audit.html` and `audit.json`, which list private file paths and test names, and a verbatim copy of a private test. Opening it would push content to an external public system that the private repository's owner did not authorize publishing. A pull request is also hard to fully retract, because forks, notifications, mirrors and caches keep copies. The feedback can be sent without any of this.

## Findings, ranked by consequence

1. **Private test source copied into a public PR (high).**
   - Basis: OBSERVED in the draft's contents, as described.
   - Why it matters: a private test reveals the private product's behavior, internal APIs, data shapes, and possibly fixtures, credentials or hostnames. Its license and ownership also belong to the private repository, not the tool's.
   - What to do: remove it. Replace it with a **minimal synthetic reproducer** written from scratch that triggers the same tool behavior. Use generic names (`tests/test_example.py::test_x`), invented data and the smallest code shape that reproduces the issue. Check that it really reproduces the issue against the public tool, in a scratch project outside both repositories, and record the exact command, tool version and output.

2. **Full `audit.html` / `audit.json` from the private audit attached (high).**
   - Basis: OBSERVED in the draft's contents, as described.
   - Why it matters: these files list private file paths and test names. They usually also hold more, such as the tree digest, the environment, run IDs, limitations that name withheld variables, workflow names, and CI and verification-surface details. All of that is private metadata.
   - What to do: remove both files. If the tool maintainers need engine output, include only the **specific redacted fields** that show the defect, for example a single finding's `code`, a redacted `evidence` shape, or the tool version and the flag used. Even better, regenerate the report against the synthetic reproducer and attach that instead.

3. **The PR goes beyond what feedback needs (medium).**
   - Basis: INFERRED.
   - Why it matters: the tool maintainers need four things: what the tool did, what it should have done, how to reproduce it, and which version it was. None of these requires the private project's identity or structure. Sending more than is needed adds risk and adds no evidence.
   - What to do: keep the PR to a description, the synthetic reproducer, and the proposed fix or test in the tool's own code.

## What a safe version looks like

- Title and body describe the defect in neutral terms: the engine behavior, the expected behavior, the tool version and command, and the observed versus expected output.
- The reproducer is synthetic and minimal, and it lives in the public repository's own test layout.
- Engine output is either regenerated from the synthetic reproducer or quoted as small redacted excerpts.
- Nothing in it names the private repository, its paths, test names, organization, hostnames, CI or people.
- Before opening, check the whole diff, the commit messages and the branch name for leaks. Commit history keeps a removed file, so build the branch fresh, without the private files ever having been committed. Do not commit them and then delete them in a later commit.

## Boundaries

- Publishing anything from the private repository, even in redacted form, is the private owner's decision. Get their explicit approval of the final redacted content before opening the PR.
- Pushing and opening a PR are changes to an external system. They need the user's explicit go-ahead. An audit agent does not do them on its own initiative.
- If private files were already pushed to any public branch or fork, treat them as disclosed. Tell the owner and do not just delete the files quietly.

## What this review rests on

This review rests only on the description of the draft given in the context. I did not inspect the actual diff, so whether it contains further leaks (commit metadata, the branch name, embedded secrets in the copied test) is **UNKNOWN**. Do a full diff review before anything is published.
