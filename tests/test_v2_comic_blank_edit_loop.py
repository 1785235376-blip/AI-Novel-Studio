"""SPEC IMAGE-COMIC closed loop for standalone blank comic pages (no model).

Covers the SPEC-2026.10.19-r1 flow B minimum: create a blank comic page (no novel
chapter and no screenplay), draw panels, import an existing approved Image asset,
edit independent bubble/text objects, save (CAS version), close/reopen, edit text
only, preflight -> approve -> export PNG segments, add a second page and verify the
original permission/branch/asset fences still apply.

This reuses the existing comic-layouts owner, the original ExperimentalStore CAS,
AssetLibraryService, trusted-session/role authorization and the original review and
export path. It creates no Comic Studio application, no second asset database, no
parallel job queue and never calls a model/provider.

The pinned OFL CJK font licensing/glyph suite remains test_r5_comic_layouts.py; this
suite injects PIL's deterministic FreeType default font only to isolate edit-loop
semantics so it can run offline in a minimal environment.
"""
import base64
import hashlib
import io
import json
import zipfile

import pytest
from PIL import ImageFont

from test_r3_mounted_contracts import checked, mounted, prefix, scoped
from test_r5_comic_layouts import synthetic_png

COMIC = '/comic-layouts'


@pytest.fixture(autouse=True)
def deterministic_font(monkeypatch):
    import app.experimental.comic_layouts as module

    def fake_font():
        return b'TEST-ONLY-OFL-PLACEHOLDER', b'TEST-ONLY-OFL-PLACEHOLDER-LICENSE', frozenset()

    def fake_text_layout(bubble, font_data, coverage):
        return ImageFont.load_default(), bubble['text'].split('\n'), 36

    def fake_font_status():
        return {'available': True, 'family': 'PIL default (test injection)', 'license': 'TEST_ONLY',
                'sha256': '0' * 64, 'embedded': False, 'rendered_into_pixels': True}

    monkeypatch.setattr(module, 'licensed_font', fake_font)
    monkeypatch.setattr(module, '_text_layout', fake_text_layout)
    monkeypatch.setattr(module, 'font_status', fake_font_status)


def page_payload(*, asset=None, approved_version=None, bubbles=None, page_number=1,
                 title='Blank comic page', reading='LTR'):
    panel = {'id': 'panel-1', 'order': 1, 'x': 24, 'y': 24, 'width': 752, 'height': 1000}
    if asset is not None:
        panel['asset_id'] = asset['id']
        panel['expected_asset_version'] = approved_version
    if bubbles:
        panel['bubbles'] = bubbles
    return {'title': title, 'source_mode': 'STANDALONE', 'page_number': page_number,
            'reading_direction': reading, 'preset': 'PAGE', 'width': 800, 'height': 1120,
            'segment_height': 560, 'panels': [panel]}


def upload_and_approve_image(e, headers=None):
    headers = headers or {}
    asset = e.assets.create(e.nid, 'SYNTHETIC-COMIC-PANEL.png',
                            base64.b64encode(synthetic_png()).decode(), 'image/png',
                            branch_id=e.scope.get('branch_id'))
    image_path = e.base + COMIC + '/images/' + asset['id']
    preview = e.client.get(image_path, headers=headers)
    assert preview.status_code == 200 and preview.content.startswith(b'\x89PNG')
    approved = checked(e.client.post(image_path + '/approve', headers=headers,
                                     json={'expected_version': asset['version']}))
    return asset, approved, preview.content


