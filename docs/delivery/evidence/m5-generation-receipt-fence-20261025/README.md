# M5 receipt final-boundary evidence

Base e7f2eaec2a5010a98cad6aa1d48df8e0ffc3b459. Only production change:
app/repositories/generation_repository.py. No M6/v2/API admission code.

- red.stdout/XML: four intentional regression failures on unchanged base,
  retained global receipt corruption despite unchanged replacement project bytes.
- red-generation_repository.py and red-source.sha256: exact reproduced source.
- targeted.stdout/XML: 95 passed on initial repair, before root-lock pinning and
  fifth regression test. Not the final source proof.
- frozen-source.sha256, source-verified.txt, final-frozen-regression.stdout/XML:
  480 passed, one real PostgreSQL concurrency test skipped, three existing
  warnings. Isolated actual worktree imports, network disabled before app import.
- specialized.stdout/XML: 9 passed, 1 failure. specialized-baseline.stdout/XML
  reproduces the identical NOT_CONFIGURED versus AWAITING_REVIEW failure on
  pristine detached e7f2eae, with the same isolated no-credentials setup. No new
  regression or broad-suite-green claim; no provider was contacted.
- independent/: original red, final review and exact source hashes (full source archives retained in the runtime evidence directory).
  Independent final 341 passed, including 8 seam/lock probes.

Existing helper fixtures deliberately distinguish synthetic trusted persisted
ordinary v1 drafts from original Mock memory inference. New bound generation
admission/dispatch remains closed. Raw pytest whitespace is preserved verbatim.
