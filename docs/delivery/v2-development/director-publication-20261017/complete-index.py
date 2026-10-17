"""Complete retained-evidence index; stdlib only, no product imports."""
import hashlib, json, pathlib, subprocess
root = pathlib.Path.cwd()
folder = root / 'docs/delivery/v2-development/director-publication-20261017'
assert root.name == 'studio-director-publication'
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
assert head == '39ba1c7bc6d8438cc7c7d59f5767ba67f97aca0a'
expected = {'origin-before', 'new', 'regression', 'file-staging', 'packaging',
    'ui', 'type', 'build', 'tokens', 'origin-after', 'independent-origin', 'independent'}
receipts = {}
frozen = None
paths = []
for label in sorted(expected):
    path = root / ('docs/delivery/v2-development/director-publication-' + label + '-r1.json')
    item = json.loads(path.read_text())
    assert item['status'] == 'PASS' and item['exit_code'] == 0 and item['head'] == head
    assert item['cwd'] == str(root) and not item['sources_changed_during_check']
    assert item['source_sha256'] == item['source_sha256_before']
    if frozen is None: frozen = item['source_sha256']
    assert item['source_sha256'] == frozen
    log = root / item['log']
    assert hashlib.sha256(log.read_bytes()).hexdigest() == item['log_sha256']
    receipts[label] = {'receipt': path.relative_to(root).as_posix(), 'log': item['log'],
        'status': item['status'], 'source_count': len(item['source_sha256']),
        'started_utc': item['started_utc'], 'finished_utc': item['finished_utc']}
    paths.extend((path, log))
assert len(frozen) == 2603
assert all(hashlib.sha256((root / p).read_bytes()).hexdigest() == sha for p, sha in frozen.items())
assert not subprocess.check_output(['git', 'diff', '--name-only', '--', 'tests', 'frontend', 'scripts'], text=True).strip()
manifest_sha = hashlib.sha256((root / 'packaging/public-build.json').read_bytes()).hexdigest()
assert manifest_sha == '353b92aff6116d873ea4402a1ef627e7899214b46ba823a9b4300ba75c5d0448'
archive_index = json.loads((folder / 'packaging-evidence/index.json').read_text())
assert archive_index['status'] == 'PASS_OFFLINE_PUBLIC_ARCHIVE_INSPECTION'
assert len(archive_index['archives']) == 4
assert sum(x['kind'] == 'wheel' for x in archive_index['archives']) == 2
assert sum(x['kind'] == 'sdist' for x in archive_index['archives']) == 2
for archive in archive_index['archives']:
    assert hashlib.sha256((root / archive['archive']).read_bytes()).hexdigest() == archive['sha256']
    assert 'app/creative/director_terminal_evidence.py' in archive['changed_modules']
for name in ('natural-startup-r1.json', 'independent-natural-startup-r2.json'):
    proof = json.loads((folder / name).read_text())
    assert proof['status'] == 'PASS_STARTUP_AND_EXPLICIT_PATHFINDER_ONLY'
    assert proof['product_or_pytest_imported'] is False
    assert proof['executable'] == '/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python'
    assert proof['probe_sha256'] == hashlib.sha256((folder / 'origin-probe.py').read_bytes()).hexdigest()
assert (folder / 'independent-natural-startup-failed-r1.log').is_file()
assert (folder / 'independent-natural-startup-failed-r1.stdout').read_bytes() == b''
paths.extend(p for p in folder.rglob('*') if p.is_file() and p.name not in {'complete-index.json', 'complete-index.log'})
files = {p.relative_to(root).as_posix(): {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'size': p.stat().st_size}
    for p in sorted(set(paths))}
result = {'status': 'PASS_COMPLETE_RETAINED_EVIDENCE', 'verification_base_head': head,
    'frozen_source_count': len(frozen), 'source_sha256': frozen,
    'all_primary_and_independent_sources_match_current': True,
    'original_tests_frontend_runner_unchanged': True,
    'manifest_sha256': manifest_sha, 'receipts': receipts, 'files': files,
    'retained_failed_attempt': {'kind': 'REVIEW_ORIGIN_LAUNCHER_ONLY',
        'cause': 'Direct script invocation used docs sys.path[0]; missing explicit app spec before product/tests.',
        'recorded_failure_note': 'docs/delivery/v2-development/director-publication-20261017/independent-natural-startup-failed-r1.log',
        'retained_stdout': 'docs/delivery/v2-development/director-publication-20261017/independent-natural-startup-failed-r1.stdout',
        'retry': 'Approved -c launcher without sys.path injection; source/tests unchanged.'},
    'boundaries': {'historical_only': True, 'default_opt_in': False, 'new_consumers': False,
        'durable_pending_review_solved': False, 'postgres_verified': False,
        'checkpoint': 'Authority and bounds sampled before original atomic replacement, not guaranteed live at physical replace.',
        'generic_file_change': 'All generation saves use pre-IO basename validation and canonical/normcase destination leaf locking.',
        'not_run': ['live provider', 'paid operation', 'PostgreSQL', 'native Windows', 'browser', 'installation', 'network', 'push']}}
(folder / 'complete-index.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'status': result['status'], 'receipt_count': len(receipts), 'indexed_evidence_files': len(files),
    'source_count': len(frozen), 'archives': len(archive_index['archives']), 'manifest_sha256': manifest_sha}, indent=2))
