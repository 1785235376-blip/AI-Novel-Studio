# Third-wave integration preparation

PREPARED ONLY. No third-wave gate, Python/product import, test, build, archive inspection or freeze has been executed. These launchers are not evidence of acceptance. Source scope must be reconciled with final independent reviews and exact merged commits before release.

## Baseline and preservation

Full tracked-document baseline is `9325818bbd98ad086db64ca0266aca6e7c4223b8`, the correction that persists six previously untracked wave2 raw inventory-origin receipts. It preserves the canonical inventory from `94307fac4c7ea89ae4737c7e1a6b39b8f20e29ea`; no claim is made that the earlier closure already committed those six files. Parent-supplied canonical V2 SHA256 is `a76dd7d972e932fe8711e1d193068839813bf67c0dc87625af9fb9f97f58f2a9`, with 17,289 rows and 2,671 inventoried sources. These inventory counts are not substituted for the unchanged runner's actual runtime source map.

Freeze protects every old test and document blob, runner/scripts/infrastructure and PUBLIC manifest, and checks the exact changed blobs of all four feature commits. It captures the complete merged tracked-tree hashes plus the original runner source map. Every gate checks these guards again; final audit checks all actual receipts and log hashes against the same source map. The original runner remains untouched.

## Provisional exact scope

`scope.json` records 62 backend nodes/files and 96 frontend files, retaining all 51/85 wave2 entries and adding:

- Director: `test_director_durable_pending_review.py`, `test_director_pending_file_races.py`.
- Caption: `test_caption_timing_offset_additive.py` and five original history/import/voice/transfer backend files; `SubtitleTimelinePanel.offset.test.tsx`, `captionTimingOffset.test.ts`, and five original subtitle history/import/voice/transfer frontend files.
- Interactive: `test_interactive_removal_handoff.py`, `InteractiveStoryPanel.removal.test.tsx`, `interactiveNodeRemoval.test.ts`.
- Comic: `test_comic_panel_duplicate.py`, `ComicLayoutsPanel.duplicate.test.tsx`, `comicDuplication.test.ts`.

Original wave2 backend scope already retains Director publication/restart/generic persistence, Interactive membership/history, Comic framing/layout, restored-file/backup and installed-CPU Audio regressions. It also retains the previously approved additive generation/backup/restore test. Parent subsequently authorized exactly one additive bridge test: `tests/test_wave3_pending_director_canvas_bridge.py`. It is authored but unexecuted and awaits independent static review; no runtime or old test was changed.

Meaningful interactions to review in existing final tests: durable pending review survives fresh File reopen and Job raw-output clearing before original human-review-to-DRAFT; interactive removal remains compatible with original membership and history restoration; comic duplication preserves original cover/framing/export invalidation and historical layout; caption offset preserves import/history restoration provenance and original PUT/source/CAS/export authority. A synthetic all-four-feature test has no demonstrated need. The separately approved bridge specifically composes durable private pending review, edited original Director DRAFT, exact schema4 Graph pin, layout save and full File-owner reopen, asserting no extra Jobs/ledger/GraphRuns. Any further new test requires explicit parent approval.

## Release and serial sequence

1. Parent finalizes all four feature commits/merges, checks independent acceptance, reconciles exact final scope, and commits or otherwise establishes an agreed clean source snapshot. No branch change/merge is performed by these launchers.
2. Parent creates `parent-release.json` from the deliberately disabled template with exact HEAD, four source commits, reviewed changed-runtime paths and explicit authorized/scope-final flags. It must not be created merely to bypass a gate. Obtain the globally serialized heavy-gate slot.
3. With the clean interpreter and clean environment used by run.sh, execute freeze-tree.py only after parent release. No freeze exists at preparation time.
4. Set WAVE3_PARENT_RELEASE=approved only for explicitly released execution. Invoke `bash <this-directory>/run.sh <stage>` serially: origin; comic-golden; backend; ui; type; build; token; packaging; origin-after. Store each launcher output in this directory. Do not overlap other workers' heavy gates. Original runner profiles are uniquely `wave3-integration-<stage>-r1`.
5. Run inspect-artifacts.py after packaging, then audit-results.py after final origin. Independent review/reruns must be separately authorized on the same frozen source. Write the actual report, then complete-index.py after all writers exit. Do not reuse old results or counts as new passes; retain failures and use new numbered profiles on authorized retries.

Natural startup is clean-interpreter `-c` from the repository root, no outer PYTHONPATH, no replacement sys.path or .pth. Actual runner-child `-c` uses only the original runner's own root PYTHONPATH. Probes use explicit PathFinder without product/pytest imports. Normal conftest applies. File tests explicitly exclude only `postgres_backend_only`; no plugin autoload, pytest cache or dependency installation. UI uses original Vite config, one worker and no parallel files. Two genuine font-dependent cases may skip: the original pinned CJK case and the new duplicate authored-copy Unicode case. Preserve each actual skip and reason; never substitute CJK rendering.

## Packaging and storage

The parent has confirmed the existing build-only interpreter exception; no renewed user permission is needed. The unchanged wave2 packaging contract uses the clean approved Python for test/runtime execution and a separate existing hash-pinned installed packaging-build Python only for offline wheel/sdist construction. Fresh path, executable SHA256 and setuptools/wheel origins must verify before each actual packaging stage; the existing release guard records parent execution release, not a new user approval requirement. No package installation is performed.

Retain only bounded logs, receipts, hashes and per-archive payload inventories. Reuse actual run-owned archives for inspection; no worktree duplication or retained archive copies. Initial free space was about 1.8 GiB; latest preparation observed 1.2 GiB. The previous wave retained 172 MiB backend fixtures and 203 MiB packaging fixtures (375 MiB combined), so allow roughly 500 MiB for this wave plus a 300 MiB safety reserve. Recheck space before packaging; lack of safe space is a blocker requiring parent action, not permission for unrelated cleanup.

## Explicit limits

Five known unresolved failures in `tests/test_v2_studio_audio_listing.py` stay excluded, not passed or fixed:
1. `test_malformed_tail_is_never_truncated_or_returned[_studio_body-value0-STUDIO_AUDIO_OPERATION_UNSUPPORTED]`
2. `test_original_per_receipt_limits_still_apply_to_tail[prompt-STUDIO_AUDIO_PROMPT_INVALID]`
3. `test_original_per_receipt_limits_still_apply_to_tail[sources-STUDIO_AUDIO_SOURCE_INVALID]`
4. `test_graph_binding_at_tail_is_still_validated`
5. `test_source_snapshot_binding_is_checked_without_refreshing_history`

No PostgreSQL, browser/visual, Windows-native, live provider, main merge, push, release, dependency installation or paid action. Full product status stays partial regardless of scoped gate outcome. Canonical inventory promotion is a separate parent-controlled activity after merged-source evidence and independent acceptance.
