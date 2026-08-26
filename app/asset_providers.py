import base64
import time
from dataclasses import dataclass
from typing import Protocol
IMAGE_PROVIDER_CATALOG={
    "comfyui":{"display_name":"ComfyUI（本地）","endpoint":"http://127.0.0.1:8188","default_model":"","api_style":"comfyui","local":True,"requires_credential":False},
    "automatic1111":{"display_name":"Stable Diffusion WebUI（本地）","endpoint":"http://127.0.0.1:7860","default_model":"","api_style":"automatic1111","local":True,"requires_credential":False},
    "ddshub":{"display_name":"DDSHub","endpoint":"https://www.ddshub.cc/v1","default_model":"gpt-image-2","api_style":"openai","local":False,"requires_credential":True},
    "openai":{"display_name":"OpenAI","endpoint":"https://api.openai.com/v1","default_model":"gpt-image-1","api_style":"openai","local":False,"requires_credential":True},
    "siliconflow":{"display_name":"SiliconFlow","endpoint":"https://api.siliconflow.cn/v1","default_model":"black-forest-labs/FLUX.1-schnell","api_style":"openai","local":False,"requires_credential":True},
    "custom":{"display_name":"其他 OpenAI-compatible 服务商","endpoint":"","default_model":"","api_style":"openai","local":False,"requires_credential":True},
}
DEFAULT_IMAGE_ENDPOINTS={key:value["endpoint"] for key,value in IMAGE_PROVIDER_CATALOG.items()}
DEFAULT_IMAGE_MODELS={key:value["default_model"] for key,value in IMAGE_PROVIDER_CATALOG.items()}

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
    idempotency_key: str | None = None

@dataclass(frozen=True)
class VideoGenerationResult:
    provider_id: str
    model_id: str
    video_uri: str | None = None
    remote_task_id: str | None = None
    status: str = "RUNNING"

class VideoProvider(Protocol):
    def generate(self, request: VideoGenerationRequest) -> VideoGenerationResult: ...
    def health_check(self) -> bool: ...
    def capabilities(self) -> dict[str, bool]: ...

class DeterministicVideoProvider:
    def health_check(self) -> bool: return True
    def capabilities(self) -> dict[str, bool]:
        return {"text_to_video": True, "image_to_video": True, "start_frame": True, "end_frame": True, "polling": False, "cancellation": False}
    def generate(self, request: VideoGenerationRequest) -> VideoGenerationResult:
        return VideoGenerationResult(request.provider_id, request.model_id, f"placeholder://video/{request.task_id}", status="SUCCEEDED")

class HttpVideoProvider:
    def __init__(self,transport,endpoint,api_key,default_model=''):
        if not endpoint: raise ValueError('video provider endpoint is required')
        self.transport=transport; self.endpoint=endpoint.rstrip('/'); self.api_key=api_key;self.default_model=default_model
    def _headers(self): return {'Authorization':f'Bearer {self.api_key}'} if self.api_key else {}
    def capabilities(self) -> dict[str, bool]:
        return {"text_to_video": True, "image_to_video": True, "start_frame": True, "end_frame": True, "polling": True, "cancellation": True}
    def health_check(self):
        try:return self.transport.get(self.endpoint,headers=self._headers(),timeout=1.5).status_code<400
        except Exception:return False
    def status(self) -> dict:
        reachable=self.health_check()
        return {"reachable":reachable,"default_model":self.default_model,"capabilities":self.capabilities()}
    def get_status(self,remote_task_id):
        response=self.transport.get(self.endpoint+'/videos/'+str(remote_task_id),headers=self._headers(),timeout=15)
        response.raise_for_status(); data=response.json(); return {'status':data.get('status','UNKNOWN'),'progress':int(data.get('progress',0) or 0),'url':data.get('url') or data.get('video_url'),'error':data.get('error')}
    def cancel(self,remote_task_id):
        response=self.transport.post(self.endpoint+'/videos/'+str(remote_task_id)+'/cancel',headers=self._headers(),json={},timeout=30)
        response.raise_for_status()
        try:data=response.json()
        except Exception:data={}
        return {'status':str(data.get('status') or 'CANCELLED').upper()}
    def generate(self,request:VideoGenerationRequest)->VideoGenerationResult:
        headers={**self._headers(),'Idempotency-Key':request.idempotency_key or request.task_id}
        response=self.transport.post(self.endpoint+'/videos',headers=headers,json={'model':request.model_id,'prompt':request.prompt,'start_frame':request.start_frame,'end_frame':request.end_frame,'task_id':request.task_id},timeout=30)
        response.raise_for_status(); data=response.json(); uri=data.get('url') or data.get('video_url'); remote=data.get('id') or data.get('task_id')
        if not uri and not remote: raise ValueError('video provider response missing url or task id')
        status=str(data.get('status') or ('SUCCEEDED' if uri else 'RUNNING')).upper()
        status={'COMPLETED':'SUCCEEDED','COMPLETE':'SUCCEEDED','IN_PROGRESS':'RUNNING','QUEUED':'PENDING'}.get(status,status)
        return VideoGenerationResult(request.provider_id,request.model_id,uri,str(remote) if remote else None,status)

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
    def health_check(self) -> bool:
        try:return self.transport.get(self.endpoint+"/models",headers={"Authorization":f"Bearer {self.api_key}"},timeout=1.5).status_code<500
        except Exception:return False
    def generate(self, request: AssetGenerationRequest) -> AssetGenerationResult:
        response=self.transport.post(self.endpoint+"/images/generations",headers={"Authorization":f"Bearer {self.api_key}"},json={"model":request.model_id,"prompt":request.prompt,"n":1})
        response.raise_for_status(); data=response.json(); item=(data.get("data") or [{}])[0]; uri=item.get("url") or item.get("b64_json")
        if item.get("b64_json"): uri="data:image/png;base64,"+str(item["b64_json"])
        if not uri: raise ValueError("image provider response missing url")
        return AssetGenerationResult(request.provider_id,request.model_id,uri)

