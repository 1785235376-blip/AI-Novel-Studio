import json,subprocess,sys
from pathlib import Path
out=Path(__file__).parent;root=out.parent/'mixed-recovery-final2-freeze';groups=json.loads((out/'groups.json').read_text());groups={'focused-context':['tests/test_file_usage_request_context.py','tests/test_file_safety_observer_context.py','tests/test_usage_request_context_tcp.py'],**groups}
for name in ['focused-context','resource-core','taskcenter-lifecycle','export-consumers-corrected','asset-regressions','compound-http']:
 args=groups[name]
 p=subprocess.run([sys.executable,str(out/'run_group.py'),str(root),str(out/'final2'),name,*args]); print('GROUP_DONE',name,p.returncode,flush=True)
