"""Bind final primary receipts, logs, reports and retained artifact inventories."""
from pathlib import Path
import hashlib
import json
root = Path('/workspace/scratch/20a0022d2b33/studio-director-pending')
directory = root / 'docs/delivery/v2-development/director-pending-20261017'
paths = set(p for p in directory.rglob('*') if p.is_file() and p.name not in {'complete-index.json', 'complete-index.log'})
for stage in ('origin-before', 'new', 'regression', 'packaging', 'ui', 'type', 'build', 'token', 'origin-after'):
    for suffix in ('json', 'log'):
        paths.add(root / f'docs/delivery/v2-development/director-pending-{stage}-r1.{suffix}')
for stage in ('origin-before', 'new', 'regression', 'origin-after'):
    for suffix in ('json', 'log'):
        paths.add(root / f'docs/delivery/v2-development/director-pending-{stage}-independent-r1.{suffix}')
paths.add(root / 'docs/INDEPENDENT_DIRECTOR_PENDING_REVIEW.md')
result = {'status': 'PASS_PRIMARY_AND_INDEPENDENT_COMPLETE',
    'files': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}}
(directory / 'complete-index.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'files': len(paths), 'index_sha256': hashlib.sha256((directory / 'complete-index.json').read_bytes()).hexdigest()}))
