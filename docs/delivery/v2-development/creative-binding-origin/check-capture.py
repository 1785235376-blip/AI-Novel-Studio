import hashlib,json
from pathlib import Path
root=Path.cwd(); out=root/'docs/delivery/v2-development'; rows={}
for label in ('creative-binding-origin-r1','creative-binding-baseline-capture-r1','creative-binding-baseline-fixture-r1'):
    r=json.loads((out/(label+'.json')).read_text())
    assert r['status']=='PASS' and r['exit_code']==0 and not r['sources_changed_during_check']
    assert r['source_sha256_before']==r['source_sha256']
    assert r['head']=='e011a0de0a21ddb2833b2689d76caf917165e706'
    assert hashlib.sha256((root/r['log']).read_bytes()).hexdigest()==r['log_sha256']
    rows[label]=r
base=rows['creative-binding-baseline-capture-r1']['source_sha256']
assert base==rows['creative-binding-origin-r1']['source_sha256']
current=rows['creative-binding-baseline-fixture-r1']['source_sha256']
assert {k for k in set(base)|set(current) if base.get(k)!=current.get(k)}=={'tests/fixtures/creative_binding_legacy_requests.json'}
assert all(hashlib.sha256((root/k).read_bytes()).hexdigest()==v for k,v in current.items())
fixture=root/'tests/fixtures/creative_binding_legacy_requests.json'
assert fixture.read_bytes()==(out/'creative-binding-origin/captured-legacy-requests.json').read_bytes()
summary={'status':'PASS_BASELINE_SOURCE_FREEZE','head':r['head'],'baseline_source_count':len(base),
    'frozen_fixture_source_count':len(current),'all_runner_source_brackets_unchanged':True,
    'only_between_run_addition':'tests/fixtures/creative_binding_legacy_requests.json',
    'fixture_sha256':hashlib.sha256(fixture.read_bytes()).hexdigest(),
    'receipt_sha256':{name:hashlib.sha256((out/(name+'.json')).read_bytes()).hexdigest() for name in rows}}
(out/'creative-binding-origin/baseline-source-freeze.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
