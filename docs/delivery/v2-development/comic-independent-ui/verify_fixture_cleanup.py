"""Bounded cleanup of this Comic test's own orphan scopes, then marked regressions."""
import json, os, re, subprocess, sys
from pathlib import Path
import psycopg
url = os.environ['TEST_POSTGRES_DATABASE_URL']
proof = Path('docs/delivery/v2-development/comic-independent-ui/fixture-cleanup.json')
receipt = {'purpose': 'Exact orphan scopes created by Comic epoch test before teardown correction', 'deleted': []}
with psycopg.connect(url) as connection:
    rows = connection.execute("SELECT scope_key, novel_id, document FROM experimental_scope_documents WHERE novel_id LIKE 'comic-epoch-%' OR novel_id LIKE 'blank-comic-%'").fetchall()
    receipt['before'] = [{'scope_key': key, 'novel_id': nid} for key,nid,_ in rows]
    assert len(rows) <= 2, 'Unexpected number of prior Comic fixtures; no cleanup authorized'
    for key, nid, document in rows:
        assert re.fullmatch(r'comic-epoch-[0-9a-f]{32}', nid)
        assert not connection.execute('SELECT 1 FROM novels WHERE slug = %s', (nid,)).fetchone()
        assert set(document['collections']) == {'comic_layouts_v2'}
        records = document['collections']['comic_layouts_v2']
        assert len(records) == 2
        for record in records.values():
            assert record['created_by'] == 'local-author'
            assert record['document']['source_mode'] == 'INDEPENDENT'
            assert record['document']['title'] in {'独立页', 'Private old title'}
        connection.execute('DELETE FROM experimental_scope_documents WHERE scope_key = %s AND novel_id = %s', (key, nid))
        receipt['deleted'].append({'scope_key': key, 'novel_id': nid})
    receipt['after_prior_cleanup'] = connection.execute("SELECT count(*) FROM experimental_scope_documents WHERE novel_id LIKE 'comic-epoch-%' OR novel_id LIKE 'blank-comic-%'").fetchone()[0]
proof.write_text(json.dumps(receipt, indent=2))
command = [sys.executable, '-m', 'pytest', 'tests/test_comic_independent.py', '-m', 'postgres_backend_only', '-p', 'no:cacheprovider', '--basetemp=.runtime/v2-checks/comic-independent-cleanup/pytest', '-q']
receipt['regression_command'] = command
result = subprocess.run(command)
receipt['regression_exit_code'] = result.returncode
with psycopg.connect(url) as connection:
    receipt['after_regressions_scope_count'] = connection.execute("SELECT count(*) FROM experimental_scope_documents WHERE novel_id LIKE 'comic-epoch-%' OR novel_id LIKE 'blank-comic-%'").fetchone()[0]
    receipt['after_regressions_project_count'] = connection.execute("SELECT count(*) FROM novels WHERE slug LIKE 'comic-epoch-%' OR slug LIKE 'blank-comic-%'").fetchone()[0]
proof.write_text(json.dumps(receipt, indent=2))
print(json.dumps(receipt))
assert receipt['after_regressions_scope_count'] == receipt['after_regressions_project_count'] == 0
sys.exit(result.returncode)
