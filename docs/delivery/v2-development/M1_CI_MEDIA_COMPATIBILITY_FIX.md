# M1 media prerequisite and protected-job compatibility correction

Evidence cutoff: 2026-10-09 13:42 UTC. This is an engineering correction in
progress, not a new hosted PASS or a completed M1 browser acceptance.

## Preserved first failure

M1 commit `57986cb13d452731baf82bbc242bfc79f9cfd145`, tree
`7b06f7eb213893ec41e4ded14810b82b070b7dc7`, added seven explicit FFmpeg
installation/version-recording lines to the V2 live-browser job. The existing
TCP self-test correctly rejected the changed job digest. The local 174-check
selection omitted the separate 102-check TCP harness; its PASS did not cover
this compatibility invariant.

- Push run `37936615942`, attempt 1, job `113840148811`: **101 passed / 1 failed**.
- PR run `37936623135`, attempt 1, job `113840173916`: **101 passed / 1 failed**.
  Actual PR merge checkout `2815d03ac31b3e132453f6b9ad63eff777269468` has the
  same tree as the M1 head.
- The failing assertion is
  `test_unrelated_jobs_preserved_exactly[v2-creative-browser-35d5bcb…]`.
  Expected job SHA256 `35d5bcb0b01d5cfdee60fed714c6c2d912141b887c8494bb648d4848f7f46277`;
  actual `ccffceb56f117783a4616dee99e7d4c8fe89db763af1a08b7b1dc1007c83613c`.
- The actual TCP product command did not execute after that failed prerequisite.
  Its missing evidence must keep both strict backend aggregates nonpassing.
- Full original logs are retained as `m1-ci-tcp-*-first-failure.log`.

The guard originated with the separately bounded TCP orchestration change. It
protects the complete unrelated frontend, V2 browser and Windows jobs: setup,
order, conditions, budgets, commands and evidence behavior. Maintaining its hash
while hiding equivalent installation in another startup path would not preserve
that contract. The old assertion, digest and all 102 tests remain unchanged.

## Approved bounded correction

The engineering review first approved restoring the original job and probing
only existing tools inside the new VIDEO fixture. Actual M1 job logs then showed
`Setting up ffmpeg (7:6.1.1-3ubuntu5)` on both browser runners; this is evidence
that the M1 command installed a package, not proof that the unchanged runner
image already has the tools. Other jobs and local tools cannot establish this
runner's prerequisites.

The subsequent approved scope is an explicit **additive independent-media job**:

1. Restore the protected V2 job's exact bytes and the original live config's
   exact M0 bytes. Original seven live cases and eight separate geometry cases
   stay with that job, with unchanged budgets and assertions.
2. Move all five new M1 cases from the two new spec files into
   `playwright.independent-live.config.ts`, executed by a visibly separate
   `v2-independent-media` job. Its Ubuntu package installation, `ffmpeg` and
   `ffprobe` version output, and `dpkg-query` package receipt are explicit steps.
   It retains a 25-minute outer budget, zero test retries and fail-closed upload.
3. Keep the new VIDEO fixture's bounded existing-tool probe. It uses no shell,
   install, download, fallback or setting changes; each `-version` invocation
   has a five-second limit and 64 KiB output cap. Both actual version outputs
   or a failure receipt are attached to the same journey before encoding.
4. Require both old and new jobs independently. A media-job success cannot
   replace an old-job failure. No failed run is rerun, relabeled or combined.

`m1-media-inventory-migration.json` and the three `m1-media-inventory-*.txt`
files record actual Playwright **collection only**, with no browser launch:
12 prior cases = 7 original + 5 independent media; exact union, no overlap and
no removed case. Original config SHA256 is
`dbbf62ee540feed65c69e7cd1a16d732220c240b0b016b868de24e91bfc14a36`.
Future additive M2 cases must be counted separately rather than changing this
historical M1 migration receipt.

Only the new M1 prerequisite-location assertions are adapted to the actual
fixture/helper/config boundary. Real-media decode, positive browser metadata,
original-byte export, scope/permission, timeout and no-skip requirements remain.

## Local diagnostics retained

- First ad-hoc mixed pytest invocation lacked the owned runtime profile:
  102 harness cases passed; 14 application-fixture setup errors hit the
  read-only default home. No permission expansion was requested. The log is
  `stage-m1-ci-prerequisite-missing-profile-first.log`.
- The owned-profile invocation then found a real receipt-classification bug:
  114 passed / 2 failed. Node's output-overflow error did not always set
  `killed`; the helper now explicitly recognizes
  `ERR_CHILD_PROCESS_STDIO_MAXBUFFER`. The same new failure tests are unchanged.
- Corrected owned check: **116 passed**, including all unchanged 102 TCP cases
  and actual child-process success/missing/nonzero/invalid/timeout/output-limit
  cases. Its receipt records no source drift. The actual-installed-tool case
  proves only this cloud workspace's tools, not hosted runners or media quality.
- The additive-job and complete-source checks are subsequent evidence; no
  hosted result is asserted here before publication and actual execution.

## Separate unresolved browser failure

Both M1 browser jobs reported eight live failures and four live passes; the
eight mocked/geometry checks separately passed. The first new relationship
journey timed out at 180 seconds. Its in-body `finally` attempted cleanup with
an already closed request context, leaving its confirmed synthetic project;
seven subsequent cases then correctly failed the original empty-server guard.
Cleanup failure and the first functional timeout are distinct defects. Moving
the job cannot establish that either is fixed.

The new push artifact `11618169199` was resolved by GitHub, but its first
materialization failed with HTTP 403 `scope_violation`: “The requested file is
outside the Library folders selected for this user turn.” No alternate route
was attempted. Full logs and source are available; trace/screenshots remain
**TRACE_ACCESS_BLOCKED** and have not been inspected. This is separate from
the earlier blocked M0 artifact, which remains untouched.
