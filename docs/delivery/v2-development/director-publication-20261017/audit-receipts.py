"""Stdlib-only frozen-source and original-file preservation audit."""
import hashlib, json, pathlib, subprocess
root = pathlib.Path.cwd()
destination = root / 'docs/delivery/v2-development/director-publication-20261017'
assert root.name == 'studio-director-publication'
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == '39ba1c7bc6d8438cc7c7d59f5767ba67f97aca0a'
allowed = {'app/jobs.py', 'app/model_execution.py', 'app/creative/generation.py',
    'app/repositories/generation_repository.py', 'app/repositories/postgres/generation.py',
    'packaging/public-build.json'}
changed = set(subprocess.check_output(['git', 'diff', '--name-only'], text=True).splitlines())
assert changed == allowed, changed
old_tests = subprocess.check_output(['git', 'diff', '--name-only', '--', 'tests'], text=True).strip()
assert not old_tests
manifest = root / 'packaging/public-build.json'
assert hashlib.sha256(manifest.read_bytes()).hexdigest() == '353b92aff6116d873ea4402a1ef627e7899214b46ba823a9b4300ba75c5d0448'
original_manifest = json.loads(subprocess.check_output(['git', 'show', 'HEAD:packaging/public-build.json'], text=True))
current_manifest = json.loads(manifest.read_text())
assert current_manifest['files'] == sorted(current_manifest['files'])
assert set(current_manifest['files']) - set(original_manifest['files']) == {'app/creative/director_terminal_evidence.py'}
assert set(original_manifest['files']) - set(current_manifest['files']) == set()
current_manifest['files'] = original_manifest['files']
assert current_manifest == original_manifest
assert hashlib.sha256((root / 'scripts/run_v2_checks.py').read_bytes()).hexdigest() == '64cf16c26412c5a1e36a1d4fb799519111ad409f7594ae15aa0b158e53396cd5'
receipts = {}
frozen = None
for label in ('origin-before', 'new', 'regression', 'file-staging', 'packaging', 'ui', 'type', 'build', 'tokens', 'origin-after'):
    path = root / ('docs/delivery/v2-development/director-publication-' + label + '-r1.json')
    row = json.loads(path.read_text())
    assert row['status'] == 'PASS' and row['exit_code'] == 0 and not row['sources_changed_during_check']
    assert row['source_sha256'] == row['source_sha256_before']
    assert row['head'] == '39ba1c7bc6d8438cc7c7d59f5767ba67f97aca0a'
    assert row['cwd'] == str(root)
    if label not in {'ui', 'type', 'build', 'tokens'}:
        assert row['command'][0] == '/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python'
    elif label == 'tokens':
        assert row['command'][0] == '/opt/codex/runtimes/codex-primary-runtime/dependencies/node/bin/node'
    else:
        assert row['command'][:3] == ['bash', '--noprofile', '--norc']
    if frozen is None: frozen = row['source_sha256']
    assert row['source_sha256'] == frozen
    assert all(hashlib.sha256((root / name).read_bytes()).hexdigest() == value for name, value in frozen.items())
    assert hashlib.sha256((root / row['log']).read_bytes()).hexdigest() == row['log_sha256']
    receipts[label] = {'receipt': str(path.relative_to(root)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'log_sha256': row['log_sha256'], 'sources_changed': False}
result = {'status': 'PASS', 'head': '39ba1c7bc6d8438cc7c7d59f5767ba67f97aca0a',
    'frozen_source_count': len(frozen), 'all_current_source_hashes_match_all_receipts': True,
    'original_tests_unchanged': True, 'original_runner_unchanged': True,
    'manifest_added_only': 'app/creative/director_terminal_evidence.py',
    'manifest_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
    'receipts': receipts, 'acceptance_limits': 'No PostgreSQL, native Windows, live provider, install, browser, or network execution.'}
(destination / 'audit.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
