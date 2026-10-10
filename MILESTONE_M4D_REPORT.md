# M4-D — Creative screenplay export checkpoint

## Scope and ownership

Continues published M4-C `e6ff3431cf84b01b77cd1bd73a977fd5e784447b`
under the 2026-10-10 overnight authorization and complete Master Roadmap.
This is the first roadmap Text/Screenplay deepening slice after the previously
authorized AI Execution Layer. It does not restart M4-A/B/C.

Roadmap TEXT-15 now has a CreativeService-owned Fountain/DOCX/Markdown adapter,
private version-pinned API and saved-document download UI. Existing industry
encoders are reused; no manuscript, legacy screenplay, registry, queue or asset
owner is duplicated. Chapterless independent creation remains explicit.

The format projection preserves ordered scene text, dialogue/delivery, emotion,
location/time and source/version attribution. Original JSON remains the complete
structured export. Encoding is outside transactions and followed by original
authority, source/privacy, incarnation, version and digest checks. Client-side
byte/MIME/version verification and late-result cancellation protect downloads.
See the [API and user contract](docs/v2/creative-screenplay-export.md).

## Parallel engineering integration

B's isolated commits `5b8a42a382a08dea6ab2e8275c097522c2d1d3d8` and
`79f2f1ef748857508cdbe77c97200aa779fdfa0c` were reviewed and serially integrated.
The only workflow change adds pip download cache inputs for backend execution
and original TCP. Original install/check/freeze and test commands, File=1/PG=2,
20/55-minute budgets, frozen jobs and strict joins remain intact.

The new read-only capacity analyzer identifies archived progress windows and
available exact JUnit timing. It never emits a coverage PASS or substitutes for
the reconciler. Hosted cache benefit remains unmeasured until a published run.
[Cache implementation](docs/delivery/ci-capacity/DEPENDENCY_CACHE_20261010.md) and
[capacity evidence](docs/delivery/ci-capacity/CAPACITY_ANALYSIS_20261010.md) retain
source/attempt identity and all observed failure distinctions.

## Actual local verification

Final source: **1,752 runner inputs**, source-map SHA256
`d711da406c1b258647b70c6efd0ef14c842774720af02c95fede8fe9b4ba578f`.
The following final checks have identical before/after maps; no mixed-source
aggregate is claimed. The [final verification receipt](docs/delivery/v2-development/stage-m4d-publish-verification.json) binds original logs, JUnit counts, source hashes, runtime shutdown and frozen-contract preservation.

- Six-file File regression: **153 passed / 118 opposite-profile skips**.
- Same six files on a new empty PostgreSQL database: **131 passed / 16 failed /
  124 opposite-profile skips**. All **21 new screenplay-export cases passed**,
  as did Creative foundation/project-lifecycle and industry exporter contracts.
  Original Creative model workflow cases account for all 16 failures.
- Those 16 calls exceeded the existing `wait_ledger` five-second observation
  window while reading RESERVED/DISPATCHED. This run overlapped the File suite,
  frontend suites and build. Contention is a hypothesis, not established cause.
  Subsequent local resource scheduling keeps PG and full frontend/build serial.
- One bounded isolated diagnostic reran one original failed case unchanged and
  passed: call 6.91 s, nine original ledger GETs 0.255–0.427 s each, ending SETTLED
  within the original five-second wait. It does not erase the 16 failures or
  establish a general performance fix. Observations and harness are retained in
  [the diagnostic folder](docs/delivery/v2-development/m4d-wait-diagnostic/).
- Both PostgreSQL runs used new clusters/databases, the 20 original migrations,
  live identity/empty-database receipts, retained data and normal server shutdown.
- Complete frontend: **2,416 passed / 8 unchanged historical skips**; 279 passed
  files and two old skipped files. This includes 15 new UI/client/parser cases.
- TypeScript, Vite build and **52-file UI token guard** passed. The existing large
  bundle warning remains a warning; no threshold was raised.
- Real HTTP/File three-format byte receipts and exact-version/owner preservation:
  **1 passed**. This request-only test does not launch or claim a browser.
- Complete CI infrastructure, including both B additions: **320 passed**.
- Two independent full collections agree on **11,363 ordered nodes**, +42 new
  backend cases. Frozen V1 bytes, original ordering and skip policy are unchanged.
  Collection is not execution or strict-coverage acceptance.
- Original staged API catalog generation: **2,125 mounted operations**, +2 GET
  routes because the existing application exposes both `/api` and `/api/v1`
  aliases. Both use the same V2 flag and original authority.
- Hosted exact-SHA CI is pending publication. Local browser/visual acceptance
  remains blocked before page execution; the additive hosted journey is ready.

**Classification: IMPLEMENTED_WITH_ACCEPTANCE_PARTIAL + FAILED_OBSERVED.**
This stage has validated export-specific File/PG behavior, not a completely
passing PostgreSQL adjacent regression or full-source acceptance.

Retained initial failures:

- File r1: the new pytest basetemp parent did not exist; 18 setup errors, no
  successful execution. File r2: four new test calls used a nonexistent fixture
  service method. The fixture was corrected to the existing ChapterService.save.
- Types r1: new client-test mock signatures/typed-array BodyInit needed explicit
  TypeScript types. Production contracts were not relaxed.
- UI r2: the new independent-parser synthetic row omitted `mode: SCREENPLAY`;
  the original mode guard correctly rejected it. The fixture was corrected.
- Full frontend final1: the invocation used a root override from the repository
  directory, while an existing browser-contract suite reads files relative to
  the frontend working directory. It reported 2,412 passed / 8 old skips plus
  one suite-load error. The original tests are unchanged; the corrected command
  runs from `frontend`, as the normal package command does.
- Local browser r1: Chromium failed at `socket()` with EPERM before opening a
  page. No sandbox/OS bypass, assertions or timeout changes were attempted.
  Trace and original console receipt remain in delivery evidence.
- PostgreSQL final1: 16 original workflow wait failures remain in the original
  log/JUnit. No existing fixture, assertion or timeout was changed to obtain
  the separate one-case diagnostic pass.

No old test bodies/assertions, frozen hashes, skip allowances or timeouts were
changed. New tests are additive, including two cases in the existing hosted V2
live suite. Default-off/V1-off, read-only role, scope, source-version/privacy,
archive and permission revocation are covered through the original owners.

## Existing unresolved evidence

Published e6ff M4-C hosted CI is **INCOMPLETE_HOSTED_CI + FAILED_OBSERVED**:
29 jobs, 22 success / 4 failure / 3 cancelled. Both File executions have no final
complete receipt. Push PG shard 0 includes an original failed call in
`test_manual_refresh_completion_boundary_requires_archive_before_review[postgres-settling]`
and was cancelled. The successful PR PG profile and bounded later diagnostic
checks do not erase that call or establish its unique cause.

Four strict joins failed their execution prerequisites; downstream reconciliation
was not reached. Historical independent security review remains BLOCKED.
Current export tests cannot close these previous findings. There is no full V2
acceptance, Windows/GPU acceptance, new real-model-quality result or release.
The original [e6ff terminal receipt](docs/delivery/v2-development/stage-m4c-e6ff-hosted-terminal.json)
is retained byte-for-byte from the completed M4-C delivery.

## Dependency-ready continuation

After this verified checkpoint, continue roadmap TEXT-17 standalone generic
Script documents within the existing CreativeService, followed by TEXT-13
source-aware reviewed screenplay adaptation. No large Image/Video milestone is
claimed complete or entered merely because this export adapter exists.
