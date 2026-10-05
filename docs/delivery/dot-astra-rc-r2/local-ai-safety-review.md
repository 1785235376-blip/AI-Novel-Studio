# Local AI review corrections (R2 follow-up)

Baseline reviewed: `547167e8` (full identity recorded by release lead). This incremental correction is kept on the same R2 branch. It does not claim Windows/GPU or actual model inference verification.

## Corrected boundaries

1. Ollama `/api/tags` and `/api/show` both preserve and inspect `remote_model` / `remote_host`. A localhost endpoint and an innocuous name do not make a hosted model local. Explicit remote declarations block LOCAL routing. Malformed/missing evidence remains NOT_VERIFIED.
2. Local eligibility requires a valid SHA256 digest, positive model size, GGUF details in both metadata surfaces, an architecture entry, explicit capabilities, and matching tag evidence before/after Show. No name-based cloud heuristic grants authority.
3. The discovery adapter checks metadata/digest/source locality again immediately before dispatch. Changed or missing evidence removes registration routing authority, even if persisting the invalidation fails. Rescan invalidates enabled registrations when the observed identity changes.
4. The legacy `OllamaProvider.generate` and `stream` leaves share the same proof, pin the observed model identity, use numeric-loopback/no-proxy/no-redirect transport, and check the forwarded permission/cancellation callback after metadata reads. There is no older brand-based escape route or cloud fallback.
5. After the final authority callback, discovery checks cancellation and enabled identity again. A Disable inside that callback cannot send a prompt. Control epochs make an older validation/Enable lose to a later Disable, Remove or Configure.
6. Text descriptors advertise the stream **protocol** needed by the existing author JobManager. The discovery adapter implements a **buffered single-final-delta stream**, not real-time token streaming. Model output remains a reviewable generation Draft until explicit acceptance.
7. External llama.cpp dispatch uses the configured, verified upstream model alias. Comfy SD workflow validation binds the selected model to the exact `CheckpointLoaderSimple.ckpt_name` enumeration, rather than merely counting available node classes.
8. Old Model Center Validate/Diagnostics now use passive executable version resources too. `--version` is never executed by discovery/validation/diagnostics. Explicit Start/on-demand task launch is unchanged.

## Reproducible tests

- `tests/test_local_ai_discovery_adversarial.py`: retained independent counterexamples and managed-startup cancellation/authority controls, 12 cases
- `tests/test_local_ai_discovery_egress.py`: actual request serialization with synthetic transport capture, metadata locality/missing-evidence/digest drift, zero-prompt denial, CAS controls, legacy leaf guards, and HTTP author workflow
- Existing discovery, provider execution, legacy egress and Model Center regression suites

The HTTP test follows Scan → Validate → Register → license review → explicit Enable → text model picker → project runtime diagnostics → `/generate/continue` → actual JobManager completion and persisted synthetic Draft. It checks the manuscript remains unchanged without acceptance. Both discovery and legacy leaf tests capture serialized requests and assert no `/api/generate` or private prompt body is sent on denial.

Final combined results are in `evidence/local-ai-review-fixes.txt` and `.xml`. Earlier in-flight runs against the pre-correction version fixture are not final evidence.

## Protocol source

The metadata handling follows Ollama's official [Go API types](https://github.com/ollama/ollama/blob/main/api/types.go) and [OpenAPI model summary schema](https://github.com/ollama/ollama/blob/main/docs/openapi.yaml), checked on 2026-10-05. Locality is evidence reported by the explicitly configured local runtime; the application does not sandbox an independently operated daemon or claim to verify a malicious daemon's implementation.

## Remaining verification boundary

Actual Windows version-resource reading, actual Ollama/llama inference, GPU behavior, native installers and non-standard Comfy workflows remain NOT_RUN/PARTIAL as stated in the main acceptance guide. A metadata proof is not a hardware benchmark, successful inference certificate or license grant.

## Final cross-runtime guard sweep

The additional five independent assertions from reviewed commit `19e240d9` are retained in `tests/test_local_ai_discovery_remaining.py`, alongside 19 positive/negative controls:

- Rescan reconciles enabled registrations for A1111, ComfyUI and llama.cpp/GGUF as well as Ollama. Observed checksum/file/header/node/loader changes invalidate route authority and pending controls; unchanged evidence preserves the existing explicit enable.
- Cached/queued text and image adapters refresh the corresponding model/runtime evidence before actual dispatch. Invalid GGUFs fail before managed launch; changed A1111 checkpoints and missing Comfy workflow requirements cannot reach the generation delegate.
- Buffered Ollama results require `done` to be the strict boolean `true`. An incomplete or malformed terminal marker cannot create a completed Draft.
- Missing/malformed counters are unknown, not reported zeros. The discovery response has `usage=None` when no valid count exists; the legacy buffered leaf uses the existing `usage_known=False` contract, and the legacy stream preserves unknown counters. Valid zero/nonzero counts remain reportable.

Final related regression: **338 passed** (`evidence/local-ai-final-guards.txt/.xml`). The independently established 50-case combination is also rerun separately in `evidence/local-ai-preserved-fifty.txt/.xml`; counts overlap and must not be added together. Native/real-model verification remains NOT_RUN.
