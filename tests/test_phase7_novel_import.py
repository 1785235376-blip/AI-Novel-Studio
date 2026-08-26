from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.main import app

def test_novel_export_supports_txt_and_epub():
    client=TestClient(app)
    created=client.post('/api/novels',json={'title':f'导出-{uuid4()}','genre':'测试'}).json()
    client.post(f"/api/novels/{created['id']}/chapters",json={'title':'第一章','content':'正文内容'})
    response=client.get(f"/api/novels/{created['id']}/export",params={'format':'txt'})
    assert response.status_code==200
    payload=response.json()
    assert payload['format']=='txt' and payload['filename'].endswith('.txt') and '正文内容' in payload['content']
    epub=client.get(f"/api/novels/{created['id']}/export",params={'format':'epub'})
    assert epub.status_code==200 and epub.json()['format']=='epub' and epub.json()['filename'].endswith('.epub')


def test_text_import_preview_splits_chinese_chapters_without_writing():
    client=TestClient(app);title=f"雾港-{uuid4()}"
    content=f"{title}\n第1章 抵达\n雾中来客。\n第2章 封锁\n港口关闭。"
    before=len(client.get('/api/novels').json())
    response=client.post('/api/novels/import',json={'format':'txt','content':content,'confirm':False})
    assert response.status_code==200
    preview=response.json()['preview']
    assert preview['title']==title and preview['chapter_count']==2
    assert [item['title'] for item in preview['chapters']]==['第1章 抵达','第2章 封锁']
    assert response.json()['plan']['chapters'][0]['content']=='雾中来客。'
    assert len(client.get('/api/novels').json())==before


def test_markdown_import_confirm_creates_chapters():
    client=TestClient(app);title=f"群星-{uuid4()}"
    content=f"# {title}\n## 第一章 启程\n离开母星。\n## 第二章 回声\n收到信号。"
    response=client.post('/api/novels/import',json={'format':'markdown','content':content,'confirm':True})
    assert response.status_code==200
    payload=response.json();novel_id=payload['novel']['id']
    chapters=client.get(f'/api/novels/{novel_id}/chapters').json()
    assert payload['preview']['chapter_count']==2
    assert [chapter['title'] for chapter in chapters]==['第一章 启程','第二章 回声']

def test_confirmed_import_is_idempotent_under_concurrent_submission():
    title=f"并发导入-{uuid4()}"; content=f"# {title}\n## 第一章\n正文"
    payload={'format':'markdown','content':content,'confirm':True}; headers={'Idempotency-Key':f'import-{uuid4()}'}
    def submit(_): return TestClient(app).post('/api/novels/import',headers=headers,json=payload).json()['novel']['id']
    with ThreadPoolExecutor(max_workers=3) as pool: ids=list(pool.map(submit,range(3)))
    assert len(set(ids))==1


def test_import_rejects_empty_or_unknown_format():
    client=TestClient(app)
    assert client.post('/api/novels/import',json={'format':'txt','content':'','confirm':False}).status_code==400
    assert client.post('/api/novels/import',json={'format':'docx','content':'data','confirm':False}).status_code==400

def test_import_preview_returns_reviewable_knowledge_base_candidates_without_writing():
    client=TestClient(app)
    content="第1章 抵达\n林默说道：我们到了雾港。秘密仍未揭开。"
    response=client.post('/api/novels/import',json={'format':'txt','content':content,'confirm':False})
    assert response.status_code==200
    knowledge=response.json()['preview']['knowledge_base']
    assert knowledge['status']=='CANDIDATES_REVIEW_REQUIRED'
    assert any(item['name']=='林默' for item in knowledge['candidates']['characters'])
    assert any(item['name']=='雾港' for item in knowledge['candidates']['locations'])
    assert knowledge['candidates']['timeline_events'][0]['chapter_number']==1
    assert knowledge['candidates']['foreshadowing']

def test_import_knowledge_review_accepts_candidates_and_rejects_without_writing():
    client=TestClient(app)
    novel=client.post('/api/novels',json={'title':f'Review-{uuid4()}','genre':'Imported'}).json()
    candidates={'characters':[{'name':'林默'}],'locations':[{'name':'雾港'}],'timeline_events':[{'title':'抵达','chapter_number':1,'description':'到达'}],'foreshadowing':[{'title':'秘密'}]}
    accepted=client.post(f"/api/novels/{novel['id']}/import/knowledge-base/review",json={'decision':'ACCEPTED','candidates':candidates})
    assert accepted.status_code==200
    assert len(accepted.json()['applied']['characters'])==1
    assert any(x['name']=='林默' for x in client.get(f"/api/novels/{novel['id']}/characters").json())
    rejected=client.post(f"/api/novels/{novel['id']}/import/knowledge-base/review",json={'decision':'REJECTED','candidates':candidates})
    assert rejected.status_code==200 and all(not values for values in rejected.json()['applied'].values())
