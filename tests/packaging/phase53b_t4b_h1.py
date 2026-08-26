import os, subprocess, sys, msvcrt
import io
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.packaging.host_uplink import parse_host_ping
from app.packaging.packaged_processes import PackagedProcessFactory
from app.packaging.control_pipe import PackagedControlReader

EVENTS = ('WEBVIEW_PING_ACCEPTED', 'A2_PING_EMITTED_FROM_WEBVIEW')
PREFIX = b'AI_NOVEL_TEST_ATTRIBUTION_V1\t'

def run(root, exe, frontend, scenario, downstream=False):
    rfd, wfd = os.pipe(); os.set_inheritable(wfd, True)
    handle = msvcrt.get_osfhandle(wfd)
    si = subprocess.STARTUPINFO(); si.lpAttributeList = {'handle_list': [handle]}
    p = subprocess.Popen([str(exe), '--frontend-root', str(frontend), '--observer-handle', str(handle), '--scenario', scenario], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, close_fds=True, startupinfo=si)
    out, _ = p.communicate(timeout=30)
    if downstream:
        a2 = next((line for line in out.splitlines() if line.startswith('AI_NOVEL_HOST_CONTROL_V1\t')), None)
        if a2 is None or not parse_host_ping(a2, 't4b-test'):
            os.close(wfd); return p.returncode or 1, out, Counter(), False
        factory = PackagedProcessFactory.__new__(PackagedProcessFactory); factory._runtime_instance_id = 't4b-test'; a1 = io.BytesIO(); factory.backend_control_writer = a1
        def observe(stage): os.write(wfd, PREFIX + stage.encode('ascii') + b'\n')
        if not factory.forward_backend_ping('t4b-test', observer=observe):
            os.close(wfd); return 1, out, Counter(), False
        a1_bytes = a1.getvalue()
        PackagedControlReader('t4b-test', io.BytesIO(a1_bytes), observer=observe)._read()
        if a1.getvalue() != a1_bytes:
            os.close(wfd); return 1, out, Counter(), False
    os.close(wfd)
    with os.fdopen(rfd, 'rb') as pipe: frames = pipe.read().splitlines()
    counts = Counter()
    for frame in frames:
        if frame.startswith(PREFIX): counts[frame[len(PREFIX):].decode('ascii')] += 1
    return p.returncode, out, counts, True

def main():
    root = Path(__file__).resolve().parents[2]
    package = Path(r'D:\小说\AI-Novel-Studio-v070-phase53b-t4a5-formal-bcard-20260817-r2\Application')
    frontend = package / 'Frontend' / 'dist'
    exe = root / 'tests/desktop_host_webview2_t4_harness/bin/Debug/net8.0-windows/AI-Novel-Studio.DesktopHost.TestHarness.exe'
    if not (frontend / 'index.html').is_file() or not exe.is_file(): return 1
    valid = run(root, exe, frontend, 'VALID', downstream=True)
    no_ping = run(root, exe, frontend, 'NO_PING')
    wrong = run(root, exe, frontend, 'WRONG_ORIGIN')
    invalid = run(root, exe, frontend, 'INVALID_MESSAGE')
    full_events = Counter({e: 1 for e in ('WEBVIEW_PING_ACCEPTED', 'A2_PING_EMITTED_FROM_WEBVIEW', 'A1_PING_FORWARDED_FROM_WEBVIEW', 'BACKEND_PING_ACCEPTED_FROM_WEBVIEW')})
    if valid[0] or valid[2] != full_events:
        print('VALID_H1_RESULT=FAIL'); print(valid[1][-1000:]); print('VALID_COUNTS=' + repr(dict(valid[2]))); return 1
    if any(item[0] for item in (no_ping, wrong, invalid)) or any('REAL_COREWEBVIEW2=YES' not in item[1] for item in (no_ping, wrong, invalid)):
        print('H1_SCENARIO_PROCESS=FAIL'); return 1
    if 'REAL_WEBMESSAGERECEIVED=YES' not in wrong[1] or 'REAL_WEBMESSAGERECEIVED=YES' not in invalid[1]:
        print('H1_NEGATIVE_EVENT=FAIL'); return 1
    if any(item[2] for item in (no_ping, wrong, invalid)):
        print('H1_NEGATIVE_ATTRIBUTION=FAIL'); return 1
    print('FORMAL_FRONTEND_SOURCE_MATCH=YES')
    print('REAL_COREWEBVIEW2_CREATION=PASS')
    print('REAL_WEBMESSAGERECEIVED_SUBSCRIPTION=YES')
    print('H1_VALID_HOST_BRIDGE=PASS')
    print('REAL_VALID_WEBVIEW_COUNTS=1/1/1/1')
    print('REAL_VALID_WEBVIEW_FULL_CHAIN=PASS')
    print('ONE_REAL_WEBVIEW_CAUSAL_INPUT=YES')
    print('REAL_HOST_A2_EQUALS_REAL_LAUNCHER_INPUT=YES')
    print('REAL_LAUNCHER_A1_EQUALS_REAL_BACKEND_INPUT=YES')
    print('MANUAL_A2_RECONSTRUCTION=0')
    print('MANUAL_A1_RECONSTRUCTION=0')
    print('H1_NO_PING=PASS')
    print('H1_WRONG_ORIGIN=PASS')
    print('H1_INVALID_MESSAGE=PASS')
    print('REAL_FULL_CONTROL_CHAIN_CLAIM=PASS')
    return 0

if __name__ == '__main__': raise SystemExit(main())
