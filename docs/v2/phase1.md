# Phase 1 — Creative Layer foundation

Recorded: 2026-10-08T05:04:00+00:00 / 2026-10-08T13:04:00+08:00.

Status: **DONE for the File/PostgreSQL typed foundation.** This stage implements document data and persistence. Model generation, reviewed agent application, planning derivation algorithms, and frontend validation belong to their subsequent owners.

The implementation is in the isolated `D:\小说\AI-Novel-Studio-V2` repository, on `feature/v2-narrative-platform`, imported baseline `1b7ff50a7e64742916bc64730df884cea819b379`. The original frozen `AI-Novel-Studio-Latest-Product` workspace is used only as the Python dependency interpreter location. No implementation or test file there was edited by this stage. No commit or push was made by this agent.

## Implementation and reuse

| File | Responsibility |
| --- | --- |
| [models.py](../../app/creative/models.py) | Strict, bounded SCREENPLAY / STORYBOARD / VIDEO_PLANNING documents; Scene, Dialogue, DirectorNote, ShotCard, VideoPlan / VideoSegment. Unknown fields, invalid links, duplicate scene/shot IDs or sequence numbers, non-integer versions/durations, and invalid mode fields are rejected. |
| [service.py](../../app/creative/service.py) | Independent `creative_documents_v2` collection; source-fenced CRUD, soft archive, CAS history, JSON export, server-owned document ancestry, transactional authority rechecks and capacity limits. |
| [api.py](../../app/creative/api.py) | Private, explicitly opted-in routes using the existing project/session/branch authority and error projections. |
| [experimental/api.py](../../app/experimental/api.py) | Composition reuses the current ExperimentalStore, NovelService, ChapterService and authorization resolver. |
| [experimental/flags.py](../../app/experimental/flags.py) | Adds only `narrative_production_v2` to the independent surface/runtime inventory; default OFF, wildcard disabled, V1 acceptance mode disabled. |
| [test_v2_creative_foundation.py](../../tests/test_v2_creative_foundation.py) | Real persistence, process restart, independent concurrent writers, source/ancestry/privacy fencing, transaction rollback, strict API input, private conflicts, and composed real identity/membership/branch permissions. |

The inherited comments describe a “forty-package” list, but the actual imported `FLAGS` contains **44** entries (9 legacy + 35 new). This stage preserves its exact order and values: canonical JSON tuple SHA256 `555b14e42e22ec4bc097034dd1ded933d20c89dcf6d132a209ec2561118fb9cc`. The new test binds that complete original tuple. The published `features` map remains the same 44-entry contract; only `surface_features` / `runtime_features` discover the additive opt-in.

Storage reuses `ExperimentalStore`'s scope transaction and the existing File workspace lock / PostgreSQL row lock. PostgreSQL uses the existing `experimental_scope_documents` table and migration 019; this foundation introduces no migration. Original ScreenplayService, its approval/shot workflows, DirectorService, Agent/Memory services, and NOVEL core remain their existing owners.

## API contract

Both existing aliases mount the same routes: `/api/novels/{nid}/experimental/creative` and `/api/v1/novels/{nid}/experimental/creative`.

| Method / suffix | Input / result |
| --- | --- |
| GET `/capabilities` | Authorized project read; `{enabled, modes: string[], can_mutate}`. OFF remains discoverable without granting mutation. |
| GET `/documents` | Fresh, non-archived authorized records in `{items}`; stale source records are omitted. |
| POST `/documents` | Strict `CreativeDocumentIn`; DRAFT document, HTTP 201. |
| GET `/documents/{id}` | Current scope/source-fenced document. |
| PUT `/documents/{id}` | Flat full `CreativeDocumentIn` plus strict positive `expected_version`; mode immutable, server ancestry preserved. |
| DELETE `/documents/{id}?expected_version=N` | CAS soft archive; `{id, version, status}`. |
| GET `/documents/{id}/history` | Current version plus bounded preimages, each checked against current source/privacy authority. No restore endpoint is claimed. |
| GET `/documents/{id}/export` | Structured JSON attachment with canonical document digest; no media rendering or model execution. |

Normal headers are `X-Session-Token` and `X-Branch-Id`. Collaboration requires the existing trusted session, workspace membership, branch scope and domain read/write permissions. Server evidence, actor/scope, status, version, history and `source_documents` are forbidden client input. A source-free document requires an explicit `source_independent=true`; chapter-bound or derived documents cannot set that opt-out.

`CreativeService` provides `get(nid, scope, rid)`, `list(nid, scope)`, `create(nid, scope, actor, value, *, reauthorize=..., source_documents=None)`, `update(nid, scope, actor, rid, expected_version, value, *, reauthorize=...)`, `archive(...)`, `history(...)`, and `export(...)`.

Trusted subsequent planners call `create_derived(nid, scope, actor, value, *, source_documents={id: {version, digest}}, reauthorize=...)`. The source document is checked inside the same scope transaction that inserts the child. Public `prepare_content`, `assert_current`, `assert_capacity`, `COLLECTION` and `document_digest` support an agent's single transaction spanning its job and target record. They do not permit an HTTP caller to forge ancestry. Derived read/write/export/history recursively reject missing, archived, changed, differently scoped or cyclic sources; traversal is bounded to 16 levels / 100 visits. Chapter versions, content digests and source privacy review state are also bound.

