# Safe backend + local mixed TaskCenter cursor: reconstructed delivery

Status **PARTIAL**: scoped patches verified; combined HTTP acceptance is not fully green. This is a newly reconstructed
and reverified package, not the lost bf0 archive. See RECOVERY.md for the complete
artifact-loss and test-observer correction history.

## Fixed inputs and production scope

Safe base e5d5e4cc18414222a9034af9a09a51bb48c26459, tree37966a1b9686f41e3e5bc7c42dc52a015a0c8f83;
mixed donor f6473e307e9d0501a41dc46dd991645a437103d7, tree9aad85d79c86030dcea6445551ea7864b0f0f43e;
actual full-history common ancestor31b6cb56ba3d2fa08719cf917c2c75ee8f168c8f.

Final code/test freeze d93034821efa4f064ac680b8bfdedef86faa3b0d,
tree b9c22586cad50ac7bfd76c9ab4fd727bac770544,
app tree775a084c75dd5cfd7ccf0189060b056bf8f1c309.
Subsequent delivery commits may change documentation/evidence only.

Eight production files: the five reviewed donor files are byte-identical to the
donor. The remaining3 files add the separately authorized budget/strict request
boundary isolation. Original Store bytes/snapshot/CAS, duplicate-key validation,
identity, scopes, Export owner and canvas auth are unchanged. No limit increases,
asset query business edits, frontend/SDK, Work integration or main modifications.
See production-scope.json and WORK_HANDOFF.md.

## Fresh acceptance

Every final group uses the same d930 source/tests. Group receipts include
commands, process exit/timeout, before/after app hashes and actual loaded module
paths. Tests use synthetic File/Mock data; no private data/model/PG access.
Groups overlap: do not add their counts. Final per-group results are RESULTS.json.
Final uninstrumented results (overlapping; no sums):

| Group | New result |
|---|---|
| Request/observer/real pipeline |26passed|
| Original asset regression |192passed|
| Resource/safety + adoption auth |178passed,35skipped|
| Expanded TaskCenter/lifecycle |508passed|
| Export consumers |101passed|
| Combined real application HTTP |3passed,1failed|
| Independent review |99passed|

The one final HTTP failure is `/api/v1` warm strict asset first-page409 after
ordinary first/continuation/replay succeeded. The `/api` original-owner mixed
cursor and reopening chain passed, as did both collaboration TaskCenter cases.
This is NOT a4/4 unified acceptance result. Both API aliases have separate
passing mixed cursor HTTP and real pipelined transport tests; those do not replace
the failed complete application combination.

Independent99 covers26 reconstructed context/observer/TCP cases,53 donor cases,
and20 real POSIX process tests. Its baseline failures are preserved separately.

The real h11 pipeline test is a scope-reporting endpoint, not a business E2E
claim. The compound application HTTP test uses original owners and both mounted
aliases,32 saved consumers/540 references/six pages, strict cold/warm behavior,
single TaskCenter sources, the exact local pair, replay and process reopening.
Original collaboration TaskCenter source-free positive/refusal/revocation cases
remain; full positive collaboration asset Host authorization is not demonstrated.

## Bounded diagnostic, not replacement acceptance

One isolated diagnostic rerun of the failing `/api/v1` case passed1/1 after adding
only test-server logging at UsageBudgetError construction. The rejection did not
reproduce, no explanatory error stack was captured, and the production app files
were unchanged. The instrumentation patch/hash and complete diagnostic logs are
separate. This run does NOT erase the uninstrumented final3pass/1fail or establish
that the cause was the30-second cooperative budget. No further asset-business
repair is included. Independent failure-scope review permits only this honest
PARTIAL branch delivery, not a merge-ready or fully accepted backend claim.

## Failures and limitations retained

- Original e5 request-boundary probes:22fail/4pass; pipeline8allfail.
- Original e5 POSIX test spy:12fail/8pass because initialize was not forwarded.
  A2-line test-only correction preserves values and real original locks; final
  independent20process tests pass. The old failed extended group is retained.
- Intermediate146 compound HTTP:3pass/1fail. The /api asset continuation after
  a successful first page returned STUDIO_ASSET_USAGE_UNAVAILABLE (409).
  This run overlapped other regression work, but load is NOT established as the
  cause. No diagnostic exception stack establishes a root cause. A later pass
  does not prove this observation repaired. No budget or timeout was increased.
- Work's previous F37 refusals and Windows asset-list cursor503 remain separate
  unresolved observations. Do not infer they are this same issue or fixed.
- Only selected Linux/File behavior is evidenced. Windows, PostgreSQL, browser,
  real model/GPU and hosted CI are NOT_RUN here. Windows-only tests stay skipped.
- No RSS/CPU/lock-wait hard bound, strong full-history ABA, cross-worker cursor
  persistence, cross-owner atomic snapshot or complete dependency discovery.
  TaskCenter is not automatically covered by asset-usage HTTP budgeting.

Publication authorization is bounded to code/tests/sanitized synthetic evidence
on work/hermia-mixed-cursor-safety-20261027. This local package does not itself
assert remote upload or release readiness. No Release or main update is made.
