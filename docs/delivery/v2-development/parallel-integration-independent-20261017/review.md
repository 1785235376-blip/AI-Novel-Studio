# Independent four-feature integration review

Verdict: PASS for this bounded combined integration and offline PUBLIC artifact review. This is not full V2 or release acceptance.

Frozen HEAD: `39ba1c7bc6d8438cc7c7d59f5767ba67f97aca0a`; tree: `adac601f4299c190507012e7dad984c2095c0ff5`.

## Independent findings

- Runtime/test paths remain exact blobs from positioned canvas `6ea323c087ac88ad280852b614c7bb54f4170dd2`, Audio sample peak `918b816e928195e937edbac318d60b60cc0cc36d`, Prompt receipt reopening `f193bb43c2bfc8223119314d073f076c4df6d541`, and terminology portability `17d64dcd489f52211ac02869fe0616f7e3539259`. Canvas inventory reconciliation `c61a5ebac07e0e7f06e13863eeb6de10e340d94f` remains intact.
- No baseline path was deleted. All 8,536 baseline docs and all original tests remain unchanged. Independent final hashing matched all 11,773 tracked files to the primary pre-run guard. Untracked new review evidence is separate.
- Fresh clean-Python natural-startup and original-runner child origin proof passed. Independent tests ran serially only after primary heavy gates completed, with original runner/configuration, one UI worker, no UI cache, owned File basetemp, no installed packages and no PostgreSQL.
- Backend: 245 passed, 117 PostgreSQL cases deselected, across 9 modules: new Audio peak CPU/contract/API, terminology portability, original edition owner and mounted owner, original graph persistence/additive persistence/schema authority. The existing Starlette/httpx deprecation and GlossaryDocument schema-shadow warnings remain.
- UI: 146 passed across 8 suites: three positioned-canvas suites, Audio peak, original Audio fades, Prompt receipt reopening and exact settlement, terminology portability. Counts overlap primary execution and must not be added to its totals.
- All 11 primary/independent integration receipts have the same complete 2,600-path source map, stable before/after, current file hashes, frozen HEAD and verified raw-log hashes. Feature-branch receipts have their distinct original declared maps and are not represented as combined-tree proof.
- PUBLIC manifest contains the new terminology module exactly once and has SHA256 `c54c87073dbd7c09d4844c6b9884c1a466491b3a9e86064511fa1983acbc9178`. Original runner SHA256 remains `64cf16c26412c5a1e36a1d4fb799519111ad409f7594ae15aa0b158e53396cd5`.
- Independently opened all four actual primary-built archives without extracting or installing: two wheels each have 510 source rows; two sdists each have 511. Every source-row payload hash equals its archive receipt and integrated current source. All five changed backend modules are present. Archive SHA256 values match their build receipts; duplicate members and special tar entries are absent; private extension namespace is absent. Archive bytes and exact names are recorded in evidence-index.json.

## Evidence

- `evidence-index.json`: complete shared source map, all 11 exact receipt/log hashes and commands, four archive byte-audit records, Git and PUBLIC guards.
- `audit.py` / `audit.log`: read-only final closure method and result.
- `run.sh` / `launcher.log`: exact independent serial invocation and output.
- `natural-startup.json`, `input-guards.sha256`: clean startup and separate manifest/runner guard.
- Original runner outputs alongside this directory: `parallel-integration-independent-{origin,backend,ui}-r1.json` and matching `.log` files.

## Boundaries

The five previously baseline-reproduced Audio listing-error-precedence failures remain excluded and unresolved; there is no global-green claim. No real PostgreSQL, browser/visual geometry, Windows/native, hosted CI, provider/model, full Audio, professional canvas, language-quality, security, full V2 or release acceptance. No main push, code/test edits, dependency installs or new packaging builds were performed by this reviewer. Canonical feature inventory reconciliation is a separate pending parent-owned action and is not certified complete here.
