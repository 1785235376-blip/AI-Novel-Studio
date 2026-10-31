import os,sys,socket
from pathlib import Path
root=Path(os.environ['PROJECT_ROOT']).resolve();sys.path[:0]=[str(root),str(root/'tests')];os.chdir(root)
def denied(*a,**kw):raise AssertionError('External network forbidden in independent review')
socket.socket.connect=denied;socket.create_connection=denied
import pytest
import app.dependencies as dep, app.adaptation_api as api
for mod in (dep,api):
    assert Path(mod.__file__).is_relative_to(root)
    print('VERIFIED_IMPORT',mod.__file__,flush=True)
class RestoreCheck:
    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_protocol(self,item,nextitem):
        keys=('EXPERIMENTAL_FEATURES','V1_ACCEPTANCE_MODE')
        before={k:os.environ.get(k) for k in keys}
        yield
        after={k:os.environ.get(k) for k in keys}
        assert after==before,(item.nodeid,before,after)
        print('ENV_RESTORED',item.nodeid,before,flush=True)
raise SystemExit(pytest.main(sys.argv[1:],plugins=[RestoreCheck()]))
