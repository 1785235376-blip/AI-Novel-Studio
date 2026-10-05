"""Official OTIO native-parser round trips and actual File/PostgreSQL receipts."""
import base64
import copy
import json
from fractions import Fraction
import pytest
try:
    import opentimelineio as otio
except ImportError:
    otio = None
pytestmark = pytest.mark.skipif(otio is None, reason="NOT_RUN: install pinned optional otio extra for official-parser verification")
from app.experimental.timeline_exchange import (TimelineExchangeService, read_otio, write_otio, time_value, seconds, semantic_document, summary)
from app.experimental.common import StaleSourceError
from test_r3_media_support import rig, branch_scope
from test_r4_director import screenplay


def clip(name='clip', rate=24, value=48):
    return otio.schema.Clip(name=name, media_reference=otio.schema.ExternalReference(target_url=f'media/{name}.mp4'),
                            source_range=otio.opentime.TimeRange(otio.opentime.RationalTime(0,rate), otio.opentime.RationalTime(value,rate)))


def source_timeline():
    timeline = otio.schema.Timeline(name='Synthetic edits'); track = otio.schema.Track(name='V1',kind='Video')
    track.append(clip('a')); track.append(otio.schema.Transition(name='dissolve',transition_type='SMPTE_Dissolve',in_offset=otio.opentime.RationalTime(6,24),out_offset=otio.opentime.RationalTime(6,24)))
    track.append(clip('b')); track.append(otio.schema.Gap(source_range=otio.opentime.TimeRange(otio.opentime.RationalTime(0,24),otio.opentime.RationalTime(12,24))))
    timeline.tracks.append(track)
    audio=otio.schema.Track(name='A1',kind='Audio');audio.append(clip('audio',48000,216000));timeline.tracks.append(audio)
    return timeline


def as_text(timeline): return otio.core.serialize_json_to_string(timeline)


@pytest.fixture
def exchange(rig):
    return TimelineExchangeService(rig.store,rig.novels,rig.chapters,rig.screenplays,rig.assets)


def test_official_parser_round_trip_tracks_gaps_dissolve_references_and_exact_time(tmp_path):
    doc, report = read_otio(as_text(source_timeline())); assert report == []
    content = write_otio(doc); path = tmp_path/'new-exchange.otio';path.write_bytes(content)
    actual = otio.core.deserialize_json_from_string(path.read_text(encoding='utf-8'))
    assert len(actual.tracks) == 2 and actual.tracks[0][0].media_reference.target_url == 'media/a.mp4'
    assert actual.duration().to_seconds() == 4.5
    again, _ = read_otio(path.read_text());assert semantic_document(again) == semantic_document(doc)
    assert summary(again)['tracks'][0]['duration_seconds'] == {'numerator': 9, 'denominator': 2}
    assert summary(again)['tracks'][0]['cuts'][1]['start_seconds'] == {'numerator': 2, 'denominator': 1}


def test_fractional_rate_and_many_frames_never_accumulate_float_drift():
    rate=Fraction(30000,1001)
    doc={'name':'rational', 'global_start_time':None, 'tracks':[{'name':'V1','kind':'Video','items':[
        {'kind':'Gap','name':str(i),'start':time_value(0,rate),'duration':time_value(1,rate)} for i in range(500)]}]}
    again,_=read_otio(write_otio(doc).decode())
    assert sum((seconds(r['duration']) for r in again['tracks'][0]['items']),Fraction()) == Fraction(500*1001,30000)
    assert semantic_document(again) == semantic_document(doc)


def test_unsupported_effect_speed_mix_subtitle_and_nested_data_have_explicit_losses():
    timeline=source_timeline();timeline.tracks[0][0].effects.append(otio.schema.LinearTimeWarp(time_scalar=2))
    timeline.tracks[0][0].effects.append(otio.schema.Effect(effect_name='unavailable-glow'))
    timeline.tracks[1].metadata['mix']={'gain':0.2}; timeline.tracks[0][0].markers.append(otio.schema.Marker(name='caption'))
    sub=otio.schema.Track(name='Captions',kind='Subtitle');sub.append(clip('caption'));timeline.tracks.append(sub)
    nested=otio.schema.Stack(children=[otio.schema.Track(children=[clip('nested')])]);timeline.tracks[0].append(nested)
    doc,report=read_otio(as_text(timeline)); codes={r['code'] for r in report}
    assert {'SPEED_EFFECT_NOT_REPRESENTED_TIMING_UNVERIFIED','EFFECT_NOT_REPRESENTED','APPLICATION_METADATA_MIX_SUBTITLES_NOT_REPRESENTED','MARKERS_NOT_REPRESENTED','SUBTITLE_OR_UNKNOWN_TRACK_NOT_REPRESENTED','NESTED_COMPOSITION_REPLACED_WITH_GAP'} <= codes
    assert doc['tracks'][0]['items'][-1]['kind']=='Gap'
    assert write_otio(doc)


