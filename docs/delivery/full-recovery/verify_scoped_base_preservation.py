"""Assert every original runtime record survives the six-wheel extension exactly."""
from pathlib import Path
from collections import Counter
import hashlib
import json
ROOT=Path(__file__).resolve().parents[3]
original_path=ROOT/'.runtime/full-recovery/pr45-approved-application/Application/base-input-provenance.json'
base=ROOT/'.runtime/full-recovery/windows-base-final'
before=json.loads(original_path.read_text(encoding='utf-8'))
after=json.loads((base/'base-input-provenance.json').read_text(encoding='utf-8'))
assert after['files'][:len(before['files'])]==before['files']
for row in after['files']:
    path=base/row['path']
    assert path.resolve().is_relative_to(base.resolve())
    data=path.read_bytes()
    assert len(data)==row['size'] and hashlib.sha256(data).hexdigest()==row['sha256']
scopes=dict(Counter(row['path'].split('/')[0] for row in after['files']))
assert set(scopes)=={'Runtime','PostgreSQL','Licenses','PREREQUISITES.txt'}
assert before['inputs']['runtime_inputs']==after['inputs']['runtime_inputs']
assert all(row in after['inputs']['wheels'] for row in before['inputs']['wheels'])
receipt={'status':'PASS','original_base_records':len(before['files']),'extended_records':len(after['files']),
         'all_original_entries_sizes_hashes_and_order_exact':True,'every_extended_file_sha256_verified':True,
         'original_runtime_inputs_unchanged':True,'original_wheel_records_unchanged':True,
         'original_provenance_sha256':hashlib.sha256(original_path.read_bytes()).hexdigest(),
         'extended_provenance_sha256':hashlib.sha256((base/'base-input-provenance.json').read_bytes()).hexdigest(),
         'top_level_scopes':scopes,'source_payload_in_base':False}
(ROOT/'docs/delivery/full-recovery/scoped-base-original-record-preservation.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(receipt,indent=2))
