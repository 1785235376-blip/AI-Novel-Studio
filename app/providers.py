from __future__ import annotations
import json, os, time, threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

@dataclass
class Generation:
    text: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    metadata: dict = field(default_factory=dict)

class ProviderError(RuntimeError): pass

class LLMProvider(ABC):
    name: str
    @abstractmethod
    def generate(self, prompt: str, model: str, **kwargs) -> Generation: ...
    def stream(self, prompt: str, model: str, **kwargs): yield self.generate(prompt, model, **kwargs).text
    @abstractmethod
    def health_check(self) -> bool: ...
    def get_model_info(self, model: str) -> dict: return {"provider": self.name, "model": model}
    def estimate_usage(self, prompt: str, output: str) -> dict: return {"input_tokens":len(prompt)//3, "output_tokens":len(output)//3}

class OllamaProvider(LLMProvider):
    name = "ollama"
    supports_stream_usage = True
    supports_dispatch_guard = True
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._metadata_client = None
        self._model_proofs = {}
        self._model_proof_lock = threading.Lock()

    def _local_client(self):
        if self._metadata_client is None:
            from .model_center.discovery_probes import LocalProbeClient
            self._metadata_client = LocalProbeClient()
        return self._metadata_client

    def local_model_metadata(self, model: str) -> dict:
        from .model_center.discovery_probes import read_ollama_local_metadata
        try: return read_ollama_local_metadata(self._local_client(), self.base_url, model, self.list_models)
        except ValueError: return {"source_locality":"NOT_VERIFIED", "reported_capabilities":[], "locality_fingerprint":None}

    def _local_dispatch(self, model, dispatch_guard=None, cancellation=None):
        from .model_center.discovery_types import local_endpoint
        evidence = self.local_model_metadata(model)
        proof = evidence.get("locality_fingerprint")
        with self._model_proof_lock:
            previous = self._model_proofs.get(model)
            if (evidence.get("source_locality") != "LOCAL_VERIFIED" or "completion" not in evidence.get("reported_capabilities", [])
                    or not proof or (previous is not None and previous != proof)):
                raise ProviderError("OLLAMA_LOCAL_MODEL_REVALIDATION_REQUIRED")
            self._model_proofs[model] = proof
        if dispatch_guard is not None: dispatch_guard()
        if cancellation is not None and cancellation.is_set(): raise ProviderError("OLLAMA_CANCELLED")
        return local_endpoint(self.base_url), self._local_client()

    def generate(self, prompt: str, model: str, **kwargs) -> Generation:
        from .model_center.discovery_probes import LocalProbeClient, ollama_token_counts
        dispatch_guard, cancellation = kwargs.pop("dispatch_guard", None), kwargs.pop("cancellation", None)
        timeout = kwargs.pop("timeout", 120)
        endpoint, metadata_client = self._local_dispatch(model, dispatch_guard, cancellation)
        started=time.monotonic()
        client=LocalProbeClient(timeout=timeout);client.open=metadata_client.open
        try: data=client.json(endpoint, "/api/generate", body={"model":model,"prompt":prompt,"stream":False,"options":kwargs})
        except Exception as exc: raise ProviderError(f"Ollama unavailable: {type(exc).__name__}") from exc
        if not isinstance(data, dict) or data.get("done") is not True or data.get("error"):
            raise ProviderError("Ollama generation ended without completion")
        input_count,output_count=ollama_token_counts(data)
        known=input_count is not None and output_count is not None
        return Generation(data.get("response",""),self.name,model,input_count or 0,output_count or 0,int((time.monotonic()-started)*1000),metadata={"usage_known":known})
    def health_check(self) -> bool:
        try: self._local_client().json(self.base_url,"/api/tags"); return True
        except Exception: return False
    def list_models(self, *, read_json=None, include_details: bool = False, strict: bool = False) -> list[dict]:
        """Enumerate installed models; discovery injects its bounded local-only reader.

        The no-argument legacy response and failure behavior remain unchanged.
        The injected reader receives a relative metadata path, never prompts or
        credentials. In strict mode probe failures remain visible to discovery.
        """
        try:
            if read_json is None:
                data=self._local_client().json(self.base_url,"/api/tags")
            else:
                data=read_json("/api/tags")
            if not isinstance(data, dict) or not isinstance(data.get("models", None if strict else []), list):
                raise ValueError("LOCAL_AI_INVALID_RESPONSE")
            models=data.get("models", [])
            if read_json is not None:
                models=models[:512]
            result=[]
            for model in models:
                if not isinstance(model, dict):
                    continue
                item={"name":model.get("name"),"size":model.get("size"),"modified_at":model.get("modified_at")}
                if include_details:
                    item.update({key:model[key] for key in ("digest", "details", "remote_model", "remote_host") if key in model})
                result.append(item)
            return result
        except Exception:
            if strict:
                raise
            return []
    def stream(self,prompt:str,model:str,**kwargs):
        usage_callback=kwargs.pop("usage_callback",None)
        dispatch_guard,cancellation=kwargs.pop("dispatch_guard",None),kwargs.pop("cancellation",None)
        timeout=kwargs.pop("timeout",120)
        endpoint,client=self._local_dispatch(model,dispatch_guard,cancellation)
        if "max_tokens" in kwargs:kwargs["num_predict"]=kwargs.pop("max_tokens")
        payload=json.dumps({"model":model,"prompt":prompt,"stream":True,"options":kwargs}).encode()
        done=False
        try:
            with client.open(Request(endpoint+"/api/generate",payload,{"Content-Type":"application/json"}),timeout=timeout) as response:
                for line in response:
                    if cancellation is not None and cancellation.is_set():raise ProviderError("OLLAMA_CANCELLED")
                    if not line:continue
                    item=json.loads(line)
                    if item.get("error"):raise ProviderError("Ollama generation failed")
                    chunk=item.get("response","")
                    if chunk:yield chunk
                    if item.get("done") is True:
                        done=True
                        if usage_callback:
                            from .model_center.discovery_probes import ollama_token_counts
                            inputs,outputs=ollama_token_counts(item)
                            usage_callback({"input_tokens":inputs,"output_tokens":outputs})
                        break
                if not done:raise ProviderError("Ollama stream ended without completion")
        except ProviderError:raise
        except Exception as exc:raise ProviderError(f"Ollama unavailable: {type(exc).__name__}") from exc

class OpenAICompatibleProvider(LLMProvider):
    def __init__(self,name:str,base_url:str,api_key_env:str): self.name=name; self.base_url=base_url.rstrip("/"); self.api_key_env=api_key_env
    def _key(self)->str:
        packaged = os.getenv('PACKAGED_WINDOWS_MODE','').lower() in {'1','true','yes','on'}
        try:
            from .config import settings
            packaged = packaged or settings.enable_packaged_runtime
        except Exception:
            pass
        from .credential_vault import credential_vault
        if credential_vault.supports_provider(self.name):
            stored=credential_vault.resolve(self.name)
            if stored:return stored
        return "" if packaged else os.getenv(self.api_key_env,"")
    def generate(self,prompt:str,model:str,**kwargs)->Generation:
        key=self._key(); 
        if not key: raise ProviderError(f"{self.name} API key missing")
        started=time.monotonic(); body=json.dumps({"model":model,"messages":[{"role":"user","content":prompt}]}).encode()
        retries = max(0, min(int(kwargs.get("retries", 0)), 5))
        backoff = max(0.0, min(float(kwargs.get("backoff", 0.35)), 10.0))
        request = Request(self.base_url+"/chat/completions",body,{"Content-Type":"application/json","Authorization":"Bearer "+key})
        for attempt in range(retries + 1):
            try:
                with urlopen(request,timeout=kwargs.get("timeout",120)) as r: data=json.load(r)
                break
            except HTTPError as exc:
                transient = exc.code == 429 or 500 <= exc.code < 600
                if not transient or attempt >= retries:
                    raise ProviderError(f"{self.name} request failed: HTTP {exc.code}") from exc
            except (URLError, TimeoutError) as exc:
                if attempt >= retries:
                    raise ProviderError(f"{self.name} unavailable: {type(exc).__name__}") from exc
            if backoff: time.sleep(backoff * (2 ** attempt))
        usage=data.get("usage",{}); text=data["choices"][0]["message"]["content"]
        return Generation(text,self.name,model,usage.get("prompt_tokens",0),usage.get("completion_tokens",0),int((time.monotonic()-started)*1000),metadata={"usage_known": bool(usage)})
    def health_check(self)->bool: return bool(self._key())
    def stream(self, prompt: str, model: str, **kwargs):
        key = self._key()
        if not key: raise ProviderError(f"{self.name} API key missing")
        payload = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}], "stream": True}).encode()
        retries = max(0, min(int(kwargs.get("retries", 0)), 5))
        emitted = False
        completed = False
        for attempt in range(retries + 1):
            try:
                request = Request(self.base_url + "/chat/completions", payload, {"Content-Type": "application/json", "Authorization": "Bearer " + key, "Accept": "text/event-stream"})
                with urlopen(request, timeout=kwargs.get("timeout", 120)) as response:
                    for raw in response:
                        line = raw.decode("utf-8", "ignore").strip()
                        if not line.startswith("data:"):continue
                        if line[5:].strip() == "[DONE]":
                            completed=True
                            break
                        item = json.loads(line[5:].strip())
                        if any(choice.get("finish_reason") for choice in item.get("choices",[])):completed=True
                        delta = item.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        if delta:
                            emitted = True
                            yield delta
                if not completed:raise ProviderError(f"{self.name} stream ended without completion")
                return
            except (HTTPError, URLError, TimeoutError) as exc:
                status = getattr(exc, "code", None)
                transient = status is None or status == 429 or status >= 500
                if emitted or not transient or attempt >= retries:
                    raise ProviderError(f"{self.name} stream unavailable: {type(exc).__name__}") from exc
                time.sleep(min(10.0, 0.35 * (2 ** attempt)))
    def probe(self, timeout: float = 8.0) -> dict:
        """Perform an explicit, side-effect-free provider connectivity check."""
        key = self._key()
        if not key:
            return {"configured": False, "reachable": False, "code": "MISSING_CREDENTIAL"}
        try:
            with urlopen(Request(self.base_url + "/models", headers={
                "Authorization": "Bearer " + key,
                "Accept": "application/json",
            }), timeout=timeout) as response:
                status = getattr(response, "status", 200)
                if status >= 400:
                    return {"configured": True, "reachable": False, "status_code": status}
                return {"configured": True, "reachable": True, "status_code": status}
        except Exception as exc:
            return {"configured": True, "reachable": False, "error": type(exc).__name__}

class MockProvider(LLMProvider):
    name="mock"
    def __init__(self,delay_ms:int=35,failure:str=""): self.delay_ms=delay_ms; self.failure=failure
    def _text(self,prompt:str)->str:
        if self.failure: raise ProviderError(f"Mock failure: {self.failure}")
        return "海风裹着雨水灌入狭窄的舱道。林海推开船舱门，锈蚀的合页发出低哑呻吟。他没有立刻迈进去——黑暗深处，某种金属正有规律地轻响。"
    def generate(self,prompt:str,model:str,**kwargs)->Generation:
        text=self._text(prompt); return Generation(text,self.name,model,len(prompt)//3,len(text)//3,metadata={"mock":True})
    def stream(self,prompt:str,model:str,**kwargs):
        text=self._text(prompt)
        for i in range(0,len(text),8): time.sleep(self.delay_ms/1000); yield text[i:i+8]
    def health_check(self)->bool: return not self.failure
