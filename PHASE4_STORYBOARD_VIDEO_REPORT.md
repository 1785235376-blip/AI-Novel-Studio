# Phase 4 — Storyboard Enhancement and Video Runtime Foundation

Baseline: c67a3c332ac493e67e5c873de3b00d8683219ca9. Branch: feature/v2-narrative-platform. PR47 remains Draft; no merge or release.

## Source and ownership

Original CreativeService/CreativeProjectStore retain documents, source evidence, scope/incarnation, CAS and history. The Storyboard adapter owns no new collection. Shot versions count actual retained shot-content changes and deletion/recreation in original history. Shot relationships are authored adjacent previous/next constraints with character/outfit/environment/camera notes, not measured pixel consistency. Director note IDs, camera/visual/rhythm advice and additional lighting/color/material/transition fields are additive. Advice never overwrites a source.

A trusted Host read returns an exact Storyboard document pin, per-shot version/digest, formal image reference and explicit approval. Image requests prepare the original MediaCommand; they do not dispatch. Original ImageJob private candidates remain unbindable until explicit human review promotes their original Asset version. Binding checks document and Shot CAS plus exact Asset version/digest and stores references only. Content edits revoke approval; changed shots lose current bindings while original history remains.

Approved Storyboards with selected formal image references can create an original schema2 Timeline draft. It maps shots to image clips, retains exact creation provenance, and performs no rendering or Video dispatch. Original Timeline editing/history/restore remain independent author actions; creation provenance is historical and does not impersonate current Storyboard approval. Limits: 30 selected shots, 600 seconds total, width16–1920, height16–1080, fps1–60.

## Explicit Graph schema5

Schemas1–4, their catalogs, request identities, 16 legacy versus24 media targets and existing budgets remain unchanged. Explicit video catalog and schema5 use typed Director/Storyboard projection, selected Shot version/digest, TEXT, kind-checked ASSET_REF and VIDEO_CANDIDATE ports. Video nodes allow original m7.video.t2v/i2v/v2v, and must connect to the original media review. Shot-bound Video requires current explicit Storyboard approval. I2V may resolve its exact bound image; conflicting sources and duration are refused. Private candidates are not formal inputs. Original WorkflowRun claims, deadlines, idempotency, UNKNOWN no replay, source fencing and recovery remain authoritative. Source-document checks stay pure under the raw scope lease; implicit image checks run separately under the original Asset lease. Graph outputs remain capped at64KiB with no automatic truncation, 24nodes,4generators,40edges.

## Local Video execution

Model Center discovers, validates, registers and explicitly enables original-registry local routes. Providers never install/start/download models. Fixed ComfyUI recipes are finite and object_info/schema/component/link proved: LTX-Video2B0.9.5 T2V/I2V, Wan2.2TI2V5B T2V/I2V, HunyuanVideo1.0 T2V. Other versions, local V2V and local reference-video conditioning remain NOT_CONFIGURED. Existing configured HTTP V2V adds optional exact video-reference source and style/action/camera purpose; unset legacy requests are unchanged. A purpose describes authored metadata, not guaranteed model behavior.

Manual preview/create/execute/poll/private candidate/review/Asset use the original VideoJob owner. Completed Comfy output must come from the fixed SaveWEBM node with successful completed status and a closed same-origin safe output receipt. Download wire/decompressed bytes are capped at25MiB; native probe/decode keep their original limits and bounded process runner. Candidate publication rechecks source, route and task. Cancellation uses original source→Asset→project leases and job CAS, can interrupt guarded native inspection from another thread, and cannot overwrite REVIEWING or promoted output. Comfy receives no global interrupt; remote compute can continue. Network cancellation is per chunk with the existing bounded read timeout, not a claim of immediate interruption during a stalled read.

Recipe parameters: width/height64–1024 multiples32, requested duration1–10s, fps1–30, at most241frames and268435456 pixel-frames. Frame counts quantize to4n+1 or8n+1 and the planned duration is shown explicitly. Original output inspection validates actual decoded media, but this foundation does not attest output dimensions/fps/frame count against the planned native model result. Synthetic CPU WEBM is a transport/owner fixture, not inference or quality proof.

## PostgreSQL defect

The prior two Director failures were reproduced on both the prior and current source before this fix. Repeated existing authorization/source/route/budget reads opened redundant PostgreSQL connections. Each authorization callback now holds one current original source lease then project lease so existing reads share that checkpoint. Checks run again on every callback; no authority snapshot persists between callbacks or provider execution. Live Host/feature rejection precedes private reads. Original source/current route/budget/author checks and original five-second ledger assertions remain. Earlier failures remain evidence and are not reclassified.

## UI and Opus boundary

