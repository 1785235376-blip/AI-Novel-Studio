"""Native OTIO + original HTTP loss acknowledgment for private clip links."""
import base64
from copy import deepcopy
import hashlib
import pytest
from test_studio_asset_query import rig
from test_studio_vtt_import_api_20261030 import case, checked, files

pytestmark = pytest.mark.file_backend_only

@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_link_metadata_loss_is_bound_to_reviewed_export(case, prefix):
    import opentimelineio as otio
    assert otio.__version__ == '0.18.1'
    from app.experimental.timeline_exchange import STUDIO_NS, read_otio
    from app.services.studio_timeline_exchange import exchange_to_studio_timeline
    e = case
    # Synthetic WAV is a formal independent asset, not an audio-history owner.
    import io, wave
    output = io.BytesIO()
    with wave.open(output, 'wb') as stream:
        stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(8000)
        stream.writeframes(b'\0\0' * 8000)
    with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
        asset = e.rig.assets.create(e.rig.nid, 'synthetic.wav', base64.b64encode(output.getvalue()).decode(),
            'audio/wav', 'audio', required_features=('narrative_production_v2',))
    timeline = deepcopy(e.row['timeline'])
    timeline['captions'] = []
    timeline['tracks'].append({'id':'a1','kind':'AUDIO','order':1,'clips':[{
        'id':'audio1','start_ms':0,'in_ms':0,'out_ms':1000,'source_snapshot':{
            'kind':'ASSET','asset_kind':'audio','id':asset['id'],'version':asset['version'],'digest':asset['sha256']}}]})
    timeline['clip_links'] = [{'video_clip_id':'clip1','audio_clip_id':'audio1','offset_ms':0}]
    collection = f'{prefix}/projects/{e.rig.nid}/studio/production/timelines'
    linked = checked(e.rig.client.post(collection, headers=e.headers, json={
        'expected_version':0,'title':'Linked synthetic timeline','timeline':timeline}), 201)
    url = collection+'/'+linked['id']
    request = {'direction':'EXPORT','format':'OTIO','expected_version':linked['version'],
               'reviewed_timeline_digest':linked['timeline_digest']}
    before = files(e.rig.root)
    preview = checked(e.rig.client.post(url+'/transfer-preview',headers=e.headers,json=request))
    losses = [x for x in preview['loss_report'] if x['code']=='CLIP_LINKS_REQUIRE_STUDIO_METADATA']
    assert len(losses)==1 and losses[0]['severity']=='LOSS'
    assert preview['requires_loss_acknowledgment'] is True
    assert files(e.rig.root)==before
    export = {**request,'reviewed_preview_digest':preview['preview_digest'],'acknowledge_losses':False}
    refused = e.rig.client.post(url+'/transfer-attachment',headers=e.headers,json=export)
    assert refused.status_code==422, refused.text
    assert files(e.rig.root)==before
    export['acknowledge_losses'] = True
    tampered = e.rig.client.post(url+'/transfer-attachment',headers=e.headers,json={**export,'reviewed_preview_digest':'0'*64})
    assert tampered.status_code==409, tampered.text
    result = e.rig.client.post(url+'/transfer-attachment',headers=e.headers,json=export)
    assert result.status_code==200, result.text
    assert hashlib.sha256(result.content).hexdigest()==preview['output_sha256']
    native = otio.adapters.read_from_string(result.text,'otio_json')
    # Explicitly simulate a consumer that drops private metadata, not all NLEs.
    del native.metadata[STUDIO_NS]
    stripped = otio.adapters.write_to_string(native,'otio_json')
    document, native_report = read_otio(stripped)
    imported = exchange_to_studio_timeline(document,media_bindings=preview['media_bindings'],
        canvas={key:linked['timeline'][key] for key in ('duration_ms','width','height','fps')})
    assert not imported['timeline'].get('clip_links')
    assert files(e.rig.root)==before
