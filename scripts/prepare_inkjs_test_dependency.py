"""Verify and extract a separately obtained official inkjs test tarball, offline.

Download URL: https://registry.npmjs.org/inkjs/-/inkjs-2.3.2.tgz
No package manager, lifecycle scripts, network access or executable loading.
"""
import argparse
import base64
import hashlib
import io
from pathlib import Path, PurePosixPath
import tarfile

INTEGRITY = 'iZjrY0lLeRiC+HtDzCfV9IEAP9ExCmBZUrxKkyLy1qIbbGbR1uTXNZ8LDIg8oVkMXZ9TeKKyEFQpQ/m5nQds8w=='
# The same runtime entry the current-artifact target pins in
# app/experimental/interactive_targets/ink/runtime.py; the acceptance verifier
# fails closed unless the installed entry matches it, so the offline extraction
# path must check it too.
RUNTIME_ENTRY = PurePosixPath('package/dist/ink-full.js')
RUNTIME_ENTRY_SHA256 = '4a76187c713c889b5e71d9380b37b5b42eaba9d24af099bb9f968d02311cfeef'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tarball',type=Path);parser.add_argument('new_destination',type=Path)
    args=parser.parse_args()
    if args.tarball.stat().st_size > 8*1024*1024: raise ValueError('TARBALL_TOO_LARGE')
    data=args.tarball.read_bytes()
    if base64.b64encode(hashlib.sha512(data).digest()).decode()!=INTEGRITY: raise ValueError('INTEGRITY_MISMATCH')
    if args.new_destination.exists(): raise ValueError('NEW_DESTINATION_REQUIRED')
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        members=archive.getmembers()
        if len(members)>500 or sum(m.size for m in members)>10*1024*1024: raise ValueError('ARCHIVE_LIMIT')
        for member in members:
            name=PurePosixPath(member.name)
            if name.is_absolute() or '..' in name.parts or not member.name.startswith('package/') or not (member.isfile() or member.isdir()):
                raise ValueError('UNSAFE_ARCHIVE_ENTRY')
        args.new_destination.mkdir(parents=True)
        archive.extractall(args.new_destination,members=members,filter='data')
    runtime_entry=args.new_destination/RUNTIME_ENTRY
    if not runtime_entry.is_file(): raise ValueError('PINNED_RUNTIME_ENTRY_MISSING:'+str(RUNTIME_ENTRY))
    runtime_sha256=hashlib.sha256(runtime_entry.read_bytes()).hexdigest()
    if runtime_sha256!=RUNTIME_ENTRY_SHA256: raise ValueError('PINNED_RUNTIME_ENTRY_MISMATCH')
    print('Verified inkjs 2.3.2; no lifecycle scripts executed. SHA256 '+hashlib.sha256(data).hexdigest())
    print('Verified pinned runtime entry '+str(RUNTIME_ENTRY)+' sha256 '+runtime_sha256)

if __name__=='__main__': main()
