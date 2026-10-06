# Local Interop V1 tutor, verifier and case adapters

A user starts Ask Tutor from the Studio integration entry. The preview separates
metadata from optional selected text/chapter/specific context. Confirmation sends
the exact versioned capsule to the explicitly connected local peer. Guidance has
summary, diagnosis, steps, warnings, references and a verification condition.
Studio displays guidance as advisory text, never executing model-suggested steps,
editing prose, accepting drafts or altering settings. Handoff remains a separate
explicit-click operation checked by Studio's own authorization.

TaskRequirement communicates modality, estimated context, privacy and bounded
quality/latency/cost priorities. A model recommendation is advice only. Both
products retain their own routing and credentials; shared metadata confers no
model execution or cloud authorization.

Diagnostics use a removable-field preview and versioned sanitized capsule. They
are local and bounded. Tutor problems map into existing Tutor/Context V2 contracts;
real host state/evidence retains its authority and privacy. Reference mappings run
without paid providers, real manuscripts or a desktop installation.

Verifier evaluates an explicit structured condition against trusted fresh source
state and evidence. Results are VERIFIED, PARTIAL, FAILED or UNKNOWN. Missing,
untrusted or stale evidence cannot become VERIFIED from an LLM sentence. The
result is informational and never silently changes Studio state.

CaseCandidate maps problem, environment, diagnosis, guidance, result, verification,
software identity/version and evidence. Default privacy is LOCAL_ONLY. The flow
is candidate -> preview -> explicit user approval -> memory/case gate. There is
no automatic upload or saving because a task appears fixed. Unsupported native
environment facts must remain unknown/unsupported rather than invented.

The cloud repository contains a real reference adapter and synthetic Studio
fixtures, not the complete tutor desktop runtime. Actual desktop app discovery,
Named Pipe wiring, UI composition and native lifecycle integration remain
LOCAL_REQUIRED. Synthetic Tutor and Synthetic Studio are always MOCK_ONLY.
