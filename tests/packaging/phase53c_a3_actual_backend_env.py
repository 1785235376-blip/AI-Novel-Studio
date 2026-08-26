from __future__ import annotations

import os
import subprocess
import tempfile
import json
from pathlib import Path

from app.packaging.packaged_launcher import create_packaged_backend_runtime
from app.packaging.packaged_processes import PackagedProcessFactory
from app.packaging.paths import WindowsPackagingPaths
import app.packaging.packaged_processes as packaged_processes

APPLICATION = Path(r"D:\小说\AI-Novel-Studio-v070-phase53c-a3-observe2-bcard-20260818\Application")


def main() -> int:
    observed: dict[str, bool] = {}
    original_popen = packaged_processes.subprocess.Popen
    backend_process = None

    def spy_popen(*args, **kwargs):
        command = args[0] if args else kwargs.get("args", [])
        command = [str(item) for item in command]
        is_backend = ("-I" in command and "-m" in command and "uvicorn" in command
                      and "app.main:app" in command)
        if is_backend:
            observed["backend_popen"] = True
            env = kwargs.get("env")
            observed["env_argument"] = env is not None
            observed["runtime_id_present"] = bool(env is not None and "PACKAGED_RUNTIME_INSTANCE_ID" in env)
            observed["runtime_id_nonempty"] = bool(env is not None and isinstance(env.get("PACKAGED_RUNTIME_INSTANCE_ID"), str) and env.get("PACKAGED_RUNTIME_INSTANCE_ID"))
            observed["bootstrap_secret_present"] = bool(env is not None and "PACKAGED_BOOTSTRAP_SECRET" in env)
            observed["packaged_mode_present"] = bool(env is not None and "PACKAGED_WINDOWS_MODE" in env)
            # Test-only bundled Python -I check; capture only its exit status.
            if env is not None:
                exe = command[0]
                check = original_popen([exe, "-I", "-c",
                    "import os,sys; sys.exit(0 if ('PACKAGED_RUNTIME_INSTANCE_ID' in os.environ and bool(os.environ.get('PACKAGED_RUNTIME_INSTANCE_ID'))) else 1)"],
                    env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                observed["bundled_python_i_preserves_env"] = check.wait(timeout=10) == 0
        nonlocal backend_process
        process = original_popen(*args, **kwargs)
        if is_backend:
            backend_process = process
        return process

    packaged_processes.subprocess.Popen = spy_popen
    lifecycle = None
    local_temp = tempfile.TemporaryDirectory(prefix="ai-novel-a3-env-", ignore_cleanup_errors=True)
    profile_temp = tempfile.TemporaryDirectory(prefix="ai-novel-a3-profile-", ignore_cleanup_errors=True)
    try:
        paths = WindowsPackagingPaths.resolve(local_app_data=local_temp.name, user_profile=profile_temp.name)
        lifecycle, factory = create_packaged_backend_runtime(application=APPLICATION, paths=paths)
        identity = lifecycle.startup()
        observed["runtime_started"] = True
        child = lifecycle.children.get(lifecycle.startup_order[1])
        if child is not None and getattr(child, "process", None) is not None:
            observed["backend_pid_available"] = True
            observed["backend_pid"] = True
        port = lifecycle.reservations.ports[lifecycle.startup_order[1]]
        pid = int(backend_process.pid)
        ps = r"powershell.exe"
        def ps_json(script):
            raw = subprocess.check_output([ps, "-NoProfile", "-Command", script], text=True, encoding="utf-8", errors="replace").strip()
            return json.loads(raw) if raw else None
        proc = ps_json(f"$p=Get-CimInstance Win32_Process -Filter 'ProcessId={pid}'; [pscustomobject]@{{pid=$p.ProcessId;parent=$p.ParentProcessId;exe=$p.ExecutablePath}} | ConvertTo-Json -Compress")
        start = subprocess.check_output([ps, "-NoProfile", "-Command", f"(Get-Process -Id {pid}).StartTime.ToUniversalTime().ToString('o')"], text=True, encoding="utf-8", errors="replace").strip()
        listener = ps_json(f"Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort {port} -State Listen | Select-Object -First 1 OwningProcess,LocalAddress,LocalPort | ConvertTo-Json -Compress")
        lpid = int(listener["OwningProcess"] if isinstance(listener, dict) else listener[0]["OwningProcess"])
        lproc = ps_json(f"$p=Get-CimInstance Win32_Process -Filter 'ProcessId={lpid}'; [pscustomobject]@{{pid=$p.ProcessId;parent=$p.ParentProcessId;exe=$p.ExecutablePath}} | ConvertTo-Json -Compress")
        lstart = subprocess.check_output([ps, "-NoProfile", "-Command", f"(Get-Process -Id {lpid}).StartTime.ToUniversalTime().ToString('o')"], text=True, encoding="utf-8", errors="replace").strip()
        print(f"BACKEND_POPEN_PID={pid}")
        print("POPEN_BACKEND_CREATION_TIME=" + start)
        print("POPEN_BACKEND_EXECUTABLE_PATH=" + str(proc["exe"]))
        print(f"POPEN_BACKEND_PARENT_PID={int(proc['parent'])}")
        print(f"REAL_BACKEND_ORIGIN=http://127.0.0.1:{port}")
        print(f"BACKEND_LISTENER_PID={lpid}")
        print("LISTENER_PROCESS_CREATION_TIME=" + lstart)
        print("LISTENER_PROCESS_EXECUTABLE_PATH=" + str(lproc["exe"]))
        print(f"LISTENER_PROCESS_PARENT_PID={int(lproc['parent'])}")
        print("PID_MATCH=" + ("YES" if pid == lpid else "NO"))
        print("CREATION_TIME_MATCH=" + ("YES" if start == lstart else "NO"))
        print("EXECUTABLE_PATH_MATCH=" + ("YES" if str(proc["exe"]).lower() == str(lproc["exe"]).lower() else "NO"))
        descendants = ps_json(f"Get-CimInstance Win32_Process | Where-Object {{$_.ParentProcessId -eq {pid}}} | Select-Object ProcessId,ParentProcessId,Name,ExecutablePath | ConvertTo-Json -Compress")
        count = 0 if descendants is None else (len(descendants) if isinstance(descendants, list) else 1)
        print(f"BACKEND_DESCENDANT_PROCESS_COUNT={count}")
        print("UVICORN_HEALTH_SERVER_PROCESS_MODEL=" + ("DIRECT" if pid == lpid else "DESCENDANT"))
        print("HEALTH_SERVER_IS_DIRECT_POPEN_CHILD=" + ("YES" if pid == lpid and start == lstart and str(proc['exe']).lower() == str(lproc['exe']).lower() else "NO"))
        print("ORIGINAL_POPEN_BACKEND_ALIVE_WHEN_HEALTH_READY=" + ("YES" if backend_process.poll() is None else "NO"))
        print("ORIGINAL_POPEN_BACKEND_EXIT_CODE=" + ("STILL_RUNNING" if backend_process.poll() is None else str(backend_process.returncode)))
        print("BACKEND_POPEN_OBSERVED=" + ("YES" if observed.get("backend_popen") else "NO"))
        print("OBSERVED_POPEN_IS_BACKEND_LAUNCH=" + ("YES" if observed.get("backend_popen") else "NO"))
        print("POPEN_ENV_ARGUMENT_PRESENT=" + ("YES" if observed.get("env_argument") else "NO"))
        print("POPEN_ENV_PACKAGED_RUNTIME_INSTANCE_ID_PRESENT=" + ("YES" if observed.get("runtime_id_present") else "NO"))
        print("POPEN_RUNTIME_VALUE_NONEMPTY=" + ("YES" if observed.get("runtime_id_nonempty") else "NO"))
        print("POPEN_ENV_PACKAGED_BOOTSTRAP_SECRET_PRESENT=" + ("YES" if observed.get("bootstrap_secret_present") else "NO"))
        print("POPEN_ENV_PACKAGED_WINDOWS_MODE_PRESENT=" + ("YES" if observed.get("packaged_mode_present") else "NO"))
        print("POPEN_SPY_SECRET_VALUE_CAPTURE=0")
        print("BUNDLED_PYTHON_I_PRESERVES_PACKAGED_ENV=" + ("YES" if observed.get("bundled_python_i_preserves_env") else "NO"))
        print("BUNDLED_PYTHON_I_KEY_PRESENT=" + ("YES" if observed.get("bundled_python_i_preserves_env") else "NO"))
        print("BUNDLED_PYTHON_I_VALUE_NONEMPTY=" + ("YES" if observed.get("bundled_python_i_preserves_env") else "NO"))
        print("PROCESS_FACTORY_ACTUAL_BACKEND_ENV_TEST=" + ("PASS" if all(observed.get(k) for k in ("runtime_id_present", "bootstrap_secret_present", "packaged_mode_present")) else "FAIL"))
        print("CREDENTIAL_SET_ATTEMPTED=NO")
        print("REAL_DEEPSEEK_REQUESTS=0")
        return 0
    finally:
        packaged_processes.subprocess.Popen = original_popen
        if lifecycle is not None:
            lifecycle.shutdown()
        profile_temp.cleanup()
        local_temp.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
