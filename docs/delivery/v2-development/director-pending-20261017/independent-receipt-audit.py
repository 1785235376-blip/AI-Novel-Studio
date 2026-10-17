"""Independently verify original-runner receipts and immutable tested sources."""
import hashlib,json,subprocess
from pathlib import Path
root=Path.cwd(); d=root/'docs/delivery/v2-development'; own=d/'director-pending-20261017'
sha=lambda b:hashlib.sha256(b).hexdigest()
primary=['origin-before','new','regression','packaging','ui','type','build','token','origin-after']
independent=['origin-before','new','regression','origin-after']
records=[]; sources=None
for suffix, stages in [('r1',primary),('independent-r1',independent)]:
    for stage in stages:
        p=d/f'director-pending-{stage}-{suffix}.json'; r=json.loads(p.read_bytes())
        assert r['status']=='PASS' and r['exit_code']==0
        assert r['sources_changed_during_check'] is False
        assert r['source_sha256']==r['source_sha256_before']
        if sources is None:sources=r['source_sha256']
        assert r['source_sha256']==sources
        log=root/r['log']; assert sha(log.read_bytes())==r['log_sha256']
        records.append({'receipt':p.relative_to(root).as_posix(),'receipt_sha256':sha(p.read_bytes()),'log':r['log'],'log_sha256':r['log_sha256'],'started_utc':r['started_utc'],'finished_utc':r['finished_utc']})
for name,h in sources.items():assert sha((root/name).read_bytes())==h,name
assert subprocess.check_output(['git','diff','--name-only','HEAD','--','tests','frontend','scripts/run_v2_checks.py','packaging/public-build.json']).strip()==b''
assert (root/'packaging/public-build.json').read_bytes()==subprocess.check_output(['git','show','HEAD:packaging/public-build.json'])
assert sha((root/'tests/fixtures/creative_binding_legacy_requests.json').read_bytes())=='640ca3823d83a378b9018a180957d375b9cef6b524f2e527f7e731236cfd90ac'
archive=json.loads((own/'independent-archive-audit-r1.json').read_bytes()); assert archive['status']=='PASS_INDEPENDENT_ACTUAL_ARCHIVE_AUDIT'
result={'status':'PASS_INDEPENDENT_TERMINAL_AUDIT','head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'source_count':len(sources),'all_primary_independent_current_sources_equal':True,'existing_tests_runner_frontend_manifest_unchanged':True,'independent_receipts':records[9:],'primary_receipts_checked':len(primary),'archives_checked':archive['archive_count'],'archive_audit_sha256':sha((own/'independent-archive-audit-r1.json').read_bytes()),'audit_script_sha256':sha(Path(__file__).read_bytes())}
(own/'independent-terminal-audit-r1.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
