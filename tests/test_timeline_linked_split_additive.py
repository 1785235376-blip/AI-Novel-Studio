"""Offset-preserving linked split: tiny imported CPU MP4/WAV and original File."""
from copy import deepcopy
import pytest
from app.services.studio_timeline_edit import apply_timeline_edits, require_timeline_lock_preservation
from app.services.studio_timeline_links import split_linked_pair
from app.services.studio_timeline_render import normalize_studio_timeline
from app.services.v1_capability_service import CapabilityVersionConflict
from test_v2_independent_workspace import rig, import_asset, reopened
from test_v2_audio_editing_pipeline import production, source, edit_body, cpu_video, audible_wav

OP={'op':'clip.split_linked','video_clip_id':'picture','audio_clip_id':'sound','at_ms':1400,'new_video_clip_id':'picture-tail','new_audio_clip_id':'sound-tail'}
def timeline(video=None,audio=None,offset=250):
    pin=lambda kind:{'id':'synthetic-'+kind,'kind':'ASSET','asset_kind':kind,'version':1,'digest':'a'*64}
    return {'schema_version':2,'duration_ms':8000,'width':64,'height':64,'fps':25,'captions':[],
        'tracks':[{'id':'visual','kind':'VIDEO','order':0,'clips':[{'id':'picture','source_snapshot':video or pin('video'),'start_ms':1000,'in_ms':100,'out_ms':900}]},
                  {'id':'voice','kind':'AUDIO','order':1,'clips':[{'id':'sound','source_snapshot':audio or pin('audio'),'start_ms':1000+offset,'in_ms':50,'out_ms':850}]}],
        'clip_links':[{'video_clip_id':'picture','audio_clip_id':'sound','offset_ms':offset}]}
def clips(value):return {clip['id']:clip for track in value['tracks'] for clip in track['clips']}
def assert_partition(before,after,offset=250):
    rows=clips(after);assert len(rows)==4
    assert sorted(pair['offset_ms'] for pair in after['clip_links'])==[offset,offset]
    for head,tail,expected in [('picture','picture-tail',(1000,100,500,1400,500,900)),('sound','sound-tail',(1000+offset,50,450,1400+offset,450,850))]:
        left,right=rows[head],rows[tail]
        assert (left['start_ms'],left['in_ms'],left['out_ms'],right['start_ms'],right['in_ms'],right['out_ms'])==expected
        assert left['source_snapshot']==right['source_snapshot']==clips(before)[head]['source_snapshot']

@pytest.mark.parametrize('offset',[250,-250,0])
def test_exact_partition_offsets_and_whole_dto_guard_without_schema_change(offset):
    before=normalize_studio_timeline(timeline(offset=offset));after=apply_timeline_edits(before,[OP])
    assert_partition(before,after,offset);assert after['schema_version']==2
    assert require_timeline_lock_preservation(before,after)==after
    assert set(after)==set(before)
    bad=deepcopy(after);clips(bad)['sound']['out_ms']+=1
    with pytest.raises(ValueError):require_timeline_lock_preservation(before,bad)
    bad=deepcopy(after);bad['clip_links']=[before['clip_links'][0]]
    with pytest.raises(ValueError):require_timeline_lock_preservation(before,bad)
    bad=deepcopy(after);clips(bad)['sound-tail']['start_ms']=1400;bad['clip_links'][1]['offset_ms']=0
    if offset:
        with pytest.raises(ValueError):require_timeline_lock_preservation(before,bad)

@pytest.mark.parametrize('fault',['start','end','fraction','ids','image','speed','fade','locked','mixed_batch','one_side'])
def test_unsupported_or_invalid_split_is_explicit_and_atomic(fault):
    before=normalize_studio_timeline(timeline());op=deepcopy(OP);ops=[op]
    if fault=='start':op['at_ms']=1000
    elif fault=='end':op['at_ms']=1800
    elif fault=='fraction':op['at_ms']=1400.5
    elif fault=='ids':op['new_audio_clip_id']='picture'
    elif fault=='image':clips(before)['picture']['source_snapshot']['asset_kind']='image';clips(before)['picture']['in_ms']=0
    elif fault=='speed':clips(before)['picture']['speed_num']=2
    elif fault=='fade':clips(before)['sound']['fade_in_ms']=20
    elif fault=='locked':before['tracks'][1]['locked']=True
    elif fault=='mixed_batch':ops.append({'op':'caption.insert','caption':{'start_ms':0,'end_ms':100,'text':'no partial'}})
    else:ops=[{'op':'clip.split','clip_id':'picture','at_ms':1400,'new_clip_id':'picture-tail'}]
    unchanged=deepcopy(before)
    with pytest.raises(ValueError):apply_timeline_edits(before,ops)
    assert before==unchanged

