"""Read-only pre-gate freeze check; no product imports."""
import hashlib,json,pathlib,runpy,subprocess
R=pathlib.Path.cwd(); D=R/'docs/delivery/v2-development/parallel-integration-wave3-20261017'
f=json.loads((D/'release-freeze-r2.json').read_text())
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==f['head'],'HEAD drift'
assert not subprocess.check_output(['git','diff','HEAD','--name-only'],text=True).strip(),'tracked source drift'
for p,h in f['tracked_sha256'].items(): assert hashlib.sha256((R/p).read_bytes()).hexdigest()==h,p
assert runpy.run_path(str(R/'scripts/run_v2_checks.py'))['source_snapshot'](R)==f['source_sha256'],'runner source map drift'
print(json.dumps({'status':'PASS_FREEZE','head':f['head'],'tracked_paths':len(f['tracked_sha256']),'source_paths':len(f['source_sha256'])}))
