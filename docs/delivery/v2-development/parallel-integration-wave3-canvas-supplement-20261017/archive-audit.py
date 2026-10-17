"""Independent in-place archive and wheel RECORD audit; stdlib only, no extraction."""
import base64,csv,hashlib,io,json,tarfile,zipfile
from pathlib import Path,PurePosixPath
R=Path.cwd(); D=R/'docs/delivery/v2-development/parallel-integration-wave3-20261017'
S=R/'docs/delivery/v2-development/parallel-integration-wave3-canvas-supplement-20261017'
B=R/'.runtime/v2-checks/wave3-integration-packaging-r2/pytest'
f=json.loads((D/'release-freeze-r2.json').read_text()); idx=json.loads((D/'packaging-evidence/index.json').read_text())
sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha((R/'packaging/public-build.json').read_bytes())==idx['manifest_sha256']
receipts=sorted({p.resolve(strict=True) for pat in ('public-*/wheel-receipt.json','public-*/sdist-receipt.json') for p in B.glob(pat)})
assert len(receipts)==4 and sum(p.name=='wheel-receipt.json' for p in receipts)==2
out=[]
for p in receipts:
 assert p.is_relative_to(B.resolve())
 receipt=json.loads(p.read_text()); kind=p.stem.removesuffix('-receipt'); a=p.parent/(kind+'s')/receipt['artifact']
 h=sha(a.read_bytes()); assert h==receipt['artifact_sha256']
 original=next(x for x in idx['archives'] if x['archive']==a.relative_to(R).as_posix()); assert original['sha256']==h
 if kind=='wheel':
  with zipfile.ZipFile(a) as z:
   assert z.testzip() is None
   names=z.namelist(); payload={n:z.read(n) for n in names if not n.endswith('/')}
  records=[n for n in payload if n.endswith('.dist-info/RECORD')]; assert len(records)==1
  rows=list(csv.reader(io.StringIO(payload[records[0]].decode())))
  assert len(rows)==len({r[0] for r in rows}) and {r[0] for r in rows}==set(payload)
  for n,d,s in rows:
   if n==records[0]: assert d==s==''
   else: assert d=='sha256='+base64.urlsafe_b64encode(hashlib.sha256(payload[n]).digest()).rstrip(b'=').decode() and int(s)==len(payload[n])
 else:
  with tarfile.open(a,'r:gz') as t:
   members=t.getmembers(); names=[m.name for m in members]
   assert all(m.isdir() or m.isfile() for m in members)
   payload={m.name:t.extractfile(m).read() for m in members if m.isfile()}
 assert len(names)==len(set(names)) and all(not PurePosixPath(n).is_absolute() and '..' not in PurePosixPath(n).parts for n in names)
 included={e['source_path']:e for e in receipt['files']}; assert len(included)==len(receipt['files'])
 assert set(f['changed_runtime'])<=set(included)
 for source,e in included.items():
  src=(R/source).resolve(strict=True); assert src.is_relative_to(R.resolve())
  assert sha(src.read_bytes())==e['sha256']==sha(payload[e['path']])
  if source in f['tracked_sha256']: assert e['sha256']==f['tracked_sha256'][source]
 inventory={n:{'size':len(v),'sha256':sha(v)} for n,v in payload.items()}
 assert inventory==json.loads((D/'packaging-evidence'/p.parent.name/'payload-inventory.json').read_text())
 out.append({'archive':a.relative_to(R).as_posix(),'sha256':h,'kind':kind,'source_payloads':len(included),'members':len(payload),'wheel_record_verified':kind=='wheel'})
result={'status':'PASS_CURRENT_SOURCE_REUSE_OF_ACTUAL_ARCHIVES','prior_packaging_head':f['head'],'current_head':json.loads((S/'release-freeze.json').read_text())['head'],'archives':out,'archive_count':len(out),'no_product_imports':True,'no_extraction_install_or_archive_copy':True,'script_sha256':sha(Path(__file__).read_bytes())}
(S/'archive-audit-r1.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
