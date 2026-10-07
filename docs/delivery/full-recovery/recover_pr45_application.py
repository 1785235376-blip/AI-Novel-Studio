"""Extract the verified exact-head historical Application as approved build material."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
ASSETS = ROOT.parent / "AI-Novel-Studio-Recovery-Assets/pr45-6658172"
OUTER = ASSETS / "11469458461-windows-acceptance-665817243cad59eef0d4140f17c2ea644f46971e.zip"
INNER = ASSETS / "AI-Novel-Studio-6658172-acceptance-inner.zip"
DESTINATION = ROOT / ".runtime/full-recovery/pr45-approved-application"
expected = "c0f8e9541a43599de6066161935ac131fb1ddc5257a314604b0e84c395ddf4ed"
if hashlib.file_digest(OUTER.open("rb"),"sha256").hexdigest() != expected:
    raise ValueError("exact-head outer artifact digest differs")
with zipfile.ZipFile(OUTER) as outer:
    candidates = [name for name in outer.namelist() if name.endswith(".zip")]
    if len(candidates) != 1:
        raise ValueError("outer package inner ZIP ambiguous")
    with outer.open(candidates[0]) as stream:
        inner_digest = hashlib.file_digest(stream,"sha256").hexdigest()
if hashlib.file_digest(INNER.open("rb"),"sha256").hexdigest() != inner_digest:
    raise ValueError("saved inner package differs from verified outer artifact member")
sys.path.insert(0,str(ROOT / "scripts"))
from prepare_windows_base import safe_members, reject_links, sha256
with zipfile.ZipFile(INNER) as archive:
    safe_members(archive)
    if archive.testzip():
        raise ValueError("inner package CRC failed")
    if DESTINATION.exists():
        raise ValueError("approved historical application output must be fresh")
    DESTINATION.mkdir(parents=True)
    for member in archive.infolist():
        if not member.filename.startswith("Application/") or member.is_dir():
            continue
        target = DESTINATION.joinpath(*Path(member.filename).parts)
        reject_links(target)
        if not target.resolve().is_relative_to(DESTINATION.resolve()):
            raise ValueError("historical application member escapes destination")
        target.parent.mkdir(parents=True,exist_ok=True)
        with archive.open(member) as source,target.open("xb") as output:
            import shutil
            shutil.copyfileobj(source,output)
application = DESTINATION / "Application"
provenance = json.loads((application / "base-input-provenance.json").read_text(encoding="utf-8-sig"))
for item in provenance["files"]:
    target = application.joinpath(*Path(item["path"]).parts)
    if target.stat().st_size != item["size"] or sha256(target) != item["sha256"]:
        raise ValueError("original approved base inventory mismatch: "+item["path"])
python = application / "Runtime/Python/python.exe"
output = subprocess.check_output([str(python),"-I","-c","import json,sys;print(json.dumps(list(sys.version_info[:3])))"],text=True)
if json.loads(output) != [3,12,9]:
    raise ValueError("recovered exact-head embedded Python differs from approved 3.12.9")
record = {"baseline_pr45_sha":"665817243cad59eef0d4140f17c2ea644f46971e","artifact_id":11469458461,
          "outer_sha256":expected,"inner_sha256":inner_digest,"original_base_inventory_files_verified":len(provenance["files"]),
          "application":str(application),"python":[3,12,9],"new_candidate":False,
          "purpose":"Exact original approved build material; current source/dependency extension/fresh build remain separate"}
(EVIDENCE / "pr45-approved-base-recovery.json").write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
print(json.dumps(record,indent=2))
