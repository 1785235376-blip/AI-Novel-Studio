# M4-B Provider contracts and reviewed text assets

**Bounded text checkpoint, PARTIAL. Corrected-source selected regression is verified; commit publication and exact new-SHA full hosted CI are pending.**

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
