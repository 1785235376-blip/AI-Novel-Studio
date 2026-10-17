"""Read-only stdlib archive/source verification; never imports product code."""
from pathlib import Path
from hashlib import sha256
import json, zipfile, tarfile
root=Path.cwd()
base=root/'docs/delivery/v2-development'
def digest(p): return sha256(p.read_bytes()).hexdigest()
index=json.loads((base/'creative-lifecycle-origin/artifact-hashes.json').read_text())
results=[]
for item in index['artifacts']:
    path=root/item['artifact']; assert digest(path)==item['artifact_sha256']
    receipt_path=root/item['saved_receipt']; assert digest(receipt_path)==item['receipt_sha256']
    receipt=json.loads(receipt_path.read_text()); assert receipt['artifact_sha256']==digest(path)
    stage_path=receipt_path.parent/'stage-receipt.json'; assert digest(stage_path)==item['stage_receipt_sha256']
    module_hashes={}
    with (zipfile.ZipFile(path) if path.suffix=='.whl' else tarfile.open(path,'r:gz')) as archive:
        if path.suffix=='.whl':
            assert archive.testzip() is None
            names=archive.namelist(); read=archive.read
        else:
            members=archive.getmembers(); names=[m.name for m in members]
            assert not any(m.issym() or m.islnk() for m in members)
            def read(name):
                stream=archive.extractfile(name); assert stream is not None
                return stream.read()
        assert len(names)==len(set(names))
        assert not any('/../' in n or n.startswith('/') for n in names)
        for row in receipt['files']:
            actual=sha256(read(row['path'])).hexdigest()
            assert actual==row['sha256'],row['path']
            source=root/row['source_path']
            if source.exists() and row['source_path'] in {'app/jobs.py','app/model_execution.py','app/creative/director_binding.py'}:
                assert actual==digest(source),row['source_path']; module_hashes[row['source_path']]=actual
        assert module_hashes['app/creative/director_binding.py']==item['new_module_sha256']
        assert set(module_hashes)=={'app/jobs.py','app/model_execution.py','app/creative/director_binding.py'}
    results.append({'artifact':item['artifact'],'sha256':digest(path),'payload_hashes_verified':len(receipt['files']),'module_hashes':module_hashes,'rebuilt':False})
checks=[]
for name in ('origin-r2','backend-r1','packaging-r1','types-r1','build-r1','tokens-r1','ui-r1'):
    path=base/f'creative-lifecycle-{name}.json'; receipt=json.loads(path.read_text())
    assert receipt['status']=='PASS' and receipt['exit_code']==0
    assert not receipt['sources_changed_during_check']
    assert receipt['source_sha256']==receipt['source_sha256_before']
    assert digest(root/receipt['log'])==receipt['log_sha256']
    for source, expected in receipt['source_sha256'].items(): assert digest(root/source)==expected,source
    checks.append({'receipt':str(path.relative_to(root)),'source_count':len(receipt['source_sha256']),'source_maps_equal':True,'current_sources_match':True,'log_hash_matches':True})
assert digest(root/'tests/fixtures/creative_binding_legacy_requests.json')=='640ca3823d83a378b9018a180957d375b9cef6b524f2e527f7e731236cfd90ac'
assert (root/'packaging/public-build.json').read_bytes()==(root.parent/'studio-creative-binding/packaging/public-build.json').read_bytes()
output={'status':'PASS_INDEPENDENT_READ_ONLY_ARTIFACT_AND_RECEIPT_AUDIT','artifacts':results,'primary_receipts':checks,'golden_fixture_unchanged':True,'public_manifest_identical_to_foundation':True,'artifact_rebuilds':0}
(base/'creative-lifecycle-independent-artifact-audit.json').write_text(json.dumps(output,indent=2)+'\n')
print(json.dumps({'status':output['status'],'artifacts':len(results),'primary_receipts':len(checks)}))
