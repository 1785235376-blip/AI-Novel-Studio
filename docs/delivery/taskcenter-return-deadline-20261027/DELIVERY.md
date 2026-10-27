# TaskCenter final return lifetime repair

Status: PARTIAL. This slice repairs a deterministic TaskCenter cursor lifetime boundary. It does not repair the separately unclassified asset pagination 409, qualify the repository for main merge, or claim browser/real-model/PostgreSQL/Windows/hosted-CI acceptance.

## Input and exact scope

- Fixed public base: `048fe2a12212df85c272cdc0741659498378d334` (tree `85266f133613fa7c3f71ee84522f069f49f60acc`).
- Final production/tests freeze: `d5845afafcbe83105374b861760cb7f0543b3d99`.
- Only two production files change: `app/experimental/taskcenter_cursor.py` and `app/experimental/taskcenter_cursor_http.py`.
- Existing source capabilities, permissions, original owner reads, Store lifecycle/CAS, export queue, assets, request budgets, frontend and SDK remain unchanged.

## Deterministic defect and repair

The engine checked its fixed deadline inside `page()`, but the HTTP adapter subsequently ran final authorization and owner observations before returning the result. Advancing a deterministic test clock to the original deadline during the last source observation caused the unmodified base to return 200 for first, continuation, last, single and empty pages. Both mounted application routes and real loopback TCP aliases reproduce this: 20 baseline tests fail on 200 versus required 409.

The engine now attaches a bounded, immutable, internal return receipt to the position. It contains only engine/epoch identity, the metadata observation, optional cache handle and issued position, never task data. After original final checks, the adapter verifies it with the same issuing engine. Exact deadline, invalid clock/rollback, issuer replacement or observation eviction prevent return. Single/empty first pages retain their ephemeral original deadline even though they create no cache entry. Validation neither allocates a new observation nor extends the fixed TTL. No source or authorization callback runs under the engine lock.

This is a final post-observation checkpoint, not an assertion that a token cannot expire or be evicted after validation while a response is transported. It creates no atomic cross-owner snapshot or stronger historical ABA guarantee. Receipts are trusted internal objects, not an HTTP capability or a substitute for authorization. They are not emitted in response JSON or accepted as HTTP input. Existing token grammar and response fields do not change.

## Evidence classification

The initial test attempt lacked the original XDG user-data environment and failed before business execution; it is not the red regression. `baseline-red-valid-env.log` records the 10 mounted red cases; `baseline-tcp-red.log` records the full 20 mounted/TCP red cases on the original public base. Independent review also exposed numeric equality of altered internal receipt fields (`False`/`0.0` vs `0`, and `1` vs `True`); exact type validation was added. Initial failed and later passed independent results are retained.

The final immutable results and command/source/module receipts are summarized in `RESULTS.json`. Groups overlap and must not be added. Final code was tested in a separate detached worktree; acceptance uses exit codes plus unchanged source hashes and loaded-module origins, not JUnit alone.

## Work handoff

Keep the existing Work integration and frontend ownership. Do not reimplement this repair or copy whole files over unrelated changes. Apply this reviewed TaskCenter-only diff and its two tests after reconciling the published backend base. Re-run original selected single sources and local pair, fixed-TTL replay/last-page behavior, final permissions/lifecycle refusal, and both API aliases on the combined source.

Do not relax a deadline, replace original authorizers, reset a token to a fresh first page automatically, add offset fallback, alter budget limits, or treat an empty page as complete history. Public upload is a separate parent-controlled step; local freeze hashes are not promises of remote availability until a publication receipt is supplied.
