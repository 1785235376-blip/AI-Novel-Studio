# Director IMAGE V3 foundation (internal, unmounted)

Base: e66c53138989de1aff021994110c2083900f0aec. This is a partial development
foundation, **not user-ready Director vision and not a completed image-analysis
loop**. No API/UI registration, provider transport, Broker admission, Job,
model inference, pending review, adoption, second workflow engine or canonical
store is added. V1/V2 text contracts and terminal receipts are untouched.

## Added seams

- `director_image_source.py`: exact original formal Asset ID/version/SHA-256,
  original actor/scope/project incarnation, real decode, read-only source capture.
  Uses original `GraphAssetInputs.phase` only for its existing scope → Asset →
  project lease ordering; no graph execution. `existing_owner_only` prevents
  missing project identity provisioning. Private candidates remain unsupported.
- `director_image_preview.py`: compulsory caller authorization guard, exact
  original host registry selection, explicit IMAGE_UNDERSTANDING declaration.
  OCR/TEXT/IMAGE_GENERATION cannot substitute. Declaration is **DECLARED_ONLY**,
  admission is **UNKNOWN**, and execution/adoption are always unavailable.
  This is a point-in-time projection, not consent or a reusable capability.
- `director_vision_wire.py`: pure Ollama REST request/response codec. It is **not
  a runtime adapter** and has no transport, credentials, endpoint, installation,
  automatic registration or model discovery. Wire fixture tests are not image
  understanding or live compatibility evidence.

## Bounds and source handling

One PNG/JPEG, ≤4 MiB compressed, ≤4096 each side, ≤4,194,304 pixels. Pillow
12.3.0 (existing optional comic dependency) performs actual verification and
full decoding in memory. Missing Pillow fails closed. No package is installed.
Animation/multiple frames, non-identity EXIF orientation, malformed/truncated
content, MIME mismatch and unsafe global truncated-image mode are rejected.
There is no re-encoding, thumbnail, orientation transform or temporary image
file. Pillow's existing decompression/metadata safety limits additionally
apply; this is not a hard process-memory or wall-clock isolation guarantee.

The original bounded Asset reader supplies no-follow, regular-file,
size/hash/identity checks and authorization checkpoints. Bytes are transient,
never embedded in preview/receipt/job metadata or copied to a canonical store.
REST encoding creates transient base64 only. A future caller must never log or
persist that wire payload. Prompt ≤16,000 UTF-8 bytes, response envelope ≤128,000
bytes, max output tokens ≤2048. Codec parsing rejects duplicate keys, nonfinite
JSON, wrong models, incomplete/truncated completions, tools and malformed text.
The returned text is untrusted and has no source provenance or quality claim.

## Official wire references and version limits

Verified read-only on 2026-10-18:

- https://docs.ollama.com/capabilities/vision : REST `messages[].images` contains
  base64 image bytes (SDK paths/URLs are deliberately not accepted here).
- https://docs.ollama.com/api/chat : `/api/chat`, `stream:false`, `format:json`,
  `options`, and terminal `model/message/done/done_reason` response fields.

Ollama does not expose a version in these documented REST contracts. No installed
Ollama version was probed. Live model compatibility, exact model aliases,
capability quality and inference are NOT_RUN. Exact response model equality is
a conservative restriction; alias resolution would need trusted host evidence.

## Required next vertical-slice integration (not implemented)

1. Add a host-admitted local vision runtime adapter using original provider/model
   registries and stable identities. Verify exact local route, model version/hash,
   adapter implementation hash, local execution identity, confirmed license and
   explicit IMAGE_UNDERSTANDING capability. Preserve the distinction between
   declarations, trusted admission and measured model quality. Do not infer
   vision support from a filename, OCR capability or successful text request.
2. Extend original Broker admission for an exact local vision route using its
   FRAME_ANALYSIS/IMAGE_UNDERSTANDING concept, retaining known-zero cost,
   local-only, no fallback, no synthetic, current-source and route guards.
   Do not enable the currently blocked Research generic-vision path as a shortcut.
3. Have the original Director proposal/coordinator create a V3 reviewed preview
   bound to one exact Asset and a closed image-observation/advice schema. Keep
   visible observations separate from hypothetical camera/performance choices;
   a still image cannot establish motion, continuity or measured geometry.
