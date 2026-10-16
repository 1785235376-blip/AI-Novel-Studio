# M4-B Provider contracts and reviewed text assets

**Bounded text checkpoint, PARTIAL. Initial M4-B a1eb536 is published. Its first hosted CI exposed an unstable new parameter ID and a manual-refresh archival race. Both narrow corrections are implemented; final-source File/new-PostgreSQL neighbor regression is verified. Corrected-SHA hosted execution remains pending.**

The user-defined M4 AI Execution Layer scope continues from verified local and
remote `09883fb7fe35b241f97ea7fe0a3e292178441935` on
`feature/v2-narrative-platform`. Delivery remains [Draft PR 47](https://github.com/1785235376-blip/AI-Novel-Studio/pull/47).
This report does not rewrite the historical [M4-A report](MILESTONE_M4_REPORT.md)
or treat its CI outcomes as this source's acceptance.

## Implemented slice

| Module | Code, API and UI | Acceptance boundary |
|---|---|---|
| ModelProvider | Uniform capability, availability, execution and result contracts; static facades for Ollama, llama.cpp, LM Studio, ComfyUI and reserved API | Original registry, TextModelNode and JobManager remain the only execution owners. Declarations do not authorize a call. |
| ModelRouter | Original ModelBroker facade; TEXT/IMAGE/VIDEO task requirements, explicit route preference and RAM/VRAM filtering | Read-only advice. Unknown capacity fails an explicit minimum; total capacity is not free memory or measured fit. No allocation/global fairness or fallback. |
| Local text | Existing enabled, explicitly authorized external Ollama/llama.cpp adapters; bounded request/result contracts | Real host/inference/quality NOT_RUN. Built-in Mock contracts only. |
| LM Studio | Actual OpenAI-compatible request/response codecs, loaded-instance identity validation and contract tests | Execution fails closed with LMSTUDIO_LOCALITY_UNVERIFIED. A loopback address does not establish local execution. |
| Image/video/API | Typed modality and provider availability interfaces; ComfyUI capability declarations; API reservation | Not executable through this text slice. No ImageStudio/VideoStudio, API key entry or paid requests. |
| Text result assets | TextNode → original Runtime/Provider/JobManager → original AssetLibraryService private DRAFT v1 → original human review → asset review v2 | No manuscript/Canon writes; v2 records a review transition, not edited text content. |

The two added scoped endpoints are GET `.../studio/graphs/provider-contracts`
and POST `.../studio/graphs/model-match`, under both existing API aliases.
They retain current host, actor/project scope/incarnation, feature/acceptance and
no-store guards. Capability/match UI is advisory and never dispatches implicitly.
The existing execution confirmation now discloses private draft storage in one
sentence; no extra checkbox, recovery button or required step was added.

Current UI dispatches with `archive_result: true`. The field remains an exact
optional boolean on the historical HTTP endpoint for old clients; omitted/false
uses the preserved M4-A proposal contract. Consequently this milestone does not
claim that every historical client/job has been migrated to mandatory archival.
All accepted new-UI text results use the new archival path before review.

## Ownership and interruption recovery

The user accepted the two-owner storage approach subject to no extra user steps.
[Text-asset design](docs/v2/text-result-assets.md) specifies the actual ordering:

1. Original job must be durably COMPLETED, with completed terminal accounting
   and its original zero-cost SETTLED ledger, exact source/job/route identity.
2. Original AssetLibraryService atomically commits text bytes and sealed origin
   as one actor-private DRAFT asset v1, using an incarnation-bound idempotency key.
3. Original WorkflowRun admits the saved result to its existing human review.
4. Original approve/reject is authoritative; asset metadata CAS projects that
   decision to v2 without changing text bytes or making the asset public.

A current authorized run read/reopen or existing refresh makes one bounded
convergence attempt. Failed automatic reads have a two-second cooldown with at
most 100 transient keys; run-list reads never bulk-reconcile. Recovery never
reconstructs the old dispatch closure, schedules model work, or retries inference.
Uncertain terminal receipts, changed source/route, unavailable private bytes or
archive failures mask output and expose INCOMPLETE. Original completed job bytes
remain retained for recovery. This is not a distributed transaction or unattended
background recovery guarantee. Original cancellation/late-callback fences remain.

Asset/project aggregate quotas include private assets. A raw source lease and
existing asset→project ownership order guard short storage commits; slow provider
observation stays outside the persistence transaction. The original graph, asset,
provider, generation and review owners remain authoritative; no second queue,
registry, asset database or review state machine was introduced.

## Official protocol evidence and real-host boundary

The [provider contract design](docs/v2/model-provider-contracts.md) records current
primary sources. LM Studio's [LM Link documentation](https://lmstudio.ai/docs/developer/core/lmlink)
allows localhost requests to run linked remote models; the
[native model-list schema](https://lmstudio.ai/docs/developer/rest/list) does not
provide trusted device locality and file digest. Therefore generic OpenAI-local
compatibility and model listing are insufficient authorization. No LM Studio SDK
was added; the existing HTTP stack is used for codecs/contracts only.

A bounded passive check on 2026-10-10 at 10:29 UTC found no `ollama`, `lms`,
`llama-server` or `nvidia-smi` executable and no connection at the five inspected
loopback runtime ports. This is an observation of this dot cloud only, not a
machine-wide absence claim. No install, model start, download or inference was
performed. Real model output quality and user Windows/GPU acceptance remain
NOT_RUN / LOCAL_REQUIRED.

## Corrected-source verification

Exactly two runner inputs changed after the first candidate: the new archival
adapter and its new test module. Original JobManager, settlement, original tests,
CI budgets and assertions are unchanged. Corrected **1,733-input** source map:
`77929b825e274d15f5b371893618d82dbd55a82925aa107b7acdc4f5e17f328b`.
Corrected full frontend: **2,313 passed / 8 original skips**. The entire new
archival test module passes **21 / 21 opposite-profile skips**, including DRAFT
and APPROVED stability after original terminal notifications and rejection of a
contradictory settled ledger. The full corrected **18-file File selection passes 554 / 350 opposite-profile
skips** in 159.32 seconds. TypeScript/Vite, the 52-file token guard, infrastructure
279, and original 7/additive 17 browser inventories pass on this same source.
The identical fresh PostgreSQL selection passes **548 / 356 opposite-profile
skips** in 514.07 seconds. PostgreSQL 17.11 started with a new empty database,
applied all 20 unchanged migrations and stopped normally; data is retained.
The [publication verification](docs/delivery/v2-development/stage-m4b-publish-verification.json)
checks each final receipt, log hash, JUnit counts and identical before/after source
map. This is selected owner regression, not execution of the full 11,071-node
backend inventory. The earlier ledger below is historical candidate evidence,
not substituted acceptance.

Current generated catalog remains **2,123 operations**, now bound to the corrected
application fingerprint. Corrected V2 inventory: **11,071 nodes (+343 over M4-A)**,
with original order/skips/gates preserved; SHA256
`bd35e4c5ddf02e9f53740c77511ec2fa87836e364214fd68175f8439da46e400`.

## Verification ledger

First candidate runner source: **1,733 inputs**, SHA256
`bce61d73ffbcd3f593d4c10f84abffd6c28b77703f439ca2e6e21c1546a9a11c`.
Full frontend: **2,313 passed / 8 original skips**. TypeScript/Vite and the
**52-file** design-token guard pass; catalog/CI infrastructure **279 passed**.
The final **18-file File selection passed 551 / 347 opposite-profile skips**
in 165.94 seconds. The identical new-empty PostgreSQL 17.11 selection passed **545 / 353
opposite-profile skips** in 526.26 seconds, with all 20 original migrations and
normal shutdown. Its fresh database is retained. These candidate passes do not
resolve the additional timestamp defect described below. Development passes and failures retain distinct source maps
and are not combined into a final whole-tree pass.

The generated catalog has **2,123 operations (+4 / -0)**. The separate V2
inventory has **11,065 nodes (+337 over M4-A)**, preserving the old node order,
exact skips and gates. Manifest SHA256:
`a5dc7987bfd8d33495bc924997bfb9192c7f3695432dd1f2b69a58b76b099922`.
The first inventory attempt rejected concurrent catalog generation before writing;
that rejection is retained. The second collected after catalog stability and
passed preservation checks. Collection is not executed test coverage.

- Provider module contracts: 118 passed (76 new plus 42 unchanged execution tests).
- Asset owner selected regression: 162 passed / 127 opposite-profile skips.
- Early 12-file File neighbor selection: 473 passed / 333 PostgreSQL-profile skips.
- Original-worker restart fixture initially raced its final persisted updated_at;
  red receipts are retained. The test now waits for the actual original worker
  with its existing finite join and checks that it stopped. Durable identity
  checking in production was not relaxed.
- An isolated original-owner diagnostic found that JobManager's legitimate final
  notification changes job.updated_at after settlement. Using that mutable value
  as immutable asset produced_at can strand an already saved DRAFT as INCOMPLETE.
  The red receipt and diagnostic are retained. The correction uses the original
  ledger's stable completed-settlement timestamp and confirms job_status COMPLETED.
  JobManager and its full durable/in-memory timestamp check remain unchanged;
  new DRAFT/APPROVED notification and contradictory-settlement regressions apply.
- A new late-registration red test demonstrated provider change after asset
  validation could precede workflow review commit. Current-registration checks
  now remain bound through both review and asset commit; its red and subsequent
  verification remain separate.
- Real mounted API wire replay initially exposed one newly added LM Studio reason
  code mismatch. The new UI contract was aligned to LMSTUDIO_LOCALITY_UNVERIFIED;
  actual catalog/match/dispatch/DRAFT/APPROVED wire replay is 8/8.
- Browser fixture self-check uses real File/API/JobManager and built-in Mock only.
  Additive browser inventory is 17 tests, preserving the earlier 16. Collection
  and HTTP/strict-client replay do not establish browser pixels or interaction.

Local Chromium execution remains blocked before page creation by the existing
IPC EPERM restriction. No security workaround was used. Exact new-SHA hosted CI
must execute the unchanged original browser jobs plus the additive M4-B journey.

## Preserved historical limits and remaining work

M4-A `09883fb7` hosted terminal history remains **29 jobs: 25 success, 3 failure,
1 cancelled**. Its push Cloud strict joins passed; its PR File job was cancelled
at the original capacity limit and strict joins failed their prerequisites.
The separate shared R123 historical-source assertion failed. These are distinct
outcomes, not a merged cross-event pass. M3-C PARTIAL_PR_CI_CAPACITY remains
historical evidence, and the independent security-review BLOCKED state has not
been lifted by this implementation's same-round code checks or tests.

M4-B remains PARTIAL: LM Studio trusted-local execution, live local model quality,
API execution, image/video generation, measured GPU fit/global scheduling,
editable text-content versions and user-machine acceptance are not completed.
No V1 frozen source, original CI timeout/skip/assertion/hash policy, Interop
protocol or QingJian source is changed. No main merge, release or deployment.

## Hosted collection correction after a1eb536

Initial M4-B commit `a1eb536de906bc87999fad8f5b3328f84c9252e5` was
published on the feature branch with 158 files. The original backend collection
gate rejected its inventory before product execution: a new future-timestamp
case used `datetime.now() + one day` as an automatically generated parameter ID.
The hosted 11,071-node list differed at exactly one position (10739), solely
because collection happened later. The failed source, logs and artifact are
retained; the earlier selected regression never established full-suite acceptance.

The correction gives only that new parameter an explicit `future_utc` ID. Its
actual future time value and rejection assertion remain unchanged. No production
code, original test, timeout, skip, V1 frozen hash or coverage gate changes. The
separate V2 inventory was regenerated through the original fail-closed generator.

Corrected runner source (1,733 inputs):
`0393024d699c1ef7e5e95e584e0847c44e011db2acd7046957ae2da58599f19b`.
Corrected manifest SHA256:
`05556ea87c8c8122608d8d0ec723b142a8686f7ed1505849690fa2dd1d97b7e9`.
Two independent full collections with different hash seeds each produce the
identical ordered 11,071-node inventory and backend classifications, preserving
all 10,728 M4-A nodes in order and exact historical skips/gates. This is inventory
proof, not product execution. The entire provider module passes 76 tests and
unchanged infrastructure passes 279 on the corrected source. See the
[collection proof](docs/delivery/v2-development/stage-m4b-stable-node-collection-proof.json)
and its adjacent reproducible verification script. Exact corrected-SHA hosted
File 1 / PostgreSQL 2 execution and strict joins remain required.

## First hosted CI and manual-refresh consistency correction

All five initial `a1eb536` workflows completed naturally, attempt 1, with
**29 jobs: 17 success, 12 failure, 0 cancelled**. Each push/PR Cloud event has
three collection-gate failures, two prerequisite-failed strict joins (reconciliation
not reached), and one failed original M4 live browser case. No run was cancelled
or rerun. Original creative browser 7+8, frontend 2,313 unit passes/8 original
skips and remaining original business journeys, Interop and limited hosted
Windows checks passed in both events. The shared fixed-source R123 workflow
succeeded by actually reproducing all three known historical defects as red;
this does not certify the current source or overturn earlier R123 failures.

The additive browser inventory executed **16 passed / 1 failed** in each event.
The new M4-B flow passed: one original Mock call, one private asset, one injected
review-metadata failure, original GET/reopen recovery to APPROVED v2, no model
replay/cloud calls/chapters; both matching and asset geometry passed all three
viewports. The failed case was the unchanged original M4 manual-refresh flow.
Its trace shows WAITING_APPROVAL / RESULT_REVIEW with asset PENDING and no review
shown because the safety view correctly marked the inconsistent result stale.

The production cause is completion between refresh's two observations. An
archival dispatch could reach legacy success processing without current asset
phase authority. The narrow runtime correction defers completed output until
a later authorized refresh establishes that phase outside the transaction.
Only the exact original bound live job retaining its nonpersistent prepared
invocation and all original callbacks may remain refreshable during unsettled
accounting. Restored, missing-authority or otherwise uncertain completion remains
masked INCOMPLETE, with no accepted output/asset/review. Original FAILED/CANCELLED
handling remains unchanged. No second state owner, automatic model retry, UI
workaround or relaxed browser assertion/180-second limit was added.

Two deterministic completion/settling barrier regressions failed before repair
and passed afterward. The two M4-B asset modules then passed 39 File tests,
including both mounted aliases and existing storage-failure/revoke/source-change/
cancel/restored-accounting boundaries. Eleven original terminal/cancellation
cases also passed. Existing fence cases were rerun, not newly invented. Original
browser spec and fixture remain byte-identical. The final 18-file selection passes **File 558 / 354 profile skips** in 172.42
seconds and **new PostgreSQL 552 / 360 profile skips** in 532.89 seconds. The
new database began with zero objects, applied all 20 original migrations and
stopped normally with its data retained. These are same-final-source receipts;
earlier source results are not substituted.

Final correction source (1,733 inputs): `b1589462aa97198dec5a91d5285dc4fab8ac9a607d6159f5e69f183a2e9f1968`.
The regenerated inventory is **11,079 nodes** (eight additional fixture-profile
regressions, original M4-A nodes/order/skips/gates unchanged), SHA256
`7f6a1a9b2ffd23ff3a27a9f3819aa185cc51307479f185b7a535b965e75cdaf5`.
API count remains **2,123**, with no operations added or removed by these fixes.

The first hosted attempt is retained in the [terminal summary](docs/delivery/v2-development/stage-m4b-a1eb-hosted-terminal.json)
and [compact evidence ZIP](docs/delivery/v2-development/stage-m4b-a1eb-hosted-evidence.zip).
The compact packet preserves all 29 decoded logs, all six collection-failure
receipts, source identities, original failed trace/network text and screenshots,
and successful M4-B owner/geometry receipts. It does not contain a fully playable
trace or all large original artifacts; the full original traces and complete
portable evidence remain preserved for the final downloadable delivery.

Final-source validation also passes unchanged infrastructure **279 tests** and
two independent full **11,079-node** collections with exact ordered IDs and
backend classifications. The [final publication proof](docs/delivery/v2-development/stage-m4b-ci-corrections-publish-verification.json)
binds all final selected results to the same source map and confirms fresh-PG
normal shutdown. Full corrected-SHA hosted execution remains pending.
