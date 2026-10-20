"""Bounded non-ripple linked source trim on the original File timeline owner."""
from copy import deepcopy
import pytest
from app.services.studio_timeline_edit import apply_timeline_edits, require_timeline_lock_preservation
from app.services.studio_timeline_links import trim_linked_pair
from app.services.studio_timeline_render import normalize_studio_timeline
from app.services.v1_capability_service import CapabilityVersionConflict
from test_v2_independent_workspace import rig, import_asset, reopened
from test_v2_audio_editing_pipeline import production, source, edit_body, cpu_video, audible_wav
from test_timeline_linked_split_additive import timeline, clips, files

OP = {'op':'clip.trim_linked','video_clip_id':'picture','audio_clip_id':'sound','keep_from_ms':100,'keep_to_ms':650}

def with_unselected(video=None, audio=None, offset=250):
    value=timeline(video,audio,offset)
    for track,identity in zip(value['tracks'],('picture-other','sound-other')):
        clip=deepcopy(track['clips'][0]);clip.update(id=identity,start_ms=4000,in_ms=0,out_ms=500);track['clips'].append(clip)
    value['captions']=[{'start_ms':3000,'end_ms':3500,'text':'Unselected synthetic caption'}]
    return value

def assert_trim(before, after, start=100, end=650):
    old,new=clips(before),clips(after)
    assert set(old)==set(new) and after['clip_links']==before['clip_links']
    expected=deepcopy(before)
    for identity in ('picture','sound'):
        target=clips(expected)[identity];target.update(in_ms=old[identity]['in_ms']+start,out_ms=old[identity]['in_ms']+end)
        assert new[identity]['start_ms']==old[identity]['start_ms']
        assert new[identity]['source_snapshot']==old[identity]['source_snapshot']
    assert after==expected

@pytest.mark.parametrize('offset,start,end',[(250,100,650),(-250,0,600),(0,100,800)])
def test_precise_shared_interval_keeps_offset_and_all_unselected_content(offset,start,end):
    before=normalize_studio_timeline(with_unselected(offset=offset))
    after=apply_timeline_edits(before,[{**OP,'keep_from_ms':start,'keep_to_ms':end}])
    assert_trim(before,after,start,end)
    assert require_timeline_lock_preservation(before,after)==after
    assert set(before)==set(after)
    for fault in ('audio_range','source','position','property','unselected'):
        bad=deepcopy(after)
        if fault=='audio_range':clips(bad)['sound']['in_ms']+=1
        if fault=='source':clips(bad)['sound']['source_snapshot']['digest']='b'*64
        if fault=='position':clips(bad)['sound']['start_ms']+=1
        if fault=='property':clips(bad)['sound']['gain_db']=-1
        if fault=='unselected':clips(bad)['sound-other']['start_ms']+=1
        with pytest.raises(ValueError):require_timeline_lock_preservation(before,bad)

@pytest.mark.parametrize('fault',['negative','empty','reversed','fraction','bool','beyond_shorter','noop','locked','image','speed','fade','extra_field','ripple','mixed','single'])
def test_invalid_modes_bounds_and_old_single_linked_trim_refuse_atomically(fault):
    before=normalize_studio_timeline(with_unselected());op=deepcopy(OP);ops=[op]
    if fault=='negative':op['keep_from_ms']=-1
    elif fault=='empty':op['keep_to_ms']=100
    elif fault=='reversed':op['keep_from_ms']=700
    elif fault=='fraction':op['keep_from_ms']=100.5
    elif fault=='bool':op['keep_from_ms']=True
    elif fault=='beyond_shorter':clips(before)['sound']['out_ms']=600
    elif fault=='noop':op.update(keep_from_ms=0,keep_to_ms=800)
    elif fault=='locked':before['tracks'][1]['locked']=True
    elif fault=='image':clips(before)['picture']['source_snapshot']['asset_kind']='image';clips(before)['picture']['in_ms']=0
    elif fault=='speed':clips(before)['sound']['speed_num']=2
    elif fault=='fade':clips(before)['sound']['fade_out_ms']=10
    elif fault=='extra_field':op['other_clip_id']='picture-other'
    elif fault=='ripple':op['ripple']=True
    elif fault=='mixed':ops.append({'op':'clip.move','clip_id':'picture-other','track_id':'visual','start_ms':5000})
    else:ops=[{'op':'clip.trim','clip_id':'picture','in_ms':200,'out_ms':750,'ripple':False}]
    unchanged=deepcopy(before)
    with pytest.raises(ValueError):apply_timeline_edits(before,ops)
    assert before==unchanged

