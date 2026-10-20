# Reviewed cloud authoring batch

Product `b8371a48816b852176d45151eb9a0e3618a32c07`, tree `d1abbaaf64d7fd95535ad75ea2470fa288a35579`, based on `9ce5e243f925f6fb5141046758045c59b1dca46f`. Four original reviewed feature commits are retained exactly, plus two conflict-free integration-only merge commits. The bundle contains six commits and 60 new objects. Twenty changed paths exactly match their reviewed final source blobs; no conflict resolution or additional product edit was needed.

## Scope
- 3D: read-only validated GLB scene-instance/shared-mesh inventory and highlight. Whole-scene diagnostic export remains independent of selection.
- Image: bounded local mask redo; undo/redo share the original 16-state history limit. New edits discard/zero redo history; restored pixels still require fresh save consent.
- Assets: explicit left/right original-media preview and lifecycle cleanup. Decoder failure disposes the current preview and allows explicit retry. Dedicated transport memoization preserves playback on unrelated host redraw and retires media on credential/owner change.

## Review and verification
Independent review found no remaining scoped P1/P2 after two Asset findings were fixed. Model review passed two targeted checks; mask review passed three adversarial checks, including a 1,500-operation independent pixel oracle. The extra standalone model authorization-ABA diagnostic fails against both feature and base. It is retained as inherited component-hardening evidence, not counted as passing. The production host permanently latches retirement for identity/authority loss and does not permit the tested false-to-true callback reuse. No broad standalone ABA guarantee is claimed.

Asset final author/reviewer evidence: 60 focused plus 7 actual-mounted-React tests with fixture HTTP/media APIs passed. Mask author evidence: 210 tests across ten files passed. The 3D author reported 24 unique focused cases and build checks, but those raw author logs were not persisted; the package does not reconstruct or present them as file-backed evidence. This integration did not rerun either complete focused set: exactly 12 selected cross-slice cases passed, with 24 intentionally filtered cases skipped. One serial `npm run build` passed TypeScript and Vite (2516 modules; existing large-chunk warning). Token guard and diff whitespace checks passed. The build and mounted UI tests do not establish real media decoding or backend acceptance.

## Evidence and restoration
The evidence ZIP includes exact changed-source snapshots, author/reviewer tests and reports, sanitized raw logs including initial failures and browser blockers, exact integration commands, a per-entry SHA256 index and the object verifier. Local evidence paths are normalized; original byte counts and SHA256 values are retained. The original evidence files and author worktrees were not modified. Dependencies were reused by symlink and are excluded, as are build outputs, secrets, private user data, internal notes and unpublished local work.

The product prerequisite is the previously verified public `9ce5e243f925f6fb5141046758045c59b1dca46f` restoration; use the pinned prior archive chain in RESTORE.md. The archive branch is a delivery archive, not this product tree. No main merge, release, deployment, paid service or real-data mutation occurred.

## Acceptance limits
- Bounded frontend authoring improvements only; no full feature or Studio V2 completion
- Browser geometry/screenshots blocked by observed Chromium Unix-socket and escalated bwrap restriction; not retried
- Real codecs, installed Host, PostgreSQL, Windows-native and full-suite/full-E2E NOT_ACCEPTED
- Standalone 3D false-to-true isCurrent ABA diagnostic fails in both base and feature; production host permanently retires authority and does not offer that contract
- DSH unpublished Audio/U16 and inaccessible private migration inputs NOT_INCLUDED; schema7 remains DEFAULT OFF; PromptAdoption POST remains closed
