# Director proposal review preservation

Base: `32478f37abd9aff9773856d909f02aec9f900fa2`.

## Runtime change

- Local review edits or an active human-review confirmation block queue replacement, new suggestion preparation, and optional model replacement.
- Restoring the original suggestion requires a dedicated discard checkbox. Any further review edit invalidates that confirmation.
- Ordinary refresh and uncertainty status reads retain local review text. A failed read does not clear it.
- Applying a recovered status requires explicit local-review discard. It preserves the separate unsent preparation target.
- Recovery is tied to the uncertain operation's target ID. An unknown creation has no receipt ID, so an older selected row cannot be treated as its receipt. Missing/unknown results retain a warning and never trigger an automatic write or document callback.

Only `AIDirectorPanel.tsx` and `AIDirectorReopen.test.tsx` change. Existing original-owner source checks, linked-DRAFT reopen behavior, permissions, model consent, and backend persistence remain unchanged.

## Verification

See `verification.json` for exact owned hashes, commands and retained logs.

- Focused panel/reopen/receipt/model-control tests: **49 passed**.
- Independent panel/reopen review: **43 passed**. It found and verified fixes for the separate-preparation-target and unknown-creation identity edges.
- Mounted graph and adjacent workspace/wrapper tests: **61 passed**, including screenplay suggestion → human review → original DIRECTOR DRAFT → explicit graph pin → both owners reopen.
- TypeScript, Vite build and UI token guard: **passed**. The existing Vite chunk-size warning remains.
- Browser/visual/geometry checks: **NOT_RUN** because of the prior unresolved browser socket EPERM; no retry was performed.

These are in-session protections, not new persistent draft storage or page-reload recovery. Explicit discard abandons local review text only; a missing list row or unknown creation is not proof that the prior write did not execute. No model/provider calls were made. Shared graph display-note work was present during validation, so this evidence binds the owned source hashes rather than claiming a clean whole-tree snapshot.
