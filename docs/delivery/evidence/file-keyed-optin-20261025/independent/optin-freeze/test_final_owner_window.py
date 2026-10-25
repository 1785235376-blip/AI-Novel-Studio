from contextlib import contextmanager
import pytest
from test_file_keyed_activation import keyed, memory_settings, queued, replace_owner, files
from app.services.generation_project_binding import FIELD
pytestmark=pytest.mark.file_backend_only

def test_original_generation_owner_lease_entry_replacement_fences_final_write(keyed):
    f=keyed
    repository=f.bundle.generations
    original=repository._graph_owner
    replaced=[]; retained={}; replacement={}
    @contextmanager
    def scheduled(row,binding):
        with original(row,binding):
            if row.get('status')=='COMPLETED' and FIELD in row and not replaced:
                path=repository.root/(row['id']+'.json')
                retained['path']=path; retained['bytes']=path.read_bytes()
                replace_owner(f); replaced.append(True)
                replacement.update(files(f))
            yield
    f.monkeypatch.setattr(repository,'_graph_owner',scheduled)
    _,job=queued(f)
    f.release.set(); assert f.finished.wait(10)
    assert replaced and f.counts['provider']==1
    assert files(f)==replacement
    assert job.status!='COMPLETED'
    assert retained['path'].read_bytes()==retained['bytes'], 'late original-owner COMPLETED receipt was written after genuine owner replacement'
