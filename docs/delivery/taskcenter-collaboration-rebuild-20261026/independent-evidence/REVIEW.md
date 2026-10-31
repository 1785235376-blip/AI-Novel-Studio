# Independent frozen TaskCenter review

Candidate: `97ab69b40435b18b1b5b946ad0e73774aa6da103`
Tree: `f580829b5d05ffffa303678c33655bd5bdf6492f`
Independent clone: `/workspace/scratch/20a0022d2b33/taskcenter-rebuild-independent`
Production source unchanged: `frozen-source-before.sha256` equals `frozen-source-after.sha256`.

## Evidence

- Public c2bb baseline RED: real original HTTP POST creates team rows; cursor first page returns unsupported 501 (new test expects 200). See baseline-red artifacts.
- Frozen candidate corrected run: **22 PASS**, process exit 0, no timeout, no outside-source modules. See candidate-97ab-final log/XML/summary/module manifest.
- Initial candidate developmental run: 20 PASS plus 2 incorrect test assertions comparing independently minted first-page cursors. Preserved in candidate-97ab artifacts. Corrected test compares first-page content excluding freshly minted cursor and exact response for continuation replay. These were harness defects, not implementation defects.

Tests use original trusted sessions, identity/membership service, scopes/grants repositories, original TeamService HTTP creation, real temporary File writes, mounted FastAPI routes on both prefixes, and no model execution. Independent fixtures reuse only established original repository rig; tests are not implementation-owner tests.

Covered: token revoke/register ABA; resolver replacement; membership deactivate/reactivate; original permission revoke and direct repository identical restore; role ADMIN cross-domain semantics and restore; scope retire/relink same topology; observed private row ABA; project deletion/recreation; unrelated member and irrelevant grant privacy; other actor token reuse; unrelated collection privacy; branch revision/display changes; mid-source-read revocation and restore; fresh/legacy reserved-null injection rejection. Repeated reads verify unchanged File bytes (excluding lock files).

## Assessment / boundaries

No new production defect found in examined narrow behavior. This is not cross-owner atomic transaction certification, PostgreSQL/cloud proof, real-model execution proof, or support for every TaskCenter authority. Only source-free File collaboration agent_team is the new supported case. Exact byte-for-byte out-of-band backup restoration is outside original-writer lifecycle guarantees. Before/after authorization sampling is not durable global history of every transient authorization event. No production changes, external upload, frontend/SDK, audio, asset-reference or graph changes performed by reviewer.

Supplemental source-document replacement and unmatched-row filtering probes: **2 PASS**, exit 0, no timeout or outside-source modules (`candidate-97ab-extra-final` artifacts). First supplemental attempt had missing fixture import and no test bodies executed; retained as `candidate-97ab-extra` setup-error evidence. Corrected by importing existing original rig fixture. Total final independent cases: **24 PASS** (22 + 2 disjoint cases); not added to implementation-owner or original suite counts.

The supplemental tests confirm that deleting the source document then recreating identical business collections through the original ExperimentalStore writer changes its document incarnation and rejects the old cursor, while a new first page works. Mutation of an unmatched private row through the original writer does not invalidate a filtered cursor. Both probes verify GET leaves persistent bytes unchanged.
