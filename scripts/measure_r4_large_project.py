"""U13 reproducible synthetic File/API benchmark; never open an existing profile.

Run from the repository with its existing Python dependencies:
    python scripts/measure_r4_large_project.py --output /tmp/r4-performance.json

Six fresh child processes (three sizes x flags off/on), 3 warmups and 30 measured
queries each. Every sample, including misses/errors/truncation, is retained.
No real manuscript, model, credential, database, listening socket or browser is
used. TestClient exercises the mounted app and real File services in-process.
Results are measurements on this environment, not universal performance claims.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
SIZES = (100_000, 500_000, 1_000_000)
CHAPTERS = 12
WARMUPS = 3
SAMPLES = 30
WORKER_TIMEOUT_SECONDS = 300
SEARCH_TARGET_MS = 500
TASK_HISTORY_COUNT = 240
FIXTURE_SESSION = 'r4-fixture-only-not-a-real-session'
# Explicit misses measure the negative-result path instead of hiding it.
QUERIES = ('星桥灯塔', '阿澄', '旧信', '月港', '不存在的线索', '.*')
HAN = re.compile(r'[\u3400-\u4dbf\u4e00-\u9fff\U00020000-\U0002ebef\U00030000-\U000323af]')
STORY = (
    '阿澄在月港修理星桥灯塔。乔岚把旧信放进木盒，沈墨守在门外。',
    '作者知道沈墨藏着铜钥，阿澄尚不知道这个秘密。乔岚误以为旧桥已经封闭。',
    '记录说船在昨日离港，另一页却写它明日才造好；这个时间冲突还没有解决。',
    '约定第三章揭开的旧信一直没有打开，这条伏笔已经过期。',
    '月港既是城镇名称，也是同名船只；阿澄在月港望着月港号。',
    '北岸路线保留灯塔，南岸路线拆除旧桥。两个分支只是规划，没有替换正文。',
    '乔岚说：“灯塔照亮归途。”乔岚再次解释，灯塔照亮归途。',
    '三人核对潮汐，沿石阶慢慢返回；清风吹动纸页，远处传来钟声。\n',
)


def han_count(text: str) -> int:
    return len(HAN.findall(text))


def prefix_han(text: str, count: int) -> str:
    if count == 0:
        return ''
    for index, match in enumerate(HAN.finditer(text), 1):
        if index == count:
            return text[:match.end()]
    raise ValueError('insufficient generated Han characters')


def synthetic_fixture(size: int) -> dict:
    """Exactly size Han characters, with deterministic non-Han punctuation.

    Titles are ASCII, so real repository Markdown headings do not change the
    persisted Han count. This is intentionally repetitive stress data, not a
    claim to represent the literary/lexical diversity of a real novel.
    """
    if not 4_000 <= size <= max(SIZES):
        raise ValueError('fixture size outside predetermined bounds')
    chapters = []
    for index in range(CHAPTERS):
        target = size // CHAPTERS + (index < size % CHAPTERS)
        sentence = ''.join(STORY[index % len(STORY):] + STORY[:index % len(STORY)])
        content = prefix_han(sentence * (target // han_count(sentence) + 1), target)
        chapters.append({'number': index + 1, 'title': f'R4 Synthetic Chapter {index + 1:02d}', 'content': content})
    return {
        'schema': 'r4-original-synthetic-v1', 'han_characters': size, 'chapters': chapters,
        'characters': [{'id': key, 'name': name, 'privacy_level': 'LOCAL_ONLY'}
                       for key, name in [('acheng', '阿澄'), ('qiaolan', '乔岚'), ('shenmo', '沈墨')]],
        'story_routes': [
            {'id': 'north', 'title': '北岸路线', 'route_type': 'ORIGINAL', 'summary': '保留灯塔', 'status': 'DRAFT'},
            {'id': 'south', 'title': '南岸路线', 'route_type': 'ALTERNATE', 'parent_route_id': 'north',
             'divergence_chapter': 6, 'shared_until_chapter': 5, 'summary': '拆除旧桥', 'status': 'DRAFT'},
        ],
        'provenance': 'Original deterministic synthetic prose; no imported books or generated model output.',
        'branch_boundary': 'Two legacy story-route planning records; not collaboration branch manuscripts.',
    }


def percentile(values: list[float], fraction: float) -> float | None:
    """Nearest-rank percentile: sorted[ceil(p*n)-1], no sample exclusion."""
    if not values:
        return None
    return sorted(values)[max(0, math.ceil(fraction * len(values)) - 1)]


def summary(samples: list[dict]) -> dict:
    values = [sample['duration_ms'] for sample in samples]
    return {'sample_count': len(samples), 'p50_ms': percentile(values, .50),
            'p95_ms': percentile(values, .95), 'max_ms': max(values) if values else None,
            'http_errors': sum(not 200 <= sample.get('status', 200) < 300 for sample in samples),
            'misses': sum(sample.get('item_count') == 0 for sample in samples),
            'truncated_samples': sum(bool(sample.get('truncated')) for sample in samples),
            'samples': samples}


def safe_environment(directory: Path, enabled: bool) -> dict[str, str]:
    """Allowlist process necessities; never inherit provider/database secrets."""
    keep = ('PATH', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATHEXT', 'LANG', 'LC_ALL', 'TZ')
    env = {key: os.environ[key] for key in keep if key in os.environ}
    env.update({
        'HOME': str(directory), 'USERPROFILE': str(directory), 'TMPDIR': str(directory),
        'TEMP': str(directory), 'TMP': str(directory), 'XDG_CONFIG_HOME': str(directory / 'config'),
        'XDG_DATA_HOME': str(directory / 'xdg'), 'PROJECT_ROOT': str(ROOT),
        'NOVEL_DATA_PATH': str(directory / 'data'), 'STORAGE_BACKEND': 'file',
        'ENABLE_CLOUD': 'false', 'ENABLE_PROVIDER_FALLBACK': 'false', 'MOCK_PROVIDER': 'false',
        'CREATION_PROFILE': 'LOCAL_ONLY', 'ENABLE_COLLABORATION_RUNTIME': 'false',
        'ENABLE_PACKAGED_RUNTIME': 'false', 'CREDENTIAL_VAULT_BACKEND': 'memory',
        'CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK': 'true',
        'EXPERIMENTAL_FEATURES': 'workspace_tools_v2' if enabled else '',
        'V1_ACCEPTANCE_MODE': 'false', 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUTF8': '1',
        'R4_BENCHMARK_OWNED_DIRECTORY': str(directory),
        'COLLABORATION_DEV_SESSIONS_JSON': json.dumps([{'token': FIXTURE_SESSION,
            'session_id': 'r4-fixture-session', 'client_id': 'r4-fixture-client',
            'actor_id': 'r4-fixture-author', 'workspace_id': 'r4-fixture-workspace'}]),
    })
    return env


def memory() -> dict:
    result = {'rss_bytes': None, 'peak_rss_bytes': None, 'source': 'UNAVAILABLE'}
    try:
        status = Path('/proc/self/status').read_text()
        result.update(rss_bytes=int(re.search(r'^VmRSS:\s+(\d+)', status, re.M)[1]) * 1024,
                      peak_rss_bytes=int(re.search(r'^VmHWM:\s+(\d+)', status, re.M)[1]) * 1024,
                      source='Linux /proc/self/status VmRSS/VmHWM')
    except (OSError, TypeError):
        try:
            import resource
            multiplier = 1 if platform.system() == 'Darwin' else 1024
            result.update(peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * multiplier,
                          source='resource.ru_maxrss; current RSS unavailable')
        except ImportError:
            pass
    return result


def source_receipt() -> dict:
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()
    paths = git('ls-files', '--cached', '--others', '--exclude-standard', '--', 'app',
                'scripts/measure_r4_large_project.py').splitlines()
    digest = hashlib.sha256()
    for relative in sorted(set(paths)):
        path = ROOT / relative
        if path.is_file() and path.suffix == '.py':
            digest.update(relative.encode() + b'\0' + path.read_bytes() + b'\0')
    return {'commit': git('rev-parse', 'HEAD'), 'python_source_sha256': digest.hexdigest(),
            'dirty_paths': git('status', '--porcelain', '--', 'app', 'scripts/measure_r4_large_project.py').splitlines()}


def measured_call(client, method, path, **kwargs):
    started = time.perf_counter_ns()
    response = client.request(method, path, **kwargs)
    elapsed = (time.perf_counter_ns() - started) / 1_000_000
    sample = {'duration_ms': elapsed, 'status': response.status_code,
              'response_bytes': len(response.content)}
    if response.headers.get('content-type', '').startswith('application/json'):
        value = response.json()
    else:
        value = None
    if isinstance(value, dict) and 'items' in value:
        sample.update(item_count=len(value['items']), updated_documents=value.get('updated_documents'),
                      truncated=value.get('truncated'), model_called=value.get('model_called'))
    return sample, value


def require_ok(sample: dict, value):
    if not 200 <= sample['status'] < 300:
        raise RuntimeError(f"fixture API returned HTTP {sample['status']}")
    return value


def run_worker(size: int, enabled: bool, result: dict | None = None) -> dict:
    # This entrypoint is only valid inside the exact fresh directory made by run().
    owned = Path(os.environ['R4_BENCHMARK_OWNED_DIRECTORY']).resolve()
    if Path(os.environ['NOVEL_DATA_PATH']).resolve() != owned / 'data' or not (owned / '.r4-owned').is_file():
        raise RuntimeError('refusing non-owned fixture directory')
    network = {'blocked_connect_attempts': 0}
    def no_network(event, args):
        if event in {'socket.connect', 'socket.getaddrinfo'}:
            network['blocked_connect_attempts'] += 1
            raise RuntimeError('benchmark forbids all network connections')
    sys.addaudithook(no_network)
    sys.path.insert(0, str(ROOT))
    started = time.perf_counter_ns()
    from app.main import app
    from app.experimental.api import workspace_tools_service
    from app.experimental.ux import ReadContext
    from app.api import chapter_service
    from fastapi.testclient import TestClient
    imported_ms = (time.perf_counter_ns() - started) / 1_000_000
    result = result if result is not None else {}
    result.update({'size_han': size, 'flags': 'workspace_tools_v2' if enabled else 'ALL_OFF',
              'status': 'REAL_RUNTIME_VERIFIED', 'cold_app_import_ms': imported_ms,
              'memory_after_import': memory(), 'startup_heavy_modules': [name for name in
              ('torch', 'transformers', 'diffusers', 'tensorflow') if name in sys.modules],
              'network': network, 'model_quality': 'NOT_RUN', 'model_execution_requested': False,
              'api_transport': 'FastAPI TestClient in-process; real mounted app/File storage, no TCP latency'})
    fixture = synthetic_fixture(size)
    result['fixture'] = {key: value for key, value in fixture.items() if key not in {'chapters', 'characters', 'story_routes'}}
    result['fixture'].update(chapter_count=12, character_count=3, story_route_count=2,
        content_sha256=hashlib.sha256(''.join(row['content'] for row in fixture['chapters']).encode()).hexdigest())
    startup = time.perf_counter_ns()
    with TestClient(app) as client:
        result['lifespan_start_ms'] = (time.perf_counter_ns() - startup) / 1_000_000
        novel = require_ok(*measured_call(client, 'POST', '/api/novels', json={'id': 'r4-owned-synthetic', 'title': 'R4 synthetic scale'}))
        nid = novel['id']
        create_samples = []
        for row in fixture['chapters']:
            sample, value = measured_call(client, 'POST', f'/api/novels/{nid}/chapters', json=row)
            require_ok(sample, value)
            create_samples.append(sample)
        for resource, key in [('characters', 'characters'), ('story-routes', 'story_routes')]:
            for row in fixture[key]:
                require_ok(*measured_call(client, 'PUT', f"/api/novels/{nid}/{resource}/{row['id']}",
                                         json={k: v for k, v in row.items() if k != 'id'}))
        require_ok(*measured_call(client, 'PUT', f'/api/novels/{nid}/locations/moon-port', json={'name': '月港', 'privacy_level': 'LOCAL_ONLY'}))
        require_ok(*measured_call(client, 'PUT', f'/api/novels/{nid}/foreshadowing/old-letter',
                                 json={'title': '旧信', 'planted_chapter': 1, 'target_chapter': 3, 'status': 'OPEN', 'privacy_level': 'LOCAL_ONLY'}))
        result['chapter_creation'] = summary(create_samples)
        listing, rows = measured_call(client, 'GET', f'/api/novels/{nid}/chapters')
        require_ok(listing, rows)
        result['chapter_list_api'] = listing
        result['persisted_han_characters'] = sum(han_count(row['content']) for row in rows)
        assert result['persisted_han_characters'] == size
        assert len(rows) == 12
        serialize_started = time.perf_counter_ns()
        payload = json.dumps(rows, ensure_ascii=False, separators=(',', ':')).encode()
        result['chapter_list_json_encoding'] = {'duration_ms': (time.perf_counter_ns() - serialize_started) / 1_000_000,
                                               'bytes': len(payload), 'method': 'stdlib JSON encode of loaded API list; not isolated FastAPI serializer'}
        root = f'/api/novels/{nid}/experimental/workspace'
        if enabled:
            cold, _ = measured_call(client, 'GET', root + '/search', params={'q': QUERIES[0]})
            result['cold_search'] = cold
            warmups, samples = [], []
            for index in range(WARMUPS + SAMPLES):
                sample, _ = measured_call(client, 'GET', root + '/search', params={'q': QUERIES[index % len(QUERIES)]})
                sample['query'] = QUERIES[index % len(QUERIES)]
                sample['expected_outcome'] = 'MISS' if sample['query'] in QUERIES[-2:] else 'HIT'
                sample['outcome_matches_expectation'] = (sample.get('item_count') == 0 if sample['expected_outcome'] == 'MISS' else sample.get('item_count', 0) > 0)
                (warmups if index < WARMUPS else samples).append(sample)
            result['warm_search'] = summary(samples)
            result['warm_search']['warmup_samples'] = warmups
            target = result['warm_search']['p95_ms'] <= SEARCH_TARGET_MS
            valid = all(200 <= s['status'] < 300 and not s.get('truncated') and s.get('model_called') is False and s['outcome_matches_expectation'] for s in samples)
            result['search_target'] = {'target_ms': SEARCH_TARGET_MS, 'status': 'PASS' if valid and target else 'MISS' if valid else 'PARTIAL'}
            # Separately measure the real repository reread and direct service costs.
            direct_samples, rereads = [], []
            ctx = ReadContext(nid, {'mode': 'local', 'novel_id': nid}, 'local-author')
            for index in range(WARMUPS):
                chapter_service.list(nid)
                workspace_tools_service.search(ctx, QUERIES[index % len(QUERIES)])
            for index in range(SAMPLES):
                before = time.perf_counter_ns(); chapter_service.list(nid)
                rereads.append({'duration_ms': (time.perf_counter_ns() - before) / 1_000_000})
                before = time.perf_counter_ns(); found = workspace_tools_service.search(ctx, QUERIES[index % len(QUERIES)])
                direct_samples.append({'duration_ms': (time.perf_counter_ns() - before) / 1_000_000,
                    'item_count': len(found['items']), 'updated_documents': found['updated_documents'], 'truncated': found['truncated']})
            result['chapter_list_service'] = summary(rereads)
            result['direct_search_service'] = summary(direct_samples)
            first = require_ok(*measured_call(client, 'GET', f"/api/chapters/{rows[0]['id']}"))
            updated = require_ok(*measured_call(client, 'PUT', f"/api/chapters/{rows[0]['id']}",
                json={'content': first['content'] + '\n增量检验新桥标记', 'version': first['version'], 'source': 'MANUAL_SAVE'}))
            sample, value = measured_call(client, 'GET', root + '/search', params={'q': '增量检验新桥标记'})
            result['single_chapter_update_search'] = sample
            result['incremental_cache_contract'] = {'status': 'PASS' if sample.get('updated_documents') == 1 and sample.get('item_count') == 1 else 'MISS',
                'boundary': 'Derived search documents reused; each query still reads and hashes authorized source chapters.'}
            require_ok(*measured_call(client, 'POST', f"/api/chapters/{rows[0]['id']}/archive", params={'expected_version': updated['version']}))
            removed, _ = measured_call(client, 'GET', root + '/search', params={'q': '增量检验新桥标记'})
            result['archive_invalidation'] = removed
            if size == SIZES[0]:
                # Real bounded queue/cancel writes, no task execution/model call.
                # The existing authority supplies pagination; no fake TaskReader.
                headers = {'X-Session-Token': FIXTURE_SESSION}
                started = time.perf_counter_ns()
                for index in range(TASK_HISTORY_COUNT):
                    job = require_ok(*measured_call(client, 'POST', '/api/agent-jobs', headers=headers,
                        json={'agent_id': 'planner', 'novel_id': nid, 'chapter': 2,
                              'instruction': f'Original synthetic queue history {index:04d}',
                              'target': 'local', 'execution_mode': 'deterministic'}))
                    require_ok(*measured_call(client, 'POST', f"/api/agent-jobs/{job['id']}/cancel", headers=headers))
                history = {'created_then_cancelled_count': TASK_HISTORY_COUNT,
                           'setup_ms': (time.perf_counter_ns() - started) / 1_000_000,
                           'executed_tasks': 0, 'pages': []}
                seen = set()
                for page in (1, 2, 3):
                    sample, value = measured_call(client, 'GET', '/api/agent-jobs', headers=headers,
                                                 params={'novel_id': nid, 'page': page, 'page_size': 100})
                    require_ok(sample, value)
                    history['pages'].append(sample | {'has_more': value['has_more'], 'total': value['total']})
                    seen.update(row['id'] for row in value['items'])
                    assert all(row['status'] == 'CANCELLED' for row in value['items'])
                assert len(seen) == TASK_HISTORY_COUNT
                projection = []
                for index in range(WARMUPS + SAMPLES):
                    sample, value = measured_call(client, 'GET', root + '/tasks', headers=headers)
                    if index >= WARMUPS:
                        projection.append(sample)
                history['workspace_projection'] = summary(projection)
                history['boundary'] = '240 real queued/cancelled File records; workspace shows capped page and truncation. No worker/model execution or virtual-list claim.'
                result['task_history'] = history
        else:
            flags = require_ok(*measured_call(client, 'GET', '/api/experimental/features'))
            assert not any(flags['features'].values())
            blocked, _ = measured_call(client, 'GET', root + '/search', params={'q': '阿澄'})
            assert blocked['status'] == 404 and not workspace_tools_service._indexes
            baseline = []
            for index in range(WARMUPS + SAMPLES):
                sample, _ = measured_call(client, 'GET', f"/api/chapters/{rows[0]['id']}")
                if index >= WARMUPS:
                    baseline.append(sample)
            result['flags_off_chapter_open'] = summary(baseline)
            result['flags_off_gate'] = {'http_status': blocked['status'], 'index_scope_count': len(workspace_tools_service._indexes)}
        result['memory_after_measurement'] = memory()
        result['owned_fixture_disk_bytes'] = sum(path.stat().st_size for path in owned.rglob('*') if path.is_file())
        result['browser_input_latency'] = 'NOT_RUN: separate browser test required'
        result['windows_ime_screen_reader_native_zoom'] = 'NOT_RUN'
        if network['blocked_connect_attempts']:
            result['status'] = 'PARTIAL'
    return result


def run(sizes=SIZES) -> dict:
    if not sizes or any(size not in SIZES for size in sizes) or len(set(sizes)) != len(sizes):
        raise ValueError('only unique 100000,500000,1000000 sizes supported')
    before = source_receipt()
    report = {'schema': 'r4-u13-performance-v1', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
        'source_before': before, 'environment': {'os': platform.system(), 'architecture': platform.machine(),
        'python': platform.python_version(), 'logical_cpus': os.cpu_count(),
        'dependencies': {name: importlib.metadata.version(name) for name in ('fastapi', 'starlette', 'httpx', 'pydantic')}},
        'method': {'sizes_han': list(sizes), 'chapters_per_project': CHAPTERS,
            'warmups': WARMUPS, 'samples': SAMPLES, 'query_cycle': list(QUERIES),
            'percentile': 'nearest rank ceil(p*n), all measured samples retained',
            'clock': 'perf_counter_ns; real monotonic wall clock', 'worker_timeout_seconds': WORKER_TIMEOUT_SECONDS,
            'rss': 'separate process for each size/mode; peak includes imports and fixture construction',
            'cold_start': 'fresh process/import/cache; OS filesystem cache is not flushed',
            'model_calls': 'No model/generation endpoints; cloud/fallback off, memory vault, no inherited credentials, network audit denied',
            'synthetic_limit': 'Repetitive original data; not representative of every literary corpus',
            'cleanup': 'Only TemporaryDirectory created by this invocation; no existing profile paths accepted'}, 'runs': []}
    for size in sizes:
        for enabled in (False, True):
            with tempfile.TemporaryDirectory(prefix='r4-owned-benchmark-') as directory:
                owned = Path(directory)
                (owned / '.r4-owned').write_text('owned synthetic benchmark fixture')
                command = [sys.executable, str(Path(__file__).resolve()), '--worker', str(size), '--mode', 'on' if enabled else 'off']
                try:
                    child = subprocess.run(command, cwd=ROOT, env=safe_environment(owned, enabled),
                                           text=True, capture_output=True, timeout=WORKER_TIMEOUT_SECONDS)
                    if child.returncode:
                        # Keep failure classification without leaking local paths or raw logs.
                        failure = child.stderr.strip().splitlines()[-1] if child.stderr.strip() else 'no stderr'
                        report['runs'].append({'size_han': size, 'flags': 'ON' if enabled else 'ALL_OFF', 'status': 'ERROR',
                                               'returncode': child.returncode, 'error_type': failure.split(':')[0].split('.')[-1]})
                    else:
                        report['runs'].append(json.loads(child.stdout))
                except subprocess.TimeoutExpired:
                    report['runs'].append({'size_han': size, 'flags': 'ON' if enabled else 'ALL_OFF', 'status': 'TIMEOUT',
                                           'timeout_seconds': WORKER_TIMEOUT_SECONDS})
            report['runs'][-1]['owned_fixture_removed'] = not owned.exists()
    report['source_after'] = source_receipt()
    report['source_stable'] = before == report['source_after']
    report['status'] = 'MEASURED' if report['source_stable'] and all(row['status'] == 'REAL_RUNTIME_VERIFIED' for row in report['runs']) else 'PARTIAL'
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--sizes', nargs='+', type=int, default=list(SIZES), choices=SIZES)
    parser.add_argument('--worker', type=int, choices=SIZES, help=argparse.SUPPRESS)
    parser.add_argument('--mode', choices=('on', 'off'), help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        result = {'size_han': args.worker, 'flags': 'workspace_tools_v2' if args.mode == 'on' else 'ALL_OFF'}
        try:
            run_worker(args.worker, args.mode == 'on', result)
        except Exception as error:
            # Retain completed phases on any later failure; do not serialize
            # exception text, which can contain local paths or environment data.
            result.update(status='ERROR', error_type=type(error).__name__, partial_measurements_retained=True)
    else:
        result = run(tuple(args.sizes))
    encoded = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(encoded + '\n', encoding='utf-8')
    else:
        print(encoded)
