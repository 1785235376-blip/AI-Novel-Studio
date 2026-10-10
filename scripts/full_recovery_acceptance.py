"""Real HTTP/model acceptance for the requested amnesia-city novel.

Run only after implementation and unit checks are complete. No mocked provider,
prewritten manuscript, service replacement or test dependency override is used.
All stage receipts are retained, including failures.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from pathlib import Path
import time
from uuid import uuid4, uuid5, UUID

import httpx

PREMISE = '一个失忆者在废弃城市寻找过去身份，最终发现自己曾经毁灭城市。'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8051')
    parser.add_argument('--runtime', type=Path, default=Path('.runtime/full-recovery/runtime.json'))
    parser.add_argument('--output', type=Path, default=Path('docs/delivery/full-recovery/verification/product-acceptance'))
    args = parser.parse_args()
    runtime = json.loads(args.runtime.read_text(encoding='utf-8'))
    token = json.loads(Path(runtime['session_file']).read_text(encoding='utf-8'))['token']
    args.output.mkdir(parents=True, exist_ok=True)
    client = httpx.Client(base_url=args.base_url, headers={'X-Session-Token': token}, timeout=190, trust_env=False)
    receipts = []
    state = {}
    run_id = str(uuid4())

    def request(method, path, **kwargs):
        response = client.request(method, path, **kwargs)
        if not response.is_success:
            raise RuntimeError(f'{method} {path}: HTTP {response.status_code}: {response.text[:1200]}')
        return response.json()

    def stage(name, fn):
        started = time.perf_counter()
        try:
            value = fn()
            receipt = {'stage': name, 'status': 'PASS', 'seconds': round(time.perf_counter()-started, 3), 'evidence': value}
        except Exception as exc:
            receipt = {'stage': name, 'status': 'FAIL', 'seconds': round(time.perf_counter()-started, 3), 'error': str(exc)}
        receipts.append(receipt)
        (args.output / f'{run_id}-{name}.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({key: receipt[key] for key in receipt if key != 'evidence'}, ensure_ascii=False), flush=True)
        (args.output / f'{run_id}-receipt.json').write_text(json.dumps({'run_id': run_id, 'premise': PREMISE,
            'model': {key: runtime[key] for key in ('provider_id', 'id', 'model_name')}, 'stages': receipts},
            ensure_ascii=False, indent=2), encoding='utf-8')
        return receipt['status'] == 'PASS'

    def poll(path, terminal, *, deadline=180):
        expires = time.monotonic() + deadline
        while time.monotonic() < expires:
            item = request('GET', path)
            if item['status'] in terminal:
                return item
            time.sleep(0.25)
        raise TimeoutError(f'Task did not settle: {path}')

    def create_project():
        project = request('POST', '/api/novels', json={'title': '废城回声 · 完整产品验收', 'genre': '悬疑科幻'})
        state['nid'] = project['id']
        return project
    if not stage('01-project', create_project):
        return 1

    def planning(kind):
        nid = state['nid']
        row = request('POST', f'/api/novels/{nid}/planning-runs', json={
            'kind': kind, 'mode': 'MODEL', 'premise': PREMISE, 'sources': [], 'candidate_count': 1,
            'provider_id': runtime['provider_id'], 'model_id': runtime['id'], 'timeout_seconds': 180})
        row = poll(f'/api/novels/{nid}/planning-runs/{row["id"]}', {'READY', 'FAILED', 'CANCELLED'})
        if row['status'] != 'READY' or row.get('execution_mode') != 'real':
            raise RuntimeError(json.dumps(row, ensure_ascii=False))
        candidate = row['candidates'][0]
        applied = request('POST', f'/api/novels/{nid}/planning-runs/{row["id"]}/candidates/{candidate["id"]}/apply',
                          json={'expected_version': row['version']})
        return {'proposal': row, 'application': applied}
    for index, kind in enumerate(('WORLD', 'CHARACTERS', 'OUTLINE'), 2):
        if not stage(f'{index:02}-{kind.lower()}', lambda kind=kind: planning(kind)):
            return 1

    def generate(operation, instruction):
        chapter = request('GET', f'/api/chapters/{state["cid"]}')
        row = request('POST', f'/api/generate/{operation}', json={'novel_id': state['nid'], 'chapter_id': state['cid'],
            'provider_id': runtime['provider_id'], 'model_id': runtime['id'], 'profile': 'LOCAL_ONLY',
            'instruction': instruction, 'source': chapter['content']}, headers={'Idempotency-Key': str(uuid4())})
        row = poll(f'/api/generation/{row["job_id"]}', {'COMPLETED', 'FAILED', 'CANCELLED'})
        if row['status'] != 'COMPLETED' or row.get('execution_mode') != 'real' or not row.get('output', '').strip():
            raise RuntimeError(json.dumps(row, ensure_ascii=False))
        accepted = request('POST', f'/api/generation/{row["id"]}/accept', json={'expected_version': chapter['version']})
        state['cid'] = accepted['chapter']['id']
        return {'job': row, 'accepted': accepted}

    def first_chapter():
        chapter = request('POST', f'/api/novels/{state["nid"]}/chapters', json={'title': '醒于废墟', 'content': ''})
        state['cid'] = chapter['id']
        result = generate('continue', '根据已批准世界观、角色、大纲写第一章700–900字中文正文。失忆者在废弃城市醒来，埋下毁城身份线索，暂不揭示结局。只返回正文，不要标题或说明。')
        state['original'] = request('GET', f'/api/chapters/{state["cid"]}')
        return result
    if not stage('05-chapter', first_chapter):
        return 1
    def memory_extraction():
        chapter = state['original']
        identity = uuid5(UUID('93e54f54-f779-5d9f-a354-fdfcc48bc146'),
                         f'job:{state["nid"]}:{chapter["id"]}:{chapter["version"]}')
        path = Path(runtime['data_dir']) / 'runtime' / 'jobs' / f'{identity}.json'
        expires = time.monotonic() + 180
        while time.monotonic() < expires:
            if path.exists():
                item = json.loads(path.read_text(encoding='utf-8'))
                if item['status'] not in {'QUEUED', 'GENERATING'}:
                    assert item['status'] == 'COMPLETED', json.dumps(item, ensure_ascii=False)
                    assert item['execution_mode'] == 'real'
                    return {'persisted_job': item, 'proposals': request('GET', f'/api/novels/{state["nid"]}/lore/proposals')}
            time.sleep(0.25)
        raise TimeoutError('Accepted chapter memory extraction did not settle')
    stage('05b-memory-extraction', memory_extraction)
    if not stage('06-ai-revision', lambda: generate('rewrite', '保留全部已建立事实与人物身份，改写现有第一章，加强废城的感官细节与悬疑伏笔。600–900字中文。只返回完整修订正文。')):
        return 1

    def consistency():
        findings = request('POST', f'/api/novels/{state["nid"]}/continuity/scan-chapter', json={'chapter_id': state['cid']})
        context = request('GET', '/api/context-preview', params={'novel_id': state['nid'], 'chapter': state['original']['number'],
            'chapter_id': state['cid'], 'target': 'local'})
        return {'findings': findings, 'context': context}
    stage('07-consistency', consistency)

    def versions():
        current = request('GET', f'/api/chapters/{state["cid"]}')
        saved = request('PUT', f'/api/chapters/{state["cid"]}', json={'content': current['content'] + '\n\n（作者校订存档）', 'version': current['version']})
        conflict = client.put(f'/api/chapters/{state["cid"]}', json={'content': '这次过期写入不能覆盖正文', 'version': current['version']})
        if conflict.status_code != 409:
            raise AssertionError(f'CAS did not reject stale version: {conflict.status_code}')
        state['saved'] = saved
        return {'save': saved, 'history': request('GET', f'/api/chapters/{state["cid"]}/history'),
            'conflict_http_status': conflict.status_code, 'comparison': list(difflib.unified_diff(
                state['original']['content'].splitlines(), saved['content'].splitlines(), fromfile='original', tofile='current'))}
    stage('08-version-save-compare-conflict', versions)

    def restore():
        original = state['original']
        current = request('GET', f'/api/chapters/{state["cid"]}')
        row = request('POST', f'/api/chapters/{state["cid"]}/history/{original["version"]}/restore', params={'expected_version': current['version']})
        latest = request('GET', f'/api/chapters/{state["cid"]}')
        assert latest['content'] == original['content']
        assert latest['version'] > current['version']
        return {'restore': row, 'verified_content_sha256': hashlib.sha256(latest['content'].encode()).hexdigest(), 'new_version': latest['version']}
    stage('09-history-restore', restore)

    def export():
        row = request('POST', '/api/exports', params={'novel_id': state['nid']}, json={'format': 'md'},
                      headers={'Idempotency-Key': str(uuid4())})
        row = poll(f'/api/exports/{row["id"]}', {'succeeded', 'failed', 'cancelled'})
        assert row['status'] == 'succeeded', json.dumps(row, ensure_ascii=False)
        downloaded = client.get(f'/api/exports/{row["id"]}/download')
        downloaded.raise_for_status()
        content = downloaded.content
        assert state['original']['content'].encode() in content
        destination = args.output / f'{run_id}-novel.md'
        destination.write_bytes(content)
        return {'job': row, 'download_bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest(), 'artifact': destination.name}
    stage('10-export', export)

    for agent in ('planner', 'writer', 'editor', 'reviewer', 'verifier'):
        def execute(agent=agent):
            row = request('POST', '/api/agent-jobs', json={'agent_id': agent, 'novel_id': state['nid'],
                'chapter': state['original']['number'], 'chapter_id': state['cid'], 'instruction': '针对本作品现有章节执行你的职责；给出简短中文建议或检查发现，不自动修改作品。严格遵守要求的JSON输出结构。',
                'provider_id': runtime['provider_id'], 'model_id': runtime['id'], 'execution_mode': 'model',
                'target': 'local', 'timeout_seconds': 180})
            result = request('POST', f'/api/agent-jobs/{row["id"]}/execute')
            assert result['status'] == 'COMPLETED' and result.get('model_called') is True, json.dumps(result, ensure_ascii=False)
            assert result['provider_execution_mode'] == 'real', json.dumps(result, ensure_ascii=False)
            return result
        stage(f'11-agent-{agent}', execute)
    client.close()
    return 0 if all(row['status'] == 'PASS' for row in receipts) else 1


if __name__ == '__main__':
    raise SystemExit(main())
