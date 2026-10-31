# Offline metadata protocol only: no actual local model/server inference.
import os, socket, sys
from pathlib import Path
root=Path.cwd(); sys.path.insert(0,str(root))
run=root/'.runtime/file-keyed-activation/local-route'
for part in ('home','xdg','data','tmp'): (run/part).mkdir(parents=True,exist_ok=True)
os.environ.update(PROJECT_ROOT=str(root),HOME=str(run/'home'),XDG_CONFIG_HOME=str(run/'xdg'),
    XDG_DATA_HOME=str(run/'xdg'),NOVEL_DATA_PATH=str(run/'data'),STORAGE_BACKEND='file',
    CREDENTIAL_VAULT_BACKEND='memory',TMPDIR=str(run/'tmp'))
def blocked(*args,**kwargs):raise AssertionError('network not permitted')
socket.socket.connect=blocked;socket.create_connection=blocked;socket.getaddrinfo=blocked
from app.runtime import Runtime
from app.stable_identity import StableIdentityStore
from app.model_center.discovery import LocalDiscoveryService
from app.model_center.discovery_bridge import LocalDiscoveryBridge, LocalTextAdapter
from app.asset_providers import AssetProviderRegistry
from app.services.file_generation_execution import classify_route
runtime=Runtime(StableIdentityStore(run/'identities.json'))
service=LocalDiscoveryService(None)
bridge=LocalDiscoveryBridge(service,runtime,AssetProviderRegistry())
candidate={'id':'local-protocol-model','provider_id':'local-protocol-provider','display_name':'Protocol only',
    'runtime_type':'OLLAMA','enabled':True,'enable_eligible':True,'verified_capabilities':['TEXT'],
    'source_locality':'LOCAL_VERIFIED','model_evidence_fingerprint':'offline-evidence',
    'runtime_config':{'type':'OLLAMA','management':'EXTERNAL','endpoint':'http://127.0.0.1:11434'}}
service.registrations[candidate['id']]=candidate
bridge(candidate)
assert type(runtime.provider_registry.resolve(candidate['provider_id'])) is LocalTextAdapter
payload={'provider_id':candidate['provider_id'],'model_id':candidate['id']}
route=classify_route(runtime,payload)
assert (route.provider,route.model)==(candidate['provider_id'],candidate['id'])
for field,value in [('source_locality','REMOTE'),('model_evidence_fingerprint','')]:
    old=candidate[field];candidate[field]=value
    try:classify_route(runtime,payload)
    except ValueError:pass
    else:raise AssertionError(field+' must refuse')
    candidate[field]=old
candidate['runtime_config']['management']='MANAGED'
try:classify_route(runtime,payload)
except ValueError:pass
else:raise AssertionError('managed must refuse')
candidate['runtime_config']['management']='EXTERNAL'
candidate['enabled']=False
try:classify_route(runtime,payload)
except Exception:pass
else:raise AssertionError('disabled must refuse')
print('PASS: original LocalDiscoveryService/Bridge/LocalTextAdapter metadata family selection and locality, fingerprint, management, enabled refusals; socket-blocked; actual local-model inference NOT_RUN')
