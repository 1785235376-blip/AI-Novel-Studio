from __future__ import annotations
import json, os, time
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
    def __init__(self, base_url: str): self.base_url = base_url.rstrip("/")
    def generate(self, prompt: str, model: str, **kwargs) -> Generation:
        started=time.monotonic(); payload=json.dumps({"model":model,"prompt":prompt,"stream":False,"options":kwargs}).encode()
        try:
            with urlopen(Request(self.base_url+"/api/generate",payload,{"Content-Type":"application/json"}),timeout=kwargs.get("timeout",120)) as r: data=json.load(r)
        except Exception as exc: raise ProviderError(f"Ollama unavailable: {type(exc).__name__}") from exc
        return Generation(data.get("response",""),self.name,model,data.get("prompt_eval_count",0),data.get("eval_count",0),int((time.monotonic()-started)*1000))
    def health_check(self) -> bool:
        try: urlopen(self.base_url+"/api/tags",timeout=3); return True
        except Exception: return False
    def list_models(self) -> list[dict]:
        try:
            with urlopen(self.base_url+"/api/tags",timeout=3) as r: data=json.load(r)
            return [{"name":m.get("name"),"size":m.get("size"),"modified_at":m.get("modified_at")} for m in data.get("models",[])]
        except Exception: return []
    def stream(self,prompt:str,model:str,**kwargs):
        payload=json.dumps({"model":model,"prompt":prompt,"stream":True,"options":kwargs}).encode()
        try:
            with urlopen(Request(self.base_url+"/api/generate",payload,{"Content-Type":"application/json"}),timeout=kwargs.get("timeout",120)) as r:
                for line in r:
                    if line:
                        item=json.loads(line); chunk=item.get("response","")
                        if chunk: yield chunk
        except Exception as exc: raise ProviderError(f"Ollama unavailable: {type(exc).__name__}") from exc

class OpenAICompatibleProvider(LLMProvider):
    def __init__(self,name:str,base_url:str,api_key_env:str): self.name=name; self.base_url=base_url.rstrip("/"); self.api_key_env=api_key_env
    def _key(self)->str:
        packaged = os.getenv('PACKAGED_WINDOWS_MODE','').lower() in {'1','true','yes','on'}
        try:
            from .config import settings
            packaged = packaged or settings.enable_packaged_runtime
        except Exception:
            pass
        if self.name=="deepseek":
            from .credential_vault import credential_vault
            stored=credential_vault.resolve("deepseek")
            if stored:return stored
        return "" if packaged else os.getenv(self.api_key_env,"")
    def generate(self,prompt:str,model:str,**kwargs)->Generation:
        key=self._key(); 
        if not key: raise ProviderError(f"{self.name} API key missing")
        started=time.monotonic(); body=json.dumps({"model":model,"messages":[{"role":"user","content":prompt}]}).encode()
        retries = max(0, min(int(kwargs.get("retries", 2)), 5))
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
        return Generation(text,self.name,model,usage.get("prompt_tokens",0),usage.get("completion_tokens",0),int((time.monotonic()-started)*1000))
    def health_check(self)->bool: return bool(self._key())
    def stream(self, prompt: str, model: str, **kwargs):
        key = self._key()
        if not key: raise ProviderError(f"{self.name} API key missing")
        payload = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}], "stream": True}).encode()
        retries = max(0, min(int(kwargs.get("retries", 2)), 5))
        for attempt in range(retries + 1):
            try:
                request = Request(self.base_url + "/chat/completions", payload, {"Content-Type": "application/json", "Authorization": "Bearer " + key, "Accept": "text/event-stream"})
                with urlopen(request, timeout=kwargs.get("timeout", 120)) as response:
                    for raw in response:
                        line = raw.decode("utf-8", "ignore").strip()
                        if not line.startswith("data:") or "[DONE]" in line: continue
                        item = json.loads(line[5:].strip())
                        delta = item.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        if delta: yield delta
                return
            except (HTTPError, URLError, TimeoutError) as exc:
                status = getattr(exc, "code", None)
                transient = status is None or status == 429 or status >= 500
                if not transient or attempt >= retries:
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
