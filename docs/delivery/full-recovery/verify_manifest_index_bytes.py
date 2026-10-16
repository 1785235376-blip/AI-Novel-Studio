"""Record actual working-tree versus staged bytes for every strict input."""
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
manifest = json.loads(gzip.decompress((ROOT / '.github/ci/coverage_manifest.json.gz').read_bytes()))
rows = []
names = sorted(manifest['source_files'])
batch = subprocess.check_output(['git', 'cat-file', '--batch'], cwd=ROOT,
                                input=(''.join(':' + name + '\n' for name in names)).encode('utf-8'))
offset = 0
for name, expected in sorted(manifest['source_files'].items()):
    current = (ROOT / name).read_bytes()
    header_end = batch.index(b'\n', offset)
    header = batch[offset:header_end].split()
    present = len(header) == 3 and header[1] == b'blob'
    if present:
        length = int(header[2])
        staged = batch[header_end + 1:header_end + 1 + length]
        offset = header_end + 1 + length + 1
    else:
        staged = b''
        offset = header_end + 1
    rows.append({'path': name, 'expected_sha256': expected,
                 'working_sha256': hashlib.sha256(current).hexdigest(),
                 'index_sha256': hashlib.sha256(staged).hexdigest() if present else None,
                 'index_present': present,
                 'bytes_equal': present and staged == current})
receipt = {'source_inputs': len(rows),
           'manifest_hash_mismatches': [row['path'] for row in rows if row['working_sha256'] != row['expected_sha256']],
           'index_byte_mismatches': [row['path'] for row in rows if not row['bytes_equal']], 'files': rows}
(ROOT / 'docs/delivery/full-recovery/candidate-source-index-verification.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8', newline='\n')
print(json.dumps({key: value for key, value in receipt.items() if key != 'files'}))
raise SystemExit(bool(receipt['manifest_hash_mismatches'] or receipt['index_byte_mismatches']))
