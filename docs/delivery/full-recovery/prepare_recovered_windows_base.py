"""Extend the exact approved artifact base with the official hash-locked closure.

Original CPython/PostgreSQL payload files are independently rehashed and copied.
Only new wheels are installed; all old wheel pins/files are preserved. The build
machine's pip unpacks wheels, never the embedded runtime. No services/installers
or new runtime licence agreements are invoked here.
"""
from __future__ import annotations

import email
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
SOURCE = ROOT / ".runtime/full-recovery/pr45-approved-application/Application"
OUTPUT = ROOT / ".runtime/full-recovery/windows-base-final"
CACHE = ROOT / ".runtime/full-recovery/windows-runtime-cache/wheels"
sys.path.insert(0,str(ROOT / "scripts"))
from prepare_windows_base import download, inventory, reject_links, safe_members, sha256, validate_dependency_closure

reject_links(SOURCE)
reject_links(OUTPUT)
if OUTPUT.exists():
    raise ValueError("candidate extended base must be fresh")
original = json.loads((SOURCE / "base-input-provenance.json").read_text(encoding="utf-8"))
lock = json.loads((ROOT / "packaging/windows-runtime-inputs.json").read_text(encoding="utf-8"))
validate_dependency_closure(lock)
old = {row["name"]:row for row in original["inputs"]["wheels"]}
for name,row in old.items():
    if row not in lock["wheels"]:
        raise ValueError("original runtime wheel metadata/pin changed: "+name)
if original["inputs"]["runtime_inputs"] != lock["runtime_inputs"]:
    raise ValueError("approved CPython/PostgreSQL input pin changed")
new = [row for row in lock["wheels"] if row["name"] not in old]
CACHE.mkdir(parents=True,exist_ok=True)
for row in new:
    path = download(row,CACHE)
    with zipfile.ZipFile(path) as archive:
        safe_members(archive)
        if archive.testzip() or any(name not in archive.namelist() for name in row["license_files"]):
            raise ValueError("new wheel integrity/complete license verification failed")
        metadata_paths = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(metadata_paths) != 1:
            raise ValueError("new wheel metadata ambiguous")
        metadata = email.message_from_bytes(archive.read(metadata_paths[0]))
        if (metadata["Name"] != row["name"] or metadata["Version"] != row["version"] or
            metadata.get_all("Requires-Dist",[]) != row["requires_dist"] or metadata.get("Requires-Python") != row["requires_python"]):
            raise ValueError("official wheel metadata differs from reviewed lock")
for row in original["files"]:
    path = SOURCE / row["path"]
    reject_links(path)
    if not path.resolve().is_relative_to(SOURCE.resolve()) or path.stat().st_size != row["size"] or sha256(path) != row["sha256"]:
        raise ValueError("approved original base inventory mismatch: "+row["path"])
OUTPUT.mkdir(parents=True)
for row in original["files"]:
    source = SOURCE / row["path"]
    target = OUTPUT / row["path"]
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,target)
# The original reviewed launcher is kept as payload material. Backend, frontend
# and DesktopHost are replaced by the same-run current-source application build.
if (SOURCE / "Launcher").exists():
    shutil.copytree(SOURCE / "Launcher",OUTPUT / "Launcher")
requirements = EVIDENCE / "new-windows-runtime-wheels.lock.txt"
requirements.write_text("".join(f"{row['name']}=={row['version']} --hash=sha256:{row['sha256']}\n" for row in new),encoding="utf-8",newline="\n")
subprocess.run([sys.executable,"-m","pip","--isolated","install","--no-index","--no-deps","--no-compile",
                "--only-binary=:all:","--platform","win_amd64","--python-version","3.12","--implementation","cp","--abi","cp312",
                "--require-hashes","--find-links",str(CACHE),"--target",str(OUTPUT / "Runtime/Python/Lib/site-packages"),
                "-r",str(requirements)],check=True)
(OUTPUT / "Licenses/PYTHON-WHEEL-LICENSES.txt").write_text(
    "Full wheel notices are retained in Runtime/Python/Lib/site-packages/*.dist-info.\n"+
    "\n".join(row["filename"]+": "+", ".join(row["license_files"]) for row in lock["wheels"])+"\n",encoding="utf-8",newline="\n")
manifest = {**original,"inputs":lock,"input_manifest_sha256":sha256(ROOT / "packaging/windows-runtime-inputs.json"),
            "native_runtime_verification":"NOT_RUN","interactive_acceptance":"NOT_RUN",
            "recovery_source":{"exact_pr45_artifact_id":11469458461,"base":str(SOURCE),
                               "original_verified_files":len(original["files"]),"original_wheels_preserved":len(old),
                               "new_official_hash_locked_wheels":len(new),"old_runtime_input_pins_unchanged":True},
            "files":inventory(OUTPUT)}
(OUTPUT / "base-input-provenance.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
probe = "import json,sys,importlib.metadata as m,jsonschema,pypdf;from jsonschema import Draft202012Validator;Draft202012Validator.check_schema({'type':'object'});print(json.dumps({'python':list(sys.version_info[:3]),'jsonschema':m.version('jsonschema'),'pypdf':m.version('pypdf')}))"
observed = json.loads(subprocess.check_output([str(OUTPUT / "Runtime/Python/python.exe"),"-I","-c",probe],text=True))
if observed != {"python":[3,12,9],"jsonschema":"4.26.0","pypdf":"6.19.0"}:
    raise ValueError("actual isolated embedded runtime did not match approved new dependency pins")
receipt = {"base_application":str(OUTPUT),"files":len(manifest["files"]),"actual_embedded_probe":observed,
           "original_wheels_preserved":len(old),"new_wheels":len(new),"all_wheel_records":len(lock["wheels"]),
           "native_smoke":"NOT_RUN","system_runtime_modified":False}
(EVIDENCE / "windows-extended-base-recovery.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
print(json.dumps(receipt,indent=2))
