# CI reconciliation: staged verification proposal

Status: PROPOSAL ONLY. No tests, collection, generator write, or manifest promotion has been executed by this plan.

Base: `72e636f87c7299a62cb3357bcb6a6e44a9388883`. Worktree: `/workspace/scratch/20a0022d2b33/studio-ci-reconciliation`.

## Release boundaries

The runtime owners must finish and the reviewer must freeze exact source paths first. Every stage below needs the parent release appropriate to its scope. A still-blocked lifecycle/security module or candidate blocks full unfiltered collection; no exclusion may be used to manufacture completeness.

## 0. Freeze and permission boundary

- Wait for every runtime writer and independent reviewer to freeze; checkpoint the reviewed sources. Record actual commit, tree, clean/dirty status, dependency symlink target and existing tool versions. No install.
- Retain every failed run and its real exit code. A successful rerun is additional evidence, never a replacement.
- Resolve authorization for full unfiltered pytest collection explicitly. The unchanged collector imports every test module and offers no safe subset mode for an authoritative full manifest. Any still-blocked lifecycle/security task or candidate blocks this stage; do not ignore, skip, rename, or exclude it.

## 1. Read-only preservation and provenance preflight

- Verify both baseline manifest bytes and all guard/generator boundaries against the audit JSON; verify all 1123 old V2 protected source entries, not just the 43 restored files. Verify sole Windows-B approved after-hash.
- Recompute stale/new source sets from the stable checkpoint using exactly the existing traversal plus frozen V1 source-map paths; do not reuse 72e counts as final totals.
- Produce a separate additive source-provenance companion for frontend/scripts/** and frontend/e2e/**. Do not patch existing guards, generator, runner, or canonical manifest to add their coverage.
- Recompute static missing-suite list; retain exact test function/decorator extraction ledgers and minimal shared helpers. Do not equate AST declarations with parametrized collected nodes.

## 2. Narrow execution and infrastructure checks after release

- Complete the approved exact restored/additive compatibility scopes using existing tools and unique retained receipts; stop acceptance on real failures. Include explicit new-version MP3 and original legacy submission/readback/reconciliation security boundaries.
- Run the three unchanged synthetic CI helper suites with the existing isolated runner. Historical 166 is context, not an expected count to force.
- Run frontend discovery only when explicitly released: it lists Vitest files and imports/list-collects two Playwright configs; it does not execute browser acceptance. Follow with separately approved build/lint commands.
- Bracket every command with the additive source-provenance companion described below; require identical before/after maps and preserve tool/dependency identity.

## 3. Review collection with canonical V2 unchanged

- After explicit broad-collection release and writer freeze, run existing generator WITHOUT --write, using unique report/runner labels.
- Immediately archive raw collection.json bytes, inventory report, runner receipt and log. Hash each; record exit codes, errors, source maps before/after, commit/tree, dependencies and additive companion maps.
- Run the independent 15142-row comparator and final missing-suite reconciliation before any next collection. A rejected collection or any failed comparator is retained and blocks progression.

## 4. Quarantined candidate generation

- Only after approval, run unchanged generator with --write and --output under .runtime; canonical V2 remains untouched. This is a fresh full collection, not serialization of the previous rows.
- Immediately archive its fixed-path raw collection.json before any later invocation. Record the candidate gzip digest.
- Require candidate rows EXACTLY equal review rows, including all additional row IDs, order and classifications, and require identical source/provenance snapshots. Independently rerun old-row, old protected-byte, manifest metadata and missing-suite checks.

## 5. Promotion of reviewed exact bytes

- After independent signoff and explicit promotion approval, reverify canonical old digest, candidate digest, no source changes and unchanged frozen/gates.
- Promote exactly the already-generated candidate gzip bytes to canonical coverage_manifest_v2.json.gz. No recompression, manual fields, ID edits, classification edits, or new exceptions.
- Verify canonical digest equals candidate digest, V1 and guard hashes unchanged, and only intended V2 manifest/evidence changed. Keep previous canonical bytes through Git and archived digest.

## 6. Independent confirmation

- Run a separately released, uniquely labeled fresh review-only collection; archive raw rows immediately. Require full rows equal approved candidate rows, sources equal canonical source_files, classification digest equal canonical v2_extension digest, and exact old-row preservation.
- Require additive companion maps unchanged from approved source checkpoint. Re-run only approved narrow CI helper checks and exact source-hash validation.
- Record source checkpoint HEAD separately from later evidence/manifest commit HEAD; never rewrite generator-produced collection_head to disguise the distinction.
- Report inventory validation separately from real execution. Full File/PostgreSQL/TCP/browser/windows acceptance, services, hosted CI and publication require their own authorization and actual receipts. Do not infer coverage from collection.

## Exact existing command templates

`PY` must be resolved to the already-approved existing pinned environment; never install or assume the current shell interpreter is the right one. Labels are unique per actual attempt. Do not overwrite r1 receipts on retry.

### variables

```sh
ROOT=/workspace/scratch/20a0022d2b33/studio-ci-reconciliation; PY=<verified existing pinned Python executable>; cd "$ROOT"
```

### narrow_harness

```sh
"$PY" scripts/run_v2_checks.py ci-reconciliation-harness-r1 -- python -m pytest -q -p no:cacheprovider .github/ci/test_suite_coverage.py .github/ci/test_coverage_reconcile.py .github/ci/test_v2_manifest_extension.py --basetemp=.runtime/v2-checks/ci-reconciliation-harness-r1/pytest
```

### frontend_discovery

```sh
pnpm --dir frontend test:discovery
```

### frontend_build

```sh
pnpm --dir frontend build
```

### frontend_lint

```sh
pnpm --dir frontend lint
```

### review

```sh
"$PY" scripts/run_v2_checks.py ci-reconciliation-review-r1 -- python scripts/extend_v2_coverage_manifest.py --report docs/delivery/v2-development/ci-reconciliation-review-r1-inventory.json
```

### candidate

```sh
"$PY" scripts/run_v2_checks.py ci-reconciliation-candidate-r1 -- python scripts/extend_v2_coverage_manifest.py --write --output .runtime/v2-checks/ci-reconciliation-candidate-r1/coverage_manifest_v2.json.gz --report docs/delivery/v2-development/ci-reconciliation-candidate-r1-inventory.json
```

### confirmation

```sh
"$PY" scripts/run_v2_checks.py ci-reconciliation-confirm-r1 -- python scripts/extend_v2_coverage_manifest.py --report docs/delivery/v2-development/ci-reconciliation-confirm-r1-inventory.json
```

## Independent old-row/candidate validation

- Load baseline V2 and historical row evidence using git show at exact72e ref, not mutable working-tree copies. Verify both artifact SHA256 hashes from the audit report before decoding.
- Old row object must have exit_code==0 and errors==[]; rows have exactly15142 unique node IDs; node IDs equal old V2 product_nodes in exact order; classification counts are file4865, postgres4819, both5458; canonical row digest matches e7e543708b0ac8ebd1f81f77262a4afa6503d222af2b2e0ad9e71d6a749754d6.
- New raw object must have exit_code==0 and errors==[] and no missing/duplicate IDs or invalid backend values. All row dictionaries must have the expected nodeid/backend shape.
- Let old_ids be the old row IDs. Require [row for row in fresh_rows if row["nodeid"] in old_ids] == old_rows. This single exact equality preserves every old literal ID, order and classification, including tests/test_v2_audio_flac.py::test_format_is_closed_in_original_command_and_audio_body[MP3].
- For candidate and confirmation, additionally require fresh_rows == archived_review_rows in full. Counts alone, set equality alone, V1-only preservation, or digest comparison without authenticating the reference are insufficient.
- Candidate product_nodes must equal fresh row node IDs; candidate v2_extension.collection_classifications_sha256 must equal SHA256(json.dumps(fresh_rows,separators=(",", ":")).encode()) with Python default ensure_ascii=True.
- Preserve exact old skips and external_gates; old added_nodes must remain as an ordered subset. Preserve all old source paths; allow only reviewed runtime fingerprints plus genuinely new additive source entries. All1123 old protected source hashes remain exact.
- Every collected test-file path must exist in candidate source_files and have the actual stabilized bytes. Reconcile every static missing suite with actual new collected rows; helpers/fixtures get source hashes but no invented test rows. Retain unexpected extras as a failure for review, not a reason to alter expected IDs.
- Compare current source bytes and complete existing-traversal path map against candidate source_files; before/after snapshots must match. Run separate companion directory closure/hash checks for omitted frontend directories.

The immutable old raw archive is `docs/delivery/v2-creative-save-state-20261017/collection-confirmation-rows.json.gz` at72e; gzip SHA256 `8a63aa4ad872695d1699816910647dec8070f2566f9a8aea3eb3943ffa9bbd34`.

## Raw receipt preservation

The generator always reuses `.runtime/v2-checks/v2-manifest-collection/collection.json` and its `pytest` basetemp. A unique `--report` does not isolate those files. Before the next invocation, archive raw bytes and all failure/success metadata under a unique stage label and hash them. Preserve the review, candidate and confirmation row files independently. Do not run collectors concurrently.

## Additive provenance for omitted frontend directories

- Additive source provenance only; no claim that unchanged source_errors or source_snapshot covers the omitted directories.
- Recursively enumerate every regular file under both directories, including tracked and genuine untracked source files, using repository-relative POSIX paths and sorted ordering. Record symlinks explicitly; never silently follow an out-of-tree target or claim completeness while omitting it. Verify complete path sets, not only hashes of known files, so additions/deletions are detected.
- Separate additive evidence JSON beside the corresponding delivery receipt after release, with a copy/hash in external audit evidence if desired. It is not inserted manually into canonical V2 source_files. Existing source_snapshot covers frontend root configs/package/lock/runner manifest, frontend/src and frontend/tests; bind those through its normal receipt too.
- This companion can prove provenance of local commands but does not add hosted automatic enforcement. At72e cloud-ci does not call test:discovery, and existing inventory traversal omits these directories. Any later enforcement change must be separately proposed without weakening old guards; keep this residual limitation explicit.

Companion fields: schema, stage_label, source_checkpoint_head, source_checkpoint_tree, worktree_status, command_and_cwd, started_utc, finished_utc, dependency_symlink_target_and_tool_identity, existing_runner_receipt_path_and_sha256, before_complete_path_to_sha256_map, after_complete_path_to_sha256_map, per_file_git_blob_at_checkpoint_or_untracked_status, path_set_unchanged, bytes_unchanged, all_observed_failures.

The known72e omitted files are:

- `frontend/e2e/README.md`
- `frontend/e2e/prompt-acceptance-s0.spec.ts`
- `frontend/e2e/prompt-workspace-acceptance.spec.ts`
- `frontend/e2e/promptAcceptanceEntry.ts`
- `frontend/e2e/studio-release-acceptance.spec.ts`
- `frontend/scripts/benchmark-canvas-notes.mjs`
- `frontend/scripts/benchmark-graph-display.mjs`
- `frontend/scripts/check-test-discovery.mjs`
- `frontend/scripts/local_interop_browser_host.py`
- `frontend/scripts/measure_interop_bundle.mjs`
- `frontend/scripts/run-experimental-http.mjs`

## Missing-suite treatment

22 missing backend suite files at72e; six extracted additive suites are now additional known files. These are baseline/minimum path facts, not final collection counts. Recompute after runtime freeze, including new MP3 compatibility suites and legacy fixture. 35 new frontend additive files need default Vitest discovery, not a manually enumerated unit registration entry.

The22 baseline files (full functions and hashes are retained in the JSON/audit):

- `tests/test_declarative_checkpoint_edit.py`
- `tests/test_declarative_definition_history.py`
- `tests/test_public_archive_limits.py`
- `tests/test_public_build_profile.py`
- `tests/test_public_sdist_artifact.py`
- `tests/test_public_wheel_artifact.py`
- `tests/test_research_evidence_location.py`
- `tests/test_style_comparison_review.py`
- `tests/test_template_copy_editing_workflow.py`
- `tests/test_v2_audio_mp3.py`
- `tests/test_v2_audio_mp3_api.py`
- `tests/test_v2_canvas_large_notes.py`
- `tests/test_v2_caption_transfer_preflight.py`
- `tests/test_v2_director_handoff_reopen.py`
- `tests/test_v2_director_model_planning.py`
- `tests/test_v2_director_proposal_reopen.py`
- `tests/test_v2_graph_capacity_continuation.py`
- `tests/test_v2_graph_director_proposal_loop.py`
- `tests/test_v2_graph_presentation_contract.py`
- `tests/test_v2_nle_review.py`
- `tests/test_v2_timeline_asset_handoff.py`
- `tests/test_v2_timeline_short_media_handoff.py`

The six extracted backend suites:

- `tests/test_r4_story_simulator_additive.py`
- `tests/test_r5_comic_layouts_additive.py`
- `tests/test_r5_interactive_story_additive.py`
- `tests/test_round2_bible_additive.py`
- `tests/test_v2_creative_graph_persistence_additive.py`
- `tests/test_v2_director_workspace_additive.py`

The five new support files are source inventory, not additional test suites:

- `tests/support_reconciliation_test_r3_planning.py`
- `tests/support_reconciliation_test_r3_media_support.py`
- `tests/support_reconciliation_test_r4_director.py`
- `tests/support_reconciliation_test_r4_revision_intelligence.py`
- `tests/support_reconciliation_test_v2_independent_workspace.py`

## Scope and verified static status

At22:36:43UTC the read-only check of all1123 protected old V2 source entries found no mismatches. This includes all43 restored files; it is broader than merely rechecking the changed paths. Runtime work was still active, so repeat after freeze.

The unchanged generator enforces9151 frozenV1 node rows, not all15142 oldV2 rows. Its candidate-output option is therefore essential: validate independently before promoting exact bytes. Source inventory, discovery and passing unit tests do not establish real PostgreSQL/TCP/browser/Windows acceptance or hostedCI success.
