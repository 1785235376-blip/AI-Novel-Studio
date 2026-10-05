# R4 / R5 / UX feature matrix

All 40 packages remain in scope. This is an implementation register, not a completion claim. Baseline: released R3 `d712ab81e9d87bfd5902d0a6bbd47c4edaccac5b`. Frozen PR37 is unchanged.

| Package | Wave | Reuse | Implementation | Frontend | Next concrete work |
|---|---:|---|---|---|---|
| F00 Foundation, reuse and dependency registry | 0 | EXTEND | PENDING | PENDING | Register 40 capabilities, server dependency allowlist and new exact-head evidence. |
| U02 Loss-resistant editing and visible save state | 1 | EXTEND | PENDING | PENDING | Storage write failure currently throws; add honest volatile/durable journal states, IME and late-hydration fences, export recovery and browser failure journeys. |
| U01 Resume the previous workspace | 1 | EXTEND | PENDING | PENDING | Add scoped version-aware resume anchors, user stopping notes and damaged-layout reset without storing tokens. |
| U03 Search, commands and recents | 1 | EXTEND | PENDING | PENDING | Implement authorized project/entity search and keyboard command surface; no sensitive action execution from query. |
| U07 Unified task center and honest progress | 1 | EXTEND | PENDING | PENDING | Aggregate existing task authorities and expose traceable IDs, stages, status filters and domain-specific recovery. |
| U08 Context and privacy inspector | 1 | EXTEND | PENDING | PENDING | Bind rendered request manifest to actual final dispatch, sources and exclusions; test captures rather than invent token counts. |
| U09 Local AI diagnostic and setup guidance | 1 | EXTEND | PENDING | PENDING | Add explicit untrusted Comfy API workflow inspection and actionable missing dependencies; never execute/import/install external nodes. |
| U12 Actionable errors and private diagnostic export | 1 | EXTEND | PENDING | PENDING | Add bounded allowlisted user-created diagnosis with preview, redaction and no automatic upload. |
| U04 Focus, reference split and inspiration | 1 | EXTEND | PENDING | PENDING | Extend existing editor with focus/preferences and read-only references, preserving selection and error visibility. |
| U10 Scenario onboarding and progressive disclosure | 1 | EXTEND | PENDING | PENDING | Provide safe task shortcuts and skippable no-model journey, respect server capability flags. |
| U13 Chinese input, accessibility and scale | 1 | EXTEND | PENDING | PENDING | Actual synthetic 100k/500k/1m measurements and zoom/keyboard checks, no fabricated Windows IME or performance PASS. |
| A04 Temporal semantic story graph | 2 | EXTEND | PENDING | PENDING | Typed time-aware relation projection over existing IDs, source versions, perspectives and bounded impact index. |
| A05 Character knowledge and mind state | 2 | EXTEND | PENDING | PENDING | Reviewed knowledge events, belief/secret distinction and physically filtered perspective context; no second character store. |
| A06 Explainable model broker | 2 | EXTEND | PENDING | PENDING | Current registered authority routing, honest unknown cost and idempotent budget reservation/settlement; final recheck. |
| A07 Model benchmark and capability evidence | 2 | EXTEND | PENDING | PENDING | User-triggered bounded benchmark management and evidence versioning; real-model quality requires configured model. |
| A09 Asset lineage and derived relationships | 2 | EXTEND | PENDING | PENDING | Extend parent graph, cycle rejection, drift/impact and retained missing-source lineage. |
| A13 Production manifest and controlled replay | 2 | EXTEND | PENDING | PENDING | Versioned redacted manifests, dependency preview and new authorized replay task, reproducibility levels separated. |
| U06 Change impact and selective refresh | 2 | EXTEND | PENDING | PENDING | Show exact source dependency changes, preserve locked output and require explicit per-domain rerun. |
| A02 Style metrics and drift | 3 | EXTEND | PENDING | PENDING | Compute language-specific transparent metrics on selected versioned text; attach to existing STYLE records. |
| A03 Evidence-based narrative judge | 3 | EXTEND | PENDING | PENDING | Versioned rubric, exact evidence spans, deterministic repeated-exposition findings, ignore/review/stale handling. |
| A01 Bounded story simulation | 3 | EXTEND | PENDING | PENDING | Finite deterministic event branches and constraints with explicit draft-only route promotion; no manuscript writes. |
| A10 Layered research library | 3 | EXTEND | PENDING | PENDING | Reuse research store and safe parsing, versioned citations, local search and derived invalidation. |
| A11 Revision intelligence and partial changes | 3 | EXTEND | PENDING | PENDING | Source-fenced paragraph patch preview and individually accepted blocks through existing version service. |
| U05 Selection assistant and partial accept | 3 | EXTEND | PENDING | PENDING | Stable Unicode selection digest and patch review; only selected approved blocks can change. |
| U11 Reading, proofreading and publishing checks | 3 | EXTEND | PENDING | PENDING | Read-only preflight with actionable provenance; separate integrity blockers from subjective advice. |
| U15 Writing goals and controlled notices | 3 | EXTEND | PENDING | PENDING | Session goal, stopping note and deduplicated task notices; only persisted activity counts, reminders explicit. |
| A08 Camera grammar and scene direction | 4 | EXTEND | PENDING | PENDING | Extend existing shot version fields and geometry-based rule checks with insufficient-information states. |
| A12 OTIO and NLE exchange | 4 | EXTEND | PENDING | PENDING | Rational-time supported subset OTIO round-trip and loss report; no application compatibility claim without opening it. |
| B03 Voice direction and speaker attribution | 4 | EXTEND | PENDING | PENDING | Editable segment identity/voices/locking and selective stale segment redo; actual audio quality separate. |
| B04 Subtitle editing and timeline | 4 | EXTEND | PENDING | PENDING | Versioned user-time subtitles, duration/overlap validation and real SRT/VTT parsing; no fake forced alignment. |
| U14 Portable project, relink and safe cleanup | 4 | EXTEND | PENDING | PENDING | New destination portable manifest, digest relink and cache-only explicit cleanup preview; archive/path hardening. |
| U16 Safe batch preflight | 4 | EXTEND | PENDING | PENDING | Snapshot-bound domain-delegating batch preflight, bounded execution, partial receipt and unknown-outcome handling. |
| B01 Declarative template library | 5 | EXTEND | PENDING | PENDING | Local template preview/instantiate/version compare using existing services; no executable package or remote marketplace. |
| B02 Custom agents and workflow SDK | 5 | EXTEND | PENDING | PENDING | Bounded declarative graph editor/contracts and registry-only nodes, reuse scheduler, DENY_ALL code extensions. |
| B05 Multilingual revisions and terminology | 5 | NEW | PENDING | PENDING | Parallel versioned target-language paragraphs, glossary checks and explicit accept without source overwrite. |
| B06 Comic and Webtoon layouts | 5 | EXTEND | PENDING | PENDING | Manual approved-image panels, reading order and speech text preflight with actual layout export. |
| B07 Interactive narrative export | 5 | EXTEND | PENDING | PENDING | Restricted condition parser, bounded two-ending preview and engine-neutral export; target runtime validation separate. |
| B08 Writer room and team review | 6 | EXTEND | PENDING | PENDING | Scoped assignment and asynchronous version comments, domain review authority and revocation checks. |
| B09 Project fork and merge | 6 | EXTEND | PENDING | PENDING | Baseline-backed three-way preview/conflict resolution and recovery journal; preserve original branches. |
| B10 Offline synchronization foundation | 6 | NEW | PENDING | PENDING | Default-off scoped outbox/inbox protocol and two isolated local endpoints, idempotency/conflict/revocation; production cloud blocked. |

