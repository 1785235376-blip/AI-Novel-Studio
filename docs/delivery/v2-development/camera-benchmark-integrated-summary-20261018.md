# Bounded camera and video benchmark integration

2026-10-18 18:22 UTC. Base: 9ccac0be925666f6b9ad1d32cc6286255668f4f0.
This is an implementation checkpoint, not formal V2 acceptance. Expanded release
scope GAP-BACKLOG-2026-10-19-r2 remains authoritative; DIF-05 and DIF-08 are partial.

## Verified evidence

- Static camera owner: 107 real PostgreSQL cases passed, 112 non-PG cases
  deselected. Existing UTF8 database OID 16384 reused; durable table fingerprints
  restored after fixture cleanup, no migrations/database creation. Independent
  shutdown confirmed stopped process, absent PID file and closed port.
- Camera combined File suite: 253 passed across 13 modules, 123 PG cases deselected.
- Benchmark final incarnation API tests: 40 File and 40 PostgreSQL cases passed.
  Old responses after project deletion/recreation denied; fresh-owner positives
  retained. Prior lifecycle, regression and failure receipts remain separately
  recorded; overlapping totals are not summed.
- Root combined frontend: 193 tests across nine files passed, TypeScript build,
  Vite production build and UI token guard passed. Large-chunk warning remains.
- Root PUBLIC artifact/catalog: six checks passed, including an actual offline
  wheel and metadata dependency checks. Both new STANDARD modules explicitly
  included; private namespace exclusions preserved.
- Root frontend/PUBLIC and final camera/benchmark PG receipts all report
  sources_changed_during_check=false.
- Catalog: 2423 operations, six additive operations, zero removed;
  source fingerprint bbabe217c3fb5ac2b64c6c436695a7ead1b1b1860cc930439d3f014569e35e4a.

## Honest boundaries

Camera output is deterministic camera-only glTF with rigid ancestry and exact
source provenance. Actual Blender/UE import, identical framing, animation and
Windows acceptance are not established. Benchmark transport is synthetic with
CPU-generated real media; no model server or paid API ran. Observed latency
includes orchestration and polling; hardware and actual upstream costs are not
invented. Human approval, original owners and billing reconciliation remain.
Browser/visual and final same-candidate release acceptance are NOT_RUN here.

See STATIC_GLB_CAMERA_EXCHANGE.md and the original runner JSON/log receipts
for source maps and detailed lifecycle/authority tests. Public archive delivery
is a separate subsequent action, not implied by this local checkpoint.
