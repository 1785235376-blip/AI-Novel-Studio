# Core Story record version and recovery closure

Scope: deepen the existing Story → Characters, Locations and Relationships editors. No new workspace, storage authority, flag, migration, provider or visual system.

## Original owner and API

The existing `story_record_versions_v1` flag now gates the five original record kinds: Timeline, Foreshadowing, Characters, Locations and Relationships. The additional editors consume the same `StoryRecordVersionEditor`, `NovelService`, and `story_record_versions` repository mechanism.

For both `/api` and `/api/v1`, the existing project route `/novels/{nid}/experimental/story-records` provides:

- `GET /catalog`: project scope, permitted kinds, write/review capabilities, cancel/recovery contract.
- `GET /{kind}/{rid}`: exact public record, SHA-256 digest, version, bounded history, source lineage, stale state and terminal review feedback.
- `PUT /{kind}/{rid}`: explicit expected digest and version; editable structured fields only.
- `POST /{kind}/{rid}/restore`: explicit confirmation and CAS; restore a retained snapshot as a new current revision.
- `POST /{kind}/{rid}/feedback`: CAS-protected human decision, note and evidence for the exact record/source state.

Characters and Locations keep their existing File JSON files / PostgreSQL character and location models. Relationships keep their existing JSON file / PostgreSQL relationship-state model. Private bounded metadata is embedded in the existing original owner; public V1 rows and outbound context omit it. No second editable record store is introduced.

## Compatibility and concurrency boundaries

- Existing record IDs, including non-ASCII and imported non-slug IDs, remain exact. Older clients address an existing exact ID before applying historical creation slug rules.
- Imported opaque extension fields stay server-owned and survive edits from both the versioned UI and older clients. Versioned clients cannot author arbitrary extension fields or private revision metadata.
- Existing plain V1 / digest-only replace-known-field behavior and backend-specific sparse defaults remain compatible. Versioned SAVE permits partial structured-field changes while preserving unsupplied fields. RESTORE and FEEDBACK use exact public snapshots, including sparse shape and privacy state.
- File mutations use the original project lifecycle lock and atomic file write. PostgreSQL mutations use the original novel row transaction lock and original serialization. Permission, flag, source and CAS checks occur again at the mutation boundary. Denial rolls back without publishing a new version.
- History remains bounded to 20 revisions. Legacy saves after opt-in increment the same version and record their prior snapshot. Reopening the original repository recovers the committed state and history.
- Both digest and version are required, so equal-content revisions and feedback cannot bypass version CAS. Conflict responses contain no current private record/history.
- This is PROJECT shared Story data. Branch domain grants are not promoted to project authority; branch-scoped requests are rejected by the existing authority boundary.

## Source and review behavior

Relationship sources are exact existing project character IDs and optional start/end timeline-event IDs. Missing or foreign references fail closed. An exact known `Character.current_location` ID captures the location digest. Historical free-text locations remain unlinked rather than guessing an identity. Locations themselves can remain unlinked.

Changed sources mark the record and its old feedback stale. Saving requires an explicit source-refresh acknowledgement. Sources are rechecked before commit. Restore retains the selected historical lineage and can honestly return STALE; it never restores or rebinds the referenced entity. Feedback remains terminal for the reviewed record/source version, becomes stale when that version changes, and does not rewrite the old decision.

## Existing editor surfaces

All three existing structured forms now accept a novel ID and pass through the shared version owner when the flag is on. Feature-off and component-only use retain the original editor callback. The local App surfaces supply the novel ID; collaboration's existing scoped owner remains separate.

The shared wrapper provides loading, empty/new-record, read-only, unavailable/denied, error, saving, retained-draft conflict, bounded history, preview/confirm/cancel restore, explicit source refresh and human feedback states. Conflict and restore previews show the actual structured fields for each record type. No raw JSON editing surface is substituted.

Drafts are local-only and owner-keyed by actor, workspace, project, storyline/branch, record kind and record ID; no session token is persisted. Access is rechecked before recovery. Invalid or identity-mismatched stored drafts cannot change the selected record identity. An unconfirmed session actor does not receive persistent local storage. Changing owner, record or project, or losing access, prevents a delayed response from updating the active editor. Cancel discards only unsubmitted editing; an uncertain write is resolved through reading current state rather than blind retry. Pending server commits are not presented as cancellable.

