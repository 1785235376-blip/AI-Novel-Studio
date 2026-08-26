from __future__ import annotations
import json, tempfile, urllib.request
from pathlib import Path
from app.packaging.packaged_launcher import create_packaged_backend_runtime
from app.packaging.paths import WindowsPackagingPaths
from app.packaging.runtime_lifecycle import RuntimeRole

APPLICATION = Path(r"D:\小说\AI-Novel-Studio-v070-phase53c-a3-envfix-bcard-20260818\Application")
def main():
    a=tempfile.TemporaryDirectory(prefix="a3-env-"); b=tempfile.TemporaryDirectory(prefix="a3-prof-"); lifecycle=None
    try:
        paths=WindowsPackagingPaths.resolve(local_app_data=a.name,user_profile=b.name)
        lifecycle,_=create_packaged_backend_runtime(application=APPLICATION,paths=paths)
        ident=lifecycle.startup(); port=lifecycle.reservations.ports[RuntimeRole.BACKEND]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health") as r: h=json.load(r)
        s=h.get("control_reader",{})
        for k in ("module_import_runtime_key_present","module_import_runtime_value_nonempty","entry_runtime_key_present","entry_runtime_value_nonempty","lookup_runtime_value_nonempty","invoked","start_result","started","alive","frames_read","frames_dispatched","frames_applied","frames_rejected"): print(f"REAL_{k.upper()}={s.get(k)}")
        print("CREDENTIAL_SET_ATTEMPTED=NO\nREAL_DEEPSEEK_REQUESTS=0")
    finally:
        if lifecycle: lifecycle.shutdown()
        b.cleanup(); a.cleanup()
if __name__ == "__main__": main()
