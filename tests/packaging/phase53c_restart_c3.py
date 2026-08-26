import io, os, secrets, subprocess, sys, msvcrt, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.packaging.host_uplink import CREDENTIAL_PREFIX
from app.packaging.packaged_processes import PackagedProcessFactory
from tests.packaging.phase53c_a1_c1 import host

def start(root, python):
    rfd,wfd=os.pipe(); os.set_inheritable(rfd,True); handle=msvcrt.get_osfhandle(rfd)
    si=subprocess.STARTUPINFO(); si.lpAttributeList={'handle_list':[handle]}
    child=subprocess.Popen([str(python),str(root/'tests/packaging/phase53c_test_backend_process.py'),'--control-handle',str(handle),'--runtime','test-runtime'],cwd=root,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,close_fds=True,startupinfo=si)
    os.close(rfd); return child,wfd

def status(child):
    child.stdin.write('STATUS\n'); child.stdin.flush(); return child.stdout.readline().strip()

def stop(child,wfd):
    os.close(wfd); child.stdin.write('EXIT\n'); child.stdin.flush(); child.wait(timeout=10)

def main():
    root=Path(__file__).resolve().parents[2]; python=root/'.venv/Scripts/python.exe'; exe=root/'tests/desktop_host_test_harness/bin/Debug/net8.0-windows/AI-Novel-Studio.DesktopHost.TestHarness.exe'
    sentinel=secrets.token_urlsafe(32); code,line,_,_,_=host(root,exe,'credential-set',sentinel)
    if code or line is None: return 1
    child,wfd=start(root,python); factory=PackagedProcessFactory.__new__(PackagedProcessFactory); factory._runtime_instance_id='test-runtime'; factory.backend_control_writer=os.fdopen(wfd,'wb',closefd=False)
    if not factory.forward_backend_credential(line) or status(child)!='CONFIGURED=YES': return 1
    factory.backend_control_writer.close(); stop(child,wfd)
    child2,wfd2=start(root,python); fresh=status(child2); stop(child2,wfd2)
    if fresh!='CONFIGURED=NO': return 1
    print('BACKEND_REAL_PROCESS_RESTART=PASS'); print('BACKEND_RESTART_RETURNS_UNCONFIGURED=YES'); print('AUTOMATIC_CREDENTIAL_REPLAY=0'); print('SENTINEL_VALUE_OUTPUT=0'); return 0
if __name__=='__main__': raise SystemExit(main())
