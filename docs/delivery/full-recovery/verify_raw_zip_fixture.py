"""Show that the reviewed fixture really serializes/rejects a raw ZIP separator."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("raw_fixture_proof",ROOT / "tests/test_r2_windows_base_inputs.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
archive = module.archive("good/file","dir\\escape")
raw = archive.fp.getvalue()
receipt = {"raw_backslash_bytes_present":b"dir\\escape" in raw,"zip_sha256":hashlib.sha256(raw).hexdigest(),
           "entries":[{"filename":row.filename,"orig_filename":row.orig_filename} for row in archive.infolist()],
           "raw_malicious_entry_rejected":False}
try:
    module.base.safe_members(archive)
except ValueError as exc:
    receipt.update(raw_malicious_entry_rejected=True,reason=str(exc))
assert receipt["raw_backslash_bytes_present"] and receipt["raw_malicious_entry_rejected"]
(Path(__file__).resolve().parent / "windows-raw-zip-fixture-proof.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
print(json.dumps(receipt,indent=2))
