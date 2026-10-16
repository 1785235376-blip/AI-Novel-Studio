# V2 Windows Acceptance Plan

Prepared in the cloud on 2026-10-09. **Execution status: NOT_RUN / LOCAL_REQUIRED. M12 authorization: USER_APPROVAL_REQUIRED.** This plan does not authorize connecting to or operating the user's computer, installing software, launching models, consuming GPU resources, uploading data or using paid API credits.

Development baseline: `4350a61fb9f61acccb845fef96b24b9b1275bbd3`, [Draft PR 47](https://github.com/1785235376-blip/AI-Novel-Studio/pull/47). M1 is in progress and M2–M11 are not complete. There is **no final M11/M12 V2 candidate package identified by this document**. Package hashes and the approved execution scope must be filled from actual delivery before any native test begins.

## 1. What native CI does and does not prove

At the historical `4350a61` source tree, [PR Cloud 37907528214](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37907528214) and the corresponding [push run](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37907521986) completed their bounded Windows jobs. This covered Host compile/native/packaging **59 tests**, **3 V2 environment fixtures**, an unsigned internal package and real embedded Python **3.12.9** / PostgreSQL **16.15** UTF-8/dump-restore smoke. Windows pipe reference tests in the Interop workflow are **MOCK_ONLY**. Push Cloud overall remained cancelled for backend capacity; no all-CI-green claim follows.

| Evidence level | May establish | Cannot substitute for |
| --- | --- | --- |
| Cloud Linux unit/API/mock | Schema, permission, lifecycle and synthetic/real-loopback contracts at exact source | Windows host behavior, GPU, installed user runtime or model quality. |
| Hosted Windows native fixture/package | Compile, packaged runtime and bounded native contracts on runner | User installation/upgrade, interactive WebView, IME, DPI, personal model discovery. |
| User-approved Windows desktop | Actual tested installation, hardware and interaction cases | Untested adapters/model sizes, different package hashes or commercial-release approval. |
| Actual model inference | Specific model/runtime/workflow input→output and resources | General model-family compatibility, aesthetic quality, licenses or unrelated modalities. |

Existing implementation references: `.github/workflows/cloud-ci.yml`, `.github/workflows/local-interop.yml`, `scripts/package_windows_acceptance.ps1`, `scripts/prepare_windows_base.py`, `scripts/verify_windows_base.py`; [Local AI Windows checklist](LOCAL_AI_WINDOWS_ACCEPTANCE.md), [Local AI integration](AI_NOVEL_STUDIO_V2_LOCAL_MODEL_INTEGRATION.md), [UI/UX gates](AI_NOVEL_STUDIO_V2_UI_UX_REVIEW.md). The older engineering installation note is not a requirement to install every model/runtime for V2 manual use.

## 2. Cloud preparation gate before asking to execute M12

The engineering owner must prepare and verify:

- Exact candidate commit and source tree, package SHA256 and per-file manifest, dependency/runtime versions and licenses, reproducible build receipt and known limitations. If unsigned, say so. A blocked signature/security warning must be handed to the user; do not bypass it.
- Candidate-specific launch, uninstall, upgrade and rollback instructions matching actual packaging. Do not reuse instructions for a different RC1 or silently replace its frozen package.
- Source-bound feature matrix, milestone reports, complete applicable File/real PostgreSQL/frontend/browser/native/Interop results and current CI terminal states. Preserve historical `PARTIAL_CI_CAPACITY` and independent-review `BLOCKED`.
- Small synthetic non-private fixtures: text, images, two short distinct videos, two distinct audio clips, subtitle file, supported 3D sample and expected digests/media metadata. Include redistributable rights/licenses, not user materials or model weights.
- Explicit installed-model/runtime dependency inventory and unsupported capabilities. Models are referenced in a manifest and are not bundled or copied into the candidate.
- Previewable cleanup manifest/script that touches only the test-owned paths it created, rejects roots/symlinks/junction escapes and preserves logs first. **No new cleanup script is delivered or executed by this documentation task.**
- Safe owned data/cache/export directories, backup/rollback plan and bounded disk-space budget; no default mutation of existing V1 projects or third-party model directories.
- A clear approval request naming the machine, package/hash, test scope, paths, runtimes/model launch and any installation or network action. Downloads, credentials, fees or extra permissions are separately disclosed where required. No blanket approval is inferred from the roadmap.

If an actual feature is still missing, mark its acceptance cases BLOCKED by implementation. Do not generate fake media or treat a mocked scenario as its native replacement. Other approved independent cases may continue.

## 3. Candidate and environment record

Complete this locally after approval; publish only a redacted summary.

| Field | Current value |
| --- | --- |
| M12 approval and bounded scope | **NOT GIVEN** |
| Final candidate commit/tree | **UNKNOWN; candidate not selected** |
| Package name/SHA256/per-file manifest | **UNKNOWN; not a new package delivery** |
| Windows edition/build/architecture; DesktopHost/WebView2 versions | **NOT_RUN** |
| GPU/driver and measured VRAM; RAM | **NOT_RUN** |
| Primary target | Windows 11, RTX 5080 16GB, 64GB RAM; target only, not measured facts |
| Other resource targets | 8GB and 12GB VRAM; identify physical test vs simulation explicitly |
| Runtime/model/quantization/component/workflow versions and licenses | **NOT_RUN** |
| Owned test project/cache/export root and external read-only model roots | Select locally with user approval; do not publish personal absolute paths |
| Feature flags and network/privacy mode | Record exact values; local/manual first; no personal paid API by default |
| Start/end UTC and tester | **NOT_RUN** |

Before launch, compare the package's actual SHA256 with its supplied receipt (for example, PowerShell `Get-FileHash -Algorithm SHA256` on the selected file). Hash mismatch blocks execution. A new build or modified source requires a new identity and affected-case rerun; copying an old PASS is not permitted.

## 4. Execution sequence after explicit approval

Use a synthetic profile with the existing project's real storage/backend flow. Keep real user projects and weights outside the writable test boundary. First verify no-model/manual operation; then test one selected runtime/model at a time. Multi-runtime/GPU concurrency is a separate resource case, not the initial default.

### A. Installation, baseline compatibility and manual entry

| ID | Procedure | Required observation/evidence |
| --- | --- | --- |
| W-A01 | Install/extract and launch the approved candidate using its actual documented path; start with no model runtime | Host/window opens; no model download/load/scan or mandatory AI setup; no unexpected network request. Capture package identity and startup errors. |
| W-A02 | Select supported independent project/assets/cache/export locations in an owned test profile | Paths remain separate; usable free space displayed where implemented; install directory does not force media/model placement. Missing Storage Manager behavior is a gap, not PASS. |
| W-A03 | Create blank project, skip intent, import external image, save/reopen, independently export | Exact asset bytes/digest/version/provenance survive; no novel chapter, Director, graph or model required. |
| W-A04 | Change/clear/multiply intent/preset and visit other modules | Assets/permissions remain unchanged; available modules stay reachable; no automatic execution. |
| W-A05 | Open a backed-up synthetic V1-compatible project with V2 off and in `V1_ACCEPTANCE_MODE=true` | Existing novel manuscript/version/CAS/export behavior and shell text unchanged; disabled V2 routes fail closed. |
| W-A06 | Upgrade a disposable previous-version fixture using supported path, then execute documented rollback/uninstall | Fixture data retained or recoverable by documented backup; external models untouched; actual migration/rollback receipts retained. No live project migration. |

### B. Model discovery, registration and runtime truth

Use the detailed [Local AI checklist](LOCAL_AI_WINDOWS_ACCEPTANCE.md) together with the current [integration contract](AI_NOVEL_STUDIO_V2_LOCAL_MODEL_INTEGRATION.md). Run only the approved runtime/model cases.

| ID | Procedure | Required observation/evidence |
| --- | --- | --- |
| W-B01 | Open Model Center, skip setup, read environment, then explicitly Scan | No startup/GET scan; hardware matches Windows observations or stays unverified; bounded missing services do not break editing. |
| W-B02 | Scan approved standard/cache roots and a synthetic model directory; include malformed headers and out-of-scope link fixtures | No whole-drive/LAN scan, link traversal or executable/model-code load. Partial results and cancellation are truthful. |
| W-B03 | Reuse an existing authorized default or trusted configured non-default loopback service | Normal path avoids port entry when configuration suffices; metadata reports real listed models; no duplicate weight copy/download. Unknown discovery remains explained. |
| W-B04 | Detect → Validate → Register → review license → Enable with a supported model | Distinct states; disabled until confirmed; validate/enable do not generate or preload; no claim that file/header equals inference. |
| W-B05 | Dispatch one actual local task; record selected route/model/input/output and process/network observations | Real inference occurs only now; exact runtime/weights used, output valid, result remains a reviewable candidate. Record elapsed time and peak memory. |
| W-B06 | Disable/remove/change/restart runtime or backend; repeat stale task action | Routing authority invalidated; removed registration does not remove files; restart needs revalidation/Enable; no automatic job replay. |
| W-B07 | Present unsupported Comfy family/components, hosted Ollama model, wrong runtime binding and unavailable API budget | Precise blocker before data/fees; no guessed adapter, silent cloud fallback or custom-node install. |

Scan paths, raw hardware identifiers and model license copies stay local unless sharing is separately approved. A system CUDA DLL is a component observation; W-B05 is needed for actual compute evidence. API tests remain NOT_RUN unless a specific provider, outgoing data and spending limit are separately authorized.

### C. Independent Studios and optional connections

Execute only implemented capabilities, and record missing prerequisites by case rather than declaring the whole Studio complete.

| ID | Procedure | Required result |
| --- | --- | --- |
| W-C01 Text only | Manual novel and independent screenplay edit/save/export; optional approved novel-adaptation proposal | No image/video/model requirement for manual work; proposal review preserves original chapters and source versions. |
| W-C02 Image only | External image import/manual supported edit/export; approved real T2I or I2I/edit path separately | Real decoded/encoded output and versioned source; supported workflow requirements explicit. |
| W-C03 External image → video | Begin directly in Video with user-selected synthetic image, choose supported I2V task, review/export video | No upstream generated-image record, chapter, screenplay or Director required; real video metadata and receipt. |
| W-C04 Audio only | External audio listen/trim/export; separately synthesize a short authorized text using supported TTS | No Text project dependency; actual audible content, measured duration/rate/channels and rights metadata. |
| W-C05 External video → Editing | Import media without AI and perform the complete NLE case below | No generation/Director/Storyboard prerequisite; saved timeline and encoded film are real. |
| W-C06 Optional graph/Director | Save/reopen graph; test illegal port, cycle, partial rerun, source-version change, remove optional Director | Invalid execution prevented; only affected descendants stale; completed assets retained; unrelated valid nodes run independently. |
| W-C07 Gray-model references | Separately try static gray-model image, Previs clip and supported real 3D/camera asset | Inputs remain distinct; only supported conditioning offered; no false precise motion/camera reconstruction guarantee. |
| W-C08 Research/Delivery | Organize manual sources, link licensed assets, export supported assets/package; reopen isolated package | Citations/relationships/digests retained; no private data/weights silently copied; absent models do not block reading completed media. |

### D. Mandatory real NLE acceptance, after M9 implementation

W-D01 requires **at least two video tracks, two audio tracks and a subtitle track** using distinct synthetic fixtures. Import, set in/out points, split and move clips, exercise overlap/insert where implemented, mute/adjust audio, edit timed captions, preview at multiple playhead positions, undo/redo and save. Export a real media file and inspect codec, resolution, frame rate, duration, audio streams and subtitle treatment. Play the result to check sync and intended cuts. Close/reopen the project and compare track/clip/source/version/timebase data and visible edit state.

W-D02 makes one media source unavailable, exercises proxy/cache policy, cancels a render and interrupts/restarts only test-owned processes. Offline media is labelled, confirmed assets persist, render outcomes remain truthful and temporary output is not promoted as complete. Record sync tolerance and measured deviation based on the final timebase test design; do not invent a PASS threshold after observing the result.

`ProductionTimeline.tsx` shot-plan cards do not satisfy either case. Current status: **BLOCKED by pending M9 / LOCAL_REQUIRED** for native behavior, not executed.

### E. UI, input, windowing and Tutor

- W-E01: inspect 1366×768, 1440×900, 1920×1080 and 2560×1440 with long labels; check geometry, clipping, scrolling and actual click targets. Record browser versus native window dimensions and display scaling.
- W-E02: test Windows 100%/125%/150%/200% scaling where available, Chinese IME composition, keyboard-only forms/canvas/timeline, visible focus, Escape/restore focus and reduced motion. A cloud browser screenshot does not establish these native results.
- W-E03: with QingJian absent/disconnected, all ordinary creation and saved assets remain usable. Once an approved compatible peer exists, validate `poemseed.creative.studio` / `poemseed.tutor.desktop`, PoemSeed Local Interop 1.0 HELLO/negotiation/session and bounded local transport. A reference peer remains MOCK_ONLY, never “production dual-app accepted.”
- W-E04: preview approved minimal context, connect/deny/revoke/restart, test stale session/version mismatch and absent permissions. No default manuscript/media/path/key/raw-log sharing; no project-memory write, mouse/keyboard control, paid job, delete or edit merely from Tutor advice.
- W-E05: after the approved Tutor Slot exists, dock/collapse/float/close and move between displays. No obscured playhead/export/critical canvas actions, focus theft or unavoidable popup. Failed revocation remains visibly unknown until confirmed; merely closing a panel is not proof sharing stopped.

### F. Resources, failure, recovery and clean exit

- W-F01: measure actual 16GB target VRAM/RAM and chosen model workflow under one job, then approved queue contention. Insufficient VRAM/disk must yield understandable block/low-resource options without automatic API spend. Do not assume every model fits or simultaneous models can remain loaded.
- W-F02: record 8GB/12GB tests as **physical hardware**, **bounded simulation** or **NOT_RUN**. Simulation proves rejection/resource logic only, not real performance on those GPUs.
- W-F03: create stale CAS, permission revocation, source update, missing model, runtime disconnect, low owned-disk quota, cancellation and backend restart. Preserve drafts/confirmed outputs as contracted; unknown upstream/billing must stay unresolved until reconciled.
- W-F04: use synthetic data to delete/recreate the same-title project; verify old assets never leak into its new incarnation. Cross-project/branch/actor reads and late callbacks fail closed.
- W-F05: quit normally and after cancelled work. Test-owned managed processes release; existing external services/models are not terminated or removed unless that exact action was approved. Check test data and model digests/reference inventories before cleanup.

## 5. Failure evidence and privacy

For every case record `PASS / PARTIAL / FAIL / BLOCKED / NOT_RUN / LOCAL_REQUIRED`, its execution level and exact package/source/runtime/model identity. Store locally: start/end times, minimal reproduction, expected/actual behavior, error code, relevant bounded sanitized logs, screenshot/video when useful, Job/asset/version/digest IDs, measured resources and export media inspection. Evidence may include private paths or windows: inspect/redact before publishing anything.

Do not copy credentials, model weights, personal prompts/manuscripts, real file paths, raw machine identifiers or unrelated logs into GitHub. A public receipt can use synthetic path aliases and content hashes. Separate a test failure, missing implementation, unavailable environment and denied authorization. Retain first failures and subsequent fixes with different identities; no silent overwriting.

## 6. Cleanup, exit criteria and release boundary

1. Stop only processes owned by the approved test session. Confirm whether outstanding jobs are terminal; uncertain external tasks remain explicitly unresolved, not automatically retried.
2. Preserve failure/success evidence before cleanup. Show the exact owned files/directories and retained outputs, check no symlink/junction points outside that boundary and obtain any required deletion approval.
3. Clean only created test cache/temp/resources listed in the owned manifest. Never recursively clean a drive, profile, arbitrary model root, ComfyUI/Ollama installation, RC1 package or pre-existing project. If ownership is uncertain, leave it and report.
4. Verify external user assets/weights are unchanged and record residual test artifacts. Cleanup failure does not justify broader deletion.
5. Issue a candidate-bound acceptance report with per-case outcomes, unresolved gaps, all deferred checks and recommended next action. If the package changed, rerun the affected cases under its new hash.

M12 can close only after the user-authorized scope is actually executed, results are accepted at their real evidence level and remaining limits are explicit. **Even a completed M12 does not authorize merging, tagging, production deployment or Release.** Those actions require separate user approval. Until then, this remains a prepared plan and all user-desktop execution remains **NOT_RUN / LOCAL_REQUIRED**.
