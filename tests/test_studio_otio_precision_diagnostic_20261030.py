"""Read-only diagnostic at the existing strict transfer-preview error boundary."""
import pytest
import opentimelineio as otio
from test_studio_asset_query import rig
from test_studio_otio_runtime_20261029 import case, attachment, base, body, files

pytestmark = pytest.mark.file_backend_only

@pytest.mark.parametrize('prefix',['/api','/api/v1'])
@pytest.mark.parametrize('native_frames,rate,status',[(5,25,'INTEGER_MILLISECONDS'),(1,24,'FRACTIONAL_MILLISECONDS')])
def test_preview_diagnoses_first_precision_conflict_without_importing(case,prefix,native_frames,rate,status):
    e=case;url=base(e,prefix)
    exported,result=attachment(e,prefix)
    native=otio.adapters.read_from_string(result.text,'otio_json')
    clip=native.tracks[0][0]
    clip.name='PRIVATE_CLIP_NAME_DO_NOT_ECHO'
    clip.media_reference.target_url='file:///PRIVATE_MEDIA_PATH_DO_NOT_ECHO.mp4'
    clip.source_range=otio.opentime.TimeRange(otio.opentime.RationalTime(native_frames,rate),clip.source_range.duration)
    content=otio.adapters.write_to_string(native,'otio_json')
    request=body(e,'IMPORT',content=content,media_bindings=exported['media_bindings'])
    before=files(e.rig.root)
    response=e.rig.client.post(url+'/transfer-preview',headers=e.headers,json=request)
    assert response.status_code==422,response.text
    detail=response.json()['detail']
    assert detail['code']=='EXPERIMENTAL_INVALID'
    assert detail['message']=='OTIO_EXACT_TIME_METADATA_MISMATCH'
    assert detail['diagnostic']=={
        'contract':'studio-otio-precision-diagnostic/1',
        'path':'tracks[0].items[0]','field':'start',
        'first_conflict_only':True,'native_time_status':status,
        'strict_import_allowed':False,'source_validation':'NOT_EVALUATED',
        'remaining_timeline_validation':'NOT_EVALUATED',
        'compatibility_mode':'EXPLICIT_OPT_IN_AVAILABLE' if status=='INTEGER_MILLISECONDS' else 'NOT_AVAILABLE_FOR_THIS_CONFLICT',
        'potential_loss_codes':['EXACT_TIME_METADATA_WOULD_BE_DISCARDED'],
        'next_action':'PREVIEW_EXPLICIT_EXTERNAL_NATIVE_API_MODE' if status=='INTEGER_MILLISECONDS' else 'REVIEW_SOURCE_APPLICATION_EXPORT'}
    assert 'PRIVATE_' not in response.text
    assert files(e.rig.root)==before
    # Writes remain strict, with exactly their previous opaque rejection body.
    imported=e.rig.client.post(url+'/transfer-import',headers=e.headers,json={**request,
        'request_id':'never-import-conflicting-metadata','reviewed_preview_digest':'0'*64,'acknowledge_losses':True})
    assert imported.status_code==422,imported.text
    assert imported.json()['detail']=={'code':'EXPERIMENTAL_INVALID','message':'OTIO_EXACT_TIME_METADATA_MISMATCH'}
    assert 'diagnostic' not in imported.text
    assert files(e.rig.root)==before
    denied=e.rig.client.post(url+'/transfer-preview',headers={'X-Session-Token':'unknown-session'},json=request)
    assert denied.status_code in (401,403),denied.text
    assert 'diagnostic' not in denied.text and 'PRIVATE_' not in denied.text
    assert files(e.rig.root)==before


def test_diagnostic_does_not_revalidate_native_fraction_and_replace_strict_error():
    from app.experimental.timeline_exchange import _read_time, time_value, NS
    item=otio.schema.Clip()
    item.metadata[NS]={'start':time_value(1,25)}
    with pytest.raises(ValueError,match='^OTIO_EXACT_TIME_METADATA_MISMATCH$') as error:
        _read_time(item,'start',otio.opentime.RationalTime(0.3333333333333333,25),'tracks[0].items[0]')
    assert error.value.diagnostic['native_time_status']=='FRACTIONAL_MILLISECONDS'


def test_preview_reauthorizes_before_exposing_diagnostic(case,monkeypatch):
    from app.experimental import api as experimental_api
    from app.experimental.timeline_exchange import ExactTimeMetadataMismatch
    e=case;before=files(e.rig.root)
    def revoked(*args,**kwargs):
        e.rig.sessions.revoke(e.headers['X-Session-Token'])
        raise ExactTimeMetadataMismatch('tracks[0].items[0]','start',None)
    monkeypatch.setattr(experimental_api.studio_production_service,'timeline_transfer_preview',revoked)
    response=e.rig.client.post(base(e,'/api')+'/transfer-preview',headers=e.headers,json=body(e))
    assert response.status_code in (401,403),response.text
    assert 'diagnostic' not in response.text
    assert files(e.rig.root)==before


def test_auxiliary_classification_failure_cannot_replace_primary_error():
    from app.experimental.timeline_exchange import ExactTimeMetadataMismatch
    error=ExactTimeMetadataMismatch('timeline','global_start_time',{'frames':{}})
    assert str(error)=='OTIO_EXACT_TIME_METADATA_MISMATCH'
    assert error.diagnostic['native_time_status']=='NOT_EVALUATED'
