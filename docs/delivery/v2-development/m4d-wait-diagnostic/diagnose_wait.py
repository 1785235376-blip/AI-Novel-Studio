"""One unchanged historical case with read-only call timing observations."""
import hashlib, json, time
from pathlib import Path
import pytest
root=Path.cwd(); out=root/'.runtime/m4d/wait-diagnostic';out.mkdir(exist_ok=False)
node='tests/test_v2_creative_workflows.py::test_untrusted_model_json_is_discarded_without_derived_write[postgres-/api/v1-not json]'
source=root/'tests/test_v2_creative_workflows.py';before=hashlib.sha256(source.read_bytes()).hexdigest()
class Observe:
    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_call(self, item):
        e=item.funcargs['creative_model']; original=e.client.get; rows=[]; start=time.monotonic()
        def observed_get(*args,**kwargs):
            tick=time.monotonic();response=original(*args,**kwargs)
            if '/model-broker/jobs/' in str(args[0]):
                body=response.json(); rows.append({'started_seconds':tick-start,'elapsed_seconds':time.monotonic()-tick,
                    'http_status':response.status_code,'ledger_status':body.get('ledger',{}).get('status'),
                    'job_status':(body.get('job') or {}).get('status'),
                    'job_terminal_hook_status':(body.get('job') or {}).get('terminal_hook_status')})
            return response
        e.client.get=observed_get
        outcome=yield
        e.client.get=original
        result={'nodeid':item.nodeid,'elapsed_seconds':time.monotonic()-start,'failed':bool(outcome.excinfo),
            'reads':rows,'job_states':[{'id':j.id,'status':j.status,'terminal_hook_status':j.terminal_hook_status} for j in e.manager.jobs.values()],
            'original_test_sha256':before,'original_test_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==before,
            'diagnostic_only':True,'changed_waits_assertions_or_product':False}
        (out/'observation.json').write_text(json.dumps(result,indent=2)+'\n')
status=pytest.main(['-q',node,'--tb=short','--basetemp=.runtime/m4d/wait-diagnostic/pytest','--junitxml=.runtime/m4d/wait-diagnostic/junit.xml'],plugins=[Observe()])
raise SystemExit(status)
