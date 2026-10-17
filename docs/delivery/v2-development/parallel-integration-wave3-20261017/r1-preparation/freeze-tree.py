"""PREPARED ONLY: freeze merged wave3 after explicit parent release; no product imports."""
import hashlib, json, pathlib, runpy, subprocess
R = pathlib.Path.cwd()
D = R / 'docs/delivery/v2-development/parallel-integration-wave3-20261017'
BASELINE = '9325818bbd98ad086db64ca0266aca6e7c4223b8'
def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()
def tree(commit):
    result = {}
    for row in subprocess.check_output(['git', 'ls-tree', '-r', '-z', commit]).decode().split('\0'):
        if row:
            metadata, path = row.split('\t', 1)
            result[path] = metadata.split()[2]
    return result
release = json.loads((D / 'parent-release.json').read_text())
assert release['authorized'] is True and release['scope_final'] is True
assert release['baseline'] == BASELINE
head = release['head']
assert git('rev-parse', 'HEAD') == head
assert not git('diff', 'HEAD', '--name-only'), 'tracked edits before freeze'
assert not (D / 'release-freeze.json').exists(), 'never overwrite freeze'
current, baseline = tree(head), tree(BASELINE)
assert len(release['feature_commits']) == 4
proof = {}
for commit in release['feature_commits']:
    subprocess.run(['git', 'merge-base', '--is-ancestor', commit, head], check=True)
    paths = git('diff-tree', '--no-commit-id', '--name-only', '-r', commit).splitlines()
    feature = tree(commit)
    for path in paths:
        assert feature.get(path) == current.get(path), (commit, path, 'feature blob differs')
    proof[git('rev-parse', commit)] = {p: feature.get(p) for p in paths}
old_tests = [p for p in baseline if p.startswith(('tests/', 'frontend/tests/')) or p.startswith('frontend/src/') and ('.test.' in p or '.spec.' in p)]
old_docs = [p for p in baseline if p.startswith('docs/')]
protected = old_tests + old_docs + [p for p in baseline if p.startswith(('.github/', 'scripts/', 'local_interop_')) or p in {'AGENTS.md', 'pyproject.toml', 'packaging/public-build.json'}]
for path in protected:
    assert baseline[path] == current.get(path), ('protected baseline', path)
assert hashlib.sha256((R / 'scripts/run_v2_checks.py').read_bytes()).hexdigest() == '64cf16c26412c5a1e36a1d4fb799519111ad409f7594ae15aa0b158e53396cd5'
assert hashlib.sha256((R / 'packaging/public-build.json').read_bytes()).hexdigest() == '353b92aff6116d873ea4402a1ef627e7899214b46ba823a9b4300ba75c5d0448'
source = runpy.run_path(str(R / 'scripts/run_v2_checks.py'))['source_snapshot'](R)
changed_runtime = sorted(p for p in current if p.startswith('app/') and current[p] != baseline.get(p))
assert changed_runtime == sorted(release['changed_runtime'])
result = {'status': 'FROZEN_AFTER_PARENT_RELEASE', 'head': head, 'tree': git('rev-parse', 'HEAD^{tree}'), 'baseline': BASELINE, 'source_commits': proof, 'changed_runtime': changed_runtime, 'tracked_sha256': {p: hashlib.sha256((R / p).read_bytes()).hexdigest() for p in current}, 'source_sha256': source, 'source_count': len(source), 'protected_old_tests': len(old_tests), 'protected_old_docs': len(old_docs), 'manifest_sha256': hashlib.sha256((R / 'packaging/public-build.json').read_bytes()).hexdigest(), 'lineage': git('log', '-12', '--format=%H %P %s')}
(D / 'release-freeze.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k: result[k] for k in ['status', 'head', 'tree', 'source_count', 'changed_runtime']}, indent=2))
