from __future__ import annotations
import os
from .config import settings
from .providers import MockProvider,OllamaProvider,OpenAICompatibleProvider
from .router import ModelRouter,Route
from .model_runtime import (
    GenerationRuntime,
    LegacyTextProviderAdapter,
    ModelDescriptor,
    ModelRuntimeError,
    ModelRegistry,
    Modality,
    ProviderDescriptor,
    ProviderRegistry,
    RuntimeErrorCode,
)
from .openai_compatible import CompatibleProviderConfig,OpenAICompatibleTextProvider
from .stable_identity import ExecutionNodeIdentityStore, StableIdentityStore, canonical_identity_store_path

class Runtime:
    def __init__(self, identity_store: StableIdentityStore | None = None):
        self.providers={"ollama":OllamaProvider(settings.ollama_url),"mock":MockProvider(settings.mock_delay_ms,settings.mock_failure)}
        configs={"openai":("https://api.openai.com/v1","OPENAI_API_KEY"),"deepseek":("https://api.deepseek.com/v1","DEEPSEEK_API_KEY"),"openrouter":("https://openrouter.ai/api/v1","OPENROUTER_API_KEY")}
        for name,(url,key) in configs.items(): self.providers[name]=OpenAICompatibleProvider(name,url,key)
        identity_path = canonical_identity_store_path()
        identity_store = identity_store or StableIdentityStore(identity_path)
        self.identity_store = identity_store
        self.execution_node_identity = ExecutionNodeIdentityStore(identity_store.path)
        self.provider_registry=ProviderRegistry(identity_store);self.model_registry=ModelRegistry(identity_store);self.generation_runtime=GenerationRuntime(self.provider_registry,self.model_registry)
        self._sync_model("mock","mock-writer",display_name="内置测试写作模型",context_window=8192)
        deepseek=OpenAICompatibleTextProvider(CompatibleProviderConfig("deepseek",os.getenv("DEEPSEEK_BASE_URL","https://api.deepseek.com/v1"),"DEEPSEEK_API_KEY"))
        self._deepseek_execution_mode = "mock_standin" if settings.mock_provider and not settings.enable_packaged_runtime else "real"
        if self._deepseek_execution_mode == "mock_standin":
            configured = True
            available = self.providers["mock"].health_check()
            self._deepseek_provider_adapter = LegacyTextProviderAdapter("deepseek", self.providers["mock"])
            health_status = "mock_standin" if available else "mock_standin_unavailable"
        else:
            from .credential_vault import credential_vault
            configured = credential_vault.has("deepseek") or bool(os.getenv("DEEPSEEK_API_KEY"))
            available = configured
            self._deepseek_provider_adapter = deepseek
            health_status = "available" if available else "not_configured"
        self.provider_registry.register(ProviderDescriptor("deepseek","DeepSeek","remote",frozenset({Modality.TEXT}),configured,available,health_status),self._deepseek_provider_adapter,replace=True)
        for model_id,display_name in (("deepseek-chat","DeepSeek Chat"),("deepseek-reasoner","DeepSeek Reasoner")):
            self.model_registry.register(ModelDescriptor(model_id,"deepseek",display_name,Modality.TEXT,frozenset({"generate","stream"}),streaming=True,enabled=True),replace=True)
    def provider_status(self)->dict:
        result={}
        for name,p in self.providers.items():
            if name == "deepseek":
                if self._deepseek_execution_mode == "mock_standin":
                    configured = True
                    available = self.providers["mock"].health_check()
                    health_status = "mock_standin" if available else "mock_standin_unavailable"
                    execution_mode = "mock_standin"
                else:
                    from .credential_vault import credential_vault
                    configured = credential_vault.has("deepseek") or bool(os.getenv("DEEPSEEK_API_KEY"))
                    available = p.health_check() if configured else False
                    health_status = "available" if available else ("not_configured" if not configured else "unavailable")
                    execution_mode = "real"
            else:
                configured=name in {"ollama","mock"} or bool(os.getenv(getattr(p,"api_key_env","")))
                available=p.health_check() if configured else False
            item={"available":available,"configured":configured,"kind":"local" if name in {"ollama","mock"} else "cloud"}
            if name == "deepseek": item["execution_mode"] = execution_mode
            if name=="ollama": item["models"]=p.list_models()
            result[name]=item
            if name == "deepseek":
                current = next((d for d in self.provider_registry.descriptors() if d.provider_id == name), None)
                if current is not None:
                    self.provider_registry.register(ProviderDescriptor(
                        current.provider_id, current.display_name, current.provider_type,
                        current.supported_modalities, configured, available,
                        health_status
                    ), self._deepseek_provider_adapter, replace=True)
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
        packaged=bool(settings.enable_packaged_runtime)
        local="mock" if settings.mock_provider and not packaged else "ollama"
        local_model="mock-writer" if local=="mock" else settings.local_model
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
        # Route preparation is read-only: registration is the only identity minting path.
        identities_present = (
            self.identity_store.get("provider", provider_id) is not None
            and self.identity_store.get("model", model_id) is not None
        )
        if not identities_present or not self.provider_registry.contains(provider_id) or not self.model_registry.contains(provider_id, model_id):
            # A caller-provided adapter may be used as a non-authoritative,
            # in-memory compatibility node; it never enters the owner store.
            if provider is not None and provider_id not in self.providers:
                ephemeral_providers = ProviderRegistry()
                ephemeral_models = ModelRegistry()
                adapter = provider if hasattr(provider, "stream_text") else LegacyTextProviderAdapter(provider_id, provider)
                ephemeral_providers.register(ProviderDescriptor(provider_id, provider_id, "ephemeral", frozenset({Modality.TEXT}), True, True), adapter)
                ephemeral_models.register(ModelDescriptor(model_id, provider_id, model_id, Modality.TEXT, frozenset({"generate", "stream"}), streaming=True))
                return GenerationRuntime(ephemeral_providers, ephemeral_models).text_node
            raise ModelRuntimeError(RuntimeErrorCode.INVALID_CONFIGURATION, "模型服务或模型尚未完成注册")
        return self.generation_runtime.text_node
    def packaged_author_route_ready(self, provider_id: str) -> bool:
        """Packaged DesktopHost must not complete author text with mock or unconfigured DeepSeek."""
        if not settings.enable_packaged_runtime:
            return True
        if provider_id == "mock":
            return False
        if provider_id == "deepseek":
            from .credential_vault import credential_vault
            return credential_vault.has("deepseek") or bool(os.getenv("DEEPSEEK_API_KEY"))
        provider = self.providers.get(provider_id)
        health = getattr(provider, "health_check", None)
        return bool(health()) if callable(health) else False
runtime=Runtime()
