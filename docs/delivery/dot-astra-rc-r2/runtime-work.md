# D04 / D13 / D15 runtime work

Baseline: `f8c141c39a543cc9dbea57647ac91185bc9aecd6`; working branch: `work/dot-astra-v1-rc-r2`.
Environment: isolated Linux, synthetic content, in-memory test credentials, no paid model calls. This is implementation/contract evidence, not Windows or real-provider acceptance.

## D04 — text dispatch and protocol adapters

Implemented:

- Existing text-node path retained. Provider Runtime v2 diagnostic `ALLOW` does not authorize dispatch, and the read-only routing service was not promoted to an execution broker.
- Actual adapter identity determines egress. The development DeepSeek mock stand-in is explicitly labeled in the model picker, response and Agent job; it is not misrepresented as a real DeepSeek request. Packaged readiness still rejects mock execution.
- Author generation re-reads current chapter/source review and approved creation-record versions, status, privacy and referenced chapter versions immediately before dispatch. It checks again after context/snapshot assembly. The shared source policy is hash/version/branch-bound; missing, revoked, stale or restricted policy blocks cloud dispatch. A source selection outside the reviewed chapter is rejected. Current collaboration authorization is checked again before the send.
- Context is rebuilt per actual route. Raw selected/chapter text can no longer bypass filtered context. Partial output or an already-dispatched request cannot silently fall back/replay; incomplete adapter EOF is a failure, not a fabricated completion.
- Completed responses preserve reported usage, provider reference and execution mode. Missing metering remains null/UNKNOWN. No invented cost calculation.
- Ollama NDJSON streams now require the actual terminal `done=true` record and preserve its reported input/output token counts through the normalized adapter ([official Ollama API contract](https://github.com/ollama/ollama/blob/main/docs/api.md)). Legacy compatible SSE also requires a completion marker.
- Non-stream and stream cancellation/late-result checks; safe transport error messages; no automatic replay of a partial legacy stream. Legacy automatic HTTP retries default to zero, with explicit bounded retry still available to existing callers.
- Agent context now filters every domain section for remote execution. Agent jobs recheck egress kind, source context hash and chapter version, preserve actual usage, fail safely on drift, and reconcile interrupted persisted WORKING jobs to FAILED without replay at startup.
- Existing OS credential vault is reused. Legacy supported providers now resolve their vault entry, not only DeepSeek. Packaged configuration does not treat an environment-only DeepSeek key as configured.

Native protocol addition:

- `app/native_text_providers.py` implements text-only Claude Messages/SSE and Gemini `generateContent`/`streamGenerateContent` SSE. It uses native headers/body/usage formats, refuses tool calls, fails truncated streams, honors cancellation and maps safe HTTP failures. It never retries, discovers keys or sends during bootstrap.
- Host configuration must explicitly set `ANTHROPIC_MODEL` or `GEMINI_MODEL`; no current model ID is guessed or preselected. Provider IDs are `claude` (existing vault identity) and `gemini`. Production credentials remain in the OS vault; existing development env fallback remains limited to non-packaged use. `ENABLE_CLOUD` remains required by route preparation.
- Explicitly registered models become selectable through the existing text-model catalog. No compatibility claim is made beyond the supported text protocol and synthetic contract tests.
- Sources checked 2026-10-05: [Claude Messages](https://platform.claude.com/docs/en/api/messages/create), [Claude SSE event contract](https://platform.claude.com/docs/en/build-with-claude/streaming), [Gemini REST authentication](https://ai.google.dev/api), [Gemini GenerateContent API](https://ai.google.dev/api/generate-content), [Gemini GenerateContent text guide](https://ai.google.dev/gemini-api/docs/generate-content/text-generation). Google currently labels GenerateContent as legacy alongside its newer Interactions API. This adapter implements the documented GenerateContent protocol, not Interactions.

Still partial / not run:

- Real model, network-disconnection behavior against real services, real provider billing, host hardware compatibility, Windows OS vault and native host bootstrap are NOT_RUN.
- Full authoritative v2 capability/compatibility/permission/credential/budget broker integration and multiple named vault profiles remain incomplete. Existing explicit trusted routes are used; diagnostic snapshots never fill those missing authorities.
- Transport cancellation prevents accepting late output and checks between chunks; a blocking socket read can last until its configured timeout. No unsupported claim of server-side cancellation.

## D13 — bounded durable workflow and Agent execution

Implemented:

- Corrected a false-success defect: triggering an Agent node now leaves it QUEUED, then WORKING. Downstream nodes wait for actual completion. Cancelled/rejected/paused workflows cannot be resumed through stale approval/worker updates.
- Added authenticated, owner/workspace/branch-bound workflow router. It rechecks current project/branch permissions for reads and changes. User-supplied `approved_by` is ignored; review records use the trusted actor. Unowned legacy workflow rows are not silently adopted by another user.
- Direct unscoped Agent jobs are bound to trusted actor/workspace ownership for get/list/CSV/mutations; retries retain ownership and review/apply audit names use the server actor. Existing authorized branch collaboration access is retained, while linked projects cannot create an unscoped bypass.
- Replaced public manual “mark success/failure” queue entrance with explicit selected-model execution backed by persisted Agent jobs and result synchronization. No API accepts arbitrary caller-provided worker success as proof of real model execution. Results still require the existing review/apply process.
- Three bounded local recipes are available in the current Workflow UI: import text → knowledge candidates → review; planning text → user-supplied draft/beat outline → review; scene text → shot/asset task proposals → review. These are real local rule-based transformations, explicitly labeled as such. They do not claim model authorship, create final Canon/manuscript, or submit media requests.
- Recipe input limits: 20,000 characters / 100 nonempty lines. Existing DAG limits: 100 nodes / 300 edges, with cycle validation. Runs keep their definition snapshots, node outputs/provenance, idempotent identity, deadline, explicit rejection, skipped failure descendants and durable review artifacts.
- Workflow UI now exposes recipe input, persisted run results, actual current manual approval, rejection, state-aware pause/resume/cancel and explicit retry. Agent queue shows selected provider/model and model-execution notice.

Still partial:

- The three reusable recipes prepare bounded review artifacts. End-to-end autonomous multi-agent knowledge import, model-written manuscript Draft/Diff/Accept routing and automatic media task execution remain incomplete; these are not advertised as completed workflows.
- Linked Agent jobs survive restart as interrupted failures and can be synchronized; no request is automatically re-billed. A crash between worker claim and job linkage requires explicit workflow cancellation/retry rather than silent replay.
- No claim of multi-process transactional sidecar scheduling or distributed worker leases. Current persisted workflow engine is a local host service.

## D15 — declarative package lifecycle; executable plugins remain disabled

Implemented:

- Host-local JSON bundle installation/update with strict manifest/resource allowlists, path/symlink rejection, resource SHA-256 and byte/count/JSON checks before atomic directory swap.
- Failed update restores the previous directory. One prior version supports explicit rollback; earlier/removed packages are retained in recoverable host archive directories. Package changes reset permission grants and require review; rollback never restores implicit trust.
- Existing manifest activation/resource reading remains separate from execution. UI adds bounded JSON bundle install/update, rollback and recoverable removal with truthful runtime boundary.
- Package mutation requires a trusted local session. Shared collaboration/packaged package mutation remains BLOCKED until a real host-admin authority exists, and the UI explains that boundary. No new account/permission bypass was added.

PR #26 independently inspected through `origin/feature/plugin-runtime-phase2b-windows-sandbox`, SHA `5cae6e00356e2c7a2f05f83352d99611a33dd948`. It is an older AppContainer prototype, not third-party plugin execution. Its own documentation marks real Windows token identity tests NOT_RUN, broker/credential resolver absent, third-party execution disabled. The branch was not merged; its absence of newer runtime/model-center work also rules out blindly replacing the current baseline with it.

`execution_supported=false`, `isolation=DENY_ALL` remain unchanged. Real Windows file/network/process denial, AppContainer token identity, cleanup and executable package trust remain NOT_RUN/BLOCKED. A normal process or Job Object is not treated as a sandbox.

## Verification

Focused tests added:

- `tests/test_r2_generation_egress.py`: actual transport capture, denied unknown/local/redacted source, current reviewed source, revocation during context construction, stale source/selection, no partial fallback, creation-record revocation and real reported usage.
- `tests/test_r2_provider_execution.py`: incomplete SSE, cancellation-before-send, adapter EOF, mock disclosure, whole-Agent-context filtering, interrupted-job recovery.
- `tests/test_r2_native_text_providers.py`: native request headers/payloads, streaming usage, safe 401/429/503 behavior, no replay and tool-output refusal.
- `tests/test_r2_workflow_execution.py`: all three recipes, persistence/restart/idempotency, real approval/rejection, cycles/input bounds, worker gating/cancel terminality, API owner isolation and trusted approval identity.
- `tests/test_r2_plugin_packages.py`: install/update/rollback/recoverable removal, failed-update restoration, malformed/hostile/integrity cases and symlink rejection.

Frontend focused run: 21 tests passed across WorkflowPanel, AgentQueuePanel, PluginManagerPanel and WorkflowInspector. Production build passed. UI token guard passed (39 files). No global shell/tokens/theme changes. Full-suite and browser geometry results are recorded by the integration owner; no Windows golden-image pass is asserted here.

Direct synthetic before/after reproduction: the original author `_run` sent a LOCAL_ONLY chapter canary; after the last-hop guard it returns FAILED with zero captured transport requests and no canary sent. `/tmp` scratch reproduction itself is not a deliverable and contains only synthetic input; the permanent regression is the egress test above.

## Opus handoff boundaries

Visible files: `frontend/src/novel/WorkflowPanel.tsx`, `AgentQueuePanel.tsx`, `WorkflowConsole.css`, `PluginManagerPanel.tsx`; API functions remain in `frontend/src/api.ts`. Continue using existing Panel/Button/StatusMessage primitives and DS-v1.0 tokens. Preserve failure/loading/empty states, disabled terminal actions, explicit review, source/usage provenance and non-executable plugin labels. Never replace actual worker state with a UI “success” button or make a disabled runtime appear available.

Final focused verification updates (development worktree; these overlapping runs are not additive test totals):

- Runtime/Agent/native/workflow/package/credential focused selection: 123 passed.
- Later plugin legacy/security plus native adapters and workflow selection: 181 passed.
- Aggregate regression follow-up: collaboration catalog, generation snapshot and phase-1 closure: 16 passed, 2 PostgreSQL-only skipped. Stable public error text and no-send assertions were retained; mock catalog exact-key tests now also assert the disclosure marker.
- Geometry attempt: 5 tests could not launch system Chromium because the environment denied its process-singleton socket; repeated approved execution had the same OS error. This worker records browser geometry as BLOCKED, not an assertion pass. Integration-owner runs may provide separate browser evidence. No snapshots were regenerated.
