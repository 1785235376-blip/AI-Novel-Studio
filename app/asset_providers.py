from dataclasses import dataclass
from typing import Protocol
DEFAULT_IMAGE_ENDPOINTS={"ddshub":"https://www.ddshub.cc/v1","openai":"https://api.openai.com/v1","custom":""}
DEFAULT_IMAGE_MODELS={"ddshub":"gpt-image-2","openai":"gpt-image-1","custom":""}

@dataclass(frozen=True)
class AssetGenerationRequest:
    provider_id: str
    model_id: str
    prompt: str
    task_id: str

@dataclass(frozen=True)
class AssetGenerationResult:
    provider_id: str
    model_id: str
    asset_uri: str

class AssetProvider(Protocol):
    def generate(self, request: AssetGenerationRequest) -> AssetGenerationResult: ...

@dataclass(frozen=True)
class VisionRequest:
    provider_id: str
    model_id: str
    prompt: str
    image_url: str

@dataclass(frozen=True)
class VisionResult:
    provider_id: str
    model_id: str
    text: str

class VisionProvider(Protocol):
    def analyze(self, request: VisionRequest) -> VisionResult: ...

@dataclass(frozen=True)
class SpeechRequest:
    provider_id: str
    model_id: str
    voice: str
    text: str

@dataclass(frozen=True)
class SpeechResult:
    provider_id: str
    model_id: str
    audio_uri: str

class SpeechProvider(Protocol):
    def synthesize(self, request: SpeechRequest) -> SpeechResult: ...

class OpenAICompatibleSpeechProvider:
    def __init__(self, transport, api_key: str, endpoint: str):
        if not api_key or not endpoint: raise ValueError('speech provider credentials are required')
        self.transport,self.api_key,self.endpoint=transport,api_key,endpoint.rstrip('/')
    def synthesize(self, request: SpeechRequest) -> SpeechResult:
        response=self.transport.post(self.endpoint+'/audio/speech',headers={'Authorization':f'Bearer {self.api_key}'},json={'model':request.model_id,'voice':request.voice,'input':request.text,'response_format':'mp3'})
        response.raise_for_status(); data=response.json() if hasattr(response,'json') else {}; uri=data.get('url') or data.get('audio_url')
        if not uri: raise ValueError('speech provider response missing audio URL')
        return SpeechResult(request.provider_id,request.model_id,uri)

class OpenAICompatibleVisionProvider:
    def __init__(self, transport, api_key: str, endpoint: str):
        if not api_key or not endpoint: raise ValueError('vision provider credentials are required')
        self.transport,self.api_key,self.endpoint=transport,api_key,endpoint.rstrip('/')
    def analyze(self, request: VisionRequest) -> VisionResult:
        response=self.transport.post(self.endpoint+'/chat/completions',headers={'Authorization':f'Bearer {self.api_key}'},json={'model':request.model_id,'messages':[{'role':'user','content':[{'type':'text','text':request.prompt},{'type':'image_url','image_url':{'url':request.image_url}}]}]})
        response.raise_for_status(); data=response.json(); text=((data.get('choices') or [{}])[0].get('message') or {}).get('content','')
        if not text: raise ValueError('vision provider response missing content')
        return VisionResult(request.provider_id,request.model_id,str(text))

@dataclass(frozen=True)
class VideoGenerationRequest:
    provider_id: str
    model_id: str
    prompt: str
    start_frame: str
    end_frame: str
    task_id: str

@dataclass(frozen=True)
class VideoGenerationResult:
    provider_id: str
    model_id: str
    video_uri: str

class VideoProvider(Protocol):
    def generate(self, request: VideoGenerationRequest) -> VideoGenerationResult: ...
    def health_check(self) -> bool: ...

class DeterministicVideoProvider:
    def health_check(self) -> bool: return True
    def generate(self, request: VideoGenerationRequest) -> VideoGenerationResult:
        return VideoGenerationResult(request.provider_id, request.model_id, f"placeholder://video/{request.task_id}")

class HttpVideoProvider:
    def __init__(self,transport,endpoint,api_key):
        if not endpoint or not api_key: raise ValueError('video provider endpoint and credential are required')
        self.transport=transport; self.endpoint=endpoint.rstrip('/'); self.api_key=api_key
    def health_check(self): return True
    def get_status(self,remote_task_id):
        response=self.transport.get(self.endpoint+'/videos/'+str(remote_task_id),headers={'Authorization':f'Bearer {self.api_key}'})
        response.raise_for_status(); data=response.json(); return {'status':data.get('status','UNKNOWN'),'progress':int(data.get('progress',0) or 0),'url':data.get('url') or data.get('video_url'),'error':data.get('error')}
    def generate(self,request:VideoGenerationRequest)->VideoGenerationResult:
        response=self.transport.post(self.endpoint+'/videos',headers={'Authorization':f'Bearer {self.api_key}'},json={'model':request.model_id,'prompt':request.prompt,'start_frame':request.start_frame,'end_frame':request.end_frame,'task_id':request.task_id})
        response.raise_for_status(); data=response.json(); uri=data.get('url') or data.get('video_url') or data.get('id')
        if not uri: raise ValueError('video provider response missing url or task id')
        return VideoGenerationResult(request.provider_id,request.model_id,uri)

class AssetProviderRegistry:
    def __init__(self): self._providers: dict[str, AssetProvider] = {}
    def register(self, provider_id: str, provider: AssetProvider): self._providers[provider_id] = provider
    def unregister(self, provider_id: str) -> None: self._providers.pop(provider_id, None)
    def get(self, provider_id: str) -> AssetProvider:
        try: return self._providers[provider_id]
        except KeyError as exc: raise ValueError(f"asset provider is not configured: {provider_id}") from exc

class OpenAICompatibleImageProvider:
    """Transport-injected adapter; credentials never belong in this class."""
    def __init__(self, transport, api_key: str, endpoint: str):
        if not api_key or not endpoint: raise ValueError("image provider credentials are required")
        self.transport,self.api_key,self.endpoint=transport,api_key,endpoint.rstrip('/')
    def generate(self, request: AssetGenerationRequest) -> AssetGenerationResult:
        response=self.transport.post(self.endpoint+"/images/generations",headers={"Authorization":f"Bearer {self.api_key}"},json={"model":request.model_id,"prompt":request.prompt,"n":1})
        response.raise_for_status(); data=response.json(); item=(data.get("data") or [{}])[0]; uri=item.get("url") or item.get("b64_json")
        if not uri: raise ValueError("image provider response missing url")
        return AssetGenerationResult(request.provider_id,request.model_id,uri)

def build_openai_compatible_from_vault(transport, provider_id: str, endpoint: str, vault):
    secret=vault.resolve(provider_id)
    if not secret: raise ValueError(f"credential is not configured: {provider_id}")
    return OpenAICompatibleImageProvider(transport,secret,endpoint)
