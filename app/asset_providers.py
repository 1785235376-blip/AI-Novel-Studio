import base64
import time
from urllib.parse import quote
from dataclasses import dataclass, field
from typing import Callable, Protocol
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

def validate_image_parameters(parameters: dict, allowed=None) -> dict:
    known={'size','quality','width','height','steps','seed','negative_prompt','denoising_strength'}
    if set(parameters)-known or (allowed is not None and set(parameters)-set(allowed)):
        raise ValueError('IMAGE_PARAMETER_UNSUPPORTED')
    for key in ('width','height'):
        if key in parameters and (not isinstance(parameters[key],int) or isinstance(parameters[key],bool) or not 64<=parameters[key]<=2048 or parameters[key]%8): raise ValueError('image dimensions must be multiples of 8 between 64 and 2048')
    if 'steps' in parameters and (not isinstance(parameters['steps'],int) or isinstance(parameters['steps'],bool) or not 1<=parameters['steps']<=150):raise ValueError('invalid image step count')
    if 'seed' in parameters and (not isinstance(parameters['seed'],int) or isinstance(parameters['seed'],bool) or not 0<=parameters['seed']<=2147483647):raise ValueError('invalid image seed')
    if 'size' in parameters and parameters['size'] not in {'auto','1024x1024','1536x1024','1024x1536'}:raise ValueError('unsupported image size')
    if 'quality' in parameters and parameters['quality'] not in {'auto','low','medium','high','standard','hd'}:raise ValueError('unsupported image quality')
    if 'negative_prompt' in parameters and (not isinstance(parameters['negative_prompt'],str) or len(parameters['negative_prompt'])>10000):raise ValueError('invalid negative prompt')
    if 'denoising_strength' in parameters:
        import math
        value=parameters['denoising_strength']
        if type(value) not in {int,float} or not math.isfinite(value) or not 0<value<=1:raise ValueError('invalid denoising strength')
    return dict(parameters)

@dataclass(frozen=True)
class AssetGenerationRequest:
    provider_id: str
    model_id: str
    prompt: str
    task_id: str
    parameters: dict = field(default_factory=dict)
    # Optional server-owned last-mile authority, preserved by legacy callers.
    dispatch_guard: Callable[[], None] | None = field(default=None, repr=False, compare=False)

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
    parameters: dict = field(default_factory=dict)
    source_video_uri: str | None = None
    dispatch_guard: Callable[[], None] | None = field(default=None, repr=False, compare=False)

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
    """Honesty adapter: never emits a fake success URI.

    DesktopHost Phase 1 requires unconfigured video providers to stay
    ``VIDEO_PROVIDER_NOT_CONFIGURED`` / PENDING. A placeholder success would
    fail the window gate.
    """
    def health_check(self) -> bool: return False
    def capabilities(self) -> dict[str, bool]:
        return {"text_to_video": False, "image_to_video": False, "start_frame": True, "end_frame": True, "polling": False, "cancellation": False}
    def generate(self, request: VideoGenerationRequest) -> VideoGenerationResult:
        raise ValueError("VIDEO_PROVIDER_NOT_CONFIGURED")

