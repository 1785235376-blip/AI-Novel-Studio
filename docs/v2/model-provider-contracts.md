# M4-B model provider contracts

This is a bounded contract slice over the existing execution owners. It does not
establish complete M4-B acceptance. Real model inference, literary quality,
Windows/GPU behavior and independent audit remain **NOT_RUN / BLOCKED as
applicable**. Protocol mock tests are not real-model evidence.

## Ownership and concrete interfaces

`app/model_provider_contracts.py` defines `ModelProvider`, whose four methods are
`capabilities()`, `availability()`, `execute(ProviderExecutionRequest)` and
`result(ProviderExecutionRequest, TextGenerationResponse)`. The static facades
are `LocalOllamaProvider`, `LMStudioProvider`, `ComfyUIProvider`,
`LlamaCppProvider`, and `ReservedAPIProvider`. The existing
`app/model_execution.py::APIProvider` inherits the reserved contract while
retaining its old fail-closed `validate`/`stream_text` methods.

No facade is a registry, queue, scheduler, state store or transport owner.
LocalOllama and llama.cpp require exact original host registrations,
`LOCAL_VERIFIED` model evidence and external runtime management. They delegate
through the original `LocalModelInvocation`, `TextModelNode` and
`LocalTextAdapter` to the existing `LocalProbeClient`.

The new facade also requires the original request's preparation and dispatch
guards, job ID and cancellation event. Its transient request digest is checked
before delegation and in both original guarded phases. Caller-owned mutable
context cannot silently change the request after the envelope is created.
Original JobManager/Broker/WorkflowRun still own consent, source binding,
admission, accounting, cancellation, result publication and human review.

The five-family `provider_catalog(runtime=None)` is advisory and can be read
without a running model. It reads original descriptors and enabled registration
facts only. It does not health-check, scan, read credentials, initialize unrelated
modalities, start a process, load weights or contact a server. A registered
adapter may have `adapter_available: true`; catalog `execution_available` stays
false because a family record is never a reviewed invocation. Missing families
remain visible with explicit blockers rather than invented available routes.

## Capability and availability schema

Every family record has this shape (LM Studio example):

```json
{
  "family": "LM_STUDIO",
  "capability": {
    "family": "LM_STUDIO",
    "advertised": ["TEXT_GENERATION"],
    "verified": [],
    "verification": "NOT_VERIFIED",
    "inference_verification": "NOT_RUN"
  },
  "availability": {
    "family": "LM_STUDIO",
    "adapter_available": false,
    "status": "RESERVED",
    "reasons": ["LMSTUDIO_LOCALITY_UNVERIFIED"],
    "execution_available": false,
    "execution_authority": "ORIGINAL_REVIEWED_REQUEST_REQUIRED"
  },
  "registered_routes": [],
  "advisory_only": true,
  "automatic_fallback": false,
  "real_model_verification": "NOT_RUN"
}
```

Advertised modalities describe the protocol family, not a discovered executable
model. ComfyUI advertises image/video interfaces; this slice does not authorize
its graph execution. API advertises text/image/video but remains reserved.
Registered Ollama/llama.cpp text verification is
`REGISTERED_ADAPTER_CONTRACT_ONLY`, not inference or quality validation.

## TaskRequirement and matching

`TaskRequirement` accepts only the fields below. Unknown fields, URLs,
credentials, execution results and unbounded/noninteger memory limits are
rejected. `local_only` must be the literal boolean `true`.

```json
{
  "task_type": "TEXT_GENERATION",
  "preferred_route": null,
  "min_host_ram_mib": null,
  "min_host_vram_mib": 8192,
  "local_only": true,
  "api_available": false,
  "allow_synthetic": false
}
```

`task_type` is `TEXT_GENERATION`, `IMAGE_GENERATION` or `VIDEO_GENERATION`.
`preferred_route`, when supplied, is the exact original broker's 64-character
route digest; a different route is ineligible. There is no independent ranking
or fallback policy. Synthetic use remains explicitly opt-in.

`match_task_requirement(requirement, route, hardware=None)` consumes full
host-owned original broker candidate facts and the original
`ModelBrokerService.hardware_capacity()` observation. It does not collect
hardware itself. The parent router must still run its original route guard,
license/known-zero-price checks and exact reviewed-request flow. An advisory
eligible result is not permission to execute.

For required RAM/VRAM, unavailable, malformed or wrong-provenance hardware is
`UNKNOWN` and blocks eligibility; a smaller total is `INSUFFICIENT`. A passing
total is only `TOTAL_CAPACITY_ONLY`, never currently free memory, model fit,
GPU allocation or a successful inference guarantee. `gpu_fit_verified` is
always false. No hardware requirement produces `NOT_REQUESTED`.

`api_available` is an advisory supplied fact, never credential inspection or
cloud permission. Both true and false leave remote execution blocked. The
result carries `execution_authority: false` and `automatic_fallback: false`.
Image/video matching remains blocked with
`GRAPH_IMAGE_EXECUTION_NOT_ENABLED` / `GRAPH_VIDEO_EXECUTION_NOT_ENABLED` in
this graph-local-text slice, even if a model advertises those modalities.

## Result schema and evidence limits

`ProviderExecutionRequest` wraps an original host `TextGenerationRequest` in
memory. It captures the adapter-facing request digest and creation timestamp.
It is not a public dispatch payload, persisted replay record or HTTP authority.

