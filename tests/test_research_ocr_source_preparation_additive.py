"""Actual File/PG Research source reads, no OCR inference or job activation."""
import base64
import copy
import io

import pytest
from PIL import Image
from app.experimental.research_library import ResearchLibraryService
from app.experimental.research_vision import PreparedResearchOCRSource
from app.experimental.common import StaleSourceError
from test_v2_creative_project_lifecycle import rig, TITLE
from test_r4_research_library import payload


def image_payload(fmt='PNG'):
    output = io.BytesIO()
    Image.new('RGB', (24, 24), 'white').save(output, format=fmt)
    return payload(filename='fixture.' + ('jpg' if fmt == 'JPEG' else fmt.lower()),
        content_base64=base64.b64encode(output.getvalue()).decode())


def imported(e, fmt='PNG'):
    service = ResearchLibraryService(e.store, e.novels, e.chapters, historical_inspection=True)
    row = service.import_file(e.nid, e.scope, e.actor, image_payload(fmt), guard=lambda: None)
    return service, row


def prepare(e, service, row, **changes):
    args = dict(service=service, nid=e.nid, scope=e.scope, actor=e.actor,
        source_id=row['id'], source_version=row['version'], guard=lambda: None)
    args.update(changes)
    return PreparedResearchOCRSource(**args)


@pytest.mark.parametrize('fmt,media', [('PNG', 'image/png'), ('JPEG', 'image/jpeg')])
def test_capture_reads_original_bytes_without_job_or_persistence_mutation(rig, fmt, media):
    e=rig; service,row=imported(e,fmt)
    before=copy.deepcopy(e.store.read(e.nid,e.scope))
    prepared=prepare(e,service,row)
    assert prepared.read_current()==service.original(e.nid,e.scope,e.actor,row['id'])[0]
    assert prepared.binding['media_type']==media and prepared.binding['page']==1
    assert prepared.binding['project_incarnation']==service.history_identity(e.nid)
    assert prepared.binding['source_version']==1 and prepared.binding['actor_id']==e.actor
    assert e.store.read(e.nid,e.scope)==before
    assert service.vision_provider is None
    detached=prepared.binding; detached['scope']['novel_id']='another'
    assert prepared.binding['scope']==e.scope


def test_wrong_actor_and_stale_version_refuse(rig):
    e=rig; service,row=imported(e)
    with pytest.raises(FileNotFoundError):prepare(e,service,row,actor='other')
    with pytest.raises(StaleSourceError):prepare(e,service,row,source_version=2)


def test_replaced_source_invalidates_captured_snapshot(rig):
    e=rig; service,row=imported(e); prepared=prepare(e,service,row)
    service.replace_file(e.nid,e.scope,e.actor,row['id'],
        {**image_payload(), 'expected_version':1},guard=lambda:None)
    before=copy.deepcopy(e.store.read(e.nid,e.scope))
    with pytest.raises(StaleSourceError):prepared.read_current()
    assert e.store.read(e.nid,e.scope)==before


def test_same_public_project_recreation_cannot_rebind_snapshot(rig):
    e=rig; service,row=imported(e); prepared=prepare(e,service,row)
    before=copy.deepcopy(e.store.read(e.nid,e.scope))
    e.novels.delete(e.nid); assert e.novels.create({'title':TITLE})['id']==e.nid
    with pytest.raises((FileNotFoundError,StaleSourceError)):prepared.read_current()
    assert e.store.read(e.nid,e.scope)==before
    fresh=service.import_file(e.nid,e.scope,e.actor,image_payload(),guard=lambda:None)
    current=prepare(e,service,fresh)
    assert current.binding['project_incarnation']!=prepared.binding['project_incarnation']
    assert current.read_current()
    with pytest.raises((FileNotFoundError,StaleSourceError)):prepared.read_current()


def test_revoke_during_authorization_callback_is_not_returned(rig):
    e=rig; service,row=imported(e); count=0
    def guard():
        nonlocal count
        count+=1
        if count==2:
            service.transition_source(e.nid,e.scope,e.actor,row['id'],1,'revoke',guard=lambda:None)
    with pytest.raises((FileNotFoundError,StaleSourceError)):prepare(e,service,row,guard=guard)


def test_live_authorization_revocation_refuses_read(rig):
    e=rig; service,row=imported(e); revoked=False
    def guard():
        if revoked:raise PermissionError('revoked')
    prepared=prepare(e,service,row,guard=guard); revoked=True
    with pytest.raises(PermissionError):prepared.read_current()


def test_legacy_owner_without_incarnation_is_not_prepared(rig):
    e=rig; service,row=imported(e); service.historical_inspection=False
    with pytest.raises(ValueError,match='AUTHORITY'):prepare(e,service,row)


def test_non_supported_image_format_is_not_silently_converted(rig):
    e=rig; service,row=imported(e,'WEBP')
    with pytest.raises(ValueError,match='PNG_OR_JPEG'):prepare(e,service,row)


def test_tampered_bytes_fail_hash_without_repair(rig):
    e=rig; service,row=imported(e)
    with e.store.transaction(e.nid,e.scope) as state:
        state['collections']['research_sources'][row['id']]['content_base64']=base64.b64encode(b'changed').decode()
    before=copy.deepcopy(e.store.read(e.nid,e.scope))
    with pytest.raises(StaleSourceError):prepare(e,service,row)
    assert e.store.read(e.nid,e.scope)==before
