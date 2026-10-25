import os, pathlib, socket, sys
ROOT=pathlib.Path(__file__).resolve().parents[2]
EVIDENCE=pathlib.Path(__file__).resolve().parent
for k in list(os.environ):
    if any(s in k for s in ('API_KEY','DATABASE_URL','PROVIDER','TOKEN','SECRET')): os.environ.pop(k,None)
for k,part in [('HOME','home'),('XDG_CONFIG_HOME','config'),('XDG_CACHE_HOME','cache'),('XDG_DATA_HOME','data'),('TMPDIR','tmp'),('NOVEL_DATA_PATH','novel_data')]:
    p=EVIDENCE/'isolated'/part;p.mkdir(parents=True,exist_ok=True);os.environ[k]=str(p)
os.environ.update(PROJECT_ROOT=str(ROOT),STORAGE_BACKEND='file',CREDENTIAL_VAULT_BACKEND='memory')
os.chdir(ROOT);sys.path.insert(0,str(ROOT))
def deny(*a,**kw): raise RuntimeError('Independent review network forbidden')
socket.socket.connect=deny;socket.socket.connect_ex=deny;socket.create_connection=deny
if __name__=='__main__':
    import pytest
    raise SystemExit(pytest.main(['-q',str(EVIDENCE/'test_independent.py'),'--junitxml='+str(EVIDENCE/'result.xml')]+sys.argv[1:]))
