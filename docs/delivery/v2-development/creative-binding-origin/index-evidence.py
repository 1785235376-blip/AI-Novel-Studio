"""Read-only source checks and exact evidence-file index; never imports product."""
import hashlib,json
from pathlib import Path
root=Path.cwd(); out=root/'docs/delivery/v2-development'; own=out/'creative-binding-origin'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
labels=('creative-binding-origin-r1','creative-binding-baseline-capture-r1',
    'creative-binding-baseline-fixture-r1','creative-binding-origin-r2',
    'creative-binding-backend-r1','creative-binding-packaging-r1','creative-binding-types-r1',
    'creative-binding-build-r1','creative-binding-tokens-r1','creative-binding-ui-r1',
    'creative-binding-independent-origin-r1','creative-binding-independent-r1')
receipts=[]
for label in labels:
    path=out/(label+'.json'); row=json.loads(path.read_text())
    assert row['status']=='PASS' and row['exit_code']==0
    assert not row['sources_changed_during_check'] and row['source_sha256_before']==row['source_sha256']
    log=root/row['log']; assert sha(log)==row['log_sha256']
    receipts.append({'receipt':str(path.relative_to(root)),'receipt_sha256':sha(path),'log':row['log'],
        'log_sha256':sha(log),'source_count':len(row['source_sha256']),'sources_unchanged':True,
        'command':row['command']})
current=json.loads((out/'creative-binding-independent-r1.json').read_text())['source_sha256']
assert len(current)==2549 and all(sha(root/k)==v for k,v in current.items())
baseline=json.loads((out/'creative-binding-baseline-capture-r1.json').read_text())['source_sha256']
changed=sorted(k for k in baseline if current.get(k)!=baseline[k])
added=sorted(set(current)-set(baseline))
assert changed==['app/jobs.py','app/model_execution.py','app/repositories/generation_repository.py']
assert added==['app/creative/director_binding.py','tests/fixtures/creative_binding_legacy_requests.json',
    'tests/test_v2_creative_director_binding.py','tests/test_v2_creative_director_binding_packaging.py',
    'tests/test_v2_creative_director_binding_persistence.py']
fixture=root/'tests/fixtures/creative_binding_legacy_requests.json'
assert sha(fixture)=='640ca3823d83a378b9018a180957d375b9cef6b524f2e527f7e731236cfd90ac'
manifest=root/'packaging/public-build.json'
assert sha(manifest)=='3261cc7549d58e5d8e84c69572a9475d9c416bfd487588ecfbec472e8695d37c'
old=(root.parent/'studio-timeline-slip-delete/docs/v2/frozen-capability-ledger-20261016.md').read_text()
new=(root/'docs/v2/frozen-capability-ledger-20261016.md').read_text()
old_start='## Latest bounded checkpoint — 2026-10-17 05:08 UTC'
new_start=old_start.replace('Latest','Previous')
assert new[new.index(new_start):]==old[old.index(old_start):].replace(old_start,new_start,1)
files=set(own.rglob('*'))|set(out.glob('creative-binding-*.json'))|set(out.glob('creative-binding-*.log'))
files.update(root/p for p in ('docs/CREATIVE_DIRECTOR_BINDING_FOUNDATION.md',
    'docs/v2/frozen-capability-ledger-20261016.md','tests/fixtures/creative_binding_legacy_requests.json'))
files={p for p in files if p.is_file() and p.name!='evidence-index.json'}
index={'status':'PASS_COMPLETE_SCOPED_EVIDENCE','baseline_commit':'e011a0de0a21ddb2833b2689d76caf917165e706',
    'source_files_current':2549,'baseline_changed_source_paths':changed,'baseline_added_source_paths':added,
    'separate_public_manifest_sha256':sha(manifest),'frozen_fixture_sha256':sha(fixture),
    'prior_ledger_chronology_preserved':True,'primary':{'backend_passed':496,'backend_deselected':390,
    'packaging_passed':87,'packaging_skipped':0,'ui_passed':100,'ui_files':6,'types_build_tokens':'PASS'},
    'independent':{'passed':134,'postgres_marked_deselected':77,'skipped':0,'overlaps_primary':True,
    'report':'docs/delivery/v2-development/creative-binding-independent-review.json',
    'report_sha256':sha(out/'creative-binding-independent-review.json'),'artifacts_inspected_not_rebuilt':True},
    'limits':['standalone Director preview/dispatch unavailable','no PostgreSQL execution',
    'no browser/native/Windows/packaged-runtime acceptance','no live-provider/model-quality acceptance',
    'no full product/release acceptance'],'receipts':receipts,
    'files':{str(p.relative_to(root)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(files)}}
(own/'evidence-index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':index['status'],'indexed_files':len(files),'index_sha256':sha(own/'evidence-index.json'),
    'source_files':len(current),'fixture_sha256':sha(fixture)},indent=2))
