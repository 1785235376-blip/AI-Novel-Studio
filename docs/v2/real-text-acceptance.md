# Opt-in real CPU text acceptance

This operational check exercises the existing Model Center discovery/validation,
ModelRouter/ModelBroker, TextModelNode, JobManager, WorkflowRun and AssetLibrary
owners through their mounted HTTP handlers. Model inference uses a real,
explicitly supplied llama.cpp process and GGUF file on numeric loopback. The
HTTP application uses the original injected **test host-session** seam; this is
not a packaged user-login, browser or user-machine acceptance claim.

## Official inputs verified on 2026-10-10

- Runtime: [official llama.cpp b11429 Linux x64 release](https://github.com/ggml-org/llama.cpp/releases/tag/b11429),
  selected by the [v0.6.0 stable release](https://github.com/ggml-org/llama.cpp/releases/tag/v0.6.0).
  The actual executable reports `0.6.0-dev (build 11429, commit d81235049)`.
  Archive: `llama-b11429-bin-ubuntu-x64.tar.gz`, 17,693,462 bytes,
  SHA256 `f6d25dde8f51133143d1453da4fd5f73b145127177612a283bf7995957af3392`.
  [MIT license](https://github.com/ggml-org/llama.cpp/blob/b11429/LICENSE).
- Model: [official Qwen2.5-0.5B-Instruct-GGUF](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/tree/9217f5db79a29953eb74d5343926648285ec7e67),
  pinned revision `9217f5db79a29953eb74d5343926648285ec7e67`, file
  `qwen2.5-0.5b-instruct-q4_k_m.gguf`, 491,400,032 bytes,
  SHA256 `74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db`.
  [Apache-2.0 license](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/blob/9217f5db79a29953eb74d5343926648285ec7e67/LICENSE).

These public inputs require no provider payment, private token or account. The
CPU time, electricity and hardware are not described as cost-free. The existing
Broker receives an explicit, expiring zero **provider-fee** price declaration
for the exact scoped route fingerprint; unknown pricing is never bypassed.
Runtime and weights are not committed or added to normal CI dependencies.
Official [server documentation](https://github.com/ggml-org/llama.cpp/blob/b11429/tools/server/README.md)
describes the existing OpenAI-compatible endpoint used by the original adapter.

## Explicit invocation

After separately checking the executable/model provenance and licenses, provide
absolute paths and a new, unused evidence directory. The script never downloads
or installs anything and refuses a used output directory or occupied port.

```sh
.venv/bin/python scripts/run_v2_real_text_check.py \
  --server /absolute/verified/llama-server \
  --model /absolute/verified/qwen2.5-0.5b-instruct-q4_k_m.gguf \
  --model-sha256 74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db \
  --workspace /absolute/checkout/.runtime/m4c/unique-acceptance \
  --confirm-owned-cpu-runtime
```

The parent supplies a clean environment, isolated HOME/data/config/cache/temp,
File persistence, memory vault, cloud/fallback/Mock/packaged/collaboration/V1
acceptance disabled, and only the four existing text-execution feature flags.
The owned native host uses CPU only, two threads, 2,048 context tokens, one slot,
128-token batches, offline mode and no web UI, agent or UI MCP proxy. CORS is
restricted to its exact loopback origin with credentials disabled. This is a
short-lived isolated test host, not a production server configuration guide.

The check configures, scans, validates, registers, confirms the reviewed local
license, and explicitly enables the exact external runtime using the original
Model Center API. Optional absent runtimes can legitimately leave the complete
scan PARTIAL; the selected runtime must be running with matching model evidence.
It then matches and previews the route, explicitly dispatches with private draft
archival, waits within the unchanged 180-second node deadline, repeats admission
and reads to check idempotency, reviews the draft and verifies asset v1→v2.
Chapters remain empty; no text is applied to manuscript or Canon.

## Evidence and boundaries

The new directory retains:

- Input/executable SHA256, actual binary version/arguments and native logs
- Native model/host metadata and original API transcript
- Exact original Job, actual generated text, DRAFT and APPROVED asset receipts
- Before/after source identity using the existing verification source inventory
- Terminal acceptance status, owned-process shutdown and elapsed timings

The private asset receipt includes exact prompt/hash, parameters, original
route/model metadata fingerprints, request and Workflow/source digests, original
settlement time and actual `execution_mode`. Full GGUF file SHA256 belongs to
the separately measured acceptance evidence; a Model Center metadata fingerprint
is not mislabeled as the model file hash. See [receipt contract](text-execution-receipts.md).

All generated project data and failures are retained. Only the process group
created by this check may be stopped. An absent terminal receipt, abnormal
shutdown or changed source cannot establish final-tree acceptance. Mock contract
tests, real CPU execution, quality assessment and browser/Windows/GPU acceptance
are separate evidence categories. Successful generation does not certify prose
quality, all prompts, other provider families, GPU compatibility or production
performance. API, LM Studio locality and Image/Video execution remain bounded by
their existing fail-closed/reserved contracts.