## Inherited R3 gaps retained

- R3-GAP-01 / OPEN_DEFECT: File delete/lazy document read resurrection. Next: Separate shared fix with deterministic concurrency regression and backport-candidate entry.
- R3-GAP-02 / PARTIAL: Branch-specific manuscript and entity snapshot adapters. Next: Preserve fail-closed source capture until actual branch repository support is verified.
- R3-GAP-03 / PARTIAL: Organization, world-rule and relationship import promotion. Next: Add explicit adapters through existing review and stable IDs; never silently adopt candidates.
- R3-GAP-04 / PARTIAL: Interrupted media promotion after source changes requires manual reconciliation. Next: Retain actual asset/checkpoint and reconciliation-required state; do not falsely reject already-written assets.
- R3-GAP-05 / PARTIAL: Live named provider profiles and OS-vault registrar/UI. Next: Reuse contracts; block credential binding without actual Host/OS secure workflow.
- R3-GAP-06 / ADAPTER_REQUIRED: Declared media families and actual planning/agent/embedding/image/video/TTS runtime adapters. Next: No mock promotion into real quality; only registered reviewed runtime implementations can dispatch.
- R3-GAP-07 / NOT_RUN: Maximum-scale long-book processing and whole-scope serialization performance. Next: Separate measured 100k/500k/1m synthetic test from earlier 320475-character R3 import evidence.
- R3-GAP-08 / MISSING: Optional bulk asset tags, archive/restore, replace/reimport and repair UI. Next: Extend the existing asset library without replacement or automatic deletion.
- R3-GAP-09 / NOT_RUN: Interactive Windows/IME/OS vault, real GPU/models, install retention and target software. Next: Retain distinct environment/quality/user acceptance gates; no local-only substitute claim.

The machine-readable matrix preserves source paths, dependency IDs and distinct API/UI/task/browser/model verification fields. A missing real model does not block deterministic editing, inspection, local rule processing or manual workflows.