class HttpVideoProvider:
    supports_dispatch_guard = True
    def __init__(self,transport,endpoint,api_key,default_model='',*,video_to_video=False):
        if not endpoint: raise ValueError('video provider endpoint is required')
        self.transport=transport; self.endpoint=endpoint.rstrip('/'); self.api_key=api_key;self.default_model=default_model
        self.video_to_video=bool(video_to_video)
    def _headers(self): return {'Authorization':f'Bearer {self.api_key}'} if self.api_key else {}
    def capabilities(self) -> dict[str, bool]:
        return {"text_to_video": True, "image_to_video": True, "start_frame": True, "end_frame": True, "polling": True, "cancellation": True, "video_to_video": self.video_to_video}
    def health_check(self):
        try:return self.transport.get(self.endpoint,headers=self._headers(),timeout=1.5).status_code<400
        except Exception:return False
    def status(self) -> dict:
        reachable=self.health_check()
        return {"reachable":reachable,"default_model":self.default_model,"capabilities":self.capabilities()}
    def get_status(self,remote_task_id):
        response=self.transport.get(self.endpoint+'/videos/'+quote(str(remote_task_id),safe=''),headers=self._headers(),timeout=15)
        response.raise_for_status(); data=response.json(); return {'status':data.get('status','UNKNOWN'),'progress':int(data.get('progress',0) or 0),'url':data.get('url') or data.get('video_url'),'error':data.get('error')}
    def cancel(self,remote_task_id):
        response=self.transport.post(self.endpoint+'/videos/'+quote(str(remote_task_id),safe='')+'/cancel',headers=self._headers(),json={},timeout=30)
        response.raise_for_status()
        try:data=response.json()
        except Exception:data={}
        return {'status':str(data.get('status') or 'CANCELLED').upper()}
    def generate(self,request:VideoGenerationRequest)->VideoGenerationResult:
        headers={**self._headers(),'Idempotency-Key':request.idempotency_key or request.task_id}
        payload={'model':request.model_id,'prompt':request.prompt,'start_frame':request.start_frame,'end_frame':request.end_frame,'task_id':request.task_id,'parameters':request.parameters}
        if request.source_video_uri is not None:
            if not self.video_to_video: raise ValueError('VIDEO_TO_VIDEO_NOT_CONFIGURED')
            payload['source_video_uri']=request.source_video_uri
        if request.dispatch_guard is not None:
            request.dispatch_guard()
        response=self.transport.post(self.endpoint+'/videos',headers=headers,json=payload,timeout=30)
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
    supports_dispatch_guard = True
    supported_parameters = ("size", "quality")
    edit_reference_limit = 5
    def __init__(self, transport, api_key: str, endpoint: str):
        if not api_key or not endpoint: raise ValueError("image provider credentials are required")
        self.transport,self.api_key,self.endpoint=transport,api_key,endpoint.rstrip('/')
    def health_check(self) -> bool:
        try:return 200<=self.transport.get(self.endpoint+"/models",headers={"Authorization":f"Bearer {self.api_key}"},timeout=1.5).status_code<300
        except Exception:return False
    def generate(self, request: AssetGenerationRequest) -> AssetGenerationResult:
        payload={"model":request.model_id,"prompt":request.prompt,"n":1,**validate_image_parameters(request.parameters,{"size","quality"})}
        if request.dispatch_guard is not None: request.dispatch_guard()
        response=self.transport.post(self.endpoint+"/images/generations",headers={"Authorization":f"Bearer {self.api_key}"},json=payload,timeout=180)
        response.raise_for_status(); data=response.json(); item=(data.get("data") or [{}])[0]; uri=item.get("url") or item.get("b64_json")
        if item.get("b64_json"): uri="data:image/png;base64,"+str(item["b64_json"])
        if not uri: raise ValueError("image provider response missing url")
        return AssetGenerationResult(request.provider_id,request.model_id,uri)
    def edit(self, request: AssetGenerationRequest, images: list[str], **options: object) -> AssetGenerationResult:
        if not images or len(images) > 5:
            raise ValueError("between 1 and 5 reference images are required")
        payload={"model":request.model_id,"prompt":request.prompt,"images":[{"image_url":value} for value in images],"n":1,**validate_image_parameters(request.parameters,{"size","quality"})}
        for key in ("size","quality","output_format","output_compression","background","moderation"):
            if key in options and options[key] is not None: payload[key]=options[key]
        if request.dispatch_guard is not None: request.dispatch_guard()
        response=self.transport.post(self.endpoint+"/images/edits",headers={"Authorization":f"Bearer {self.api_key}"},json=payload,timeout=180)
        response.raise_for_status(); data=response.json(); item=(data.get("data") or [{}])[0]; uri=item.get("url") or item.get("b64_json")
        if item.get("b64_json"): uri="data:image/png;base64,"+str(item["b64_json"])
        if not uri: raise ValueError("image edit provider response missing url")
        return AssetGenerationResult(request.provider_id,request.model_id,uri)

