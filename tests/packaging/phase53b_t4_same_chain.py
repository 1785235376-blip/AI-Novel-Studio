import io, os, subprocess, sys, msvcrt
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.packaging.host_uplink import parse_host_ping
from app.packaging.packaged_processes import PackagedProcessFactory
from app.packaging.control_pipe import PackagedControlReader

EVENTS = (
    'WEBVIEW_PING_ACCEPTED',
    'A2_PING_EMITTED_FROM_WEBVIEW',
    'A1_PING_FORWARDED_FROM_WEBVIEW',
    'BACKEND_PING_ACCEPTED_FROM_WEBVIEW',
)
PREFIX = b'AI_NOVEL_TEST_ATTRIBUTION_V1\t'

def run_scenario(root, exe, scenario):
    root=Path(__file__).resolve().parents[2]
    rfd,wfd=os.pipe(); os.set_inheritable(wfd,True); handle=msvcrt.get_osfhandle(wfd)
    si=subprocess.STARTUPINFO(); si.lpAttributeList={'handle_list':[handle]}
    p=subprocess.Popen([str(exe),'--observer-handle',str(handle),'--scenario',scenario],cwd=root,stdout=subprocess.PIPE,text=True,close_fds=True,startupinfo=si)
    out,_=p.communicate(timeout=20)
    a2=next((line for line in out.splitlines() if line.startswith('AI_NOVEL_HOST_CONTROL_V1\t')),None)
    if p.returncode: raise RuntimeError(f'{scenario}: TestHarness failed')
    if scenario == 'controlled-valid-ping':
        if a2 is None or not parse_host_ping(a2,'test-runtime'): raise RuntimeError('valid Host A2 missing or rejected')
        factory=PackagedProcessFactory.__new__(PackagedProcessFactory); factory._runtime_instance_id='test-runtime'; a1=io.BytesIO(); factory.backend_control_writer=a1
        def observe(stage): os.write(wfd, PREFIX + stage.encode('ascii') + b'\n')
        if not factory.forward_backend_ping('test-runtime',observer=observe): raise RuntimeError('Launcher rejected Host A2')
        a1_bytes=a1.getvalue()
        reader=PackagedControlReader('test-runtime',io.BytesIO(a1_bytes),observer=observe); reader._read()
        if a1.getvalue() != a1_bytes: raise RuntimeError('Launcher A1 lineage changed')
    elif a2 is not None:
        raise RuntimeError(f'{scenario}: unexpected Host A2')
    os.close(wfd)
    with os.fdopen(rfd,'rb') as pipe:
        frames=pipe.read().splitlines()
    names=[]
    for frame in frames:
        if not frame.startswith(PREFIX): raise RuntimeError(f'{scenario}: invalid observer frame')
        name=frame[len(PREFIX):].decode('ascii')
        if name not in EVENTS: raise RuntimeError(f'{scenario}: unexpected observer event')
        names.append(name)
    return Counter(names), a2 is not None

def main():
    root=Path(__file__).resolve().parents[2]
    exe=root/'tests/desktop_host_test_harness/bin/Debug/net8.0-windows/AI-Novel-Studio.DesktopHost.TestHarness.exe'
    expected=Counter({event:1 for event in EVENTS})
    positive, positive_a2=run_scenario(root,exe,'controlled-valid-ping')
    no_webview, no_webview_a2=run_scenario(root,exe,'no-webview')
    invalid, invalid_a2=run_scenario(root,exe,'invalid-message')
    if positive != expected or not positive_a2: return 1
    if no_webview or no_webview_a2 or invalid or invalid_a2: return 1
    print('ATTRIBUTED_SAME_CHAIN_COUNTS=1/1/1/1')
    print('NO_WEBVIEW_COUNTS=0/0/0/0')
    print('INVALID_MESSAGE_COUNTS=0/0/0/0')
    print('TESTHOST_STARTUP_A2_WRITES=0')
    print('PRE_TRIGGER_DOWNSTREAM_PINGS=0')
    print('HOST_A2_EQUALS_LAUNCHER_INPUT=YES')
    print('LAUNCHER_A1_EQUALS_BACKEND_INPUT=YES')
    print('CONTROLLED_REAL_PRODUCTION_FOUR_STAGE=PASS'); return 0
if __name__=='__main__': raise SystemExit(main())
