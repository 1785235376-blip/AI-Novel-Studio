"""Offline disposable packaging tests. No services or runtime initialization."""
from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('public_build', ROOT / 'scripts/public_build.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


@pytest.fixture
def source(tmp_path):
    root = tmp_path / 'source'
    for name in build.ROOTS:
        (root / name).mkdir(parents=True)
        (root / name / ('main.py' if name == 'app' else 'fixture.txt')).write_text('PUBLIC = True\n')
    (root / 'pyproject.toml').write_text('[project]\ndependencies=[]\n')
    private = root / build.PRIVATE
    private.mkdir()
    (private / 'sentinel.py').write_text('SYNTHETIC_EXCLUDED_SENTINEL = True\n')
    manifest = {'schema': build.SCHEMA, 'profile': 'PUBLIC', 'excluded_namespace': build.PRIVATE,
                'roots': list(build.ROOTS), 'files': sorted(build.inventory(root)),
                'dependencies': {'required': [], 'optional': {}}}
    return root, manifest


def test_public_stage_excludes_private_and_hashes_actual_contents(source, tmp_path):
    root, manifest = source
    receipt = build.stage_public(root, tmp_path / 'stage', manifest)
    assert receipt['profile'] == 'PUBLIC'
    assert receipt['optional_backend'] == 'NOT_INCLUDED'
    assert not (tmp_path / 'stage' / build.PRIVATE).exists()
    assert len(receipt['files']) == len(manifest['files'])
    assert build.verify_stage(root, tmp_path / 'stage', manifest) == receipt


@pytest.mark.parametrize('name', ['new_backend.py', 'hidden.zip', 'hidden.so', 'hidden.pyd', 'hidden.dll'])
def test_unreviewed_runtime_files_fail(source, name):
    root, manifest = source
    (root / 'app' / name).write_bytes(b'SYNTHETIC')
    with pytest.raises(ValueError, match='PUBLIC_SOURCE_CLOSURE'):
        build.check_source(root, manifest)


def test_source_caches_not_copied_but_staged_bytecode_fails(source, tmp_path):
    root, manifest = source
    (root / 'app/__pycache__').mkdir()
    (root / 'app/__pycache__/local.pyc').write_bytes(b'SYNTHETIC')
    stage = tmp_path / 'stage'
    build.stage_public(root, stage, manifest)
    assert not (stage / 'app/__pycache__').exists()
    (stage / 'app/hidden.pyc').write_bytes(b'SYNTHETIC')
    with pytest.raises(ValueError, match='PUBLIC_STAGE_UNDECLARED_ENTRY'):
        build.verify_stage(root, stage, manifest)


@pytest.mark.parametrize('text', ['import studio_private_extensions', 'from studio_private_extensions import optional', "importlib.import_module('studio_private_extensions.optional')", '{"module":"studio_private_extensions.optional"}'])
def test_public_dependency_on_private_fails(source, text):
    root, manifest = source
    (root / 'app/main.py').write_text(text)
    with pytest.raises(ValueError, match='PUBLIC_PRIVATE_DEPENDENCY'):
        build.check_source(root, manifest)


def test_frontend_cannot_import_private_namespace(source):
    root, manifest = source
    path = root / 'frontend/src/feature.ts'
    path.parent.mkdir(parents=True)
    path.write_text("import 'studio_private_extensions';")
    with pytest.raises(ValueError, match='PUBLIC_PRIVATE_FRONTEND_DEPENDENCY'):
        build.check_source(root, manifest)


def test_dependency_change_needs_manifest_review(source):
    root, manifest = source
    (root / 'pyproject.toml').write_text('[project]\ndependencies=["synthetic-package"]\n')
    with pytest.raises(ValueError, match='PUBLIC_DEPENDENCY_REVIEW_REQUIRED'):
        build.check_source(root, manifest)


def test_stage_tampering_and_reuse_fail(source, tmp_path):
    root, manifest = source
    stage = tmp_path / 'stage'
    build.stage_public(root, stage, manifest)
    with pytest.raises(ValueError, match='PUBLIC_STAGE_MUST_BE_FRESH'):
        build.stage_public(root, stage, manifest)
    (stage / 'app/main.py').write_text('CHANGED = True')
    with pytest.raises(ValueError, match='PUBLIC_STAGE_CLOSURE'):
        build.verify_stage(root, stage, manifest)


def test_symlinks_fail_before_copy(source, tmp_path):
    root, manifest = source
    (root / 'app/link.py').symlink_to(root / build.PRIVATE / 'sentinel.py')
    with pytest.raises(ValueError, match='PUBLIC_SYMLINK'):
        build.stage_public(root, tmp_path / 'stage', manifest)
    assert not (tmp_path / 'stage').exists()


def test_archive_members_and_case_folded_private_paths_fail(tmp_path):
    archive = tmp_path / 'runtime.zip'
    with zipfile.ZipFile(archive, 'w') as output:
        output.writestr('STUDIO_PRIVATE_EXTENSIONS/payload.pyc', b'SYNTHETIC')
    with pytest.raises(ValueError, match='PUBLIC_PRIVATE_ARCHIVE'):
        build.check_artifact_namespace(tmp_path)


def test_actual_repo_manifest_and_disposable_artifact(tmp_path):
    manifest = build.load_manifest(ROOT / 'packaging/public-build.json')
    receipt = build.stage_public(ROOT, tmp_path / 'public', manifest)
    assert receipt['file_count'] == len(manifest['files'])
    # Compatibility vocabulary stays included; no removal of shared policy.
    assert (tmp_path / 'public/app/creative/content_policy.py').is_file()
    assert (tmp_path / 'public/app/main.py').is_file()
    archive_path = tmp_path / 'public.zip'
    with zipfile.ZipFile(archive_path, 'w') as archive:
        for item in receipt['files']:
            archive.write(tmp_path / 'public' / item['path'], item['path'])
    with zipfile.ZipFile(archive_path) as archive:
        assert set(archive.namelist()) == set(manifest['files'])
        assert {name: hashlib.sha256(archive.read(name)).hexdigest() for name in archive.namelist()} == {
            item['path']: item['sha256'] for item in receipt['files']}
    build.check_artifact_namespace(tmp_path)


def test_windows_and_docker_wire_the_guard():
    windows = (ROOT / 'scripts/build_windows_application.ps1').read_text()
    assert windows.index('PUBLIC source closure validation failed') < windows.index('--list-sdks')
    assert '--verify-stage $stagedBackend --receipt' in windows
    assert '--application $outputApplication' in windows
    assert windows.index('PUBLIC application exclusion validation failed') < windows.index('Write-Output "APPLICATION_STAGED')
    docker = (ROOT / 'Dockerfile').read_text()
    final = docker.split('FROM python:3.12-slim\n', 1)[1]
    assert 'COPY app' not in final
    assert '--stage /public' in docker
    assert 'COPY --from=public-source /public/' in final


@pytest.mark.parametrize('files', [['app/../escape.py'], ['app/a.py', 'app/a.py'], ['app/\\escape.py'], ['studio_private_extensions/a.py']])
def test_invalid_manifest_paths_fail(source, tmp_path, files):
    _, manifest = source
    manifest['files'] = files
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='PUBLIC_FILE'):
        build.load_manifest(path)


