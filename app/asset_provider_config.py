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
def save(provider_id:str,endpoint:str,default_model:str)->dict:
    if not provider_id or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', provider_id): raise ValueError('invalid provider configuration')
    if not endpoint.startswith(('http://','https://')): raise ValueError('invalid provider configuration')
    data=load(); data[provider_id]={'endpoint':endpoint.rstrip('/'),'default_model':default_model.strip()}
    atomic_write(config_path(),json.dumps(data,ensure_ascii=False,indent=2)); return data[provider_id]

def delete(provider_id: str) -> bool:
    data = load()
    if provider_id not in data:
        return False
    del data[provider_id]
    atomic_write(config_path(), json.dumps(data, ensure_ascii=False, indent=2))
    return True
