"""Bounded PUBLIC source closure and staged-payload validation.

Base guards use only stdlib. Optional wheel verification requires the already-
installed ``packaging`` parser; it never installs or downloads build tooling.

The separate studio_private_extensions namespace is never an input. Shared policy vocabulary
is public compatibility data, not an optional backend. This is packaging hygiene,
not a content classifier or a replacement for review of changed public code.
"""
from __future__ import annotations

import argparse
import base64
import csv
from collections import Counter
from email.parser import BytesParser
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import tomllib
import zipfile

ROOTS = ('app', 'local_interop_protocol', 'local_interop_desktop', 'config', 'prompts', 'workflows')
PRIVATE = 'studio_private_extensions'
SCHEMA = 'studio-public-build/1'
FONT_FILES = {'assets/fonts/NotoSansSC-Regular.ttf', 'assets/fonts/OFL.txt', 'assets/fonts/font-manifest.json'}
ARCHIVES = ('.zip', '.whl', '.egg', '.pyz')


def fail(message: str) -> None:
    raise ValueError(message)


def inventory(root: Path, *, source: bool = False) -> dict[str, str]:
    result = {}
    for name in ROOTS:
        directory = root / name
        if not directory.is_dir() or directory.is_symlink():
            fail(f'PUBLIC_ROOT_INVALID: {name}')
        for path in sorted(directory.rglob('*')):
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                fail(f'PUBLIC_SYMLINK: {relative}')
            # Existing developer caches are not source inputs. Staged caches fail.
            if source and ('__pycache__' in path.parts or path.suffix in ('.pyc', '.pyo')):
                continue
            if path.is_file():
                result[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def load_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text(encoding='utf-8'))
    if (manifest.get('schema') != SCHEMA or manifest.get('profile') != 'PUBLIC'
            or manifest.get('excluded_namespace') != PRIVATE
            or manifest.get('roots') != list(ROOTS)):
        fail('PUBLIC_MANIFEST_INVALID')
    files = manifest.get('files')
    if not isinstance(files, list) or files != sorted(set(files)):
        fail('PUBLIC_FILE_LIST_INVALID')
    for name in files:
        parts = PurePosixPath(name).parts
        if (not isinstance(name, str) or not parts or parts[0] not in ROOTS
                or '..' in parts or '\\' in name or name.startswith('/')
                or PRIVATE in name.casefold()):
            fail('PUBLIC_FILE_PATH_INVALID')
    auxiliary = manifest.get('docker_files', [])
    if not isinstance(auxiliary, list) or auxiliary != sorted(set(auxiliary)):
        fail('PUBLIC_DOCKER_FILE_LIST_INVALID')
    for name in auxiliary:
        if (name not in ('pyproject.toml', 'release/version.json') and not name.startswith('contracts/')) or any(
                part in ('..', '') for part in name.split('/')) or '\\' in name or PRIVATE in name.casefold():
            fail('PUBLIC_DOCKER_FILE_PATH_INVALID')
    return manifest


def check_docker_inputs(source: Path, manifest: dict) -> dict[str, str]:
    expected = set(manifest.get('docker_files', []))
    actual = {'pyproject.toml', 'release/version.json'}
    contracts = source / 'contracts'
    if not contracts.is_dir() or contracts.is_symlink():
        fail('PUBLIC_DOCKER_CONTRACTS_INVALID')
    for path in contracts.rglob('*'):
        if path.is_symlink():
            fail('PUBLIC_DOCKER_SYMLINK')
        if path.is_file():
            actual.add(path.relative_to(source).as_posix())
    if actual != expected:
        fail('PUBLIC_DOCKER_SOURCE_CLOSURE')
    files = {}
    for name in expected:
        path = source / name
        if path.is_symlink() or not path.is_file() or PRIVATE.encode() in path.read_bytes().lower():
            fail(f'PUBLIC_DOCKER_INPUT_INVALID: {name}')
        files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def check_source(source: Path, manifest: dict) -> dict[str, str]:
    files = inventory(source, source=True)
    expected = set(manifest['files'])
    if set(files) != expected:
        fail(f'PUBLIC_SOURCE_CLOSURE: added={sorted(set(files)-expected)} missing={sorted(expected-set(files))}')
    project = tomllib.loads((source / 'pyproject.toml').read_text())['project']
    dependencies = {'required': project.get('dependencies', []), 'optional': project.get('optional-dependencies', {})}
    if dependencies != manifest.get('dependencies'):
        fail('PUBLIC_DEPENDENCY_REVIEW_REQUIRED')
    # Literal imports, dynamic import strings, config, prompts and workflow
    # references all fail if they depend on the reserved private namespace.
    for name in files:
        if PRIVATE.encode() in (source / name).read_bytes().lower():
            fail(f'PUBLIC_PRIVATE_DEPENDENCY: {name}')
    frontend = source / 'frontend' / 'src'
    if frontend.exists():
        for path in frontend.rglob('*'):
            if path.is_symlink():
                fail('PUBLIC_FRONTEND_SYMLINK')
            if path.is_file() and PRIVATE.encode() in path.read_bytes().lower():
                fail(f'PUBLIC_PRIVATE_FRONTEND_DEPENDENCY: {path.relative_to(source)}')
    return files


