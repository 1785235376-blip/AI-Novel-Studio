"""Independent read-only actual archive byte audit; no extraction or imports."""
from pathlib import Path
import hashlib, json, tarfile, zipfile
R=Path.cwd()
D=R/'docs/delivery/v2-development/parallel-integration-wave2-independent-20261017'
P=R/'docs/delivery/v2-development/parallel-integration-wave2-20261017'
freeze=json.loads((P/'release-freeze.json').read_text())
index=json.loads((P/'packaging-evidence/index.json').read_text())
sha=lambda b: hashlib.sha256(b).hexdigest()
assert len(index['archives'])==4
assert sorted(x['kind'] for x in index['archives'])==['sdist','sdist','wheel','wheel']
records=[]
for entry in index['archives']:
    path=R/entry['archive']; kind=entry['kind']
    receipt_path=path.parent.parent/(kind+'-receipt.json')
    receipt=json.loads(receipt_path.read_text())
    assert sha(path.read_bytes())==receipt['artifact_sha256']==entry['sha256']
    if kind=='wheel':
        with zipfile.ZipFile(path) as z:
            names=z.namelist()
            assert len(names)==len(set(names))
            payload={n:z.read(n) for n in names if not n.endswith('/')}
    else:
        with tarfile.open(path,'r:gz') as t:
            members=t.getmembers()
            assert len(members)==len({m.name for m in members})
            assert all(m.isfile() or m.isdir() for m in members)
            payload={m.name:t.extractfile(m).read() for m in members if m.isfile()}
    inventory=json.loads((R/entry['durable_evidence']/'payload-inventory.json').read_text())
    assert set(payload)==set(inventory)
    for n,data in payload.items():
        assert inventory[n]=={'size':len(data),'sha256':sha(data)}
    assert len(payload)==entry['payload_file_count']
    included={v['source_path']:v for v in receipt['files']}
    assert len(included)==len(receipt['files'])
    for source,v in included.items():
        assert sha((R/source).read_bytes())==v['sha256']==sha(payload[v['path']])
    assert all(n in included for n in freeze['changed_runtime'])
    assert not any('studio_private_extensions' in n for n in payload)
    records.append({'archive':entry['archive'],'archive_sha256':sha(path.read_bytes()),
                    'payload_files':len(payload),'source_files_checked':len(included),
                    'changed_runtime_checked':freeze['changed_runtime']})
result={'status':'PASS_INDEPENDENT_ACTUAL_ARCHIVE_HASH_AUDIT','head':freeze['head'],
        'archives':records,'installed':False,'extracted':False,'product_imported':False}
(D/'archive-audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
