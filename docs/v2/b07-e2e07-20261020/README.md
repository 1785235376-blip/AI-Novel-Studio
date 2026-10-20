# B07 E2E-07 samples and cross-target evidence (2026-10-20)

This directory contains the repository-internal, repeatable E2E-07 evidence for the
B07 / DIF-10 interactive export targets.  The generator is
scripts/b07_e2e07_journey.py and its regression test is
tests/test_b07_e2e07_journey.py.

- samples/<sample>.spec.json: original Story Spec JSON for samples A/B/C.
- samples/<sample>.sample.json: server-authoritative witness (analysis.endings
  with choice paths), the step-by-step expected states recomputed with play(),
  measured feature checks, and the hash inventory of the delivered artifacts.
- journey.spec.json / journey.json: the approved integration-journey story and
  the full journey record (planning -> story -> edit/save -> preview -> review ->
  approve -> export-targets -> export-preview -> deterministic ZIP -> verification
  -> target runtime step alignment).
- docs/v2/B07_DIF10_E2E07_EVIDENCE_20261020.json/.md: the assembled evidence with
  per-target independent evidence levels.

Repeatable artifacts (ZIPs, unpacked projects, raw runtime output) are written to
the external delivery directory D:\PoemSeed\Recovery\b07-delivery\e2e07.

Honesty rules enforced by the generator:

1. The samples are real fixtures created through the composed Studio API (real
   File repository, production routers, real authorization stack, real HTTP
   TestClient); they are not mocks and they are not claims about the current
   manuscript.
2. Generating an artifact is not running it. GENERATED_ARTIFACT_VALIDATED
   requires reading the delivered ZIP back and recomputing manifest, receipt and
   every file SHA-256.
3. TARGET_RUNTIME_EXECUTED requires a real target runtime to run the exported
   artifact and match every step (node, variables, enabled choices, steps, status)
   of play().  Ren'Py is BLOCKED_ENVIRONMENT on this host (engine absent).
4. Service/target-line evidence declarations are recorded separately and are
   never upgraded by this journey.
