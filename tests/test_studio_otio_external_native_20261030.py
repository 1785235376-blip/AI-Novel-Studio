"""Explicit external-native edits use the original Studio transfer/CAS owner."""
from copy import deepcopy
import hashlib
import pytest
import opentimelineio as otio
from app.experimental.timeline_exchange import NS, read_otio, time_value, rational
from test_studio_asset_query import rig
from test_studio_otio_runtime_20261029 import case, attachment, base, body, files, call

pytestmark = pytest.mark.file_backend_only


def edited(e, prefix='/api', edit='trim'):
    exported, response = attachment(e, prefix)
    native = otio.adapters.read_from_string(response.text, 'otio_json')
    clip = native.tracks[0][0]
    if edit == 'trim':
        clip.source_range = otio.opentime.TimeRange(otio.opentime.RationalTime(5, 25),
                                                   otio.opentime.RationalTime(20, 25))
    elif edit == 'speed':
        clip.effects.append(otio.schema.LinearTimeWarp(time_scalar=2))
        clip.metadata[NS]['speed'] = rational(1)
        clip.source_range = otio.opentime.TimeRange(otio.opentime.RationalTime(5, 25),
                                                   otio.opentime.RationalTime(10, 25))
    elif edit == 'gap':
        gap = otio.schema.Gap(source_range=otio.opentime.TimeRange(
            otio.opentime.RationalTime(0, 25), otio.opentime.RationalTime(5, 25)))
        gap.metadata[NS] = {'start':time_value(0,25), 'duration':time_value(10,25)}
        native.tracks[0].insert(0, gap)
    content = otio.adapters.write_to_string(native, 'otio_json')
    return native, body(e, 'IMPORT', content=content, media_bindings=exported['media_bindings'],
                        otio_edit_mode='EXTERNAL_NATIVE')


@pytest.mark.parametrize('prefix',['/api','/api/v1'])
@pytest.mark.parametrize('edit',['trim','speed','gap'])
def test_explicit_native_edit_preview_ack_apply_replay(case,prefix,edit):
    e=case; url=base(e,prefix); native, request=edited(e,prefix,edit)
    before=files(e.rig.root)
    strict={**request,'otio_edit_mode':'STRICT'}
    response=e.rig.client.post(url+'/transfer-preview',headers=e.headers,json=strict)
    assert response.status_code==422,response.text
    preview=call(e,url+'/transfer-preview',request)
    assert files(e.rig.root)==before
    assert preview['otio_edit_mode']=='EXTERNAL_NATIVE'
    assert preview['input_sha256']==hashlib.sha256(request['content'].encode()).hexdigest()
    codes=[row['code'] for row in preview['loss_report']]
    assert 'EXACT_TIME_METADATA_DISCARDED_FOR_NATIVE_EDIT' in codes
    assert 'STUDIO_METADATA_STALE_AFTER_NATIVE_EDIT_NOT_RESTORED' in codes
    if edit=='speed': assert 'EXACT_SPEED_METADATA_DISCARDED_FOR_NATIVE_EDIT' in codes
    clip=preview['timeline']['tracks'][0]['clips'][0]
    assert (clip['start_ms'],clip['in_ms'],clip['out_ms'])==(
        (200,400,1400) if edit=='gap' else (0,200,1000))
    if edit=='speed': assert (clip['speed_num'],clip['speed_den'])==(2,1)
    commit={**request,'request_id':'external-native-'+edit,'reviewed_preview_digest':preview['preview_digest']}
    denied=e.rig.client.post(url+'/transfer-import',headers=e.headers,json=commit)
    assert denied.status_code==422 and 'REVIEW_LOSS_REPORT_REQUIRED' in denied.text
    assert files(e.rig.root)==before
    result=call(e,url+'/transfer-import',{**commit,'acknowledge_losses':True})
    assert result['version']==2 and result['timeline']==preview['timeline']
    after=files(e.rig.root)
    assert call(e,url+'/transfer-import',{**commit,'acknowledge_losses':True})==result
    assert files(e.rig.root)==after


@pytest.mark.parametrize('mutation',['bytes','binding','mode','cas','digest','source'])
def test_changed_preview_inputs_cannot_write(case,mutation):
    e=case;url=base(e,'/api');native,request=edited(e)
    preview=call(e,url+'/transfer-preview',request)
    commit={**deepcopy(request),'request_id':'changed-input','reviewed_preview_digest':preview['preview_digest'],'acknowledge_losses':True}
    if mutation=='bytes': commit['content']+=' '
    elif mutation=='binding': commit['media_bindings'][0]['reference']='media/unbound'
    elif mutation=='mode': commit['otio_edit_mode']='STRICT'
    elif mutation=='cas': commit['expected_version']+=1
    elif mutation=='digest': commit['reviewed_preview_digest']='0'*64
    else: commit['media_bindings'][0]['source_snapshot']['version']+=1
    before=files(e.rig.root)
    response=e.rig.client.post(url+'/transfer-import',headers=e.headers,json=commit)
    assert response.status_code in (409,422),response.text
    assert files(e.rig.root)==before


@pytest.mark.parametrize('bad',[None,[],{}, {'frames':{'numerator':1,'denominator':0},'rate':rational(25)},
    {'frames':rational(1),'rate':rational(0)}, {'frames':rational(1),'rate':rational(25),'extra':'bad'}])
