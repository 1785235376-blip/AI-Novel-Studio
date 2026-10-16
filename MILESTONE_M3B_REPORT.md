# M3-B Same-Scan Model Metadata Reuse and Client Ownership

**Status: M3 PARTIAL; final local checkpoint, 2026-10-09 16:46 UTC.**
The existing scan's file/index metadata is visible in Model Center, with minimal
legacy-client ownership and Agent-selection corrections. The complete selected
**56-file owner range** passes on File (**2,127 passed / 1,099 skipped**) and
fresh real PostgreSQL (**2,094 passed / 1,132 skipped**). Full frontend is
**2,040 passed / 8 existing skips**; build/49-file token guard and **279**
infrastructure checks pass on the same stable **1,688-input** source map.

These are bounded local results. Written **10,380-node** and **7+14 browser**
inventories are not full-product/browser execution. M3-B hosted browser/full CI
awaits publication. Older M3-A full Cloud acceptance remains **FAIL** despite
passing subsets. First failures, exact identities and remaining gates are below.

## 1. Source identity and preserved history

- Repository/branch: `1785235376-blip/AI-Novel-Studio`,
  `feature/v2-narrative-platform`, [Draft PR 47](https://github.com/1785235376-blip/AI-Novel-Studio/pull/47).
- Published M3-A parent HEAD: `9851bdd2d692df983664bc8f4597fbc05c0e2ceb`;
  tree: `cd6989a19e5fd5e2400f2325fe696cae03d8eda7`.
- First M3-B frozen attempt: **1,682 inputs**, map SHA256
  `d9417d263a3325b37c11ed5627fe3389bb3fef925c655601185e5653d9682270`.
- Corrected source froze at **16:30:35 UTC**: **1,688 inputs**, map SHA256
  `95f58c348feba6c15182e1b584e37c0370ff3e3e319b56443ff7cd08cd4aa7c6`.
  Map hashes use sorted compact JSON of each receipt's `source_sha256` object.
- Local receipts record the parent HEAD plus actual working-tree input hashes.
  Neither the parent nor the catalog's staged tree is the final M3-B commit.
  Its containing commit/tree will be bound through PR 47's publication receipt
  after commit; this document deliberately does not self-embed that future SHA.
- [M3-A report](MILESTONE_M3_REPORT.md) and original milestone conclusions retain
  every committed byte. Historical M2 failures and M3-A's first PG isolation
  failure are not rewritten. Old tests/selectors/timeouts/skips/gates remain.

## 2. Actual bounded implementation

`frontend/src/localAiDiscoveryApi.ts` now types existing scan
`environment_schema_version`, `model_files` and `roots` fields as optional.
`LocalAiDiscovery.tsx` shows `LocalAiModelFiles.tsx` only with V2 enabled and
schema exactly 2. The backend already supplied these observations; no production
API, scan worker, registry or backend source is added or replaced.

The display consumes the owner's **current scan**, with **20 observations per
local page** over the scanner's existing maximum **2,000-file** result. Opening,
paging, expanding details and reopening do not scan or read model files. A new
scan resets pagination. Host/session/project/epoch fencing and late-response
rejection remain with the existing owners; §10 extends that reuse to legacy UI.

- Binding uses only exact `candidate_ids` found in the same scan, then existing
  registration `id` or `candidate_id`. Names, families, paths and unrelated
  registrations cannot manufacture runtime association.
- File/index observations, runtime candidates, registered-disabled records and
  authorized routes remain distinct. Schema-2 metadata without a runnable
  candidate no longer yields the misleading “no models found” headline.
- Missing historical fields, an empty returned list, partial/cancelled results,
  bounded roots and unknown bindings remain distinguishable. None establishes
  that no model exists elsewhere on the backend host.
- Safetensors/GGUF header checks do not verify weights or inference. Family and
  capability names are hints. Diffusers path/bytes describe **model_index.json
  only**, not directory/weight size or component completeness.
- File observations remain generation **NOT_RUN**. Separate linked generation
  evidence is not attributed to the file check; uncertain state suppresses stale
  registration/generation claims. Enable is route authorization, not a load.
- Paths and roots remain collapsed advanced details. Path identity is not a
  content hash; same-named files at different paths remain separate.

Existing primitives/styles are reused. This view cannot install, download, copy,
register, enable, launch or execute models. Existing manual creation remains
available. **MODEL-06 content deduplication is not implemented by this slice.**

## 3. Development evidence and retained first failures

Linked receipts retain commands, UTC intervals, source maps and raw-log hashes.
All referenced log hashes were checked against saved bytes. These overlapping
development snapshots are never summed into a product total.

| Receipt | Actual result and qualification |
| --- | --- |
| [Mounted file projection](docs/delivery/v2-development/dev-m3b-file-projection-contract.json) | **9 PASS**, 15:56 UTC. Original mounted authority/API; snapshot/status/environment copy one scan; GET invokes no network/hardware/metadata enumeration; copies, distinct paths, explicit rescan, revoke and flag-off covered. |
| [First file fixture](docs/delivery/v2-development/dev-m3b-file-fixture-first.json) | **2 FAIL / 21 PASS**, 16:00 UTC, shared-source drift recorded. Synthetic GGUF declared zero tensors; the original checker correctly rejected it. |
| [Header-corrected fixture](docs/delivery/v2-development/dev-m3b-file-fixture-header-corrected.json) | **23 PASS**, 16:02 UTC: 7 new fixture + 7 unchanged fixture + 9 projection. Only synthetic header count changed to 1 like the original helper; no tensor payload, checker/assertion relaxation or inference. Stable maps. |
| [UI RED](docs/delivery/v2-development/stage-m3b-files-ui-red.json) | **12 FAIL / 5 PASS**, 15:57 UTC, before the view existed. |
| [Pagination RED](docs/delivery/v2-development/stage-m3b-files-pagination-red.json) / [uncertainty RED](docs/delivery/v2-development/stage-m3b-files-uncertain-red.json) | Each focused case **FAIL**; other cases are selection skips. Both defects remain recorded. |
| [Focused frontend](docs/delivery/v2-development/stage-m3b-files-ui-final.json) | **92 PASS**, 16:01 UTC: 20 new + 72 original; exact binding, missing fields, 2,000-file pagination, poll/replacement, owner/revoke/late-response and uncertain recovery coverage. |
| [Development typecheck](docs/delivery/v2-development/stage-m3b-files-typecheck.json) / [token guard](docs/delivery/v2-development/stage-m3b-files-token-lint.json) | Commands PASS; typecheck records browser-fixture source drift with four owned frontend files stable. Token guard covers 47 files. Neither replaces the final 49-file/frozen checks. |

## 4. First frozen attempt: preserved, not final corrected-source proof

These receipts have matching stable **1,682-input** maps from §1. Their later
replacement by a new source freeze does not erase these outcomes.

| Receipt | Timed outcome |
| --- | --- |
| [First full frontend](docs/delivery/v2-development/stage-m3b-full-frontend.json) | **FAIL: 1 failed / 2,000 passed / 8 skips**, 16:07:00 UTC. Existing Agent default-role test displayed `verifier` while submission used initial `planner`; log SHA256 `66c804962a43b336de7ffd4f5df0bb7ed6d6184b2360363c0cd9d2580ad63bb2`. |
| [First File owner range](docs/delivery/v2-development/stage-m3b-owner-file.json) | **2,125 PASS / 1,099 skips**, 341.57 s, 16:11:35 UTC; 55 files. Log SHA256 `8387ce12e9b23ca2f38711c5b2d32824af92ebd65ee2a0ef86a61511a29bcd9e`. |
| [First real PG owner range](docs/delivery/v2-development/stage-m3b-owner-postgres.json) | **2,092 PASS / 1,132 skips**, 853.77 s, 16:20:11 UTC; 55 files. Log SHA256 `b104e8ce42513d31d6d0af8724d710191f55f32f57598f3996b503b3a31b2a48`. |
| [First build](docs/delivery/v2-development/stage-m3b-build.json), [infrastructure](docs/delivery/v2-development/stage-m3b-infrastructure-catalog.json), [browser collection](docs/delivery/v2-development/stage-m3b-browser-collection.json) | TS/Vite/47-file token PASS; 279 PASS; **7+12 inventory only**. These precede the later two legacy browser cases and owner/Agent corrections. |

First PG used fresh `v2_m3b_owner_20261009`, OID **34415**, empty before all
20 original migrations. Its [runtime receipt](docs/delivery/v2-development/stage-m3b-owner-postgres-postgres-runtime.json)
and [server log](docs/delivery/v2-development/stage-m3b-owner-postgres-server.log)
verify PASS, retained database and normal shutdown at **16:20:11.926 UTC**.
Neither first backend run was interrupted or restarted to make a correction pass.

## 5. Additive hosted-browser input, not local browser execution

The test server adds a strictly gated seed action for three hardcoded metadata
files totalling **less than 512 bytes**. Existing host guard, feature gate, exact
confirmation payload, exclusive creation and no-repeat/no-active-scan checks
apply. No arbitrary paths, overwrite, user files, weights or real hardware are
introduced. Only explicit scope preview/confirmation invokes the original worker.

`v2-local-ai-files-live.spec.ts` follows the original consent journey in the same
single-worker serial project/server. It checks metadata/type/byte size/binding,
non-inference labels, collapsed paths, three viewport geometries and reload plus
explicit host rebinding without repeated scans. Cleanup uses only its owned
project IDs. The [initial dependency-project inventory](docs/delivery/v2-development/dev-m3b-browser-inventory.json)
was corrected to the [same-project ordered inventory](docs/delivery/v2-development/dev-m3b-browser-inventory-order-preserved.json)
before browser execution; both receipts remain.

Two later default-off/V1 journeys test lawful old-scan UI binding, explicit scan,
fixture revocation, observed 401 private-cache/form clearing, original UI unlink/
rebind to another existing synthetic identity, and another explicit scan. That
second identity exists only in the fixture's original in-memory registry.
No server or product credential owner is added. Final collection is **7 original
+ 14 independent = 18 original ordered entries + 3 new journeys**.

Local browser remains **BLOCKED**. No alternate artifact/trace/screenshot route
was used. New-SHA hosted execution is **PENDING**; no local screenshot, keyboard,
responsive-layout or visual approval follows from unit/build/collection passes.

## 6. Terminal published-M3-A hosted record, separate from M3-B

[Terminal manifest](docs/delivery/v2-development/m3-ci-terminal.json), SHA256
`345c5c6e2205dfe32c4b3c24f04052df708e776fb391cae3a015a75640775d7c`,
records all five watched workflows naturally terminal on **attempt 1**, without
agent rerun/cancellation. All **29** saved log byte counts/hashes are verified.
Push source is `9851bdd2d692df983664bc8f4597fbc05c0e2ceb`; PR checkout is
`02a3f6e9908f785a308a4605e362f8876aed4d8b`. Their equal tree
`cd6989a19e5fd5e2400f2325fe696cae03d8eda7` does not make the commits identical.

| Older hosted scope | Terminal outcome, per event unless stated |
| --- | --- |
| Cloud [push 37954818267](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37954818267) / [PR 37954826041](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37954826041) | GitHub conclusion **cancelled**, acceptance **FAIL**; each 8 successful jobs, 1 File cancellation and 2 failed mandatory joins. |
| Frontend | **1,981 unit PASS / 8 skips**, TS/build/token PASS; **104 browser PASS + 2 separate real-client PASS**. |
| Original V2 / independent / TCP | **7 live + 8 geometry PASS**; independent **11 PASS**; TCP **2 actual + 102 harness PASS**. M3-B's later 14-case suite is not covered. |
| Full File execution | **CANCELLED_INCOMPLETE**, last logged push 93% / PR 88%; **no final backend count**. Its 174 infrastructure passes are not full File acceptance. |
| PG execution shards | All four jobs PASS. Per event: shard 0 **3,434 passed / 1,740 skipped / 5,188 deselected**; shard 1 **3,388 passed / 1,800 skipped / 5,174 deselected**. **Strict aggregate FAIL**: both mandatory profile joins stopped at cancelled File's execution-success prerequisite; provenance/complete-coverage reconciliation skipped. |
| Cloud Windows | 59 native + 3 environment contracts, host/package smoke, embedded Python 3.12.9 and PG 16.15 recovery scopes pass. Interactive user desktop and model inference remain NOT_RUN. |
| Local Interop [push](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37954818409) / [PR](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37954826046) | Both SUCCESS; each File **345 PASS / 68 skips**, PG **345 PASS / 68 skips**, Windows reference 8/native-boundary 33 checks. Counterparty **MOCK_ONLY**, real desktop **LOCAL_REQUIRED**. |
| [Shared R123](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37954826039) | Workflow SUCCESS reproduces all three historical RED defects on `c6f2126115b52e17839d48efea091dc21ec08c61`; not current-head acceptance. |

Counts come from logged receipts; original JUnit/coverage artifacts were not
independently downloaded/reconciled. No trace or screenshot was inspected. The
unsupported cancellation-annotation endpoint supplied no independent timeout
annotation. Historical M2 Cloud failure and independent **6 PASS / 2 FAIL**
remain intact; passing M3-A subsets do not retroactively change them.

## 7. Requirement delta and remaining M3 gate

This slice improves **START-03 / MODEL-04** visibility and the display portion of
**MODEL-05 / MODEL-09**. **MODEL-01 / STORE-02** owner reuse and **MODEL-07** action
separation are preserved. Legacy correction improves **START-02 / MODEL-02**
compatibility without expanding host access. See the narrow appended
[feature-matrix delta](AI_NOVEL_STUDIO_V2_FEATURE_MATRIX.md#35-append-only-m3-b-file-observation-delta).

M3 remains **PARTIAL**: MODEL-06 content deduplication, complete component/runtime
compatibility, measured hardware profiles, official install/license/size guidance,
managed downloads and optional API consent/budget workflows remain incomplete.
Weight integrity, actual inference/performance/quality and user Windows acceptance
remain **LOCAL_REQUIRED / NOT_RUN** as applicable. No model, paid provider or
personal subscription was used. M12 remains **USER_APPROVAL_REQUIRED /
LOCAL_REQUIRED / NOT_RUN**.

## 8. Agent selection diagnosis and deterministic correction

The 16:07 full-suite failure was not resolved by increasing waits. The unchanged
[focused diagnostic](docs/delivery/v2-development/dev-m3b-agent-panel-diagnostic.json)
passed 5 cases at 16:09, but that timing-dependent pass did not erase the race.
The [correction summary](docs/delivery/v2-development/dev-m3b-agent-selection-fix-summary.json)
binds controlled display/description and submission to one synchronously resolved
registered role, passing the clicked ID explicitly into the existing mutation.

Clean [RED](docs/delivery/v2-development/dev-m3b-agent-selection-clean-red.json)
**3 FAIL / 4 PASS** at 16:24 becomes [GREEN](docs/delivery/v2-development/dev-m3b-agent-selection-green.json)
**7 PASS** with identical new test bytes; [nearby checks](docs/delivery/v2-development/dev-m3b-agent-selection-regression.json)
are **37 PASS**. A first new-test unsupported-matcher failure remains saved.
The deterministic catalog-replacement mutation test proves input drift; it does
not reconstruct the exact original full-suite event interleaving. Existing Agent/
job/session/chapter assertions, request authority and execution boundaries remain.
Development typecheck source drift is not final integration proof.

## 9. Full-File CI capacity remains a contract-bound blocker

Read-only review records push/PR setup **95.0/96.1 s** and pytest-to-cancellation
**1,118.6/1,116.7 s**, consistent with the unchanged **20-minute** job budget.
Progress symbols are not PASS counts; caching is not a verified remedy.
Simple File=2 sharding conflicts with mandatory File=1 reconciliation
(`.github/ci/coverage_reconcile.py:489–498`), fixed File 0 + PG 0 + PG 1 TCP
provenance (`tcp_evidence.py:187–214`) and the original assertion at
`test_tcp_evidence.py:325`, plus frozen collector/reconciler/execution hashes.
No wrapper, second reconciler, weaker assertion or budget/gate change is added.
Any acceptance-contract migration requires explicit approval.

## 10. Legacy client correction: same owners, unchanged server authority

The [source diagnosis](docs/delivery/v2-development/m3b-legacy-discovery-owner-diagnosis.md)
confirmed omitted in-memory local-host credentials on the legacy singleton and
retention of previously received private state after observed 401/403. This is
client compatibility/cache lifecycle, not evidence of unauthorized server disclosure.

The correction reuses exported `api.requestToken` and the existing React owner
in both modes. Explicit-empty captured identity, actor/collaboration scope and
packaged exclusions remain. Legacy singleton signatures stay unchanged. Opaque
keys and epoch/ABA guards fence dispatch, response and delayed-body adoption;
obsolete auth errors cannot expire a new owner. Observed 401/403, host-unavailable
denial, owner invalidation and actual permission revocation purge snapshots,
scans, hardware, paths, registrations and copied root/runtime/registration forms.
Initial loading is distinct from revocation; transient recovery remains supported.
Server host authorization, protected App/ModuleWorkspace keys, default-off labels
and V2-only consent/file gates are unchanged. No credential persistence is added.

## 11. Legacy correction evidence and fixture limits

[Verified RED](docs/delivery/v2-development/m3b-legacy-owner-red-verified.json)
**23 FAIL / 6 PASS** at 16:25 is retained. [Final focused tests](docs/delivery/v2-development/m3b-legacy-owner-green-final.json)
are **141 PASS**, including 32 new cases. The [first typecheck](docs/delivery/v2-development/m3b-legacy-owner-typecheck.json)
failed on unsupported `exact` options in a new Testing Library helper; the
[passing correction](docs/delivery/v2-development/m3b-legacy-owner-typecheck-final.json)
remains separate, without weakening an original assertion.

[Legacy HTTP fixture development](docs/delivery/v2-development/dev-m3b-legacy-http-fixture.json)
is **16 PASS**: 2 new legacy + 7 original consent + 7 file-fixture cases. It uses
isolated subprocesses, original FastAPI/TestClient routes and real synthetic files,
not external TCP/browser execution. Shared-source drift makes it development-only;
final integration includes these cases. [14-case collection](docs/delivery/v2-development/dev-m3b-legacy-browser-collection.json)
is inventory only. The original fixture `self_check` source is unchanged.

## 12. Corrected-source freeze and terminal frontend checks — 16:34 UTC

**Final update: 16:46 UTC.** All six receipts below share the corrected stable
**1,688-input** map in §1, with equal before/after maps and no drift. Their receipt
and raw-log hashes are independently verified in
[publish verification](docs/delivery/v2-development/stage-m3b-publish-verification.json),
SHA256 `16a6346ceefab97b80e5dbabe66ccb0831b240198771fb470e4878e01b60f4a4`.
This binds local evidence before publication, not the future containing commit.

| Final receipt | Actual outcome | Raw log SHA256 |
| --- | --- | --- |
| [56-file File owner range](docs/delivery/v2-development/stage-m3b-fixed-owner-file.json) | **2,127 PASS / 1,099 skips**, 352.29 s; 16:36:53 UTC. | `5944b59507a8a4876023ed58c09faa5632f2b03e33c107974c13af696fc63714` |
| [56-file real PG owner range](docs/delivery/v2-development/stage-m3b-fixed-owner-postgres.json) | **2,094 PASS / 1,132 skips**, 867.42 s; 16:45:32 UTC. | `9c20b83ff8ec1f2371b5d8b86865adad9ab6734d6034203969f8d78248412996` |
| [Full frontend](docs/delivery/v2-development/stage-m3b-fixed-full-frontend.json) | **2,040 PASS / 8 existing skips**, 266 passed / 2 skipped files; 16:32:08 UTC. | `6dfc316d1351dadfd665ea8ffde3515c9c2c928f98309b874705d62cac38a783` |
| [Build/token guard](docs/delivery/v2-development/stage-m3b-fixed-build.json) | TS/Vite and **49-file token guard PASS**. Existing large-chunk warnings: App 908.65 kB, ExperimentalWorkbench 628.01 kB. | `56cf16abd7e24db2241e88da3341553a840ded9a6fb3a241ff11268664dab134` |
| [Infrastructure/catalog](docs/delivery/v2-development/stage-m3b-fixed-infrastructure-catalog.json) | **279 PASS**, 20.02 s. | `0358bb6ddc03e9d5da656cac38fa9f8d1cb261452f8d614d0f42e18c2a3d561c` |
| [Browser collection](docs/delivery/v2-development/stage-m3b-fixed-browser-collection.json) | **7 original + 14 independent**, **INVENTORY_ONLY**. | `64c0ec09fe8f58a7085a154e43ab10c7a002800affb60ffa52433fa9770b8d95` |

Actual PostgreSQL **17.11** used fresh `v2_m3b_fixed_20261009`, OID **36708**,
empty before all **20 original migration files**. The [runtime receipt](docs/delivery/v2-development/stage-m3b-fixed-owner-postgres-postgres-runtime.json)
records PASS / stopped / completed and retained databases. Its SHA256 is
`4ba2d2cf7bba7323563af44b2496f82e3d19784e7d26ca7f4809960b624781a2`.
The [server log](docs/delivery/v2-development/stage-m3b-fixed-owner-postgres-server.log),
SHA256 `1fa543f61116973b4aa2df0901e83b8cc5601b228c4a27926435436b49dd38aa`,
records normal shutdown at **16:45:33.206 UTC**. Original opposite-profile and
actual-Windows skip policies are unchanged. Selected-owner integration does not
execute all product nodes, a browser, real model or user Windows acceptance.

## 13. Catalog, written inventory and preserved source contracts

[Catalog generation](docs/delivery/v2-development/catalog-9c6ce5e2c3b4.json)
uses staged tree `9c6ce5e2c3b43bee0c42dc13cc48703d5f7547e3`. It retains
**2,111 operations, +0/−0 versus published M3-A**, with unchanged app fingerprint
`6a6bfbc80bf2ee2f5d6f536f6d038cf43ec25c92ec357b5aee768a04dbfa83e7`.
All four output hashes match. This is source inventory, not endpoint execution.

[Actual collection review](docs/delivery/v2-development/stage-m3b-fixed-collection-review.json)
followed by the separate [manifest write](docs/delivery/v2-development/stage-m3b-fixed-manifest-extension.json)
records **10,380 nodes = 10,362 M3-A + 18** (9 projection + 7 file-fixture +
2 legacy-fixture cases). Written V2 manifest SHA256:
`904bb2488f729857af98ef7abccacf90f664aea53eb49a48f8262f764141b522`.
Both receipts state **INVENTORY_ONLY / tests_executed=false**. The distinct
9,151-node frozen baseline has 1,229 cumulative additions, not this slice's delta.

[Independent final source/inventory verification](docs/delivery/v2-development/stage-m3b-fixed-inventory-verification.json),
SHA256 `cc8f39a86097b4d0020d9e82ab1eb532e96556be6a960a096b863d9ae129a7a4`,
records zero source-digest errors, original ordered nodes/skips/gates preserved,
and all **18 old browser entries ordered within 21**. Parent tracked tests,
CI Python/workflows, protected V2 config/shell/primitives/tokens/frozen manifest
and original fixture `self_check` remain byte-identical. M3-B's publication and
exact-SHA hosted/browser acceptance remain the next evidence boundary.
