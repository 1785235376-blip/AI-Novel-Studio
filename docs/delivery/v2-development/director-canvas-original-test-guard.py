"""Read-only byte guard for every baseline test/config/fixture source; no product imports."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
root = Path('/workspace/scratch/20a0022d2b33/studio-director-canvas-handoff')
base = '9b72ff93b48dbed4c2631a83222843829ecb5505'
paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', base], cwd=root, text=True).splitlines()
paths = [p for p in paths if p.startswith(('tests/', 'frontend/tests/')) or '.test.' in p or '.testFixture' in p or p.startswith('frontend/') and ('vitest' in p or 'playwright' in p) or p in ('pyproject.toml', 'scripts/run_v2_checks.py')]
failures = []
for path in paths:
    expected = subprocess.check_output(['git', 'show', f'{base}:{path}'], cwd=root)
    current = root / path
    if not current.is_file() or current.read_bytes() != expected:
        failures.append(path)
print(json.dumps({'baseline': base, 'checked_paths': len(paths), 'unchanged': not failures, 'failures': failures}, indent=2))
sys.exit(bool(failures))
