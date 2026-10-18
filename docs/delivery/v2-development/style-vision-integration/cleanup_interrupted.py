import hashlib,json,os
from pathlib import Path
import psycopg
from app.repositories.postgres import Database,PostgresNovelRepository
url=os.environ['TEST_POSTGRES_DATABASE_URL']
proof=json.loads(Path('docs/delivery/v2-development/style-vision-interrupted-durable-probe.json').read_text())
assert not any(proof['missing'].values()) and not proof['extra']['experimental_scope_documents']
assert len(proof['extra']['novels'])==1
expected=proof['extra']['novels'][0]
assert expected['id']=='32802152-0da5-4aef-a409-5ecce8d60a91'
assert expected['slug']=='r3-mounted-dae7e39b0c9145149a893148c5f5e105' and expected['title']=='Synthetic mounted R3'
with psycopg.connect(url) as c:
    raw=c.execute('SELECT row_to_json(t)::text FROM novels t WHERE id=%s AND slug=%s',(expected['id'],expected['slug'])).fetchone()
    assert raw and json.loads(raw[0])==expected
    before_hash=hashlib.sha256(raw[0].encode()).hexdigest()
# Use the same original project-retirement owner as normal fixture teardown.
database=Database(url)
try:PostgresNovelRepository(database).delete(expected['slug'])
finally:database.engine.dispose()
baseline=json.loads(Path('docs/delivery/v2-development/comic-collections-postgres-2-cleanup.json').read_text())['after']['tables']
with psycopg.connect(url) as c:
    after={t:sorted(r[0] for r in c.execute('SELECT row_to_json(t)::text FROM '+t+' t').fetchall()) for t in ('novels','experimental_scope_documents')}
assert after==baseline,'Unexpected state after exact synthetic fixture cleanup'
result={'exact_synthetic_id':expected['id'],'exact_slug':expected['slug'],'before_row_sha256':before_hash,'owner':'PostgresNovelRepository.delete','baseline_restored':True,'after_counts':{t:len(r) for t,r in after.items()}}
Path('docs/delivery/v2-development/style-vision-interrupted-cleanup-proof.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
