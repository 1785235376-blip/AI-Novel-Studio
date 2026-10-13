# V2 reconstruction checkpoint — 2026-10-13 (Beijing)

## Source identity and evidence boundary

Reconstruction starts from the verified published commit
`4534bed9129bcf2a549b44a91f062c79a77e173b` on
`feature/v2-narrative-platform`, with PR #47 retained as Draft.

The previously reported local commit
`1134f8de50ad68b9e1aad189cb422e256af64c6f` and its source workspace were
not accessible when reconstruction began. A recovered feature-matrix blob is
historical requirement evidence only. It does not establish that the missing
implementation, raw test logs, databases or archives have been restored.
The user authorized reconstructing missing implementation from the actual
published code instead of waiting for workspace recovery.

Historical reports and assertions are preserved. New verification applies only
to the new source snapshot identified by its receipt. Historical test counts
must not be reused as acceptance of reconstructed code.

## First reconstruction slice

The first slice implements explicit manual binary-mask authoring through the
existing Studio Asset owner and Image workspace. It does not introduce a
parallel asset store, model invocation or automatic cutout operation. The mask
is a user-authored asset with exact source version/digest provenance.

The frontend authoring surface, backend admission and persistence, and source
review were implemented in independent worktrees. The separate baseline type
repair is published as `de23bb50b96f07dac3e96dc0f9a1df9940e494b3`; fetched
remote bytes match the tested source. The 21 baseline TypeScript diagnostics
are fixed without weakening runtime validation or original test assertions.

## Verified baseline checks

- Original Asset/workspace File regression: 199 passed, 172 deselected.
  The same baseline suite was inadvertently run twice; these are duplicate
  observations, not 398 independent tests or a failed-to-passed repair.
- Four original frontend workspace/asset suites: 27 passed.
- Baseline full TypeScript check: failed with 21 diagnostics in five existing
  timeline/media files. The original failing receipt is retained privately. The separate published
  repair passes type/build/token checks and 102 focused tests; the same 23
  broader frontend failures remain before and after (755 passes).
- Real PostgreSQL regression: 172 passed, 199 deselected, on isolated PostgreSQL
  17.11 with the original twenty migrations applied to a new empty test database.
  The server stopped normally and the database was retained. This run used the
  exact repository CI dependency constraints; the earlier File baseline used
  a separate development dependency environment.
- Combined frontend mask and type-repair tests: 260 passed across twelve files.
  Combined TypeScript: PASS. Integrated mask File tests: 119 passed.
  Independently source-matched backend verification: new 86 real PostgreSQL
  tests; unchanged original owner regressions 340 File + 208 PostgreSQL passed.
  Both fresh databases applied the original twenty migrations and shut down
  normally. The actual mounted response was accepted by the strict frontend
  decoder through a fetch stub, not real browser networking.

Raw logs, test databases, environment configuration and private filesystem
paths remain private. Only sanitized summaries are eligible for publication.

## Unchanged product boundaries

Windows installation, user GPU, real model quality and final user-machine
acceptance remain NOT_RUN / LOCAL_REQUIRED. Frozen V1 assets, PoemSeed Local
Interop 1.0 and prior evidence are not replaced. No merge or release is
performed. QingJian development is not part of this reconstruction.

## Hosted and browser boundaries

Published type-repair Cloud CI run `38323310949` terminated with eleven failed
jobs, each with no executed steps and runner ID zero. Exact infrastructure
cause is not established. No hosted test pass is claimed or test gate weakened.

The official Playwright Chromium download failed archive validation. A separate
system Chromium launch with its sandbox enabled failed with a socket permission
error before any page ran. Browser/native image-decode acceptance is BLOCKED;
unit decode stubs and geometry tests are not browser evidence.
