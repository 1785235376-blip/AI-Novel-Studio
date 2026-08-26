from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_scene_create_update_and_chapter_order_round_trip():
    client=TestClient(app);novel=client.post('/api/novels',json={'title':f'Phase5 Scenes {uuid4()}'}).json();nid=novel['id'];chapter=client.post(f'/api/novels/{nid}/chapters',json={'title':'第一章'}).json();base=f'/api/novels/{nid}/scenes'
    client.put(f'{base}/confrontation',json={'title':'码头对峙','sequence':2,'volume_id':'fog','chapter_id':chapter['id'],'location_id':'mist-port','characters':['lin-hai','su-ye'],'purpose':'迫使苏夜合作','conflict':'巡逻队逼近','outcome':'取得密道图','status':'PLANNED'})
    client.put(f'{base}/arrival',json={'title':'抵达雾港','sequence':1,'volume_id':'fog','chapter_id':chapter['id'],'location_id':'mist-port','characters':['lin-hai'],'purpose':'展示封锁','conflict':'证件失效','outcome':'潜入码头','status':'DRAFTED'})
    updated=client.put(f'{base}/confrontation',json={'title':'码头对峙','sequence':2,'volume_id':'fog','chapter_id':chapter['id'],'location_id':'mist-port','characters':['lin-hai','su-ye'],'purpose':'迫使苏夜合作','conflict':'巡逻队逼近','outcome':'共同进入密道','status':'COMPLETED'}).json();rows=client.get(base).json()
    assert [row['id'] for row in rows]==['arrival','confrontation']
    assert updated['status']=='COMPLETED' and rows[1]['characters']==['lin-hai','su-ye']
