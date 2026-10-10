"""Verify two independent complete collections; inventory is not execution."""
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

root = Path.cwd()
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / '.github/ci'))
from scripts.run_v2_checks import isolated_environment, source_snapshot
from suite_coverage import source_errors

sha = lambda b: hashlib.sha256(b).hexdigest()
git = lambda *args: subprocess.check_output(['git', *args], cwd=root)
head = git('rev-parse', 'HEAD').decode().strip()
assert head == 'a1eb536de906bc87999fad8f5b3328f84c9252e5'
before = source_snapshot(root)
manifest_path = root / '.github/ci/coverage_manifest_v2.json.gz'
raw = manifest_path.read_bytes()
manifest = json.loads(gzip.decompress(raw))
old = json.loads(gzip.decompress(git('show', head + ':.github/ci/coverage_manifest_v2.json.gz')))
baseline = json.loads(gzip.decompress(git('show', '09883fb7fe35b241f97ea7fe0a3e292178441935:.github/ci/coverage_manifest_v2.json.gz')))
expected = manifest['product_nodes']
assert len(expected) == 11079 and len(old['product_nodes']) == 11071
future = 'tests/test_v2_model_provider_contracts.py::test_normalized_result_rejects_invalid_naive_or_future_request_timestamps[future_utc]'
removed = [n for n in old['product_nodes'] if n not in set(expected)]
added = [n for n in expected if n not in set(old['product_nodes'])]
assert len(removed) == 1 and removed[0].startswith(future.split('[')[0] + '[2026-10-11T')
assert len(added) == 9 and future in added
assert all(n == future or '::test_manual_refresh_completion_boundary_requires_archive_before_review[' in n
           or '::test_existing_manual_refresh_stays_current_across_completion_then_returns_one_asset[' in n for n in added)
assert [n for n in expected if n in set(old['product_nodes'])] == [n for n in old['product_nodes'] if n not in removed]
changes = {'removed_dynamic_id': removed, 'added_stable_id_and_regressions': added}
assert [n for n in expected if n in set(baseline['product_nodes'])] == baseline['product_nodes']
assert manifest['skips'] == old['skips'] == baseline['skips']
assert manifest.get('external_gates') == old.get('external_gates') == baseline.get('external_gates')
assert source_errors(root, manifest) == []
protected = git('ls-tree', '-r', '--name-only', head, '.github/ci', '.github/workflows').decode().splitlines()
protected = [p for p in protected if p != '.github/ci/coverage_manifest_v2.json.gz']
for p in protected:
    assert (root / p).read_bytes() == git('show', head + ':' + p), p
results = []
for attempt, seed in [('a', '17'), ('b', '31')]:
    profile = root / '.runtime/m4b-ci-corrections-collection' / attempt
    env = os.environ.copy()
    for key in list(env):
        if key.endswith(('_API_KEY', '_TOKEN', '_SECRET')) or key in {'DATABASE_URL', 'TEST_POSTGRES_DATABASE_URL', 'E2E_DATABASE_URL', 'PYTEST_ADDOPTS', 'PYTEST_PLUGINS'}:
            env.pop(key, None)
    env.update(isolated_environment(root, profile))
    env['PYTHONHASHSEED'] = seed
    target = profile / 'collection.json'
    command = [sys.executable, 'scripts/extend_v2_coverage_manifest.py', '--collect-worker', str(target), '--basetemp', str(profile / 'pytest')]
    result = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, timeout=180)
    (profile / 'collection.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads(target.read_text())
    assert data['exit_code'] == 0 and not data['errors']
    assert [row['nodeid'] for row in data['rows']] == expected
    classifications = sha(json.dumps(data['rows'], separators=(',', ':')).encode())
    assert classifications == manifest['v2_extension']['collection_classifications_sha256']
    results.append({'attempt': attempt, 'hash_seed': seed, 'node_count': len(data['rows']), 'ordered_inventory_exact': True,
                    'collection_sha256': sha(target.read_bytes()), 'classifications_sha256': classifications,
                    'stdout': result.stdout, 'stderr': result.stderr, 'tests_executed': False})
assert source_snapshot(root) == before and manifest_path.read_bytes() == raw
out = {'status': 'TWO_INDEPENDENT_COLLECTIONS_EXACT', 'utc': datetime.now(timezone.utc).isoformat(), 'parent': head,
       'source_count': len(before), 'source_map_sha256': sha(json.dumps(before, sort_keys=True, separators=(',', ':')).encode()),
       'source_sha256': before, 'manifest_sha256': sha(raw), 'node_id_changes': changes, 'collections': results,
       'baseline_nodes_preserved': len(baseline['product_nodes']), 'original_skips_gates_and_frozen_hash_unchanged': True,
       'tests_executed': False, 'remaining_acceptance': 'Exact corrected-SHA full hosted execution still required'}
path = root / 'docs/delivery/v2-development/stage-m4b-ci-corrections-collection-proof.json'
path.write_text(json.dumps(out, indent=2) + '\n')
print(json.dumps({k: v for k, v in out.items() if k != 'source_sha256'}, indent=2))
