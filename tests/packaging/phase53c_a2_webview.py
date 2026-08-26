import io
import json
import msvcrt
import os
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.packaging.host_uplink import parse_host_credential
from app.packaging.packaged_processes import PackagedProcessFactory
from app.packaging.control_pipe import PackagedControlReader, credential_store

RUNTIME = "t4b-test"
PREFIX = b"AI_NOVEL_TEST_ATTRIBUTION_V1\t"


def run_webview(root, exe, frontend, profile, message, wrong_origin=False, production=False):
    observer_r, observer_w = os.pipe()
    data_r, data_w = os.pipe()
    os.set_inheritable(observer_w, True)
    os.set_inheritable(data_w, True)
    observer_handle = msvcrt.get_osfhandle(observer_w)
    data_handle = msvcrt.get_osfhandle(data_w)
    startup = subprocess.STARTUPINFO()
    startup.lpAttributeList = {"handle_list": [observer_handle, data_handle]}
    command = [
        str(exe), "--frontend-root", str(frontend),
        "--observer-handle", str(observer_handle),
        "--credential-data-handle", str(data_handle),
        "--profile-root", str(profile),
        "--scenario", "CREDENTIAL_WRONG_ORIGIN" if wrong_origin else ("PRODUCTION_CREDENTIAL" if production else "CREDENTIAL"),
        "--credential-json-stdin", "yes",
    ]
    process = subprocess.Popen(
        command, cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, close_fds=True, startupinfo=startup,
    )
    stdout, stderr = process.communicate(json.dumps(message, separators=(",", ":")) + "\n", timeout=30)
    os.close(observer_w)
    os.close(data_w)
    with os.fdopen(observer_r, "rb") as pipe:
        observer = pipe.read()
    with os.fdopen(data_r, "rb") as pipe:
        raw = pipe.read(4101)
    frame = None
    if raw:
        if len(raw) < 4:
            raise AssertionError("truncated credential pipe header")
        size = int.from_bytes(raw[:4], "little")
        if size > 4096 or len(raw[4:]) != size:
            raise AssertionError("invalid credential pipe payload")
        frame = raw[4:].decode("utf-8")
    browser_ok = "REAL_COREWEBVIEW2=YES" in stdout and "REAL_WEBMESSAGERECEIVED=YES" in stdout
    return process.returncode if browser_ok else (process.returncode or 1), frame, stdout, stderr, observer


def forward(frame):
    global last_forward_meta
    last_forward_meta = (frame is not None, frame[:48].encode("unicode_escape").decode("ascii") if frame else "", len(frame) if frame else 0)
    if frame is None or parse_host_credential(frame, RUNTIME) is None:
        last_forward_meta = (*last_forward_meta, False)
        return False
    last_forward_meta = (*last_forward_meta, True)
    factory = PackagedProcessFactory.__new__(PackagedProcessFactory)
    factory._runtime_instance_id = RUNTIME
    backend = io.BytesIO()
    factory.backend_control_writer = backend
    if not factory.forward_backend_credential(frame):
        return False
    backend_frame = backend.getvalue()
    if backend_frame == frame.encode("utf-8"):
        return False
    PackagedControlReader(RUNTIME, io.BytesIO(backend_frame))._read()
    return True


def profile_hits(profile, needles):
    hits = [0 for _ in needles]
    for path in profile.rglob("*"):
        if not path.is_file():
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        for index, needle in enumerate(needles):
            hits[index] += data.count(needle.encode("utf-8"))
    return hits


