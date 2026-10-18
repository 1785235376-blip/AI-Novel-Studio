"""Comic panel generation composes original Image review and Comic CAS owners.

Synthetic local-provider HTTP returns real CRC-correct PNG bytes. Nothing here
starts a model, uses live inference, or claims artistic/Windows acceptance.
"""
from copy import deepcopy
import base64
import hashlib

import httpx
import pytest

from app.creative.production_execution import digest
from app.creative.production_execution_models import MediaJobAction, MediaReview
from app.experimental.comic_layouts import ComicLayoutsService
from app.services.screenplay_service import ScreenplayService
from app.services.v1_capability_service import CapabilityVersionConflict
from test_v2_discovered_image_production import discovery, owner
from test_v2_independent_workspace import rig, png_bytes

REJECTED = (ValueError, FileNotFoundError, CapabilityVersionConflict)


@pytest.fixture
def comic_image(rig, monkeypatch):
    e = rig
    e.discovery, registry, e.adapter = discovery(e.root, 'AUTOMATIC1111')
    e.production = owner(registry, monkeypatch, e)
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2,asset_lineage_v2,ai_execution_v2,model_broker_v2,author_context_inspector_v2,comic_layouts_v2,ai_director_v2")
    e.comic = ComicLayoutsService(e.raw_store, e.novels, e.chapters,
        ScreenplayService(e.bundle.novels, e.bundle.chapters), e.assets,
        independent_store=e.store)
    e.production.configure_comic(e.comic)
    e.page = e.comic.save(e.nid, e.scope, e.actor, {
        'title': 'SYNTHETIC independent comic', 'source_mode': 'INDEPENDENT',
        'panels': [{'id': 'panel-one', 'artwork_mode': 'IMAGE', 'order': 1,
            'x': 24, 'y': 24, 'width': 752, 'height': 320,
            'image_brief': '  SYNTHETIC moonlit station\nKeep the empty foreground.  '}]})
    e.pixels, e.posts = png_bytes(), []
    def post(url, **kwargs):
        e.posts.append((url, deepcopy(kwargs)))
        return httpx.Response(200, json={'images': [base64.b64encode(e.pixels).decode()]},
            request=httpx.Request('POST', url))
    monkeypatch.setattr(e.adapter.delegate.transport, 'post', post)
    return e


def request(e, **changes):
    return e.production.comic_images.image_request(e.nid, e.scope, e.actor,
        e.page['id'], 'panel-one', {'expected_version': e.page['version'],
        'request_id': 'comic-image-one', 'provider_id': e.adapter.candidate['provider_id'],
        'model_id': e.adapter.candidate['id'], 'parameters': {'width': 64, 'height': 64, 'seed': 3},
        **changes}, lambda: None)


def preview(e, command):
    return e.production.preview(e.nid, e.scope, e.actor, command, lambda: None)[0]


def queue(e, command=None, captured=None):
    command = command if command is not None else request(e)['command']
    captured = captured if captured is not None else preview(e, command)
    return e.production.create(e.nid, e.scope, e.actor,
        {'command': command, 'reviewed_preview_digest': captured['preview_digest']}, lambda: None)


def action(row):
    return MediaJobAction(expected_version=row['version'], expected_request_digest=row['request_digest'])


def execute(e, row):
    return e.production.execute(e.nid, e.scope, e.actor, 'image', row['id'], action(row), lambda: None)


def review(e, row):
    return e.production.review(e.nid, e.scope, e.actor, 'image', row['id'],
        MediaReview(**action(row).model_dump(), reviewed_output_digest=row['output_candidate']['digest']), lambda: None)


def adoption(e, row):
    return {'expected_version': e.page['version'], 'job_id': row['id'],
        'expected_job_version': row['version'], 'expected_request_digest': row['request_digest'],
        'expected_asset_version': row.get('approved_asset_version') or row['output_candidate']['version'],
        'expected_output_digest': row['output_candidate']['digest']}


def adopt(e, row, *, guard=lambda: None, **changes):
    return e.production.comic_images.adopt(e.nid, e.scope, e.actor, e.page['id'], 'panel-one',
        {**adoption(e, row), **changes}, guard)


def raw_page(e):
    return e.comic._row(e.nid, e.scope, e.actor, e.page['id'])


