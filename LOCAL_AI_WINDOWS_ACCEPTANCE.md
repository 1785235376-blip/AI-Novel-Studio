# Local AI Discovery — Windows acceptance

Status: **NOT_RUN**. This checklist is for the user's actual Windows desktop. Linux synthetic adapters and CI browser tests do not replace these checks. Use a backed-up/synthetic workspace; do not upload private prompts, model paths, hardware inventories or credentials to cloud diagnostics.

## 1. Startup, session and hardware

1. Start the R2 candidate from its documented Windows host flow. Record exact Git commit, Windows version/architecture, application version and runtime versions locally.
2. Open 主控设置 → 模型中心 → Local AI. Confirm no model process starts and no scan runs until Scan is clicked. Verify Skip is available.
3. Click Scan. Check CPU, physical memory, architecture and GPU inventory against Windows system information. Unsupported/unavailable facts must show unverified, not invented values.
4. Without a trusted host session, both `/api` and `/api/v1` Local AI reads and writes must return 401 and no local paths/hardware.

## 2. Partial discovery, cancellation and boundaries

1. Stop Ollama, ComfyUI and A1111. Scan must finish with NOT_FOUND/partial results without an application error.
2. Start one runtime. Rescan should retain other NOT_FOUND outcomes and list only its actual installed models.
3. Cancel while a probe is waiting. The UI remains responsive; partial results persist. A late probe cannot replace a newer scan.
4. Configure a small synthetic model directory. Include one nested GGUF, one invalid header, a text file, a symlink/junction outside the root, and a fourth-level nested GGUF. Confirm only bounded allowed GGUF entries are read; no text contents or linked destinations are scanned.
5. Try a drive root, UNC path, public/LAN endpoint, metadata address, URL credentials, redirected endpoint and oversized response. Each must fail closed; no cloud request or proxy forwarding occurs.

## 3. Ollama text lifecycle

1. With Ollama already running, install/use a model you are licensed to test. Scan lists actual name, size/update metadata where provided.
2. Verify new models are not automatically registered or enabled and no generation request is sent during Scan/Validate.
3. Validate queries only metadata. A runtime that reports `completion` may receive verified TEXT metadata capability; embedding-only/unknown models must not gain TEXT generation authority.
4. Register. Confirm the registration is disabled and unavailable in novel task model selection.
5. Configure: explicitly acknowledge your license review. Enable requires a separate confirmation. It does not preload the model.
6. Select the enabled model in a synthetic novel writing task. Confirm a real local request is made; generated text stays in the existing Draft/Diff/Accept path.
7. Disable. Subsequent generation with that saved route must fail as disabled. Remove registration must leave the installed Ollama model untouched.
8. Restart the backend. Registration persists but needs fresh validation and Enable. No model is automatically loaded.

## 4. llama.cpp / GGUF

1. Add the executable and GGUF paths; set context, GPU layers, threads and batch size. Validate observes file/header metadata; it must not invoke the executable even with `--version`.
2. On Windows, a valid PE version resource may be shown. Absence is NOT_VERIFIED. A CUDA DLL is only a component hint, not proof CUDA works.
3. For a managed runtime, enable after structural/license review, then dispatch one text task. Confirm exactly the selected model process starts on demand, uses loopback, and releases at task completion. Simultaneous managed runtime loading must be rejected.
4. Verify invalid/truncated GGUF, missing binary, wrong external runtime/model association and changed model path invalidate availability.
5. Test CPU offload and realistic context limits on your GPU independently. Record actual inference success/failure; do not promote metadata validation into a hardware benchmark.

## 5. ComfyUI and model families

1. Start your existing ComfyUI environment. Scan must read both system stats and object info, not just test whether port 8188 opens.
2. Confirm installed supported family names appear in distinct groups: Qwen-Image/FLUX/Z-Image IMAGE; MiniMax H3/Wan/LTX VIDEO; SeedVR2 RESTORATION; RIFE INTERPOLATION.
3. File presence, model enumeration, loader-node presence, workflow structure and actual generation must remain separate UI facts. Missing workflow adapters must block Enable.
4. For a supported SD/SDXL checkpoint and complete standard T2I nodes, test Register → license acknowledgment → Enable → explicit image task. Verify only that task sends `/prompt`; Scan/Validate/Enable do not.
5. Missing custom workflows for Qwen-Image/FLUX/Z-Image/H3/Wan/LTX/SeedVR2/RIFE are **PARTIAL**, not an automatic promise of runnable generation. Keep actual user workflows external until a reviewed adapter exists.
6. Verify old minimax-h3 audio history still refers to its old audio identity, which is disabled. New minimax-h3-video must be VIDEO/ComfyUI, with independent identity and license review. No audio history is relabeled video.

## 6. A1111, custom runtime and UI

1. With A1111 API enabled locally, verify actual `/sdapi/v1/sd-models` checkpoints appear and require no credential.
2. Complete explicit enable, create a synthetic image task, verify selected upstream checkpoint and returned actual image. No mock success is accepted.
3. Add local OpenAI-compatible and Custom HTTP definitions. A healthy endpoint or model-list response alone must not grant unknown capabilities. Credential-required entries remain blocked without a secure supported binding.
4. At 1366×768, 1440×900 and 1920×1080, check shell preservation, keyboard controls, groups, forms, errors, scrolling and registration-only deletion wording. Close/reopen settings during pending requests; no stale response should restore dismissed UI state.

## Acceptance record

For each section record PASS / FAIL / NOT_RUN, exact commit, runtime/model version, local evidence location and observed failures. Keep model-license review separate from technical validation. Do not publish private host paths, raw machine identifiers, prompt history or credentials in the public repository. Until these native checks run, Windows/GPU/real-model status remains NOT_RUN.
