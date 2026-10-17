"""Natural or original-runner child startup proof, without product/test imports."""
from pathlib import Path
import importlib.util
import json
import sys
root = Path('/workspace/scratch/20a0022d2b33/studio-director-canvas-handoff')
expected = Path('/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1')
assert Path(sys.prefix) == expected, (sys.prefix, expected)
print(json.dumps({'executable': sys.executable, 'prefix': sys.prefix, 'runner': str(root / 'scripts/run_v2_checks.py'),
  'module_origins': {name: importlib.util.find_spec(name).origin for name in ('json', 'pytest', 'pydantic', 'PIL')},
  'product_imported': any(name == 'app' or name.startswith('app.') for name in sys.modules)}, indent=2))