Controller-backed Storyboard shot list/canvas/preview/Inspector, Director advice groups and explicit image-binding/approval/timeline actions reuse the AppShell, design tokens and original Studio media panel. Graphschema5 catalog/upgrade/Shot selection and Video candidates retain original media execution controllers. Strict decoders use captured mounted synthetic API payloads. Opus can reorganize visual components; original Host/scope/identity retirement, late-response fences, parent mutex, CAS, exact source pins, private review and UNKNOWN no replay are not view-layer options.

## Verification

Backend File and fresh real PostgreSQL each executed **616 passed / 1 failed / 321 skipped / 0 errors**, including mounted API aliases and guarded synthetic CPU media. The one failure in each is the unchanged original local-discovery symlink fixture: Windows WinError1314 privilege prerequisite. Neither aggregate is a full PASS. The seven new module subset is 131 passed / 88 profile skips in each, with no failures. Suites overlap and are not added.

Backend tests used the independent, immutable staged tree `b6deecae76e983c6735262bbb7687a5eab3fb969`, with the c67 frontend. The 30 changed backend/test blobs match the publication index byte-for-byte. Final whole frontend checks used the separate integrated staged tree `d862969a3cbf271e7a988e25526f38261f0b0d82`; all 39 frontend blobs are pinned separately. These are distinct tested inputs, not one fabricated full-suite tree.

Complete frontend: **3167 passed / 8 original skipped / 0 failures**. All 167 new frontend tests and original assertions remain; selected 7-module follow-up 196 passed is a subset. TypeScript, 52-file design-token guard, production frontend build and 7 original Playwright shell/geometry snapshots passed without snapshot updates. Original shell snapshots do not establish new professional Storyboard/Video UX acceptance.

Original metadata checks: **44 passed / 2 failed**, both unchanged Windows symlink privilege fixtures. A separate Linux supplement executed the three unchanged assertions (the two metadata nodes and one discovery node): **3 passed**, with its owned native temporary directory removed. Windows failures remain failures; no system privilege changes were made.

Original generators, unchanged, produced **2233 API operations / 14032 collected nodes**, with all **9151 frozen nodes** retained. Collection counts are not executed tests; gates, generators, baseline bodies and exact skips were not rewritten.

Both previously failing original PostgreSQL Director alias tests passed. The added exact five-second regression measured **2516ms / 2530ms**, COMPLETED job and terminal hook, NEEDS_REVIEW proposal and one synthetic transport call. This is a source/ledger timing proof, not actual model inference. PostgreSQL was a fresh owned loopback database, original sorted migrations, stopped normally and retained for evidence.

Failed evidence is retained privately: the first orchestration attempt (146 pass / 471 setup errors / 321 skipped, missing basetemp parent) was corrected only in the private wrapper; the final File/PG privilege failures remain; the UI source-retirement regression initially had 22 pass / 2 fail and then 24 pass after the fix. All earlier provider/helper failures and prior Phase2 PostgreSQL failures remain. No rerun-until-green, original timeout extension or assertion deletion occurred.

Raw logs, database, environment, local paths and credentials are not published. The allowlisted [source/summary receipt](docs/v2/phase4-storyboard-video-20261014.json) binds the changed blobs and private receipt hashes. Python3.12.9, Node22.14.0, PostgreSQL16.15, FFmpeg8.1.2; pytest8.4.2/fastapi0.142.2/pydantic2.13.5/httpx0.28.1/psycopg3.3.6.

Full hosted milestone CI is checked separately after push. The five baseline c67 runs have 29 failure jobs with runner_id0 and no steps; they are unexecuted infrastructure receipts, not product-test PASS or failure. Historical a40 Cloud cancellation, PG failures and strict summary gates remain unchanged.

Timeline-create currently lacks persisted request idempotency: an unknown write remains separately fenced after Storyboard reread; original Timeline-list inspection cannot prove settlement and does not unlock replay. Phase5 must close this through the original Timeline owner. Source-checking preparation409/invalid200 retires old Storyboard and verified image grants; Timeline recovery errors do not clear another owner.

## Remaining boundaries

Whole Image/Director/Storyboard/Video modules remain PARTIAL; bounded phase source is IMPLEMENTED, and native Windows/GPU/real-model acceptance remains LOCAL_REQUIRED/NOT_RUN. No QingJian work, paid API, downloads, user database/works or credentials were used. Local V2V/reference-video conditioning, unsupported model versions, semantic continuity verification, full professional editing, Control inference and model-output timing/quality proof remain incomplete. Original M4→M9 gates, frozen V1, PoemSeed Local Interop1.0, F00 INTEGRATED+39PARTIAL and independent review BLOCKED remain unchanged. Earlier PostgreSQL/Cloud/File strict-summary failures persist. Hosted baseline jobs with runner_id0 and no steps are infrastructure receipts, not executed product tests.
