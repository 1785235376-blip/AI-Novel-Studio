import json,os,hashlib
from pathlib import Path
import psycopg
baseline=json.loads(Path('docs/delivery/v2-development/comic-collections-postgres-2-cleanup.json').read_text())['after']['tables']
with psycopg.connect(os.environ['TEST_POSTGRES_DATABASE_URL']) as c:
    current={table:sorted(r[0] for r in c.execute('SELECT row_to_json(t)::text FROM '+table+' t').fetchall()) for table in ('novels','experimental_scope_documents')}
extra={t:[json.loads(r) for r in rows if r not in baseline[t]] for t,rows in current.items()}
missing={t:[json.loads(r) for r in rows if r not in current[t]] for t,rows in baseline.items()}
proof={'current_counts':{t:len(r) for t,r in current.items()},'baseline_counts':{t:len(r) for t,r in baseline.items()},'extra':extra,'missing':missing,'row_sha256':{t:[hashlib.sha256(r.encode()).hexdigest() for r in rows] for t,rows in current.items()}}
Path('docs/delivery/v2-development/style-vision-interrupted-durable-probe.json').write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps({'current_counts':proof['current_counts'],'extra_novels':[(r.get('id'),r.get('slug'),r.get('title')) for r in extra['novels']],'extra_scope_rows':len(extra['experimental_scope_documents']),'missing_counts':{t:len(r) for t,r in missing.items()}}))
