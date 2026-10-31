import pytest
from test_file_keyed_activation import keyed, memory_settings, post
pytestmark=pytest.mark.file_backend_only
@pytest.mark.parametrize('provider,model',[('not-registered','not-registered'),('mock','not-registered'),('mock','')])
def test_unknown_or_incomplete_route_is_not_legacy_fallback(keyed,provider,model):
    f=keyed
    response=post(f,provider_id=provider,model_id=model)
    assert response.status_code==409,response.text
    assert response.json()['detail']['code']=='GENERATION_WRITER_ADMISSION_UNVERIFIED'
    assert not f.bundle.generations.load_all()
    assert f.counts['worker']==f.counts['provider']==0
