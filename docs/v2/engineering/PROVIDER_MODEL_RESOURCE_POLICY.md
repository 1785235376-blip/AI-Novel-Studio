# Provider admission, model capability and local resource policy

This page records the server-owned rules that keep model/provider selection evidence-based,
bounded and recoverable. It is an engineering contract, not a claim that any specific model
was benchmarked in this round.

## 1. Admission and authorization

- Experimental capabilities and their flags are server-owned
  (app/experimental/capabilities.py, app/experimental/flags.py): default OFF, explicit
  opt-in only, dependency closure only shrinks an enabled set, V1_ACCEPTANCE_MODE denies
  all. A public build never enables a wildcard.
- Provider credentials stay in the credential vault / DesktopHost runtime channel; the
  portable launcher does not read dotenv/credentials and cloud egress requires explicit
  consent (ENABLE_CLOUD=false in packaged launch profiles).
- Model Center discovery/admission is passive and local-first
  (app/model_center/discovery*.py): probes are bounded, no model download is triggered by
  the engineering tests, and an unavailable runtime reports NOT_CONFIGURED or
  BLOCKED_UNSUPPORTED_OWNED_PROCESS_PLATFORM instead of pretending success.

## 2. Capability evidence

- Capability registry entries carry model_requirement / network_requirement; the matrix
  exposes them per A/B/U/F package. Real-model quality measurement is NOT_RUN in this
  environment (no authorized weights/GPU acceptance run); contract tests never substitute.
- The subtitle/processing catalog explicitly reports the original registered-local-route
  admission literal and never auto-promotes a mock adapter to a real runtime (D-09 closure).

## 3. VRAM / RAM / scheduling budgets

- SPEC requires 8/12/16 GB VRAM tiers and queue/unload behavior; the current repository has
  partial budget metadata and fail-closed admission, not a verified tier matrix on real
  hardware. MILESTONE_M4_PLATFORM_PREFLIGHT_REPORT.md documents the bounded preflight.
- Local resource reclamation belongs to the packaged launcher/DesktopHost (single process
  tree, disposable WebView2 profile) and the media execution owners (bounded subprocess
  probes with timeout/output limits: scripts/v2_media_prerequisites.mjs).
- Benchmark harnesses must fail closed if they detect disallowed network/IO; the R4
  benchmark's Windows loopback socketpair allowance was corrected in round 3 (D-18) while
  external connects and name resolution remain denied.

## 4. Honest gaps

- Real local model inference, VRAM peak measurement, tier behavior and cloud cost evidence
  are NOT_RUN/LOCAL_REQUIRED in this baseline.
- No provider may be advertised as supported without reproducible evidence; model downloads
  are explicitly out of scope for the engineering rounds.
