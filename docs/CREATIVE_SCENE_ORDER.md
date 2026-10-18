# Local Screenplay and Director scene ordering

The existing author canvas now offers earlier/later movement for the selected SCREENPLAY or DIRECTOR scene. It swaps existing sequence values in sorted author order, preserving stable scene IDs, exact text, dialogue, notes, source bindings and unrelated document fields. It does not renumber notes, alter existing Storyboard shots, change a timeline or run a model. The original local draft and explicit Save/CAS/history owner remain responsible for persistence.

Read-only navigation remains unchanged. The new write controls are disabled without editing authority or while busy. Stale callbacks are retired after draft replacement, scene selection, permission ABA or unmount. Duplicate/missing scene identities, invalid sequence values and unsupported modes fail without mutation. The selected scene stays selected after movement.

Evidence:
- 37 focused React checks passed, including 8 new ordering cases and original Script/Director controls.
- File 2 and actual PostgreSQL 2 passed, opposite-backend cases deselected. Original save/reopen/history, unchanged scene content and Director-note associations, and stale-save refusal with unchanged persisted state are covered.
- TypeScript, actual Vite build and 52-file token guard passed. PG OID 16384 retained and server stopped.

This is local author ordering, not automatic downstream refresh or final browser/native-IME acceptance. Existing browser restriction remains; no new visual language, baseline or security guard was changed. No backend/API schema changed.

Remote main/PR heads rechecked at 2026-10-18 11:08 UTC: main fed2404c8e30b44061b7139dced45b7f3301601c, open draft PR #47 a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3, open draft PR #48 58bbaad11360330d51f49fc2bb78a955a26469f0. Archive publication remains separate from those source branches.
