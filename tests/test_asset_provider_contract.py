import base64

import pytest
from app.asset_providers import (
    AssetGenerationRequest,
    AssetProviderRegistry,
    Automatic1111ImageProvider,
    ComfyUIImageProvider,
)
def test_provider_registry_fails_closed():
 r=AssetProviderRegistry()
 with pytest.raises(ValueError,match='not configured'):
  r.get('missing')
def test_request_contract():
 req=AssetGenerationRequest('local','image-v1','prompt','task')
 assert req.provider_id=='local' and req.task_id=='task'

def test_runtime_registry_refreshes_after_vault_changes(monkeypatch):
 from app import dependencies
 class Vault:
  def __init__(self): self.values={}
  def has(self,provider): return provider in self.values
  def resolve(self,provider): return self.values.get(provider)
 vault=Vault(); registry=AssetProviderRegistry()
 monkeypatch.setattr(dependencies,'credential_vault',vault)
 monkeypatch.setattr(dependencies,'asset_provider_registry',registry)
 monkeypatch.setattr(dependencies,'load_asset_provider_config',lambda: {})
 assert dependencies.refresh_asset_provider('ddshub') is False
 vault.values['ddshub']='TEST_ONLY_DDSHUB_SECRET'
 assert dependencies.refresh_asset_provider('ddshub') is True
 assert registry.get('ddshub').endpoint == 'https://www.ddshub.cc/v1'
 vault.values.clear()
 assert dependencies.refresh_asset_provider('ddshub') is False
 with pytest.raises(ValueError,match='not configured'):
  registry.get('ddshub')

def test_custom_runtime_registry_uses_openai_vault_secret(monkeypatch):
 from app import dependencies
 class Vault:
  def resolve(self,provider): return 'TEST_ONLY_OPENAI_SECRET' if provider=='openai' else None
  def has(self,provider): return self.resolve(provider) is not None
 registry=AssetProviderRegistry()
 monkeypatch.setattr(dependencies,'credential_vault',Vault())
 monkeypatch.setattr(dependencies,'asset_provider_registry',registry)
 monkeypatch.setattr(dependencies,'load_asset_provider_config',lambda: {'custom':{'endpoint':'https://custom.test/v1'}})
 assert dependencies.refresh_asset_provider('custom') is True
 assert registry.get('custom').endpoint == 'https://custom.test/v1'

def test_custom_runtime_registry_uses_its_own_vault_secret(monkeypatch):
 from app import dependencies
 class Vault:
  def resolve(self,provider): return 'TEST_ONLY_CUSTOM_SECRET' if provider=='studio_cloud' else None
  def has(self,provider): return self.resolve(provider) is not None
 registry=AssetProviderRegistry()
 monkeypatch.setattr(dependencies,'credential_vault',Vault())
 monkeypatch.setattr(dependencies,'asset_provider_registry',registry)
 monkeypatch.setattr(dependencies,'load_asset_provider_config',lambda: {'studio_cloud':{'endpoint':'https://custom.test/v1','api_style':'openai','requires_credential':True}})
 assert dependencies.refresh_asset_provider('studio_cloud') is True
 assert registry.get('studio_cloud').api_key == 'TEST_ONLY_CUSTOM_SECRET'

class _Response:
 def __init__(self,data=None,content=b'',status_code=200): self._data=data or {};self.content=content;self.status_code=status_code
 def json(self): return self._data
 def raise_for_status(self): return None

def test_automatic1111_adapter_returns_importable_data_uri():
 class Transport:
  def post(self,url,**kwargs):
   assert url.endswith('/sdapi/v1/txt2img')
   assert kwargs['json']['override_settings']['sd_model_checkpoint']=='quality.safetensors'
   return _Response({'images':['data:image/png;base64,QUJD']})
 provider=Automatic1111ImageProvider(Transport(),'http://127.0.0.1:7860')
 result=provider.generate(AssetGenerationRequest('automatic1111','quality.safetensors','雨夜街道','task'))
 assert result.asset_uri=='data:image/png;base64,QUJD'

def test_comfyui_adapter_submits_workflow_and_fetches_generated_image(monkeypatch):
 class Transport:
  def post(self,url,**kwargs):
   assert url.endswith('/prompt')
   assert kwargs['json']['prompt']['4']['inputs']['ckpt_name']=='quality.safetensors'
   return _Response({'prompt_id':'prompt-1'})
  def get(self,url,**kwargs):
   if '/history/' in url:return _Response({'prompt-1':{'outputs':{'9':{'images':[{'filename':'out.png','type':'output'}]}}}})
   assert url.endswith('/view');return _Response(content=b'PNG')
 monkeypatch.setattr('app.asset_providers.time.sleep',lambda _seconds:None)
 provider=ComfyUIImageProvider(Transport(),'http://127.0.0.1:8188')
 result=provider.generate(AssetGenerationRequest('comfyui','quality.safetensors','电影感人物','task'))
 assert result.asset_uri=='data:image/png;base64,'+base64.b64encode(b'PNG').decode('ascii')