def edit_page(e, change):
    body = deepcopy(e.page['document'])
    change(body)
    return e.comic.save(e.nid, e.scope, e.actor, body, rid=e.page['id'], expected_version=e.page['version'])


def test_request_and_preview_are_exact_and_zero_side_effect(comic_image):
    e = comic_image
    before = deepcopy(e.raw_store.read(e.nid, e.scope))
    rows_before = list(e.root.rglob('image-jobs/*.json'))
    result = request(e)
    assert result['contract'] == 'studio-comic-image-request/1'
    assert result['automatic_dispatch'] is False and result['model_called'] is False
    source = result['source_snapshot']; row = raw_page(e)
    assert source['kind'] == 'COMIC_PANEL' and source['id'] == e.page['id'] and source['version'] == 1
    assert source['digest'] == digest({k: v for k, v in row.items() if k != 'history'})
    pin = source['comic_panel']
    assert pin['panel_id'] == 'panel-one' and pin['actor'] == e.actor
    assert pin['scope_key'] == e.store.key(e.nid, e.scope) and pin['incarnation'] == e.store.incarnation(e.nid)
    assert pin['panel_digest'] == digest(e.page['document']['panels'][0])
    assert pin['brief_digest'] == digest(e.page['document']['panels'][0]['image_brief'])
    command = result['command']
    assert command['operation_id'] == 'm5.image.t2i' and command['allow_cloud'] is False
    assert command['source_snapshots'] == [source]
    assert command['prompt'] == e.page['document']['panels'][0]['image_brief']
    assert not command.get('image_references') and not command.get('image_source')
    assert preview(e, command)['automatic_dispatch'] is False
    assert e.raw_store.read(e.nid, e.scope) == before
    assert list(e.root.rglob('image-jobs/*.json')) == rows_before
    assert e.service.list_assets(e.nid, e.scope)['items'] == []
    assert e.posts == [] and e.discovery.center.lifecycle.start.call_count == 0


def test_real_pixels_original_review_then_separate_same_page_draft_adoption(comic_image):
    e = comic_image; before = raw_page(e)
    command = request(e)['command']; queued = queue(e, command)
    assert queue(e, command) == queued and e.posts == []
    candidate = execute(e, queued)
    assert candidate['status'] == 'AWAITING_REVIEW' and len(e.posts) == 1
    assert e.posts[0][1]['json']['prompt'] == e.page['document']['panels'][0]['image_brief']
    output = candidate['output_candidate']
    assert output['digest'] == hashlib.sha256(e.pixels).hexdigest()
    assert e.service.list_assets(e.nid, e.scope)['items'] == []
    with pytest.raises(FileNotFoundError): e.service.asset(e.nid, e.scope, output['id'])
    meta, actual = e.production.candidate(e.nid, e.scope, e.actor, 'image', queued['id'], lambda: None)
    assert actual == e.pixels and meta['sha256'] == output['digest']
    with pytest.raises(REJECTED): adopt(e, candidate)
    assert raw_page(e) == before
    approved = review(e, candidate)
    assert approved['status'] == 'APPROVED'
    assert raw_page(e) == before  # Original Image approval never attaches a Comic panel.
    formal = e.service.asset(e.nid, e.scope, output['id'])
    with pytest.raises(ValueError, match='ORIGINAL_GENERATION_REVIEW'):
        e.comic.approve_image(e.nid, e.scope, e.actor, output['id'], formal['version'])
    adopted = adopt(e, approved)
    assert adopted['id'] == e.page['id'] and adopted['version'] == 2 and adopted['status'] == 'DRAFT'
    panel = adopted['document']['panels'][0]
    assert panel['asset_id'] == output['id'] and panel['expected_asset_version'] == formal['version']
    assert panel['image_brief'] == e.page['document']['panels'][0]['image_brief']
    assert adopted['history_versions'] == [1] and len(e.posts) == 1
    assert len(e.service.list_assets(e.nid, e.scope)['items']) == 1
    with pytest.raises(REJECTED): adopt(e, approved)
    assert raw_page(e)['version'] == 2
    assert e.comic.records(e.nid, e.scope, e.actor)['items'] == [adopted]
    report = e.comic.preflight(e.nid, e.scope, e.actor, adopted['id'], adopted['version'])
    assert report['can_render']
    reopened = ComicLayoutsService(e.raw_store, e.novels, e.chapters,
        ScreenplayService(e.bundle.novels, e.bundle.chapters), e.assets,
        independent_store=e.store)
    assert reopened.records(e.nid, e.scope, e.actor)['items'] == [adopted]
    rendered = reopened.preview(e.nid, e.scope, e.actor, adopted['id'], adopted['version'], 0)
    assert rendered == e.comic.preview(e.nid, e.scope, e.actor, adopted['id'], adopted['version'], 0)
    from io import BytesIO
    from PIL import Image
    with Image.open(BytesIO(rendered)) as image:
        assert image.format == 'PNG' and image.width == adopted['document']['width']
        assert image.getpixel((400, 180))[:3] == (17, 34, 51)
    e.page = adopted
    again = request(e, request_id='comic-image-next')
    assert again['source_snapshot']['version'] == 2 and len(e.posts) == 1
    assert preview(e, again['command'])['automatic_dispatch'] is False