def check_archive(archive: zipfile.ZipFile, *, depth: int = 0, budget: list[int] | None = None) -> None:
    budget = budget if budget is not None else [10000, 128 * 1024 * 1024]
    for member in archive.infolist():
        budget[0] -= 1
        if budget[0] < 0:
            fail('PUBLIC_ARCHIVE_INSPECTION_LIMIT')
        if PRIVATE in member.filename.casefold():
            fail('PUBLIC_PRIVATE_ARCHIVE')
        if PurePosixPath(member.filename).suffix.lower() in ARCHIVES:
            budget[1] -= member.file_size
            if depth >= 3 or budget[1] < 0:
                fail('PUBLIC_ARCHIVE_INSPECTION_LIMIT')
            with zipfile.ZipFile(io.BytesIO(archive.read(member))) as nested:
                check_archive(nested, depth=depth + 1, budget=budget)


def check_artifact_namespace(root: Path) -> None:
    """Inspect named payloads and bounded nested ZIP members without extraction.

    Opaque native libraries, renamed archives and arbitrary module renamings still
    need provenance review. Inspection limits fail the build rather than skip data.
    """
    if root.is_symlink() or not root.is_dir():
        fail('PUBLIC_ARTIFACT_ROOT_INVALID')
    for path in root.rglob('*'):
        if path.is_symlink():
            fail(f'PUBLIC_ARTIFACT_SYMLINK: {path.relative_to(root)}')
        if PRIVATE in path.relative_to(root).as_posix().casefold():
            fail(f'PUBLIC_PRIVATE_ARTIFACT: {path.relative_to(root)}')
        if path.is_file() and path.suffix.lower() in ARCHIVES:
            with zipfile.ZipFile(path) as archive:
                check_archive(archive)


def verify_stage(source: Path, stage: Path, manifest: dict, *, docker: bool = False, with_fonts: bool = False) -> dict:
    expected = check_source(source, manifest)
    actual = inventory(stage)
    if docker:
        expected.update(check_docker_inputs(source, manifest))
        for name in manifest['docker_files']:
            path = stage / name
            if not path.is_file() or path.is_symlink():
                fail('PUBLIC_STAGE_DOCKER_FILE_INVALID')
            actual[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    allowed = set(expected) | (FONT_FILES if with_fonts else set())
    if with_fonts and any(not (stage / name).is_file() for name in FONT_FILES):
        fail('PUBLIC_STAGE_FONT_FILES_MISSING')
    allowed_directories = {parent.as_posix() for name in allowed for parent in PurePosixPath(name).parents}
    for path in stage.rglob('*'):
        name = path.relative_to(stage).as_posix()
        if path.is_symlink() or (path.is_file() and name not in allowed) or (path.is_dir() and name not in allowed_directories):
            fail(f'PUBLIC_STAGE_UNDECLARED_ENTRY: {name}')
    if actual != expected:
        fail('PUBLIC_STAGE_CLOSURE_OR_DIGEST_MISMATCH')
    check_artifact_namespace(stage)
    return {'schema': SCHEMA, 'profile': 'PUBLIC', 'excluded_namespace': PRIVATE,
            'optional_backend': 'NOT_INCLUDED', 'file_count': len(actual),
            'files': [{'path': path, 'sha256': digest} for path, digest in sorted(actual.items())]}


def stage_public(source: Path, stage: Path, manifest: dict, *, docker: bool = False) -> dict:
    files = check_source(source, manifest)
    if docker:
        files.update(check_docker_inputs(source, manifest))
    if stage.exists():
        fail('PUBLIC_STAGE_MUST_BE_FRESH')
    # Copy only enumerated public files, never the repository or private tree.
    stage.mkdir(parents=True)
    for name in files:
        destination = stage / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, destination)
    return verify_stage(source, stage, manifest, docker=docker)


