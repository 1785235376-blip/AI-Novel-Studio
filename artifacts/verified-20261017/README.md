# Verified Studio V2 archival snapshot — 2026-10-17

This archive preserves the exact original Git objects for 164 commits after PR47 (`a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3`) through `5a6f697bccf2127b1bbfd62bb422311edc8c4afe`, including tracked source, reports, and raw evidence logs. The split bundle advertises only `refs/heads/work/dot-v2-integration-wave3-20261017`. Original commit IDs, authors, timestamps, trees, and parent relationships are preserved inside the bundle.

The remote archive branch has a new, separate archival commit based on PR47. Its checked-out product tree remains PR47 plus these archive files. It does **not** publish the original 164 development commits as the archive branch's remote ancestry. PR48 is divergent and is not a substitute for the preserved history. No existing branch, PR, workflow, Release, or Tag is changed by this archival publication.

## Integrity and restoration

Run these commands in a new directory with Git installed. The repository must retain the PR47 prerequisite commit and its ancestry. The bundle is incremental, not a standalone clone. Both declared prerequisites must be available: `a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3` and its ancestor `045b865e5a003cac3333462d055f22099f6368d6`.

```sh
git clone --single-branch --branch archive/verified-studio-v2-20261017-5a6f697 https://github.com/1785235376-blip/AI-Novel-Studio.git studio-restored
cd studio-restored/artifacts/verified-20261017
sha256sum -c SHA256SUMS
cat bundle/studio.bundle.part-* > /tmp/studio-verified-5a6f697.bundle
printf '%s  %s\n' 87f2e0253fe7d5830df6d3c5fba6541d5bf9162683af7fd39b0025c3264e4789 /tmp/studio-verified-5a6f697.bundle | sha256sum -c -
cd ../..
git cat-file -e a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3^{commit}
git cat-file -e 045b865e5a003cac3333462d055f22099f6368d6^{commit}
git bundle verify /tmp/studio-verified-5a6f697.bundle
git bundle list-heads /tmp/studio-verified-5a6f697.bundle
git fetch /tmp/studio-verified-5a6f697.bundle refs/heads/work/dot-v2-integration-wave3-20261017:refs/heads/restored/verified-studio-v2-5a6f697
test "$(git rev-parse restored/verified-studio-v2-5a6f697)" = 5a6f697bccf2127b1bbfd62bb422311edc8c4afe
test "$(git rev-list --count a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3..restored/verified-studio-v2-5a6f697)" = 164
# Optional: inspect the original accepted snapshot in a separate worktree.
git worktree add ../studio-verified restored/verified-studio-v2-5a6f697
```

The reassembled bundle is exactly 25,976,069 bytes. `manifest.json` records byte counts, SHA256 hashes, Git blob IDs, and provenance. `SHA256SUMS` covers the bundle parts, four unchanged artifacts, README, and manifest.

## Scope and acceptance limits

The four PUBLIC packaging-test outputs total 6,917,837 bytes. They originated from `db6487b5eab7340433426fefcb5499122ec3d881`; subsequent backend checks reused byte-identical artifacts at `f4a6fed15cc52c0323e73f5e410e184c42bb5200`. They are not newly built from the final archival head. These are two source distributions and two Python wheels, not a signed production installer or a new Release. Archive member checks, source checks, wheel RECORD checks, and bounded secret screening do not establish full production acceptance.

Only the reviewed incremental Git bundle and the four explicitly accepted artifacts are included. Uncommitted files, other branch histories, dependencies, entire runtime trees, and the rest of the workspace are excluded. Read the original tracked reports and raw logs at the restored verified head for each test's exact scope, result, and limits. Local fixture/browser or backend results must not be presented as native Windows/GPU/inference, signing, installer/upgrade, or end-user acceptance unless their corresponding reports actually establish that result.

CI is intentionally skipped for the archival commit via `[skip ci]`; it is **not passed**. This upload adds no CI acceptance claim and does not dispatch a workflow.
