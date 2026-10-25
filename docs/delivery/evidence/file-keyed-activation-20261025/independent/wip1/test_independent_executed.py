from copy import copy, deepcopy
from types import SimpleNamespace
import pytest
from test_file_keyed_activation import keyed, memory_settings, queued, finish, files, post, replace_owner
from app.services.generation_project_binding import FIELD, ordinary_job_binding

pytestmark = pytest.mark.file_backend_only

@pytest.mark.parametrize('field,value', [('base_chapter_version',True), ('base_chapter_version',1.0)])
def test_outer_source_base_has_strict_type(keyed, field, value):
    f=keyed
    _, job=queued(f)
    row=f.persistence.get(job.id)
    row[field]=value
    with pytest.raises(ValueError): ordinary_job_binding(row)
    finish(f,job)


def test_client_cannot_stamp_private_authority(keyed):
    f=keyed
    _, job=queued(f,ordinary_project_binding={'schema_version':2,'project_incarnation':'forged'},
        _ordinary_execution_capability={'started':True},base_chapter_digest='0'*64)
    row=finish(f,job)
    assert row[FIELD]['project_incarnation']==f.incarnation
    assert row[FIELD]['base_chapter_digest']!='0'*64


def test_capability_cannot_copy_or_transfer_after_completion(keyed):
    f=keyed
    _, job=queued(f)
    cap=job._ordinary_execution_capability
    for copier in (copy,deepcopy):
        with pytest.raises(Exception): copier(cap)
    finish(f,job)
    before=deepcopy(f.persistence.get(job.id))
    with pytest.raises(Exception): f.original_run(job)
    assert f.persistence.get(job.id)==before and f.counts['provider']==1
    cold=f.reopen(); restored=cold.get(job.id)
    restored._ordinary_execution_capability=cap
    with pytest.raises(Exception): cold._run(restored)
    assert f.counts['provider']==1


@pytest.mark.parametrize('port',['provider','model_registry','node'])
def test_live_route_rotation_refuses(keyed,port):
    f=keyed
    _,job=queued(f)
    if port=='provider':
        from app.providers import MockProvider
        f.runtime.providers['mock']=MockProvider(delay_ms=0)
        f.runtime._sync_model('mock','mock-writer')
    elif port=='model_registry': f.runtime.model_registry=copy(f.runtime.model_registry)
    else: f.runtime.generation_runtime.text_node=copy(f.runtime.generation_runtime.text_node)
    before=files(f)
    f.release.set(); assert f.finished.wait(10)
    assert job.status!='COMPLETED' and f.counts['provider']==0
    assert files(f)==before


@pytest.mark.parametrize('port',['service','repository'])
def test_terminal_original_generation_port_owner_replacement(keyed,port):
    f=keyed
    target=f.persistence if port=='service' else f.bundle.generations
    original=target.save
    replaced=[]; after={}
    def wrapped(row,*args,**kwargs):
        if row.get('status')=='COMPLETED' and FIELD in row and not replaced:
            replaced.append(True); replace_owner(f); after.update(files(f))
        return original(row,*args,**kwargs)
    f.monkeypatch.setattr(target,'save',wrapped)
    _,job=queued(f)
    f.release.set(); assert f.finished.wait(10)
    assert replaced and files(f)==after and job.status!='COMPLETED'
    assert f.counts['provider']==1

