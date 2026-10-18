# Claude and Gemini text configuration hints

2026-10-18. Existing Model Center entry; local hints only.

The original Runtime already supports explicitly host-selected native text adapters
through ANTHROPIC_MODEL and GEMINI_MODEL. The new optional panel exposes those exact
model-only startup hints beside the existing Bailian guide. It does not add another
provider registry, fetch a catalog, inspect credentials, probe an API, register/enable
a model or change the user's local/cloud preference. No API key input is offered.

The user explicitly opens the guide, chooses a provider and supplies an account-
available model ID. No vendor model ID, price or current availability is guessed.
Changing provider clears the model field. Empty, quoted, whitespace/control-character,
command-like and dot-path-segment inputs are rejected. Context, scope, transport and
owner replacement retire old hints; inactive, denied and busy contexts do not edit.
The original client constructor validates project shape, and its deferred project-
scope mismatch predicate is applied locally without making a request.

The guide corresponds only to the existing native TEXT adapters, not images, video,
tool use, Vertex/Bedrock or other alternate cloud entry points. Actual configuration,
credential handling, egress/privacy review and cost confirmation stay in original
owners and require separate user operations.

Protocol references checked 2026-10-18:
- [Claude API overview](https://platform.claude.com/docs/en/api/overview): native Messages under api.anthropic.com/v1.
- [Gemini generateContent reference](https://ai.google.dev/api/generate-content): native v1beta model generation endpoint.

These references verify protocol addresses, not account availability, model quality,
prices or this project's end-to-end cloud execution. No third-party API was called.

Evidence: native-text-preset-guide-ui-r3, 49 checks plus TypeScript and Vite build
passed. The earlier r1 caught a missing local scope fence; production code was
corrected. r2 passed behavior tests but exposed an incomplete Scope in the newly
added test fixture; that fixture was completed without changing its refusal assertion.
Both earlier logs are retained. Existing baseline tests are unchanged. Tests use
jsdom, not native/browser visual or real cloud acceptance. Existing large-chunk
warning remains. No app/backend source or mounted API catalog changed.

A separately hashed frontend dist archive is a Vite test build, not a full Studio
installer, backend, Beta or formal Release. No model weights or node_modules are
included. The archive is checked against its original build files before upload.
