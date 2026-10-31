# Independent File-bound manual review audit

Reviewer runtime only. No production edits. Target worktree: studio-file-local-bound-review, base 5eb983fd620ef905aa4dc1afae80b756ee7e7078. Read AGENTS.md and docs/backend/file-bound-memory-owner.md before probes.

`run.sh` prints exact command, commit, and status before every test run; subsequent runs preserve timestamped source tarballs, diff, and before/after SHA256 manifests. `run.py` imports target source and tests using the existing main-worktree venv, disables network socket connections, and uses isolated HOME/XDG/data/tmp. No live PostgreSQL or real model. Pytest XML and raw stdout are preserved individually. Source and test snapshots accompany frozen-source final verdict.

Preflight history (not final-source verdict):
- collection.stdout: harness environment corrected to set XDG_DATA_HOME after initial app startup tried an unavailable default directory.
- preflight.stdout/XML: harness corrected manager.start to original manager.create.
- preflight2.stdout/XML: independently reproduced legacy create NameError caused by broad `_review` substitution in in-progress production patch.
- preflight3.stdout/XML: reproduced same error after conditional-kwargs substitution; implementer acknowledged repair required.

Tests derive fresh bound records from actual original local Mock writer output, not historical-record upgrade or newly opened API admission. Memory uses original MemoryAgentRunner and original File repositories, with local Mock JSON evidence/proposal output. Concurrent deletion tests permit original-owner completion before deletion and only forbid replacement-owner writes. Tests do not claim multi-file atomic rollback or recall of lawful prior response.

## Preliminary confirmed results

`provisional5`: 32 independent probes pass. `compatibility`: 288 pass and three adaptation-authorization failures. `baseline-adaptation`: exactly the same three failures on unchanged canonical base 5eb983fd620ef905aa4dc1afae80b756ee7e7078 (404 rather than expected403; two missing created.id failures). These inherited failures are not silently excluded from evidence.

The review fixture runs original unbound JobManager.create('rewrite') against the genuine local MockProvider, copies that record into a NEW UUID, adds internal ordinary binding to the NEW record, persists it as a synthetic trusted COMPLETED draft, and cold-restores it. The existing legacy record is neither upgraded nor rewritten. This proves review-layer effects using real Mock text, not activated bound writer generation→accept E2E. New bound writer dispatch/admission remains closed.

Existing HTTP /api/generation/{id}/accept and /reject are exercised for already internally bound eligible File-local drafts. Both succeed with original response shape; their unchanged availability is not described as a closed review HTTP API. Bound writer start/_run and cancel remain denied.

Raw implementer extended failures inspected independently: VersionConflict is the original RuntimeError subclass and carries expected1/actual2; authorization refusal is the original normalized _OrdinaryRequestAuthorizationFailed. Independent probes now assert these exact classes and whole-root zero-write behavior. Their changed expected test exception classes are appropriate, not a relaxation of side-effect checks.
