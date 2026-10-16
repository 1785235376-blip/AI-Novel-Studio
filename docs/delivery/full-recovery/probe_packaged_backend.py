"""Actual packaged runtime owner startup; no DesktopHost/bootstrap simulation."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.request

from app.packaging.packaged_launcher import create_packaged_backend_runtime
from app.packaging.paths import WindowsPackagingPaths
from app.packaging.runtime_identity import RuntimeRole

application=Path(sys.argv[1]).resolve()
sandbox=Path(sys.argv[2]).resolve()
receipt_path=Path(sys.argv[3]).resolve()
source_sha=sys.argv[4]
assert not sandbox.exists()
sandbox.mkdir(parents=True)
paths=WindowsPackagingPaths.resolve(local_app_data=sandbox/'localappdata',user_profile=sandbox/'profile')
runtime,factory=create_packaged_backend_runtime(application=application,paths=paths)
record={'status':'RUNNING','source_commit':source_sha,
        'evidence_boundary':'Actual packaged native Windows runtime owner, fresh PostgreSQL/backend; no WebView2 interaction or simulated host authentication',
        'start_utc':datetime.now(timezone.utc).isoformat(),'python':sys.version,'application':str(application),
        'sandbox':str(sandbox),'host_bootstrap_exchange':'NOT RUN','webview2_interaction':'NOT RUN'}
started=time.monotonic()
try:
    identity=runtime.startup()
    ports=runtime.reservations.ports
    origin='http://127.0.0.1:'+str(ports[RuntimeRole.BACKEND])
    record['public_runtime_metadata']=factory.config.public_runtime_metadata(database_port=ports[RuntimeRole.POSTGRESQL],backend_port=ports[RuntimeRole.BACKEND])
    with urllib.request.urlopen(origin+'/health',timeout=5) as response:
        health=json.load(response)
        assert response.status==200 and health['version']==factory.config.version
        record['health']={'status':response.status,'version':health['version']}
    with urllib.request.urlopen(origin+'/',timeout=5) as response:
        html=response.read()
        assert response.status==200 and html==(application/'Frontend/dist/index.html').read_bytes()
        record['frontend_index']={'status':response.status,'bytes':len(html),'sha256':hashlib.sha256(html).hexdigest(),'exact_staged_bytes':True}
    references=re.findall(r'(?:src|href)=["\'](/assets/[^"\']+)["\']',html.decode())
    assert references
    record['frontend_assets']=[]
    for relative in references:
        with urllib.request.urlopen(origin+relative,timeout=5) as response:
            body=response.read()
            assert response.status==200 and body==(application/'Frontend/dist'/relative.lstrip('/')).read_bytes()
            record['frontend_assets'].append({'path':relative,'status':200,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),'exact_staged_bytes':True})
    try:
        urllib.request.urlopen(origin+'/api/v1/agent-jobs',timeout=5)
        raise AssertionError('Unauthenticated protected endpoint succeeded')
    except urllib.error.HTTPError as error:
        assert error.code==401,error.code
        record['protected_unauthenticated']={'path':'/api/v1/agent-jobs','status':error.code}
    record['status']='PASS'
except BaseException as error:
    record['status']='FAILED'
    record['error_type']=type(error).__name__
    record['error']=str(error)
    raise
finally:
    try:
        children=tuple(runtime.children.values())
        runtime.shutdown()
        record['cleanup_state']=runtime.state.value
        record['all_children_stopped']=all(not child.is_running() for child in children)
        record['native_child_count']=len(children)
        assert record['all_children_stopped']
    except BaseException as error:
        record['status']='FAILED'
        record['shutdown_error_type']=type(error).__name__
        record['shutdown_error']=str(error)
        raise
    finally:
        record['elapsed_seconds']=round(time.monotonic()-started,3)
        record['end_utc']=datetime.now(timezone.utc).isoformat()
        record['events']=runtime.events
        receipt_path.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':record['status'],'elapsed_seconds':record['elapsed_seconds'],'all_children_stopped':record['all_children_stopped']}))