def verify_wheel(source: Path, wheel: Path, manifest: dict) -> dict:
    """Check the actual Python distribution without importing application code.

    Python package files and declared contract data must match the same PUBLIC
    source hashes used by staging. Config/prompts/workflows remain separate stage
    assets; a wheel receipt is not standalone application or platform acceptance.
    """
    try:
        from packaging.markers import Marker
        from packaging.requirements import InvalidRequirement, Requirement
        from packaging.utils import canonicalize_name
    except ImportError:
        fail('PUBLIC_WHEEL_VERIFIER_TOOLING_UNAVAILABLE: packaging')
    sources = check_source(source, manifest)
    sources.update(check_docker_inputs(source, manifest))
    project = tomllib.loads((source / 'pyproject.toml').read_text())
    metadata = project['project']
    distribution = metadata['name'].replace('-', '_') + '-' + metadata['version']
    info = distribution + '.dist-info/'
    python_roots = ROOTS[:3]
    expected = {name: digest for name, digest in sources.items()
                if PurePosixPath(name).parts[0] in python_roots}
    source_names = {name: name for name in expected}
    for destination, patterns in project['tool']['setuptools'].get('data-files', {}).items():
        for pattern in patterns:
            matches = list(source.glob(pattern))
            if not matches:
                fail('PUBLIC_WHEEL_DATA_GLOB_EMPTY')
            for path in matches:
                original = path.relative_to(source).as_posix()
                name = f'{distribution}.data/data/{destination}/{path.name}'
                if original not in sources or name in expected or path.is_symlink():
                    fail('PUBLIC_WHEEL_DATA_INPUT_INVALID')
                expected[name] = sources[original]
                source_names[name] = original
    metadata_names = {info + name for name in ('METADATA', 'WHEEL', 'top_level.txt', 'RECORD')}
    if wheel.is_symlink() or not wheel.is_file() or wheel.suffix != '.whl':
        fail('PUBLIC_WHEEL_INVALID')
    with zipfile.ZipFile(wheel) as archive:
        check_archive(archive)
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if any(name.startswith('/') or '\\' in name or '..' in PurePosixPath(name).parts
               or PurePosixPath(name).as_posix() != name for name in names):
            fail('PUBLIC_WHEEL_UNSAFE_PATH')
        if len(names) != len(set(names)) or any(stat.S_ISLNK(entry.external_attr >> 16) for entry in entries):
            fail('PUBLIC_WHEEL_DUPLICATE_OR_SYMLINK')
        if set(names) != set(expected) | metadata_names:
            fail('PUBLIC_WHEEL_CLOSURE_MISMATCH')
        if any(entry.file_size != (source / source_names[entry.filename]).stat().st_size
               for entry in entries if entry.filename in expected):
            fail('PUBLIC_WHEEL_SOURCE_DIGEST_MISMATCH')
        if any(entry.file_size > 1024 * 1024 for entry in entries if entry.filename in metadata_names):
            fail('PUBLIC_WHEEL_METADATA_TOO_LARGE')
        payloads = {name: archive.read(name) for name in names}
        if any(hashlib.sha256(payloads[name]).hexdigest() != digest for name, digest in expected.items()):
            fail('PUBLIC_WHEEL_SOURCE_DIGEST_MISMATCH')
        if any(PRIVATE.encode() in payloads[name].lower() for name in metadata_names):
            fail('PUBLIC_PRIVATE_WHEEL_METADATA')
        headers = BytesParser().parsebytes(payloads[info + 'METADATA'])
        wheel_headers = BytesParser().parsebytes(payloads[info + 'WHEEL'])
        if (headers.get_all('Name') != [metadata['name']] or headers.get_all('Version') != [metadata['version']]
                or headers.get_all('Requires-Python') != [metadata['requires-python']]
                or wheel_headers.get_all('Wheel-Version') != ['1.0']
                or wheel_headers.get_all('Root-Is-Purelib') != ['true']
                or wheel_headers.get_all('Tag') != ['py3-none-any']
                or Counter(payloads[info + 'top_level.txt'].decode().splitlines()) != Counter(python_roots)):
            fail('PUBLIC_WHEEL_METADATA_MISMATCH')
        try:
            requirements = [Requirement(value) for value in metadata.get('dependencies', [])]
            extras = metadata.get('optional-dependencies', {})
            for extra, values in extras.items():
                for value in values:
                    requirement = Requirement(value)
                    marker = f'extra == "{canonicalize_name(extra)}"'
                    requirement.marker = Marker(f'({requirement.marker}) and {marker}' if requirement.marker else marker)
                    requirements.append(requirement)
            actual_requirements = [Requirement(value) for value in headers.get_all('Requires-Dist', [])]
        except InvalidRequirement:
            fail('PUBLIC_WHEEL_DEPENDENCY_MISMATCH')
        if (Counter(actual_requirements) != Counter(requirements)
                or Counter(headers.get_all('Provides-Extra', [])) != Counter(canonicalize_name(extra) for extra in extras)):
            fail('PUBLIC_WHEEL_DEPENDENCY_MISMATCH')
        records = list(csv.reader(io.StringIO(payloads[info + 'RECORD'].decode())))
        if any(len(row) != 3 for row in records) or len(records) != len(names) or {row[0] for row in records} != set(names):
            fail('PUBLIC_WHEEL_RECORD_CLOSURE_MISMATCH')
        for name, digest, size in records:
            if name == info + 'RECORD':
                if digest or size:
                    fail('PUBLIC_WHEEL_RECORD_INVALID')
                continue
            actual = 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(payloads[name]).digest()).rstrip(b'=').decode()
            if digest != actual or size != str(len(payloads[name])):
                fail('PUBLIC_WHEEL_RECORD_DIGEST_MISMATCH')
    return {'schema': SCHEMA, 'profile': 'PUBLIC', 'excluded_namespace': PRIVATE,
            'optional_backend': 'NOT_INCLUDED', 'artifact': wheel.name,
            'artifact_sha256': hashlib.sha256(wheel.read_bytes()).hexdigest(),
            'file_count': len(expected), 'wheel_member_count': len(names),
            'requires_dist': headers.get_all('Requires-Dist', []),
            'metadata_dependencies_verified': True,
            'wheel_tags': wheel_headers.get_all('Tag'),
            'separate_stage_files': sorted(set(sources) - set(source_names.values())),
            'files': [{'path': name, 'source_path': source_names[name], 'sha256': digest}
                      for name, digest in sorted(expected.items())]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--stage', type=Path)
    parser.add_argument('--verify-stage', type=Path)
    parser.add_argument('--application', type=Path)
    parser.add_argument('--wheel', type=Path)
    parser.add_argument('--receipt', type=Path)
    parser.add_argument('--docker', action='store_true')
    parser.add_argument('--with-fonts', action='store_true')
    args = parser.parse_args()
    manifest_path = args.manifest or args.source / 'packaging/public-build.json'
    manifest = load_manifest(manifest_path)
    result = {'schema': SCHEMA, 'profile': 'PUBLIC', 'file_count': len(check_source(args.source, manifest))}
    if args.stage:
        result = stage_public(args.source, args.stage, manifest, docker=args.docker)
    if args.verify_stage:
        result = verify_stage(args.source, args.verify_stage, manifest, docker=args.docker, with_fonts=args.with_fonts)
    if args.application:
        check_artifact_namespace(args.application)
    if args.wheel:
        result = verify_wheel(args.source, args.wheel, manifest)
    if args.receipt:
        # Refuse replacing an existing receipt, including symlinks.
        with args.receipt.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, indent=2, sort_keys=True)
            stream.write('\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'files'}, sort_keys=True))


if __name__ == '__main__':
    main()
