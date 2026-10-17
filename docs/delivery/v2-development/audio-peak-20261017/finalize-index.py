"""Read-only evidence audit plus final index write; no product import or execution."""
import hashlib
import json
from pathlib import Path
import subprocess
root=Path.cwd()
assert root.name=='studio-audio-normalize'
d=root/'docs/delivery/v2-development'
folder=d/'audio-peak-20261017'
head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
assert head=='e1e66cedeb7a140b6894850bc21a1e5ac7e06c16'
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
primary=json.loads((folder/'primary-evidence-index.json').read_text())
review=json.loads((d/'audio-peak-review-20261017/independent-evidence-index.json').read_text())
frozen=primary['source_sha256']; assert len(frozen)==2590
assert len(review['receipts'])==13
receipts=[]
for item in review['receipts']:
    path=root/item['path']; value=json.loads(path.read_text())
    assert sha(path)==item['sha256']
    assert value['head']==head and value['cwd']==str(root)
    assert value['status']=='PASS' and value['exit_code']==0
    assert not value['sources_changed_during_check']
    assert value['source_sha256']==value['source_sha256_before']==frozen
    assert sha(root/value['log'])==value['log_sha256']==item['log_sha256']
    receipts.append({**item,'log':value['log']})
for path,digest in frozen.items(): assert sha(root/path)==digest,path
fixture=root/'tests/fixtures/studio_audio_peak_omission_v1.json'
assert sha(fixture)=='d818680bf5895014cd400671d5ed95d3ca61a8886cec4e58c2f8dfcc0c4dcc16'
observations=[]
for path in sorted((folder/'observations').glob('*.json')):
    original=root/'.runtime/v2-checks/audio-peak-new-backend-r1/pytest'/path.stem/'peak-observation.json'
    assert original.read_bytes()==path.read_bytes()
    value=json.loads(path.read_text()); measurement=value['measurement']; proof=measurement['peak_normalization']
    assert value['source']==proof['source_sha256']
    assert proof['selected_frames']==proof['output_frames']
    observations.append({'path':str(path.relative_to(root)),'sha256':sha(path),'original_owned_path':str(original.relative_to(root)),
        'source_sha256':value['source'],'candidate_sha256':measurement['output_sha256'],'selected_pcm_sha256':proof['selected_pcm_sha256'],
        'output_pcm_sha256':proof['output_pcm_sha256'],'selected_frames':proof['selected_frames'],'output_frames':proof['output_frames'],
        'source_peak_s16':proof['source_peak_s16'],'output_peak_s16':proof['output_peak_s16']})
assert len(observations)==5
runtime=review['runtime_changes']
newtests=['tests/test_v2_audio_peak_contract.py','tests/test_v2_audio_peak_api.py','tests/test_v2_audio_peak_cpu.py','frontend/src/creative/studioAudioPeak.additive.test.tsx']
changed=subprocess.check_output(['git','diff','--name-only'],text=True).splitlines()
assert sorted(changed)==sorted(runtime)
# Bind all unique feature evidence, including raw launches and pre-edit capture.
artifacts={str(path.relative_to(root)):sha(path) for path in sorted(d.glob('audio-peak*')) if path.is_file()}
for directory in (folder,d/'audio-peak-review-20261017'):
    for path in sorted(directory.rglob('*')):
        if path.is_file() and path.name!='complete-evidence-index.json': artifacts[str(path.relative_to(root))]=sha(path)
result={'status':'PASS_COMPLETE_SCOPED_EVIDENCE_CLOSURE','baseline_head':head,'current_head':head,'branch':'work/dot-audio-normalize-20261017',
    'source_count':len(frozen),'source_map_reference':'docs/delivery/v2-development/audio-peak-20261017/primary-evidence-index.json',
    'source_map_reference_sha256':sha(folder/'primary-evidence-index.json'),'runtime_and_additive_tests':{path:sha(root/path) for path in runtime+newtests},
    'frozen_fixture':{'path':str(fixture.relative_to(root)),'sha256':sha(fixture)},'receipts':receipts,'observations':observations,'artifact_sha256':artifacts,
    'results':{'new_backend':'95 passed, 48 PostgreSQL-only deselected','legacy_backend':'268 passed, 148 PostgreSQL-only deselected',
        'primary_frontend':'360 passed, 15 suites','independent_backend':'171 passed, 48 PostgreSQL-only deselected',
        'independent_frontend':'170 passed, 4 suites','counts_overlap':True,'forced_typescript':'PASS','frontend_vite_build':'PASS','ui_token_guard':'PASS 52 files'},
    'limitations':['PCM16 WAV only, same source/output rate and channels, integral selected frames only','Sample-peak only, not LUFS or true-peak',
        'PostgreSQL deselected; browser visual/geometry and native desktop not run','Five known previously reproduced audio-listing precedence failures not run here and still unresolved',
        'Public wheel/sdist packaging not built for this source; parent must run on integrated branch','No live provider/model, subjective quality, full repository/product acceptance, commit, merge, push or release claim']}
path=folder/'complete-evidence-index.json';path.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'path':str(path.relative_to(root)),'sha256':sha(path),'source_count':len(frozen),'receipts':len(receipts),'observations':len(observations),'artifacts':len(artifacts)},indent=2))
