"""Recover the pinned official SDK into an isolated runtime, verifying SHA512."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
RUNTIME = ROOT / ".runtime/full-recovery"
DESTINATION = RUNTIME / "dotnet-sdk-8.0.424"
ARCHIVE = RUNTIME / "dotnet-sdk-8.0.424-win-x64.zip"
METADATA_URL = "https://builds.dotnet.microsoft.com/dotnet/release-metadata/8.0/releases.json"
RUNTIME.mkdir(parents=True,exist_ok=True)
metadata_bytes = urllib.request.urlopen(METADATA_URL,timeout=60).read()
metadata = json.loads(metadata_bytes)
files = [file for release in metadata["releases"] for sdk in release.get("sdks",[release.get("sdk",{})])
         if sdk.get("version") == "8.0.424" for file in sdk["files"]
         if file["rid"] == "win-x64" and file["name"].endswith(".zip")]
unique = {file["url"]:file for file in files}
if len(unique) != 1:
    raise ValueError("official pinned SDK metadata is ambiguous or unavailable")
entry = next(iter(unique.values()))
if not entry["url"].startswith("https://builds.dotnet.microsoft.com/"):
    raise ValueError("pinned SDK archive is not on the official release host")
(EVIDENCE / "dotnet-sdk-8.0.424-official-release.json").write_text(json.dumps(entry,indent=2)+"\n")
print("Official pinned SDK metadata selected; downloading archive",flush=True)
expected_length = int(urllib.request.urlopen(urllib.request.Request(entry["url"],method="HEAD"),timeout=60).headers["Content-Length"])
if ARCHIVE.exists() and 0 < ARCHIVE.stat().st_size < expected_length:
    partial = {"bytes":ARCHIVE.stat().st_size,"sha512":hashlib.file_digest(ARCHIVE.open("rb"),"sha512").hexdigest(),
               "expected_bytes":expected_length,"reason":"Initial response ended before official Content-Length; extraction refused"}
    (EVIDENCE / "dotnet-sdk-initial-truncated-download.json").write_text(json.dumps(partial,indent=2)+"\n")
    offset = ARCHIVE.stat().st_size
    request = urllib.request.Request(entry["url"],headers={"Range":f"bytes={offset}-"})
    with urllib.request.urlopen(request,timeout=60) as source:
        if source.status != 206 or not source.headers.get("Content-Range","").startswith(f"bytes {offset}-"):
            raise ValueError("SDK resume did not return the exact verified byte range")
        with ARCHIVE.open("ab") as target:
            while chunk := source.read(1024*1024):
                target.write(chunk)
elif not ARCHIVE.exists():
    with urllib.request.urlopen(entry["url"],timeout=60) as source, ARCHIVE.open("wb") as target:
        while chunk := source.read(1024*1024):
            target.write(chunk)
if ARCHIVE.stat().st_size != expected_length:
    raise ValueError("SDK archive length differs from official response; no extraction performed")
checksum = hashlib.file_digest(ARCHIVE.open("rb"),"sha512").hexdigest()
if checksum.lower() != entry["hash"].lower():
    raise ValueError("downloaded SDK SHA512 differs from official metadata; no extraction performed")
with zipfile.ZipFile(ARCHIVE) as archive:
    bad = archive.testzip()
    if bad:
        raise ValueError("SDK ZIP CRC failed: " + bad)
    for member in archive.infolist():
        target = (DESTINATION / member.filename).resolve()
        if not target.is_relative_to(DESTINATION.resolve()):
            raise ValueError("SDK ZIP traversal rejected")
    DESTINATION.mkdir(parents=True,exist_ok=True)
    archive.extractall(DESTINATION)
    member_count = len(archive.infolist())
output = subprocess.check_output([str(DESTINATION / "dotnet.exe"),"--list-sdks"],cwd=ROOT,text=True)
if not any(line.startswith("8.0.424 ") for line in output.splitlines()):
    raise ValueError("isolated dotnet did not report the approved SDK")
receipt = {"version":"8.0.424","metadata_url":METADATA_URL,"archive_url":entry["url"],
           "official_sha512":entry["hash"],"actual_sha512":checksum,"archive_size":ARCHIVE.stat().st_size,
           "zip_crc_verified":True,"archive_members":member_count,"archive_path":str(ARCHIVE),
           "sdk_root":str(DESTINATION),"sdk_listing":output.strip(),
           "system_installation_modified":False,"product_build_performed":False}
(EVIDENCE / "dotnet-sdk-recovery.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
print(json.dumps(receipt,indent=2),flush=True)