class Automatic1111ImageProvider:
    supports_dispatch_guard = True
    supported_parameters = ("width", "height", "steps", "seed", "negative_prompt")
    edit_reference_limit = 5
    def __init__(self, transport, endpoint: str): self.transport,self.endpoint=transport,endpoint.rstrip('/')
    def image_configuration(self):
        import copy
        recipe = copy.deepcopy(getattr(self, 'image_recipe_descriptor', None))
        if recipe:
            recipe['supported_parameters'] = {op: self.image_parameters(op) for op in recipe['operations']}
        return recipe
    def image_parameters(self, operation):
        recipe = getattr(self, 'image_recipe_descriptor', None)
        if not recipe or operation not in recipe['operations']:
            raise ValueError('IMAGE_RECIPE_OPERATION_NOT_CONFIGURED')
        supported=self.supported_parameters if operation=='t2i' else tuple(k for k in self.supported_parameters if k not in {'width','height'})
        return supported + (() if operation == 't2i' else ('denoising_strength',))
    def image_recipe(self, request, *, operation, reference_weights=(), mask=False):
        recipe = self.image_configuration()
        if not recipe or operation not in recipe['operations']:
            raise ValueError('IMAGE_RECIPE_OPERATION_NOT_CONFIGURED')
        return {'recipe_id': recipe['recipe_id'], 'operation': operation, 'model': request.model_id,
            'parameters': validate_image_parameters(request.parameters,self.image_parameters(operation)),
            'reference_weights': list(reference_weights), 'mask_semantics': recipe['mask_semantics'] if mask else None}
    def generate_image(self, request, *, operation, images, reference_weights, mask=None):
        if operation == 't2i':
            if images or reference_weights or mask or 'denoising_strength' in request.parameters:
                raise ValueError('IMAGE_RECIPE_T2I_INPUT_INVALID')
            self.image_parameters(operation)
            return self.generate(request)
        self.image_parameters(operation)
        if operation not in {'i2i','inpaint'} or len(images)!=1 or reference_weights != [1]:
            raise ValueError('IMAGE_RECIPE_REFERENCES_INVALID')
        if (operation == 'inpaint') != (mask is not None): raise ValueError('IMAGE_RECIPE_INPAINT_INPUT_INVALID')
        inline_values=[*images, *([mask] if mask is not None else [])]
        if sum(len(value) for value in inline_values if isinstance(value,str))>36*1024*1024:raise ValueError('IMAGE_EDIT_REFERENCE_LIMIT')
        measured=[_verified_inline_image(value) for value in inline_values]
        if mask is not None and (measured[0][1].get('width'),measured[0][1].get('height'))!=(measured[1][1].get('width'),measured[1][1].get('height')):
            raise ValueError('IMAGE_RECIPE_MASK_DIMENSIONS_INVALID')
        if mask is not None:
            from .services.studio_image_mask_authoring import verify_mask
            verify_mask(measured[1][0],checkpoint=request.dispatch_guard or (lambda:None))
        payload={'prompt':request.prompt,'init_images':images,'denoising_strength':0.6,'steps':28,
            'width':measured[0][1]['width'],'height':measured[0][1]['height'],
            **validate_image_parameters(request.parameters,self.image_parameters(operation))}
        if mask is not None:
            payload.update(mask=mask,inpainting_mask_invert=1,inpainting_fill=1,mask_blur=0,inpaint_full_res=False,
                inpaint_full_res_padding=0,resize_mode=0)
        if request.model_id:payload['override_settings']={'sd_model_checkpoint':request.model_id}
        if request.dispatch_guard is not None:request.dispatch_guard()
        response=self.transport.post(self.endpoint+'/sdapi/v1/img2img',json=payload,timeout=180,dispatch_guard=request.dispatch_guard)
        response.raise_for_status()
        if request.dispatch_guard is not None:request.dispatch_guard()
        values=response.json().get('images') or []
        if not values:raise ValueError('automatic1111 edit response missing image')
        return AssetGenerationResult(request.provider_id,request.model_id,'data:image/png;base64,'+str(values[0]).split(',',1)[-1])
    def health_check(self) -> bool:
        try:return self.transport.get(self.endpoint+"/sdapi/v1/sd-models",timeout=1.5).status_code==200
        except Exception:return False
    def generate(self, request: AssetGenerationRequest) -> AssetGenerationResult:
        payload={"prompt":request.prompt,"steps":28,"width":1024,"height":1024,**validate_image_parameters(request.parameters,{"width","height","steps","seed","negative_prompt"})}
        if request.model_id: payload["override_settings"]={"sd_model_checkpoint":request.model_id}
        if request.dispatch_guard is not None: request.dispatch_guard()
        response=self.transport.post(self.endpoint+"/sdapi/v1/txt2img",json=payload,timeout=180)
        response.raise_for_status(); images=response.json().get("images") or []
        if not images: raise ValueError("automatic1111 response missing image")
        return AssetGenerationResult(request.provider_id,request.model_id,"data:image/png;base64,"+str(images[0]).split(',',1)[-1])

    def edit(self, request: AssetGenerationRequest, images: list[str], **options: object) -> AssetGenerationResult:
        if not images or len(images) > 5 or options:
            raise ValueError("IMAGE_EDIT_REFERENCES_OR_OPTIONS_UNSUPPORTED")
        if any(not isinstance(value, str) or not value.startswith("data:image/") or ";base64," not in value for value in images):
            raise ValueError("IMAGE_EDIT_VERIFIED_INLINE_REFERENCES_REQUIRED")
        if sum(len(value) for value in images) > 36 * 1024 * 1024:
            raise ValueError("IMAGE_EDIT_REFERENCE_LIMIT")
        payload={"prompt":request.prompt,"init_images":images,"denoising_strength":0.6,"steps":28,"width":1024,"height":1024,
            **validate_image_parameters(request.parameters,{"width","height","steps","seed","negative_prompt"})}
        if request.model_id: payload["override_settings"]={"sd_model_checkpoint":request.model_id}
        if request.dispatch_guard is not None: request.dispatch_guard()
        response=self.transport.post(self.endpoint+"/sdapi/v1/img2img",json=payload,timeout=180)
        response.raise_for_status(); values=response.json().get("images") or []
        if not values: raise ValueError("automatic1111 edit response missing image")
        return AssetGenerationResult(request.provider_id,request.model_id,"data:image/png;base64,"+str(values[0]).split(',',1)[-1])

