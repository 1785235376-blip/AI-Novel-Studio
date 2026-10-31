"""Original app in a fresh process and actual TCP HTTP, synthetic File only."""
from pathlib import Path
import shutil

from studio_asset_usage_fixture import (
    usage_rig, audio_history, rig, copied_graph_consumers, copied_timeline_consumers, snapshot,
)
from test_studio_process_reopen_v2 import original_application


def test_loopback_resource_modes_and_both_aliases_keep_all_540_pins(usage_rig):
    e = usage_rig
    expected = copied_graph_consumers(e, 30, 16) + copied_timeline_consumers(e, count=2)
    assert expected == 540
    root = Path(__file__).resolve().parents[1]
    run = e.rig.root.parent / (e.rig.root.name + '-resource-socket')
    run.mkdir()
    shutil.copytree(e.rig.root, run / 'data')
    config = run / 'synthetic-providers.json'
    config.write_text('{}', encoding='utf-8')
    with original_application(root, run, config, 'usage-resource-original-app.log') as client:
        def state():
            return snapshot(run / 'data'), sorted(str(path.relative_to(run / 'data'))
                for path in (run / 'data').rglob('*') if path.is_dir())
        def url(prefix):
            return f'{prefix}/novels/{e.rig.nid}/experimental/production/assets/{e.asset["id"]}/studio-asset-usages'
        cold = state()
        response = client.get(url('/api'), params={'limit': 100, 'strict_read_only': 'true'})
        assert response.status_code == 409 and response.json()['code'] == 'STUDIO_USAGE_STRICT_READ_ONLY_UNAVAILABLE'
        assert state() == cold
        for strict in (False, True):
            for prefix in ('/api', '/api/v1'):
                before = state()
                cursor, found = None, []
                for number in range(20):
                    params = {'limit': 100}
                    if strict:
                        params['strict_read_only'] = 'true'
                    if cursor:
                        params['cursor'] = cursor
                    response = client.get(url(prefix), params=params)
                    assert response.status_code == 200, response.text
                    assert response.headers['cache-control'] == 'no-store'
                    body = response.json()
                    assert body['other_dependencies'] == 'UNKNOWN'
                    assert body['budgets']['authority_reads_in_budget']
                    found.extend((row['owner'], row['id'], row.get('node_id', row.get('clip_id')))
                        for row in body['items'])
                    cursor = body['next_cursor']
                    if not body['has_more']:
                        assert body['total'] == 540 and cursor is None
                        break
                assert number + 1 == 6 and len(found) == len(set(found)) == 540
                after = state()
                if strict:
                    assert after == before
                else:
                    def business(files):
                        return {name: digest for name, digest in files.items()
                            if name.replace('\\', '/').split('/')[0] != '.workspace-mutation-locks'}
                    assert business(after[0]) == business(before[0])
                print(f'LOOPBACK_RESOURCE alias={prefix} strict={strict} consumers=32 references=540 pages=6 snapshots_unchanged={after == before}')
