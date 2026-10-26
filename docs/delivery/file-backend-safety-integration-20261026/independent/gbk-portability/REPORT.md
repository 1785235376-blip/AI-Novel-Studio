# Fixed-B Windows test encoding diagnosis

The three reported failures reproduce on immutable published B
`31b6cb56ba3d2fa08719cf917c2c75ee8f168c8f` without any app/test/script source
change. They are pre-existing Windows test portability defects, not introduced
by the safety integration.

| Source | Cases | Outcome | Process exit | Timeout | Source unchanged |
| --- | --- | --- | --- | --- | --- |
| Fixed B `31b6cb56ba3d2fa08719cf917c2c75ee8f168c8f` | Legacy collaboration source; original export writer processes with distinct/same keys | 3 failed with GBK UnicodeDecodeError | 1 | No, 180 s limit | Yes |
| B plus test-only `ebc35507ff1991fddef7f7ecdcc76aea73733516` | Same three cases | 3 passed, 3 existing warnings | 0 | No, 180 s limit | Yes |

Both runs retained the real machine default `cp936`, `sys.flags.utf8_mode == 0`,
and unset `PYTHONUTF8`. No locale override, UTF-8 mode override, production
encoding change, skip, xfail, or weaker assertion was used. Both ran in separate
detached worktrees. The targeted test files are byte-identical between original
B and the earlier integration freeze F `66e5c97c22ff719aa75f036988073bc24ebf9c57`.

The failures occurred because tests read the original owners' UTF-8 JSON with
`Path.read_text()`'s GBK default. The minimal correction adds explicit UTF-8 to
the collaboration legacy-fixture read and write, and to the process test's read
of `export_jobs.json`. Production files and behavior are unchanged. The process
worker outcome and same-key/distinct-key assertions remain intact.

B has no `scripts/run_studio_backend_tests.py`. The external diagnostic harness
therefore executes the exact isolation-runner bytes from fixed A
`856d1ed3341fe0c24df1daff9a8bc1242c260e6c`, SHA256
`56da22b99915d96a235f9f962f72df72032c0a9606ae6ae17dbb4d59eba88d5b`.
This overlay is saved beside each receipt and never written into the target
source tree. Only its virtual `__file__` identifies the target root so the
existing runner provides its ordinary File/Mock, isolated runtime, cleared
provider/database credentials, and blocked external network behavior.

Each run preserves the command, source HEAD, overlay source and hash, exit code,
timeout, encoding values, full tracked app/tests/scripts SHA256 manifests before
and after, pytest results, and loaded-module paths. There are no app/test module
imports from outside the respective detached target. Baseline pytest duration
was 12.16 s; corrected pytest duration was 12.20 s. These focused diagnostics
are not added to the independent 23-case score, and are not substitutes for the
new common-freeze TaskCenter/export group reruns.

The earlier F independent 23-case report and evidence remain intact. New common
freeze G `d24458225be78f3cbe804b2e325a2f02c3e95568` includes this test-only
correction. The entire independent 23-case group was rerun on a new detached G
copy: 23 passed, exit 0, no timeout, unchanged app/tests/scripts SHA256 manifests,
and all recorded loaded modules from G. That result lives separately under
`../final-G-d2445822/`; neither focused diagnostic score is added to it.