4. Introduce an explicitly versioned original JobManager prepared vision request
   and terminal binding. Reuse cancellation, timeout, accounting and private
   publication owners. Never cast IMAGE requests into `creative_director_text`
   or broaden the existing text terminal receipt discriminator.
5. Connect durable image-specific pending review and explicit human adoption to
   the original Director document owner; the first target can be one DIRECTOR
   DRAFT. Preserve source provenance and CAS, exact output/source matching,
   lost-response reconciliation and exactly-once adoption. No automatic media
   job, Graph execution or source edit.
6. Mount Host/session/domain-guarded V3 APIs and UI only after lifecycle proofs.
   Test File and actual PostgreSQL backends and a later separately authorized
   real local model run. No production image-analysis claim before that run.

## Verification scope

See runner receipts under `docs/delivery/v2-development/`. File tests use the
original repositories and original Asset service, plus actual PNG/JPEG decoding.
Registered model objects in tests are no-call fixtures, never fake successful
vision providers. PostgreSQL tests are explicitly deselected; no server starts.
No model/API calls, installs, commits, pushes or distribution builds occurred.

## Frozen foundation result and next implementation slice

Final targeted run: **142 passed, 20 deselected**, two pre-existing warnings.
The new foundation file genuinely uses the existing File/PostgreSQL-parametrized
`rig`: **19 new PostgreSQL cases** were deselected, plus one existing Director
intent PostgreSQL regression. None were run or counted as passing. New pure
codec/decoder cases are backend-independent. Earlier failed runner receipts
are retained as development history; only the final receipt is acceptance
for this foundation. This is not a full backend suite.

Additional parameter reference: https://docs.ollama.com/modelfile documents
`temperature` and `num_predict`. Its default unlimited token count is not used.

The next bounded implementation slice should add a real local runtime adapter
and original Broker candidate/admission support, before Director Job adoption:

- New `app/vision_analysis_runtime.py`: separate typed bounded request/response,
  host-guarded original registry binding, exact source/route digests, cancellation,
  response byte limit and explicit IMAGE_UNDERSTANDING capability. Keep
  `vision_ocr_runtime.py` and `TextGenerationRequest` unchanged.
- New `app/local_ollama_vision.py`: actual guarded `/api/chat` adapter using this
  codec and the established local transport rules (numeric loopback, no DNS,
  no proxy, no redirects, timeout/byte ceilings and per-chunk guards). Inject
  transport for tests; do not execute network/model requests during development.
  `discovery_probes.LocalProbeClient.json` already bounds response bytes, but
  lacks per-chunk cancellation/authorization; do not reuse it blindly as an
  inference transport. Extend the original guarded transport seam narrowly.
- Reuse `discovery_probes.ollama_locality_evidence` and
  `read_ollama_local_metadata` for positive local-weight/hash/remote-field proof.
  Require explicit `vision` in reported capabilities in addition to current
  enable/license/model-identity checks. Metadata proves admission eligibility,
  not inference quality. Registration and metadata probing stay explicit actions.
- Shared hooks requiring root review: `GenerationRuntime` node construction;
  original Model Center discovery validation/enable bridge; original host
  registry registration; `model_broker.py` plus a new
  `experimental/local_vision_broker.py` candidate profile analogous to
  `native_ocr_broker.py`, with no changes to OCR/Text profiles. The current
  discovery bridge registers TEXT and Image-generation adapters only. A dual
  TEXT/VISION model must not overwrite its TEXT model registry entry: choose
  a versioned separate VISION registration key under the original registry and
  preserve canonical provider/model stable identities and disable propagation.
- Continue keeping the Director image request unmounted and execution unavailable
  until original JobManager preparation, capability seals, admission settlement,
  terminal evidence and V3 human review are integrated. A Broker candidate alone
  must not expose an executable Director route.
- Runtime/Broker proof: injected bounded transport captures exact image bytes;
  disabled/unconfigured/missing-license/no-vision/remote-declared adapters produce
  no sends; route/model replacement and cancellation before/during response discard
  output; stale source guard blocks; registration/disable preserves TEXT routes;
  original OCR/Text candidate fixtures remain exact. Real inference stays NOT_RUN.
