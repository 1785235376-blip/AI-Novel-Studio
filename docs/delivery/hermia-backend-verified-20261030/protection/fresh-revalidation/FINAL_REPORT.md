# Recovered public protection checkpoint: fresh validation — 2026-10-30

## Result and identity
The recovered production source is exactly **342ad72626667d622040d8eca4d6c9ab8d1e2309**, tree **3b6b7984d3c782b051e8754b94205cc14b6c9bb9**. The uploaded incremental Git bundle verified against publicly available prerequisite **395ac26dd2de3d473e56964dbeb9ac9806facb85**. No production or tracked-test code was changed for this recovery. Git working tree remained clean.

**Fresh bounded File/POSIX verification completed. Full Studio release status is not established.**

- Focused 12-file group: **284 passed**, exit 0, 30.04 seconds.
- Fresh explicitly listed 50-file joint group: **958 passed, 11 skipped**, exit 0, 340.50 seconds. `JOINT_FILES.txt` is the exact newly selected list.
- Independent fresh immutable-archive group: **14 passed**, exit 0, 7.56 seconds. Same new cases on predecessor bd19e6a2: **4 failed / 10 passed**, exit 1. Four cancellation scenarios expose the production delta; the 10 passing predecessor controls are not additional fixed bugs.
- Groups overlap and must not be added into a total coverage count.
- Main-run 5,810 tracked-file hashes are identical before/after. Independent 611 app files are identical before/after and each agrees with Git contents.

## Scope and limits
The joint group covers export ownership/cancellation/integrity and representation behavior, TaskCenter local/collaboration readers/cursors/lifecycle, request scope restoration, and original File owners. Real TCP scenarios with 32 consumers/540 references ran through both /api and /api/v1; local source mutation/reopen and collaboration revocation cases passed. Real service processes are used with deterministic/mock generation, not live paid model calls.

All 11 skipped tests are explicitly Windows-specific: 4 actual native-sharing refusal cases, 1 working-set measurement, 6 TerminateProcess/concurrent-writer observations. See skipped-cases.json. This execution does not establish Windows, PostgreSQL, live model/GPU, browser/NLE, or complete Studio V2 readiness. It does not prove historical asset-409 root causes are fixed. No main edit, GitHub upload, merge, or release occurred.

## What was recovered, and what was not
Original user attachment SHA256: **c258bf690e4336f02fb1c19e1f060e1010b22adb399302bdd2fd0f9543d91755**. It contained exactly source.bundle, changes.patch, and a pending README. Those payloads are preserved byte-for-byte under original-checkpoint/.

The historical later final report (922 passed/1 startup-timeout failure, then an isolated successful retry) and its b39e47fa final-document package were reported in conversation but their raw evidence was not included in this attachment or found locally. They are not fabricated, copied from a new run, or re-labelled as present. This new explicit 50-file selection cannot be represented as recovery of the lost original 50-file list. The previously reported startup-timeout cause remains unproven, even though both collaboration TCP aliases passed in this fresh execution (18.984s/18.651s).

## Contents and reproduction
original-checkpoint/ contains the exact uploaded three payloads. source.bundle requires public commit 395ac26; use git bundle verify after fetching that prerequisite, then fetch its HEAD 342ad726. fresh-revalidation/ contains current logs, JUnit XML, exit codes, explicit file lists, source manifests, independent tests/control evidence, and synthetic HTTP audit receipts. CHECKPOINT.md records the earlier preliminary stage and is superseded by this final report for current status.

The Python interpreter was the pre-existing cloud test venv documented in provenance.json. Synthetic runtime directories were isolated through XDG_DATA_HOME and NOVEL_DATA_PATH. No dependencies were installed for this recovery. Exact test selection and command forms are included in provenance.json, FOCUSED_FILES.txt, JOINT_FILES.txt, and independent/README.md.
