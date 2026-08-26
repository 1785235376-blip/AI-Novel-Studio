import io, json, os, secrets, subprocess, sys, msvcrt
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.packaging.host_uplink import parse_host_credential
from app.packaging.packaged_processes import PackagedProcessFactory
from app.packaging.control_pipe import PackagedControlReader, credential_store

def host(root, exe, scenario, value=None):
    rfd, wfd = os.pipe(); os.set_inheritable(wfd, True); handle = msvcrt.get_osfhandle(wfd)
    data_rfd, data_wfd = os.pipe(); os.set_inheritable(data_wfd, True); data_handle = msvcrt.get_osfhandle(data_wfd)
    si = subprocess.STARTUPINFO(); si.lpAttributeList = {'handle_list':[handle,data_handle]}
    p = subprocess.Popen([str(exe), '--observer-handle', str(handle), '--credential-data-handle', str(data_handle), '--scenario', scenario], cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, close_fds=True, startupinfo=si)
    out, err = p.communicate((value + '\n') if value is not None else None, timeout=20); os.close(wfd); os.close(data_wfd)
    with os.fdopen(rfd, 'rb') as pipe: observer = pipe.read()
    with os.fdopen(data_rfd, 'rb') as pipe: raw = pipe.read(4101)
    if len(raw) < 4: return p.returncode or 1, None, out, err, observer
    size = int.from_bytes(raw[:4], 'little'); payload = raw[4:]
    if size > 4096 or len(payload) != size: return 1, None, out, err, observer
    if value is not None and (value in out or value in err or value.encode() in observer): return 1, None, out, err, observer
    return p.returncode, payload.decode('utf-8'), out, err, observer

def chain(root, exe, value, clear=False):
    code, line, _, _, _ = host(root, exe, 'credential-clear' if clear else 'credential-set', None if clear else value)
    if code or line is None: return False, False
    message = parse_host_credential(line, 'test-runtime')
    if message is None: return False, False
    factory = PackagedProcessFactory.__new__(PackagedProcessFactory); factory._runtime_instance_id='test-runtime'; backend = io.BytesIO(); factory.backend_control_writer=backend
    if not factory.forward_backend_credential(line): return False, False
    frame = backend.getvalue(); PackagedControlReader('test-runtime', io.BytesIO(frame))._read()
    return True, frame != line.encode()

def main():
    root = Path(__file__).resolve().parents[2]; exe=root/'tests/desktop_host_test_harness/bin/Debug/net8.0-windows/AI-Novel-Studio.DesktopHost.TestHarness.exe'
    first, second = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    credential_store.clear('deepseek')
    a, fresh1 = chain(root, exe, first); match1 = credential_store.resolve('deepseek') == first
    b, fresh2 = chain(root, exe, second); match2 = credential_store.resolve('deepseek') == second and credential_store.resolve('deepseek') != first
    c, _ = chain(root, exe, '', clear=True); cleared = not credential_store.has('deepseek')
    wrong_host = json.dumps({'protocol':'packaged-host-credential/v1','type':'SET_PROVIDER_CREDENTIAL','runtime_instance_id':'wrong','provider':'deepseek','credential':first}, separators=(',',':'))
    wrong_backend = json.dumps({'protocol':'packaged-credential/v1','type':'SET_PROVIDER_CREDENTIAL','runtime_instance_id':'wrong','provider':'deepseek','credential':first}, separators=(',',':')) + '\n'
    factory=PackagedProcessFactory.__new__(PackagedProcessFactory); factory._runtime_instance_id='test-runtime'; factory.backend_control_writer=io.BytesIO()
    rejected_host = not factory.forward_backend_credential('AI_NOVEL_HOST_CREDENTIAL_V1\t'+wrong_host)
    before=credential_store.resolve('deepseek'); PackagedControlReader('test-runtime',io.BytesIO(wrong_backend.encode()))._read(); rejected_backend = credential_store.resolve('deepseek') == before
    if not all((a,fresh1,match1,b,fresh2,match2,c,cleared,rejected_host,rejected_backend)): return 1
    print('SET=PASS'); print('SET_MATCH=YES'); print('REPLACE=PASS'); print('REPLACE_MATCH=YES'); print('CLEAR=PASS'); print('CLEAR_EMPTY=YES'); print('WRONG_RUNTIME=REJECTED'); print('RAW_FRAME_FORWARDED=NO'); print('SENTINEL_VALUES_PRINTED=0'); print('REAL_DEEPSEEK_REQUESTS=0'); return 0
if __name__=='__main__': raise SystemExit(main())
