"""Refresh catalogs from the staged tree, without binding unfinished work."""
from __future__ import annotations
import hashlib
import argparse
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ('API_CATALOG.json', 'API_CATALOG.md', 'API_CATALOG_DETAIL.json.gz', 'API_OPENAPI.json.gz')
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))
from scripts.run_v2_checks import isolated_environment


def delivery_path(name):
    """Exclude exactly this historical evidence directory, never similarly named files."""
    return name == 'docs/delivery' or name.startswith('docs/delivery/')


def compact_snapshot(root, tree, folder):
    """Stream an immutable Git tree, retaining every blob outside delivery evidence.

    Inventory checks deliberately fail on archive attributes, links or other
    transformations that would make the compact snapshot differ from the tree.
    No checkout files or installed application package are used as substitutes.
    """
    if folder.is_symlink() or not folder.is_dir() or any(folder.iterdir()):
        raise ValueError('Compact snapshot requires a new empty destination directory')
    if len(tree) != 40 or any(c not in '0123456789abcdef' for c in tree):
        raise ValueError('Compact snapshot requires an exact staged tree ID')
    if subprocess.check_output(['git', 'cat-file', '-t', tree], cwd=root, text=True).strip() != 'tree':
        raise ValueError('Compact snapshot requires a tree object, not a commit or mutable ref')
    raw = subprocess.check_output(['git', 'ls-tree', '-r', '-z', '-l', tree], cwd=root)
    retained = {}
    directories = set()
    excluded_files = excluded_bytes = 0
    for row in raw.split(b'\0'):
        if not row:
            continue
        header, path = row.split(b'\t', 1)
        mode, kind, oid, size = header.decode().split()
        name = path.decode('utf-8')
        parts = name.split('/')
        directories.update('/'.join(parts[:index]) for index in range(1, len(parts)))
        if delivery_path(name):
            excluded_files += 1
            excluded_bytes += int(size) if size != '-' else 0
            continue
        if kind != 'blob' or mode not in {'100644', '100755'}:
            raise ValueError(f'Compact snapshot requires regular retained blobs: {name}')
        retained[name] = {'oid': oid, 'bytes': int(size), 'mode': mode}
    if not retained:
        raise ValueError('Compact snapshot cannot be empty')
    seen = set()
    with subprocess.Popen(['git', 'archive', '--format=tar', tree], cwd=root,
                          stdout=subprocess.PIPE) as process:
        try:
            with tarfile.open(fileobj=process.stdout, mode='r|') as archive:
                for member in archive:
                    name = member.name.rstrip('/')
                    if delivery_path(name):
                        continue
                    if member.isdir():
                        if name not in directories:
                            raise ValueError(f'Unexpected archive directory: {name}')
                    elif not member.isfile() or name not in retained or name in seen:
                        raise ValueError(f'Unexpected archive member: {name}')
                    else:
                        seen.add(name)
                    archive.extract(member, folder, filter='data')
        finally:
            process.stdout.close()
        if process.wait() != 0:
            raise RuntimeError('Git archive failed; compact snapshot is unusable')
    if seen != set(retained):
        raise ValueError('Git archive omitted retained staged files')
    for name, meta in retained.items():
        value = (folder / name).read_bytes()
        oid = hashlib.sha1(b'blob ' + str(len(value)).encode() + b'\0' + value).hexdigest()
        if oid != meta['oid']:
            raise ValueError(f'Archive bytes differ from staged Git blob: {name}')
    return {'mode': 'compact', 'excluded_prefix': 'docs/delivery/',
            'retained_files': len(retained), 'retained_blob_bytes': sum(v['bytes'] for v in retained.values()),
            'excluded_files': excluded_files, 'excluded_blob_bytes': excluded_bytes,
            'retained_inventory_sha256': hashlib.sha256(json.dumps(retained, sort_keys=True).encode()).hexdigest()}


