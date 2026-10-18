# Actor/incarnation-bound media-view local recovery

2026-10-18. The original media canvas now retains bounded unsaved display definitions in browser local storage after its existing verified draft owner is available. The namespace reuses the original actor/workspace/project/incarnation/branch identity with a separate media-view prefix. Cache content includes author layout/groups, exact asset pins, base view version/digest, original creation request ID and uncertain-save marker. No binary, token, model execution or review capability is cached.

The strict closed envelope is capped at 600000 UTF-8 bytes; the original canvas definition still enforces its own 1000-card/512000-byte limits. Masked asset bindings and extra fields are rejected. Local storage is a recovery hint, not an authorization grant or encrypted vault.

## Explicit recovery

The user requests recovery only when the current canvas is clean. The original overview rechecks project incarnation and edit permission before and after reading the original saved view and current Asset directory. Base version/digest must match. Every cached asset reference must match current readable metadata; stale, absent, deleted or mismatched assets reject the entire recovery without dropping cards or repairing the cache. These are point-in-time metadata checks; original save/execution still own actual source/content validation.

The original canvas state/history and save handlers adopt the recovered author draft. No server write or model execution happens during recovery. A previously uncertain save remains uncertain and cannot be automatically replayed. New-view creation preserves the original application request ID. Explicit successful server adoption clears only this tab's unchanged recovery cache. Other-tab changes, malformed/oversized cache, storage failure or stale authority preserve the existing cache and show a limitation rather than claiming successful recovery. Explicit cache discard requires its own displayed-snapshot consent.

## Evidence

media-canvas-recovery: 40 focused tests passed, TypeScript and Vite production build passed, original shared-token guard passed. Tests cover remount restoration and later explicit original create, preserved creation ID, uncertainty/no replay, actor/incarnation/extra-field/masked/size rejection, changed source access, permission ABA, other-tab conflict preservation, original dirty-owner/gesture handoff regressions, and all 1000 references verified through one original Asset directory read plus two overview checks.

No backend, schema, execution limit or binary store changed. Service-version conflicts are rejected for manual reconciliation; this is not automatic merging, cross-device synchronization or generic executable media-graph draft recovery. Storage availability, browser quota and real browser end-to-end/visual behavior remain separate acceptance boundaries; deterministic storage/DOM tests do not prove those environments.
