import json, os, subprocess, sys
from pathlib import Path
import psycopg
url=os.environ['TEST_POSTGRES_DATABASE_URL']
def snapshot():
    with psycopg.connect(url) as c:
        identity=c.execute("SELECT current_database(), (SELECT oid FROM pg_database WHERE datname=current_database()), current_setting('server_encoding'), version()").fetchone()
        assert identity[1]==16384 and identity[2]=='UTF8', identity
        return {'identity':list(identity),'tables':{table:sorted(r[0] for r in c.execute('SELECT row_to_json(t)::text FROM '+table+' t').fetchall()) for table in ('novels','experimental_scope_documents')}}
before=snapshot()
command=[sys.executable,'-m','pytest','tests/test_comic_collections.py','tests/test_comic_independent.py','tests/test_r5_comic_mounted.py','-m','postgres_backend_only','-p','no:cacheprovider','--basetemp=.runtime/v2-checks/comic-collections-postgres-2/pytest','-q']
result=subprocess.run(command)
after=snapshot()
proof={'command':command,'exit_code':result.returncode,'before':before,'after':after,'exact_cleanup_equal':before==after}
Path('docs/delivery/v2-development/comic-collections-postgres-2-cleanup.json').write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps({'exit_code':result.returncode,'exact_cleanup_equal':before==after,'before_counts':{t:len(r) for t,r in before['tables'].items()},'after_counts':{t:len(r) for t,r in after['tables'].items()}}))
assert before==after, 'Exact before/after rows differ; inspect fixture ownership before cleanup'
sys.exit(result.returncode)
