# R2 engineering delivery report — draft

Status: **ENGINEERING_IN_PROGRESS / NOT RELEASE-ACCEPTED**. Updated 2026-10-05T06:59:40.727167+00:00.

## Delivery identity

- Repository: https://github.com/1785235376-blip/AI-Novel-Studio
- Working branch: `work/dot-astra-v1-rc-r2`
- Draft PR: https://github.com/1785235376-blip/AI-Novel-Studio/pull/37
- Starting SHA: `f8c141c39a543cc9dbea57647ac91185bc9aecd6`
- Current fixed inspection snapshot: `547167e8abce15cad3495779f52e845310a0a1fe`
- Fixed tree: `528459b8c7d6b94dde8b70e37c1e52d12524fc81`
- Final committed/tested/remote SHA: **PENDING_LEAD**
- Last remote head reported by the integration lead: `90f4369b7367579b7aaeb00d4d25f21171353753`. The integration lead verified this remote head and source tree. Commit metadata differs from local 547167e8; source bytes are identical. See SOURCE_TREE_EQUIVALENCE.json. Newer corrective commits and final tested identity remain pending.
- Actual main development/audit model recorded by the team: `gpt-6-astra`. This is the development model, not a required product provider.
- Environment: isolated Linux; local Python 3.12.14, Node 24.19.0, pnpm 10.6.5. CI is configured for Python 3.12.9, Node 22.14.0, PostgreSQL 16 and Windows/.NET 8.0.424. Configuration is not proof a job ran.
- Product remains 0.7.0/Beta engineering candidate; no merge, formal release or production deployment is authorized or claimed.

## Implemented and connected bounded capabilities

1. Privacy/data: conservative timeline/foreshadowing/Canon persistence, migration 018, no policy downgrade on File→PostgreSQL migration, hash/version-bound source review and final dispatch guards. Backups preserve complete selected runtime sidecars/assets and restore only into new directories/databases with inventory/digest checks.
2. Authoring/review: persisted STYLE/PLOT and typed world/psychology records, comments anchored to chapter versions, explicit structured planning suggestions with validated source quotes, editable Draft review, history/restore and approved inputs to existing generation. Four-group import extraction and separate explicit-marker rule/plot extraction retain human approval and honest partial-apply journals.
3. Acceptance integrity: captured generation base is authoritative; durable single-host acceptance claims block concurrent duplicate side effects and blind retry after ambiguous failure. Workflow/Agent queue observers fence full scope changes and stale responses.
4. Controlled execution: compatible and native Claude/Gemini text adapters preserve actual usage or UNKNOWN, cancellation, safe failure and no hidden paid replay. Adaptation, Agent, image/audio and motion paths recheck authority after preparation. Automatic memory extraction is guarded-local-only. Legacy remote asset generation without exact prompt consent is explicitly unavailable.
5. Exports: scoped history, reopen/same snapshot/download, current authorization and retry; structural Fountain fixes; immutable resource ZIPs; screenplay CAS/history; licensed pinned CJK font and PDF embedding evidence. Target desktop application typography remains unverified.
6. Media: persistent reviewed image queue, decoded results, recoverable asset trash/restore, digest/version lineage and approved lexical reference search; verified video downloads, exact-request motion consent and bounded silent clip assembly; persistent voice/segment queues, verified binary audio and ordered PCM WAV export.
7. Agent/workflow/plugins: bounded persisted DAG, actual selected-model Agent job completion, manual approval/rejection/cancel/retry. Three local recipes produce reviewed artifacts. Declarative plugin install/update/rollback/remove is integrity checked; executable plugins remain DENY_ALL.
8. Functional UI remains in the existing single NOVEL/IMAGE/VIDEO shell and design tokens. New forms, histories, errors, missing-configuration states and recovery controls do not claim completed native/window acceptance.

## Independent review: repaired original findings, new open discovery findings

At earlier frozen `eb165609`, an independent audit reproduced seven finding groups: adaptation cloud egress, Agent revalidation, image/audio pre-dispatch races, stale local Accept, concurrent acceptance side effects, project/outline policy omission and stale Workflow UI scope. The original Python invariant set now passes 10/10; the exact archived UI assertion also passes. Focused repair evidence is retained in `acceptance-scope-work.md`, `evidence/dispatch-repair.*` and `evidence/workflow-scope.*`. The current full original-invariant receipt is PENDING_LEAD publication.

The separate Local AI review of `547167e8abce15cad3495779f52e845310a0a1fe` reports five issues still awaiting accepted fixes:
- Ollama cloud-proxy models were treated as local based on loopback transport
- Enabled local text registrations were excluded by Writer streaming eligibility
- Changed model/digest rescan did not reliably invalidate registration authority
- Late validation/enable could override a newer Disable
- External llama.cpp validated model alias did not consistently match actual dispatch identity

Author changes are in progress beyond the fixed snapshot. Their presence in the working tree is not independent verification. These prevent a release-final conclusion even though prior synthetic discovery tests passed.

## Local AI Discovery supplement

All 28 sections are mapped in the feature matrix. The real Settings → Model Center → Local AI entry and both `/api/model-center/local-ai` and `/api/v1/model-center/local-ai` routes are mounted. Read-only bounded detection, validation, disabled registration, separate explicit Enable, license acknowledgment, configuration, cancel/partial results and registration-only removal are implemented. Host paths stay on the trusted local surface.

