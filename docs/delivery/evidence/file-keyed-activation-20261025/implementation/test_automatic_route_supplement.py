"""Supplemental frozen-source original automatic route admission probes."""
from test_file_keyed_activation import keyed, memory_settings, queued, finish, post
from app.services.generation_project_binding import FIELD
from app.router import Route


def test_original_automatic_mock_route_activates(keyed):
    import app.runtime as runtime_module
    f=keyed
    f.monkeypatch.setattr(runtime_module,'settings',f.config)
    _,job=queued(f,provider_id=None,model_id=None)
    assert FIELD in f.persistence.get(job.id)
    row=finish(f,job)
    assert row['provider']=='mock' and row['model']=='mock-writer'
    assert f.counts['provider']==f.counts['adapter']==1


def test_ambiguous_original_automatic_routes_refuse_before_reservation(keyed):
    import app.runtime as runtime_module
    f=keyed
    f.monkeypatch.setattr(runtime_module,'settings',f.config)
    original=f.runtime.router
    def router(*args,**kwargs):
        result=original(*args,**kwargs)
        result.routes['writer']=[Route('mock','mock-writer'),Route('mock','mock-writer')]
        return result
    f.monkeypatch.setattr(f.runtime,'router',router)
    response=post(f,provider_id=None,model_id=None)
    assert response.status_code==409,response.text
    assert response.json()['detail']['code']=='GENERATION_WRITER_ADMISSION_UNVERIFIED'
    assert not f.store.path.exists() and not f.bundle.generations.load_all()
    assert f.counts['worker']==f.counts['provider']==0


def test_unknown_provider_refuses_before_reservation(keyed):
    f=keyed
    response=post(f,provider_id='unknown-local-looking-provider',model_id='not-registered')
    assert response.status_code==409,response.text
    assert response.json()['detail']['code']=='GENERATION_WRITER_ADMISSION_UNVERIFIED'
    assert not f.store.path.exists() and not f.bundle.generations.load_all()
    assert f.counts['worker']==f.counts['provider']==0


def test_missing_model_refuses_before_reservation(keyed):
    f=keyed
    response=post(f,provider_id='mock',model_id=None)
    assert response.status_code==409,response.text
    assert response.json()['detail']['code']=='GENERATION_WRITER_ADMISSION_UNVERIFIED'
    assert not f.store.path.exists() and not f.bundle.generations.load_all()
    assert f.counts['worker']==f.counts['provider']==0