The implementation uses existing DS-v1.0 controls, tokens and Story layout; no protected shell, theme or geometry change is requested.

## Verification

New backend tests use the existing File and real PostgreSQL parametrized fixtures. PostgreSQL requires an actual `TEST_POSTGRES_DATABASE_URL`; missing configuration fails its opt-in fixture rather than substituting a fake database. New mounted tests exercise both API aliases and real project/session authorization.

The added component tests exercise real forms, flag fallback, CAS payloads, local recovery, conflict, restore, feedback, authorization denial, stale requests and owner namespaces. New hosted-browser coverage is included in the existing `surface-freeze-*.spec.ts` discovery pattern.

Local Chromium execution was previously denied and was not retried. Local real PostgreSQL is unavailable. Browser and PostgreSQL runtime results must therefore be reported from the exact-head hosted jobs, not inferred from File/component tests. The historical independent-audit BLOCKED state is unchanged; this implementation work is not a replacement audit.

Final test counts and hosted results are recorded in the delivery verification report. This bounded closure does not by itself declare a formal functional freeze or authorize merge, release or deployment.

### New verification files

- `tests/test_surface_core_story_records.py`: File / real PostgreSQL original-owner revisions, concurrent writers and creators, exact IDs, restart, legacy interleaving, exact sparse restore, opaque imports, bounded history, commit denial, source lineage and race checks, unknown privacy, explicit age clearing and partial-field retention.
- `tests/test_surface_core_story_record_api.py`: both mounted API aliases, mandatory CAS, private conflict payloads, confirmed restore, feature-off and acceptance mode, legacy compatibility, project grants, branch denial, terminal feedback, permission/flag revocation at commit, input size/field checks and missing references.
- `frontend/src/novel/StoryCoreRecordVersionEditor.test.tsx`: additive tests for the existing three forms and shared version wrapper.
- `frontend/src/novel/StoryRecordNavigation.test.tsx`: two additive real-launcher DOM cases for active/inactive creation-group navigation.
- `frontend/tests/e2e/surface-freeze-core-story-records.spec.ts`: three real-mounted browser scenarios using the original File repositories, no mocked business responses; save, second-writer conflict, adopt-baseline, restore/cancel, reload recovery, feedback, source invalidation/refresh and 1366/1440/1920 shell geometry.

No historical tests, assertions or skips are changed by this closure. The already-added `surface-freeze-story-records.spec.ts` receives a reviewed navigation-selector correction after its hosted failure: the active creation group includes the `当前` badge in its accessible name. Both Story browser specs now use the actual scoped accessible-name selector; every CAS, restore, source and geometry assertion remains unchanged. No migration or frozen local-interop protocol object is changed.

### Local implementation verification (2026-10-07)

| Check | Result | Limit |
| --- | --- | --- |
| New backend tests | 53 File/mounted cases covered by passing focused run; 53 corresponding real-PostgreSQL cases authored | PostgreSQL execution NOT_RUN locally; real service required |
| Focused backend plus original Story/digest-CAS/fork/privacy compatibility | 156 passed, 113 PostgreSQL parameters deselected | File and pure unit results only; no new skips |
| Core, original Story editor and actual launcher component tests | 77 passed, including 61 new cases | jsdom/component verification |
| Full frontend integration run | 1,423 passed, 8 pre-existing skips; 213 passed files, 2 pre-existing skipped files | Working-tree integration result, including concurrent adapter additions and navigation regression tests |
| New hosted browser spec TypeScript | Passed | Runtime browser scenarios NOT_RUN locally |
| Design-token lint / diff whitespace check | Passed | Visual/geometry runtime awaits hosted browser |
| Frontend aggregate TypeScript | Passed after the adapter owner corrected its test matcher; final integrated `tsc -b` rerun passed | Working-tree integration, before publication |
| Full File suite | Supplemental: 5,773 passed, 12 existing skips, 2,936 PostgreSQL parameters deselected; one expected source-catalog hash-drift failure | Moving-tree run, not immutable final evidence; unchanged catalog assertion correctly requires regeneration |

The implementation lead owns regenerated API/UI catalogs, final source inventory, exact-head aggregate tests, GitHub commit/push and hosted PostgreSQL/browser receipts. Those final results supersede this implementation-time snapshot. Nothing here changes the historical independent-audit BLOCKED status.
