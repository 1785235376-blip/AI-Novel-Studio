"""Read-only audit of original runner receipts and frozen current sources."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path('/workspace/scratch/20a0022d2b33/studio-director-pending')
D = ROOT / 'docs/delivery/v2-development/director-pending-20261017'
assert Path.cwd() == ROOT
stages = ('origin-before', 'new', 'regression', 'packaging', 'ui', 'type', 'build', 'token', 'origin-after')
receipts = []
expected = None
for stage in stages:
    path = ROOT / f'docs/delivery/v2-development/director-pending-{stage}-r1.json'
    row = json.loads(path.read_text())
    assert row['status'] == 'PASS' and row['exit_code'] == 0
    assert not row['sources_changed_during_check']
    assert row['source_sha256_before'] == row['source_sha256']
    if expected is None: expected = row['source_sha256']
    assert row['source_sha256'] == expected, stage
    log = ROOT / row['log']
    assert hashlib.sha256(log.read_bytes()).hexdigest() == row['log_sha256']
    receipts.append({'stage': stage, 'path': path.relative_to(ROOT).as_posix(),
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'log': row['log'], 'log_sha256': row['log_sha256']})
for name, value in expected.items():
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == value, name
protected = ['tests', 'frontend', 'scripts/run_v2_checks.py', 'packaging/public-build.json']
assert not subprocess.check_output(['git', 'diff', '--name-only', 'HEAD', '--', *protected], cwd=ROOT).strip()
golden = ROOT / 'tests/fixtures/creative_binding_legacy_requests.json'
assert hashlib.sha256(golden.read_bytes()).hexdigest() == '640ca3823d83a378b9018a180957d375b9cef6b524f2e527f7e731236cfd90ac'
manifest = ROOT / 'packaging/public-build.json'
assert manifest.read_bytes() == subprocess.check_output(['git','show','HEAD:packaging/public-build.json'],cwd=ROOT)
archives = json.loads((D / 'packaging-evidence/index.json').read_text())
assert len(archives['archives']) == 4
for record in archives['archives']:
    assert hashlib.sha256((ROOT / record['archive']).read_bytes()).hexdigest() == record['sha256']
result = {'status': 'PASS_FROZEN_PRIMARY_AUDIT', 'head': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
    'source_count': len(expected), 'all_nine_receipts_and_current_sources_equal': True,
    'old_tests_frontend_original_runner_and_public_manifest_unchanged': True,
    'golden_sha256': hashlib.sha256(golden.read_bytes()).hexdigest(),
    'manifest_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest(), 'receipts': receipts,
    'archive_index_sha256': hashlib.sha256((D / 'packaging-evidence/index.json').read_bytes()).hexdigest()}
(D / 'audit.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
