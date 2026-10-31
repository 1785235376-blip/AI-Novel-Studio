"""Real narrow File keyed concurrent admission, not a dispatcher double."""
from concurrent.futures import ThreadPoolExecutor
from test_file_keyed_activation import keyed, memory_settings, post, finish
from app.services.generation_project_binding import FIELD


def test_three_real_concurrent_submissions_share_one_bound_mock_worker(keyed):
    f=keyed
    def submit(_):
        response=post(f,key='same-concurrent-key')
        assert response.status_code==202,response.text
        return response.json()
    with ThreadPoolExecutor(max_workers=3) as pool:
        responses=list(pool.map(submit,range(3)))
    assert responses[0]==responses[1]==responses[2]
    assert f.entered.wait(5)
    assert f.counts['worker']==1 and f.counts['provider']==0
    job=f.manager.jobs[responses[0]['job_id']]
    row=f.persistence.get(job.id)
    assert row['status']=='QUEUED' and row[FIELD]['schema_version']==2
    assert row[FIELD]['project_incarnation']==f.incarnation
    assert len(f.bundle.generations.load_all())==1
    finish(f,job)
    assert f.counts['worker']==f.counts['provider']==f.counts['adapter']==1
    assert len(f.responses)==1
    assert post(f,key='same-concurrent-key').json()==responses[0]