Records start DRAFT. Approval policy is a subsequent reviewed-agent owner's responsibility; this stage does not manufacture a manual approval route. CAS conflicts expose only current version/status, not the internal current document. Successful and error responses use `Cache-Control: no-store`; authority is rechecked even when a private callback raises an error, and writes recheck before their store transaction commits.

## Actual verification

Tests run with the existing dependency interpreter and `-B -X utf8`, CWD / PYTHONPATH pointing to V2. `scripts/run_v2_checks.py` establishes owned `LOCALAPPDATA`, `PROJECT_ROOT`, `NOVEL_DATA_PATH`, memory credential storage and File backend before any application import. Temporary fixtures are under V2 `.runtime/v2-test/`. No paid or local model is called by these foundation tests.

Final foundation command:

```powershell
& 'D:\小说\AI-Novel-Studio-Latest-Product\.venv\Scripts\python.exe' -B -X utf8 scripts/run_v2_checks.py phase1-foundation-final2 -- python -B -X utf8 -m pytest tests/test_v2_creative_foundation.py -q --basetemp=.runtime/v2-test/foundation-final2 --junitxml=docs/delivery/v2-development/phase1-foundation-final2.xml
```

Actual result: **exit 0, 30 passed / 29 PostgreSQL skips, 1 dependency deprecation warning**, 10.85 seconds pytest time; wrapper 2026-10-08T05:02:11.149639+00:00 → 2026-10-08T05:02:24.392344+00:00. PostgreSQL nodes preserve the existing backend markers and are not represented as executed. The same tests are parameterized for an explicitly supplied owned PostgreSQL endpoint, including actual store reads, a separate interpreter restart, CAS and derived fences.

Evidence: [receipt](../delivery/v2-development/phase1-foundation-final2.json), [raw log](../delivery/v2-development/phase1-foundation-final2.log), [JUnit](../delivery/v2-development/phase1-foundation-final2.xml). The receipt inventory includes concurrent subsequent owners' Creative directory files; it describes actual working bytes, **not a claim that their unfinished files belong in the Phase 1 commit**. Root owns a selective index snapshot/catalog and phase commit boundary.

Earlier runs are retained:

- `phase1-foundation-red1`: 24 setup errors because the owned pytest basetemp parent had not been created, and one new test assumed eager FastAPI route objects. No product defect was inferred; the parent was created and the new assertion now inspects actual OpenAPI paths.
- `phase1-foundation-red2`: 24 passed / 1 failed because the new test incorrectly assumed the inherited comment's count 40; actual baseline 44 was proven and the complete ordered tuple is now frozen by hash.
- `phase1-foundation-green1`: despite its label, **FAIL**, 25 passed / 2 failed / 2 skipped. Its new scope test supplied two differently cased duplicate HTTP branch headers, so the original branch remained selected. The test now replaces its actual existing header key.
- `phase1-foundation-final`: 29 passed / 2 skipped before the requested additional exception-path guard and expanded PostgreSQL parameterization. The final2 receipt supersedes this as the current foundation run.

Original opt-in discovery, Director and branch manuscript regressions: **exit 0, 30 passed / 25 PostgreSQL skips**, 9.92 seconds pytest time. Evidence: [receipt](../delivery/v2-development/phase1-original-regressions.json), [raw log](../delivery/v2-development/phase1-original-regressions.log), [JUnit](../delivery/v2-development/phase1-original-regressions.xml). No original test source or assertion was changed.

## Boundaries remaining for later stages

### PostgreSQL execution addendum

Root initialized a new, disposable loopback database at `127.0.0.1:55432/v2_creative_tests` with the unchanged migrations 001–020. No existing database or RC1 profile was used. `phase1-postgres` first failed with 30 setup errors because this new database had no schema; that result and its log remain available. After initialization, the same tests passed: **30 passed, 29 File skips, exit 0**, 25.85 seconds. Command: `scripts/run_v2_checks.py --postgres-url postgresql://postgres@127.0.0.1:55432/v2_creative_tests phase1-postgres-initialized -- python -X utf8 -B -m pytest tests/test_v2_creative_foundation.py -q --basetemp .runtime/v2-test/phase1-postgres-initialized --junitxml docs/delivery/v2-development/phase1-postgres-initialized.xml`. [Receipt](../delivery/v2-development/phase1-postgres-initialized.json), [log](../delivery/v2-development/phase1-postgres-initialized.log), [migration hashes](../delivery/v2-development/postgres-initialization.json).

The verification resource launcher initially mishandled localized `initdb` output as UTF-8 text; capturing its raw bytes fixed only the V2 test harness. The initialized cluster was retained and its `PG_VERSION` checked before launch. The original PostgreSQL binaries are read-only inputs; data and logs belong to V2 `.runtime/v2-real`.

PostgreSQL execution awaits root's dedicated V2 endpoint. UI, true Screenplay/Director provider calls, approve/apply jobs and algorithmic storyboard/video planning need their separate code and run receipts. Source freshness uses the existing owners' version/digest/branch contracts; the transaction guarantee here covers records sharing the ExperimentalStore scope, and does not claim one distributed transaction with every separate manuscript or identity repository. Exports are typed planning JSON and cannot be interpreted as rendered video.
