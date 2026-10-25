from contextlib import contextmanager
import pytest
from test_file_keyed_activation import keyed, memory_settings, queued, finish, replace_owner, files
from app.services.generation_project_binding import FIELD
pytestmark=pytest.mark.file_backend_only

@pytest.mark.parametrize('stage',['manual','memory'])
def test_adoption_chain_final_receipt_owner_entry_replacement(keyed,stage):
    f=keyed
    _,job=queued(f); finish(f,job)
    repository=f.bundle.generations; original=repository._graph_owner
    replaced=[]; retained={}; replacement={}
    @contextmanager
    def scheduled(row,binding):
        with original(row,binding):
            match=(stage=='manual' and row.get('status')=='ACCEPTED' and FIELD in row) or (stage=='memory' and row.get('status')=='COMPLETED' and 'memory_project_binding' in row)
            if match and not replaced:
                path=repository.root/(row['id']+'.json')
                retained['path']=path; retained['bytes']=path.read_bytes()
                replace_owner(f); replaced.append(True); replacement.update(files(f))
            yield
    f.monkeypatch.setattr(repository,'_graph_owner',scheduled)
    response=f.client.post(f'/api/generation/{job.id}/accept',json={'expected_version':1})
    if stage=='memory': assert f.memory_finished.wait(10)
    assert replaced, (stage,response.status_code,response.text)
    assert files(f)==replacement
    assert retained['path'].read_bytes()==retained['bytes'], f'late {stage} receipt was durably written after owner replacement'