def test_malformed_precision_is_not_stale_evidence(case,bad):
    native,request=edited(case)
    # JSON through native serializer retains malformed namespace values.
    native.tracks[0][0].metadata[NS]['start']=bad
    request['content']=otio.adapters.write_to_string(native,'otio_json')
    before=files(case.rig.root)
    response=case.rig.client.post(base(case,'/api')+'/transfer-preview',headers=case.headers,json=request)
    assert response.status_code==422,response.text
    assert files(case.rig.root)==before


@pytest.mark.parametrize('kind',['fractional','fractional_gap','available','global','speed_rounded'])
def test_opt_in_does_not_expand_native_or_source_contract(case,kind):
    native,request=edited(case)
    clip=native.tracks[0][0]
    if kind=='fractional':
        clip.source_range=otio.opentime.TimeRange(otio.opentime.RationalTime(1,24),clip.source_range.duration)
    elif kind=='fractional_gap':
        native.tracks[0].insert(0,otio.schema.Gap(source_range=otio.opentime.TimeRange(
            otio.opentime.RationalTime(1,24),otio.opentime.RationalTime(5,25))))
    elif kind=='available':
        clip.media_reference.available_range=otio.opentime.TimeRange(otio.opentime.RationalTime(0,25),otio.opentime.RationalTime(50,25))
        clip.media_reference.metadata[NS]={'start':time_value(1,25),'duration':time_value(50,25)}
    elif kind=='global':
        native.global_start_time=otio.opentime.RationalTime(1,25)
        native.metadata[NS]={'global_start_time':time_value(0,25)}
    else:
        clip.effects.append(otio.schema.LinearTimeWarp(time_scalar=1.0000000000001))
    request['content']=otio.adapters.write_to_string(native,'otio_json')
    before=files(case.rig.root)
    response=case.rig.client.post(base(case,'/api')+'/transfer-preview',headers=case.headers,json=request)
    assert response.status_code==422,response.text
    if kind in ('available','global'):
        assert response.json()['detail']['diagnostic']['compatibility_mode']=='NOT_AVAILABLE_FOR_THIS_CONFLICT'
    assert files(case.rig.root)==before


def test_strict_default_request_digest_and_response_unchanged(case):
    e=case;exported,response=attachment(e,'/api');request=body(e,'IMPORT',content=response.text,media_bindings=exported['media_bindings'])
    old=call(e,base(e,'/api')+'/transfer-preview',request)
    assert old==call(e,base(e,'/api')+'/transfer-preview',{**request,'otio_edit_mode':'STRICT'})
    assert 'otio_edit_mode' not in old and 'input_sha256' not in old
    explicit=call(e,base(e,'/api')+'/transfer-preview',{**request,'otio_edit_mode':'EXTERNAL_NATIVE'})
    assert explicit['timeline']==old['timeline'] and explicit['preview_digest']!=old['preview_digest']
    assert explicit['requires_loss_acknowledgment'] is True


@pytest.mark.parametrize('direction,format',[('EXPORT','OTIO'),('IMPORT','VTT'),('IMPORT','SRT')])
def test_mode_is_only_for_otio_import(case,direction,format):
    request={**body(case,direction),'format':format,'otio_edit_mode':'EXTERNAL_NATIVE','content':'WEBVTT\n\n' if direction=='IMPORT' else ''}
    response=case.rig.client.post(base(case,'/api')+'/transfer-preview',headers=case.headers,json=request)
    assert response.status_code==422,response.text


@pytest.mark.parametrize('duration',[0, -1, 86401])
def test_invalid_stale_duration_is_not_eligible(case,duration):
    native,request=edited(case)
    native.tracks[0][0].metadata[NS]['duration']=time_value(duration,1)
    request['content']=otio.adapters.write_to_string(native,'otio_json')
    before=files(case.rig.root)
    response=case.rig.client.post(base(case,'/api')+'/transfer-preview',headers=case.headers,json=request)
    assert response.status_code==422 and 'OTIO_CLIP_TIME_LIMIT' in response.text
    assert files(case.rig.root)==before


@pytest.mark.parametrize('value',[None, {}, {'numerator':0,'denominator':1}, {'numerator':1,'denominator':0}, {'numerator':True,'denominator':1}])
def test_invalid_stale_speed_is_not_eligible(case,value):
    native,request=edited(case)
    native.tracks[0][0].metadata[NS]['speed']=value
    request['content']=otio.adapters.write_to_string(native,'otio_json')
    before=files(case.rig.root)
    response=case.rig.client.post(base(case,'/api')+'/transfer-preview',headers=case.headers,json=request)
    assert response.status_code==422,response.text
    assert files(case.rig.root)==before


def test_native_speed_removal_discards_valid_old_hint(case):
    native,request=edited(case)
    native.tracks[0][0].metadata[NS]['speed']=rational(2)
    request['content']=otio.adapters.write_to_string(native,'otio_json')
    preview=call(case,base(case,'/api')+'/transfer-preview',request)
    clip=preview['timeline']['tracks'][0]['clips'][0]
    assert (clip['speed_num'],clip['speed_den'])==(1,1)
    assert any(row['code']=='EXACT_SPEED_METADATA_DISCARDED_FOR_NATIVE_EDIT' for row in preview['loss_report'])


def test_out_of_range_stale_start_is_not_eligible(case):
    native,request=edited(case)
    native.tracks[0][0].metadata[NS]['start']=time_value(86401,1)
    request['content']=otio.adapters.write_to_string(native,'otio_json')
    before=files(case.rig.root)
    response=case.rig.client.post(base(case,'/api')+'/transfer-preview',headers=case.headers,json=request)
    assert response.status_code==422 and 'OTIO_CLIP_TIME_LIMIT' in response.text
    assert files(case.rig.root)==before