COMPACT_BOOTSTRAP = """import json, os, runpy, sys
from pathlib import Path
root = Path.cwd().resolve()
omitted = root / 'docs' / 'delivery'
def reject_omitted_reads(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
        path = Path(os.fsdecode(args[0])).resolve()
        if path == omitted or path.is_relative_to(omitted):
            raise RuntimeError('Compact catalog accessed excluded delivery evidence')
sys.addaudithook(reject_omitted_reads)
runpy.run_path(str(root / 'scripts/refresh_product_api_catalog.py'), run_name='__main__')
origins = {}
for name, module in list(sys.modules.items()):
    if name.split('.')[0] in {'app', 'local_interop_protocol', 'local_interop_desktop'}:
        for origin in [getattr(module, '__file__', None), *getattr(module, '__path__', [])]:
            if origin and not Path(origin).resolve().is_relative_to(root):
                raise RuntimeError('Project import escaped compact snapshot: ' + name)
        if getattr(module, '__file__', None):
            origins[name] = str(Path(module.__file__).resolve().relative_to(root))
(root / '.profile/catalog-import-origins.json').write_text(json.dumps(origins, sort_keys=True) + '\\n')
"""


def generate_catalog(folder, compact=False):
    command = [sys.executable, '-B', '-c', COMPACT_BOOTSTRAP] if compact else [
        sys.executable, '-B', 'scripts/refresh_product_api_catalog.py']
    result = subprocess.run(command, cwd=folder, env=staged_environment(folder),
                            capture_output=True, text=True, encoding='utf-8',
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    print(result.stdout + result.stderr)
    result.check_returncode()
    # Read every output before publishing any, so missing outputs cannot leave
    # a mixed catalog after an otherwise successful generator invocation.
    return command, {name: (folder / name).read_bytes() for name in OUTPUTS}


def staged_environment(folder):
    """Catalog imports may initialize identity stores; own every state path."""
    env = os.environ.copy()
    for key in list(env):
        if key.endswith(("_API_KEY", "_TOKEN", "_SECRET")) or key in {
            "DATABASE_URL", "TEST_POSTGRES_DATABASE_URL", "E2E_DATABASE_URL",
            "COLLABORATION_DEV_SESSIONS_JSON", "PACKAGED_CONTROL_PIPE",
        }:
            env.pop(key, None)
    env.update(isolated_environment(folder, folder / '.profile'))
    return env

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compact', action='store_true',
                        help='Opt in to omitting only docs/delivery from the staged snapshot')
    args = parser.parse_args(argv)
    tree = subprocess.check_output(['git', 'write-tree'], cwd=ROOT, text=True).strip()
    folder = ROOT / '.runtime' / 'v2-staged' / uuid4().hex
    folder.mkdir(parents=True)
    snapshot = None
    if args.compact:
        snapshot = compact_snapshot(ROOT, tree, folder)
    else:
        archive = subprocess.check_output(['git', 'archive', '--format=tar', tree], cwd=ROOT)
        with tarfile.open(fileobj=io.BytesIO(archive)) as contents:
            contents.extractall(folder, filter='data')
    command, outputs = generate_catalog(folder, args.compact)
    if snapshot is not None:
        snapshot['project_import_origins_sha256'] = hashlib.sha256(
            (folder / '.profile/catalog-import-origins.json').read_bytes()).hexdigest()
    hashes = {}
    for name, value in outputs.items():
        (ROOT / name).write_bytes(value)
        hashes[name] = hashlib.sha256(value).hexdigest()
    suffix = f'-compact-{folder.name}' if args.compact else ''
    evidence = ROOT / 'docs' / 'delivery' / 'v2-development' / f'catalog-{tree[:12]}{suffix}.json'
    evidence.write_text(json.dumps({'staged_tree': tree, 'utc': datetime.now(timezone.utc).isoformat(),
                                   'command': command,
                                   'cwd': str(folder), 'exit_code': 0,
                                   **({'snapshot': snapshot} if snapshot else {}),
                                   'sha256': hashes}, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'snapshot': str(folder), 'receipt': str(evidence)}))

if __name__ == '__main__':
    main()
