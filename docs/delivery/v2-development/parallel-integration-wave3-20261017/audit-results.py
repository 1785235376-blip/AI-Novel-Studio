"""PREPARED ONLY: bind actual wave3 receipts, source guards and archive evidence."""
import hashlib, json, pathlib, re, runpy
R = pathlib.Path.cwd()
E = R / 'docs/delivery/v2-development'
D = E / 'parallel-integration-wave3-20261017'
runpy.run_path(str(D / 'check-freeze.py'))
f = json.loads((D / 'release-freeze-r2.json').read_text())
receipts, summaries = {}, {}
for label in ['origin-before', 'comic-golden', 'backend', 'ui', 'type', 'build', 'token', 'packaging', 'origin-after']:
    p = E / f'wave3-integration-{label}-r2.json'
    data = json.loads(p.read_text())
    assert data['status'] == 'PASS' and data['exit_code'] == 0, label
    assert data['head'] == f['head'] and not data['sources_changed_during_check']
    assert data['source_sha256_before'] == data['source_sha256'] == f['source_sha256'], label
    log = R / data['log']
    assert hashlib.sha256(log.read_bytes()).hexdigest() == data['log_sha256']
    summaries[label] = [line.strip() for line in log.read_text().splitlines() if re.search(r'\d+ passed|Test Files|Tests\s|\d+ files|built in|chunks exceed', line)]
    receipts[label] = {'path': p.relative_to(R).as_posix(), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'log': data['log'], 'log_sha256': data['log_sha256'], 'command': data['command']}
archives = json.loads((D / 'packaging-evidence/index.json').read_text())
assert len(archives['archives']) == 4
for a in archives['archives']:
    assert hashlib.sha256((R / a['archive']).read_bytes()).hexdigest() == a['sha256']
assert json.loads((D / 'natural-startup-r2.json').read_text())['status'] == 'PASS_STARTUP_AND_EXPLICIT_PATHFINDER_ONLY'
artifacts = {p.relative_to(R).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(D.rglob('*')) if p.is_file() and p.name not in {'evidence-index.json', 'audit-results.log', 'complete-index.json'}}
result = {'status': 'PASS_SCOPED_MERGED_WAVE3', 'head': f['head'], 'tree': f['tree'], 'source_path_count': len(f['source_sha256']), 'tracked_path_count': len(f['tracked_sha256']), 'protected_old_tests': f['protected_old_tests'], 'protected_old_docs': f['protected_old_docs'], 'receipts': receipts, 'actual_log_summaries': summaries, 'artifacts': artifacts, 'archives': archives, 'known_audio_listing_failures_excluded': 5, 'full_repository_green': False}
(D / 'evidence-index.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k: result[k] for k in ['status', 'head', 'source_path_count', 'actual_log_summaries']}, indent=2))