class ComfyUIImageProvider:
    supports_dispatch_guard = True
    supported_parameters = ("width", "height", "steps", "seed", "negative_prompt")
    edit_supported_parameters = ("steps", "seed", "negative_prompt")
    edit_reference_limit = 1
    def __init__(self, transport, endpoint: str): self.transport,self.endpoint=transport,endpoint.rstrip('/')
    def image_configuration(self):
        import copy
        recipe=copy.deepcopy(getattr(self,'image_recipe_descriptor',None))
        if recipe:recipe['supported_parameters']={op:self.image_parameters(op) for op in recipe['operations']}
        return recipe
    def image_parameters(self, operation):
        recipe=getattr(self,'image_recipe_descriptor',None)
        if not recipe or operation not in recipe['operations']:raise ValueError('IMAGE_RECIPE_OPERATION_NOT_CONFIGURED')
        parameters=self.supported_parameters if operation=='t2i' else self.edit_supported_parameters+('denoising_strength',)
        if recipe['recipe_id']=='comfy-flux1-v1':parameters=tuple(k for k in parameters if k!='negative_prompt')
        return parameters
    def image_recipe(self, request, *, operation, reference_weights=(), mask=False):
        from .services.studio_image_provider_recipes import build_workflow
        recipe=self.image_configuration()
        if not recipe:raise ValueError('IMAGE_RECIPE_OPERATION_NOT_CONFIGURED')
        parameters=validate_image_parameters(request.parameters,self.image_parameters(operation))
        return build_workflow(recipe,request.prompt,parameters,operation=operation,
            uploads=tuple('source-'+str(i)+'.png' for i in range(len(reference_weights))),weights=reference_weights,
            mask='mask.png' if mask else None)
    def generate_image(self, request, *, operation, images, reference_weights, mask=None):
        import hashlib
        import re
        from .services.studio_image_provider_recipes import RECIPES,project_comfy_image_recipe,build_workflow,validate_workflow
        descriptor=getattr(self,'image_recipe_descriptor',None)
        if not descriptor:raise ValueError('IMAGE_RECIPE_OPERATION_NOT_CONFIGURED')
        parameters=validate_image_parameters(request.parameters,self.image_parameters(operation))
        if operation=='t2i' and (images or reference_weights or mask):raise ValueError('IMAGE_RECIPE_T2I_INPUT_INVALID')
        if operation!='t2i' and (not 1<=len(images)<=descriptor['reference_limit'] or len(images)!=len(reference_weights)):
            raise ValueError('IMAGE_RECIPE_REFERENCES_INVALID')
        family=next(r['family'] for r in RECIPES if r['id']==descriptor['recipe_id'])
        def observed():
            if request.dispatch_guard is not None:request.dispatch_guard()
            response=self.transport.get(self.endpoint+'/object_info',timeout=10,dispatch_guard=request.dispatch_guard)
            response.raise_for_status()
            if request.dispatch_guard is not None:request.dispatch_guard()
            info=response.json()
            projected=project_comfy_image_recipe(info,request.model_id,family)
            if projected!=descriptor:raise ValueError('IMAGE_RECIPE_CONFIGURATION_CHANGED')
            return info
        if sum(len(value) for value in [*images,*([mask] if mask is not None else [])] if isinstance(value,str))>36*1024*1024:
            raise ValueError('IMAGE_EDIT_REFERENCE_LIMIT')
        values=[_verified_inline_image(value) for value in images]
        mask_value=_verified_inline_image(mask) if mask is not None else None
        if operation=='inpaint' and (len(values)!=1 or mask_value is None):raise ValueError('IMAGE_RECIPE_INPAINT_INPUT_INVALID')
        if operation!='inpaint' and mask_value is not None:raise ValueError('IMAGE_RECIPE_INPAINT_INPUT_INVALID')
        if mask_value is not None and (values[0][1].get('width'),values[0][1].get('height'))!=(mask_value[1].get('width'),mask_value[1].get('height')):
            raise ValueError('IMAGE_RECIPE_MASK_DIMENSIONS_INVALID')
        if mask_value is not None:
            from .services.studio_image_mask_authoring import verify_mask
            verify_mask(mask_value[0],checkpoint=request.dispatch_guard or (lambda:None))
        preflight=build_workflow(descriptor,request.prompt,parameters,operation=operation,
            uploads=tuple('source-'+str(i)+'.png' for i in range(len(values))),weights=reference_weights,
            mask='mask.png' if mask_value is not None else None)
        validate_workflow(observed(),preflight)
        names=[];mask_name=None
        for index,(data,measured) in enumerate([*values,*([mask_value] if mask_value is not None else [])]):
            filename='studio-'+hashlib.sha256((request.task_id+':'+str(index)).encode()).hexdigest()+'.'+measured['extension']
            if request.dispatch_guard is not None:request.dispatch_guard()
            response=self.transport.post(self.endpoint+'/upload/image',files={'image':(filename,data,measured['media_type'])},
                data={'type':'input','overwrite':'false'},timeout=30,dispatch_guard=request.dispatch_guard)
            response.raise_for_status()
            if request.dispatch_guard is not None:request.dispatch_guard()
            receipt=response.json();name=receipt.get('name')
            if (not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,239}',name)
                    or '..' in name or receipt.get('subfolder','') or receipt.get('type','input')!='input'):
                raise ValueError('COMFYUI_UPLOAD_RECEIPT_INVALID')
            if index==len(values):mask_name=name
            else:names.append(name)
        info=observed()
        workflow=build_workflow(descriptor,request.prompt,parameters,operation=operation,uploads=names,
            weights=reference_weights,mask=mask_name)
        validate_workflow(info,workflow)
        if request.dispatch_guard is not None:request.dispatch_guard()
        response=self.transport.post(self.endpoint+'/prompt',json={'prompt':workflow},timeout=15,dispatch_guard=request.dispatch_guard)
        response.raise_for_status()
        if request.dispatch_guard is not None:request.dispatch_guard()
        prompt_id=response.json().get('prompt_id')
        if not isinstance(prompt_id,str) or not prompt_id or len(prompt_id)>240:raise ValueError('ComfyUI response missing prompt_id')
        return self._image_result(request,prompt_id)
    def _image_result(self,request,prompt_id):
        import re
        from .media_files import inspect_image
        for _ in range(120):
            if request.dispatch_guard is not None:request.dispatch_guard()
            response=self.transport.get(self.endpoint+'/history/'+quote(prompt_id,safe=''),timeout=10,dispatch_guard=request.dispatch_guard)
            response.raise_for_status()
            if request.dispatch_guard is not None:request.dispatch_guard()
            entry=response.json().get(prompt_id) or {}
            if (entry.get('status') or {}).get('status_str') in {'error','failed'}:
                raise ValueError('COMFYUI_EXECUTION_FAILED')
            # Only the closed SaveImage node owns the output; unrelated node
            # history or preview images never become the reviewed candidate.
            values=((entry.get('outputs') or {}).get('9') or {}).get('images') or []
            if values:
                item=values[0]
                if (not isinstance(item,dict) or not isinstance(item.get('filename'),str)
                        or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,239}',item['filename'])
                        or '..' in item['filename'] or item.get('subfolder','') or item.get('type','output')!='output'):
                    raise ValueError('COMFYUI_OUTPUT_RECEIPT_INVALID')
                if request.dispatch_guard is not None:request.dispatch_guard()
                binary=self.transport.get(self.endpoint+'/view',params={'filename':item['filename'],'subfolder':'','type':'output'},
                    timeout=30,dispatch_guard=request.dispatch_guard)
                binary.raise_for_status()
                if request.dispatch_guard is not None:request.dispatch_guard()
                if len(binary.content)>25*1024*1024:raise ValueError('IMAGE_OUTPUT_LIMIT')
                measured=inspect_image(binary.content)
                if request.dispatch_guard is not None:request.dispatch_guard()
                return AssetGenerationResult(request.provider_id,request.model_id,'data:'+measured['media_type']+';base64,'+base64.b64encode(binary.content).decode('ascii'))
            time.sleep(.5)
        raise ValueError('ComfyUI generation timed out')
    def health_check(self) -> bool:
        try:return self.transport.get(self.endpoint+"/system_stats",timeout=1.5).status_code==200
        except Exception:return False
    def _workflow(self, request: AssetGenerationRequest) -> dict:
        parameters=validate_image_parameters(request.parameters,{"width","height","steps","seed","negative_prompt"})
        return {
            "3":{"class_type":"KSampler","inputs":{"seed":parameters.get("seed",int(time.time()*1000)%2147483647),"steps":parameters.get("steps",28),"cfg":7,"sampler_name":"euler","scheduler":"normal","denoise":1,"model":["4",0],"positive":["6",0],"negative":["7",0],"latent_image":["5",0]}},
            "4":{"class_type":"CheckpointLoaderSimple","inputs":{"ckpt_name":request.model_id}},
            "5":{"class_type":"EmptyLatentImage","inputs":{"width":parameters.get("width",1024),"height":parameters.get("height",1024),"batch_size":1}},
            "6":{"class_type":"CLIPTextEncode","inputs":{"text":request.prompt,"clip":["4",1]}},
            "7":{"class_type":"CLIPTextEncode","inputs":{"text":parameters.get("negative_prompt","low quality, blurry, artifacts"),"clip":["4",1]}},
            "8":{"class_type":"VAEDecode","inputs":{"samples":["3",0],"vae":["4",2]}},
            "9":{"class_type":"SaveImage","inputs":{"filename_prefix":"AI-Novel-Studio","images":["8",0]}},
        }
    def generate(self, request: AssetGenerationRequest) -> AssetGenerationResult:
        if not request.model_id: raise ValueError("ComfyUI checkpoint is required")
        recipe=getattr(self,'image_recipe_descriptor',None)
        if recipe:
            return self.generate_image(request,operation='t2i',images=[],reference_weights=[])
        workflow=self._workflow(request)
        if request.dispatch_guard is not None: request.dispatch_guard()
        response=self.transport.post(self.endpoint+"/prompt",json={"prompt":workflow},timeout=15)
        response.raise_for_status(); prompt_id=response.json().get("prompt_id")
        if not prompt_id: raise ValueError("ComfyUI response missing prompt_id")
        return self._result(request,prompt_id)

    def edit(self, request: AssetGenerationRequest, images: list[str], **options: object) -> AssetGenerationResult:
        if len(images) != 1 or options or not request.model_id:
            raise ValueError("COMFYUI_EDIT_SINGLE_REFERENCE_AND_CHECKPOINT_REQUIRED")
        import hashlib
        import re
        from .media_files import inspect_image
        validate_image_parameters(request.parameters, self.edit_supported_parameters)
        value=images[0]
        if not isinstance(value,str) or not value.startswith("data:image/") or ";base64," not in value or len(value)>36*1024*1024:
            raise ValueError("IMAGE_EDIT_VERIFIED_INLINE_REFERENCE_REQUIRED")
        data=base64.b64decode(value.split(";base64,",1)[1],validate=True)
        if not data or len(data)>25*1024*1024: raise ValueError("IMAGE_EDIT_REFERENCE_LIMIT")
        measured=inspect_image(data)
        filename="studio-"+hashlib.sha256(request.task_id.encode()).hexdigest()+"."+measured["extension"]
        workflow=self._workflow(request)
        if request.dispatch_guard is not None: request.dispatch_guard()
        uploaded=self.transport.post(self.endpoint+"/upload/image",files={"image":(filename,data,measured["media_type"])},
            data={"type":"input","overwrite":"false"},timeout=30)
        uploaded.raise_for_status(); name=uploaded.json().get("name")
        if not isinstance(name,str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,239}",name) or ".." in name:
            raise ValueError("COMFYUI_UPLOAD_RECEIPT_INVALID")
        workflow["10"]={"class_type":"LoadImage","inputs":{"image":name}}
        workflow["5"]={"class_type":"VAEEncode","inputs":{"pixels":["10",0],"vae":["4",2]}}
        workflow["3"]["inputs"]["denoise"]=0.6
        if request.dispatch_guard is not None: request.dispatch_guard()
        response=self.transport.post(self.endpoint+"/prompt",json={"prompt":workflow},timeout=15)
        response.raise_for_status(); prompt_id=response.json().get("prompt_id")
        if not prompt_id: raise ValueError("ComfyUI response missing prompt_id")
        return self._result(request,prompt_id)

    def _result(self, request, prompt_id):
        for _ in range(120):
            if request.dispatch_guard is not None: request.dispatch_guard()
            history=self.transport.get(self.endpoint+"/history/"+quote(str(prompt_id),safe=""),timeout=10);history.raise_for_status()
            entry=history.json().get(str(prompt_id)) or {}
            for output in (entry.get("outputs") or {}).values():
                images=output.get("images") or []
                if images:
                    image=images[0]
                    if request.dispatch_guard is not None: request.dispatch_guard()
                    if request.dispatch_guard is not None:
                        from urllib.parse import urlencode
                        from .media_files import fetch_media_bytes, inspect_image
                        url=self.endpoint+"/view?"+urlencode({"filename":image.get("filename"),"subfolder":image.get("subfolder",''),"type":image.get("type",'output')})
                        content=fetch_media_bytes(url,25*1024*1024,configured_provider_endpoint=self.endpoint)
                        request.dispatch_guard()
                        measured=inspect_image(content)
                        uri="data:"+measured["media_type"]+";base64,"+base64.b64encode(content).decode('ascii')
                    else:
                        binary=self.transport.get(self.endpoint+"/view",params={"filename":image.get("filename"),"subfolder":image.get("subfolder",''),"type":image.get("type",'output')},timeout=30)
                        binary.raise_for_status();uri="data:image/png;base64,"+base64.b64encode(binary.content).decode('ascii')
                    return AssetGenerationResult(request.provider_id,request.model_id,uri)
            time.sleep(.5)
        raise ValueError("ComfyUI generation timed out")

def build_openai_compatible_from_vault(transport, provider_id: str, endpoint: str, vault):
    secret=vault.resolve(provider_id)
    if not secret: raise ValueError(f"credential is not configured: {provider_id}")
    return OpenAICompatibleImageProvider(transport,secret,endpoint)

def _verified_inline_image(value):
    from .media_files import inspect_image
    if not isinstance(value,str) or not value.startswith('data:image/') or ';base64,' not in value or len(value)>36*1024*1024:
        raise ValueError('IMAGE_EDIT_VERIFIED_INLINE_REFERENCE_REQUIRED')
    try:data=base64.b64decode(value.split(';base64,',1)[1],validate=True)
    except ValueError:raise ValueError('IMAGE_EDIT_VERIFIED_INLINE_REFERENCE_REQUIRED') from None
    if not data or len(data)>25*1024*1024:raise ValueError('IMAGE_EDIT_REFERENCE_LIMIT')
    return data,inspect_image(data)
