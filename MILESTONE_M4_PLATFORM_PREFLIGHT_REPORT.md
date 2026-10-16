# M4 incremental closeout: owned acceptance platform preflight

2026-10-11 UTC. Parent: `5af9bfc40abc305154a1a35e50f5e8e47c1c1322`,
existing Draft [PR 47](https://github.com/1785235376-blip/AI-Novel-Studio/pull/47),
branch `feature/v2-narrative-platform`.

**Bounded harness fix verified; M4 remains PARTIAL. Windows operational
acceptance remains BLOCKED / NOT_RUN. No new real model or GPU result.**

## Existing owner and precise behavior

`scripts/run_v2_real_text_check.py` already owns an isolated POSIX process group,
an exact child runtime and evidence directory. Its cleanup uses `os.killpg`; it
cannot safely be represented as a Windows acceptance harness.

The same owner now checks OS/platform and callable `setsid`, `killpg` and
signal-handler APIs plus required signal constants. Native Windows, Cygwin/MSYS
and missing process APIs fail with `BLOCKED_UNSUPPORTED_OWNED_PROCESS_PLATFORM`.
The CLI reports exit 2 after lexical argument parsing, before model hashing,
port probing, workspace creation, source inspection or child/runtime launch.
Both CLI branches, direct execution and direct input validation are guarded.
Blocked invocation creates no receipt or evidence directory. API availability
is a narrow prerequisite, not proof of permissive OS policy on every POSIX host.

The allowlisted child environment now binds `TEMP` and `TMP` to the same owned
directory as `TMPDIR`, and verifies all three paths. Inherited private temp
locations remain unchanged. Existing CPU argv, 180-second node deadline,
360-second harness deadline and process cleanup semantics are unchanged.

No project, model, runtime, session, credential, job or asset owner was added.
No Model Center authority change or Windows containment fallback was invented.
Product APIs and catalog operations are unchanged.

## Exact-source execution

A fresh official Git checkout at the parent reproduced the published 1,782-input
source map, SHA256
`9971f879d1a2ae898f329d65f732d88f98787140eab86b4bf41895ec16899259`.
All integrated checks below use the unchanged original `run_v2_checks.py`,
original applicable pytest setup and an isolated File profile, with no new skip
or deselection. Source maps stayed stable during every run.

- Baseline original harness: **140 passed**, zero failures/errors/skips.
- Patched complete harness: **165 passed**, zero failures/errors/skips.
- Patched harness plus original verification-runner tests: **170 passed**, zero
  failures/errors/skips. This overlaps the preceding harness count.
- Complete existing infrastructure: **352 passed**, zero failures/errors/skips.
- `git diff --check` and targeted Python compilation pass. No separate Python
  formatter/linter is configured in the inspected project/workflows.

Final 1,782-input source-map SHA256:
`23564336236efd8d55ac055cb5f5d30f3581e797472918c9c6971f7006fda410`.
The two changed executable/test input hashes are in the receipts; the original
harness test file remains an exact byte-for-byte prefix of the new file.

Original commands, source maps and log hashes are preserved losslessly in
`docs/delivery/v2-development/m4-preflight-{baseline,integrated,adjacent,infrastructure}.json.gz`,
with readable `.log` and JUnit `.xml` siblings. Compression is storage only;
full original JSON files remain in the working evidence archive.

An ordinary read-only code review found no blocking issue and independently
verified ordering, no side effects on blocked paths, unchanged deadlines,
original-test preservation, receipt log hashes and current-source identity.
This is not the historically blocked independent security audit.

## Two unfiltered collection inventories

The unchanged `extend_v2_coverage_manifest.py` first reviewed a complete
collection and then explicitly wrote the separate V2 manifest after a second
independent collection. Both contain the same **12,131 ordered nodes**, no
collection errors, compared with 12,106 at the parent. The 25 added cases include
four new TEMP/TMP expansions in an unchanged original parametrized test.
Collection is inventory only, not execution or complete coverage.

Only `coverage_manifest_v2.json.gz` is regenerated. The frozen V1 manifest stays
byte-identical at SHA256
`6457dd4cae85adee42486ef503fdb1cdabcdaf6eb9667eff3e2e97d05d040262`.
Every preceding V2 node remains in relative order, historical skip maps and
external gates are unchanged, and the existing exact historical migration proof
is retained. The V2 manifest SHA256 is
`82c21d47984500c3da8d7c6c657a4bb8c7387a5d842171c81c73829ce586ffa6`.
Two compressed original inventories and
`m4-preflight-inventory-proof.json` preserve the comparison.

## Failed and narrower development checks remain visible

Before implementation, 15 newly added contracts failed against the original
runner. Their RED log/JUnit/exit remain under `m4-preflight-development/`.
Early connector-snapshot checks passed 158/1 deselected and 164/1 deselected with
`--noconftest`; those were focused orchestration checks, not integrated product
tests. The subsequent full 165/170 harness runs above use original applicable
setup and no deselection, closing that setup gap without deleting earlier logs.
Initial source materialization added one terminal newline; initial bytes remain
preserved, and corrected baseline bytes were accepted only after matching exact
remote Git blob hashes. Official Git recovery separately reproduced the full
published baseline map. Dependency and reconstruction evidence is retained.

## Remaining gates and publication

This is one incremental M4 safety fix, not M4 completion, Windows support,
valid real adaptation, prose quality, full File/PG/backend/frontend execution,
or a release. No native model, download, paid API, credential, user computer or
GPU was used. The Windows process-tree lifecycle must be a separately verified
scope; broad process-name termination is not an acceptable substitute.

Parent-SHA hosted CI remains terminal and incomplete: Cloud push
[38095580679](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/38095580679)
and PR [38095584365](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/38095584365)
are cancelled. File's 20-minute and PostgreSQL's 55-minute boundaries, strict
coverage gates and historical settling failures remain unchanged/unresolved.
New publication requires its own naturally triggered hosted results.

The preceding PR body is archived byte-for-byte at
`docs/delivery/pr-history/PR47_BEFORE_M4_PLATFORM_PREFLIGHT_20261011.md`.
The existing Draft PR stays Draft; no main merge, release or V1 change follows.
