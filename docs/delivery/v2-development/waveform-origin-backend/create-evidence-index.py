"""Index terminal slice evidence and its actual source/provenance dependencies."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path('/workspace/scratch/20a0022d2b33/studio-timeline-waveform')
EVIDENCE = ROOT / 'docs/delivery/v2-development'
INDEX = EVIDENCE / 'waveform-evidence-index.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


assert Path.cwd() == ROOT
final_receipt = EVIDENCE / 'waveform-independent-backend-r1.json'
final = json.loads(final_receipt.read_text())
assert final['status'] == 'PASS' and not final['sources_changed_during_check']
sources = final['source_sha256']
assert sources == final['source_sha256_before']
assert all((ROOT / name).is_file() and sha(ROOT / name) == digest for name, digest in sources.items())
assert json.loads((EVIDENCE / 'waveform-independent-ui-r1.json').read_text())['status'] == 'PASS'
validation = {}
for path in sorted(EVIDENCE.glob('waveform-*.json')):
    if path == INDEX:
        continue
    value = json.loads(path.read_text())
    if 'command' not in value or 'source_sha256' not in value:
        continue
    current = value['source_sha256']
    assert sha(ROOT / value['log']) == value['log_sha256'], str(path)
    assert value['source_sha256_before'] == current and not value['sources_changed_during_check'], str(path)
    differences = sorted(name for name in set(sources) | set(current) if sources.get(name) != current.get(name))
    validation[path.relative_to(ROOT).as_posix()] = {
        'exit_code': value['exit_code'], 'status': value['status'], 'source_count': len(current),
        'pre_equals_post': True, 'log_hash_verified': True, 'differences_from_final_source_map': differences,
    }

before = EVIDENCE / 'waveform-packaging/public-build-before.json'
manifest = ROOT / 'packaging/public-build.json'
added = ['app/creative/timeline_waveform.py', 'app/services/pcm16_envelope.py']
original, current_manifest = json.loads(before.read_text()), json.loads(manifest.read_text())
assert sorted(set(current_manifest['files']) - set(original['files'])) == added
assert not set(original['files']) - set(current_manifest['files'])
assert {key: value for key, value in current_manifest.items() if key != 'files'} == {
    key: value for key, value in original.items() if key != 'files'}
stripped = manifest.read_bytes()
for name in added:
    stripped = stripped.replace(('    "' + name + '",\n').encode(), b'', 1)
assert stripped == before.read_bytes(), 'manifest changed beyond two inserted lines'

files = {ROOT / 'docs/TIMELINE_WAVEFORM_PREVIEW.md'}
for path in EVIDENCE.glob('waveform-*'):
    if path == INDEX:
        continue
    if path.is_file():
        files.add(path)
    elif path.is_dir():
        files.update(item for item in path.rglob('*') if item.is_file())
changes = subprocess.check_output(['git', 'diff', '--name-only'], cwd=ROOT, text=True).splitlines()
changes += subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard'], cwd=ROOT, text=True).splitlines()
source_dependencies = sorted({name for name in changes if name.startswith(('app/', 'tests/', 'frontend/src/'))})
source_dependencies += ['packaging/public-build.json', 'scripts/run_v2_checks.py', 'scripts/public_build.py', 'pyproject.toml', 'AGENTS.md']
files.update(ROOT / name for name in source_dependencies)
assert all(path.is_file() for path in files)
entries = {path.relative_to(ROOT).as_posix(): {'sha256': sha(path), 'bytes': path.stat().st_size}
           for path in sorted(files)}

build = json.loads((EVIDENCE / 'waveform-packaging/build-interpreter-r1.json').read_text())
startup = json.loads((EVIDENCE / 'waveform-origin-backend/normal-startup-r3.json').read_text())
clean_prefix = Path(startup['prefix'])
external = {Path(startup['executable']), clean_prefix / 'setup-receipt.json', clean_prefix / 'pyvenv.cfg',
            Path(build['executable']), *(Path(item['origin']) for item in build['modules'].values())}
external_hashes = {str(path): {'sha256': sha(path), 'bytes': path.stat().st_size} for path in sorted(external)}
result = {
    'status': 'INDEXED_AFTER_SCOPED_INDEPENDENT_REVIEW',
    'base_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
    'final_source_count': len(sources), 'final_sources_match_current': True,
    'final_source_map_sha256': hashlib.sha256(json.dumps(sources, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
    'notes': [
        'Independent counts overlap primary coverage; this is bounded File/jsdom/offline-artifact evidence, not full acceptance.',
        'r1 backend failure retained: exact empty original wrong-scope lock housekeeping now explicitly asserted.',
        'r2 backend failure retained: real original-owner identity provisioning fixed by opt-in nonprovision context; recreate no-write assertion preserved.',
        'Supplementary archive inspector r1 failed before writing evidence on pytest current aliases; r2 resolves unique owned receipts and verifies all four real artifacts.',
        'PUBLIC manifest is outside original runner source maps; its exact two-entry delta and before/after hashes are separately bound here.',
        'Windows/platform support, browser geometry, PostgreSQL, native media/provider/model/render and packaged-runtime acceptance remain NOT_RUN.',
    ],
    'receipt_validation': validation,
    'manifest': {'path': 'packaging/public-build.json', 'before_sha256': sha(before),
                 'after_sha256': sha(manifest), 'added_files': added, 'all_other_bytes_preserved': True},
    'files': entries, 'external_dependencies': external_hashes,
}
INDEX.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'index': INDEX.relative_to(ROOT).as_posix(), 'sha256': sha(INDEX),
                  'files': len(entries), 'external_dependencies': len(external_hashes),
                  'source_count': len(sources)}, indent=2))
