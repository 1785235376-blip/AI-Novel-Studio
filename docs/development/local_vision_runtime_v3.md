# Guarded local IMAGE_UNDERSTANDING runtime / Broker seam

Base: `64f35bd1642f475391f700eaa009de905ccf0032` (the separately frozen IMAGE
foundation). This slice adds a real HTTP adapter implementation and guarded
runtime node, but **does not complete Director IMAGE**. All verification uses
injected transport and metadata responses, never live inference.

## Original owners and exact changes

- `app/vision_analysis_runtime.py`: separate V3 `VisionAnalysisRequest`, response,
  protocol and `VisionAnalysisModelNode`; uses original ProviderRegistry,
  ModelRegistry, stable identities and original execution flags. An image pin and
  job ID are passive data, not consent. Host callers must supply a live guard.
- `app/model_runtime.py`: constructs the new node without registering, probing or
  executing anything; adds its protocol to original registry type annotations.
  TEXT/OCR request contracts are unchanged.
- `app/local_ollama_vision.py`: actual `/api/chat` adapter with bounded streaming
  HTTP I/O and explicit Model Center enable/disable synchronization. Runtime
  output is untrusted text with exact source/route/output digests; quality is
  NOT_RUN. There is no new canonical store or queue.
- `app/model_center/discovery.py`: optional internal bounded metadata-client and
  authority-guard injection; default TEXT dispatch remains unchanged.
- `app/model_center/discovery_bridge.py`: two-line helper hook in the original
  explicit-enable bridge. A deterministic domain-separated VISION provider key
  preserves existing TEXT provider/model entries despite their keys lacking a
  modality. Original registry stable identities persist across disable/re-enable.
  Invalid/disabled VISION admission disables only that helper-owned VISION entry.
- `app/experimental/local_vision_broker.py` and `model_broker.py`: private
  `local_vision_only=True` inventory. Valid configured bindings show
  `runtime_available:true` but `available:false`, `execution_available:false`
  and `DIRECTOR_IMAGE_JOB_NOT_INTEGRATED`. This means an admitted adapter, not a
  live server health result. No price, measured performance, GPU fit or inference
  quality is invented. Default/Text/OCR inventories remain unchanged. No reserve
  or dispatch path accepts this new private profile.

## Trusted admission

The adapter accepts only an original host registration that is currently
explicitly enabled/eligible and license-confirmed, with OLLAMA EXTERNAL runtime,
canonical numeric loopback endpoint, positive LOCAL_VERIFIED evidence, exact
model digest/locality/runtime/model-evidence fingerprints, and both verified
TEXT/VISION plus reported completion/vision capabilities. No naming heuristic,
OCR fallback or generic IMAGE_GENERATION capability can qualify.

Observation reads only the original cached registration and registries; it does
not call health, discovery or model metadata endpoints. Explicit runtime
execution invokes the original `check_ollama_dispatch` owner before and after
the inference request. That owner rechecks local model metadata and invalidates
changed registrations. Cached guards recheck registration and original registry
object identity throughout upload, response and result return.

## Transport and source guarantees / limits

- No credentials, authorization headers, environment proxy, redirect following,
  DNS-host endpoints, managed process launch, installation or fallback.
- An explicit default HTTP transport uses retries=0. No POST retry is performed
  after an error, timeout, cancellation or lost response.
- Exact image bytes from the foundation: PNG/JPEG ≤4 MiB and ≤4,194,304 pixels;
  no conversion. Wire base64 is transient and must never be logged/persisted.
- JSON request ≤6 MiB, upload chunks ≤64 KiB, unbuffered raw response reads,
  inference response ≤128,000 bytes and metadata response ≤4 MiB. A received
  chunk is checked before accumulation; HTTPX owns socket read granularity.
  Compressed responses are rejected. Content-length and codec validity are checked.
- One absolute monotonic deadline (≤180 seconds) covers tag/show/tag metadata,
  inference headers/body, and final metadata. AsyncClient network operations are
  cancelled and awaited on expiry or authority loss. A 50ms watchdog checks
  authority even while response headers or a body chunk are withheld; raw chunks
  also check immediately. Socket inactivity timeouts remain 10 seconds, separate
  from the absolute deadline. No threads, detached tasks or retry queues exist.
