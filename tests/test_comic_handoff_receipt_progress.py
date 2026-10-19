"""Reusable receipt-integrity probes; original source/tests remain untouched.

Run against a fixed archive with its tests/ on PYTHONPATH. Set REVIEW_COMMIT and
REVIEW_EVIDENCE_DIR for a future repair without replacing the original evidence.
"""
import copy,json,os
from pathlib import Path
import pytest
from test_v2_independent_workspace import rig
from test_comic_timeline_handoff import handoff,page
from test_comic_timeline_handoff_recovery import body,confirm,status,timelines
from app.experimental.comic_timeline_handoff import COLLECTION

def output(name,data):
    root=Path(os.environ.get('REVIEW_EVIDENCE_DIR',str(Path(os.environ['NOVEL_DATA_PATH']).parent / 'receipt-integrity-probes')))
    root.mkdir(parents=True,exist_ok=True)
    data['commit']=os.environ.get('REVIEW_COMMIT','working-receipt-repair')
    (root/(name+'.json')).write_text(json.dumps(data,indent=2),encoding='utf8')

@pytest.mark.parametrize('case',[
    'completed_incarnation','completed_missing_incarnation','completed_counter',
    'partial_counter','completed_state_rewind','cancelled_state_rewind'])
def test_corrupt_identity_or_state_cannot_replay_effects(rig,handoff,monkeypatch,case):
    if case in {'partial_counter','cancelled_state_rewind'}:
        value=body(rig,handoff,[page(rig,handoff),page(rig,handoff,shift=10)])
        original=rig.assets.create;calls=0
        def fail_second(*args,**kwargs):
            nonlocal calls
            calls+=1
            if calls==2:raise OSError('retain first exact native Asset for review probe')
            return original(*args,**kwargs)
        monkeypatch.setattr(rig.assets,'create',fail_second)
        with pytest.raises(OSError):confirm(rig,handoff,value)
        monkeypatch.setattr(rig.assets,'create',original)
        first=status(rig,handoff)
        assert first['version']==2 and [s['state'] for s in first['steps']]==['READY','PENDING']
        if case=='cancelled_state_rewind':
            first=handoff.cancel(rig.nid,rig.scope,rig.actor,'create',2)
            assert first['status']=='CANCELLED' and first['version']==3
    else:
        value=body(rig,handoff,[page(rig,handoff)])
        first=confirm(rig,handoff,value)
        assert first['status']=='DRAFT_CREATED' and first['version']==3
    before={'assets':len(list(rig.assets.root.glob('*.bin'))),'timelines':len(timelines(rig))}
    with rig.raw_store.transaction(rig.nid,rig.scope) as state:
        row=state['collections'][COLLECTION][first['id']]
        if case=='completed_incarnation':row['incarnation']='file:11111111-1111-4111-8111-111111111111'
        elif case=='completed_missing_incarnation':del row['incarnation']
        elif case=='completed_counter':row['version']=2
        elif case=='partial_counter':row['version']=1
        elif case=='completed_state_rewind':row.update(status='PLANNED',timeline_snapshot=None)
        else:row['status']='PLANNED'
    evidence={'case':case,'before':before,'original_receipt_id':first['id'],'before_corruption_status':first['status'],'before_corruption_version':first['version']}
    try:
        if case=='completed_counter':result=status(rig,handoff)
        elif case=='partial_counter':result=handoff.resume(rig.nid,rig.scope,rig.actor,'create',1)
        elif case in {'completed_state_rewind','cancelled_state_rewind'}:result=handoff.resume(rig.nid,rig.scope,rig.actor,'create',first['version'])
        else:result=confirm(rig,handoff,value)
    except (ValueError,FileNotFoundError) as error:evidence.update(rejected=True,error=str(error))
    else:
        evidence.update(rejected=False,returned_status=result['status'],returned_version=result['version'],returned_receipt_id=result['id'])
    evidence['after']={'assets':len(list(rig.assets.root.glob('*.bin'))),'timelines':len(timelines(rig))}
    output(case,evidence)
    assert evidence['rejected'],'Corrupt receipt was accepted: '+json.dumps(evidence)
    assert evidence['after']==before,'Rejection must retain exact existing effects without adding new ones'

