"""Extend the exact approved artifact base with the official hash-locked closure.

Original CPython/PostgreSQL payload files are independently rehashed and copied.
Only new wheels are installed; all old wheel pins/files are preserved. The build
machine's pip unpacks wheels, never the embedded runtime. No services/installers
or new runtime licence agreements are invoked here.
"""
from __future__ import annotations

import copy
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
original_provenance_bytes = (SOURCE / "base-input-provenance.json").read_bytes()
(EVIDENCE / "PR45_ORIGINAL_BASE_INPUT_PROVENANCE.json").write_bytes(original_provenance_bytes)
lock = json.loads((ROOT / "packaging/windows-runtime-inputs.json").read_text(encoding="utf-8"))
validate_dependency_closure(lock)
old = {row["name"]:row for row in original["inputs"]["wheels"]}
for name,row in old.items():
    if row not in lock["wheels"]:
        raise ValueError("original runtime wheel metadata/pin changed: "+name)
if original["inputs"]["runtime_inputs"] != lock["runtime_inputs"]:
    raise ValueError("approved CPython/PostgreSQL input pin changed")
new = [row for row in lock["wheels"] if row["name"] not in old]
allowed_site_package_roots = set()
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
        allowed_site_package_roots.update(name.split("/",1)[0] for name in archive.namelist()
                                         if name and not name.split("/",1)[0].endswith(".data"))
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
# Base inputs contain only the original declared runtime/licences scope.
# Current product payload is supplied by the original application/package builder.
requirements = EVIDENCE / "new-windows-runtime-wheels.lock.txt"
requirements.write_text("".join(f"{row['name']}=={row['version']} --hash=sha256:{row['sha256']}\n" for row in new),encoding="utf-8",newline="\n")
subprocess.run([sys.executable,"-m","pip","--isolated","install","--no-index","--no-deps","--no-compile",
                "--only-binary=:all:","--platform","win_amd64","--python-version","3.12","--implementation","cp","--abi","cp312",
                "--require-hashes","--find-links",str(CACHE),"--target",str(OUTPUT / "Runtime/Python/Lib/site-packages"),
                "-r",str(requirements)],check=True)
(OUTPUT / "Licenses/RECOVERY-PYTHON-WHEEL-LICENSES.txt").write_text(
    "Full wheel notices are retained in Runtime/Python/Lib/site-packages/*.dist-info.\n"+
    "\n".join(row["filename"]+": "+", ".join(row["license_files"]) for row in new)+"\n",encoding="utf-8",newline="\n")
original_paths = {row["path"] for row in original["files"]}
for row in original["files"]:
    path = OUTPUT / row["path"]
    if path.stat().st_size != row["size"] or sha256(path) != row["sha256"]:
        raise ValueError("new wheel install changed an original base input: "+row["path"])
additional_files = [row for row in inventory(OUTPUT) if row["path"] not in original_paths]
for row in additional_files:
    name = row["path"]
    relative = name.removeprefix("Runtime/Python/Lib/site-packages/")
    if name == "Licenses/RECOVERY-PYTHON-WHEEL-LICENSES.txt":
        continue
    if relative == name or relative.split("/",1)[0] not in allowed_site_package_roots | {"bin"}:
        raise ValueError("new runtime input is outside the declared six-wheel scope: "+name)
    if relative.startswith("bin/") and relative != "bin/jsonschema.exe":
        raise ValueError("undeclared wheel console entry: "+name)
manifest = {**original,"inputs":lock,"input_manifest_sha256":sha256(ROOT / "packaging/windows-runtime-inputs.json"),
            "native_runtime_verification":"NOT_RUN","interactive_acceptance":"NOT_RUN",
            "recovery_source":{"exact_pr45_artifact_id":11469458461,"base":str(SOURCE),
                               "original_verified_files":len(original["files"]),"original_wheels_preserved":len(old),
                               "new_official_hash_locked_wheels":len(new),"old_runtime_input_pins_unchanged":True,
                               "original_base_provenance_sha256":sha256(SOURCE / "base-input-provenance.json"),
                               "original_base_records_unchanged":True,"additional_input_files":len(additional_files),
                               "new_wheel_site_package_roots":sorted(allowed_site_package_roots),
                               "source_owned_payload_excluded_from_base":True},
            "files":[*copy.deepcopy(original["files"]),*additional_files]}
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
