import json, os, re
from pathlib import Path
from .storage import atomic_write

def config_path()->Path:
    return Path(os.getenv('ASSET_PROVIDER_CONFIG_PATH', str(Path.home()/'.ai-novel-studio'/'asset-providers.json')))
def load()->dict:
    path=config_path()
    if not path.exists(): return {}
    try: return json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError): return {}
def save(provider_id:str,endpoint:str,default_model:str,*,api_style:str="openai",local:bool=False,enabled:bool=True,requires_credential:bool=True,display_name:str="")->dict:
    if not provider_id or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', provider_id): raise ValueError('invalid provider configuration')
    if not endpoint.startswith(('http://','https://')): raise ValueError('invalid provider configuration')
    if api_style not in {'openai','comfyui','automatic1111'}: raise ValueError('invalid provider configuration')
    data=load(); data[provider_id]={'endpoint':endpoint.rstrip('/'),'default_model':default_model.strip(),'api_style':api_style,'local':bool(local),'enabled':bool(enabled),'requires_credential':bool(requires_credential),'display_name':str(display_name or provider_id)[:120]}
    atomic_write(config_path(),json.dumps(data,ensure_ascii=False,indent=2)); return {'endpoint':data[provider_id]['endpoint'],'default_model':data[provider_id]['default_model']}

def delete(provider_id: str) -> bool:
    data = load()
    if provider_id not in data:
        return False
    del data[provider_id]
    atomic_write(config_path(), json.dumps(data, ensure_ascii=False, indent=2))
    return True
