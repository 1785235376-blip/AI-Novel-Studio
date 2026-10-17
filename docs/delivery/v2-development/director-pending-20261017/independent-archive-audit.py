"""Independent stdlib archive byte audit; no product imports, copies, or extraction."""
from pathlib import Path, PurePosixPath
import base64, csv, hashlib, io, json, tarfile, zipfile
ROOT=Path.cwd().resolve()
D=ROOT/'docs/delivery/v2-development/director-pending-20261017'
BASE=ROOT/'.runtime/v2-checks/director-pending-packaging-r1/pytest'
manifest=ROOT/'packaging/public-build.json'
changed=('app/creative/generation.py','app/creative/director_binding.py','app/creative/director_terminal_evidence.py','app/creative/proposals.py','app/repositories/generation_repository.py')
sha=lambda data: hashlib.sha256(data).hexdigest()
index=json.loads((D/'packaging-evidence/index.json').read_text())
assert index['manifest_sha256']==sha(manifest.read_bytes())
receipts=sorted({p.resolve(strict=True) for pattern in ('public-*/wheel-receipt.json','public-*/sdist-receipt.json') for p in BASE.glob(pattern)})
assert len(receipts)==4
assert [p.name for p in receipts].count('wheel-receipt.json')==2
assert [p.name for p in receipts].count('sdist-receipt.json')==2
results=[]
for receipt_path in receipts:
    assert receipt_path.is_relative_to(BASE.resolve())
    receipt=json.loads(receipt_path.read_text())
    kind=receipt_path.stem.removesuffix('-receipt')
    archive=receipt_path.parent/(kind+'s')/receipt['artifact']
    checksum=sha(archive.read_bytes())
    assert checksum==receipt['artifact_sha256']
    prior=next(x for x in index['archives'] if x['archive']==archive.relative_to(ROOT).as_posix())
    assert prior['sha256']==checksum
    if kind=='wheel':
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None
            names=z.namelist(); assert len(names)==len(set(names))
            payload={n:z.read(n) for n in names if not n.endswith('/')}
        record_names=[n for n in payload if n.endswith('.dist-info/RECORD')]; assert len(record_names)==1
        for name, digest, size in csv.reader(io.StringIO(payload[record_names[0]].decode())):
            assert name in payload
            if digest:
                assert digest=='sha256='+base64.urlsafe_b64encode(hashlib.sha256(payload[name]).digest()).rstrip(b'=').decode()
                assert int(size)==len(payload[name])
    else:
        with tarfile.open(archive,'r:gz') as t:
            members=t.getmembers(); names=[m.name for m in members]
            assert len(names)==len(set(names))
            assert all(m.isdir() or m.isfile() for m in members)
            payload={m.name:t.extractfile(m).read() for m in members if m.isfile()}
    assert all(not PurePosixPath(n).is_absolute() and '..' not in PurePosixPath(n).parts for n in names)
    included={e['source_path']:e for e in receipt['files']}
    assert len(included)==len(receipt['files'])
    assert all(n in included for n in changed)
    for source, entry in included.items():
        source_path=(ROOT/source).resolve(strict=True)
        assert source_path.is_relative_to(ROOT)
        assert entry['path'] in payload
        assert sha(source_path.read_bytes())==entry['sha256']==sha(payload[entry['path']])
    expected_inventory=json.loads((D/'packaging-evidence'/receipt_path.parent.name/'payload-inventory.json').read_text())
    actual_inventory={n:{'size':len(v),'sha256':sha(v)} for n,v in payload.items()}
    assert expected_inventory==actual_inventory
    results.append({'kind':kind,'archive':archive.relative_to(ROOT).as_posix(),'sha256':checksum,'all_source_payloads_verified':len(included),'all_archive_members_verified':len(payload),'changed_module_sha256':{n:sha(payload[included[n]['path']]) for n in changed}})
result={'status':'PASS_INDEPENDENT_ACTUAL_ARCHIVE_AUDIT','archive_count':len(results),'archives':results,'manifest_sha256':sha(manifest.read_bytes()),'audit_script_sha256':sha(Path(__file__).read_bytes()),'imports_product':False,'installs':False,'extracts':False,'copies_archives':False}
(D/'independent-archive-audit-r1.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
