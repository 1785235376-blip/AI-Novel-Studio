import io,json,os,secrets,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from app.packaging.host_uplink import CREDENTIAL_PREFIX,parse_host_credential
from app.packaging.control_pipe import PackagedControlReader,credential_store

def main():
    runtime='test-runtime'; fake=secrets.token_urlsafe(24); base={'protocol':'packaged-host-credential/v1','type':'SET_PROVIDER_CREDENTIAL','runtime_instance_id':runtime,'provider':'deepseek','credential':fake}
    variants=[]
    for change in ({'credential':None},{'credential':''},{'credential':7},{'extra':1},{'type':'UNKNOWN'},{'provider':'other'},{'protocol':'wrong'},{'runtime_instance_id':'wrong'},{'credential':'x'*1025},{'credential':'x\0'},{'credential':'x\r'},{'credential':'x\n'}):
        v=dict(base); v.update(change)
        if change.get('credential') is None: v.pop('credential',None)
        variants.append(v)
    clear=dict(base,type='CLEAR_PROVIDER_CREDENTIAL'); variants.extend([clear,{**clear,'extra':1}])
    host_ok=all(parse_host_credential(CREDENTIAL_PREFIX+json.dumps(v,separators=(',',':')),runtime) is None for v in variants)
    backend=[]
    for v in variants:
        x=dict(v); x['protocol']='packaged-credential/v1'; backend.append((json.dumps(x,separators=(',',':'))+'\n').encode())
    credential_store.clear('deepseek')
    for frame in backend: PackagedControlReader(runtime,io.BytesIO(frame))._read()
    backend_ok=not credential_store.has('deepseek')
    code='''import os\nfrom app.packaging.control_pipe import credential_store\nfrom app.openai_compatible import OpenAICompatibleTextProvider,CompatibleProviderConfig\ncredential_store.clear("deepseek")\np=OpenAICompatibleTextProvider(CompatibleProviderConfig("deepseek","http://127.0.0.1","DEEPSEEK_API_KEY"))\ntry:\n p._key(); raise SystemExit(1)\nexcept Exception:\n raise SystemExit(0)'''
    env=dict(os.environ,PACKAGED_WINDOWS_MODE='true',DEEPSEEK_API_KEY=secrets.token_urlsafe(24)); packaged=subprocess.run([sys.executable,'-c',code],env=env,cwd=Path(__file__).resolve().parents[2]).returncode==0
    env2=dict(os.environ,PACKAGED_WINDOWS_MODE='false',DEEPSEEK_API_KEY=secrets.token_urlsafe(24)); nonpack=subprocess.run([sys.executable,'-c',code.replace('raise SystemExit(1)','raise SystemExit(0)').replace('except Exception:\n raise SystemExit(0)','except Exception:\n raise SystemExit(1)')],env=env2,cwd=Path(__file__).resolve().parents[2]).returncode==0
    if not(host_ok and backend_ok and packaged and nonpack): return 1
    print('MALFORMED_HOST_CREDENTIAL_MATRIX=PASS'); print('MALFORMED_BACKEND_CREDENTIAL_MATRIX=PASS'); print('NUL_CREDENTIAL=REJECTED'); print('CR_CREDENTIAL=REJECTED'); print('LF_CREDENTIAL=REJECTED'); print('PACKAGED_ENV_FALLBACK_TEST=PASS'); print('NON_PACKAGED_PROVIDER_ENV_REGRESSION=PASS'); return 0
if __name__=='__main__':raise SystemExit(main())
