"""Stdlib-only primary receipt/source/artifact index; no product imports."""
import hashlib,json
from pathlib import Path
root=Path.cwd(); out=root/'docs/delivery/v2-development'; own=out/'creative-lifecycle-origin'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
labels=('creative-lifecycle-origin-r1','creative-lifecycle-origin-r2','creative-lifecycle-backend-r1',
    'creative-lifecycle-packaging-r1','creative-lifecycle-types-r1','creative-lifecycle-build-r1',
    'creative-lifecycle-tokens-r1','creative-lifecycle-ui-r1')
receipts=[]
for label in labels:
    path=out/(label+'.json'); row=json.loads(path.read_text())
    assert row['status']=='PASS' and row['exit_code']==0 and not row['sources_changed_during_check']
    assert row['source_sha256_before']==row['source_sha256']
    log=root/row['log']; assert sha(log)==row['log_sha256']
    receipts.append({'receipt':str(path.relative_to(root)),'receipt_sha256':sha(path),
        'log':row['log'],'log_sha256':sha(log),'source_count':len(row['source_sha256']),
        'sources_unchanged':True,'command':row['command']})
current=json.loads((out/'creative-lifecycle-backend-r1.json').read_text())['source_sha256']
assert all(sha(root/k)==v for k,v in current.items())
for label in labels[1:]:
    assert json.loads((out/(label+'.json')).read_text())['source_sha256']==current
baseline=json.loads((out/'creative-binding-independent-r1.json').read_text())['source_sha256']
changed=sorted(k for k in baseline if current.get(k)!=baseline[k]); added=sorted(set(current)-set(baseline))
assert changed==['app/creative/director_binding.py','app/creative/generation.py','app/creative/proposals.py','app/jobs.py','app/model_execution.py']
assert added==['tests/creative_director_execution_fixture.py','tests/test_v2_creative_director_execution_lifecycle.py','tests/test_v2_creative_director_invocation.py']
fixture=root/'tests/fixtures/creative_binding_legacy_requests.json'; manifest=root/'packaging/public-build.json'
assert sha(fixture)=='640ca3823d83a378b9018a180957d375b9cef6b524f2e527f7e731236cfd90ac'
assert sha(manifest)=='3261cc7549d58e5d8e84c69572a9475d9c416bfd487588ecfbec472e8695d37c'
artifacts=json.loads((own/'artifact-hashes.json').read_text())['artifacts']
for artifact in artifacts: assert sha(root/artifact['artifact'])==artifact['artifact_sha256']
files={p for p in set(own.rglob('*'))|{out/(label+suffix) for label in labels for suffix in ('.json','.log')}
    if p.is_file() and p.name not in {'primary-evidence-index.json','evidence-index.json'}
    and 'independent' not in p.name}
files.update(root/name for name in ('docs/CREATIVE_DIRECTOR_INTERNAL_LIFECYCLE.md','docs/v2/frozen-capability-ledger-20261016.md'))

index={'status':'PASS_PRIMARY_SCOPED_EVIDENCE','baseline_commit':'3087f53276e42c57bf4baed2a76fbf75380d947e',
    'source_files_current':len(current),'changed_source_paths':changed,'added_source_paths':added,
    'public_manifest_sha256':sha(manifest),'frozen_fixture_sha256':sha(fixture),
    'primary':{'backend_passed':699,'backend_deselected':410,'backend_skipped':0,'packaging_passed':87,
        'packaging_skipped':0,'ui_passed':100,'ui_files':6,'types_build_tokens':'PASS'},
    'independent':'SEPARATE_REVIEW_SEE_COMPLETE_EVIDENCE_INDEX','artifacts':artifacts,'receipts':receipts,
    'limits':['internal lifecycle only; public independent Director routes/content/review/adoption closed',
        'no PostgreSQL execution','no live-provider/model-quality acceptance','no browser/native/Windows/packaged runtime acceptance',
        'no installation/merge/tag/release'],
    'files':{str(p.relative_to(root)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(files)}}
(own/'primary-evidence-index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':index['status'],'sources':len(current),'files':len(files),
    'index_sha256':sha(own/'primary-evidence-index.json')},indent=2))
