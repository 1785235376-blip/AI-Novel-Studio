import pytest
from app.asset_providers import AssetProviderRegistry,AssetGenerationRequest
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
