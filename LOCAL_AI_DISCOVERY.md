# Local AI Discovery / Model Center

R2 supplement implementation. Discovery is an explicit, read-only, host-local operation. Interactive Windows Local AI Discovery, GPU and real-model generation acceptance is **NOT_RUN**. The separate hosted native Python/PostgreSQL package smoke has passed at its recorded CI revision; that does not validate hardware discovery or real model inference. Synthetic protocol tests are not evidence of real model compatibility.

## Entry and state contract

Open **主控设置 → 模型中心 → Local AI**. Nothing scans on application startup. The first-use panel can be skipped. Click **Scan**, review partial results, **Validate**, **Register**, review the model's license under **Configure**, then explicitly confirm **Enable**. These are separate backend operations:

1. **Detect** enumerates local runtime metadata and configured GGUF roots. It never registers or launches models.
2. **Validate** refreshes runtime/model metadata and records capability evidence. It never generates a sample or executes an executable, including `--version`.
3. **Register** saves a disabled Model Center entry. It neither loads weights nor changes routing.
4. **Enable** requires a separate `confirmed: true` request, current validation, supported execution adapter and explicit license-review acknowledgment. The backend refreshes observations before accepting it.
5. **Launch** occurs only when a real task dispatches to an enabled, managed llama.cpp registration. The managed process is stopped after that task. Other runtimes are **EXTERNAL_RUNTIME** and remain under the user's control.

Disable stops future dispatch through the registration. Remove registration removes only application metadata and route authority, never the executable or any model file. Current task cancellation remains the task's existing control. Revalidating or editing a registration disables it until explicitly enabled again.

After a backend restart, registrations remain visible but are disabled and require fresh validation and Enable. This deliberately avoids trusting stale runtime, node, hardware or file observations. No startup network probe or automatic launch is performed.

## Supported runtimes and bounded probes

| Runtime | Automatic detection | Validation / actual route |
| --- | --- | --- |
| Ollama | `127.0.0.1:11434`, saved loopback addresses; `/api/tags` via the existing Ollama enumerator with an injected bounded reader; installed names, size, update time, digest/details and safe `/api/version` metadata where provided | `/api/show` is metadata-only. Explicit `completion` capability enables the existing text registry bridge. `vision` is recorded separately; embedding-only models are not treated as generators. |
| llama.cpp / GGUF | Saved executable/model paths, configured model directories; passive executable metadata and bounded GGUF header/metadata reads | Version resources on Windows and CUDA-DLL presence are hints. Known GGUF text architecture plus usable external runtime or configured managed executable are required. Managed execution is on demand only. |
| ComfyUI | `127.0.0.1:8188`, saved addresses; `/system_stats` and `/object_info` | Model enumerations, loader nodes, workflow structure and actual generation are separate evidence. Only the existing supported SD checkpoint T2I adapter can currently dispatch. Other families remain safely registered/blocked until an adapter is supplied in code. |
| Automatic1111 | `127.0.0.1:7860`, saved addresses; `/sdapi/v1/sd-models` | Advertised checkpoints establish IMAGE protocol capability. Uses the existing A1111 generation adapter without credentials. |
| OpenAI-compatible local | Saved endpoint; `/v1/models` (or `/models` under `/v1`) | Enumerates models; a models list alone does not establish generation capability. Registration works; Enable stays blocked pending a verified adapter/capability contract. |
| Custom HTTP | Explicit saved loopback endpoint and health path | Health-only discovery and declared modality. Unknown adapters/capabilities remain unverified and disabled. |

Missing services are `NOT_FOUND`, not application failures. Unavailable/timeout/error probes preserve successful results from other services. A scan runs off the request/UI thread; Cancel is honored between bounded probes and directory entries. The current request may finish before cancellation becomes terminal.

Limits: 16 custom runtimes, 16 configured directories, 20 deduplicated runtime probes, 512 models per runtime, 4 MiB per JSON response, 2-second network I/O timeout with a bounded response-read deadline, and a 45-second scan budget checked between probes. Directory enumeration is limited to 3 subdirectory levels, 5,000 entries and 2,000 GGUF files; no full-drive scan. GGUF inspection reads at most 256 KiB and at most 256 metadata fields, never tensors. Counts/strings/arrays are bounded. Root directories, UNC/network paths, symlinks and junctions are rejected or skipped. Results can therefore be partial by design.

## Model families and evidence

Flexible family recognition includes Qwen text versions and future Qwen-prefixed variants, Qwen-Image, FLUX/FLUX.2, Z-Image, MiniMax H3, Wan, LTX, SeedVR2 and RIFE. Names are **declared** classification hints only. They cannot make a candidate READY or create a verified capability.

- SeedVR2 is RESTORATION; RIFE is INTERPOLATION. They are not displayed as ordinary IMAGE just because they use ComfyUI.
- Unrecognized model names remain `UNKNOWN` / capability unverified. Advanced users can supply a declared modality when adding a runtime, but this cannot grant verified capabilities.
- Qwen-Image, FLUX, Z-Image, H3, Wan, LTX, SeedVR2 and RIFE: discovery and registration are implemented; execution remains **PARTIAL** where a compatible workflow adapter is absent. No placeholder generation or guessed workflow is returned.
- Runtime identity, model registration and workflow adapter ID are separate. Future T2V, I2V, start/end-frame or continuation adapters should bind to model capability/family without redefining the model's identity.
- `LOCAL_VIDEO_PIPELINE_V1` and its independent VIDEO → RESTORATION → INTERPOLATION stages remain unchanged.

