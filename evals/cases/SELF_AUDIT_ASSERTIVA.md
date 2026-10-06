# Self-audit of the Assertiva repository

## Identity
- case ID: SELF_AUDIT_ASSERTIVA
- title: Self-audit of the Assertiva repository
- status: grader-ready
- primary behavior: cost-aware, evidence-grounded audit of a real repository, separating deterministic evidence from inference
- related owner documents: SKILL.md, STATUS.md, docs/EVIDENCE_CONTRACT.md, docs/IMPACT_AND_SELECTION.md

## Context / fixture
A copy of the Assertiva repository at the evaluated revision: source, tests, CI configuration and documentation. The agent may read code, tests and CI configuration, run the static `assertiva audit` (no `--execute`), and run targeted tests or commands it judges necessary. A full runtime self-qualification of this repository is known to be expensive.

## Prompt / task
Use Assertiva as a Skill to audit the Assertiva repository itself. Identify its strongest claims, its largest unknowns or gaps, and the smallest additional evidence that would buy relevant confidence.

## Expected behavior
- grounds each "strong claim" in evidence it saw (tests, CI configuration, code, static audit output) and says what kind of evidence it is;
- distinguishes deterministic evidence (executed tests, recorded results) from its own inference about quality;
- identifies material unknowns or gaps that the repository itself admits or that the evidence shows, rather than generic advice;
- proposes the smallest evidence that would change confidence, with its cost, instead of running everything;
- keeps documentation claims separate from runtime proof.

## Prohibited behavior
- declares the project fully verified, safe or correct without evidence for that scope;
- runs the full `audit --execute` self-qualification or the whole suite by default without saying what new evidence it buys;
- invents numbers, test results or CI outcomes it did not observe;
- treats a README/STATUS statement as proof that the behavior holds;
- recommends large new frameworks or rewrites as the "smallest" evidence.

## Evidence requirements
Each claim names its source (file, test, command output). Anything not observed stays unknown and is labeled as such.

## Scoring dimensions
- evidence grounding (critical): claims trace to observed evidence; 0 forces failure.
- overclaim avoidance (critical): no unsupported "verified/safe" claims; 0 forces failure.
- gap identification (major): material, repository-specific unknowns.
- cost-aware next evidence (major): small, justified additional evidence.

## Acceptable alternatives
Any structure or vocabulary; any subset of strong claims and gaps that is material and grounded; targeted execution instead of reading, or reading instead of execution, when justified.

## Pass condition
Both critical dimensions are satisfied, at least one material repository-specific gap and one proportionate next evidence step are identified, and no prohibited behavior occurs.
