"""Real offline setuptools source distribution, a future-format verification only."""
from __future__ import annotations

import gzip
import hashlib
import io
import tarfile

import pytest

from test_public_wheel_artifact import build, build_distribution

pytestmark = pytest.mark.file_backend_only


@pytest.fixture(scope='module')
def artifact(tmp_path_factory):
    return build_distribution(tmp_path_factory, 'sdist')


def rewrite(archive, path, *, replace=None, remove=(), extra=None, directories=None):
    """Derive inert negatives from the real backend build without extracting it."""
    files, original_dirs = build.check_tar(archive.read_bytes(), archive.name)
    for name in remove:
        del files[name]
    files.update(replace or {})
    files.update(extra or {})
    dirs = original_dirs if directories is None else directories
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w', format=tarfile.USTAR_FORMAT) as target:
        for name in sorted(dirs):
            member = tarfile.TarInfo(name)
            member.type = tarfile.DIRTYPE
            target.addfile(member)
        for name, data in sorted(files.items()):
            member = tarfile.TarInfo(name)
            member.size = len(data)
            target.addfile(member, io.BytesIO(data))
    path.write_bytes(gzip.compress(output.getvalue()))
    return path


def test_actual_sdist_preserves_stage_hashes_and_standard_model_safety_inputs(artifact, monkeypatch):
    _, stage, archive, manifest, staged, verified = artifact
    def forbidden(*args, **kwargs):
        raise AssertionError('No filesystem extraction')
    monkeypatch.setattr(tarfile.TarFile, 'extract', forbidden)
    monkeypatch.setattr(tarfile.TarFile, 'extractall', forbidden)
    assert build.verify_sdist(stage, archive, manifest) == verified
    assert verified['format_status'] == 'FUTURE_FORMAT_VERIFICATION'
    assert verified['artifact_sha256'] == hashlib.sha256(archive.read_bytes()).hexdigest()
    source_hashes = {item['path']: item['sha256'] for item in staged['files']}
    included = {item['source_path']: item['sha256'] for item in verified['files']}
    for name, digest in included.items():
        assert digest == source_hashes[name] == hashlib.sha256((stage / name).read_bytes()).hexdigest()
    for name in ('app/main.py', 'app/project_retirement.py', 'app/creative/content_policy.py',
                 'app/provider_routing_policy_v2.py', 'app/model_center/service.py', 'pyproject.toml'):
        assert name in included
    assert verified['metadata_dependencies_verified']
    assert any(value.startswith('psycopg[binary]') for value in verified['requires_dist'])
    assert verified['generated_metadata_count'] == 7
    assert {'config/model_manifest.json', 'prompts/writer/system.md', 'workflows/dify/novel-workflow.yml'} <= set(verified['separate_stage_files'])
    build.check_artifact_namespace(archive.parent)


@pytest.mark.parametrize('source', ['app/project_retirement.py', 'app/creative/content_policy.py', 'app/model_center/service.py', 'pyproject.toml'])
@pytest.mark.parametrize('change', ['missing', 'tampered'])
def test_standard_payload_missing_or_tampered_fails(artifact, tmp_path, source, change):
    _, stage, archive, manifest, _, verified = artifact
    name = next(item['path'] for item in verified['files'] if item['source_path'] == source)
    args = {'remove': [name]} if change == 'missing' else {'replace': {name: b'INERT = True\n'}}
    candidate = rewrite(archive, tmp_path / 'changed.tar.gz', **args)
    with pytest.raises(ValueError, match='PUBLIC_SDIST_(CLOSURE|SOURCE_DIGEST)_MISMATCH'):
        build.verify_sdist(stage, candidate, manifest)


@pytest.mark.parametrize('name,code', [
    ('studio_private_extensions/inert.py', 'PUBLIC_PRIVATE_ARCHIVE'),
    ('app/unreviewed.py', 'PUBLIC_SDIST_CLOSURE_MISMATCH'),
    ('ai_novel_studio.egg-info/entry_points.txt', 'PUBLIC_SDIST_CLOSURE_MISMATCH'),
    ('ai_novel_studio.egg-info/unreviewed.txt', 'PUBLIC_SDIST_CLOSURE_MISMATCH'),
])
def test_no_blanket_metadata_or_private_path_allowance(artifact, tmp_path, name, code):
    _, stage, archive, manifest, _, verified = artifact
    prefix = verified['files'][0]['path'].split('/')[0]
    candidate = rewrite(archive, tmp_path / 'extra.tar.gz', extra={prefix + '/' + name: b'inert\n'})
    with pytest.raises(ValueError, match=code):
        build.verify_sdist(stage, candidate, manifest)


