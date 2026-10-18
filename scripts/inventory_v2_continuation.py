"""Read-only pinned Git source inventory; not a functional acceptance runner."""
from pathlib import Path
import subprocess,json,re,hashlib,argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", default=".runtime/v2-inventory/source.json")
args=parser.parse_args()

def git(*args):return subprocess.check_output(['git',*args])
head=git('rev-parse','HEAD').decode().strip()
tree=git('rev-parse','HEAD^{tree}').decode().strip()
paths=set(git('ls-tree','-r','--name-only',head).decode().splitlines())
p=json.loads(git('show',head+':POST_INTEROP_FEATURE_MATRIX.json'))
ledger=git('show',head+':docs/v2/frozen-capability-ledger-20261016.md').decode()
rows=[]
for x in p['packages']:
 rows.append({'id':x['id'],'name':x['name'],'retained_status':x['current_status'],
  'historical_gap_not_reaudited':x['current_remaining_scope'],'owners':x.get('current_owners',x.get('sources',[])),
  'source_basis':'POST_INTEROP_FEATURE_MATRIX.json','functional_audit':'NOT_REAUDITED_BY_THIS_INVENTORY'})
assert {x['id'] for x in rows}=={'F00'}|{f'A{i:02}' for i in range(1,14)}|{f'B{i:02}' for i in range(1,11)}|{f'U{i:02}' for i in range(1,17)}
for line in ledger.splitlines():
 if not re.match(r'^\| (GRAPH-\d\d|CONSOLE-\d\d|CORE_[A-Z_]+|FS_[A-Z0-9_]+)',line):continue
 columns=[s.strip() for s in line.strip('|').split('|')]
 ident=re.match(r'(GRAPH-\d\d|CONSOLE-\d\d|CORE_[A-Z_]+|FS_[A-Z0-9_]+)',columns[0]).group(0)
 owners=re.findall(r'\]\(\.\./\.\./([^\)]+)\)',line)
 rows.append({'id':ident,'name':columns[0][len(ident):].strip(' —'),'retained_status':'PARTIAL',
  'historical_gap_not_reaudited':columns[-1],'owners':list(dict.fromkeys(owners)),
  'source_basis':'docs/v2/frozen-capability-ledger-20261016.md','functional_audit':'NOT_REAUDITED_BY_THIS_INVENTORY'})
assert {f'GRAPH-{i:02}' for i in range(1,23)}<={x['id'] for x in rows}
assert {f'CONSOLE-{i:02}' for i in range(1,7)}<={x['id'] for x in rows}
assert len(rows)==len({x['id'] for x in rows})
extra={
 'GRAPH-03':(['frontend/src/creative/GraphCanvas.tsx','frontend/src/creative/GraphCanvas.connection.additive.test.tsx'],'Pointer drag connection implementation and focused tests now exist. Historical pointer-MISSING wording is not current absence evidence.'),
 'GRAPH-04':(['frontend/src/creative/GraphCanvas.tsx','frontend/src/creative/GraphCanvas.insertion.additive.test.tsx','frontend/src/creative/StudioGraphInsertion.additive.test.tsx'],'Current canvas insertion controls and tests exist; real keyboard/browser acceptance remains separate.'),
 'GRAPH-06':(['frontend/src/creative/GraphVisualGroups.tsx','frontend/src/creative/graphVisualMembership.ts','frontend/src/creative/graphVisualHierarchy.ts','docs/GRAPH_VISUAL_GROUP_MEMBERSHIP.md'],'Persisted visual groups, two-level hierarchy and explicit direct membership edits exist. Not an executable nested subworkflow.'),
 'GRAPH-08':(['frontend/src/creative/StudioGraphDraftRecovery.tsx','frontend/src/creative/StudioGraphDraftRecovery.test.tsx'],'Explicit graph draft recovery exists; inspect its bounded contract rather than treating old missing text as current absence.'),
 'GRAPH-10':(['frontend/src/creative/GraphCanvasLargeNotes.test.tsx','frontend/src/creative/GraphNoteNavigator.tsx','frontend/src/creative/graphCanvasNotes.ts'],'Large-note bounded rendering and note navigation exist; browser FPS/memory remain unmeasured here.'),
 'CONSOLE-01':(['frontend/src/creative/GraphDirectorConsole.tsx','frontend/src/creative/GraphDirectorProposalReview.tsx','frontend/src/creative/GraphDirectorStoryboardHandoff.tsx'],'Current mounted Console has original review and storyboard handoff; this inventory does not re-run its end-to-end gate.'),
 'A08':(['docs/INDEPENDENT_DIRECTOR_REVIEW.md','docs/DIRECTOR_SHEET_EXPORT.md','frontend/src/creative/GraphDirectorConsole.tsx'],'See current Director/PG/review/CSV slices; film/model quality remains distinct.'),
 'A10':(['app/experimental/research_vision.py','app/experimental/review_adapter_jobs.py','docs/v2/RESEARCH_CURRENT_INCARNATION.md'],'Current-source audit: ReviewAdapterJobs.run rejects non-MOCK_ONLY with ADAPTER_MODEL_ADMISSION_NOT_CONFIGURED. An installed OCR executable alone must not bypass the original JobManager/admission requirement.'),
 'B01':(['docs/REVIEWED_GRAPH_PERSONAL_BRIEF.md'],'Reviewed Graph text to personal brief bridge now exists; no public third-party marketplace.'),
 'U03':(['docs/CREATIVE_DOCUMENT_NAVIGATION.md'],'Read-only creative scene/shot navigation and bounded local search added.'),
 'U02':(['docs/PROMPT_INDEPENDENT_DRAFT.md'],'Independent loaded Prompt copy is a new local manual draft, not durable autosave.'),
 'A12':(['docs/TIMELINE_SOURCE_BOUNDS.md','docs/TIMELINE_REVIEW_PLAYBACK_OPTIONS.md'],'NLE source-bound diagnostics/local repair and cache review controls added; no target NLE interoperability claim.'),
}
missing=[]
for row in rows:
 additions,note=extra.get(row['id'],([],None));row['bounded_current_observation']=note
 row['owners']=list(dict.fromkeys(row['owners']+additions));entries=[]
 for path in row['owners']:
  if path in paths:
   raw=git('show',head+':'+path);entries.append({'path':path,'kind':'file','git_blob':git('rev-parse',head+':'+path).decode().strip(),'sha256':hashlib.sha256(raw).hexdigest(),'last_commit':git('log','-1','--format=%H',head,'--',path).decode().strip()})
  elif any(x.startswith(path.rstrip('/')+'/') for x in paths):entries.append({'path':path,'kind':'directory','tracked_files':sum(x.startswith(path.rstrip('/')+'/') for x in paths)})
  else:entries.append({'path':path,'kind':'ABSENT_AT_PINNED_SOURCE'});missing.append({'id':row['id'],'path':path})
 row['owner_inventory']=entries;del row['owners']
result={'schema_version':1,'source_head':head,'source_tree':tree,'purpose':'Pinned structural continuation inventory, not a full functional audit or completion percentage',
 'historical_statuses_unchanged':True,'total_ids':len(rows),'absent_references':missing,'rows':sorted(rows,key=lambda x:x['id'])}
destination=Path(args.output);destination.parent.mkdir(parents=True,exist_ok=True)
destination.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'source_head':head,'ids':len(rows),'absent_references':missing}))