def test_blank_comic_page_edit_loop_without_screenplay_or_model(mounted):
    e = mounted
    # 1) Blank page creation: no screenplay id/version, no novel chapter, project scope only.
    first = checked(e.client.post(e.base + COMIC + '/records',
                                  json=page_payload(title='Blank page one')), 201)
    assert first['status'] == 'DRAFT'
    assert first['document']['source_mode'] == 'STANDALONE'
    assert first['document']['page_number'] == 1 and first['document']['reading_direction'] == 'LTR'
    assert first['scene_ids'] == {} and first['document'].get('screenplay_id') is None
    record_path = e.base + COMIC + '/records/' + first['id']

    # 2) Reopen by id and through the list; the empty panel is a visible blocker.
    reopened = checked(e.client.get(record_path))
    assert reopened['document']['title'] == 'Blank page one'
    listed = checked(e.client.get(e.base + COMIC + '/records'))
    assert [row['id'] for row in listed['items']] == [first['id']]
    empty_report = checked(e.client.post(record_path + '/preflight', json={'expected_version': 1}))
    assert empty_report['can_render'] is False
    assert any(issue['code'] == 'COMIC_MISSING_APPROVED_IMAGE' for issue in empty_report['issues'])

    # 3) Import an existing Image asset (original asset owner) and attach it to the panel.
    asset, approved, image_preview = upload_and_approve_image(e)
    bubbles = [{'id': 'bubble-1', 'kind': 'DIALOGUE', 'text': 'HELLO COMIC',
                'x': 48, 'y': 48, 'width': 500, 'height': 160, 'font_size': 28}]
    second = checked(e.client.put(record_path, json={
        **page_payload(asset=asset, approved_version=approved['version'], bubbles=bubbles,
                       title='Blank page one'),
        'expected_version': 1}))
    assert second['version'] == 2
    assert second['document']['panels'][0]['asset_id'] == asset['id']
    assert second['document']['panels'][0]['bubbles'][0]['text'] == 'HELLO COMIC'

    # 4) Text-only edit: new page version, unchanged image asset bytes/version.
    before_asset = e.assets.get(asset['id'], branch_id=e.scope.get('branch_id'))
    before_preview = e.client.get(e.base + COMIC + '/images/' + asset['id']).content
    edited = checked(e.client.put(record_path, json={
        **page_payload(asset=asset, approved_version=approved['version'], bubbles=[
            {**bubbles[0], 'text': 'EDITED DIALOGUE ONLY'}], title='Blank page one'),
        'expected_version': 2}))
    assert edited['version'] == 3
    assert edited['document']['panels'][0]['bubbles'][0]['text'] == 'EDITED DIALOGUE ONLY'
    after_asset = e.assets.get(asset['id'], branch_id=e.scope.get('branch_id'))
    after_preview = e.client.get(e.base + COMIC + '/images/' + asset['id']).content
    assert (after_asset['version'], after_asset['sha256']) == (before_asset['version'], before_asset['sha256'])
    assert after_preview == before_preview == image_preview

    # 5) Close/reopen then review + export through the original path.
    reopened = checked(e.client.get(record_path))
    assert reopened['document']['panels'][0]['bubbles'][0]['text'] == 'EDITED DIALOGUE ONLY'
    report = checked(e.client.post(record_path + '/preflight', json={'expected_version': 3}))
    assert report['can_render'] is True
    approved_page = checked(e.client.post(record_path + '/approve', json={
        'expected_version': 3, 'review_digest': report['review_digest'],
        'acknowledge_warnings': True}))
    export_path = record_path + '/export?expected_version=' + str(approved_page['version'])
    exported = e.client.get(export_path)
    assert exported.status_code == 200 and exported.content.startswith(b'PK')
    with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
        names = archive.namelist()
        assert 'segment-001.png' in names and 'manifest.json' in names and 'OFL.txt' in names
        manifest = json.loads(archive.read('manifest.json'))
        assert manifest['source_mode'] == 'STANDALONE'
        assert manifest['page']['number'] == 1 and manifest['page']['reading_direction'] == 'LTR'
        assert manifest['page']['title'] == 'Blank page one'
        assert manifest['status'] == 'APPROVED_LAYOUT_EXPORT_COPY'
        segment = archive.read('segment-001.png')
        assert segment == e.client.get(
            record_path + '/segments/0?expected_version=' + str(approved_page['version'])).content
        assert manifest['segments'][0]['sha256'] == hashlib.sha256(segment).hexdigest()

    # 6) Unapproved edits are not exportable; page two is a separate CAS page.
    checked(e.client.put(record_path, json={
        **page_payload(asset=asset, approved_version=approved['version'], bubbles=[
            {**bubbles[0], 'text': 'LATE UNREVIEWED EDIT'}], title='Blank page one'),
        'expected_version': 4}))
    blocked = e.client.get(record_path + '/export?expected_version=5')
    assert blocked.status_code >= 400 and not blocked.content.startswith(b'PK')
    second_page = checked(e.client.post(e.base + COMIC + '/records',
                                        json=page_payload(page_number=2, title='Blank page two')), 201)
    catalog = checked(e.client.get(e.base + COMIC + '/catalog'))
    assert catalog['source_modes'] == ['SCREENPLAY', 'STANDALONE']
    assert catalog['standalone_requires_model'] is False
    assert catalog['renderer']['model_called'] is not True
    pages = checked(e.client.get(e.base + COMIC + '/records'))['items']
    assert [row['document']['page_number'] for row in pages] == [1, 2]
    assert second_page['document']['source_mode'] == 'STANDALONE'


def test_blank_page_permission_branch_and_unknown_asset_fences(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch)
    created = checked(e.client.post(e.base + COMIC + '/records', headers=e.headers,
                                    json=page_payload(title='Scoped blank page')), 201)
    record_path = e.base + COMIC + '/records/' + created['id']
    # Viewer can read the namespace but the owner-filtered listing never leaks the page.
    viewer_list = e.client.get(e.base + COMIC + '/records', headers=e.viewer_headers)
    assert viewer_list.status_code == 200
    assert 'Scoped blank page' not in viewer_list.text and created['id'] not in viewer_list.text
    # Viewer lacks domain.write.
    denied = e.client.put(record_path, headers=e.viewer_headers, json={
        **page_payload(title='Scoped blank page'), 'expected_version': 1})
    assert denied.status_code in {401, 403, 404}
    # Another branch of the same project is fenced by the original authority stack.
    other = e.client.get(record_path, headers={**e.headers, 'X-Branch-ID': e.other_branch})
    assert other.status_code in {401, 403, 404}
    # Unknown asset ids fail closed and never mutate the page.
    missing = e.client.put(record_path, headers=e.headers, json={
        **page_payload(asset={'id': 'missing-asset'}, approved_version=1), 'expected_version': 1})
    assert missing.status_code in {400, 404, 422}
    still = checked(e.client.get(record_path, headers=e.headers))
    assert still['version'] == 1 and still['document']['panels'][0].get('asset_id') is None
    # Revoked authority cannot write.
    e.authorization.revoke_role(e.role, e.lead)
    revoked = e.client.put(record_path, headers=e.headers, json={
        **page_payload(title='Scoped blank page'), 'expected_version': 1})
    assert revoked.status_code in {401, 403, 404}
