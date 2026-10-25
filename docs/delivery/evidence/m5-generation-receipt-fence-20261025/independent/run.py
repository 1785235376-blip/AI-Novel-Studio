import os,sys,socket
from pathlib import Path
root=Path(os.environ.get('REVIEW_TARGET','/workspace/scratch/20a0022d2b33/studio-m5-receipt-fence'))
sys.path[:0]=[str(root),str(root/'tests')]
os.chdir(root)
def denied(*a,**k):raise AssertionError('Network access prohibited in independent review')
socket.socket.connect=denied
socket.create_connection=denied
import pytest
raise SystemExit(pytest.main(['-o','cache_dir=/workspace/scratch/20a0022d2b33/review-m5-receipt-independent/pytest-cache']+sys.argv[1:]))