class Automatic1111ImageProvider:
    def __init__(self, transport, endpoint: str): self.transport,self.endpoint=transport,endpoint.rstrip('/')
    def health_check(self) -> bool:
        try:return self.transport.get(self.endpoint+"/sdapi/v1/sd-models",timeout=1.5).status_code==200
        except Exception:return False
    def generate(self, request: AssetGenerationRequest) -> AssetGenerationResult:
        payload={"prompt":request.prompt,"steps":28,"width":1024,"height":1024}
        if request.model_id: payload["override_settings"]={"sd_model_checkpoint":request.model_id}
        response=self.transport.post(self.endpoint+"/sdapi/v1/txt2img",json=payload,timeout=180)
        response.raise_for_status(); images=response.json().get("images") or []
        if not images: raise ValueError("automatic1111 response missing image")
        return AssetGenerationResult(request.provider_id,request.model_id,"data:image/png;base64,"+str(images[0]).split(',',1)[-1])

class ComfyUIImageProvider:
    def __init__(self, transport, endpoint: str): self.transport,self.endpoint=transport,endpoint.rstrip('/')
    def health_check(self) -> bool:
        try:return self.transport.get(self.endpoint+"/system_stats",timeout=1.5).status_code==200
        except Exception:return False
    def _workflow(self, request: AssetGenerationRequest) -> dict:
        return {
            "3":{"class_type":"KSampler","inputs":{"seed":int(time.time()*1000)%2147483647,"steps":28,"cfg":7,"sampler_name":"euler","scheduler":"normal","denoise":1,"model":["4",0],"positive":["6",0],"negative":["7",0],"latent_image":["5",0]}},
            "4":{"class_type":"CheckpointLoaderSimple","inputs":{"ckpt_name":request.model_id}},
            "5":{"class_type":"EmptyLatentImage","inputs":{"width":1024,"height":1024,"batch_size":1}},
            "6":{"class_type":"CLIPTextEncode","inputs":{"text":request.prompt,"clip":["4",1]}},
            "7":{"class_type":"CLIPTextEncode","inputs":{"text":"low quality, blurry, artifacts","clip":["4",1]}},
            "8":{"class_type":"VAEDecode","inputs":{"samples":["3",0],"vae":["4",2]}},
            "9":{"class_type":"SaveImage","inputs":{"filename_prefix":"AI-Novel-Studio","images":["8",0]}},
        }
    def generate(self, request: AssetGenerationRequest) -> AssetGenerationResult:
        if not request.model_id: raise ValueError("ComfyUI checkpoint is required")
        response=self.transport.post(self.endpoint+"/prompt",json={"prompt":self._workflow(request)},timeout=15)
        response.raise_for_status(); prompt_id=response.json().get("prompt_id")
        if not prompt_id: raise ValueError("ComfyUI response missing prompt_id")
        for _ in range(120):
            history=self.transport.get(self.endpoint+"/history/"+str(prompt_id),timeout=10);history.raise_for_status()
            entry=history.json().get(str(prompt_id)) or {}
            for output in (entry.get("outputs") or {}).values():
                images=output.get("images") or []
                if images:
                    image=images[0];binary=self.transport.get(self.endpoint+"/view",params={"filename":image.get("filename"),"subfolder":image.get("subfolder",''),"type":image.get("type",'output')},timeout=30)
                    binary.raise_for_status();uri="data:image/png;base64,"+base64.b64encode(binary.content).decode('ascii')
                    return AssetGenerationResult(request.provider_id,request.model_id,uri)
            time.sleep(.5)
        raise ValueError("ComfyUI generation timed out")

def build_openai_compatible_from_vault(transport, provider_id: str, endpoint: str, vault):
    secret=vault.resolve(provider_id)
    if not secret: raise ValueError(f"credential is not configured: {provider_id}")
    return OpenAICompatibleImageProvider(transport,secret,endpoint)
