# Existing backend regression fixture repairs

## Scope and unchanged contracts

Starting commit: `11d8615cccb688462ff814d025b339e1b6eb0efe`, tree `353b8669da72659da2ead4d9b34ac255504c077a`.
This follow-on repairs the six retained failures documented in [TaskCenter query verification](../taskcenter_query_backend.md). It changes only the three original test files and this report. No production backend, frontend, query implementation, permission rule, queue owner, Audio Asset history, dependency or lockfile changes are included.

The original ten-file result was **195 passed / 6 failed**, not a green suite. All six were reproduced unchanged before editing in this checkout: **6 failed** in 10.10 seconds. The originals are retained under `.runtime/baseline-repair-20261025/original-tests/`; the red log and JUnit are `red.log` and `red.xml`.

Git history explains the mismatch. Commit `94befa78` deliberately changed project deletion to the original atomic retirement coordinator, bound agent review to the trusted session actor, and required export routes to re-read and validate persisted owner/scope even after runtime mode changes. The older fixtures were not updated with those changes. The repair does not reverse them or redefine the authorization policy.

## Repairs and regression coverage

### Project deletion

The old `SimpleNamespace(delete=...)` could not supply the repositories required by `AtomicPathMutationPort` and asserted an obsolete direct-delete call. The replacement uses real File repositories, membership and role services, trusted sessions, and the original HTTP application.

The authorized positive case still requires HTTP 204. It additionally proves project removal, retirement of project bindings, storylines, branches and project roles, preservation of earlier audit events, and exactly one new `PROJECT_DELETED` audit attributed to the trusted actor. Missing/invalid sessions, a same-workspace member without a role, a cross-workspace actor, and membership revoked between the first authorization and the commit all reject without retiring the project or changing its audit.

### Agent review

The old assertion trusted the request's `reviewed_by` value. The replacement uses an independently chosen trusted owner, deliberately submits a different actor in the body, and requires the persisted review to name the trusted owner. It retains `ACCEPTED`, `applied=false`, the output hash, and unchanged chapter content. Missing/invalid sessions, another actor in the same workspace, and the same actor in another workspace cannot impersonate the owner or mutate the stored job.

### Export authorization and lifecycle

The three local route doubles now expose the actual stored-record `get` contract, explicit local permission context, and state suitable for download/readiness/cancel/retry. The original HTTP 200 attachment, 409 not-ready, and 200/202 lifecycle expectations are retained. Tests assert the original gate reads the job before the downstream operation.

The collaboration double now contains the complete context produced by the existing export owner: mode, novel, workspace, storyline, branch, actor and permission. Unit tests preserve cross-project concealment and add same-workspace/different-actor rejection, incomplete or mismatched contexts, request-branch mismatch, invalid sessions, current-membership checks and local-runtime access to persisted collaboration records. Rejected requests do not invoke download/cancel/retry. A real `ExportJobService` test checks context persistence, restart, retry inheritance and actor-scoped idempotency with a deterministic failing local exporter.

These route doubles do **not** validate the branch snapshot authority gate: their minimal novel service has no `branch_authority`. Independent review identified this as a coverage gap rather than a production vulnerability. Six additional File/HTTP integration cases close that gap using real `NovelService`, `BranchManuscriptService`, `TrustedSessionResolver`, membership/role repositories and `ExportJobService`, mounted through `app.main`:

- A branch-only reader can download a valid branch-owned snapshot. Its text includes branch content but not the mainline-only sentinel.
- Removing the snapshot, changing its authority, corrupting a chapter document digest, or adding project-owned dataset content makes all four job routes return concealed 404 for that branch-only reader.
- Granting the same owner independent PROJECT rights restores the existing historical-artifact fallback. This is not an unconditional rejection of historical jobs.
- Disabling the branch feature flag or revoking current membership prevents download after successful creation/completion.

No provider or model is called. These tests validate the existing snapshot ownership contract; they do not establish a new cryptographic artifact verification scheme or change production behavior.

## Verification ledger

The runs overlap and must not be summed into unique coverage.

