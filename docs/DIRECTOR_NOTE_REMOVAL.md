# Explicit local Director-note removal

Actual source inspection found that the original Director note controls supported adding, duplicating and reordering top-level author notes, but not removing one. The existing editor now offers a collapsed removal control with an unchecked, draft-bound confirmation. It changes only the local author draft through the original onChange callback. Persistence still requires the existing explicit Save action.

Surviving IDs, numbering, scene content, embedded notes and source evidence are preserved. A note still referenced by a current shot is refused rather than silently detaching it. This does not modify previously saved documents or downstream pinned versions. The warning recommends retaining a backup before removal. No new API, persistence owner, model call or automatic save is introduced.

Confirmation expires when the draft, note or permission lifetime changes. Retained event handlers cannot reuse consent after an unchecked checkbox in the same batch, a changed draft, permission ABA or unmount.

Evidence:
- 23 focused React tests across original note controls, Director backup and Graph Director Console passed.
- TypeScript, actual production Vite build and 52-file UI token guard passed.
- One original-owner File case and one actual PostgreSQL case each passed (opposite backend deselected). These verify explicit save, fresh service reopen, untouched prior history, stale-save refusal with unchanged persistence and original history restoration as a new revision.
- PostgreSQL reused disposable OID 16384 and stopped normally.

The UI and persistence checks are separate targeted evidence, not a mounted end-to-end browser test. Existing production-browser socket restriction remains unresolved; no security boundary or visual baseline was changed. This does not promote whole V2 release readiness. No backend code or API catalog changed.
