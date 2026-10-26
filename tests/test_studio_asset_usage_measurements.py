"""Reproducible measurements on saved synthetic File owners and mounted HTTP."""
import json
import os
from pathlib import Path
import pytest
from studio_asset_usage_fixture import usage_rig, audio_history, rig, graph_create, create_timeline, snapshot
from studio_asset_usage_meter import measured

pytestmark = pytest.mark.file_backend_only


def test_measure_original_usage_graph(usage_rig, monkeypatch):
    e = usage_rig
    for i in range(14):
        graph_create(e, 16, f'graph-{i}')
    before = snapshot(e.rig.root)
    results = []
    for phase in ('first-read-warm-os-cache', 'repeat-read-warm-process'):
        response, metrics = measured(e, monkeypatch, lambda: e.client.get(
            e.usage_base + '/studio-graph-usages', headers=e.headers))
        assert response.status_code == 200, response.text
        assert len(response.json()['items']) == 200 and response.json()['truncated']
        results.append({'phase': phase, 'entry': 'original-main.app-HTTP', 'references': 224,
            'consumers': 14, 'response_bytes': len(response.content), **metrics})
    assert snapshot(e.rig.root) == before
    destination = Path(os.environ['STUDIO_TEST_RUN_ROOT']) / 'usage-metrics.json'
    destination.write_text(json.dumps(results, indent=2), encoding='utf-8')
    print('USAGE_MEASUREMENTS ' + json.dumps(results))


@pytest.mark.parametrize('entry', ['HTTP', 'File-service'])
@pytest.mark.parametrize('scenario', ['graph', 'mixed-graph', 'timeline'])
def test_new_paged_usage_measurements(usage_rig, monkeypatch, scenario, entry):
    from studio_asset_usage_fixture import copied_graph_consumers, copied_timeline_consumers
    e = usage_rig
    expected = copied_timeline_consumers(e) if scenario == 'timeline' else copied_graph_consumers(e, 30, 16, mixed=scenario == 'mixed-graph')
    suffix = 'studio-timeline-usages' if scenario == 'timeline' else 'studio-graph-usages'
    before = snapshot(e.rig.root)
    runs = []
    for phase in ('first-read-warm-os-cache', 'repeat-read-warm-process'):
        cursor, found, pages = None, [], []
        for page_number in range(100):
            params = {'limit': 100}
            if cursor:
                params['cursor'] = cursor
            def query():
                if entry == 'HTTP':
                    return e.client.get(e.usage_base + '/' + suffix, headers=e.headers, params=params)
                from app.creative.asset_usages import graph_asset_usages, timeline_asset_usages
                from types import SimpleNamespace
                function = timeline_asset_usages if scenario == 'timeline' else graph_asset_usages
                service = e.production if scenario == 'timeline' else e.graph
                with service.store.existing_owner_only():
                    body = function(service, e.rig.nid, e.rig.scope, e.actor, e.asset['id'], lambda: None, **params)
                content = json.dumps(body, separators=(',', ':')).encode()
                return SimpleNamespace(status_code=200, text=content.decode(), content=content, json=lambda: body)
            response, metrics = measured(e, monkeypatch, query)
            assert response.status_code == 200, response.text
            body = response.json()
            assert body['other_dependencies'] == 'UNKNOWN'
            assert len(body['items']) <= 100
            found.extend((x['id'], x.get('node_id', x.get('clip_id'))) for x in body['items'])
            pages.append({'page': page_number, 'returned': len(body['items']),
                'response_bytes': len(response.content), 'scanned_consumers': body['scanned_consumers'],
                'scanned_references': body['scanned_references'], **metrics})
            cursor = body['next_cursor']
            if not body['has_more']:
                assert cursor is None
                assert body['total'] == expected
                break
        assert len(found) == len(set(found)) == expected
        runs.append({'phase': phase, 'entry': entry,
            'scenario': scenario, 'fixture': 'Copied saved valid original owner records; Graph count30 exceeds normal creation cap25',
            'pages': pages})
    assert snapshot(e.rig.root) == before
    destination = Path(os.environ['STUDIO_TEST_RUN_ROOT']) / f'paged-usage-metrics-{scenario}-{entry}.json'
    destination.write_text(json.dumps(runs, indent=2), encoding='utf-8')
    print('PAGED_USAGE_MEASUREMENTS ' + json.dumps(runs))


