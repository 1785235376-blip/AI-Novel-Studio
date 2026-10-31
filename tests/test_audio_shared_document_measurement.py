"""Pure accounting against synthetic real File owner documents."""
import base64
import copy
import hashlib
import json
import os
from pathlib import Path

import pytest

from app.experimental.audio_shared_document_measurement import measure_file_scope_document
from app.experimental.store import canonical
from app.experimental.common import change_row, new_row, snapshot
from test_studio_asset_query import rig
from test_audio_shared_document_quota_observation import audio_candidate, initialized


def owner_candidate(rig):
    payload = audio_candidate()
    payload.pop('id')
    payload.pop('title')  # Not a field written by AudiobookV2Service.mix.
    payload.update(plan_version=1, sources={}, mixer_id='synthetic')
    return new_row(rig.nid, rig.scope, 'synthetic-actor', payload)


def test_real_mixed_owner_document_exact_bytes_and_full_atomic_peak(rig, monkeypatch):
    import app.storage as storage
    store, unrelated = initialized(rig)
    candidate = owner_candidate(rig)
    candidate['history'] = [snapshot(candidate)]
    document = store.read(rig.nid, rig.scope)
    document['collections']['audio_v2_mix_proposals'][candidate['id']] = candidate
    # Dedicated audio configuration is not a candidate and must not be billed.
    document['collections']['audio_v2_profiles'] = {'profile': {'title': '配置☃'}}
    target = canonical(document).encode('utf-8')
    field = b'"audio_v2_mix_proposals":' + canonical(document['collections']['audio_v2_mix_proposals']).encode('utf-8')
    assert field in target
    measure = measure_file_scope_document(target, rig.nid, rig.scope)
    assert measure['mix_collection_bytes'] == len(field) + 1
    assert measure['mix_collection_bytes'] + measure['other_document_bytes'] == len(target)
    assert measure['full_document_bytes'] == measure['atomic_temporary_bytes'] == len(target)
    # Two physically serialized occurrences are charged, with no digest dedup.
    encoded_audio = candidate['content_base64'].encode('ascii')
    assert target.count(encoded_audio) == 2
    assert measure['mix_collection_bytes'] > 2 * len(encoded_audio)
    samples, replace = [], os.replace
    def observe(source, dest):
        if Path(dest) == store.path(rig.nid, rig.scope): samples.append(Path(source).read_bytes())
        return replace(source, dest)
    monkeypatch.setattr(storage.os, 'replace', observe)
    with store.transaction(rig.nid, rig.scope) as actual:
        actual['collections'] = copy.deepcopy(document['collections'])
    assert samples == [target]
    assert store.path(rig.nid, rig.scope).read_bytes() == target
    assert store.read(rig.nid, rig.scope)['collections']['unrelated_synthetic'] == unrelated


def test_absent_and_empty_collection_have_exact_different_storage(rig):
    store, _ = initialized(rig)
    doc = store.read(rig.nid, rig.scope)
    empty = canonical(doc).encode()
    e = measure_file_scope_document(empty, rig.nid, rig.scope)
    assert e['mix_collection_bytes'] == len(b'"audio_v2_mix_proposals":{},')
    del doc['collections']['audio_v2_mix_proposals']
    missing = measure_file_scope_document(canonical(doc).encode(), rig.nid, rig.scope)
    assert missing['mix_collection_bytes'] == 0


def test_unrelated_changes_do_not_charge_unrelated_content(rig):
    store, _ = initialized(rig)
    doc = store.read(rig.nid, rig.scope)
    candidate = owner_candidate(rig)
    doc['collections']['audio_v2_mix_proposals'][candidate['id']] = candidate
    before = measure_file_scope_document(canonical(doc).encode(), rig.nid, rig.scope)
    doc['collections']['unrelated_synthetic']['large'] = {'body':'雪' * 1000}
    after = measure_file_scope_document(canonical(doc).encode(), rig.nid, rig.scope)
    assert before['mix_collection_bytes'] == after['mix_collection_bytes']
    assert after['full_document_bytes'] > before['full_document_bytes']


@pytest.mark.parametrize('bad', ['missing_content', 'bad_base64', 'wrong_digest', 'bad_history'])
def test_corrupt_candidate_or_history_is_unknown(rig, bad):
    store, _ = initialized(rig)
    doc = store.read(rig.nid, rig.scope)
    candidate = owner_candidate(rig)
    if bad == 'missing_content': candidate.pop('content_base64')
    elif bad == 'bad_base64': candidate['content_base64'] = 'not base64!'
    elif bad == 'wrong_digest': candidate['content_sha256'] = '0' * 64
    else: candidate['history'] = [{'content_base64': base64.b64encode(b'x').decode(), 'content_sha256':'0'*64}]
    doc['collections']['audio_v2_mix_proposals'][candidate['id']] = candidate
    with pytest.raises(ValueError, match='MEASUREMENT_UNAVAILABLE'):
        measure_file_scope_document(canonical(doc).encode(), rig.nid, rig.scope)


