import os, sys, socket
from pathlib import Path
root=Path(os.environ['PROJECT_ROOT']); sys.path[:0]=[str(root),str(root/'tests')]; os.chdir(root)
def denied(*args,**kwargs): raise AssertionError('Network prohibited in adaptation fixture verification')
socket.socket.connect=denied; socket.create_connection=denied
import app.dependencies, app.adaptation_api
print('IMPORTS',app.dependencies.__file__,app.adaptation_api.__file__,flush=True)
import pytest
raise SystemExit(pytest.main(sys.argv[1:]))