### MiniMax migration

`minimax-h3-video` is a new, independent VIDEO/ComfyUI catalog identity with license/workflow validation required. The old `minimax-h3` ID is retained only as a **DISABLED legacy audio identity** with a deprecation explanation. Its UUID and old audio history are not rewritten into video history. There is no automatic conversion, launch or license acceptance.

## Status and compatibility

- `DISCOVERED`: observed; not validated or registered automatically
- `NOT_FOUND`: runtime probe unavailable
- `NOT_INSTALLED`: static catalog model without installed evidence
- `VALIDATION_REQUIRED`: capability, runtime or workflow evidence is incomplete
- `RUNTIME_REQUIRED`: explanatory enable blocker when no usable runtime exists
- `LICENSE_REQUIRED`: license review has not been acknowledged
- `INCOMPATIBLE`: invalid GGUF/header or unsupported structural evidence
- `DISABLED`: registered with no routing authority
- `DEGRADED`: explicitly enabled with metadata/protocol validation; actual inference remains unverified
- `READY`: reserved for sufficient independent validation; discovery never emits it from a filename or checkpoint listing

The discovery fields distinguish `declared_capabilities`, `verified_capabilities` (runtime metadata/adapter structure), and `verified` (actual inference). This implementation never sets inference `verified` to true. Comfy evidence separately reports `model_listed`, `model_file_exists` (unknown for remote runtime enumeration), `loader_nodes`, `node_classes`, `workflow_status` and `generation_verified`.

Hardware collection reuses the Host inventory. Platform, architecture, CPU, physical memory and available GPU vendor/name/dedicated memory are local display information. Compatibility uses `POSSIBLY_COMPATIBLE`, `UNSUPPORTED` and `NOT_VERIFIED`; unknown host facts are not fabricated. Low memory never deletes a model. Offload/context/GPU-not-verified warnings remain visible. `COMPATIBLE` is reserved for a real matched hardware validation.

## Configuration and privacy

**Add Local Runtime** accepts name, type, loopback endpoint, upstream model ID, declared modality, health path, credential requirement and lifecycle management. llama.cpp additionally accepts an absolute executable and model path, context size, GPU layers, threads and batch size. Lifecycle management is supported only for llama.cpp. Credential-required custom runtimes can be recorded but remain blocked until an explicit secure credential-binding adapter exists; secrets are never entered into discovery settings.

All discovery API reads and writes require the same trusted host session as Model Center control. Local filenames, paths, hardware and endpoints are returned only through the protected local discovery surface. General catalog responses omit discovered local paths. Discovery never reads prompt history, novel content or arbitrary private documents. No cloud model is used to classify results.

HTTP probes accept numeric loopback or `localhost` canonicalized to numeric loopback. LAN, wildcard, link-local and public addresses, URL credentials, query strings and fragments are rejected. Environment proxies are disabled; redirects are rejected, including redirects to another loopback address. Inference bridges retain a local-only transport and the application's normal source-privacy/task boundaries.

Unknown licenses require the user's explicit review acknowledgment. This is not a statement that commercial usage is permitted, nor a license granted by the application. MiniMax H3, LTX and restricted variants must be checked against the user's actual model license and intended use.

## APIs and extension points

Both `/api/model-center/local-ai` and `/api/v1/model-center/local-ai` expose:

- GET snapshot; POST `/scan`; GET `/scan/{id}`; POST `/scan/{id}/cancel`
- PUT `/settings`; POST `/runtimes`; PUT `/runtimes/{id}`
- POST `/candidates/{id}/validate`; POST `/candidates/{id}/register`
- PUT `/registrations/{id}` for adapter/license review settings
- POST `/registrations/{id}/enable` with explicit confirmation; POST `/disable`; DELETE registration

Implementation: `app/model_center/discovery_types.py`, `discovery_probes.py`, `discovery.py`, `discovery_api.py`, `discovery_bridge.py`; frontend `LocalAiDiscovery` and `localAiDiscoveryApi`. Storage is an atomic, host-local JSON file alongside runtime configuration, using the existing stable identity store and existing Model Center/text/image registries.

To extend: add a bounded metadata probe; keep family declarations distinct from verified capabilities; add a reviewed workflow adapter with explicit node/model requirements; test Detect → Validate → Register → Enable → authorized task dispatch and disable/restart invalidation. Do not infer safe arbitrary custom-node execution from `/object_info` presence. See `LOCAL_AI_WINDOWS_ACCEPTANCE.md` for independent native acceptance.

## R2 safety-review update: Ollama locality and author dispatch

A localhost Ollama server may advertise hosted models. Both `/api/tags` and `/api/show` remote source fields are checked; explicit `remote_host` or `remote_model` blocks LOCAL routing regardless of the model name. Missing/malformed metadata is NOT_VERIFIED. Positive local GGUF metadata, architecture, completion capability and a stable digest are required. Discovery and the old Ollama generation/stream leaves share this check, and repeat it before prompt dispatch. Rescan identity drift, changed source locality, cancellation and later Disable/Remove/Configure invalidate older authority.

Enabled discovery text models use the existing author stream protocol with a buffered final delta; this is not real-time token streaming. External llama aliases and the selected Comfy checkpoint's exact loader field are honored. Legacy Model Center Validate/Diagnostics are also passive and never execute `--version`.

See `docs/delivery/dot-astra-rc-r2/local-ai-safety-review.md` for the review fixes and synthetic HTTP-to-author-Draft evidence. Actual native/model acceptance remains separate.