@pytest.mark.parametrize('name,data,code', [
    ('setup.cfg', b'[options]\ninstall_requires = inert-unreviewed\n', 'METADATA'),
    ('ai_novel_studio.egg-info/dependency_links.txt', b'https://invalid.example/inert\n', 'METADATA'),
    ('ai_novel_studio.egg-info/top_level.txt', b'app\n', 'METADATA'),
    ('ai_novel_studio.egg-info/requires.txt', b'inert-unreviewed\n', 'EGG_REQUIREMENTS'),
])
def test_generated_files_are_explicitly_validated(artifact, tmp_path, name, data, code):
    _, stage, archive, manifest, _, verified = artifact
    prefix = verified['files'][0]['path'].split('/')[0]
    candidate = rewrite(archive, tmp_path / 'metadata.tar.gz', replace={prefix + '/' + name: data})
    with pytest.raises(ValueError, match='PUBLIC_SDIST_' + code + '_MISMATCH'):
        build.verify_sdist(stage, candidate, manifest)


@pytest.mark.parametrize('change', ['missing', 'extra', 'duplicate', 'traversal'])
def test_sources_manifest_exactly_covers_only_declared_inputs(artifact, tmp_path, change):
    _, stage, archive, manifest, _, _ = artifact
    contents, _ = build.check_tar(archive.read_bytes(), archive.name)
    name = next(name for name in contents if name.endswith('.egg-info/SOURCES.txt'))
    rows = contents[name].decode().splitlines()
    if change == 'missing': rows = rows[1:]
    if change == 'extra': rows.append('inert.txt')
    if change == 'duplicate': rows.append(rows[0])
    if change == 'traversal': rows.append('../inert.txt')
    candidate = rewrite(archive, tmp_path / 'sources.tar.gz', replace={name: ('\n'.join(rows) + '\n').encode()})
    with pytest.raises(ValueError, match='PUBLIC_SDIST_SOURCES_MISMATCH'):
        build.verify_sdist(stage, candidate, manifest)


@pytest.mark.parametrize('change', ['added_dependency', 'removed_dependency', 'extra', 'identity', 'duplicate_identity', 'unknown_header', 'disagree'])
def test_metadata_identity_and_dependencies_match_even_when_both_copies_change(artifact, tmp_path, change):
    _, stage, archive, manifest, _, _ = artifact
    contents, _ = build.check_tar(archive.read_bytes(), archive.name)
    names = [name for name in contents if name.endswith('/PKG-INFO')]
    old = contents[names[0]]
    if change == 'added_dependency': new = old.replace(b'Name:', b'Requires-Dist: inert-unreviewed==1\nName:', 1)
    if change == 'removed_dependency': new = b'\n'.join(line for line in old.split(b'\n') if not line.startswith(b'Requires-Dist: fastapi'))
    if change == 'extra': new = old.replace(b'Provides-Extra: dev', b'Provides-Extra: unreviewed')
    if change == 'identity': new = old.replace(b'Version: 0.7.0', b'Version: 0.7.1')
    if change == 'duplicate_identity': new = old.replace(b'Name:', b'Name: ai-novel-studio\nName:', 1)
    if change == 'unknown_header': new = old.replace(b'Name:', b'Dynamic: Requires-Dist\nName:', 1)
    if change == 'disagree': new = old.replace(b'Summary:', b'Summary: changed ', 1)
    changes = {name: new for name in (names[:1] if change == 'disagree' else names)}
    candidate = rewrite(archive, tmp_path / 'pkg-info.tar.gz', replace=changes)
    with pytest.raises(ValueError, match='PUBLIC_SDIST_(METADATA|DEPENDENCY)_MISMATCH'):
        build.verify_sdist(stage, candidate, manifest)


def test_extra_empty_directory_fails(artifact, tmp_path):
    _, stage, archive, manifest, _, _ = artifact
    contents, dirs = build.check_tar(archive.read_bytes(), archive.name)
    prefix = next(iter(contents)).split('/')[0]
    candidate = rewrite(archive, tmp_path / 'directory.tar.gz', directories=dirs | {prefix + '/unreviewed'})
    with pytest.raises(ValueError, match='PUBLIC_SDIST_CLOSURE_MISMATCH'):
        build.verify_sdist(stage, candidate, manifest)