- Synchronous owner/source checks and decoder/JSON CPU work must return before
  the event loop can cancel: the deadline is not a preemption guarantee for those
  trusted host operations. Caller guards must not probe services or hold source
  leases across I/O. The synchronous runtime entry rejects an active event loop.
  Client cancellation does not prove upstream inference stopped; future Job
  integration must preserve unknown upstream outcomes without automatic replay.
- HTTPX transport/protocol failures become a fixed error code, with raw exception
  context suppressed; endpoint/path/response errors are not exposed.
- Permission/source/cancellation/flags and route changes prevent POST, stop
  subsequent upload/response chunks, and reject output before returning it.
  The caller's source guard must validate the original Asset and permissions.
  The integrated fixture releases source leases before inference and revalidates
  exact pins on callbacks, avoiding a network call while holding project locks.
- Runtime methods are trusted-host Python seams, not a sandbox against hostile
  code in the process. No HTTP body can install a provider or inject a guard or
  transport. Test transport injection is in-process only.

## Still blocked and next integration

No original JobManager prepared IMAGE operation, budget/admission settlement,
IMAGE terminal evidence, durable pending review, adoption or executable Director
API/UI is provided. The old text terminal contract remains unchanged. No
`creative_director_text` request is broadened or cast to image.

Next slice: extend the original Director coordinator and JobManager with a sealed
V3 image prepared request and separately versioned passive job/source binding.
The original Broker needs private image admission/reservation tied to the exact
source owner and host principal; current inventory must remain blocked until
that exists. Terminal accounting and durable evidence must identify IMAGE,
provider/model hashes, source pin, reviewed preview and output digest. Then add
closed observation/advice parsing, pending review and exactly-once human adoption
through the original Director document owner. Keep model interpretation separate
from observed pixels and authored intent. Only after File/PostgreSQL lifecycle
proof should a versioned UI/API be mounted. A separately authorized real local
model run is still required for compatibility and quality evidence.

## Official references and verified versions

Read-only checked on 2026-10-18:

- https://docs.ollama.com/capabilities/vision
- https://docs.ollama.com/api/chat
- https://docs.ollama.com/modelfile
- https://www.python-httpx.org/advanced/transports/
- https://www.python-httpx.org/advanced/timeouts/
- https://www.python-httpx.org/async/
- https://docs.python.org/3.12/library/asyncio-task.html

Ollama documents an unversioned REST contract. No installed Ollama version or live
model was probed. Exact response model-name equality is intentionally strict;
model aliases may require a later trusted normalization contract. HTTPX MockTransport
and streaming responses are used solely for offline transport checks. Python/Pillow
are the existing clean interpreter/decoder; no package changes were made.

## Verification

Runner receipts are retained under `docs/delivery/v2-development/`. New tests
exercise original registry classes and the original Model Center validate/register/
license-confirm/enable/disable flow with injected metadata, plus actual original
Asset source ownership. The source integration fixture is parametrized for File
and PostgreSQL; PostgreSQL is explicitly deselected in this worker. The existing
real-loopback-server probe regression is also explicitly deselected to keep
verification exclusively on injected HTTP transports. No real server/model/API,
PostgreSQL startup, install, credential, commit, push or distribution build occurs.

Pre-fix result retained in `local-vision-runtime-final`: **364 passed, 21 deselected**.
Post-review async verification is recorded in `local-vision-runtime-reviewed-v3`.
Its tests include withheld headers and one-byte slow drips for inference and
metadata, cancellation/expiry cleanup, sanitized transport/protocol errors, and
strict duplicate-key/nonfinite/scalar metadata JSON rejection and injected
parser RecursionError sanitization. Deselections:
19 foundation PostgreSQL cases, 1 new source-to-runtime PostgreSQL case, and 1
existing real-loopback-server test. The remaining new runtime/transport checks
are backend-independent. This is a targeted suite, not full application or
PostgreSQL acceptance. Verified interpreter packages: Python **3.12.14**, HTTPX
**0.28.1**, Pillow **12.3.0**. The final receipt binds exact source hashes.
