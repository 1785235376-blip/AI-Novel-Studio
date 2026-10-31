import hashlib, json, pathlib, socket, sys
attempts=[]
def no_network(self, address):
    attempts.append(repr(address))
    raise AssertionError('Network disabled for combined verification')
socket.socket.connect=no_network
socket.socket.connect_ex=no_network
if __name__ == '__main__':
    import app.jobs, app.api, app.idempotency, app.services.generation_admission_receipt
    root=pathlib.Path.cwd().resolve()
    modules=[app.jobs,app.api,app.idempotency,app.services.generation_admission_receipt]
    paths=['app/jobs.py','app/api.py','app/idempotency.py','app/services/generation_admission_receipt.py']
    verified={}
    for module, relative in zip(modules,paths):
        path=pathlib.Path(module.__file__).resolve()
        assert path == root/relative, str(path)
        verified[relative]=hashlib.sha256(path.read_bytes()).hexdigest()
    print(json.dumps({'verified_primary_imports':verified,'cwd':str(root)}),flush=True)
    import pytest
    result=pytest.main(sys.argv[1:])
    print(json.dumps({'network_attempts':attempts,'pytest_exit':int(result)}),flush=True)
    raise SystemExit(result if not attempts else 99)
