"""Reviewed c40 source closure and staged PUBLIC isolation; no service startup."""
from __future__ import annotations

import ast
import importlib.util
import re
import runpy

import pytest

from test_public_build_profile import ROOT, build


REVIEWED_MODULES = frozenset({
    'app/creative/graph_conditions_catalog.py',
    'app/creative/graph_failed_retry.py',
    'app/creative/graph_local_conditions.py',
    'app/creative/graph_local_subgraph.py',
    'app/creative/impact_reads.py',
    'app/creative/storyboard_video_timeline.py',
    'app/experimental/audio_manifest.py',
    'app/experimental/audio_manifest_api.py',
    'app/experimental/comic_timeline_handoff.py',
    'app/experimental/portable_cache_policy.py',
    'app/experimental/safe_batch_studio_image.py',
    'app/experimental/storyboard_impact_adapter.py',
    'app/services/asset_bounded_file_windows.py',
    'app/services/comic_page_origin.py',
    'app/services/comic_page_source_reads.py',
    'app/services/studio_audio_denoise.py',
    'app/services/studio_audio_loudness.py',
    'app/services/studio_image_composite.py',
    'app/services/studio_image_cutout_webp.py',
    'app/services/studio_timeline_links.py',
})
_LOCAL_ROOTS = ('app', 'local_interop_protocol', 'local_interop_desktop')
_PRIVATE_SURFACE = re.compile(
    r'studio_private_extensions|(?:^|[^a-z0-9])(?:nsfw|mature[_-]only|adult[_-]only)(?:$|[^a-z0-9])',
    re.IGNORECASE,
)


def _module_path(root, name):
    if name.split('.')[0] not in _LOCAL_ROOTS:
        return None
    for path in (name.replace('.', '/') + '.py', name.replace('.', '/') + '/__init__.py'):
        if (root / path).is_file():
            return path
    raise AssertionError('Local import has no staged module: ' + name)


def _local_imports(root, path, tree):
    module = path[:-3].replace('/', '.')
    package = module[:-9] if path.endswith('/__init__.py') else module.rpartition('.')[0]
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            name = (importlib.util.resolve_name('.' * node.level + (node.module or ''), package)
                    if node.level else node.module or '')
            names.add(name)
            for alias in node.names:
                child = name + '.' + alias.name
                if any((root / candidate).is_file() for candidate in (
                        child.replace('.', '/') + '.py', child.replace('.', '/') + '/__init__.py')):
                    names.add(child)
        elif isinstance(node, ast.Call) and (
                isinstance(node.func, ast.Name) and node.func.id in {'__import__', 'import_module'}
                or isinstance(node.func, ast.Attribute) and node.func.attr == 'import_module'):
            assert node.args and isinstance(node.args[0], ast.Constant), (path, node.lineno)
            name = node.args[0].value
            assert isinstance(name, str), (path, node.lineno)
            names.add(importlib.util.resolve_name(name, package) if name.startswith('.') else name)
    paths = set()
    for name in names:
        resolved = _module_path(root, name)
        if resolved:
            paths.add(resolved)
            # Importing a module also consumes every package initializer.
            for count in range(1, len(name.split('.'))):
                parent = '/'.join(name.split('.')[:count]) + '/__init__.py'
                if (root / parent).is_file():
                    paths.add(parent)
    return paths


def _private_surface_refs(tree):
    # Shared policy vocabulary/docstrings remain legal. Inspect executable names
    # and strings so a private router, executor or capability cannot hide there.
    docstrings = {id(node.body[0].value) for node in ast.walk(tree)
                  if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                  and ast.get_docstring(node, clean=False) is not None}
    for node in ast.walk(tree):
        value = None
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            value = node.value
        elif isinstance(node, ast.Name):
            value = node.id
        elif isinstance(node, ast.Attribute):
            value = node.attr
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            value = node.name
        elif isinstance(node, ast.alias):
            value = node.name
        if value is not None and _PRIVATE_SURFACE.search(value):
            yield node.lineno, value


@pytest.fixture(scope='module')
def public_stage(tmp_path_factory):
    stage = tmp_path_factory.mktemp('c40-public-parent') / 'stage'
    manifest = build.load_manifest(ROOT / 'packaging/public-build.json')
    receipt = build.stage_public(ROOT, stage, manifest)
    assert manifest['profile'] == 'PUBLIC'
    assert manifest['excluded_namespace'] == build.PRIVATE == 'studio_private_extensions'
    return stage, manifest, receipt


def test_reviewed_modules_have_a_closed_staged_local_import_graph(public_stage):
    stage, manifest, receipt = public_stage
    allowed = set(manifest['files'])
    assert REVIEWED_MODULES <= allowed
    assert {item['path'] for item in receipt['files']} == allowed
    pending, seen = list(REVIEWED_MODULES), set()
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        assert path in allowed, 'Unreviewed transitive import: ' + path
        seen.add(path)
        tree = ast.parse((stage / path).read_text(encoding='utf-8-sig'), filename=path)
        pending.extend(_local_imports(stage, path, tree) - seen)
    assert REVIEWED_MODULES <= seen


def test_actual_public_payload_has_no_private_execution_surface(public_stage):
    stage, manifest, _ = public_stage
    assert not (stage / build.PRIVATE).exists()
    for path in manifest['files']:
        assert build.PRIVATE not in path.casefold()
        if path.endswith('.py'):
            tree = ast.parse((stage / path).read_text(encoding='utf-8-sig'), filename=path)
            assert not list(_private_surface_refs(tree)), path
    policy = runpy.run_path(str(stage / 'app/creative/content_policy.py'))
    assert policy['STATUS'] == 'RESERVED'
    assert policy['DEFAULT_CONTENT_POLICY'] == 'STANDARD'
    # Compatibility vocabulary is preserved without adding an enabled mode.
    assert 'MATURE' in policy['POLICIES']
    notice = policy['export_notice']('MATURE')
    assert notice['status'] == 'RESERVED' and not notice['rendered'] and not notice['blocking']


@pytest.mark.parametrize('source', [
    "router = APIRouter(prefix='/nsfw/private')",
    "def nsfw_executor(): pass",
    "capability = 'nsfw.execute'",
    "import studio_private_extensions.optional",
])
def test_private_surface_audit_detects_routes_executors_and_capabilities(source):
    assert list(_private_surface_refs(ast.parse(source)))
