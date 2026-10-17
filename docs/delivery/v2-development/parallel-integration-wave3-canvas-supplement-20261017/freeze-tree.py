"""Freeze approved frontend-only supplement; no product imports."""
import hashlib, json, pathlib, runpy, subprocess
R = pathlib.Path.cwd()
D = R / 'docs/delivery/v2-development/parallel-integration-wave3-canvas-supplement-20261017'
BASE = '550396ae4de489e21c41288335dae557bbd5dbfa'
ACCEPTED = 'db6487b5eab7340433426fefcb5499122ec3d881'
def git(*args): return subprocess.check_output(['git', *args], text=True).strip()
def tree(c):
    result = {}
    for row in subprocess.check_output(['git', 'ls-tree', '-rz', c]).decode().split('\0'):
        if row:
            meta, path = row.split('\t'); result[path] = meta.split()[2]
    return result
release = json.loads((D / 'parent-release.json').read_text())
assert release['authorized'] is True
head, feature = release['head'], release['feature_commit']
assert git('rev-parse', 'HEAD') == head
assert not git('diff', 'HEAD', '--name-only')
assert not (D / 'release-freeze.json').exists()
subprocess.run(['git', 'merge-base', '--is-ancestor', feature, head], check=True)
a, old, current, f = tree(ACCEPTED), tree(BASE), tree(head), tree(feature)
allowed = sorted([
 'frontend/src/creative/GraphDirectorConsole.tsx',
 'frontend/src/creative/useStudioGraphEditor.tsx',
 'frontend/src/creative/useStudioGraphEditorController.ts',
 'frontend/src/creative/directorCanvasHandoff.ts',
 'frontend/src/creative/GraphDirectorCanvasHandoff.additive.test.tsx',
 'frontend/src/creative/ReviewedDirectorCanvas.integration.test.tsx',
 'frontend/src/creative/directorCanvasHandoff.additive.test.tsx'])
actual = sorted(p for p in set(old) | set(current) if old.get(p) != current.get(p) and not p.startswith('docs/'))
assert actual == allowed, actual
for p in git('diff-tree', '--no-commit-id', '--name-only', '-r', feature).splitlines():
    assert current.get(p) == f.get(p), ('feature byte mismatch', p)
for p in old:
    if p not in allowed: assert current.get(p) == old[p], ('baseline preservation', p)
backend = [p for p in a if p.startswith(('app/', 'tests/', 'local_interop_', 'scripts/', '.github/', 'packaging/')) or p.endswith('.py') or p == 'pyproject.toml']
for p in backend: assert current.get(p) == a[p], ('backend/infrastructure drift', p)
source = runpy.run_path(str(R / 'scripts/run_v2_checks.py'))['source_snapshot'](R)
result = {'status': 'FROZEN_FRONTEND_ONLY_SUPPLEMENT', 'head': head, 'tree': git('rev-parse', 'HEAD^{tree}'), 'feature_commit': feature, 'accepted_backend_head': ACCEPTED, 'evidence_baseline': BASE, 'exact_frontend_delta': allowed, 'backend_paths_byte_identical': len(backend), 'tracked_sha256': {p: hashlib.sha256((R / p).read_bytes()).hexdigest() for p in current}, 'source_sha256': source}
(D / 'release-freeze.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k:v for k,v in result.items() if k not in {'tracked_sha256','source_sha256'}}, indent=2))
