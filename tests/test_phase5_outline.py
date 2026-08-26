from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_outline_create_and_update_round_trip():
    client=TestClient(app);novel=client.post('/api/novels',json={'title':f'Phase5 Outline {uuid4()}'}).json();url=f"/api/novels/{novel['id']}/outline"
    created=client.put(url,json={'theme':'信任与代价','premise':'记者追查雾港封锁真相。','structure':'THREE_ACT','beginning':'罗盘失灵','middle':'盟友背叛','ending':'公开真相','main_conflict':'真相与家族安全冲突','climax':'灯塔对峙','status':'DRAFT'}).json()
    updated=client.put(url,json={**created,'status':'ACTIVE','ending':'保留证据并救出家人'}).json();stored=client.get(url).json()
    assert updated['status']=='ACTIVE' and stored['theme']=='信任与代价'
    assert stored['ending']=='保留证据并救出家人' and stored['structure']=='THREE_ACT'
