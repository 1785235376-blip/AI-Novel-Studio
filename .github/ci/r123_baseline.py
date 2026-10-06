"""Run unchanged supplied reproductions against the fixed pre-fix tree.

These scripts report observations, so an explicit assertion below establishes RED.
No provider/network calls: the supplied scripts disable model networking.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

p = argparse.ArgumentParser()
p.add_argument('--baseline', required=True, type=Path)
p.add_argument('--scripts', required=True, type=Path)
p.add_argument('--output', required=True, type=Path)
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=True)
sha = subprocess.check_output(['git', '-C', str(a.baseline), 'rev-parse', 'HEAD'], text=True).strip()
tree = subprocess.check_output(['git', '-C', str(a.baseline), 'rev-parse', 'HEAD^{tree}'], text=True).strip()
assert sha == 'c6f2126115b52e17839d48efea091dc21ec08c61', sha
assert tree == 'eb80a9fa5f5aa6b8c2cbd0e1e67f7b7a48ac522f', tree
assert sys.version_info[:3] == (3, 12, 9), sys.version
rows = {}
for name in ('repro_project_authority', 'repro_stream_revocation', 'repro_reject_running'):
    script = a.scripts / (name + '.py')
    result = subprocess.run([sys.executable, str(script.resolve()), '--repo', str(a.baseline.resolve()), '--output-dir', str(a.output.resolve())], capture_output=True, text=True, timeout=90)
    (a.output / (name + '.stdout.txt')).write_text(result.stdout)
    (a.output / (name + '.stderr.txt')).write_text(result.stderr)
    (a.output / (name + '.exit-code.txt')).write_text(str(result.returncode) + '\n')
    assert result.returncode == 0, (name, result.stderr)
    rows[name] = {'script_sha256': hashlib.sha256(script.read_bytes()).hexdigest(), 'observations': json.loads(result.stdout)}
r1 = rows['repro_project_authority']['observations']
assert r1['control_project_write_authorization']['status'] == 403
for prefix in ('/api', '/api/v1'):
    r = r1['aliases'][prefix]
    assert r['no_token'] == 401 and r['protected_export'] == 403
    assert all(r[k] == 200 for k in ('goal_get', 'goal_put', 'raw_novel_get', 'chapters_get', 'overview'))
    assert r['chapter_content_disclosed'] and r['goal_persisted']['target_words'] == 4321 and r['goal_persisted']['target_chapters'] == 7
r2 = rows['repro_stream_revocation']['observations']['result']
assert r2['new_read_after_revocation'] == 401 and r2['post_revocation_output_disclosed']
for r in rows['repro_reject_running']['observations']['results']:
    assert r['before'] == {'status': 'GENERATING', 'output': 'SYNTHETIC_FIRST_CHUNK'}
    assert r['reject'] == {'http': 200, 'state': 'REJECTED', 'cancelled': False}
    assert r['final_status'] == r['persisted_status'] == 'COMPLETED'
    assert r['final_output'] == 'SYNTHETIC_FIRST_CHUNK'
receipt = {'baseline_sha': sha, 'baseline_tree': tree, 'python': sys.version, 'result': 'ALL_THREE_KNOWN_DEFECTS_REPRODUCED_RED', 'scripts_exit_zero_is_not_pass': True, 'reproductions': rows}
(a.output / 'baseline-red.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(receipt, ensure_ascii=False, indent=2))
