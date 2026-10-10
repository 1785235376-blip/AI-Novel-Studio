"""Verify freshly built current-source package bytes against original inventories."""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile

ROOT=Path(__file__).resolve().parents[3]
parser=argparse.ArgumentParser()
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--sha',required=True)
parser.add_argument('--fingerprint',required=True)
parser.add_argument('--receipt',type=Path,default=ROOT/'docs/delivery/full-recovery/candidate-package-verification.json')
args=parser.parse_args()
output=args.output.absolute()
expected_sha=args.sha
provenance=json.loads((output/'application-provenance.json').read_text(encoding='utf-8-sig'))
assert provenance['source_commit']==expected_sha, provenance['source_commit']
counts={}
for component in ('backend','frontend'):
    info=provenance[component]
    directory=Path(info['stage']).resolve()
    assert directory.is_relative_to((output/'Application').resolve())
    for row in info['inventory']:
        path=directory/row['path']
        assert path.resolve().is_relative_to(directory)
        data=path.read_bytes()
        assert len(data)==row['size']
        assert hashlib.sha256(data).hexdigest().lower()==row['sha256'].lower()
        if component=='backend':
            source=ROOT/row['path']
            assert source.read_bytes()==data,('Source/stage changed',row['path'])
    counts[component]=len(info['inventory'])
manifest=json.loads((output/'acceptance-package-manifest.json').read_text(encoding='utf-8-sig'))
assert manifest['public_release'] is False
package=(output/'Package').resolve()
for row in manifest['files']:
    path=package/row['path']
    assert path.resolve().is_relative_to(package)
    data=path.read_bytes()
    assert len(data)==row['size']
    assert hashlib.sha256(data).hexdigest().lower()==row['sha256'].lower()
archive=output/'AI-Novel-Studio-Windows-DesktopHost-acceptance.zip'
with zipfile.ZipFile(archive) as value:
    assert value.testzip() is None
    for info in value.infolist():
        path=package/info.filename
        assert path.resolve().is_relative_to(package)
        if not info.is_dir():
            assert value.read(info)==path.read_bytes(),info.filename
    members=len(value.infolist())
receipt={'status':'PASS','evidence_boundary':'Fresh unsigned internal acceptance ZIP from current candidate, not historical PR45 artifact',
         'source_commit':expected_sha,'source_fingerprint':args.fingerprint,
         'application':str(output/'Application'),'archive':str(archive),
         'archive_bytes':archive.stat().st_size,'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
         'archive_crc':'PASS','all_archive_entries_match_package_bytes':True,
         'package_inventory_files':len(manifest['files']),'package_inventory_sha256':hashlib.sha256((output/'acceptance-package-manifest.json').read_bytes()).hexdigest(),
         'component_inventory_counts':counts,'all_staged_backend_bytes_match_frozen_current_source':True,
         'python_runtime':provenance['python_runtime'],'postgresql_runtime':provenance['postgresql_runtime'],
         'dotnet_sdk_version':provenance['desktophost']['dotnet_sdk_version'],'public_release':False,
         'setup_exe':'Not built; original CI-equivalent -SkipIExpress; ZIP and PowerShell installer present'}
args.receipt.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(receipt,indent=2))
