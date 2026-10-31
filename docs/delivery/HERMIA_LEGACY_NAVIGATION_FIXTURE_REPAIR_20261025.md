# Legacy project navigation fixture repair

Base: `11d8615cccb688462ff814d025b339e1b6eb0efe`. This slice changes only
`tests/test_v060_project_path_persistence.py` and this report. No production,
frontend, asset-history, dependency, provider, or database changes are included.

## Classification and preserved contracts

The precise original test failed during setup, before it called navigation:
`create_storyline` for an absent `legacy-project` raised
`ValueError("project does not exist")`. This is a stale fixture, not evidence
that navigation stopped supporting historical data.

- `CollaborationScopeService._project_write` deliberately checks the live Novel
  owner under the project authority lease. Commit `94befa7` added that guard to
  new Storyline/Branch writes; this repair does not remove or bypass it.
- `navigation_paths` still retains existing persisted paths when Novel metadata
  is missing and uses `未命名小说`. This is the compatibility contract recorded
  in `docs/v0.6.0_novel_production_workflow_report.md`, “Runtime findings closed.”
- The original File owner stores workspace links, storylines, and branches in
  `collaboration_scope.json`. The same persisted shape exists in `ddf7997`.
  The fixture now writes that format before constructing any repository.
  Its records are synthetic test data, not a captured user-data backup.

## What the tests now prove

1. The original valid project/storyline/branch creation, display names, and audit
   test is unchanged.
2. Historical navigation is covered separately with no project directory and
   with a legacy project directory missing `novel.json`. Both cases reconstruct
   the real File repository bundle twice, verify the entire original path and
   Chinese display fallback, and preserve the scope file byte-for-byte.
3. An unrelated workspace gets no legacy path; direct cross-workspace Storyline
   listing still rejects the request. Navigation does not synthesize metadata
   or recreate a missing project directory.
4. With the project absent, current `link_project`, `create_storyline`, and
   `create_branch` calls still reject with the exact missing-project error, even
   though the historical link and parent Storyline are readable. Each rejection
   leaves the scope bytes unchanged and the historical path readable through a
   newly constructed File owner.

These are real File persistence tests with same-process owner reconstruction,
not browser, PostgreSQL, external-provider, or process-restart acceptance.

## Verification

All commands sourced `.runtime/activate-backend.sh` and used separate basetemps
under `.runtime/legacy-navigation-repair-20261025`.

| Check | Result | Receipt |
| --- | --- | --- |
| Original exact legacy-navigation node before repair | **1 failed**, 2 warnings, 5.53 s | `before.log` |
| Repaired complete project-path test file | **6 passed**, 2 warnings, 5.60 s | `after.log` |
| Scope, scope API, V0.5.9 admin, V0.6 content API, and repaired path tests together | **35 passed**, 3 warnings, 9.40 s | `adjacent.log` |
| Guard-sensitivity check: remove `_project_write` only in one disposable Python process, run the three rejection cases | **3 expected failures**, all `DID NOT RAISE`; pytest exit 1 | `guard-sensitivity.log` |
| Scoped `git diff --check` | **PASS** | Local command |
| `git diff --quiet HEAD -- app` | **PASS**, exit 0 | No production application diff |

The sensitivity check is not a production regression or an ignored failure:
it proves that weakening the live-owner guard makes all three new counterexamples
fail. No source file was modified for that check.

Reproduction for the passing adjacent selection:

```sh
source .runtime/activate-backend.sh
pytest -q \
  tests/test_collaboration_scope.py \
  tests/test_collaboration_scope_api.py \
  tests/test_v059_collaboration_admin.py \
  tests/test_v060_collaboration_content_api.py \
  tests/test_v060_project_path_persistence.py \
  --basetemp=.runtime/legacy-navigation-repair-20261025/tmp-adjacent
```

The warnings concern the existing Starlette TestClient deprecation and two
Pydantic `schema` field-name warnings. This slice did not run the full backend
suite, access the network, commit, or push. Concurrent repairs in the other
three test files were left untouched.
