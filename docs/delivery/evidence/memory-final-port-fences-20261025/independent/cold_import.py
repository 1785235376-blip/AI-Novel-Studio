import socket,sys,importlib

def denied(*a,**kw):raise AssertionError('cold import network prohibited')
socket.socket.connect=denied
socket.socket.connect_ex=denied
socket.create_connection=denied
socket.getaddrinfo=denied
for name in sys.argv[1:]:
    importlib.import_module(name)
    print('IMPORTED',name,flush=True)
from app.main import app
from app.runtime import runtime
assert app is not None and runtime is not None
print('COMPOSITION_READY',flush=True)