@pytest.mark.parametrize('change', ['page', 'brief', 'panel', 'references'])
@pytest.mark.parametrize('stage', ['preview', 'queue', 'execute', 'review', 'adopt'])
def test_saved_source_drift_fails_closed_at_every_transition(comic_image, change, stage):
    e = comic_image; command = request(e)['command']; captured = preview(e, command)
    row = queue(e, command, captured) if stage in {'execute', 'review', 'adopt'} else None
    if stage in {'review', 'adopt'}: row = execute(e, row)
    if stage == 'adopt': row = review(e, row)
    if change == 'page': edit_page(e, lambda body: body.update(title='Changed page'))
    else:
        # Storage corruption without a version bump must not evade content pins.
        with e.raw_store.transaction(e.nid, e.scope) as state:
            panel = state['collections'][e.comic.RECORDS][e.page['id']]['document']['panels'][0]
            if change == 'brief': panel['image_brief'] += ' changed'
            elif change == 'panel': panel['x'] += 1
            else: panel['appearance_references'] = [{'character_id': 'unreviewed-reference'}]
    before = deepcopy(e.raw_store.read(e.nid, e.scope)); calls = len(e.posts)
    with pytest.raises(REJECTED):
        if stage == 'preview': preview(e, command)
        elif stage == 'queue': queue(e, command, captured)
        elif stage == 'execute': execute(e, row)
        elif stage == 'review': review(e, row)
        else: adopt(e, row)
    assert e.raw_store.read(e.nid, e.scope) == before and len(e.posts) == calls
    if stage == 'adopt':
        assert e.service.asset(e.nid, e.scope, row['output_candidate']['id'])['version'] == row['approved_asset_version']


@pytest.mark.parametrize('change', ['empty', 'blank', 'references'])
def test_ineligible_panel_cannot_build_request(comic_image, change):
    e = comic_image
    with e.raw_store.transaction(e.nid, e.scope) as state:
        panel = state['collections'][e.comic.RECORDS][e.page['id']]['document']['panels'][0]
        if change == 'empty': panel['image_brief'] = ' \n '
        elif change == 'blank': panel['artwork_mode'] = 'BLANK'
        else: panel['appearance_references'] = [{'character_id': 'alice'}]
    before = deepcopy(e.raw_store.read(e.nid, e.scope))
    with pytest.raises(REJECTED): request(e)
    assert e.raw_store.read(e.nid, e.scope) == before and not e.posts


@pytest.mark.parametrize('field,value', [('prompt', 'unsaved replacement'), ('allow_cloud', True),
    ('operation_id', 'm5.image.i2i')])
def test_comic_source_cannot_be_repurposed_as_arbitrary_command(comic_image, field, value):
    e = comic_image; command = request(e)['command']; command[field] = value
    with pytest.raises(REJECTED): preview(e, command)
    assert not e.posts


@pytest.mark.parametrize('identity', ['actor', 'branch', 'incarnation'])
@pytest.mark.parametrize('stage', ['request', 'execute', 'review', 'adopt'])
def test_old_identity_cannot_request_execute_review_or_attach(comic_image, identity, stage, monkeypatch):
    e = comic_image
    row = queue(e) if stage != 'request' else None
    if stage in {'review', 'adopt'}: row = execute(e, row)
    if stage == 'adopt': row = review(e, row)
    original_scope = deepcopy(e.scope)
    before = deepcopy(e.raw_store.read(e.nid, e.scope)); calls = len(e.posts)
    if identity == 'actor': e.actor = 'another-author'
    elif identity == 'branch': e.scope = {**e.scope, 'branch_id': 'another-branch'}
    else: monkeypatch.setattr(e.store, 'incarnation', lambda nid: 'replacement-project-incarnation')
    with pytest.raises(REJECTED):
        if stage == 'request': request(e)
        elif stage == 'execute': execute(e, row)
        elif stage == 'review': review(e, row)
        else: adopt(e, row)
    assert len(e.posts) == calls
    assert e.raw_store.read(e.nid, original_scope) == before


