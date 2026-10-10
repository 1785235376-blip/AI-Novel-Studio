"""Opt-in catalog snapshots preserve staged source and fail before publication."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from scripts import refresh_v2_staged_catalog as catalog


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, text=True).strip()


def put(root, name, value):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding='utf-8')


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / 'repository'
    root.mkdir()
    git(root, 'init', '-q')
    put(root, 'app/current.py', 'staged source')
    put(root, 'docs/delivery/history.txt', 'historical evidence')
    put(root, 'docs/delivery/v2-development/keep.txt', 'existing receipts')
    for name in catalog.OUTPUTS:
        put(root, name, 'old catalog: ' + name)
    put(root, 'scripts/refresh_product_api_catalog.py',
        'from pathlib import Path\n'
        f'for name in {catalog.OUTPUTS!r}:\n'
        "    Path(name).write_text('generated: ' + Path('app/current.py').read_text())\n")
    git(root, 'add', '.')
    return root


def stage(root):
    git(root, 'add', '.')
    return git(root, 'write-tree')


def snapshot(root, destination):
    destination.mkdir()
    return catalog.compact_snapshot(root, git(root, 'write-tree'), destination)


@pytest.mark.parametrize('name,excluded', [
    ('docs/delivery', True), ('docs/delivery/receipt.json', True),
    ('docs/delivery/deep/evidence.log', True), ('docs/delivery.md', False),
    ('docs/delivery-next/file', False), ('docs/deliveries/file', False),
    ('other/docs/delivery/file', False), ('docs/Delivery/file', False),
])
def test_exclusion_has_exact_directory_boundary(name, excluded):
    assert catalog.delivery_path(name) is excluded


def test_snapshot_reads_the_named_tree_not_current_index_or_worktree(repository, tmp_path):
    root = repository
    put(root, 'docs/delivery-next/file', 'retained evidence-like name')
    put(root, 'frontend/test.ts', 'frontend remains included')
    original_tree = stage(root)
    put(root, 'app/current.py', 'later staged source')
    git(root, 'add', 'app/current.py')
    put(root, 'app/current.py', 'unstaged source')
    put(root, 'app/untracked.py', 'must not be copied')
    folder = tmp_path / 'snapshot'
    folder.mkdir()
    report = catalog.compact_snapshot(root, original_tree, folder)
    assert (folder / 'app/current.py').read_text() == 'staged source'
    assert not (folder / 'app/untracked.py').exists()
    assert not (folder / 'docs/delivery').exists()
    assert (folder / 'docs/delivery-next/file').read_text() == 'retained evidence-like name'
    assert (folder / 'frontend/test.ts').is_file()
    retained = {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}
    expected = set(git(root, 'ls-tree', '-r', '--name-only', original_tree).splitlines())
    assert retained == {name for name in expected if not catalog.delivery_path(name)}
    assert report['retained_files'] == len(retained)
    assert report['retained_blob_bytes'] == sum((folder / p).stat().st_size for p in retained)
    assert report['excluded_files'] == 2
    assert len(report['retained_inventory_sha256']) == 64
    assert (root / 'docs/delivery/history.txt').read_text() == 'historical evidence'


@pytest.mark.parametrize('compact', [False, True])
def test_refresh_runs_staged_generator_and_source_only(repository, monkeypatch, compact):
    root = repository
    tree = git(root, 'write-tree')
    put(root, 'scripts/refresh_product_api_catalog.py', "raise RuntimeError('unstaged generator')")
    put(root, 'app/current.py', 'unstaged source')
    old_receipt = root / f'docs/delivery/v2-development/catalog-{tree[:12]}.json'
    if compact:
        old_receipt.write_text('existing full receipt must remain unchanged')
    monkeypatch.setattr(catalog, 'ROOT', root)
    catalog.main(['--compact'] if compact else [])
    assert all((root / name).read_text() == 'generated: staged source' for name in catalog.OUTPUTS)
    if compact:
        assert old_receipt.read_text() == 'existing full receipt must remain unchanged'
        receipts = list((root / 'docs/delivery/v2-development').glob(f'catalog-{tree[:12]}-compact-*.json'))
        assert len(receipts) == 1
        receipt = json.loads(receipts[0].read_text())
    else:
        receipt = json.loads(old_receipt.read_text())
    assert receipt['staged_tree'] == tree
    folder = Path(receipt['cwd'])
    assert (folder / 'docs/delivery/history.txt').exists() is (not compact)
    assert ('snapshot' in receipt) is compact
    assert receipt['sha256'] == {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in catalog.OUTPUTS}
    if compact:
        assert (folder / '.profile/catalog-import-origins.json').is_file()
    else:
        assert receipt['command'][-1] == 'scripts/refresh_product_api_catalog.py'


@pytest.mark.parametrize('kind', ['generator-error', 'missing-output', 'outside-import',
                                  'outside-namespace', 'delivery-read'])
def test_generation_or_provenance_failure_publishes_no_catalog(repository, monkeypatch, kind):
    root = repository
    before = {name: (root / name).read_bytes() for name in catalog.OUTPUTS}
    source = (root / 'scripts/refresh_product_api_catalog.py').read_text()
    if kind == 'generator-error':
        source += "raise RuntimeError('original failure retained')\n"
    elif kind == 'missing-output':
        source += "Path('API_OPENAPI.json.gz').unlink()\n"
    elif kind in {'outside-import', 'outside-namespace'}:
        source += "import types, sys\nmodule = types.ModuleType('app.synthetic')\n"
        if kind == 'outside-import':
            source += f"module.__file__ = {str(root / 'app/current.py')!r}\n"
        else:
            source += f"module.__path__ = [{str(root / 'app')!r}]\n"
        source += "sys.modules['app.synthetic'] = module\n"
    else:
        source += "Path('docs/delivery/history.txt').read_text()\n"
    put(root, 'scripts/refresh_product_api_catalog.py', source)
    stage(root)
    monkeypatch.setattr(catalog, 'ROOT', root)
    with pytest.raises((subprocess.CalledProcessError, FileNotFoundError)) as failure:
        catalog.main(['--compact'])
    error = failure.value
    if kind == 'missing-output':
        assert isinstance(error, FileNotFoundError) and error.filename.endswith('API_OPENAPI.json.gz')
    else:
        expected = ('original failure retained' if kind == 'generator-error' else
                    'excluded delivery evidence' if kind == 'delivery-read' else
                    'Project import escaped compact snapshot')
        assert expected in error.stderr
    assert {name: (root / name).read_bytes() for name in catalog.OUTPUTS} == before
    assert not list((root / 'docs/delivery/v2-development').glob('catalog-*.json'))
    assert len(list((root / '.runtime/v2-staged').iterdir())) == 1


@pytest.mark.parametrize('attribute', ['export-ignore', 'export-subst'])
def test_archive_attributes_cannot_silently_change_retained_staged_bytes(repository, tmp_path, attribute):
    root = repository
    put(root, 'app/current.py', '$Format:%H$')
    put(root, '.gitattributes', f'app/current.py {attribute}\n')
    stage(root)
    if attribute == 'export-subst':
        # Substitution is applied only when archive is given a commit/tag, while
        # production passes an exact tree. The staged literal must stay intact.
        folder = tmp_path / 'snapshot'
        snapshot(root, folder)
        assert (folder / 'app/current.py').read_text() == '$Format:%H$'
    else:
        with pytest.raises(ValueError, match='omitted retained'):
            snapshot(root, tmp_path / 'snapshot')


def test_retained_symlink_is_rejected_before_generator(repository, tmp_path):
    (repository / 'app/link.py').symlink_to('current.py')
    stage(repository)
    with pytest.raises(ValueError, match='regular retained blobs'):
        snapshot(repository, tmp_path / 'snapshot')


def test_excluded_evidence_symlink_is_not_followed(repository, tmp_path):
    (repository / 'docs/delivery/link').symlink_to(tmp_path / 'outside')
    stage(repository)
    folder = tmp_path / 'snapshot'
    snapshot(repository, folder)
    assert not (folder / 'docs/delivery').exists()
    assert not (tmp_path / 'outside').exists()


def test_invalid_tree_stops_before_archive(repository, tmp_path):
    folder = tmp_path / 'snapshot'
    folder.mkdir()
    with pytest.raises(subprocess.CalledProcessError):
        catalog.compact_snapshot(repository, '0' * 40, folder)


@pytest.mark.parametrize('tree', ['HEAD', 'refs/heads/main', 'a' * 39, 'A' * 40])
def test_mutable_refs_and_abbreviations_are_rejected(repository, tmp_path, tree):
    folder = tmp_path / 'snapshot'
    folder.mkdir()
    with pytest.raises(ValueError, match='exact staged tree ID'):
        catalog.compact_snapshot(repository, tree, folder)


def test_commit_object_cannot_replace_exact_tree(repository, tmp_path):
    git(repository, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
        'commit', '-qm', 'fixture')
    folder = tmp_path / 'snapshot'
    folder.mkdir()
    with pytest.raises(ValueError, match='tree object'):
        catalog.compact_snapshot(repository, git(repository, 'rev-parse', 'HEAD'), folder)


def test_existing_destination_cannot_supply_untracked_sources(repository, tmp_path):
    folder = tmp_path / 'snapshot'
    put(folder, 'app/stealth.py', 'not in any staged source')
    with pytest.raises(ValueError, match='new empty destination'):
        catalog.compact_snapshot(repository, git(repository, 'write-tree'), folder)


def test_compact_byte_validation_rejects_extraction_drift(repository, tmp_path, monkeypatch):
    extract = catalog.tarfile.TarFile.extract
    def mutate(archive, member, path, **kwargs):
        extract(archive, member, path, **kwargs)
        if member.name == 'app/current.py':
            (Path(path) / member.name).write_text('changed after archive')
    monkeypatch.setattr(catalog.tarfile.TarFile, 'extract', mutate)
    with pytest.raises(ValueError, match='differ from staged Git blob'):
        snapshot(repository, tmp_path / 'snapshot')
