import json

TABLES={"threads":"narrative_threads","foreshadowing":"narrative_foreshadowing","events":"narrative_events","expectations":"narrative_expectations","findings":"narrative_findings","mysteries":"narrative_mysteries","character_goals":"narrative_character_goals","chapter_links":"narrative_chapter_links","proposals":"narrative_change_proposals"}
class PostgresNarrativeRepository:
 def __init__(self,connection_factory):self.connection_factory=connection_factory
 def _cas(self,c,revision):
  if not revision:return None
  branch_id,expected,enforce,scope=revision
  from ...collaboration import RevisionConflict
  if enforce and expected is None:raise ValueError("expected_revision is required")
  if expected is None:row=c.execute("UPDATE storyline_branches SET revision=revision+1 WHERE id=%s RETURNING revision",(branch_id,)).fetchone()
  else:row=c.execute("UPDATE storyline_branches SET revision=revision+1 WHERE id=%s AND revision=%s RETURNING revision",(branch_id,expected)).fetchone()
  if not row:
   current=c.execute("SELECT revision FROM storyline_branches WHERE id=%s",(branch_id,)).fetchone()
   if not current:raise KeyError(branch_id)
   raise RevisionConflict(scope,expected,current[0])
  return row[0]
 def create(self,project,kind,payload):
  table=TABLES[kind];cols="id,project_id,payload";vals=[payload["id"],project,json.dumps(payload)]
  if kind=="events":cols="id,project_id,subject_id,chapter_version_id,fingerprint,payload";vals=[payload["id"],project,payload["subject_id"],payload["chapter_version_id"],payload["fingerprint"],json.dumps(payload)]
  elif kind=="mysteries":cols="id,project_id,status,payload";vals=[payload["id"],project,payload["status"],json.dumps(payload)]
  elif kind=="character_goals":cols="id,project_id,character_id,status,payload";vals=[payload["id"],project,payload["character_id"],payload["status"],json.dumps(payload)]
  elif kind=="chapter_links":cols="id,project_id,chapter_id,chapter_version,entity_type,entity_id,progress_type,event_id,payload";vals=[payload["id"],project,payload["chapter_id"],payload["chapter_version"],payload["entity_type"],payload["entity_id"],payload["progress_type"],payload["event_id"],json.dumps(payload)]
  elif kind=="proposals":cols="id,project_id,proposal_type,status,subject_type,subject_id,chapter_version_id,fingerprint,summary,payload,evidence_ids,created_at,updated_at";vals=[payload["id"],project,payload["proposal_type"],payload["status"],payload["subject_type"],payload["subject_id"],payload["chapter_version_id"],payload["fingerprint"],payload["summary"],json.dumps(payload["payload"]),json.dumps(payload["evidence_ids"]),payload["created_at"],payload["updated_at"]]
  if payload.get("storyline_id") and payload.get("branch_id"):cols+=",storyline_id,branch_id";vals.extend([payload["storyline_id"],payload["branch_id"]])
  conflict="ON CONFLICT DO NOTHING" if kind=="proposals" else "ON CONFLICT(id) DO NOTHING"
  with self.connection_factory() as c:c.execute(f"INSERT INTO {table}({cols}) VALUES ({','.join(['%s']*len(vals))}) {conflict}",vals);c.commit()
  return self.get(project,kind,payload["id"])
 def transition(self,project,kind,item_id,status,event,revision=None):
  table=TABLES[kind]
  with self.connection_factory() as c:
   row=c.execute(f"SELECT payload FROM {table} WHERE project_id=%s AND id=%s FOR UPDATE",(project,item_id)).fetchone()
   if not row:raise KeyError(item_id)
   self._cas(c,revision)
   item=row[0];item["status"]=status
   if kind=="threads" and event["id"] not in item.setdefault("event_ids",[]):item["event_ids"].append(event["id"])
   if kind=="foreshadowing" and status=="PAYOFF":item["payoff_event_id"]=event["id"]
   fingerprint=event.get("fingerprint",event["id"])
   c.execute("INSERT INTO narrative_events(id,project_id,subject_id,chapter_version_id,fingerprint,payload,storyline_id,branch_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING",(event["id"],project,event["subject_id"],event["chapter_version_id"],fingerprint,json.dumps(event),event.get("storyline_id"),event.get("branch_id")))
   c.execute(f"UPDATE {table} SET payload=%s WHERE project_id=%s AND id=%s",(json.dumps(item),project,item_id));c.commit()
  return item
 def set_status(self,project,kind,item_id,status):
  table=TABLES[kind]
  with self.connection_factory() as c:
   row=c.execute(f"UPDATE {table} SET payload=jsonb_set(payload,'{{status}}',to_jsonb(%s::text)) WHERE project_id=%s AND id=%s RETURNING payload",(status,project,item_id)).fetchone();c.commit()
  if not row:raise KeyError(item_id)
  return row[0]
 def update(self,project,kind,item_id,payload,revision=None):
  table=TABLES[kind]
  with self.connection_factory() as c:
   self._cas(c,revision)
   if kind=="proposals":row=c.execute(f"UPDATE {table} SET status=%s,updated_at=%s WHERE project_id=%s AND id=%s RETURNING id,project_id,proposal_type,status,subject_type,subject_id,chapter_version_id,fingerprint,summary,payload,evidence_ids,created_at,updated_at",(payload["status"],payload["updated_at"],project,item_id)).fetchone();c.commit()
   else:row=c.execute(f"UPDATE {table} SET status=%s,payload=%s WHERE project_id=%s AND id=%s RETURNING payload",(payload["status"],json.dumps(payload),project,item_id)).fetchone();c.commit()
  if not row:raise KeyError(item_id)
  return self._proposal(row) if kind=="proposals" else row[0]
 def _proposal(self,row):
  keys=("id","project_id","proposal_type","status","subject_type","subject_id","chapter_version_id","fingerprint","summary","payload","evidence_ids","created_at","updated_at");out=dict(zip(keys,row));out["created_at"]=out["created_at"].isoformat() if hasattr(out["created_at"],"isoformat") else out["created_at"];out["updated_at"]=out["updated_at"].isoformat() if hasattr(out["updated_at"],"isoformat") else out["updated_at"];return out
 def get(self,project,kind,item_id):
  if kind=="proposals":
   with self.connection_factory() as c:r=c.execute("SELECT id,project_id,proposal_type,status,subject_type,subject_id,chapter_version_id,fingerprint,summary,payload,evidence_ids,created_at,updated_at FROM narrative_change_proposals WHERE project_id=%s AND id=%s",(project,item_id)).fetchone()
   if not r:raise KeyError(item_id)
   return self._proposal(r)
  with self.connection_factory() as c:r=c.execute(f"SELECT payload FROM {TABLES[kind]} WHERE project_id=%s AND id=%s",(project,item_id)).fetchone()
  if not r:raise KeyError(item_id)
  return r[0]
 def list(self,project,kind):
  if kind=="proposals":
   with self.connection_factory() as c:rows=c.execute("SELECT id,project_id,proposal_type,status,subject_type,subject_id,chapter_version_id,fingerprint,summary,payload,evidence_ids,created_at,updated_at FROM narrative_change_proposals WHERE project_id=%s ORDER BY id",(project,)).fetchall()
   return [self._proposal(x) for x in rows]
  order="created_at,id" if kind=="events" else "id"
  with self.connection_factory() as c:rows=c.execute(f"SELECT payload FROM {TABLES[kind]} WHERE project_id=%s ORDER BY {order}",(project,)).fetchall()
  return [r[0] for r in rows]
 def get_proposal_by_fingerprint(self,project,fingerprint):
  with self.connection_factory() as c:r=c.execute("SELECT id,project_id,proposal_type,status,subject_type,subject_id,chapter_version_id,fingerprint,summary,payload,evidence_ids,created_at,updated_at FROM narrative_change_proposals WHERE project_id=%s AND fingerprint=%s",(project,fingerprint)).fetchone()
  return self._proposal(r) if r else None
 def accept_proposal_atomic(self,project,proposal_id,kind,item_id,updated,event,link,accepted,revision=None):
  table=TABLES[kind]
  with self.connection_factory() as c:
   proposal=c.execute("SELECT status FROM narrative_change_proposals WHERE project_id=%s AND id=%s FOR UPDATE",(project,proposal_id)).fetchone();entity=c.execute(f"SELECT payload FROM {table} WHERE project_id=%s AND id=%s FOR UPDATE",(project,item_id)).fetchone()
   if not proposal or not entity:raise KeyError(proposal_id if not proposal else item_id)
   if proposal[0]!="PENDING":raise ValueError("proposal must be PENDING")
   self._cas(c,revision)
   if kind in {"mysteries","character_goals"}:c.execute(f"UPDATE {table} SET status=%s,payload=%s WHERE project_id=%s AND id=%s",(updated["status"],json.dumps(updated),project,item_id))
   else:c.execute(f"UPDATE {table} SET payload=%s WHERE project_id=%s AND id=%s",(json.dumps(updated),project,item_id))
   c.execute("INSERT INTO narrative_events(id,project_id,subject_id,chapter_version_id,fingerprint,payload,storyline_id,branch_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",(event["id"],project,event["subject_id"],event["chapter_version_id"],event["fingerprint"],json.dumps(event),event.get("storyline_id"),event.get("branch_id")));c.execute("INSERT INTO narrative_chapter_links(id,project_id,chapter_id,chapter_version,entity_type,entity_id,progress_type,event_id,payload,storyline_id,branch_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",(link["id"],project,link["chapter_id"],link["chapter_version"],link["entity_type"],link["entity_id"],link["progress_type"],link["event_id"],json.dumps(link),link.get("storyline_id"),link.get("branch_id")));c.execute("UPDATE narrative_change_proposals SET status='ACCEPTED',updated_at=%s WHERE project_id=%s AND id=%s",(accepted["updated_at"],project,proposal_id));c.commit()
  return self.get(project,"proposals",proposal_id)
 def record_progress(self,project,kind,item_id,updated,event,link,revision=None):
  table=TABLES[kind]
  with self.connection_factory() as c:
   existing=c.execute("SELECT payload FROM narrative_chapter_links WHERE project_id=%s AND id=%s",(project,link["id"])).fetchone()
   if existing:return existing[0]
   row=c.execute(f"SELECT payload FROM {table} WHERE project_id=%s AND id=%s FOR UPDATE",(project,item_id)).fetchone()
   if not row:raise KeyError(item_id)
   self._cas(c,revision)
   c.execute(f"UPDATE {table} SET status=%s,payload=%s WHERE project_id=%s AND id=%s",(updated["status"],json.dumps(updated),project,item_id)) if kind in {"mysteries","character_goals"} else c.execute(f"UPDATE {table} SET payload=%s WHERE project_id=%s AND id=%s",(json.dumps(updated),project,item_id))
   c.execute("INSERT INTO narrative_events(id,project_id,subject_id,chapter_version_id,fingerprint,payload,storyline_id,branch_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",(event["id"],project,event["subject_id"],event["chapter_version_id"],event["fingerprint"],json.dumps(event),event.get("storyline_id"),event.get("branch_id")))
   c.execute("INSERT INTO narrative_chapter_links(id,project_id,chapter_id,chapter_version,entity_type,entity_id,progress_type,event_id,payload,storyline_id,branch_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",(link["id"],project,link["chapter_id"],link["chapter_version"],link["entity_type"],link["entity_id"],link["progress_type"],link["event_id"],json.dumps(link),link.get("storyline_id"),link.get("branch_id")));c.commit()
  return link
