"""Final supplemental receipt/source/hash closure; no product imports."""
import hashlib, json, pathlib, runpy
R = pathlib.Path.cwd()
E = R / 'docs/delivery/v2-development'
D = E / 'parallel-integration-wave3-canvas-supplement-20261017'
P = E / 'parallel-integration-wave3-20261017'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
runpy.run_path(str(D / 'check-freeze.py'))
f = json.loads((D / 'release-freeze.json').read_text())
records = {}
for stage in ['origin-before','ui','type','build','token','archive','origin-after']:
    path = E / f'wave3-canvas-supplement-{stage}-r1.json'
    r = json.loads(path.read_text())
    assert r['status'] == 'PASS' and r['exit_code'] == 0
    assert r['head'] == f['head'] and not r['sources_changed_during_check']
    assert r['source_sha256_before'] == r['source_sha256'] == f['source_sha256']
    assert sha(R / r['log']) == r['log_sha256']
    records[stage] = {'receipt': path.relative_to(R).as_posix(), 'sha256': sha(path), 'log': r['log'], 'log_sha256': r['log_sha256']}
old = json.loads((P / 'complete-index.json').read_text())
assert old['head'] == f['accepted_backend_head']
for p, h in old['files'].items(): assert sha(R / p) == h, p
archive = json.loads((D / 'archive-audit-r1.json').read_text())
assert archive['current_head'] == f['head'] and archive['prior_packaging_head'] == f['accepted_backend_head']
assert len(archive['archives']) == 4
for a in archive['archives']: assert sha(R / a['archive']) == a['sha256']
result = {'status': 'PASS_FRONTEND_ONLY_SUPPLEMENT', 'head': f['head'], 'tree': f['tree'], 'source_count': len(f['source_sha256']), 'tracked_count': len(f['tracked_sha256']), 'backend_paths_byte_identical': f['backend_paths_byte_identical'], 'backend_tests_rerun': False, 'packaging_tests_rerun': False, 'archive_rebuilt': False, 'historical_accepted_head': f['accepted_backend_head'], 'historical_complete_index_sha256': sha(P / 'complete-index.json'), 'receipts': records, 'archive_audit_sha256': sha(D / 'archive-audit-r1.json')}
(D / 'terminal-audit.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k:v for k,v in result.items() if k != 'receipts'}, indent=2))
