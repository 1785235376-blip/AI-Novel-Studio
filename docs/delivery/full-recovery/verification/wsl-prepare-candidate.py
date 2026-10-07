"""Extract final actual-byte candidate into this task's native ext4 runtime."""
from __future__ import annotations
import hashlib
import json
import os
import subprocess
import tarfile
from pathlib import Path

runtime = Path(__file__).resolve().parent
origin = runtime.parents[2]
native_environment = json.loads((runtime/"native-environment.json").read_text(encoding="utf8"))
native = Path(native_environment["native"])
project = native/"project"
assert native.parent == Path("/tmp") and native.name.startswith("ai-novel-full-recovery-"), native
assert not project.exists(), "A final candidate must start in a fresh directory"
inventory = json.loads((runtime/"candidate-source-inventory.json").read_text(encoding="utf8"))
archive = runtime/"candidate-source.tar"
assert hashlib.sha256(archive.read_bytes()).hexdigest() == inventory["tar_sha256"]
project.mkdir()
with tarfile.open(archive) as source:
    source.extractall(project, filter="data")
actual = {name:hashlib.sha256((project/name).read_bytes()).hexdigest() for name in inventory["files"]}
assert actual == inventory["files"], "Candidate source bytes drifted during copy"
digest = hashlib.sha256(json.dumps(actual,ensure_ascii=True,sort_keys=True,separators=(",",":")).encode()).hexdigest()
assert digest == inventory["files_digest"]
proof = {"origin":"Current Windows actual source bytes; no checkout/smudge", "destination":str(project),
         "files":len(actual),"origin_inventory_digest":inventory["files_digest"],"native_copy_inventory_digest":digest,
         "all_file_sha256_equal":True,"tar_sha256":inventory["tar_sha256"],
         "boundary":"Native ext4 copy of final candidate; original Git history stays in Windows baseline; no userdata/runtime/node_modules/venv copied"}
(origin/"docs/delivery/full-recovery/verification/wsl-source-copy-proof.json").write_text(json.dumps(proof,indent=2)+"\n",encoding="utf8")
(native/"source-copy-proof.json").write_text(json.dumps(proof,indent=2)+"\n",encoding="utf8")
environment = dict(os.environ)
environment["UV_CACHE_DIR"] = str(runtime/"cache")
uv = runtime/"tools/uv-x86_64-unknown-linux-gnu/uv"
subprocess.run([str(uv),"venv","--python","/usr/bin/python3",str(native/"venv")],env=environment,check=True)
with (origin/"docs/delivery/full-recovery/verification/wsl-native-python-install.log").open("w",encoding="utf8") as output:
    subprocess.run([str(uv),"pip","install","--python",str(native/"venv/bin/python"),"-c",str(project/".github/ci/python-constraints.txt"),"-e",str(project)+"[dev,fontbuild,otio,comic]"],cwd=project,env=environment,stdout=output,stderr=subprocess.STDOUT,check=True)
    subprocess.run([str(uv),"pip","check","--python",str(native/"venv/bin/python")],cwd=project,env=environment,stdout=output,stderr=subprocess.STDOUT,check=True)
    subprocess.run([str(uv),"pip","freeze","--python",str(native/"venv/bin/python")],cwd=project,env=environment,stdout=output,stderr=subprocess.STDOUT,check=True)
print(json.dumps(proof))
