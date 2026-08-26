from __future__ import annotations
import os
from .config import settings
from .providers import MockProvider,OllamaProvider,OpenAICompatibleProvider
from .router import ModelRouter,Route
from .model_runtime import (
    GenerationRuntime,
    LegacyTextProviderAdapter,
    ModelDescriptor,
    ModelRegistry,
    Modality,
    ProviderDescriptor,
    ProviderRegistry,
)
from .openai_compatible import CompatibleProviderConfig,OpenAICompatibleTextProvider

class Runtime:
    def __init__(self):
        self.providers={"ollama":OllamaProvider(settings.ollama_url),"mock":MockProvider(settings.mock_delay_ms,settings.mock_failure)}
        configs={"openai":("https://api.openai.com/v1","OPENAI_API_KEY"),"deepseek":("https://api.deepseek.com/v1","DEEPSEEK_API_KEY"),"openrouter":("https://openrouter.ai/api/v1","OPENROUTER_API_KEY")}
        for name,(url,key) in configs.items(): self.providers[name]=OpenAICompatibleProvider(name,url,key)
        self.provider_registry=ProviderRegistry();self.model_registry=ModelRegistry();self.generation_runtime=GenerationRuntime(self.provider_registry,self.model_registry)
        self._sync_model("mock","mock-writer",display_name="内置测试写作模型",context_window=8192)
        deepseek=OpenAICompatibleTextProvider(CompatibleProviderConfig("deepseek",os.getenv("DEEPSEEK_BASE_URL","https://api.deepseek.com/v1"),"DEEPSEEK_API_KEY"))
        from .credential_vault import credential_vault
        configured=settings.mock_provider or credential_vault.has("deepseek") or bool(os.getenv("DEEPSEEK_API_KEY"))
        deepseek_provider=LegacyTextProviderAdapter("deepseek",self.providers["mock"]) if settings.mock_provider else deepseek
        self.provider_registry.register(ProviderDescriptor("deepseek","DeepSeek","remote",frozenset({Modality.TEXT}),configured,configured,"available" if configured else "not_configured"),deepseek_provider,replace=True)
        for model_id,display_name in (("deepseek-chat","DeepSeek Chat"),("deepseek-reasoner","DeepSeek Reasoner")):
            self.model_registry.register(ModelDescriptor(model_id,"deepseek",display_name,Modality.TEXT,frozenset({"generate","stream"}),streaming=True,enabled=True),replace=True)
    def provider_status(self)->dict:
        result={}
        for name,p in self.providers.items():
            if name == "deepseek":
                from .credential_vault import credential_vault
                configured = credential_vault.has("deepseek") or bool(os.getenv("DEEPSEEK_API_KEY"))
            else:
                configured=name in {"ollama","mock"} or bool(os.getenv(getattr(p,"api_key_env","")))
            available=p.health_check() if configured else False
            item={"available":available,"configured":configured,"kind":"local" if name in {"ollama","mock"} else "cloud"}
            if name=="ollama": item["models"]=p.list_models()
            result[name]=item
            if name == "deepseek":
                current = next((d for d in self.provider_registry.descriptors() if d.provider_id == name), None)
                if current is not None:
                    self.provider_registry.register(ProviderDescriptor(
                        current.provider_id, current.display_name, current.provider_type,
                        current.supported_modalities, configured, available,
                        "available" if available else ("not_configured" if not configured else "unavailable")
                    ), getattr(self.provider_registry, "_providers")[name], replace=True)
        result["anthropic"]={"available":False,"configured":bool(os.getenv("ANTHROPIC_API_KEY")),"kind":"cloud","status":"adapter_not_implemented"}
        result["gemini"]={"available":False,"configured":bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),"kind":"cloud","status":"adapter_not_implemented"}
        return result
    def models(self)->list[dict]:
        models=[]
        for m in self.providers["ollama"].list_models(): models.append({"name":m["name"],"provider":"ollama","context_window":None,"capabilities":["generate","stream"],"local":True,"cloud":False,"available":True})
        models.append({"name":"mock-writer","provider":"mock","context_window":8192,"capabilities":["generate","stream","test"],"local":True,"cloud":False,"available":self.providers["mock"].health_check()})
        return models
    def text_models(self)->list[dict]:
        providers={item.provider_id:item for item in self.provider_registry.descriptors()}
        return [
            {"provider_id":model.provider_id,"model_id":model.model_id,"display_name":model.display_name,"available":bool(provider and provider.configured and provider.available)}
            for model in self.model_registry.descriptors()
            if model.modality is Modality.TEXT and model.enabled and model.provider_id!="mock"
            for provider in (providers.get(model.provider_id),)
        ]
    def is_remote_text_provider(self,provider_id:str|None)->bool:
        if not provider_id:return False
        return any(item.provider_id==provider_id and item.provider_type=="remote" for item in self.provider_registry.descriptors())
    def router(self,profile:str,role:str)->ModelRouter:
        local="mock" if settings.mock_provider else "ollama"; local_model="mock-writer" if local=="mock" else settings.local_model
        cloud=os.getenv(f"CLOUD_{role.upper()}_PROVIDER") or os.getenv("DEFAULT_CLOUD_PROVIDER")
        cloud_model=os.getenv(f"CLOUD_{role.upper()}_MODEL") or ""
        routes=[]
        if profile!="LOCAL_ONLY" and cloud: routes.append(Route(cloud,cloud_model))
        routes.append(Route(local,local_model))
        return ModelRouter(self.providers,{role:routes})
    def _sync_model(self,provider_id:str,model_id:str,*,display_name:str|None=None,context_window:int|None=None,configured_override:bool|None=None):
        provider=self.providers.get(provider_id)
        if provider is None:return
        configured=configured_override if configured_override is not None else (provider_id in {"ollama","mock"} or bool(os.getenv(getattr(provider,"api_key_env",""))))
        health_check=getattr(provider,"health_check",None)
        available=(health_check() if callable(health_check) else True) if configured else False
        self.provider_registry.register(ProviderDescriptor(provider_id,provider_id.title(),"development" if provider_id=="mock" else ("local" if provider_id=="ollama" else "cloud"),frozenset({Modality.TEXT}),configured,available),LegacyTextProviderAdapter(provider_id,provider),replace=True)
        self.model_registry.register(ModelDescriptor(model_id,provider_id,display_name or model_id,Modality.TEXT,frozenset({"generate","stream"}),context_window,streaming=True,enabled=True),replace=True)
    def prepare_text_route(self,provider_id:str,model_id:str,provider=None):
        if self.provider_registry.is_configured(provider_id):return self.generation_runtime.text_node
        if provider is not None:self.providers[provider_id]=provider
        self._sync_model(provider_id,model_id,configured_override=True if provider is not None else None)
        return self.generation_runtime.text_node
runtime=Runtime()
