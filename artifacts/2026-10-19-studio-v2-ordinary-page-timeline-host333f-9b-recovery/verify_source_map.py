"""Read-only verifier: no application imports, tests, checkouts, refs or network."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

parser=argparse.ArgumentParser()
parser.add_argument('--repo',required=True,type=Path)
parser.add_argument('--tip',help='Optional git-am reconstructed backend tip; exact expected tree is still required')
parser.add_argument('--candidate',action='store_true',help='Verify recorded candidate metadata, not acceptance')
args=parser.parse_args()
root=Path(__file__).resolve().parent
manifest=json.loads((root/'SOURCE_MAP.json').read_text(encoding='utf-8'))
def git(*cmd,data=None): return subprocess.check_output(['git',*cmd],cwd=args.repo,input=data)
def txt(*cmd): return git(*cmd).decode().strip()
def sha(data): return hashlib.sha256(data).hexdigest()
base=manifest['uniqueExternalPrerequisite']
git('cat-file','-e',base+'^{commit}')
assert sha((root/'BACKEND_RESTORE_9b_to_65.patch').read_bytes()) == manifest['restoration']['patchSha256']
tip=args.tip or manifest['backendTip']
assert txt('rev-parse',tip+'^{tree}') == manifest['backendTree']
commits=txt('rev-list','--reverse',base+'..'+tip).splitlines()
assert len(commits)==len(manifest['backendCommits'])
for commit,expected in zip(commits,manifest['backendCommits']):
    result=git('patch-id','--stable',data=git('show','--format=','--binary',commit)).decode().split()[0]
    assert result==expected['stablePatchId']
    if not args.tip:
        assert commit==expected['commit']
        assert txt('show','-s','--format=%P',commit).split()==expected['parents']
for item in json.loads((root/'BACKEND_FINAL_FILES.json').read_text(encoding='utf-8')):
    assert sha(git('show',tip+':'+item['path']))==item['sha256']
    assert txt('rev-parse',tip+':'+item['path'])==item['blob']
if args.candidate:
    pending=manifest['candidateCombination']
    assert txt('rev-parse',pending['tip']+'^{tree}')==pending['tree']
    for item in pending['commits']:
        assert txt('show','-s','--format=%P',item['commit']).split()==item['parents']
        result=git('patch-id','--stable',data=git('show','--format=','--binary',item['commit'])).decode().split()[0]
        assert result==item['stablePatchId']
    for path in manifest['backendCommits'][-1]['changedPaths']:
        assert git('show',tip+':'+path)==git('show',pending['tip']+':'+path)
print(json.dumps(dict(status='SOURCE_METADATA_MATCHES',base=base,backendTip=tip,
    backendCommits=len(commits),candidateMetadataChecked=args.candidate,
    acceptanceInferred=False,noMutation=True),indent=2))
