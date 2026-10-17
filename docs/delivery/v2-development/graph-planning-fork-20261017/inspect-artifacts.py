"""Read actual offline archives without extraction, installation or app imports."""
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import zipfile

ROOT = Path('/workspace/scratch/20a0022d2b33/studio-director-transport')
LABELS = ('director-application-public-wheel-r1', 'director-application-public-sdist-binding-r1')
BASES = [ROOT / '.runtime/v2-checks' / label / 'pytest' for label in LABELS]
DESTINATION = ROOT / 'docs/delivery/v2-development/graph-planning-fork-20261017/reused-backend-packages'
CHANGED = ('app/experimental/api.py', 'app/creative/director_model_api.py', 'app/creative/director_observation_api.py')

assert Path.cwd() == ROOT
assert not DESTINATION.exists(), 'evidence destination must be fresh'
for label in LABELS:
    result = json.loads((ROOT / 'docs/delivery/v2-development' / (label + '.json')).read_text())
    assert result['status'] == 'PASS' and not result['sources_changed_during_check']
    assert result['source_sha256'] == result['source_sha256_before']
manifest = ROOT / 'packaging/public-build.json'
assert all(path in json.loads(manifest.read_text())['files'] for path in CHANGED)
# pytest's *current symlinks alias existing owned builds; inspect each real
# receipt exactly once without treating aliases as additional artifacts.
candidates = [p for base in BASES for pattern in ('public-*/wheel-receipt.json','public-*/sdist-receipt.json') for p in base.glob(pattern)]
receipts = sorted({path.resolve(strict=True) for path in candidates})
assert all(any(path.is_relative_to(base.resolve()) for base in BASES) for path in receipts)
assert sum(path.name == 'wheel-receipt.json' for path in receipts) == 2
assert sum(path.name == 'sdist-receipt.json' for path in receipts) == 2
DESTINATION.mkdir(parents=True)
records = []
for path in receipts:
    receipt = json.loads(path.read_text())
    kind = path.stem.removesuffix('-receipt')
    archive = path.parent / (kind + 's') / receipt['artifact']
    assert archive.is_file()
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    assert digest == receipt['artifact_sha256']
    payloads = {}
    if kind == 'wheel':
        with zipfile.ZipFile(archive) as handle:
            assert len(handle.namelist()) == len(set(handle.namelist()))
            payloads = {name: handle.read(name) for name in handle.namelist() if not name.endswith('/')}
    else:
        with tarfile.open(archive, 'r:gz') as handle:
            members = handle.getmembers()
            assert len(members) == len({member.name for member in members})
            assert all(member.isfile() or member.isdir() for member in members)
            for member in members:
                if member.isfile():
                    payloads[member.name] = handle.extractfile(member).read()
    included = {entry['source_path']: entry for entry in receipt['files']}
    for source, entry in included.items():
        expected = hashlib.sha256((ROOT / source).read_bytes()).hexdigest()
        assert expected == entry['sha256'] == hashlib.sha256(payloads[entry['path']]).hexdigest()
    assert all(name in included for name in CHANGED)
    retained = DESTINATION / (path.parents[2].name + '__' + path.parent.name)
    retained.mkdir()
    for name in (path.name, 'stage-receipt.json', 'build.log'):
        shutil.copyfile(path.parent / name, retained / name)
    inventory = {name: {'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                 for name, data in sorted(payloads.items())}
    (retained / 'payload-inventory.json').write_text(json.dumps(inventory, indent=2) + '\n')
    records.append({'archive': archive.relative_to(ROOT).as_posix(), 'kind': kind,
                    'sha256': digest, 'payload_file_count': len(payloads),
                    'changed_modules': {name: {'member': included[name]['path'], 'sha256': included[name]['sha256']}
                                        for name in CHANGED},
                    'durable_evidence': retained.relative_to(ROOT).as_posix()})
summary = {'status': 'PASS_OFFLINE_PUBLIC_ARCHIVE_INSPECTION',
           'manifest_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
           'archives': records, 'all_runtime_source_bytes_verified': True,
           'application_imported': False, 'installed': False, 'extracted': False,
           'artifact_installation_and_native_execution': 'NOT_RUN'}
(DESTINATION / 'index.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))
