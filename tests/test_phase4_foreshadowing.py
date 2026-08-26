from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_foreshadowing_create_and_update_round_trip():
    client = TestClient(app)
    novel = client.post("/api/novels", json={"title": f"Phase4 Foreshadowing {uuid4()}"}).json()
    url = f"/api/novels/{novel['id']}/foreshadowing/broken-compass"
    created = client.put(url, json={"title": "破损罗盘", "description": "指针总指向雾港", "planted_chapter": 1, "target_chapter": 8, "characters": ["lin-hai"], "events": ["port-lockdown"]}).json()
    updated = client.put(url, json={**created, "status": "PAID_OFF", "target_chapter": 7}).json()
    rows = client.get(f"/api/novels/{novel['id']}/foreshadowing").json()
    assert updated["status"] == "PAID_OFF"
    assert rows[0]["id"] == "broken-compass"
    assert rows[0]["characters"] == ["lin-hai"]
    assert rows[0]["events"] == ["port-lockdown"]
    assert rows[0]["target_chapter"] == 7
