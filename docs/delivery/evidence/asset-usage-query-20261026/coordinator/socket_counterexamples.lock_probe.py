"""Actual loopback HTTP on the original frozen app, with synthetic saved File data."""
from pathlib import Path
import shutil

from conftest import restore_global_settings
from studio_asset_usage_fixture import (
    usage_rig, audio_history, rig, copied_graph_consumers, copied_timeline_consumers, snapshot,
)
from test_studio_process_reopen_v2 import original_application


def test_original_loopback_both_aliases_page_all_540_saved_pins(usage_rig):
    e = usage_rig
    expected = copied_graph_consumers(e, 30, 16) + copied_timeline_consumers(e, count=2)
    assert expected == 540
    root = Path(__file__).resolve().parents[5]
    assert (root / 'app/main.py').is_file()
    run = e.rig.root.parent / (e.rig.root.name + '-socket')
    run.mkdir()
    shutil.copytree(e.rig.root, run / 'data')
    config = run / 'synthetic-providers.json'
    config.write_text('{}', encoding='utf-8')
    with original_application(root, run, config, 'usage-original-app.log') as client:
        before = snapshot(run / 'data')
        for prefix in ('/api', '/api/v1'):
            cursor, found = None, []
            for number in range(100):
                params = {'limit': 100}
                if cursor:
                    params['cursor'] = cursor
                response = client.get(
                    f'{prefix}/novels/{e.rig.nid}/experimental/production/assets/{e.asset["id"]}/studio-asset-usages',
                    params=params,
                )
                assert response.status_code == 200, response.text
                assert response.headers['cache-control'] == 'no-store'
                body = response.json()
                found.extend((row['owner'], row['id'], row.get('node_id', row.get('clip_id')))
                             for row in body['items'])
                cursor = body['next_cursor']
                if not body['has_more']:
                    assert body['total'] == expected and cursor is None
                    break
            else:
                raise AssertionError('loopback pagination did not terminate')
            assert number + 1 == 6 and len(found) == len(set(found)) == expected
            assert snapshot(run / 'data') == before
            print(f'LOOPBACK_USAGE {prefix} saved_consumers=32 references=540 pages=6 duplicate_or_missing=0 source_files_unchanged=true')
