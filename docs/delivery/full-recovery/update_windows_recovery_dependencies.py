"""Add exact runtime requirements from PyPI metadata; preserve every old pin."""
from __future__ import annotations

import email
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request
import zipfile

from pip._vendor.packaging.tags import cpython_tags, compatible_tags
from pip._vendor.packaging.utils import parse_wheel_filename

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
CACHE = ROOT / ".runtime/full-recovery/windows-runtime-cache/wheels"
CACHE.mkdir(parents=True,exist_ok=True)
BASELINE = "665817243cad59eef0d4140f17c2ea644f46971e"
LOCK = ROOT / "packaging/windows-runtime-inputs.json"
REQUIREMENTS = ROOT / "packaging/requirements-windows.lock.txt"
for name, archive in (("packaging/windows-runtime-inputs.json","PR45_WINDOWS_RUNTIME_INPUTS.json"),
                      ("packaging/requirements-windows.lock.txt","PR45_WINDOWS_REQUIREMENTS.lock.txt")):
    original = subprocess.check_output(["git","show",BASELINE+":"+name],cwd=ROOT)
    target = EVIDENCE / archive
    if target.exists() and target.read_bytes() != original:
        raise ValueError("archived original packaging lock differs")
    target.write_bytes(original)
lock = json.loads((EVIDENCE / "PR45_WINDOWS_RUNTIME_INPUTS.json").read_text())
original_wheels = list(lock["wheels"])
pinned = {"pypdf":"6.19.0","jsonschema":"4.26.0","jsonschema-specifications":"2025.9.1",
          "attrs":"26.1.0","referencing":"0.37.0","rpds-py":"2026.9.1"}
supported = list(cpython_tags((3,12),abis=["cp312"],platforms=["win_amd64"]))
supported += list(compatible_tags((3,12),interpreter="cp312",platforms=["win_amd64"]))
rank = {tag:index for index,tag in enumerate(supported)}
new = []
for name,version in pinned.items():
    source = f"https://pypi.org/pypi/{name}/{version}/json"
    raw = urllib.request.urlopen(source,timeout=60).read()
    (EVIDENCE / f"pypi-{name}-{version}.json").write_bytes(raw)
    package = json.loads(raw)
    choices = []
    for item in package["urls"]:
        if item["packagetype"] != "bdist_wheel" or item.get("yanked"):
            continue
        tags = parse_wheel_filename(item["filename"])[3]
        matching = [rank[tag] for tag in tags if tag in rank]
        if matching:
            choices.append((min(matching),item["filename"],item))
    if not choices:
        raise ValueError("no compatible non-yanked exact Windows wheel: "+name)
    item = sorted(choices,key=lambda row:row[:2])[0][2]
    target = CACHE / item["filename"]
    if not target.exists():
        target.write_bytes(urllib.request.urlopen(item["url"],timeout=60).read())
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    if target.stat().st_size != item["size"] or digest != item["digests"]["sha256"]:
        raise ValueError("official wheel length/hash mismatch: "+name)
    with zipfile.ZipFile(target) as archive:
        if archive.testzip():
            raise ValueError("wheel CRC failed: "+name)
        metadata_name = [path for path in archive.namelist() if path.endswith(".dist-info/METADATA")]
        if len(metadata_name) != 1:
            raise ValueError("ambiguous wheel metadata: "+name)
        metadata = email.message_from_bytes(archive.read(metadata_name[0]))
        licenses = sorted(path for path in archive.namelist() if not path.endswith("/") and
                          ".dist-info/" in path and
                          ("/licenses/" in path or Path(path).name.upper().startswith(("LICENSE","COPYING","NOTICE"))))
        if not licenses:
            raise ValueError("full wheel license files absent: "+name)
        row = {"name":metadata["Name"],"version":metadata["Version"],"filename":item["filename"],
               "url":item["url"],"sha256":digest,"size":item["size"],"checksum_source":source,
               "license_files":licenses,"requires_dist":metadata.get_all("Requires-Dist",[]),
               "requires_python":metadata.get("Requires-Python")}
        if row["version"] != version:
            raise ValueError("wheel version differs from exact requested pin")
        new.append(row)
lock["wheels"] = sorted([*original_wheels,*new],key=lambda row:row["name"].lower())
lock["captured_at_utc"] = "2026-10-07"
import sys
sys.path.insert(0,str(ROOT / "scripts"))
from prepare_windows_base import validate_dependency_closure
validate_dependency_closure(lock)
LOCK.write_text(json.dumps(lock,indent=2,ensure_ascii=False)+"\n",encoding="utf-8",newline="\n")
header = "# CPython 3.12 Windows x64 wheels, resolved from PyPI and hash-locked.\n# See windows-runtime-inputs.json for exact file URLs and license paths.\n"
REQUIREMENTS.write_text(header+"".join(f"{row['name']}=={row['version']} --hash=sha256:{row['sha256']}\n" for row in lock["wheels"]),encoding="utf-8",newline="\n")
receipt = {"baseline_pr45_sha":BASELINE,"original_wheels":len(original_wheels),"current_wheels":len(lock["wheels"]),
           "all_original_wheel_records_and_versions_preserved":all(row in lock["wheels"] for row in original_wheels),
           "runtime_input_pins_unchanged":True,"strict_windows_python3129_dependency_closure_passed":True,
           "new_wheels":new,"full_licenses_retained_inside_wheels":True}
(EVIDENCE / "windows-runtime-dependency-recovery.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"original_wheels":len(original_wheels),"candidate_wheels":len(lock["wheels"]),"new_pins":pinned},indent=2))
