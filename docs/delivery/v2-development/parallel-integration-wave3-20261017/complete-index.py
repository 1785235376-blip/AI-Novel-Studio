"""Close evidence only after primary and independent writers are terminal."""
import hashlib, json, pathlib
R = pathlib.Path.cwd()
E = R / 'docs/delivery/v2-development'
D = E / 'parallel-integration-wave3-20261017'
index = json.loads((D / 'evidence-index.json').read_text())
freeze = json.loads((D / 'release-freeze-r2.json').read_text())
for p, h in index['artifacts'].items():
    assert hashlib.sha256((R / p).read_bytes()).hexdigest() == h, p
independent = json.loads((D / 'independent-terminal-audit-r1.json').read_text())
assert independent['status'] == 'PASS_INDEPENDENT_WAVE3_TERMINAL'
assert independent['head'] == index['head'] == freeze['head']
for item in independent['receipts']:
    path = R / item['receipt']
    assert hashlib.sha256(path.read_bytes()).hexdigest() == item['receipt_sha256']
    receipt = json.loads(path.read_text())
    assert receipt['status'] == 'PASS' and receipt['exit_code'] == 0
    assert receipt['head'] == freeze['head']
    assert not receipt['sources_changed_during_check']
    assert receipt['source_sha256_before'] == receipt['source_sha256'] == freeze['source_sha256']
    assert hashlib.sha256((R / receipt['log']).read_bytes()).hexdigest() == receipt['log_sha256'] == item['log_sha256']
paths = [p for p in D.rglob('*') if p.is_file() and p.name != 'complete-index.json']
for prefix in ('wave3-integration-', 'wave3-independent-'):
    paths += list(E.glob(prefix + '*-r*.json')) + list(E.glob(prefix + '*-r*.log'))
result = {'status': 'PASS_COMPLETE_PRIMARY_AND_INDEPENDENT_EVIDENCE', 'head': index['head'],
          'files': {p.relative_to(R).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths))}}
(D / 'complete-index.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'status': result['status'], 'files': len(result['files'])}))
