from datetime import datetime, timezone
from hashlib import sha256
import json, os
from pathlib import Path
import subprocess, sys
from scripts.run_v2_checks import isolated_environment, source_snapshot
root=Path.cwd(); owned=root/'.runtime/m4c-size-fix'; label=sys.argv[1]
env=os.environ.copy()
for key in list(env):
    if key.endswith(('_API_KEY','_TOKEN','_SECRET')) or key in {'DATABASE_URL','TEST_POSTGRES_DATABASE_URL','E2E_DATABASE_URL','COLLABORATION_DEV_SESSIONS_JSON','PACKAGED_CONTROL_PIPE'}:
        env.pop(key,None)
env.update(isolated_environment(root,owned/label/'profile'))
env['PYTHONPATH']=str(root)+os.pathsep+str(root/'tests')
targets=sys.argv[2:] or [str(owned/'test_receipt_size_admission.py')]
plugins=[] if sys.argv[2:] else ['-p','conftest']
command=[sys.executable,'-m','pytest','-q',*plugins,*targets,'-m','not postgres_backend_only','--basetemp='+str(owned/label/'basetemp')]
before=source_snapshot(root); started=datetime.now(timezone.utc).isoformat()
r=subprocess.run(command,cwd=root,env=env,text=True,capture_output=True)
(owned/(label+'.log')).write_text(r.stdout+r.stderr)
receipt={'command':command,'started':started,'finished':datetime.now(timezone.utc).isoformat(),'exit_code':r.returncode,'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'source_before':before,'source_after':source_snapshot(root),'test_sha256':sha256((owned/'test_receipt_size_admission.py').read_bytes()).hexdigest()}
(owned/(label+'.json')).write_text(json.dumps(receipt,indent=2)+'\n')
print(r.stdout+r.stderr); sys.exit(r.returncode)