@pytest.mark.parametrize('status', ['FAILED', 'UNKNOWN', 'CANCELLED', 'REVIEWING', 'AWAITING_REVIEW'])
def test_unapproved_or_ambiguous_job_cannot_attach(comic_image, status):
    e = comic_image; row = execute(e, queue(e)); before = raw_page(e)
    jobs = e.production._image(e.actor)
    def mutate(rows):
        current = next(item for item in rows if item['id'] == row['id'])
        current['status'] = status
        return current
    jobs._mutate(e.nid, e.scope.get('branch_id'), mutate)
    with pytest.raises(REJECTED): adopt(e, row)
    assert raw_page(e) == before and len(e.posts) == 1
    assert e.service.list_assets(e.nid, e.scope)['items'] == []


@pytest.mark.parametrize('field,value', [('expected_version', 99), ('expected_job_version', 99),
    ('expected_request_digest', '0' * 64), ('expected_asset_version', 99), ('expected_output_digest', '0' * 64)])
def test_adoption_requires_exact_page_job_and_asset_review(comic_image, field, value):
    e = comic_image; row = review(e, execute(e, queue(e))); before = raw_page(e)
    with pytest.raises(REJECTED): adopt(e, row, **{field: value})
    assert raw_page(e) == before and len(e.service.list_assets(e.nid, e.scope)['items']) == 1


def test_approved_asset_revision_rejects_attach_without_deleting_asset(comic_image):
    e = comic_image; row = review(e, execute(e, queue(e))); before = raw_page(e)
    with e.service._asset_scope(e.nid, e.scope):
        changed = e.assets.update_metadata(row['output_candidate']['id'], {'scene_id': 'changed'},
            expected_version=row['approved_asset_version'])
    with pytest.raises(REJECTED): adopt(e, row)
    assert raw_page(e) == before
    assert e.service.asset(e.nid, e.scope, changed['id'])['version'] == changed['version']


def test_revoked_attach_preserves_approved_asset_and_original_page(comic_image):
    e = comic_image; row = review(e, execute(e, queue(e))); before = raw_page(e)
    def revoked(): raise PermissionError('synthetic authority revoked')
    with pytest.raises(PermissionError): adopt(e, row, guard=revoked)
    assert raw_page(e) == before
    assert e.service.asset(e.nid, e.scope, row['output_candidate']['id'])['version'] == row['approved_asset_version']


@pytest.mark.parametrize('forgery', ['job_source', 'asset_origin', 'source_job'])
def test_forged_job_or_asset_provenance_never_attaches(comic_image, forgery):
    import json
    e = comic_image; row = review(e, execute(e, queue(e))); before = raw_page(e)
    if forgery == 'job_source':
        jobs = e.production._image(e.actor)
        def mutate(rows):
            current = next(item for item in rows if item['id'] == row['id'])
            current['context']['sources'][0]['comic_panel']['panel_id'] = 'forged-panel'
            return current
        jobs._mutate(e.nid, e.scope.get('branch_id'), mutate)
    else:
        path = e.assets._meta_path(row['output_candidate']['id'])
        meta = json.loads(path.read_text())
        if forgery == 'asset_origin': meta['_studio_result_origin']['sources'] = []
        else: meta['source_job_id'] = 'different-job'
        path.write_text(json.dumps(meta))
    with pytest.raises(REJECTED): adopt(e, row)
    assert raw_page(e) == before and len(e.posts) == 1
    assert e.assets._meta_path(row['output_candidate']['id']).is_file()


def test_missing_explicit_dimensions_and_unrequested_fields_rejected(comic_image):
    e = comic_image
    for changes in ({'parameters': {}}, {'prompt': 'unsaved'}, {'allow_cloud': True},
                    {'expected_version': True}, {'parameters': {'width': 64}}):
        with pytest.raises(REJECTED): request(e, **changes)
    assert not e.posts


