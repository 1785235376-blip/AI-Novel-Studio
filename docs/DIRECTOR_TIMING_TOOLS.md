# Director planning timing through the existing authoring tools

The original Director editor now reuses the existing Storyboard timing allocator and preview/confirm/local-undo controls for top-level Director notes. It can apply a uniform duration or distribute an exact target total over the current scene or all notes. The same 1–600 second, 1–200 item and deterministic largest-remainder/capped allocation rules apply. Existing Storyboard entry admission stays mode-specific; a separate Director wrapper calls the shared pure kernel.

Only note duration_seconds changes. Surviving identity, numbering, scenes, source bindings, planning evidence and performance author fields remain unchanged. Embedded scene notes are explicitly excluded. This is planning time, not measured video or a guarantee of final film duration. Application changes the original local draft; the original Save, CAS, history and review owners still govern persistence. There is no new graph, workflow, model execution or automatic save.

The original preview lifetime, IME/input checks, consumed-action fence and local undo retirement are reused. Changes to source draft, selected scene, permissions/busy state or unmount invalidate old application callbacks. A save/busy interval still retires local undo.

Evidence:
- 46 focused React checks passed, including all 17 original Storyboard timing cases, 8 new Director cases and existing note/Console coverage.
- TypeScript, actual production Vite build and 52-file token guard passed.
- File 2 and genuine PostgreSQL 2 passed, with opposite-backend cases deselected. Original-owner save/reopen, retained history, unmodified note/source identity and persisted rejection of an out-of-range duration were checked. PG OID 16384 reused and server stopped.
- UI and persistence are separate targeted evidence, not an asserted full browser journey. Browser visual acceptance remains blocked by the previously recorded sandbox restriction; no baseline or guard changed.

No API/backend source or public/private build boundary changed. Whole V2 remains subject to its existing acceptance gates.
