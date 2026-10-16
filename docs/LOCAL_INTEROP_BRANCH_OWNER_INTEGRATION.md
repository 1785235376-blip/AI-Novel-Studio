# Local Interop branch-owner integration

Status: `CONTRACT_VERIFIED` for the production-owner/Host/client boundary on File and the actual TypeScript client over isolated loopback HTTP. Real PostgreSQL and hosted browser results remain pending the published CI run. Actual Desktop remains `LOCAL_REQUIRED`. This implementation is not an independent audit and does not change the historical audit's `BLOCKED` result.

## One authoritative owner

`InteropContextProvider` now selects `CollaborationReadService.chapters_for(scope)`. A registered production branch reads only the existing `BranchManuscriptService`; an empty branch stays empty and never borrows mainline. Disabled branch flags, revoked permission, archived/deleted chapters and scope mismatches fail closed. Legacy adapters that explicitly lack a registered branch owner retain their existing mainline behavior.

No second Host, executor, session store, chapter store or permission system was introduced. The existing Host's sessions, content consent, bounded source selection, capability checks and cancel/revoke boundaries remain authoritative.

## Frozen protocol identity boundary

`app/local_interop/chapter_ids.py` and `frontend/src/interop/chapterIds.ts` implement the same canonical projection:

- Existing IDs valid under the frozen 1.0 `OpaqueId` alphabet remain unchanged.
- Incompatible native IDs, including A43 and branch IDs containing `~`, become `chapter-` plus the full SHA-256 of the compact UTF-8 JSON tuple `["studio-chapter-v1", workspace_id, project_id, storyline_id, branch_id, native_id]`.
- Labels are 72 characters, deterministic across restart and bound to all four scope dimensions. They cannot be decoded into repository keys.
- Reverse lookup enumerates current exact-scope owner rows, requires the same canonical native identity, and rejects missing, archived, tombstoned or ambiguous matches. It never resolves a chapter number or chooses between colliding labels.
- Connect and preview convert native IDs in the existing browser client. Specific-context choices, capsules, evidence, events and Tutor messages contain only wire labels. Explicit, currently authorized editor handoff alone returns the real native ID to the existing Studio router.
- Sessions pin the native identity internally and do not survive Host restart. No durable alias registry or shadow authority exists.

The existing delivery binding also pins selected additional chapters and cross-chapter handoff targets through response-body delivery. Source-list responses and queued event/SSE frames recheck live owner authority. Per-action selection/content/metadata consent and current source versions remain required. Existing polling remains explicitly polling; this change does not claim new native Desktop or realtime branch event support.

No PoemSeed Local Interop 1.0 schema, regex, product ID, public field, protocol source or migration 001–020 changed.

## Authorized synthetic fixture migration

Only `frontend/scripts/local_interop_browser_host.py` changed among the original Interop test fixtures. Under its existing mandatory `MOCK_ONLY` guard and isolated-directory checks, it explicitly enables `branch_manuscript_v1` before app import and initializes the real branch through `preview_fork` / `apply_fork`. The exact synthetic title and manuscript payload remain unchanged. Production defaults and peer mainline privileges are unchanged.

Fixture SHA-256:

- Before: `993452f9a52f8e4b28dd51642ba21da7433c8844242c6c6359643163a9b22144`
- After: `f2e313afd45b7f58fb8ab98c63afcabfc056c761bf3d03bb6d363215f2f53060`

Starting published commit: `d9d2df3a0a831a5bba6249793fd21946c17ce7d4`. The unchanged original HTTP suite was run before implementation and reproduced `TypeError: Cannot read properties of undefined (reading 'length')` at its `chapters.items.length` assertion. The same unmodified suite passes after integration. Both original TypeScript HTTP tests and all original browser assertions remain byte-for-byte unchanged.

## Verification and boundaries

New coverage: `tests/test_surface_interop_branch_authority.py` and `frontend/src/interop/ChapterWireIdentity.test.ts`.

The File/real-PG parametrized matrix covers exact branch ownership; empty, other branch and other project sources; same legacy chapter number under different owners; mainline distinction; A43 qualified native IDs on explicitly legacy adapters; full-length/Unicode/malformed IDs; collision denial; content and metadata consent; selection/deep-link revocation; source-version changes; archive/tombstone behavior; restart/reconnect; and stale response-body delivery after a nonactive source or active event source is deleted. PostgreSQL cases use the existing real database fixtures and gates; there is no emulation or broadened skip.

Local final checks:

- Original `tests/test_local_interop*.py` plus the new owner matrix: **365 passed, 86 existing backend/platform gate skips**.
- Frontend Interop tests plus the original actual TypeScript HTTP client: **106 passed** across seven files.
- TypeScript build/typecheck and scoped `git diff --check`: passed.
- Hash comparison: all frozen protocol files and database migrations match the published baseline; original Interop tests and browser assertions are unchanged.

Local Chromium was previously denied and was not retried. Browser verification is `NOT_RUN` locally and must use the authorized hosted workflow. Real PostgreSQL is `NOT_RUN` locally and must use the existing hosted PostgreSQL 16 service. These are distinct from the passing actual loopback HTTP/client integration and the synthetic Tutor's `MOCK_ONLY` status.
