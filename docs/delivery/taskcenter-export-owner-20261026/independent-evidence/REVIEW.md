# Independent export-owner review

Final production freeze: 335fdd6ac6a7f1e350792eb2179d6c372ccb19c5.
Final app tree: 6ee7fd97bf422d99a931d4672d0b07f81f650f60.
Test-only commit: 8285e7e5d64784260f045759d9b73e4a3a4c25df (three files, parent335).

## Result

Final18 PASS, exit0, no timeout and no outside-source app modules. Before/after full app SHA256 manifests are identical. Runtime97.26 seconds, two known Pydantic warnings. Executed in dot cloud workspace, synthetic temporary File roots, no external model/export/background jobs; original _submit was stubbed in fixtures/children.

Covered: two independently running writer processes for distinct creation and idempotency collision; selected-row evidence versus unrelated writes and observed ABA; original read/get/public shape; legacy unbound state; reserved null injection; pre-atomic-write failure; SIGKILL before/after atomic write and next writer recovery; original queued startup recovery/cancellation; corrupt lifecycle fail-closed observation; JSON-distinct bool/int and int/float changes; reserved metadata namespace rejection; missing/legacy/managed observers+get/list create no lockfiles or repair writes; nested mixed numeric/string JSON key compatibility.

The final18 launch six explicit child processes: four for two races and two for before/after SIGKILL. One atomic write exception case is in-process, not a crash. No claim of multi-file/power-loss atomicity, full ABA, backup-replay detection, Windows SIGKILL verification, exclusive executor ownership, or TaskCenter cursor/API support for exports. Startup recovery remains original running-to-queued behavior and may replay work; this review does not certify single execution across workers.

## Retained history, not additive test counts

- baseline-race: two intentional failures on original0eb app: original distinct creates lose an acknowledged job, concurrent same-key creates return different IDs. Original production source was unchanged. Candidate tests were appended to the test module during this baseline run, but only the two unchanged original race cases were collected and executed; module receipt reflects file contents at session finish.
- candidate-8dfe: earlier11 PASS. Its app was kept immutable until terminal.
- candidate-d7d-final: earlier14 PASS, app before/after manifests identical. Despite filename, d7d was superseded by read-only fixes.
- candidate-08fe-final: earlier17 PASS, app before/after manifests identical.
- candidate-08fe-json-probe: one intentional FAIL (TypeError sorting mixed string/int object keys); this led to335 normalizing via original JSON persistence before canonical comparison.
- candidate-335-final: final18 PASS, authoritative for this independent test suite.

The counts overlap and must not be summed. The review also identified metadata namespace selection reaching KeyError, fixed before d7d, and confirmed parent self-review fixes for JSON type-sensitive comparison and no-write reader compatibility. No unresolved production defect found in final scoped owner implementation.

## Evidence

Each run has .log/.xml/-summary.json/-loaded-modules.json. Final source manifests are335-source-before.sha256 and335-source-after.sha256. Earlier d7d/08fe manifests retained. run.py targets the initial independent clone; run-final.py targets the final independent clone. Both use the repository's isolated original verifier plugin, fresh temporary HOME/data/settings, Mock/File mode and240-second bound. The copied independent test sources correspond to the final18 suite; baseline only collected the original race cases as recorded in its summary.
