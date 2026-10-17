"""Listing diagnostics never admit modified immutable bytes or alter action checks."""
from copy import deepcopy
import hashlib
import pytest
from app.services.audiobook_service import AudiobookError
from test_v2_studio_audio_listing import audio,save_rows,listed
pytestmark=pytest.mark.file_backend_only

def persisted(e):
    return {str(p.relative_to(e.owner.store.root)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in e.owner.store.root.rglob('*.json') if p.is_file()}

@pytest.mark.parametrize('change',['prompt','rights','source'])
def test_valid_shape_tampering_is_still_rejected_without_writing_storage(audio,change):
    row=deepcopy(audio.row)
    if change=='prompt':row['_studio_body']['prompt']='Another valid bounded prompt'
    elif change=='rights':row['context']['rights']['license_note']='A different bounded license'
    else:
        source={'id':'changed-source','version':1,'digest':'d'*64,'kind':'CREATIVE_DOCUMENT'}
        row['_studio_body']['source_snapshots']=[source]
        row['context']['sources']=[deepcopy(source)]
    save_rows(audio,[row]);before=persisted(audio)
    for operation in (lambda:listed(audio),lambda:audio.owner.get(audio.nid,row['id'],audio.context,lambda:None)):
        with pytest.raises(AudiobookError) as caught:operation()
        assert (caught.value.code,caught.value.status)==('STUDIO_AUDIO_JOB_BINDING_CHANGED',409)
        assert persisted(audio)==before

@pytest.mark.parametrize('change,diagnostic',[
    ('body','STUDIO_AUDIO_OPERATION_UNSUPPORTED'),('prompt','STUDIO_AUDIO_PROMPT_INVALID'),
    ('sources','STUDIO_AUDIO_SOURCE_INVALID'),('graph','CREATIVE_GRAPH_MEDIA_BINDING_INVALID')])
def test_shape_diagnostic_is_listing_only_and_original_job_access_remains_hash_first(audio,change,diagnostic):
    row=deepcopy(audio.row)
    if change=='body':row['_studio_body']={}
    elif change=='prompt':row['_studio_body']['prompt']='x'*16001
    elif change=='sources':row['_studio_body']['source_snapshots']=[{}]*9
    else:row['context']['graph_binding']=None
    save_rows(audio,[row]);before=persisted(audio)
    with pytest.raises((AudiobookError,ValueError)) as caught:listed(audio)
    assert getattr(caught.value,'code',str(caught.value))==diagnostic
    with pytest.raises(AudiobookError) as caught:audio.owner.get(audio.nid,row['id'],audio.context,lambda:None)
    assert (caught.value.code,caught.value.status)==('STUDIO_AUDIO_JOB_BINDING_CHANGED',409)
    assert persisted(audio)==before
