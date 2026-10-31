#!/bin/sh
set -eu
cd /tmp
export XDG_DATA_HOME=/tmp/taskcenter-owner-evidence/frozen-xdg
export NOVEL_DATA=/tmp/taskcenter-owner-evidence/frozen-runtime
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=/tmp/taskcenter-independent-774e:/tmp/taskcenter-independent-774e/tests
/workspace/scratch/20a0022d2b33/studio-overnight/.venv/bin/python -m pytest -p conftest /tmp/taskcenter-owner-evidence/test_green_contracts.py /tmp/taskcenter-owner-evidence/test_committed_observation_contract.py /tmp/taskcenter-owner-evidence/test_http_lifecycle_contract.py -v --tb=short -p no:cacheprovider
