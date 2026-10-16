"""Additive reconciliation scenarios and their minimal independent fixture support."""

from __future__ import annotations

import base64

import copy

import io

import json

import zipfile

import pytest

from app.experimental.comic_layouts import ComicLayoutsService

from support_reconciliation_test_r3_media_support import rig

from support_reconciliation_test_r4_director import screenplay

def synthetic_png(width=240, height=160):
    from PIL import Image, ImageDraw
    image = Image.new('RGB', (width, height), 'white'); draw = ImageDraw.Draw(image)
    draw.rectangle((8, 8, width - 8, height - 8), outline='black', width=3)
    draw.line((10, height - 10, width // 2, 16, width - 10, height - 10), fill='blue', width=3)
    draw.text((12, height // 2), 'SYNTHETIC TEST ASSET', fill='black')
    stream = io.BytesIO(); image.save(stream, format='PNG'); return stream.getvalue()

@pytest.fixture
def comic(rig):
    return ComicLayoutsService(rig.store, rig.novels, rig.chapters, rig.screenplays, rig.assets)

@pytest.fixture
def image_asset(rig, comic):
    asset = rig.assets.create(rig.nid, 'SYNTHETIC-TEST-ASSET.png', base64.b64encode(synthetic_png()).decode(), 'image/png')
    approved = comic.approve_image(rig.nid, rig.scope, rig.actor, asset['id'], asset['version'])
    return rig.assets.get(approved['id'])

def layout(rig, asset=None):
    source = screenplay(rig)
    return {'title': 'Synthetic test layout', 'screenplay_id': source['id'], 'expected_screenplay_version': source['edit_version'],
            'width': 800, 'height': 1120, 'safe_area': 24, 'segment_height': 560,
            'panels': [{'id': 'panel', 'shot_id': source['shots'][0]['id'], 'order': 1, 'x': 24, 'y': 24, 'width': 752, 'height': 1000,
                        'asset_id': asset['id'] if asset else None, 'expected_asset_version': asset['version'] if asset else None}]}

def save(comic, rig, body): return comic.save(rig.nid, rig.scope, rig.actor, body)

def preflight(comic, rig, row): return comic.preflight(rig.nid, rig.scope, rig.actor, row['id'], row['version'])

def approve(comic, rig, row, report=None):
    report = report or preflight(comic, rig, row)
    return comic.approve(rig.nid, rig.scope, rig.actor, row['id'], row['version'], report['review_digest'], True)

def test_manual_vertical_arrangement_keeps_original_bindings_and_history(rig, comic, image_asset):
    body = layout(rig, image_asset)
    body['panels'][0].update(x=48, y=80, width=600, height=320)
    second = copy.deepcopy(body['panels'][0]); second.update(id='second', order=2, y=440)
    body['panels'].append(second)
    row = save(comic, rig, body); approved = approve(comic, rig, row)
    arranged = copy.deepcopy(row['document'])
    for panel, y in zip(arranged['panels'], [24, 360]): panel.update(x=24, y=y)
    edited = comic.save(rig.nid, rig.scope, rig.actor, arranged, rid=row['id'], expected_version=approved['version'])
    assert edited['status'] == 'DRAFT' and edited['history_versions'] == [1, 2]
    reopened = ComicLayoutsService(rig.store, rig.novels, rig.chapters, rig.screenplays, rig.assets)
    assert reopened.records(rig.nid, rig.scope, rig.actor)['items'][0]['document'] == arranged
    assert preflight(reopened, rig, edited)['can_render']
    accepted = approve(reopened, rig, edited)
    with zipfile.ZipFile(io.BytesIO(reopened.export(rig.nid, rig.scope, rig.actor, row['id'], accepted['version']))) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        assert manifest['asset_bindings'][image_asset['id']]['sha256'] == image_asset['sha256']
        assert manifest['asset_bindings'][image_asset['id']]['version'] == image_asset['version']
    restored = reopened.restore(rig.nid, rig.scope, rig.actor, row['id'], accepted['version'], 1)
    assert restored['document'] == row['document']
    assert rig.assets.get(image_asset['id'])['version'] == image_asset['version']
