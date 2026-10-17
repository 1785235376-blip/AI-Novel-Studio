"""Bind final primary, independent and documentation evidence without imports."""
import hashlib
import json
from pathlib import Path
import sys

root = Path.cwd()
assert root == Path('/workspace/scratch/20a0022d2b33/studio-director-review')
out = root / 'docs/delivery/v2-development'
own = out / 'director-review-origin'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
primary_path = own / 'primary-evidence-index.json'
assert sha(primary_path) == 'c3649fd15bc4960cadc699e265940b67add6b436ecc2d1a778d416dbe37009ec'
primary = json.loads(primary_path.read_text())
for name, record in primary['files'].items():
    assert sha(root / name) == record['sha256']
current = json.loads((out / 'director-review-backend-r2.json').read_text())['source_sha256']
assert all(sha(root / name) == value for name, value in current.items())
report_path = root / sys.argv[1]
report = json.loads(report_path.read_text())
assert str(report['status']).startswith('PASS'), report['status']
independent = []
for path in sorted(out.glob('director-review-independent*.json')):
    row = json.loads(path.read_text())
    if 'source_sha256' not in row:
        continue
    assert row['status'] == 'PASS' and row['exit_code'] == 0
    assert not row['sources_changed_during_check']
    assert row['source_sha256_before'] == row['source_sha256'] == current
    log = root / row['log']
    assert sha(log) == row['log_sha256']
    independent.append({'path': str(path.relative_to(root)), 'sha256': sha(path),
        'log': row['log'], 'log_sha256': sha(log), 'command': row['command']})
assert len(independent) >= 2
for artifact in primary['artifacts']:
    assert sha(root / artifact['artifact']) == artifact['artifact_sha256']
files = {p for p in own.rglob('*') if p.is_file() and p.name not in
    {'evidence-index.json', 'index-evidence.log'}}
files.update(out.glob('director-review-independent*'))
files = {p for p in files if p.is_file()}
files.update(root / record['receipt'] for record in primary['initial_r1'] + primary['final_r2'])
files.update(root / record['log'] for record in primary['initial_r1'] + primary['final_r2'])
files.update([root / 'docs/INDEPENDENT_DIRECTOR_REVIEW.md',
    root / 'docs/v2/frozen-capability-ledger-20261016.md', report_path])
result = {'status': 'PASS_COMPLETE_SCOPED_EVIDENCE', 'source_count': len(current),
    'primary_index': str(primary_path.relative_to(root)), 'primary_index_sha256': sha(primary_path),
    'independent_report': str(report_path.relative_to(root)), 'independent_report_sha256': sha(report_path),
    'independent_runner_receipts': independent, 'r1_r2_scopes': 'DISTINCT_NOT_ADDITIVE',
    'public_manifest_sha256': primary['public_manifest_sha256'],
    'frozen_fixture_sha256': primary['frozen_fixture_sha256'], 'artifacts': primary['artifacts'],
    'limits': primary['limits'],
    'files': {str(p.relative_to(root)): {'sha256': sha(p), 'bytes': p.stat().st_size} for p in sorted(files)}}
(own / 'evidence-index.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'status': result['status'], 'source_count': len(current),
    'file_count': len(files), 'index_sha256': sha(own / 'evidence-index.json')}, indent=2))
