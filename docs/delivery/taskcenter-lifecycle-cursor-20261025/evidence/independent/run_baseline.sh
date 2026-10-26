#!/bin/sh
set -eu
cd /tmp
export XDG_DATA_HOME=/tmp/taskcenter-owner-evidence/xdg
export NOVEL_DATA=/tmp/taskcenter-owner-evidence/runtime
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=/tmp/taskcenter-independent-6363:/tmp/taskcenter-independent-6363/tests
/workspace/scratch/20a0022d2b33/studio-overnight/.venv/bin/python -m pytest -p conftest /tmp/taskcenter-owner-evidence/test_owner_risks.py -v -s --tb=short -p no:cacheprovider
