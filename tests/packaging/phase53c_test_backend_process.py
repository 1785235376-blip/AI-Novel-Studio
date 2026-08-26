import msvcrt, os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.packaging.control_pipe import PackagedControlReader, credential_store

def main():
    i=sys.argv.index('--control-handle'); handle=int(sys.argv[i+1]); runtime=sys.argv[sys.argv.index('--runtime')+1]
    fd=msvcrt.open_osfhandle(handle, os.O_RDONLY)
    stream=os.fdopen(fd,'rb',closefd=True); reader=PackagedControlReader(runtime,stream); reader.start()
    for command in sys.stdin:
        command=command.strip()
        if command=='STATUS':
            time.sleep(.2); print('CONFIGURED=' + ('YES' if credential_store.has('deepseek') else 'NO'),flush=True)
        elif command=='EXIT': break
    stream.close(); return 0
if __name__=='__main__': raise SystemExit(main())