def test_real_new_incarnation_reuses_key_without_adopting_or_rewriting_history(rig,handoff):
    old=confirm(rig,handoff,body(rig,handoff,[page(rig,handoff)]))
    before=copy.deepcopy(rig.raw_store.read(rig.nid,rig.scope))
    old_receipt=before['collections'][COLLECTION][old['id']]
    old_ids=[s['asset_id'] for s in old['steps']]
    old_bytes={aid:rig.assets._bin_path(aid).read_bytes() for aid in old_ids}
    rig.novels.delete(rig.nid);rig.create_project('Real recreated owner',nid=rig.nid)
    rig.service.activate(rig.nid,rig.scope,rig.actor)
    new=confirm(rig,handoff,body(rig,handoff,[page(rig,handoff)]))
    after=rig.raw_store.read(rig.nid,rig.scope)
    assert new['preview']['incarnation']!=old['preview']['incarnation']
    assert new['id']!=old['id'] and new['timeline']['id']!=old['timeline']['id']
    assert {s['asset_id'] for s in new['steps']}.isdisjoint(old_ids)
    assert after['collections'][COLLECTION][old['id']]==old_receipt
    assert all(rig.assets._bin_path(aid).read_bytes()==raw for aid,raw in old_bytes.items())
    with handoff.workspace._asset_scope(rig.nid,rig.scope):
        for aid in old_ids:
            with pytest.raises(FileNotFoundError):rig.assets.get(aid)
    output('legal_historical_incarnation',{'passed':True,'same_request_id':new['request_id']==old['request_id'],'old_receipt_preserved':True,
      'old_asset_bytes_preserved':True,'old_assets_denied_in_new_binding':True,'new_ids_allocated':True,
      'old_incarnation':old['preview']['incarnation'],'new_incarnation':new['preview']['incarnation']})


def test_completed_creation_proof_blocks_rewind_even_with_adjusted_counter(rig,handoff):
    value=body(rig,handoff,[page(rig,handoff)])
    first=confirm(rig,handoff,value)
    before={'assets':len(list(rig.assets.root.glob('*.bin'))),'timelines':len(timelines(rig))}
    with rig.raw_store.transaction(rig.nid,rig.scope) as state:
        row=state['collections'][COLLECTION][first['id']]
        row.update(status='PLANNED',version=2,timeline_snapshot=None)
    with pytest.raises(ValueError,match='RECEIPT_CORRUPT'):
        handoff.resume(rig.nid,rig.scope,rig.actor,'create',2)
    assert {'assets':len(list(rig.assets.root.glob('*.bin'))),'timelines':len(timelines(rig))}==before


def test_ready_steps_must_be_a_reachable_ordered_prefix(rig,handoff,monkeypatch):
    value=body(rig,handoff,[page(rig,handoff),page(rig,handoff,shift=10)])
    original=rig.assets.create
    def fail(*args,**kwargs):raise OSError('intent only')
    monkeypatch.setattr(rig.assets,'create',fail)
    with pytest.raises(OSError):confirm(rig,handoff,value)
    monkeypatch.setattr(rig.assets,'create',original)
    first=status(rig,handoff)
    with rig.raw_store.transaction(rig.nid,rig.scope) as state:
        row=state['collections'][COLLECTION][first['id']]
        row['steps'][1].update(state='READY',asset_version=1)
        row['version']=2
    with pytest.raises(ValueError,match='RECEIPT_CORRUPT'):
        handoff.resume(rig.nid,rig.scope,rig.actor,'create',2)
    assert not list(rig.assets.root.glob('*.bin')) and not timelines(rig)


@pytest.mark.parametrize('remove_collection',[False,True])
def test_missing_journal_with_retained_creation_proof_cannot_be_a_new_request(rig,handoff,remove_collection):
    value=body(rig,handoff,[page(rig,handoff)])
    first=confirm(rig,handoff,value)
    before={'assets':len(list(rig.assets.root.glob('*.bin'))),'timelines':len(timelines(rig))}
    with rig.raw_store.transaction(rig.nid,rig.scope) as state:
        if remove_collection:del state['collections'][COLLECTION]
        else:del state['collections'][COLLECTION][first['id']]
    with pytest.raises(ValueError,match='RECEIPT_CORRUPT'):confirm(rig,handoff,value)
    assert {'assets':len(list(rig.assets.root.glob('*.bin'))),'timelines':len(timelines(rig))}==before