| Run | Result | Evidence |
| --- | --- | --- |
| Original six node IDs before edits | 6 failed | `red.log/xml` |
| First revised three-file run | 98 passed / 6 failed | `focused.log/xml`; new delete assertions initially omitted the fixture's existing `ROLE_ASSIGNED` audit |
| Corrected three-file run before snapshot integration | 104 passed | `focused-final.log/xml` |
| Same original ten-file combination before snapshot integration | 257 passed | `compatibility.log/xml`; original 201 cases plus 56 new cases |
| Real File/HTTP branch snapshot integration | 6 passed | `receipt.log/xml` |
| Final same ten-file combination, including snapshot integration | **263 passed / 0 failed**, 64.44 seconds | `compatibility-final.log/xml`; original 201 cases plus 62 new cases |
| Independent final three-file rerun | **110 passed / 0 failed / 0 skipped**, 39.14 seconds | `.runtime/review-baseline-fixtures/final/suite.log/xml` |

The first revised audit assertion failure is retained, not hidden: it was corrected to compare with the pre-operation audit, require exactly one new deletion event on success, and require an unchanged audit on denial. No audit event or production behavior was removed to make the test pass.

The final JUnit was compared against the red JUnit by exact original node ID: all six pass, without renaming, skips or xfails (`original-six-comparison.json`). All 591 tracked production files under `app/` match their HEAD Git blobs (`source-integrity.json`); `git diff --check` is clean.

Independent review found no remaining blocking P1/P2 after the real snapshot integration was added. Nine process-local mutation categories were killed by assertion failures with no setup errors: trusting the review body actor; skipping export authorization; omitting persisted owner checks; letting local runtime bypass collaboration owner checks; skipping deletion commit reauthorization; leaving stale project scopes; leaving stale project roles; ignoring branch snapshot authority; and skipping the branch feature flag. In the final two categories the actual HTTP response became 200 instead of the required 404, rather than failing only a fixture precondition. These are sensitivity evidence, not extra passing product tests. Mutations never changed production files on disk. Detailed evidence is in `.runtime/review-baseline-fixtures/mutations/` and `mutation-summary.json`.

Local evidence root: `.runtime/baseline-repair-20261025/`. Independent three-file and sensitivity evidence: `.runtime/review-baseline-fixtures/`.

## Additional observation and limits

A separate adjacent check, outside the original ten-file selection, returned **20 passed / 1 failed**. The failure is `tests/test_v060_project_path_persistence.py::test_navigation_keeps_legacy_linked_project_without_novel_metadata_reachable`: its legacy fixture attempts to create a storyline for a nonexistent project, while the existing scope service now raises `ValueError("project does not exist")`. This file and its production owner were not changed in this repair. Its logs are retained as `adjacent.log/xml`; a complete clean HEAD archive reproduced the same node ID and exact failure message in an independent working directory (`adjacent-baseline.log/xml`). It is outside this six-failure repair; subsequent work is tracked separately in [the legacy navigation fixture report](HERMIA_LEGACY_NAVIGATION_FIXTURE_REPAIR_20261025.md), not counted in the results above.

This is not a full backend pass. No PostgreSQL, Windows Host, real provider/model, frontend integration, remote CI, commit or push is claimed by this report.
# Parent integration verification

The parent independent review also ran all four changed test files, including the separate legacy-navigation repair: **116 passed, 3 warnings, 33.51 seconds**. Its remaining receipt-coverage concern was closed by real File/HTTP tests, with an observation-only wrapper recording actual `_authorize_export_record` calls into the original receipt gate (3 true and 20 false outcomes). No production behavior was modified to satisfy tests.

Portable evidence is checked in under [evidence/backend-regression-repair-20261025](evidence/backend-regression-repair-20261025/): the normalized case/outcome manifest retains the SHA256 of each original JUnit file, the final test-source hashes, compact original success logs with checkout paths normalized, and receipt-gate observations. Counts overlap and must not be added into a unique total. These files are evidence from the actual runs, not a new test execution or a claim about PostgreSQL, frontend, real models, or remote CI.