@pytest.fixture
def saved_pair(rig,tmp_path):
    e=rig;e.service.activate(e.nid,e.scope,e.actor)
    e.video=import_asset(e,data=cpu_video(tmp_path/'synthetic.mp4'),kind='video',filename='synthetic.mp4')
    e.audio=import_asset(e,data=audible_wav(),kind='audio',filename='synthetic.wav')
    e.production=production(e)
    e.saved=e.production.timeline_save(e.nid,e.scope,e.actor,None,{'expected_version':0,'title':'Synthetic persisted linked pair','timeline':timeline(source(e.video),source(e.audio))},lambda:None)
    return e
def edit(e,row,ops,key):return e.production.timeline_edit(e.nid,e.scope,e.actor,row['id'],edit_body(row,ops,key),lambda:None)
def files(e):return {str(p.relative_to(e.root)):p.read_bytes() for p in e.root.rglob('*.json')}

def test_file_split_same_request_reopen_and_two_relations_still_work(saved_pair):
    e=saved_pair;body=edit_body(e.saved,[OP],'linked-split-once')
    made=e.production.timeline_edit(e.nid,e.scope,e.actor,e.saved['id'],body,lambda:None)
    assert_partition(e.saved['timeline'],made['timeline']);assert made['version']==2
    before=files(e);assert e.production.timeline_edit(e.nid,e.scope,e.actor,made['id'],body,lambda:None)==made;assert files(e)==before
    assert production(e,reopened(e)).timeline_get(e.nid,e.scope,e.actor,made['id'],lambda:None)==made
    with pytest.raises(ValueError):edit(e,made,[OP],'second-click-new-request')
    assert files(e)==before
    moved=edit(e,made,[{'op':'clip.move','clip_id':'sound-tail','track_id':'voice','start_ms':1750}],'move-tail-after-split')
    assert clips(moved['timeline'])['picture-tail']['start_ms']==1500
    assert clips(moved['timeline'])['picture']['start_ms']==1000 and clips(moved['timeline'])['sound']['start_ms']==1250

def test_file_original_cas_save_accepts_exact_partition_and_rejects_forgery(saved_pair):
    e=saved_pair;after=split_linked_pair(e.saved['timeline'],'picture','sound',1400,'picture-tail','sound-tail')
    bad=deepcopy(after);clips(bad)['sound']['out_ms']+=1;before=files(e)
    with pytest.raises(ValueError):e.production.timeline_save(e.nid,e.scope,e.actor,e.saved['id'],{'expected_version':1,'title':e.saved['title'],'timeline':bad},lambda:None)
    assert files(e)==before
    made=e.production.timeline_save(e.nid,e.scope,e.actor,e.saved['id'],{'expected_version':1,'title':e.saved['title'],'timeline':after},lambda:None)
    assert_partition(e.saved['timeline'],made['timeline']);assert made['version']==2
    before=files(e)
    with pytest.raises(CapabilityVersionConflict):e.production.timeline_save(e.nid,e.scope,e.actor,e.saved['id'],{'expected_version':1,'title':e.saved['title'],'timeline':after},lambda:None)
    assert files(e)==before
    assert production(e,reopened(e)).timeline_get(e.nid,e.scope,e.actor,made['id'],lambda:None)==made
    assert e.production.timeline_history(e.nid,e.scope,e.actor,made['id'],lambda:None)['items'][0]['timeline']==e.saved['timeline']

def test_file_lock_boundary_stale_source_failure_leaves_no_half_split(saved_pair):
    e=saved_pair;before=files(e)
    for op in ({**OP,'at_ms':1000},{**OP,'new_video_clip_id':'sound'}):
        with pytest.raises(ValueError):edit(e,e.saved,[op],'invalid-split')
        assert files(e)==before
    locked=edit(e,e.saved,[{'op':'track.update','track_id':'voice','changes':{'locked':True}}],'lock')
    before=files(e)
    with pytest.raises(ValueError,match='TRACK_LOCKED'):edit(e,locked,[OP],'locked-split')
    assert files(e)==before
    ready=edit(e,locked,[{'op':'track.update','track_id':'voice','changes':{'locked':False}}],'unlock')
    e.service.lifecycle(e.nid,e.scope,e.audio['id'],e.audio['version'],actor_id=e.actor);before=files(e)
    with pytest.raises((FileNotFoundError,ValueError)):edit(e,ready,[OP],'stale-split')
    assert files(e)==before