def test_missing_public_file_fails(source):
    root, manifest = source
    manifest['files'].append('app/missing.py')
    with pytest.raises(ValueError, match='PUBLIC_SOURCE_CLOSURE'):
        build.check_source(root, manifest)


@pytest.mark.parametrize('name', ['unexpected_backend.py', 'other/backend.py', 'app/extra.py'])
def test_stage_top_level_and_nested_extras_fail(source, tmp_path, name):
    root, manifest = source
    stage = tmp_path / 'stage'
    build.stage_public(root, stage, manifest)
    path = stage / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('SYNTHETIC = True')
    with pytest.raises(ValueError, match='PUBLIC_STAGE_UNDECLARED_ENTRY'):
        build.verify_stage(root, stage, manifest)


def test_missing_artifact_directory_fails(tmp_path):
    with pytest.raises(ValueError, match='PUBLIC_ARTIFACT_ROOT_INVALID'):
        build.check_artifact_namespace(tmp_path / 'missing')


def test_nested_archive_private_payload_fails(tmp_path):
    import io
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w') as nested:
        nested.writestr('studio_private_extensions/sentinel.py', 'SYNTHETIC = True')
    with zipfile.ZipFile(tmp_path / 'runtime.zip', 'w') as outer:
        outer.writestr('vendor.whl', data.getvalue())
    with pytest.raises(ValueError, match='PUBLIC_PRIVATE_ARCHIVE'):
        build.check_artifact_namespace(tmp_path)


def test_actual_docker_stage_has_only_manifest_inputs(tmp_path):
    manifest = build.load_manifest(ROOT / 'packaging/public-build.json')
    receipt = build.stage_public(ROOT, tmp_path / 'docker', manifest, docker=True)
    assert receipt['file_count'] == len(manifest['files']) + len(manifest['docker_files'])
    assert (tmp_path / 'docker/pyproject.toml').is_file()
    assert (tmp_path / 'docker/release/version.json').is_file()
    assert set(path.relative_to(tmp_path / 'docker').as_posix() for path in (tmp_path / 'docker').rglob('*') if path.is_file()) == set(manifest['files'] + manifest['docker_files'])


def test_supplemental_fonts_require_explicit_complete_allowance(source, tmp_path):
    root, manifest = source
    stage = tmp_path / 'stage'
    build.stage_public(root, stage, manifest)
    for name in build.FONT_FILES:
        path = stage / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('SYNTHETIC_FONT_FIXTURE')
    with pytest.raises(ValueError, match='PUBLIC_STAGE_UNDECLARED_ENTRY'):
        build.verify_stage(root, stage, manifest)
    build.verify_stage(root, stage, manifest, with_fonts=True)
