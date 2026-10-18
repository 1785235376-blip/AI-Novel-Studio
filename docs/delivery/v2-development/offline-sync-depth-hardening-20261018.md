# Offline sync JSON depth hardening

## Result

Offline file and manual-paste input now rejects more than 64 nested JSON object/array containers before parsing. The linear scan uses constant extra state, ignores brackets in strings, and handles escaped quotes/backslashes. The unchanged native JSON parser remains responsible for syntax, and the original backend remains responsible for the sync envelope.

The raw 512 KiB UTF-8 byte cap still runs first, including BOM bytes. One leading BOM remains accepted without modifying editable text. Rejection uses a fixed message and preserves prior file input or the pasted text; no unsafe preview, receive, or apply is triggered.

## Changed source paths

- frontend/src/experimental/offlineSyncFile.ts
- frontend/src/experimental/offlineSyncFile.test.ts
- frontend/src/experimental/OfflineSyncReceive.test.tsx

No shared Details, global parser, backend, dependency, runner, or unrelated UI changes were made for this fix.

## Verification

- Reproduced the failure before implementation: a 20,001-byte value with 10,000 nested arrays passes native JSON.parse but JSON.stringify(value, null, 2) throws RangeError. Five new rejection assertions failed, while 19 tests passed. Evidence: offline-sync-depth-red-direct-20261018.json and .log.
- After implementation: 64/64 focused tests passed across the helper and receive component. Evidence: offline-sync-depth-green-20261018.json and .log. The receipt reports no sources changed during the check, and final source hashes were rechecked against the receipt.
- Coverage includes array/object/mixed 64-level acceptance and 65-level rejection; escaped strings and property names; BOM plus depth boundaries; exact raw byte caps and invalid UTF-8; deeply pasted and file-loaded input preservation; recovery with corrected BOM-prefixed input; explicit preview/receive; original endpoint, auth header, expected version, and envelope forwarding; existing stale-read/cancellation and retained-callback fences.
- Scoped git diff --check passed.
- No full frontend build was run; root integration owns that check.

Commands used the original runner:

    python scripts/run_v2_checks.py offline-sync-depth-red-direct-20261018 -- node frontend/node_modules/vitest/vitest.mjs run --root frontend src/experimental/offlineSyncFile.test.ts
    python scripts/run_v2_checks.py offline-sync-depth-green-20261018 -- node frontend/node_modules/vitest/vitest.mjs run --root frontend src/experimental/offlineSyncFile.test.ts src/experimental/OfflineSyncReceive.test.tsx

An initial pnpm invocation failed before tests due to installed pnpm 11.25.0 versus required 10.6.5. Its separate failure receipt/log are retained as offline-sync-depth-red-20261018.json and .log; the existing local Vitest binary was then used without installing or changing dependencies.
