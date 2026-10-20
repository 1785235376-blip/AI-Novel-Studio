# GRAPH-08: source-bound authoring drafts (schemas3–6)

Requirement: `AI_NOVEL_STUDIO_V2_FEATURE_MATRIX.md`, GRAPH-08 §7.2, local authoring
preservation across refresh/disconnect. At product `7883878a`, the original cache owner
still rejected schemas3–6. The original palette also emits empty provider/model IDs and
an unselected storyboard prompt: these are legitimate local authoring states, but the
original strict Save decoder correctly rejects them. This slice closes that concrete
loss path in one shared recovery extension; schema7 behavior is unchanged.

## Cache is author input, not an execution receipt

Reuse the existing bounded localStorage envelope, original actor/scope/project-incarnation
namespace, request ID, source baseline and UNKNOWN bit. A recovery-only decoder admits
only the known empty palette fields, validates the rest through the original typed graph
decoder and restores those fields exactly empty. Temporary syntax placeholders never
leave the decoder. The original Save decoder/transport is unchanged and still refuses
these incomplete DTOs. No provider discovery, fallback, run, preview, approval or model
execution is performed. Provider/model strings remain unverified author intent.

## Fresh original reads before explicit adoption

| Schema | Original catalog/source checks |
|---|---|
| 3 | Original media catalog; current asset pins and Graph timeline snapshot/declared source pins. |
| 4 | Original image/production catalog; current asset and Director/Storyboard document pins, plus exact selected shot where declared. |
| 5 | Original video catalog; current planning/shot pins and any referenced I2V image source. Missing connections or an empty route remain authoring only. |
| 6 | Original gated subgraph catalog; original child GET + existing child inspector; exact child ID/version/definition digest/execution digest/input/output interface, current scope/edit grant, pure enabled schema1 child and original node budget. |

Read sources twice with live authority checks, reread the catalog gate, and recheck the
original overview/incarnation/edit grant before adopting. Saved baselines retain the exact
CAS version and both digests. Existing immutable asset/planning bindings and schema6
saved topology/pins cannot be changed by a cache. A new unsaved schema6 call retains the
existing fixed three-node parent chain. No stale pin is silently upgraded or detached.

The shared original lifetime fence/mutex handles owner/source/permission/busy ABA,
late reads, retained callbacks, duplicate recovery and other-tab cache edits. Nothing is
written remotely during recovery, and no runtime/review/cache authority is restored.
Schema7 stays on its prior branch and the default gates are not enabled by this feature.

## Explicit safe boundary

- Stale, unavailable, foreign or unverifiable references remain in the cache/readonly
  inspection; they are not adopted into the current graph. This does not delete author text.
- Timeline verification is conservative: even an old reference that an unapplied edit
  would remove must remain current. The recovery owner does not replay Timeline edits.
- Unapplied Timeline/execution side-form state remains excluded by the original
  `timelineEditor.formDirty` / `executionDirty` persistence guards: it is not a serialized
  Graph definition and belongs to its existing owner. Those owners were not changed.
- Malformed/oversized graphs and forbidden external references in legacy schemas1–2
  remain rejected. Existing typed ports, cycles, parameter and size limits remain.
- An unsaved UNKNOWN **create** retains the exact original key/payload for the original
  explicit same-key retry. A saved UNKNOWN **PUT** retains its CAS/payload and uses the
  original server readback/adoption path; no blind PUT replay was added.
- These frontend reads are observations, not a cross-owner transaction or a runnable
  certificate. Original Save/preflight/run/human-review owners remain authoritative and
  revalidate current permissions, pins, private bytes and capabilities themselves.

No backend, workflow engine, model execution, NLE/Timeline/DSH owner, design token or
shared shell was changed. Full GRAPH-08 and real Host/PostgreSQL acceptance remain open.
Task-local evidence retains the consolidated RED, corrected original-contract expectations,
final focused results and controlled component screenshots; no full-suite claim is made.
