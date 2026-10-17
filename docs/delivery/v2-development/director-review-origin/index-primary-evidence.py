"""Stdlib-only final source, receipt and actual PUBLIC archive audit."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import tarfile
import zipfile

root = Path.cwd()
assert root == Path('/workspace/scratch/20a0022d2b33/studio-director-review')
out = root / 'docs/delivery/v2-development'
own = out / 'director-review-origin'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
final_labels = ['director-review-origin-r2', 'director-review-backend-r2',
    'director-review-packaging-r2', 'director-review-types-r2', 'director-review-build-r2',
    'director-review-tokens-r2', 'director-review-ui-r2']
initial_labels = ['director-review-origin-r1', 'director-review-backend-r1']

def receipt(label):
    path = out / (label + '.json')
    row = json.loads(path.read_text())
    assert row['status'] == 'PASS' and row['exit_code'] == 0
    assert not row['sources_changed_during_check']
    assert row['source_sha256_before'] == row['source_sha256']
    log = root / row['log']
    assert sha(log) == row['log_sha256']
    summaries = [line for line in log.read_text().splitlines()
        if re.search(r'\d+ passed|Test Files|Tests |checked \d+|PASS', line)]
    return row, {'receipt': str(path.relative_to(root)), 'receipt_sha256': sha(path),
        'log': row['log'], 'log_sha256': sha(log), 'command': row['command'],
        'source_count': len(row['source_sha256']), 'sources_unchanged': True,
        'summary_lines': summaries}

final_rows = [receipt(label) for label in final_labels]
initial_rows = [receipt(label) for label in initial_labels]
current = final_rows[0][0]['source_sha256']
assert all(row['source_sha256'] == current for row, _ in final_rows)
assert initial_rows[0][0]['source_sha256'] == initial_rows[1][0]['source_sha256']
assert all(sha(root / path) == value for path, value in current.items())
initial = initial_rows[0][0]['source_sha256']
assert sorted(path for path in initial if initial[path] != current.get(path)) == [
    'app/creative/generation.py', 'tests/test_v2_independent_director_adoption.py']
baseline_path = out / 'creative-lifecycle-inventory-confirmation-origin.json'
baseline = json.loads(baseline_path.read_text())['source_sha256']
changed = sorted(path for path in baseline if baseline[path] != current.get(path))
added = sorted(set(current) - set(baseline))
assert changed == ['app/creative/generation.py', 'app/creative/proposals.py', 'app/creative/storyboard_model.py']
assert added == ['tests/test_v2_creative_director_review_contract.py', 'tests/test_v2_independent_director_adoption.py']
fixture = root / 'tests/fixtures/creative_binding_legacy_requests.json'
manifest = root / 'packaging/public-build.json'
assert sha(fixture) == '640ca3823d83a378b9018a180957d375b9cef6b524f2e527f7e731236cfd90ac'
assert sha(manifest) == '3261cc7549d58e5d8e84c69572a9475d9c416bfd487588ecfbec472e8695d37c'
artifacts = []
for kind in ('wheel', 'sdist'):
    for index in (0, 1):
        name = f'public-{kind}{index}'
        directory = root / '.runtime/director-review-packaging-r2-pytest' / name
        path = directory / f'{kind}-receipt.json'
        row = json.loads(path.read_text())
        paths = list((directory / ('wheels' if kind == 'wheel' else 'sdists')).glob(
            '*.whl' if kind == 'wheel' else '*.tar.gz'))
        assert len(paths) == 1
        archive = paths[0]
        assert sha(archive) == row['artifact_sha256']
        members = {item['source_path']: item for item in row['files']}
        module_hashes = {}
        reader = zipfile.ZipFile(archive) if kind == 'wheel' else tarfile.open(archive, 'r:gz')
        with reader:
            for module in changed + ['app/creative/director_binding.py']:
                item = members[module]
                data = reader.read(item['path']) if kind == 'wheel' else reader.extractfile(item['path']).read()
                assert hashlib.sha256(data).hexdigest() == item['sha256'] == sha(root / module)
                module_hashes[module] = item['sha256']
        saved = own / 'artifacts' / name
        saved.mkdir(parents=True, exist_ok=True)
        saved_receipts = []
        for original in (path, directory / 'stage-receipt.json'):
            copy = saved / original.name
            shutil.copyfile(original, copy)
            assert sha(copy) == sha(original)
            saved_receipts.append({'path': str(copy.relative_to(root)), 'sha256': sha(copy)})
        artifacts.append({'name': name, 'artifact': str(archive.relative_to(root)),
            'artifact_sha256': sha(archive), 'actual_archived_module_hashes': module_hashes,
            'receipts': saved_receipts, 'installed_runtime_acceptance': False})
(own / 'artifact-hashes.json').write_text(json.dumps({'status': 'PASS_REAL_OFFLINE_ARTIFACTS',
    'artifacts': artifacts}, indent=2) + '\n')
files = {p for p in own.rglob('*') if p.is_file() and p.name not in
         {'primary-evidence-index.json', 'evidence-index.json', 'index-primary-evidence.log'} and 'independent' not in p.name}
files.update(out / (label + suffix) for label in initial_labels + final_labels for suffix in ('.json', '.log'))
result = {'status': 'PASS_PRIMARY_SCOPED_EVIDENCE', 'baseline_commit': '586c388b09844d2587043effb4b51955c17f8bb5',
    'baseline_receipt': str(baseline_path.relative_to(root)), 'baseline_receipt_sha256': sha(baseline_path),
    'source_files_current': len(current), 'changed_source_paths': changed, 'added_source_paths': added,
    'public_manifest_sha256': sha(manifest), 'frozen_fixture_sha256': sha(fixture),
    'initial_r1': [record for _, record in initial_rows],
    'final_r2': [record for _, record in final_rows], 'artifacts': artifacts,
    'independent': 'SEPARATE_REVIEW_PENDING',
    'limits': ['private live candidate and explicit review only; public model routes/content/adoption stay closed',
        'pending candidates expire with original execution deadline and cannot resume after restart',
        'no PostgreSQL execution', 'no live-provider/model-quality acceptance',
        'no browser/native/Windows/installed-package acceptance', 'no installation/merge/tag/release'],
    'files': {str(p.relative_to(root)): {'sha256': sha(p), 'bytes': p.stat().st_size} for p in sorted(files)}}
(own / 'primary-evidence-index.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'status': result['status'], 'source_files_current': len(current),
    'index_sha256': sha(own / 'primary-evidence-index.json'), 'artifacts': len(artifacts)}, indent=2))