@pytest.mark.parametrize('bad', ['row', 'snapshot', 'media', 'source', 'timeline', 'frame', 'identity'])
def test_unknown_fields_and_mismatched_identity_fail_closed(rig, bad):
    store, _ = initialized(rig)
    doc = store.read(rig.nid, rig.scope)
    row = owner_candidate(rig)
    row['history'] = [snapshot(row)]
    if bad == 'row': row['unrelated_payload'] = 'secret'
    elif bad == 'snapshot': row['history'][0]['unrelated_payload'] = 'secret'
    elif bad == 'media': row['media']['unrelated_payload'] = 'secret'
    elif bad == 'source': row['sources'] = {'chapter': {'version': 1, 'digest': 'x', 'unknown': 'secret'}}
    elif bad == 'timeline': row['timeline'] = [{'id': 'a', 'unknown': 'secret'}]
    elif bad == 'frame': row['timeline'] = [{'id': 'a', 'frame_timing': {'frames': 1, 'sample_rate': 1, 'unknown': 'secret'}}]
    else: row['id'] = 'wrong-id'
    doc['collections']['audio_v2_mix_proposals']['different-id' if bad == 'identity' else row['id']] = row
    with pytest.raises(ValueError, match='MEASUREMENT_UNAVAILABLE'):
        measure_file_scope_document(canonical(doc).encode(), rig.nid, rig.scope)


@pytest.mark.parametrize('final', ['REJECTED', 'APPROVED'])
def test_original_change_row_history_preserves_candidate_body(rig, final):
    store, _ = initialized(rig)
    doc = store.read(rig.nid, rig.scope)
    row = owner_candidate(rig)
    if final == 'APPROVED':
        change_row(row, 'actor', 1, lambda r: r.update(status='APPROVING', promotion_token='t', promotion_started_at='now', promotion_actor='actor'))
        change_row(row, 'actor', 2, lambda r: r.update(promotion_asset_id='a', promotion_asset_digest='d', promotion_state='ASSET_CREATED'))
        change_row(row, 'actor', 3, lambda r: r.update(status='APPROVED', asset_id='a', approved_at='now', approved_by='actor'))
    else:
        change_row(row, 'actor', 1, lambda r: r.update(status='REJECTED'))
    doc['collections']['audio_v2_mix_proposals'][row['id']] = row
    raw = canonical(doc).encode('utf-8')
    assert raw.count(row['content_base64'].encode()) == len(row['history']) + 1
    assert measure_file_scope_document(raw, rig.nid, rig.scope)['mix_collection_bytes'] > len(row['content_base64']) * (len(row['history']) + 1)


def test_duplicate_key_noncanonical_and_wrong_scope_rejected(rig):
    store, _ = initialized(rig)
    raw = store.path(rig.nid, rig.scope).read_bytes()
    document = json.loads(raw)
    with pytest.raises(ValueError): measure_file_scope_document(json.dumps(document).encode(), rig.nid, rig.scope)
    duplicate = raw.replace(b'"schema_version":1', b'"schema_version":1,"schema_version":1', 1)
    assert duplicate != raw
    with pytest.raises(ValueError): measure_file_scope_document(duplicate, rig.nid, rig.scope)
    with pytest.raises(ValueError): measure_file_scope_document(raw, rig.nid, {'mode':'local','novel_id':'other'})


def test_boolean_schema_version_is_unknown(rig):
    store, _ = initialized(rig)
    doc = store.read(rig.nid, rig.scope)
    doc['schema_version'] = True
    with pytest.raises(ValueError, match='MEASUREMENT_UNAVAILABLE'):
        measure_file_scope_document(canonical(doc).encode(), rig.nid, rig.scope)


@pytest.mark.parametrize('field,value', [('version', True), ('plan_version', True), ('status', 'SYNTHETIC_UNKNOWN')])
def test_invalid_candidate_state_is_unknown(rig, field, value):
    store, _ = initialized(rig)
    doc = store.read(rig.nid, rig.scope)
    row = owner_candidate(rig)
    row[field] = value
    doc['collections']['audio_v2_mix_proposals'][row['id']] = row
    with pytest.raises(ValueError, match='MEASUREMENT_UNAVAILABLE'):
        measure_file_scope_document(canonical(doc).encode(), rig.nid, rig.scope)
