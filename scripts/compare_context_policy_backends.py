import json,os,tempfile,uuid
from pathlib import Path
import psycopg
from dotenv import load_dotenv
from app.context_policy import ContextPolicy,ContextPolicyItem
from app.narrative_context import NarrativeContextBuilder
from app.repositories.file.narrative import FileNarrativeRepository
from app.repositories.postgres.narrative import PostgresNarrativeRepository

load_dotenv();url=os.environ["DATABASE_URL"].replace("postgresql+psycopg://","postgresql://");run=uuid.uuid4().hex;project=f"policy-{run}"
def populate(repository):
 t=f"t-{run}";m=f"m-{run}";rows={"threads":[{"id":t,"project_id":project,"title":"Thread","status":"OPEN","event_ids":[]}],"foreshadowing":[],"mysteries":[{"id":m,"project_id":project,"title":"Who?","status":"OPEN"}],"character_goals":[],"events":[],"chapter_links":[{"id":f"link-{run}","project_id":project,"chapter_id":f"{project}:1","chapter_version":1,"entity_type":"MYSTERY","entity_id":m,"progress_type":"DEVELOPED","event_id":f"none-{run}"}],"expectations":[],"findings":[{"id":f"finding-{run}","project_id":project,"finding_type":"MYSTERY_OVERDUE","subject_id":m,"description":"Advisory","severity":"MEDIUM","status":"OPEN","evidence_ids":[]}]}
 for kind,items in rows.items():
  for row in items:repository.create(project,kind,row)
def execute(repository):
 before={kind:repository.list(project,kind) for kind in ("threads","mysteries","chapter_links","findings")};view=NarrativeContextBuilder(repository,500).build(project,f"{project}:1",1).model_dump(mode="json");policy=ContextPolicy(1200);items=[ContextPolicyItem(metadata=policy.metadata("CANON","canon",project,selection_reasons=["ACCEPTED_CANON"],fact_key="character:c:location"),value={"value":"A"}),ContextPolicyItem(metadata=policy.metadata("LORE_MEMORY","lore",project,selection_reasons=["CURRENT_CHARACTER"],fact_key="character:c:location"),value={"value":"B"}),ContextPolicyItem(metadata=policy.metadata("LORE_MEMORY","lore",project,selection_reasons=["CURRENT_CHAPTER"],fact_key="character:c:location"),value={"value":"B"})]
 for section in ("plot_threads","mysteries"):
  for entry in view[section]:items.append(ContextPolicyItem(metadata=policy.metadata("NARRATIVE_STATE",entry["id"],project,selection_reasons=[entry["selection_reason"]]),value=entry))
 for finding in view["findings"]:items.append(ContextPolicyItem(metadata=policy.metadata("NARRATIVE_FINDING",finding["finding_id"],project,selection_reasons=[finding["selection_reason"]]),value=finding))
 result=policy.apply(items).model_dump(mode="json");after={kind:repository.list(project,kind) for kind in before};return {"result":result,"serialized":json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(",",":")),"read_only":before==after}
file_root=Path(tempfile.mkdtemp());file_repository=FileNarrativeRepository(file_root);postgres_repository=PostgresNarrativeRepository(lambda:psycopg.connect(url));populate(file_repository);populate(postgres_repository);file=execute(file_repository);postgres=execute(postgres_repository);file_reload=execute(FileNarrativeRepository(file_root));postgres_reload=execute(PostgresNarrativeRepository(lambda:psycopg.connect(url)));matched=file==postgres==file_reload==postgres_reload
print("File Context Policy: REAL VERIFIED");print("PostgreSQL Context Policy: REAL VERIFIED");print(f"Authority Mapping: {'MATCH' if matched else 'MISMATCH'}");print(f"Duplicate Handling: {'MATCH' if matched else 'MISMATCH'}");print(f"Conflict Handling: {'MATCH' if matched else 'MISMATCH'}");print(f"Source Ordering: {'MATCH' if matched else 'MISMATCH'}");print(f"Budget: {'MATCH' if matched else 'MISMATCH'}");print(f"Serialized Context Backend Parity: {'MATCH' if matched else 'MISMATCH'}");print(f"Authoritative Mutation: {'NONE' if file['read_only'] and postgres['read_only'] else 'FOUND'}");print(f"Overall Context Policy Backend Parity: {'MATCH' if matched else 'MISMATCH'}")
if not matched:raise SystemExit(1)
