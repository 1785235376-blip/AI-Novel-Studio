from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_volume_create_update_and_order_round_trip():
    client=TestClient(app);novel=client.post('/api/novels',json={'title':f'Phase5 Volumes {uuid4()}'}).json();base=f"/api/novels/{novel['id']}/volumes"
    client.put(f'{base}/truth',json={'title':'真相卷','sequence':2,'goal':'揭露雾港秘密','summary':'进入灯塔','start_chapter':9,'end_chapter':16,'status':'PLANNED'})
    client.put(f'{base}/fog',json={'title':'迷雾卷','sequence':1,'goal':'建立悬念','summary':'罗盘失灵','start_chapter':1,'end_chapter':8,'status':'WRITING'})
    updated=client.put(f'{base}/truth',json={'title':'真相卷','sequence':2,'goal':'揭露雾港秘密','summary':'灯塔对峙','start_chapter':9,'end_chapter':15,'status':'WRITING'}).json();rows=client.get(base).json()
    assert [row['id'] for row in rows]==['fog','truth']
    assert updated['end_chapter']==15 and rows[1]['status']=='WRITING'
