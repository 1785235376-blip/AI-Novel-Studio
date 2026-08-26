from app.asset_providers import OpenAICompatibleImageProvider,AssetGenerationRequest,build_openai_compatible_from_vault
class Response:
 def raise_for_status(self): pass
 def json(self): return {'data':[{'url':'https://cdn.test/a.png'}]}
class Transport:
 def post(self,*args,**kwargs): self.args=args; self.kwargs=kwargs; return Response()
def test_openai_compatible_adapter():
 t=Transport(); p=OpenAICompatibleImageProvider(t,'secret','https://api.test'); result=p.generate(AssetGenerationRequest('openai','image-1','a prompt','task'))
 assert result.asset_uri.endswith('.png'); assert t.kwargs['json']['model']=='image-1'; assert t.kwargs['headers']['Authorization']=='Bearer secret'
def test_vault_missing_credential_fails_closed():
 class Vault:
  def resolve(self,provider): return None
 import pytest
 with pytest.raises(ValueError,match='not configured'): build_openai_compatible_from_vault(Transport(),'openai','https://api.test',Vault())
