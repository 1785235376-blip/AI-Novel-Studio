"""Build a real offline PUBLIC wheel; never import the packaged application.

PUBLIC_WHEEL_BUILD_PYTHON may select an already-installed packaging interpreter.
PUBLIC_WHEEL_SOURCE may select a previously captured immutable PUBLIC source stage.
Missing optional build tooling skips this artifact suite, never installs tooling.
"""
from __future__ import annotations

import base64
import csv
from email.parser import BytesParser
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tomllib
import zipfile

from packaging.requirements import Requirement
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('public_wheel_build', ROOT / 'scripts/public_build.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)
pytestmark = pytest.mark.file_backend_only

BUILD = r'''
import importlib.abc, sys
class NoApplicationImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('app', 'local_interop_protocol', 'local_interop_desktop'):
            raise RuntimeError('Application import forbidden during packaging: ' + fullname)
sys.meta_path.insert(0, NoApplicationImports())
def offline(event, args):
    if event in ('socket.connect', 'socket.bind', 'socket.getaddrinfo', 'subprocess.Popen'):
        raise RuntimeError('Packaging must remain offline and pure Python: ' + event)
sys.addaudithook(offline)
from setuptools import build_meta
assert sys.argv[2] in ('wheel', 'sdist')
print(getattr(build_meta, 'build_' + sys.argv[2])(sys.argv[1]))
assert not any(name.split('.')[0] in ('app', 'local_interop_protocol', 'local_interop_desktop') for name in sys.modules)
print('APPLICATION_IMPORTS=NONE NETWORK=NONE')
'''


def build_distribution(tmp_path_factory, kind='wheel'):
    assert kind in ('wheel', 'sdist')
    root = tmp_path_factory.mktemp('public-' + kind)
    python = os.environ.get('PUBLIC_WHEEL_BUILD_PYTHON', sys.executable)
    env = {key: value for key, value in os.environ.items()
           if not key.endswith(('_API_KEY', '_TOKEN', '_SECRET'))
           and key not in ('PYTHONPATH', 'PYTHONHOME', 'DATABASE_URL', 'TEST_POSTGRES_DATABASE_URL')}
    for key, name in (('HOME', 'home'), ('TMPDIR', 'tmp'), ('XDG_CACHE_HOME', 'cache')):
        path = root / name
        path.mkdir()
        env[key] = str(path)
    env.update(PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1', PIP_NO_INDEX='1',
               PIP_CONFIG_FILE=os.devnull, PIP_DISABLE_PIP_VERSION_CHECK='1')
    available = subprocess.run([python, '-B', '-c',
        "from importlib.util import find_spec; import sys; sys.exit(not all(find_spec(x) for x in ('setuptools', 'wheel')))"],
        cwd=root, env=env, capture_output=True, text=True, timeout=30)
    if available.returncode:
        if 'PUBLIC_WHEEL_BUILD_PYTHON' in os.environ:
            pytest.fail('Selected packaging interpreter lacks installed setuptools/wheel: ' + available.stderr)
        pytest.skip('Offline wheel tooling unavailable; set PUBLIC_WHEEL_BUILD_PYTHON to an existing interpreter')
    manifest = build.load_manifest(ROOT / 'packaging/public-build.json')
    source = Path(os.environ.get('PUBLIC_' + kind.upper() + '_SOURCE', os.environ.get('PUBLIC_WHEEL_SOURCE', str(ROOT)))).resolve()
    stage = root / 'public'
    receipt = build.stage_public(source, stage, manifest, docker=True)
    # Build in a disposable copy so egg-info/build output cannot alter the
    # pristine PUBLIC stage whose exact bytes own this artifact receipt.
    work = root / 'build-source'
    shutil.copytree(stage, work)
    output = root / (kind + 's')
    output.mkdir()
    result = subprocess.run([python, '-B', '-c', BUILD, str(output), kind], cwd=work,
                            env=env, capture_output=True, text=True, timeout=120)
    (root / 'build.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'APPLICATION_IMPORTS=NONE NETWORK=NONE' in result.stdout
    artifacts = list(output.glob('*.whl' if kind == 'wheel' else '*.tar.gz'))
    assert len(artifacts) == 1
    (root / 'stage-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    verified = getattr(build, 'verify_' + kind)(stage, artifacts[0], manifest)
    (root / (kind + '-receipt.json')).write_text(json.dumps(verified, indent=2) + '\n')
    return root, stage, artifacts[0], manifest, receipt, verified


@pytest.fixture(scope='module')
def artifact(tmp_path_factory):
    return build_distribution(tmp_path_factory)


def payloads(wheel):
    with zipfile.ZipFile(wheel) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def rewrite(wheel, path, *, replace=None, remove=(), extra=None, records=None):
    """Derive inert negative fixtures from a genuinely built wheel, not a fake build."""
    entries = payloads(wheel)
    for name in remove:
        del entries[name]
    entries.update(replace or {})
    entries.update(extra or {})
    record = next(name for name in entries if name.endswith('.dist-info/RECORD'))
    rows = []
    for name, data in entries.items():
        digest = 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode()
        rows.append([name, '', ''] if name == record else [name, digest, str(len(data))])
    if records:
        rows = records(rows, record)
    text = io.StringIO()
    csv.writer(text, lineterminator='\n').writerows(rows)
    entries[record] = text.getvalue().encode()
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return path


def test_real_wheel_matches_public_stage_and_keeps_standard_inputs(artifact):
    _, stage, wheel, _, staged, verified = artifact
    source_hashes = {item['path']: item['sha256'] for item in staged['files']}
    assert verified['artifact_sha256'] == hashlib.sha256(wheel.read_bytes()).hexdigest()
    assert verified['wheel_member_count'] == verified['file_count'] + 4
    for item in verified['files']:
        assert item['sha256'] == source_hashes[item['source_path']]
        assert item['sha256'] == hashlib.sha256((stage / item['source_path']).read_bytes()).hexdigest()
    included = {item['path']: item['sha256'] for item in verified['files']}
    # Read bytes only, including the approved Codex lifecycle addition. Shared
    # standard/safety/model inputs remain present; no application code executes.
    for name in ('app/main.py', 'app/project_retirement.py', 'app/creative/content_policy.py',
                 'app/provider_routing_policy_v2.py', 'app/model_center/service.py'):
        assert included[name] == source_hashes[name]
    assert 'config/model_manifest.json' in verified['separate_stage_files']
    assert 'prompts/writer/system.md' in verified['separate_stage_files']
    assert 'workflows/dify/novel-workflow.yml' in verified['separate_stage_files']
    build.check_artifact_namespace(wheel.parent)


def test_real_metadata_keeps_declared_dependencies_external(artifact):
    _, stage, wheel, _, _, verified = artifact
    contents = payloads(wheel)
    metadata = BytesParser().parsebytes(next(data for name, data in contents.items() if name.endswith('.dist-info/METADATA')))
    project = tomllib.loads((stage / 'pyproject.toml').read_text())['project']
    expected = {Requirement(value) for value in project['dependencies']}
    for extra, requirements in project['optional-dependencies'].items():
        expected.update(Requirement(f'{value}; extra == "{extra}"') for value in requirements)
    assert {Requirement(value) for value in metadata.get_all('Requires-Dist')} == expected
    assert set(metadata.get_all('Provides-Extra')) == set(project['optional-dependencies'])
    assert verified['wheel_tags'] == ['py3-none-any']
    assert any(value.startswith('psycopg[binary]') for value in verified['requires_dist'])
    assert not any(name.endswith(('.so', '.dll', '.pyd')) for name in contents)


@pytest.mark.parametrize('name', ['app/creative/content_policy.py', 'app/project_retirement.py'])
@pytest.mark.parametrize('change', ['missing', 'tampered'])
def test_standard_payload_missing_or_tampered_fails_even_with_valid_record(artifact, tmp_path, name, change):
    _, stage, wheel, manifest, _, _ = artifact
    args = {'remove': [name]} if change == 'missing' else {'replace': {name: b'INERT_TAMPER_FIXTURE = True\n'}}
    candidate = rewrite(wheel, tmp_path / 'changed.whl', **args)
    with pytest.raises(ValueError, match='PUBLIC_WHEEL_CLOSURE_MISMATCH|PUBLIC_WHEEL_SOURCE_DIGEST_MISMATCH'):
        build.verify_wheel(stage, candidate, manifest)


@pytest.mark.parametrize('name,code', [
    ('studio_private_extensions/inert_sentinel.py', 'PUBLIC_PRIVATE_ARCHIVE'),
    ('app/unreviewed_inert_sentinel.py', 'PUBLIC_WHEEL_CLOSURE_MISMATCH'),
    ('app/unreviewed_inert_native.so', 'PUBLIC_WHEEL_CLOSURE_MISMATCH'),
    ('../inert_sentinel.py', 'PUBLIC_WHEEL_UNSAFE_PATH'),
    ('/inert_sentinel.py', 'PUBLIC_WHEEL_UNSAFE_PATH'),
])
def test_inert_extra_or_forbidden_payloads_fail(artifact, tmp_path, name, code):
    _, stage, wheel, manifest, _, _ = artifact
    candidate = rewrite(wheel, tmp_path / 'extra.whl', extra={name: b'INERT_PACKAGING_SENTINEL = True\n'})
    with pytest.raises(ValueError, match=code):
        build.verify_wheel(stage, candidate, manifest)


@pytest.mark.parametrize('change', ['missing', 'extra', 'digest', 'length', 'self'])
def test_exact_record_coverage_digests_lengths_and_self_row(artifact, tmp_path, change):
    _, stage, wheel, manifest, _, _ = artifact
    def alter(rows, record):
        if change == 'missing':
            return rows[1:]
        if change == 'extra':
            return rows + [['absent-inert.txt', 'sha256=invalid', '1']]
        row = next(row for row in rows if row[0] == (record if change == 'self' else 'app/main.py'))
        row[2 if change == 'length' else 1] = '1' if change == 'length' else 'sha256=invalid'
        return rows
    candidate = rewrite(wheel, tmp_path / 'record.whl', records=alter)
    with pytest.raises(ValueError, match='PUBLIC_WHEEL_RECORD_'):
        build.verify_wheel(stage, candidate, manifest)


def test_duplicate_zip_member_fails(artifact, tmp_path):
    _, stage, wheel, manifest, _, _ = artifact
    candidate = tmp_path / 'duplicate.whl'
    shutil.copyfile(wheel, candidate)
    with pytest.warns(UserWarning, match='Duplicate name'):
        with zipfile.ZipFile(candidate, 'a') as archive:
            archive.writestr('app/main.py', b'INERT_DUPLICATE = True\n')
    with pytest.raises(ValueError, match='PUBLIC_WHEEL_DUPLICATE_OR_SYMLINK'):
        build.verify_wheel(stage, candidate, manifest)


@pytest.mark.parametrize('original,replacement', [
    (b'Root-Is-Purelib: true', b'Root-Is-Purelib: false'),
    (b'Root-Is-Purelib: true', b'Root-Is-Purelib: true\nRoot-Is-Purelib: false'),
    (b'Wheel-Version: 1.0', b'Wheel-Version: 9.0'),
])
def test_wheel_metadata_cannot_claim_a_different_platform(artifact, tmp_path, original, replacement):
    _, stage, wheel, manifest, _, _ = artifact
    name, data = next((name, data) for name, data in payloads(wheel).items() if name.endswith('.dist-info/WHEEL'))
    candidate = rewrite(wheel, tmp_path / 'platform.whl', replace={name: data.replace(original, replacement)})
    with pytest.raises(ValueError, match='PUBLIC_WHEEL_METADATA_MISMATCH'):
        build.verify_wheel(stage, candidate, manifest)


@pytest.mark.parametrize('change', ['added', 'missing', 'replaced', 'extra', 'duplicate'])
def test_metadata_dependency_tampering_fails_with_self_consistent_record(artifact, tmp_path, change):
    _, stage, wheel, manifest, _, _ = artifact
    name, data = next((name, data) for name, data in payloads(wheel).items() if name.endswith('.dist-info/METADATA'))
    if change == 'added':
        data = data.replace(b'Name: ', b'Requires-Dist: inert-packaging-sentinel==0\nName: ', 1)
    elif change == 'missing':
        data = b'\n'.join(line for line in data.split(b'\n') if not line.startswith(b'Requires-Dist: fastapi'))
    elif change == 'replaced':
        data = data.replace(b'Requires-Dist: fastapi', b'Requires-Dist: inert-packaging-sentinel')
    elif change == 'extra':
        data = data.replace(b'Provides-Extra: dev', b'Provides-Extra: inert-extra')
    else:
        data = data.replace(b'Provides-Extra: dev', b'Provides-Extra: dev\nProvides-Extra: dev')
    candidate = rewrite(wheel, tmp_path / 'dependencies.whl', replace={name: data})
    with pytest.raises(ValueError, match='PUBLIC_WHEEL_DEPENDENCY_MISMATCH'):
        build.verify_wheel(stage, candidate, manifest)


def test_symlink_member_cannot_substitute_a_standard_file(artifact, tmp_path):
    _, stage, wheel, manifest, _, _ = artifact
    candidate = tmp_path / 'symlink.whl'
    with zipfile.ZipFile(candidate, 'w') as archive:
        for name, data in payloads(wheel).items():
            member = zipfile.ZipInfo(name)
            if name == 'app/main.py':
                member.create_system = 3
                member.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(member, data)
    with pytest.raises(ValueError, match='PUBLIC_WHEEL_DUPLICATE_OR_SYMLINK'):
        build.verify_wheel(stage, candidate, manifest)
