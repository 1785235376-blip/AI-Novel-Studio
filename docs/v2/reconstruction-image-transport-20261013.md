# Image transport reconstruction

Date: 2026-10-13 UTC.

## Result and preserved ownership

Configured ComfyUI and Automatic1111 adapters now use the existing bounded image
transport for both startup and refresh. The original production execution
owner's endpoint-locality predicate selects proxy policy: owner-local endpoints
ignore environment proxies; authorized nonlocal endpoints retain their original
proxy behavior. Intentional private/LAN configuration remains supported. A
public endpoint declared local still requires the original cloud and source
consent gates.

Discovery remains strictly loopback-only, directly connected, origin-pinned,
and redirect-rejecting. Its construction path does not enable configured-provider
policy. No new registry, transport owner, framework, or execution service was
introduced. Existing adapter dispatch guards, guarded Comfy media-download
ownership, credential/vault behavior, and production source gates are unchanged.

The transport bounds raw and decoded responses independently at 64 MiB and limits
every decompressor allocation before appending output. Identity, gzip,
zlib-wrapped deflate, and legacy raw deflate support both JSON and binary bodies.
Decoded responses no longer retain stale encoding or wire-length headers.
The single bounded raw-deflate fallback handles valid streams with a misleading
zlib-looking prefix; size-limit failures never trigger a retry. Unsupported or
stacked encodings, truncated streams, trailing encoded bytes, and concatenated
streams fail closed.

## Final verification

The original isolation and fresh-database harnesses were unchanged. The pinned
verification interpreter was used throughout. Original assertions, backend
markers, and skip conditions were preserved.

- Scoped File suite: 273 passed, 2 PostgreSQL-only skips.
- Scoped fresh PostgreSQL suite, including original dispatch/privacy tests:
  277 passed, 3 skips. Two were File-only counterparts. The remaining original
  dump/restore test skipped because its already-installed client tools were not
  on the command search path.
- Separate run of that unmodified dump/restore test with those tools available:
  1 passed.
- Both successful PostgreSQL runs verified no preexisting application objects,
  applied all 20 original migrations, and shut down cleanly.
- Final source snapshots were unchanged before and after verification.
- `git diff --check` passed. The existing Starlette/httpx deprecation warning
  remains.

Coverage includes actual startup and refresh for both adapters; proxy selection
with NO_PROXY absent; IPv4, IPv6, localhost, private LAN, and public-declared-local
routes; original production-preview cloud/source gates on File and PostgreSQL;
strict discovery destinations; all redirect statuses; identity/gzip/deflate JSON
and binary responses; exact limits and one-byte overflow; chunked, missing, and
false lengths; compressed expansion; truncated and trailing encoded input; stream
closure; response metadata; and unchanged guarded Comfy download ownership.

Independent read-only review additionally passed 90 separate split-chunk
compression roundtrips, 82 wire contracts, and all 20 startup/refresh cases. Its
valid raw-deflate prefix-collision finding was repaired and added as a dedicated
regression covering multiple chunk boundaries and exact decoded capacity.

## Retained failure evidence

Earlier results are retained privately and were not overwritten or represented
as final acceptance:

- Initial test construction: 18 failed, 34 passed. A synthetic proxy fixture and
  cloud-owner fixture needed correction.
- Corrected before-source run: 38 failed, 18 passed. It reproduced local prompt
  routing through a proxy, normal gzip double decoding, missing wire bounds, and
  unbounded decompressor allocation. Four interim remote-route expectations were
  later corrected to preserve existing authorized remote proxy behavior; this
  historical total is not a count of distinct final-contract defects.
- First implementation: 56 passed, before independent review.
- Expanded intermediate run: 5 failed, 261 passed. A synthetic command and
  empty-body header case needed completion.
- Review-stage intermediate run: 24 failed, 77 passed. A required synthetic
  prompt was missing, and deflate overflow incorrectly retried; both were fixed.
- Reviewed intermediate suite: 271 passed, before persisted-backend cases.
- Two later setup attempts failed before product tests ran because an ordinary
  temporary-directory helper was mistakenly loaded as a pytest plugin. Corrected
  commands used the original documented temporary-directory option. No harness
  or test assertion was changed to hide the error.

## Final source SHA-256

- `app/dependencies.py`: `403c9e33b4967ab92d9af4b885ea2f39355a864c718f696c1276cf9237f3158d`
- `app/model_center/discovery_bridge.py`: `45c8991a5cd64d2b2c9ea53b4c165fb8870fe5a500a4d76529ef8cbfd0b6119f`
- `tests/test_rebuild_image_transport.py`: `f90b2ff20be09f60c311841cb39baad059319d4b96644b68fd7bf23bf3dbe14f`

## Limits

Image HTTP used synthetic mock transports only. Database tests used disposable
synthetic data. No real model service, paid API, credential, user data, or user
computer was used. This is scoped source and disposable-database verification,
not full-repository, Windows-native, GPU, or real-model acceptance. Generated
inventories were not refreshed as part of this change.

## Root integration check

The reviewed production and additive-test SHA-256 values above match the integrated
root source exactly. The original isolated harness then ran the transport, manual
mask API/owner and audio-listing regression union: **236 passed, 90 canonical
backend skips**, with the existing dependency deprecation warning. This File
integration result does not replace the separate fresh PostgreSQL evidence.
Only production files, additive tests and this sanitized report are selected for
publication; raw logs, runtime receipts and environment details remain private.