`normalize_text_result` and facade `result` accept an original
`TextGenerationResponse` only. They reject changed request data, wrong
provider/model, incomplete termination, empty/oversized text, invalid time or
unsupported execution labels. The normalized `model-provider-result/1` contains:

- `task_type`, `provider_id`, `model_id`
- Exact original `parameters` (`temperature`, `max_output_tokens`, `stop_sequences`)
- `request_created_at`, `result_recorded_at` and original `latency_ms`
- SHA-256 `request_digest` and `output_digest`, plus `text`
- `execution_mode` (`real` or `mock_standin`), `proposal_only: true`
- `quality_verification: "NOT_RUN"`
- `acceptance_authority: "ORIGINAL_JOB_RECEIPT_AND_HUMAN_REVIEW"`

The result timestamp is when this representation was recorded, not an invented
inference start/finish observation. The `real` response label identifies an
adapter's protocol mode; mocked transports can exercise that mode in tests.
Neither that label nor successful decoding proves real inference, job
settlement, acceptance, asset publication or quality. There is no API to submit
a provider result as graph execution authority.

## LM Studio protocol support and exact blocker

`LMStudioProvider.wire_request` and `wire_response` implement pure, bounded
OpenAI-compatible text payload/response contracts. The encoder requires an
exact loaded-instance identifier, ordinary reviewed system/user text, at most
2,048 output tokens and the graph's 32,000-byte prompt bound. It emits a
nonstreaming request with no tools, schema, credential, loading or model
management operation. The strict decoder requires one completed assistant
response for that exact instance; it rejects tools/refusals, truncated or
malformed output, wrong model IDs, invalid usage and more than 32,000 output
bytes. Missing usage remains unknown.

These codecs perform no I/O. `execute` uses the same original guarded invocation
path as other text facades, but **currently fails
`LMSTUDIO_LOCALITY_UNVERIFIED` before any transport call**. No discovery
allowlist or enablement rule was widened. A decoder unit test must not be
reported as an executable registered LM Studio route.

Official documentation checked on 2026-10-10:

- [Native model listing](https://lmstudio.ai/docs/developer/rest/list) documents
  `/api/v1/models` and loaded-instance metadata. Its documented fields do not
  establish the serving device's locality or bind a model-file digest.
- [LM Link](https://lmstudio.ai/docs/developer/core/lmlink) explicitly permits
  localhost API calls to use remote devices, including preferred-device
  selection when the same model exists on multiple devices.
- [OpenAI-compatible model listing](https://lmstudio.ai/docs/developer/openai-compat/models)
  may expose unloaded downloaded models under just-in-time loading.
- [Chat completions](https://lmstudio.ai/docs/developer/openai-compat/chat-completions)
  documents the OpenAI-compatible text request surface.

Therefore a loopback endpoint, listed name, loaded-instance record or a local
GGUF with matching size is insufficient proof that a prompt will remain on this
host. Native metadata plus a matching file cannot safely grant execution here.
A future extension needs an original-owner, revalidated serving-device and
artifact binding, and a no-JIT/no-remote dispatch guarantee. This task did not
invent that evidence, add an attestation checkbox or use user-supplied JSON as
positive authority.

## Verification

New tests: `tests/test_v2_model_provider_contracts.py`. They cover all five
family states, existing Ollama/llama.cpp adapter/node delegation, exact request
and final-hop guards, protocol changes, remote/managed/disabled routes,
RAM/VRAM unknown/insufficient/total-only matching, preferred routes, synthetic
permission, normalized result binding and LM Studio codec/locality failures.

The implementation also runs the unchanged
`tests/test_v2_model_execution.py` regression suite. All wire payloads and
responses are local mocks; no provider credentials, paid API, process launch,
installation, PostgreSQL lifecycle or real model inference is used.

### Focused verification receipt

- Official documentation read: 2026-10-10 10:31–10:32 UTC. The exact native
  listing, LM Link, model-listing and chat-completion links are above.
- No LM Studio SDK is used or installed. The existing local transport owner is
  `LocalProbeClient` using **httpx 0.28.1**.
- Actual verification interpreter: **Python 3.12.14**, Clang 22.1.3;
  **Pydantic 2.13.5**, **pytest 8.4.2**.
- Focused final run at 2026-10-10 10:39 UTC: **118 passed**, comprising **76 new
  provider-contract cases** and **42 unchanged graph model-execution cases**.
  Timestamp validation, JSON serialization and provider/model binding are
  included. `git diff --check` passed.
- Initial development attempt without a writable XDG application-data root
  stopped at shared test-fixture initialization (`OSError: read-only file
  system`), before any test ran. Setting a repository-local XDG test root
  resolved the setup problem. This was not a product failure.
- These are focused File/backend-neutral tests, not full-suite, PostgreSQL,
  hosted CI or independent-audit acceptance. Real model inference remains
  **NOT_RUN**.

Reproduction from the checkout:

```sh
XDG_DATA_HOME="$PWD/.runtime/m4b/provider-contracts-xdg" \
NOVEL_DATA_PATH="$PWD/.runtime/m4b/provider-contracts-data" \
STORAGE_BACKEND=file CREDENTIAL_VAULT_BACKEND=memory \
.venv/bin/python -m pytest -q \
  tests/test_v2_model_provider_contracts.py \
  tests/test_v2_model_execution.py --disable-warnings
```
