# Cloud image workflow and asset-query backend combination

The reviewed asset-query backend is now combined with the cloud image-task workflow without replacing either owner or changing the frontend layout. The combination uses a normal merge, retaining both public source histories. Main, release state, dependency manifests and lockfiles are unchanged.

## Source receipt

| Role | Commit |
| --- | --- |
| First parent: delivered cloud image workflow | `2c13ef513b61f2a8a860a4aadce9348a86122562` |
| Second parent: reviewed asset-query scale backend | `0563e561a50ebcf11022792e52237858bac80f17` |
| Common source baseline | `6ba25ad7a47ed7677c32483b5234b656a3c0c2ed` |
| Fixed combination tested here | `a8ab5935ff09476859c55a8deafbae9d057ec152` |
| Combination tree | `3493869786b674db8123be73608a23333eca7bde` |

Independent blob-level review verified the entire combination tree: all 22 imported asset paths exactly match the asset parent; every other path exactly matches the image parent. There were no merge conflicts, hidden source fixes, new execution owners or additional runtime data. The asset changes comprise 8 application files, 7 documents, 1 benchmark script and 6 test files. The original asset stage commits remain ancestors of this merge.

The cloud task resumed on October 24 after an interrupted agent turn. Inspection confirmed that the merge, File/API regression and frontend regression had already completed on the fixed combination. They were preserved, not repeated. Only the missing standard build and final delivery review were completed after resumption. All work used GitHub-derived cloud files; no Windows source, old local migration package or private local Git history was read or uploaded.

## Shared-service and interface review

The asset branch does not alter `app/api.py` or the original `ImageJobService`. Its shared `AssetLibraryService` change adds request-budget accounting to metadata/content reads only when a Studio asset-query context is active. That context has a default of `None` and is reset in `finally`. Independent original image-job execution and asset downloads do not activate it and keep their original paths. Images queried through the Studio asset endpoint are subject to the new query budgets.

The old unpaged Studio request retains `{items}` and the full existing asset projection. Explicit offset requests retain `{items,total,limit,offset,has_more}`. The new cursor mode is a separate explicit opt-in with its `asset-metadata/1` projection; the current frontend has not been switched to it. The existing Studio client still requests the old shape. Legacy image/asset APIs and image-task confirmation requests remain unchanged from the image parent. The complete frontend tree and all three dependency manifests/lock files are byte-identical to that parent.

Compatibility means normal, supported File requests and response shapes. New corpus/directory/metadata/time budgets and unsafe-path checks can return 503 in old unpaged/offset modes too; source or visibility changes can return 409. The index does not replace original-owner facts or authorization. Exact visible total still requires candidate traversal; no hard RSS limit, cross-owner atomic snapshot or wall-clock I/O guarantee is claimed.

**Windows cursor mode remains unsupported/unverified.** If the required secure POSIX key primitives are unavailable, explicit cursor requests return `503 ASSET_QUERY_CURSOR_UNAVAILABLE`. A Linux simulation verified that the old unpaged/offset requests remain available before and after that refusal. This is not actual Windows execution or a general Windows acceptance claim. No platform-security workaround was added.

## Independent asset-parent evidence: overlapping groups

These three completed groups apply to fixed asset parent `0563e561`, before combination. Their counts overlap and **must not be added together**, or substituted for the author's separately reported 191-test run.

| Recorded group | Result | Coverage and limits |
| --- | --- | --- |
| `original_six_refusal_counterexamples` | 6 passed, 6.03s | No-grant plus invalid kind/limit, missing branch, revoked membership, disabled local feature and missing local project. Original rejection statuses were `403,403,400,403,404,404`; no content/total was exposed. |
| `small_real_file_route_group` | 60 passed, 9.58s | Original query, authority and indexed-query groups; selected cursor traversal, visible totals, query/scope/permission changes and old response compatibility; one unsupported-key-primitives case. This was not the full cursor codec or process-recovery suite. |
| `independent_missing_primitives_and_index_rebuild` | 3 passed, 5.34s | Linux simulation of unavailable cursor key primitives, plus missing and synthetically corrupted derived SQLite rebuilding through original routes. Canonical source bytes/size/inode/mtime remained unchanged. The first case overlaps the 60-test group. This was not a power-loss, real Windows or hardware-failure experiment. |