def test_invalid_inputs_fail_without_external_access():
    with pytest.raises(ValueError,match='DUPLICATE'):read_otio('{"a":1,"a":2}')
    with pytest.raises(ValueError,match='SIZE'):read_otio('x'*(2*1024*1024+1))
    with pytest.raises(ValueError,match='ROOT'):read_otio('{"foo":"bar"}')
    for url in ['javascript:alert(1)','https://user:password@host/media.mp4','https://host/media?token=secret']:
        timeline=source_timeline();timeline.tracks[0][0].media_reference.target_url=url
        with pytest.raises(ValueError):read_otio(as_text(timeline))
    timeline=source_timeline();timeline.tracks[0][1].in_offset=otio.opentime.RationalTime(300,24)
    with pytest.raises(ValueError,match='EXCEEDS'):read_otio(as_text(timeline))


def test_import_copy_persistence_loss_acknowledgement_and_actor_branch(rig,exchange):
    timeline=source_timeline();timeline.metadata['unsupported subtitles']={'title':'Synthetic'}
    text=as_text(timeline)
    row=exchange.import_file(rig.nid,rig.scope,rig.actor,{'filename':'original.otio','content':text})
    with pytest.raises(ValueError,match='REVIEW'):exchange.download(rig.nid,rig.scope,rig.actor,row['id'],1,False)
    output,filename=exchange.download(rig.nid,rig.scope,rig.actor,row['id'],1,True)
    assert filename!='original.otio' and read_otio(output.decode())[0]
    assert as_text(timeline)==text
    restarted=TimelineExchangeService(rig.store,rig.novels,rig.chapters,rig.screenplays,rig.assets)
    assert restarted.records(rig.nid,rig.scope,rig.actor)['items'][0]['id']==row['id']
    assert restarted.records(rig.nid,rig.scope,'other')['items']==[]
    assert restarted.records(rig.nid,branch_scope(rig),rig.actor)['items']==[]
    with pytest.raises(FileNotFoundError):exchange.download(rig.nid,rig.scope,'other',row['id'],1,True)


def test_screenplay_asset_snapshot_stale_missing_media_and_reauth(rig,exchange):
    row=screenplay(rig)
    asset=rig.assets.create(rig.nid,'synthetic.mp4',base64.b64encode(b'synthetic-no-codec-claim').decode(),'video/mp4','video')
    body={'screenplay_id':row['id'],'expected_screenplay_version':row['edit_version'],'rate_numerator':24000,'rate_denominator':1001,
          'shots':[{'shot_id':row['shots'][0]['id'],'asset_id':asset['id']}]}
    record=exchange.from_screenplay(rig.nid,rig.scope,rig.actor,body)
    output,_=exchange.download(rig.nid,rig.scope,rig.actor,record['id'],1,True)
    assert asset['sha256'] in output.decode() and str(rig.root) not in output.decode()
    assert record['summary']['tracks'][0]['duration_seconds']=={'numerator':5,'denominator':1}
    def revoked():raise PermissionError('revoked')
    with pytest.raises(PermissionError):exchange.download(rig.nid,rig.scope,rig.actor,record['id'],1,True,revoked)
    rig.assets.update_metadata(asset['id'],{'model_id':'changed-model'})
    assert exchange.records(rig.nid,rig.scope,rig.actor)['items'][0]['stale']
    assert 'media' not in exchange.records(rig.nid,rig.scope,rig.actor)['items'][0]
    with pytest.raises(StaleSourceError):exchange.download(rig.nid,rig.scope,rig.actor,record['id'],1,True)
    missing=exchange.from_screenplay(rig.nid,rig.scope,rig.actor,{**body,'shots':[{'shot_id':row['shots'][0]['id']}]})
    assert missing['media'][0]['state']=='MISSING'
    changed=rig.screenplays.approve_shots(rig.nid,row['id'],row['edit_version'])
    assert all(r['stale'] for r in exchange.records(rig.nid,rig.scope,rig.actor)['items'])
    assert changed['edit_version']>row['edit_version']


