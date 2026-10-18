# B10: explicit local-file receive input

## Delivered scope

- The existing offline-sync receive surface now has a labeled local JSON file chooser alongside the same editable paste field.
- Selecting a file performs local reading and syntax checking only. It never calls the sync API. Preview and receive remain two explicit actions; applying an inbox candidate still uses the existing review/apply flow.
- No backend, API route, envelope schema, owner, authorization or persistence changes. The original `offlineSyncClient` receives the selected channel/version, parsed envelope and explicit target.
- Failed, cancelled or invalidated reads preserve the previous text. Choosing another file, typing, changing target, or cancelling fences late success and error callbacks.
- Channel identity/version/range/revocation, permission blocking, client replacement and unmount invalidate in-flight reads and cached previews. A blocked-to-unblocked transition does not revive an old read.
- Retained preview/receive callbacks require their captured generation and current text, target and exact preview identity. Receive consumes the candidate synchronously, preventing duplicate callback dispatch. Failed/unknown receive results retain editable input for a new explicit preview/retry; nothing replays automatically.

## Local input boundary

- Maximum 512 KiB, checked before reading against `File.size`, independently against actual returned bytes, and against UTF-8 bytes for manual paste.
- Fatal UTF-8 decoding rejects invalid or truncated sequences.
- One leading UTF-8 BOM is accepted for Windows text-export interoperability. Raw bytes, including the BOM, count toward the limit. The exact text stays in the editor; repeated or misplaced BOMs outside JSON strings are not trimmed.
- Only local JSON syntax is checked. There is no new glossary/OTIO schema restriction and no filename/MIME trust boundary. The original sync owner validates the actual envelope and permissions.
- Parse, read and decode failures use fixed helpful messages rather than parser excerpts, file contents or filesystem paths.
- FileReader abort events settle the promise; cancellation removes callbacks/listeners and aborts an active reader. Clearing the native input permits selecting the same file again.

## Source files

- `frontend/src/experimental/OfflineSyncPanel.tsx`: delegates its previous inline receive view to the new component; unrelated panels are unchanged.
- `frontend/src/experimental/OfflineSyncReceive.tsx`: shared text/preview/receive surface, local file input and lifecycle fencing.
- `frontend/src/experimental/offlineSyncFile.ts`: bounded cancellable reader and safe local parser/errors.
- `frontend/src/experimental/OfflineSyncReceive.test.tsx`: 37 component/integration/adversarial cases.
- `frontend/src/experimental/offlineSyncFile.test.ts`: 18 byte/encoding/parser/cancellation cases.

## Verification and limits

Focused debugging passed **91 tests in 4 suites**:

- `OfflineSyncReceive.test.tsx`: 37 passed.
- `offlineSyncFile.test.ts`: 18 passed.
- Existing `OfflineSyncPanel.test.tsx`: 11 passed, unchanged.
- Existing `OfflineSyncRecoveryStatus.test.tsx`: 25 passed, unchanged.

The focused command used Vitest with `--maxWorkers=2 --minWorkers=1`. An initial test-fixture error put the multibyte sample exactly at the allowed limit rather than over it; the fixture was corrected by one character and the full focused set rerun successfully. Production enforcement was not relaxed.

The root owner coordinates final source-bound receipts through `scripts/run_v2_checks.py`, the shared TypeScript/Vite build, and relevant visual/geometry checks after both independent source edits stabilize. This report's focused debugging is not a substitute for those aggregate checks.

The change follows the repository UI skill, DS-v1.0, component rules and canonical NOVEL reference. It consumes existing `Panel`, `Field`, `Button`, `Details` and `StatusMessage`; it introduces no CSS, tokens or protected-shell changes. No real-browser acceptance, Windows desktop validation or external transport acceptance is claimed here. No commit, push or merge was performed by this worker.
