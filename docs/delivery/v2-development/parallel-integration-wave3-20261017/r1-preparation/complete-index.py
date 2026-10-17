"""Hash finalized evidence after all launchers and report writers have exited."""
import hashlib,json,pathlib
R=pathlib.Path.cwd(); E=R/'docs/delivery/v2-development'; D=E/'parallel-integration-wave3-20261017'
index=json.loads((D/'evidence-index.json').read_text())
for p,h in index['artifacts'].items(): assert hashlib.sha256((R/p).read_bytes()).hexdigest()==h,p
paths=[p for p in D.rglob('*') if p.is_file() and p.name!='complete-index.json']
paths += list(E.glob('wave3-integration-*-r1.json'))+list(E.glob('wave3-integration-*-r1.log'))
result={'status':'PASS_COMPLETE_PRIMARY_EVIDENCE','head':index['head'],'files':{p.relative_to(R).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}}
(D/'complete-index.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'status':result['status'],'files':len(result['files'])}))
