"""Linked edits are private Studio metadata, not part of the native projection."""
from copy import deepcopy

import pytest

from app.services.studio_timeline_exchange import (
    exchange_to_studio_timeline,
    studio_timeline_to_exchange,
)
from app.services.studio_timeline_render import normalize_studio_timeline


def timeline(links=True):
    def source(identity, kind):
        return {'id': identity, 'kind': 'ASSET', 'asset_kind': kind,
                'version': 1, 'digest': 'a' * 64}

    row = {'schema_version': 2, 'duration_ms': 1000, 'width': 320,
           'height': 240, 'fps': 24,
           'tracks': [
               {'id': 'v', 'kind': 'VIDEO', 'order': 0, 'clips': [
                   {'id': 'vc', 'source_snapshot': source('video', 'video'),
                    'start_ms': 0, 'in_ms': 0, 'out_ms': 1000}]},
               {'id': 'a', 'kind': 'AUDIO', 'order': 1, 'clips': [
                   {'id': 'ac', 'source_snapshot': source('audio', 'audio'),
                    'start_ms': 0, 'in_ms': 0, 'out_ms': 1000}]},
           ]}
    if links is not None:
        row['clip_links'] = ([{'video_clip_id': 'vc', 'audio_clip_id': 'ac',
                              'offset_ms': 0}] if links else [])
    return normalize_studio_timeline(row)


def test_linked_export_reports_private_metadata_requirement():
    exported = studio_timeline_to_exchange(timeline(), title='Linked edit')
    receipts = [entry for entry in exported['report'] if entry['path'] == 'clip_links']
    assert receipts == [{'path': 'clip_links',
                         'code': 'CLIP_LINKS_REQUIRE_STUDIO_METADATA', 'severity': 'LOSS'}]


@pytest.mark.parametrize('links', [None, False])
def test_unlinked_export_does_not_claim_link_loss(links):
    exported = studio_timeline_to_exchange(timeline(links), title='Independent edits')
    assert not any(entry['path'] == 'clip_links' for entry in exported['report'])


def test_unchanged_extension_preserves_exact_linked_timeline():
    original = timeline()
    exported = studio_timeline_to_exchange(original, title='Linked edit')
    imported = exchange_to_studio_timeline(
        exported['document'], media_bindings=exported['media_bindings'],
        canvas={'width': 320, 'height': 240, 'fps': 24})
    assert imported['timeline'] == original
    assert imported['timeline']['clip_links'] == original['clip_links']
    assert imported['report'] == []


def test_native_projection_alone_does_not_preserve_linked_edit_relationship():
    exported = studio_timeline_to_exchange(timeline(), title='Linked edit')
    native_only = deepcopy(exported['document'])
    native_only.pop('studio')
    imported = exchange_to_studio_timeline(
        native_only, media_bindings=exported['media_bindings'],
        canvas={'width': 320, 'height': 240, 'fps': 24})
    assert not imported['timeline'].get('clip_links')
    assert len(imported['timeline']['tracks']) == 2
    assert all(len(track['clips']) == 1 for track in imported['timeline']['tracks'])
