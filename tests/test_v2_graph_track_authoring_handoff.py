from copy import deepcopy
import pytest
from test_v2_timeline_slip_delete_handoff import edit_env,rig,asset_pins
from app.services.studio_timeline_edit import apply_timeline_edits
pytestmark=[pytest.mark.file_backend_only,pytest.mark.parametrize('rig',['file'],indirect=True)]


def test_original_track_operation_order_save_and_fresh_file_reopen(edit_env):
    e=edit_env;before=e.save(e.timeline);pins=asset_pins(e)
    operations=[{'op':'track.update','track_id':'audio','changes':{'muted':True,'gain_db':-6,'role':'MUSIC'}},
                {'op':'track.update','track_id':'audio','changes':{'muted':False,'gain_db':-12,'role':'EFFECTS'}}]
    candidate=apply_timeline_edits(before['timeline'],operations)
    assert next(t for t in candidate['tracks'] if t['id']=='audio')['gain_db']==-12
    assert next(t for t in apply_timeline_edits(before['timeline'],list(reversed(operations)))['tracks'] if t['id']=='audio')['gain_db']==-6
    saved=e.save(candidate,before);reopened=e.get(saved,True)
    assert reopened['timeline']==candidate and asset_pins(e)==pins
    locked=deepcopy(candidate);next(t for t in locked['tracks'] if t['id']=='audio')['locked']=True
    with pytest.raises(ValueError,match='STUDIO_TIMELINE_TRACK_LOCKED'):apply_timeline_edits(locked,operations)
    assert e.get(saved,True)['timeline']==candidate
