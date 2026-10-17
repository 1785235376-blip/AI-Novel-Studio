from pathlib import Path
import hashlib,json
R=Path.cwd(); D=R/'docs/delivery/v2-development/parallel-integration-wave2-independent-20261017'
freeze=json.loads((R/'docs/delivery/v2-development/parallel-integration-wave2-20261017/release-freeze.json').read_text())
receipts=[]
for stage in ('origin-before','backend','comic-golden','ui','origin-after'):
    p=R/f'docs/delivery/v2-development/wave2-independent-{stage}-r1.json'
    r=json.loads(p.read_text())
    assert r['status']=='PASS' and not r['sources_changed_during_check']
    assert r['source_sha256_before']==r['source_sha256']==freeze['source_sha256']
    receipts.append(str(p.relative_to(R)))
assert json.loads((D/'archive-audit.json').read_text())['status']=='PASS_INDEPENDENT_ACTUAL_ARCHIVE_HASH_AUDIT'
report="""# Independent second-wave integration review

Result: PASS on frozen source b5f52c823b4df58ffe69ec309bfc2fc0e4a114fe. No blocking source-interaction finding.

- All four source commits are retained in Git lineage. Original tests, frozen fixtures, and historical documentation were preserved.
- The one new cross-feature test uses the original generic GenerationRepository save, actual persistent leaf-lock housekeeping, original backup/restore, read-only restored verifier, and fresh exact repository get. No mocks or claimed application readiness.
- Director publication remains private opt-in through original owners; its envelope represents the pre-commit historical checkpoint, not live authority at physical replacement or durable review/adoption authority.
- Comic omitted alignment fields remain omitted and original centered floor arithmetic is preserved. Legacy approved JSON/report/state/review digest remain unchanged without reapproval; PNG and ZIP are byte-exact.
- Storage verification remains byte-only, read-only, offline and trusted-tree scoped. No database/application compatibility or switching is claimed.

## Independent execution

- Backend: 270 passed, 1 skipped, 86 deselected. The skip is the original unavailable pinned-font case; deselections are PostgreSQL-only cases.
- UI: 147 passed in 11 files, covering membership, original interactive history/editor, comic framing/original editor/arrangement, and Director controls/review.
- Natural startup and actual original-runner child origin checks passed before/after, using the sole clean interpreter and normal conftest.
- Five independent original-runner receipts preserve the identical 2,609-path source map. Full before/after freeze checks preserve all 12,113 tracked file hashes.
- Independently read actual two wheels and two sdists without extraction or installation. Archive hashes, complete retained payload inventories, and every source entry in each build receipt match current source, including all changed runtime modules.

## Remaining limits

Five previously identified original Audio listing diagnostic-precedence failures are excluded, unresolved, and not claimed passing. No live provider, PostgreSQL, browser/native Windows, push, main merge, release, or install was performed. This is an independently verified meaningful subset, not a full-suite claim.

Commands and exact output are retained in run.sh, launch logs, archive-audit.json/log, and the wave2-independent-*-r1 raw receipts/logs.
"""
(D/'report.md').write_text(report)
paths=sorted([p for p in D.iterdir() if p.is_file() and p.name!='evidence-index.json']+
             [R/q for q in receipts]+[R/q.replace('.json','.log') for q in receipts])
index={'status':'PASS_INDEPENDENT_REVIEW','source_head':freeze['head'],
       'runner_receipts':receipts,'source_map_paths':2609,'tracked_paths':12113,
       'backend':{'passed':270,'skipped':1,'postgres_deselected':86},
       'frontend':{'files':11,'passed':147},
       'files':{str(p.relative_to(R)):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths}}
(D/'evidence-index.json').write_text(json.dumps(index,indent=2)+'\n')
print(json.dumps({k:v for k,v in index.items() if k!='files'}))
