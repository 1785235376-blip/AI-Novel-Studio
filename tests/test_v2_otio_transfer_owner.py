"""Retimed OTIO preview/import through the existing File Timeline owner."""
import copy
import json
from fractions import Fraction

import pytest

from app.creative.production_execution import TIMELINES
from app.experimental.common import StaleSourceError
from app.experimental.timeline_exchange import time_value, write_otio
from app.services.studio_timeline_exchange import studio_timeline_to_exchange
from test_v2_independent_workspace import rig, import_asset, reopened
from test_v2_audio_editing_pipeline import production, cpu_video, timeline


def test_original_owner_previews_then_imports_retimed_otio_as_draft(rig, tmp_path):
    pytest.importorskip('opentimelineio')
    e = rig
    e.service.activate(e.nid, e.scope, e.actor)
    asset = import_asset(e, data=cpu_video(tmp_path / 'synthetic-blue.mp4'),
                         filename='synthetic-blue.mp4', kind='video')
    owner = production(e)
    value = timeline(asset)
    value['tracks'][0]['clips'][0].update(in_ms=120, out_ms=720, speed_num=2, speed_den=3)
    row = owner.timeline_save(e.nid, e.scope, e.actor, None,
        {'expected_version': 0, 'title': 'Synthetic retimed timeline', 'timeline': value}, lambda: None)
    projected = studio_timeline_to_exchange(row['timeline'], title=row['title'])
    doc = copy.deepcopy(projected['document'])
    doc.pop('studio')
    doc['global_start_time'] = time_value(Fraction(1, 3), Fraction(30000, 1001))
    doc['tracks'][0]['items'][0]['available_range'] = {
        'start': time_value(0, Fraction(30000, 1001)),
        'duration': time_value(Fraction(30000, 1001), Fraction(30000, 1001)),
    }
    raw = json.loads(write_otio(doc))
    raw['metadata']['external_review'] = {'status': 'APPROVED', 'execute': True}
    content = json.dumps(raw)
    body = {'expected_version': row['version'], 'reviewed_timeline_digest': row['timeline_digest'],
            'direction': 'IMPORT', 'format': 'OTIO', 'content': content,
            'media_bindings': projected['media_bindings']}
    before = e.raw_store.read(e.nid, e.scope)
    preview = owner.timeline_transfer_preview(e.nid, e.scope, e.actor, row['id'], body, lambda: None)
    assert e.raw_store.read(e.nid, e.scope) == before
    assert (preview['model_called'], preview['automatic_replay'], preview['external_media_access']) == (False, False, False)
    assert preview['target_applications'] == {'Resolve': 'NOT_RUN', 'Premiere': 'NOT_RUN'}
    assert 'GLOBAL_TIMECODE_NOT_STUDIO_TIMELINE_PLACEMENT' in {item['code'] for item in preview['loss_report']}
    apply = {**body, 'reviewed_preview_digest': preview['preview_digest'],
             'request_id': 'otio-exact-reviewed-import', 'acknowledge_losses': False}
    with pytest.raises(ValueError, match='REVIEW_LOSS_REPORT_REQUIRED'):
        owner.timeline_transfer_import(e.nid, e.scope, e.actor, row['id'], apply, lambda: None)
    with pytest.raises(StaleSourceError, match='PREVIEW_CHANGED'):
        owner.timeline_transfer_import(e.nid, e.scope, e.actor, row['id'],
            {**apply, 'reviewed_preview_digest': '0' * 64, 'acknowledge_losses': True}, lambda: None)
    assert e.raw_store.read(e.nid, e.scope) == before
    imported = owner.timeline_transfer_import(e.nid, e.scope, e.actor, row['id'],
        {**apply, 'acknowledge_losses': True}, lambda: None)
    clip = imported['timeline']['tracks'][0]['clips'][0]
    assert (clip['in_ms'], clip['out_ms'], clip['speed_num'], clip['speed_den']) == (120, 720, 2, 3)
    assert imported['version'] == row['version'] + 1
    stored = e.raw_store.read(e.nid, e.scope)
    assert stored['collections'][TIMELINES][row['id']]['status'] == 'DRAFT'
    assert {key: value for key, value in stored['collections'].items() if key != TIMELINES} == {
        key: value for key, value in before['collections'].items() if key != TIMELINES}
    assert production(e, reopened(e)).timeline_get(e.nid, e.scope, e.actor, row['id'], lambda: None) == imported