def test_unlinked_single_trim_keeps_original_fixed_start_behavior():
    before=with_unselected();before.pop('clip_links');before=normalize_studio_timeline(before)
    after=apply_timeline_edits(before,[{'op':'clip.trim','clip_id':'sound','in_ms':150,'out_ms':700,'ripple':False}])
    expected=deepcopy(before);clips(expected)['sound'].update(in_ms=150,out_ms=700)
    assert after==expected

@pytest.fixture
def saved_pair(rig,tmp_path):
    e=rig;e.service.activate(e.nid,e.scope,e.actor)
    e.video=import_asset(e,data=cpu_video(tmp_path/'synthetic.mp4'),kind='video',filename='synthetic.mp4')
    e.audio=import_asset(e,data=audible_wav(),kind='audio',filename='synthetic.wav')
    e.production=production(e)
    e.saved=e.production.timeline_save(e.nid,e.scope,e.actor,None,{'expected_version':0,'title':'Synthetic linked trim','timeline':with_unselected(source(e.video),source(e.audio))},lambda:None)
    return e

def edit(e,row,op=OP,key='linked-trim-once',guard=lambda:None):
    return e.production.timeline_edit(e.nid,e.scope,e.actor,row['id'],edit_body(row,[op],key),guard)

def test_file_trim_replay_and_reopen_use_original_persistent_owner(saved_pair):
    e=saved_pair;made=edit(e,e.saved);assert made['version']==2
    assert_trim(e.saved['timeline'],made['timeline']);before=files(e)
    assert edit(e,e.saved)==made and files(e)==before
    assert production(e,reopened(e)).timeline_get(e.nid,e.scope,e.actor,made['id'],lambda:None)==made

def test_file_full_save_cas_history_and_forged_partner_rollback(saved_pair):
    e=saved_pair;after=trim_linked_pair(e.saved['timeline'],'picture','sound',100,650)
    bad=deepcopy(after);clips(bad)['sound']['in_ms']+=1;before=files(e)
    with pytest.raises(ValueError):e.production.timeline_save(e.nid,e.scope,e.actor,e.saved['id'],{'expected_version':1,'title':e.saved['title'],'timeline':bad},lambda:None)
    assert files(e)==before
    body={'expected_version':1,'title':e.saved['title'],'timeline':after}
    made=e.production.timeline_save(e.nid,e.scope,e.actor,e.saved['id'],body,lambda:None);assert_trim(e.saved['timeline'],made['timeline']);before=files(e)
    with pytest.raises(CapabilityVersionConflict):e.production.timeline_save(e.nid,e.scope,e.actor,e.saved['id'],body,lambda:None)
    assert files(e)==before
    assert production(e,reopened(e)).timeline_get(e.nid,e.scope,e.actor,made['id'],lambda:None)==made
    assert e.production.timeline_history(e.nid,e.scope,e.actor,made['id'],lambda:None)['items'][0]['timeline']==e.saved['timeline']

def test_file_permission_revoked_at_commit_guard_leaves_no_partial_trim(saved_pair,monkeypatch):
    e=saved_pair;before=files(e);revoked=[False];original=e.production._timeline_view
    def view(*args,**kwargs):
        result=original(*args,**kwargs);revoked[0]=True;return result
    def guard():
        if revoked[0]:raise PermissionError('Synthetic authority revoked before commit')
    monkeypatch.setattr(e.production,'_timeline_view',view)
    with pytest.raises(PermissionError):edit(e,e.saved,guard=guard)
    assert revoked[0] and files(e)==before

def test_file_lock_stale_source_and_bounds_are_atomic(saved_pair):
    e=saved_pair;before=files(e)
    with pytest.raises(ValueError):edit(e,e.saved,{**OP,'keep_to_ms':900})
    assert files(e)==before
    locked=edit(e,e.saved,{'op':'track.update','track_id':'voice','changes':{'locked':True}},'lock');before=files(e)
    with pytest.raises(ValueError,match='TRACK_LOCKED'):edit(e,locked)
    assert files(e)==before
    ready=edit(e,locked,{'op':'track.update','track_id':'voice','changes':{'locked':False}},'unlock')
    e.service.lifecycle(e.nid,e.scope,e.audio['id'],e.audio['version'],actor_id=e.actor);before=files(e)
    with pytest.raises((FileNotFoundError,ValueError)):edit(e,ready)
    assert files(e)==before
