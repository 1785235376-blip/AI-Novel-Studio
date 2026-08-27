from app.asset_providers import OpenAICompatibleImageProvider,AssetGenerationRequest,build_openai_compatible_from_vault
class Response:
 def raise_for_status(self): pass
 def json(self): return {'data':[{'url':'https://cdn.test/a.png'}]}
class Transport:
 def post(self,*args,**kwargs): self.args=args; self.kwargs=kwargs; return Response()
def test_openai_compatible_adapter():
 t=Transport(); p=OpenAICompatibleImageProvider(t,'secret','https://api.test'); result=p.generate(AssetGenerationRequest('openai','image-1','a prompt','task'))
 assert result.asset_uri.endswith('.png'); assert t.kwargs['json']['model']=='image-1'; assert t.kwargs['headers']['Authorization']=='Bearer secret'; assert t.kwargs['timeout']==180
def test_vault_missing_credential_fails_closed():
 class Vault:
  def resolve(self,provider): return None
 import pytest
 with pytest.raises(ValueError,match='not configured'): build_openai_compatible_from_vault(Transport(),'openai','https://api.test',Vault())
def test_openai_compatible_image_edit_uses_multiple_references():
 t=Transport();p=OpenAICompatibleImageProvider(t,'secret','https://api.test');result=p.edit(AssetGenerationRequest('ddshub','gpt-image-2','keep the character','task'),['https://cdn.test/a.png','data:image/png;base64,YQ=='],size='1536x1024',quality='high',output_format='png')
 assert result.asset_uri.endswith('.png');assert t.args[0]=='https://api.test/images/edits';assert t.kwargs['json']['images']==[{'image_url':'https://cdn.test/a.png'},{'image_url':'data:image/png;base64,YQ=='}];assert t.kwargs['json']['quality']=='high';assert t.kwargs['timeout']==180
