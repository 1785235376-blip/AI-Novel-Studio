import hashlib,json
from pathlib import Path
root=Path.cwd(); out=root/'docs/delivery/v2-development/creative-binding-origin'; records=[]
for kind in ('wheel','sdist'):
    for index in (0,1):
        name=f'public-{kind}{index}'; directory=root/'.runtime/creative-binding-packaging-r1-pytest'/name
        receipt=json.loads((directory/f'{kind}-receipt.json').read_text())
        artifacts=list((directory/('wheels' if kind=='wheel' else 'sdists')).glob('*.whl' if kind=='wheel' else '*.tar.gz'))
        assert len(artifacts)==1
        artifact=artifacts[0]; actual=hashlib.sha256(artifact.read_bytes()).hexdigest()
        assert actual==receipt['artifact_sha256']
        source={row['source_path']:row['sha256'] for row in receipt['files']}
        new='app/creative/director_binding.py'
        assert source[new]==hashlib.sha256((root/new).read_bytes()).hexdigest()
        records.append({'name':name,'artifact':str(artifact.relative_to(root)), 'artifact_sha256':actual,
            'new_module_sha256':source[new],'payload_file_count':len(source),
            'saved_receipt':str((out/'artifacts'/name/f'{kind}-receipt.json').relative_to(root)),
            'receipt_sha256':hashlib.sha256((directory/f'{kind}-receipt.json').read_bytes()).hexdigest(),
            'stage_receipt_sha256':hashlib.sha256((directory/'stage-receipt.json').read_bytes()).hexdigest()})
(out/'artifact-hashes.json').write_text(json.dumps({'status':'PASS_REAL_OFFLINE_ARTIFACTS','artifacts':records},indent=2)+'\n')
print(json.dumps(records,indent=2))