def test_core_parser_never_calls_adapter_discovery_hooks_or_fetches_media(monkeypatch, tmp_path):
    import socket
    def denied(*args, **kwargs): raise AssertionError('plugin dispatch or network must not run')
    timeline=source_timeline();timeline.tracks[0][0].media_reference.target_url='https://example.invalid/missing.mp4'
    timeline.metadata['OTIO_PLUGIN_MANIFEST_PATH']={'module':'untrusted.py','adapter':'execute-me'}
    text=as_text(timeline)
    monkeypatch.setenv('OTIO_PLUGIN_MANIFEST_PATH',str(tmp_path/'untrusted.json'))
    monkeypatch.setattr(otio.plugins,'ActiveManifest',denied)
    monkeypatch.setattr(otio.adapters,'read_from_string',denied)
    monkeypatch.setattr(otio.adapters,'write_to_string',denied)
    monkeypatch.setattr(socket,'create_connection',denied)
    doc,losses=read_otio(text);data=write_otio(doc)
    assert b'https://example.invalid/missing.mp4' in data
    assert b'execute-me' not in data
    assert any(r['code']=='APPLICATION_METADATA_MIX_SUBTITLES_NOT_REPRESENTED' for r in losses)
    with pytest.raises(ValueError,match='ROOT'):
        read_otio('{"OTIO_SCHEMA":"UntrustedExecutable.1","module":"untrusted.py"}')


def test_missing_optional_parser_is_a_supported_failure_not_an_auto_install(monkeypatch):
    import builtins
    original=builtins.__import__
    def unavailable(name,*args,**kwargs):
        if name=='opentimelineio':raise ImportError('absent')
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',unavailable)
    with pytest.raises(ValueError,match='PARSER_NOT_INSTALLED'):read_otio('{"OTIO_SCHEMA":"Timeline.1"}')


def test_exact_time_metadata_cannot_lie_about_native_timing():
    doc,_=read_otio(as_text(source_timeline()));raw=json.loads(write_otio(doc))
    raw['tracks']['children'][0]['children'][0]['metadata']['ai_novel_studio_exchange_v1']['duration']['frames']['numerator']=999
    with pytest.raises(ValueError,match='MISMATCH'):read_otio(json.dumps(raw))


def test_scoped_media_change_hides_exchange_ids_and_current_read_rejects(rig,exchange):
    row=screenplay(rig)
    asset=rig.assets.create(rig.nid,'private-name.mp4',base64.b64encode(b'synthetic').decode(),'video/mp4','video')
    record=exchange.from_screenplay(rig.nid,rig.scope,rig.actor,{'screenplay_id':row['id'],'expected_screenplay_version':row['edit_version'],'shots':[{'shot_id':row['shots'][0]['id'],'asset_id':asset['id']}]})
    meta=rig.assets.get(asset['id']);meta['branch_id']='hidden';rig.assets._write_meta(meta)
    encoded=json.dumps(exchange.records(rig.nid,rig.scope,rig.actor))
    assert record['id'] not in encoded and asset['id'] not in encoded and 'private-name' not in encoded
    with pytest.raises(FileNotFoundError):exchange.download(rig.nid,rig.scope,rig.actor,record['id'],1,True)


def test_disabled_clip_with_available_media_range_becomes_reported_gap():
    timeline=source_timeline();item=timeline.tracks[1][0]
    item.enabled=False
    item.media_reference.available_range=otio.opentime.TimeRange(otio.opentime.RationalTime(0,48000),otio.opentime.RationalTime(240000,48000))
    doc,losses=read_otio(as_text(timeline))
    assert doc['tracks'][1]['items'][0]['kind']=='Gap'
    assert any(r['code']=='DISABLED_ITEM_REPLACED_WITH_GAP' for r in losses)
    assert write_otio(doc)


def test_long_names_are_not_silently_lost():
    timeline=source_timeline();timeline.name='x'*241
    document,losses=read_otio(as_text(timeline))
    assert document['name']=='x'*240
    assert any(r['code']=='NAME_TRUNCATED_TO_240_CHARACTERS' for r in losses)
    assert write_otio(document)
