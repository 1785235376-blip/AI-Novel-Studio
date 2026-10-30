import os
import pytest
from app.services.export_job_service import ExportJobService

@pytest.mark.parametrize('failure',['fstat','fdopen'])
def test_descriptor_closes_if_setup_fails(tmp_path,monkeypatch,failure):
    target=tmp_path/'artifact';target.write_bytes(b'contents')
    service=ExportJobService.__new__(ExportJobService)
    original_open=os.open
    seen=[]
    def tracked(*args,**kwargs):
        fd=original_open(*args,**kwargs);seen.append(fd);return fd
    def broken(*args,**kwargs): raise OSError('synthetic I/O failure')
    with monkeypatch.context() as m:
        m.setattr(os,'open',tracked)
        m.setattr(os,failure,broken)
        with pytest.raises(OSError,match='synthetic'):
            service._read_artifact_file(target)
    assert len(seen)==1
    with pytest.raises(OSError):os.fstat(seen[0])