The original dependency probe produced setup errors because the selected existing Python environment lacked `jsonschema`. It reached no product assertions. Appending an already installed runtime dependency directory resolved that environment issue; nothing was installed. These records retain the initial error instead of presenting it as a product failure or hiding it.

## Actual combination verification

| Check at fixed `a8ab5935` | Result |
| --- | --- |
| Real File/API combination | **78 passed**, 3 existing warnings, 12.17s; exit 0 |
| Frontend targeted regression | **430 passed**, 22 files, one worker, 29.27s; exit 0 |
| Standard `corepack pnpm build` | **PASS**, `tsc -b && vite build`, exit 0; Vite 8.14s, total build process 48.025s |
| Independent tree/provenance and shared-contract review | **PASS** within the stated scope |
| Dependency/source mutation during verification | None; existing frozen dependencies reused |

The 78 File/API cases comprise 4 original image queue, 3 image candidate protocol, 9 explicit image execution, 37 asset query, 8 authority, 9 indexed query, 3 independent compatibility/rebuild, and 5 cases from four selected cursor test functions. The estimate before collection was 76. The actual collection includes two derived-index recovery cases subsequently added to the private independent test file, so the retained XML/log records correctly report **78**, not 76. The authority group already covers the original six rejection combinations; they were not collected again as another external group.

Image execution tests use the original adapter with an injected in-memory synthetic transport. Candidate/download tests use known synthetic files and explicit fixture states. They do not establish real inference, generation quality, actual human approval or continuous authorization. No provider/GPU/paid model, acceptance/ingestion, restricted media safety review, PostgreSQL, 79-process/SIGKILL recovery stress or browser/geometry acceptance was run for this combination. The known browser sandbox-helper ownership block remains, without a bypass.

The only formatting finding is an extra blank line at EOF in imported `tests/test_studio_asset_query.py:282`, already present in the asset parent. It is retained to preserve the exact imported blob. Consequently, the full parent-to-combination `git diff --check` reports that inherited warning; it is not described as clean. There is no functional conflict. Build retains its existing large-chunk warning.

Exact commands, application import paths, hashes, environment receipts and results remain in cloud-only `checkpoint-round7.json`, `combined-file-review/command.json`, `combined-file-review/results.xml`, `round7-frontend-tests-result.json`, `round7-frontend-build-result.json` and independent audit records. Raw logs, test stores, index/key material, dependencies and build outputs are excluded from Git. Repeating a test must use a fresh test directory rather than deleting retained evidence.

## Publication and next capability boundary

Delivery targets the existing `cloud/canvas-task-20261023` branch by normal fast-forward push after verifying its expected remote HEAD. The final source receipt is the merge above; a following delivery-document commit does not change tested application/test bytes. Remote HEAD and the final commit's CI status are checked after publication and recorded in the cloud checkpoint. Local tests/build passing is not a claim that GitHub CI ran or passed.

Manual candidate review and adoption remain a separate next slice. Current approved assets can be read through their original owner, but the Rebuild node has no asset-adoption field or shared versioned mapping, and current preview has no successful-load acknowledgement. A browser-only ID association could be designed separately and must not be called server approval or shared-canvas adoption. Full adoption requires an explicit mapping to the existing canvas owner, real current asset version/digest and reviewed-content/permission/graph preconditions. Pending network-only candidates cannot be treated as viewed; no proxy, automatic accept or alternate media route was added here.

This is a combined source handoff, not whole-product acceptance, an actual Windows/PostgreSQL deployment or proof that unique local source/history/data can be deleted.
