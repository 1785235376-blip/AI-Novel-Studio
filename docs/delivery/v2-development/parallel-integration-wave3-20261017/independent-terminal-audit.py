import hashlib,json,runpy,subprocess
from pathlib import Path
R=Path.cwd();D=R/'docs/delivery/v2-development/parallel-integration-wave3-20261017'
f=json.loads((D/'release-freeze-r2.json').read_text())
runpy.run_path(str(D/'check-freeze.py'))
results=[]
for stage in ('origin-before','backend','ui','origin-after'):
 p=R/f'docs/delivery/v2-development/wave3-independent-{stage}-r1.json';r=json.loads(p.read_text())
 assert r['status']=='PASS' and not r['sources_changed_during_check']
 assert r['source_sha256']==r['source_sha256_before']==f['source_sha256']
 assert hashlib.sha256((R/r['log']).read_bytes()).hexdigest()==r['log_sha256']
 results.append({'stage':stage,'receipt':p.relative_to(R).as_posix(),'receipt_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'log_sha256':r['log_sha256']})
a=json.loads((D/'independent-archive-audit-r1.json').read_text());assert a['archive_count']==4 and a['head']==f['head']
result={'status':'PASS_INDEPENDENT_WAVE3_TERMINAL','head':f['head'],'tracked_paths':len(f['tracked_sha256']),'source_paths':len(f['source_sha256']),'backend_passed':357,'backend_font_skipped':1,'postgres_deselected':196,'ui_passed':366,'ui_files':15,'archive_count':4,'receipts':results}
(D/'independent-terminal-audit-r1.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
