"""Run after all supplemental writers have stopped; stdout must stay outside indexed files."""
import hashlib, json, pathlib
R = pathlib.Path.cwd()
E = R / 'docs/delivery/v2-development'
D = E / 'parallel-integration-wave3-canvas-supplement-20261017'
a = json.loads((D / 'terminal-audit.json').read_text())
assert a['status'] == 'PASS_FRONTEND_ONLY_SUPPLEMENT'
paths = [p for p in D.rglob('*') if p.is_file() and p.name != 'complete-index.json']
paths += list(E.glob('wave3-canvas-supplement-*-r1.json')) + list(E.glob('wave3-canvas-supplement-*-r1.log'))
result = {'status': 'PASS_COMPLETE_SUPPLEMENT_EVIDENCE', 'head': a['head'], 'files': {p.relative_to(R).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}, 'reused_historical_evidence': {'path': 'docs/delivery/v2-development/parallel-integration-wave3-20261017/complete-index.json', 'sha256': a['historical_complete_index_sha256'], 'head': a['historical_accepted_head']}}
(D / 'complete-index.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'status': result['status'], 'files': len(result['files'])}))
