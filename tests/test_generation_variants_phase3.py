from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.idempotency import IdempotencyStore
from app.main import app


@pytest.fixture
def isolated_generation_idempotency_store(tmp_path, monkeypatch):
    """Run-scoped store. Does not read or write repository novel_data."""
    import app.api as api

    store = IdempotencyStore(tmp_path / "idempotency.json")
    monkeypatch.setattr(api, "_idempotency_store", store)
    return store


def test_generation_is_idempotent_under_concurrent_submission(monkeypatch, isolated_generation_idempotency_store):
    from app.api import jobs
    created=[]
    class Item:
        def __init__(self): self.id='one-job'; self.status='QUEUED'; self.base_chapter_version=1
    def create(*args,**kwargs): created.append(1); return Item()
    monkeypatch.setattr(jobs,'create',create)
    headers={'Idempotency-Key':'generation-race-unique'}
    payload={'novel_id':'n','chapter_id':'c','instruction':'继续'}
    def submit(_): return TestClient(app).post('/api/generate/continue',headers=headers,json=payload).json()['job_id']
    with ThreadPoolExecutor(max_workers=3) as pool: ids=list(pool.map(submit,range(3)))
    assert ids==['one-job']*3 and len(created)==1

def test_variant_generation_creates_independent_jobs(monkeypatch):
    from app.api import jobs
    created=[]
    class Item:
        def __init__(self,index): self.id=f"job-{index}";self.status="QUEUED";self.base_chapter_version=7
    def create(operation,payload,actor=None,scope=None):
        created.append((operation,payload));return Item(len(created))
    monkeypatch.setattr(jobs,"create",create)
    response=TestClient(app).post("/api/generate/continue/variants",json={"novel_id":"n","chapter_id":"c","instruction":"向东","count":3})
    assert response.status_code==202
    body=response.json();assert body["count"]==3
    assert [item["job_id"] for item in body["variants"]]==["job-1","job-2","job-3"]
    assert len({item[1]["instruction"] for item in created})==3

def test_variant_generation_limits_count():
    client=TestClient(app)
    assert client.post("/api/generate/continue/variants",json={"novel_id":"n","chapter_id":"c","count":1}).status_code==422
    assert client.post("/api/generate/continue/variants",json={"novel_id":"n","chapter_id":"c","count":4}).status_code==422

def test_variant_lifecycle_accepts_one_and_rejects_the_rest(monkeypatch):
    from app.api import jobs

    class Item:
        def __init__(self,index):
            self.id=f"variant-{index}"
            self.status="COMPLETED"
            self.base_chapter_version=3
            self.output=f"candidate {index}"
        def public(self):
            return {"id":self.id,"status":self.status,"output":self.output}

    items={}
    def create(operation,payload,actor=None,scope=None):
        item=Item(len(items)+1);items[item.id]=item;return item
    def get(jid): return items[jid]
    def accept(jid,content=None,*args):
        items[jid].status="ACCEPTED"
        return {"chapter":{"id":"n:2","content":content or items[jid].output}}
    def reject(jid):
        items[jid].status="REJECTED"
        return items[jid]

    monkeypatch.setattr(jobs,"create",create)
    monkeypatch.setattr(jobs,"get",get)
    monkeypatch.setattr(jobs,"accept",accept)
    monkeypatch.setattr(jobs,"reject",reject)
    monkeypatch.setattr(jobs,"diff",lambda jid:"")
    client=TestClient(app)
    response=client.post("/api/generate/continue/variants",json={"novel_id":"n","chapter_id":"c","count":3})
    job_ids=[row["job_id"] for row in response.json()["variants"]]

    accepted=client.post(f"/api/generation/{job_ids[1]}/accept",json={}).json()
    client.post(f"/api/generation/{job_ids[0]}/reject")
    client.post(f"/api/generation/{job_ids[2]}/reject")

    assert accepted["chapter"]=={"id":"n:2","content":"candidate 2"}
    assert [client.get(f"/api/generation/{jid}").json()["status"] for jid in job_ids]==[
        "REJECTED","ACCEPTED","REJECTED"
    ]

def test_failed_variant_can_be_retried_independently(monkeypatch):
    from app.api import jobs

    class Item:
        def __init__(self,jid,status):
            self.id=jid;self.status=status;self.operation="continue";self.novel_id="n";self.chapter_id="c"
            self.instruction="候选方案 2";self.profile="LOCAL_ONLY";self.requested_provider=None
            self.requested_model=None;self.source="";self.base_chapter_version=4
    failed=Item("failed-variant","FAILED")
    created=[]
    monkeypatch.setattr(jobs,"get",lambda jid:failed)
    def create(operation,payload,actor=None,scope=None):
        created.append((operation,payload));return Item("retried-variant","QUEUED")
    monkeypatch.setattr(jobs,"create",create)

    response=TestClient(app).post("/api/generation/failed-variant/retry")

    assert response.status_code==202
    assert response.json()=={
        "job_id":"retried-variant","status":"QUEUED","events_url":"/api/generation/retried-variant/events",
        "base_chapter_version":4,"retry_of":"failed-variant",
    }
    assert created[0][0]=="continue"
    assert created[0][1]["instruction"]=="候选方案 2"

def test_completed_variant_cannot_be_retried(monkeypatch):
    from app.api import jobs
    item=type("Item",(),{"status":"COMPLETED"})()
    monkeypatch.setattr(jobs,"get",lambda jid:item)
    response=TestClient(app).post("/api/generation/completed/retry")
    assert response.status_code==409
    assert response.json()["detail"]["code"]=="GENERATION_NOT_RETRYABLE"

def test_variant_jobs_can_be_cancelled_independently(monkeypatch):
    from app.api import jobs
    class Item:
        def __init__(self,jid,status):self.id=jid;self.status=status
        def public(self):return {"id":self.id,"status":self.status}
    items={"working-a":Item("working-a","GENERATING"),"working-b":Item("working-b","GENERATING")}
    def cancel(jid):items[jid].status="CANCELLED";return items[jid]
    monkeypatch.setattr(jobs,"cancel",cancel)
    client=TestClient(app)
    assert client.post("/api/generation/working-a/cancel").json()["status"]=="CANCELLED"
    assert client.post("/api/generation/working-b/cancel").json()["status"]=="CANCELLED"