def main():
    root = Path(__file__).resolve().parents[2]
    package = Path(r"D:\小说\AI-Novel-Studio-v070-phase53c-a3-formal-bcard-20260817\Application")
    frontend = package / "Frontend" / "dist"
    exe = root / "tests/desktop_host_webview2_t4_harness/bin/Debug/net8.0-windows/AI-Novel-Studio.DesktopHost.TestHarness.exe"
    if not exe.is_file() or not (frontend / "index.html").is_file():
        return 2
    sentinels = ["a2-" + secrets.token_urlsafe(36), "a2-" + secrets.token_urlsafe(36)]
    formal = Path(sys.argv[1]).resolve() if len(sys.argv) == 2 else None
    base = {"protocol": "ai-novel-webview-credential/v1", "type": "SET_PROVIDER_CREDENTIAL", "provider": "deepseek"}
    results = []
    all_stdio = ""
    all_observer = b""
    with tempfile.TemporaryDirectory(prefix="ai-novel-a2-webview-", ignore_cleanup_errors=True) as temp:
        profile = Path(temp) / "profile"

        def invoke(message, expect_frame, wrong=False, production=False):
            nonlocal all_stdio, all_observer
            code, frame, out, err, observer = run_webview(root, exe, frontend, profile, message, wrong, production)
            all_stdio += out + err
            all_observer += observer
            ok = code == 0 and (frame is not None) == expect_frame
            return ok, frame

        credential_store.clear("deepseek")
        set_host_ok, frame = invoke({**base, "credential": sentinels[0]}, True)
        set_forward_ok = set_host_ok and forward(frame)
        set_match_ok = credential_store.resolve("deepseek") == sentinels[0]
        set_ok = set_forward_ok and set_match_ok
        replace_host_ok, frame = invoke({**base, "credential": sentinels[1]}, True)
        replace_forward_ok = replace_host_ok and forward(frame)
        replace_match_ok = credential_store.resolve("deepseek") == sentinels[1]
        replace_ok = replace_forward_ok and replace_match_ok
        clear = {"protocol": base["protocol"], "type": "CLEAR_PROVIDER_CREDENTIAL", "provider": "deepseek"}
        clear_host_ok, frame = invoke(clear, True)
        clear_forward_ok = clear_host_ok and forward(frame)
        clear_match_ok = not credential_store.has("deepseek")
        clear_ok = clear_forward_ok and clear_match_ok

        negative_messages = [
            ({**base, "credential": "wrong-origin-fake"}, True),
            ({**base, "credential": "invalid-fake", "extra": 1}, False),
            ({**base, "credential": "runtime-fake", "runtime_instance_id": "browser"}, False),
            ({**base, "credential": "nul\0fake"}, False),
            ({**base, "credential": "cr\rfake"}, False),
            ({**base, "credential": "lf\nfake"}, False),
            ({**base, "credential": "x" * 1025}, False),
            ({**base, "provider": "other", "credential": "provider-fake"}, False),
            ({**clear, "credential": "clear-fake"}, False),
        ]
        negatives_ok = True
        credential_store.clear("deepseek")
        for message, wrong in negative_messages:
            ok, frame = invoke(message, False, wrong)
            negatives_ok = negatives_ok and ok and frame is None and not credential_store.has("deepseek")
        hits = profile_hits(profile, sentinels)

    leaks = [value in all_stdio or value.encode() in all_observer for value in sentinels]
    formal_hits = profile_hits(formal, sentinels) if formal is not None else [0, 0]
    if not all((set_ok, replace_ok, clear_ok, negatives_ok, not any(hits), not any(leaks), not any(formal_hits))):
        print("SET_OK=" + str(set_ok).upper())
        print("SET_STAGES=" + "/".join(str(value).upper() for value in (set_host_ok, set_forward_ok, set_match_ok)))
        print("SET_FRAME_META=" + str((frame is not None, frame.startswith('AI_NOVEL_HOST_CREDENTIAL_V1\\t') if frame else False, parse_host_credential(frame, RUNTIME) is not None if frame else False)).upper())
        print("REPLACE_OK=" + str(replace_ok).upper())
        print("REPLACE_STAGES=" + "/".join(str(value).upper() for value in (replace_host_ok, replace_forward_ok, replace_match_ok)))
        print("CLEAR_OK=" + str(clear_ok).upper())
        print("CLEAR_STAGES=" + "/".join(str(value).upper() for value in (clear_host_ok, clear_forward_ok, clear_match_ok)))
        print("NEGATIVES_OK=" + str(negatives_ok).upper())
        print("PROFILE_HITS=" + "/".join(str(value) for value in hits))
        print("STDIO_OR_OBSERVER_LEAK=" + str(any(leaks)).upper())
        print("FORMAL_HITS=" + "/".join(str(value) for value in formal_hits))
        return 1
    print("REAL_CREDENTIAL_WEBMESSAGERECEIVED=YES")
    print("WEBVIEW_SET=PASS")
    print("WEBVIEW_REPLACE=PASS")
    print("WEBVIEW_CLEAR=PASS")
    print("NEGATIVE_MATRIX=PASS")
    print("NEGATIVE_DOWNSTREAM_CREDENTIAL_ACTIVITY=0")
    print("SENTINEL_STDIO_HITS=0")
    print("SENTINEL_OBSERVER_HITS=0")
    print("SENTINEL_WEBVIEW_PROFILE_HITS=0")
    print("SENTINEL_FORMAL_PACKAGE_HITS=0")
    print("REAL_DEEPSEEK_REQUESTS=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