def test_source_edit_during_provider_send_prevents_candidate_publication(comic_image, monkeypatch):
    e = comic_image; queued = queue(e)
    original = e.adapter.delegate.transport.post
    def changed_during_send(*args, **kwargs):
        response = original(*args, **kwargs)
        edit_page(e, lambda body: body['panels'][0].update(image_brief='Changed while provider was running'))
        return response
    monkeypatch.setattr(e.adapter.delegate.transport, 'post', changed_during_send)
    result = execute(e, queued)
    assert result['status'] == 'UNKNOWN' and result['output_candidate'] is None
    assert len(e.posts) == 1 and e.service.list_assets(e.nid, e.scope)['items'] == []
    assert raw_page(e)['version'] == 2
    assert raw_page(e)['document']['panels'][0]['asset_id'] is None


@pytest.mark.parametrize('stage', ['execute', 'review', 'adopt'])
def test_actual_delete_recreate_fences_old_generation(comic_image, stage):
    e = comic_image; row = queue(e)
    if stage in {'review', 'adopt'}: row = execute(e, row)
    if stage == 'adopt': row = review(e, row)
    incarnation = e.store.incarnation(e.nid); calls = len(e.posts)
    e.novels.delete(e.nid)
    e.create_project('Replacement project with same slug', nid=e.nid)
    e.service.activate(e.nid, e.scope, e.actor)
    assert e.store.incarnation(e.nid) != incarnation
    before = deepcopy(e.raw_store.read(e.nid, e.scope))
    with pytest.raises(REJECTED):
        if stage == 'execute': execute(e, row)
        elif stage == 'review': review(e, row)
        else: adopt(e, row)
    assert e.raw_store.read(e.nid, e.scope) == before and len(e.posts) == calls
    assert e.comic.records(e.nid, e.scope, e.actor)['items'] == []
    assert e.service.list_assets(e.nid, e.scope)['items'] == []


def test_adoption_clears_page_approval_preserves_other_panels_and_old_asset(comic_image):
    e = comic_image
    manual = e.assets.create(e.nid, 'SYNTHETIC-original.png', base64.b64encode(e.pixels).decode(), 'image/png')
    manual = e.comic.approve_image(e.nid, e.scope, e.actor, manual['id'], manual['version'])
    body = deepcopy(e.page['document'])
    body['panels'][0].update(asset_id=manual['id'], expected_asset_version=manual['version'])
    second = deepcopy(body['panels'][0]); second.update(id='panel-two', order=2, y=370, image_brief='Untouched second panel')
    body['panels'].append(second)
    e.page = e.comic.save(e.nid, e.scope, e.actor, body, rid=e.page['id'], expected_version=e.page['version'])
    report = e.comic.preflight(e.nid, e.scope, e.actor, e.page['id'], e.page['version'])
    assert report['can_render']
    e.page = e.comic.approve(e.nid, e.scope, e.actor, e.page['id'], e.page['version'], report['review_digest'], True)
    assert e.page['status'] == 'APPROVED'
    before = raw_page(e); old_asset = e.assets.get(manual['id'])
    approved = review(e, execute(e, queue(e)))
    adopted = adopt(e, approved)
    assert adopted['status'] == 'DRAFT' and adopted['version'] == before['version'] + 1
    assert adopted['document']['panels'][1] == second
    assert e.assets.get(manual['id']) == old_asset
    after = raw_page(e)
    assert not after.get('approval')
    assert after['history'][-1]['document'] == before['document']
    assert after['history'][-1]['status'] == 'APPROVED'


def test_request_resolves_seed_once_and_original_preview_and_job_keep_exact_command(comic_image):
    e = comic_image
    result = request(e, parameters={'width': 64, 'height': 64})
    command = result['command']
    assert type(command['parameters']['seed']) is int
    assert request(e, parameters={'width': 64, 'height': 64}) == result
    captured = preview(e, command)
    assert captured['command'] == command
    queued = queue(e, command, captured)
    assert queue(e, command, captured) == queued
    stored = e.production._image(e.actor).get_studio(e.nid, e.scope.get('branch_id'), e.actor, queued['id'], lambda: None)
    assert stored['context']['command'] == command
    assert not e.posts and raw_page(e)['version'] == 1
