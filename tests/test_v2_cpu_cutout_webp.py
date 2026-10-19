"""Actual WebP pixels and original File Job/private candidate/Review/Asset path."""
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path

from PIL import Image, features
import pytest

from app.creative.production_execution import digest
from app.creative.production_execution_models import MediaCommand, MediaParameters
from app.services.studio_image_cutout import render_cutout
from app.services.studio_image_cutout_webp import PROFILE, OUTPUT_PROFILE, encode
from app.services.studio_image_execution import _context
from test_v2_cpu_cutout_pixels import rows_for_color, filtered_raw, png, mask
from test_v2_cpu_cutout_api import cpu_client, mask_client, client, checked, mounted, prefix, queue, run, action
from test_v2_manual_mask_api import post


@pytest.mark.parametrize('color', [0, 2, 4, 6])
def test_native_lossless_webp_preserves_every_rgba_byte(color):
    assert features.check('webp'), 'existing local WebP encoder required; no install/fallback'
    source = png(filtered_raw(rows_for_color(color), color, 'mixed'), color=color)
    original, proof = render_cutout(source, mask())
    data, result = encode(original, proof, lambda: None)
    assert data[:4] == b'RIFF' and data[8:16] == b'WEBPVP8L'
    with Image.open(io.BytesIO(original)) as before, Image.open(io.BytesIO(data)) as after:
        assert after.format == 'WEBP' and after.size == before.size
        raw = before.convert('RGBA').tobytes()
        assert after.convert('RGBA').tobytes() == raw
    assert result['rgba_sha256'] == hashlib.sha256(raw).hexdigest()
    assert result['output_sha256'] == hashlib.sha256(data).hexdigest() and result['output_bytes'] == len(data)
    assert proof['contract'] == 'cpu-binary-mask-cutout/1'


@pytest.mark.parametrize('profile', [None, True, 'PNG', 'WEBP', 'WEBP_LOSSLESS_V2'])
def test_closed_profile_not_admitted_as_generic_encoder(cpu_client, profile):
    raw = deepcopy(cpu_client.command); raw['parameters'] = {'cutout_output': profile}
    with pytest.raises(ValueError): MediaCommand.model_validate(raw)
    assert cpu_client.client.post(cpu_client.base + '/preview', headers=cpu_client.headers, json=raw).status_code == 422


def test_unchanged_default_and_graph_parameter_class():
    raw = {'operation_id': 'm5.image.cutout', 'request_id': 'legacy', 'provider_id': None, 'model_id': None,
        'prompt': '', 'parameters': {}, 'source_snapshots': [{'kind': 'ASSET', 'asset_kind': 'image', 'id': name, 'version': 1, 'digest': 'a'*64} for name in ('source', 'mask')],
        'allow_cloud': False, 'license_note': ''}
    assert MediaCommand.model_validate(raw).model_dump(exclude_none=True)['parameters'] == {}
    with pytest.raises(ValueError): MediaParameters.model_validate({'cutout_output': PROFILE})


@pytest.mark.parametrize('change', ['missing_command', 'missing_recipe', 'command_profile_removed', 'recipe_profile_removed'])
def test_new_profile_requires_exact_original_binding(cpu_client, change):
    e = cpu_client; e.command['parameters'] = {'cutout_output': PROFILE}
    _, row = queue(e)
    stored = next(job for path in e.root.glob('image-jobs/actors/*/image-jobs/*.json')
        for job in json.loads(path.read_text(encoding='utf-8')) if job['id'] == row['id'])
    context, body = deepcopy(stored['context']), deepcopy(stored['body'])
    if change == 'missing_command': context.pop('command')
    elif change == 'missing_recipe': context.pop('execution_recipe')
    elif change == 'command_profile_removed': context['command']['parameters'].clear()
    else:
        context['execution_recipe']['parameters'].clear()
        recipe = context['execution_recipe']; recipe['recipe_digest'] = digest({key: value for key, value in recipe.items() if key != 'recipe_digest'})
    if 'command' in context:
        context['request_digest'] = digest({'context': {key: value for key, value in context.items() if key not in {'command', 'request_digest'}}, 'command': context['command']})
    with pytest.raises(ValueError): _context(context, body, stored['owner_actor_id'])
    assert row['status'] == 'QUEUED'


def test_actual_file_candidate_review_and_saved_webp(cpu_client):
    e = cpu_client; e.command['parameters'] = {'cutout_output': PROFILE}
    preview, queued = queue(e)
    assert preview['execution_recipe']['output_profile'] == OUTPUT_PROFILE
    result = checked(run(e, queued)); assert result['status'] == 'AWAITING_REVIEW', result
    candidate = result['output_candidate']; proof = result['processing_proof']
    assert e.client.get(e.studio_base + '/assets/' + candidate['id'], headers=e.headers).status_code == 404
    response = e.client.get(e.base + '/jobs/image/' + result['id'] + '/candidate', headers=e.headers)
    assert response.status_code == 200 and response.headers['content-type'].startswith('image/webp')
    assert hashlib.sha256(response.content).hexdigest() == proof['output_sha256'] == candidate['digest']
    source = e.client.get(e.studio_base + '/assets/' + e.source['id'] + '/download', headers=e.headers).content
    mask_bytes = e.client.get(e.studio_base + '/assets/' + e.mask['id'] + '/download', headers=e.headers).content
    reference, _ = render_cutout(source, mask_bytes)
    with Image.open(io.BytesIO(reference)) as before, Image.open(io.BytesIO(response.content)) as after:
        assert after.format == 'WEBP' and after.size == (64, 64)
        raw = before.convert('RGBA').tobytes(); assert after.convert('RGBA').tobytes() == raw
    assert proof['rgba_sha256'] == hashlib.sha256(raw).hexdigest()
    approved = checked(e.client.post(e.base + '/jobs/image/' + result['id'] + '/review', headers=e.headers,
        json={**action(result), 'reviewed_output_digest': candidate['digest']}))
    assert approved['status'] == 'APPROVED'
    asset = checked(e.client.get(e.studio_base + '/assets/' + candidate['id'], headers=e.headers))
    assert asset['media_type'] == 'image/webp' and asset['filename'].endswith('.webp')
    assert asset['provenance']['origin'] == 'DERIVED_PROCESSING' and asset['provider_id'] is None and asset['model_id'] is None
    assert e.client.get(e.studio_base + '/assets/' + candidate['id'] + '/download', headers=e.headers).content == response.content
    folder = os.environ.get('CUTOUT_WEBP_EVIDENCE_DIR')
    if folder:
        folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
        (folder / 'actual-file.json').write_text(json.dumps({'command': e.command, 'source': e.source, 'mask': e.mask, 'preview': preview,
            'queued': queued, 'executed': result, 'approved': approved, 'asset': asset}, indent=2), encoding='utf-8')
        (folder / 'output.webp').write_bytes(response.content)


def test_host_revoke_after_native_webp_cannot_publish(cpu_client, monkeypatch):
    e = cpu_client; e.command['parameters'] = {'cutout_output': PROFILE}; _, queued = queue(e)
    import app.services.studio_image_cutout_webp as helper
    original = helper.encode
    def revoked(*args, **kwargs):
        value = original(*args, **kwargs); e.sessions.revoke(e.host); return value
    monkeypatch.setattr(helper, 'encode', revoked)
    assert run(e, queued).status_code in {401, 403, 404}
    assert len(list(e.assets.root.glob('*.bin'))) == 2