Supported discovery: Ollama tags/show metadata; configured llama.cpp/GGUF header/metadata; ComfyUI system_stats/object_info and model/node evidence; A1111 checkpoint lists; configured local OpenAI-compatible models lists and Custom HTTP health. Flexible family declarations include Qwen text, Qwen-Image, FLUX/FLUX.2, Z-Image, H3, Wan, LTX, SeedVR2 and RIFE. Unknown names remain unverified.

Execution depth: existing Ollama/llama text and A1111/standard SD Comfy image bridges are present but current local-route review fixes remain pending. Nonstandard Comfy video/restoration/interpolation/family workflows are **PARTIAL**, not generated from guessed JSON. Generic HTTP/model-list and credential-required custom runtimes remain disabled without verified adapters. `minimax-h3-video` is independent VIDEO identity; old audio `minimax-h3` stays disabled for history. No actual GPU/model inference ran.

Source: `app/model_center/discovery_*.py`, `discovery.py`, existing provider/hardware/domain/services; UI `LocalAiDiscovery.tsx`, `localAiDiscoveryApi.ts`; docs `LOCAL_AI_DISCOVERY.md`, `LOCAL_AI_WINDOWS_ACCEPTANCE.md`, `OPUS_UI_HANDOFF.md`.

## Test status, without combining verification layers

- Latest full File checkpoint: **2032 passed, 35 skipped, 1 failed**. The failure is the missing-policy-authority import fixture expecting the older error contract; production currently rejects with 403. The focused contract rerun now passes 143 tests; it does not replace the pending full rerun.
- Latest full frontend checkpoint: **548 tests / 108 files passed**. Later discovery changes still need rerunning at the final SHA.
- Earlier dedicated provider/hardware/discovery checkpoint: **263 passed, 1 skipped**, synthetic metadata/adapter contracts. Skip is real Windows native acceptance. Independent review subsequently found the issues above.
- File/provider/UI focused counts overlap and must not be summed into a completion measure.
- Final exact-SHA File/PostgreSQL/frontend/build/tokens/browser/hosted Windows results: **PENDING_LEAD**.
- Local browser launch: blocked before assertions by socket EPERM. Browser test existence or collection is not a pass.
- Real model/GPU, interactive Windows/WebView2/OS vault, full installer/upgrade/uninstall and user acceptance: **NOT_RUN**.

See [TEST_RESULTS.md](TEST_RESULTS.md) for checkpoint provenance and [RELEASE_READINESS.md](RELEASE_READINESS.md) for gates.

## Packaging and user acceptance

The current scripts verify source/Host/font provenance and can build a hosted Windows Host artifact when the job succeeds. A standalone Host EXE is not a complete installer. No verified complete BaseApplication distribution was available; full installation and bundled codec/license delivery remain explicit blockers. No new-head hosted Windows result is assumed.

Use root `USER_ACCEPTANCE_GUIDE.md` and `LOCAL_AI_WINDOWS_ACCEPTANCE.md` with isolated synthetic data after the lead provides the verified final candidate/checkouts. Preserve original data, validate backup to a new instance, review model licenses and enter credentials only through the existing trusted Host/OS-vault path.

## Remaining concrete work

- Close the five discovery review findings and prove actual approved Writer dispatch plus current revocation/locality.
- Retain the 143-test focused correction evidence without weakening fail-closed authority; rerun all final gates.
- Publish newer corrective changes, read back the final branch/PR head and inspect every CI job/artifact at its exact checkout SHA; existing fixed-tree delivery is already verified.
- Keep multi-key profiles/full v2 broker, semantic visual retrieval, cover/storyboard-specific generation, whole-book hierarchical planning, automatic speaker/emotion/mastering, final-master video and executable plugin sandbox clearly partial/missing.
- Complete actual Windows/model/GPU and user acceptance separately; these are not transferred to Opus as hidden backend work.

## Delivered commit chain through current integration snapshot

These are the delivered remote-chain commits through 90f4369b. SOURCE_TREE_EQUIVALENCE.json maps metadata-different local review commits to byte-identical remote trees. Later corrective publication/testing remains PENDING_LEAD.

- `825b3caf40f6f7f617e5350fd1efcfe86533a003` build: pin frontend toolchain and record verified R2 baseline
- `78920f2f9435a9c1d5625479c37b0948c1db5b51` fix: preserve privacy across storage and verified recovery
- `e8ebfccdce0678cac15c632d640ac57bd822b93f` feat: enforce controlled model dispatch and durable workflow execution
- `ff34bf87979e2c4dc39681b3d91069979bca06a7` feat: add scoped reviewed media queues and recoverable assets
- `c6e8c07d8786da24c3e265561cece80c4bf5b73b` feat: persist reviewed author plans and version-anchored collaboration
- `db3212c3f1418557e3ab0152e8c3c0c8ee27ef97` build: verify CJK font provenance and expand release candidate gates
- `40464f656aa1437e5b56969212ea801eccfcafc0` feat: recover frozen exports and version screenplay edits
- `16b65c10ada1670ac57891054ffe4571fa463491` feat: integrate reviewed planning and fail-closed release candidate workflows
- `90f4369b7367579b7aaeb00d4d25f21171353753` fix: close independent dispatch and acceptance gaps and integrate local AI discovery
