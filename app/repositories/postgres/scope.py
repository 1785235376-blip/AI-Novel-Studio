import json
from datetime import datetime,timezone
from uuid import uuid4

TABLES={"workspaces":"workspaces","storylines":"storylines","branches":"storyline_branches"}
class PostgresScopeRepository:
 def __init__(self,connection_factory):self.connection_factory=connection_factory
 def create(self,kind,item):
  table=TABLES[kind]
  if kind=="branches":item={**item,"revision":int(item.get("revision",0))}
  columns="id,payload,revision" if kind=="branches" else "id,payload";values=(item["id"],json.dumps(item),item["revision"]) if kind=="branches" else (item["id"],json.dumps(item))
  with self.connection_factory() as c:c.execute(f"INSERT INTO {table}({columns}) VALUES ({','.join(['%s']*len(values))}) ON CONFLICT(id) DO NOTHING",values);c.commit()
  return self.get(kind,item["id"])
 def get(self,kind,item_id):
  select="payload,revision" if kind=="branches" else "payload"
  with self.connection_factory() as c:row=c.execute(f"SELECT {select} FROM {TABLES[kind]} WHERE id=%s",(item_id,)).fetchone()
  if not row:raise KeyError(item_id)
  return {**row[0],"revision":row[1]} if kind=="branches" else row[0]
 def list(self,kind,**filters):
  if kind=="project_workspaces":
   with self.connection_factory() as c:rows=c.execute("SELECT project_id,workspace_id FROM project_workspaces ORDER BY project_id").fetchall()
   values=[{"id":row[0],"workspace_id":row[1]} for row in rows];return [x for x in values if all(x.get(k)==v for k,v in filters.items())]
  select="payload,revision" if kind=="branches" else "payload"
  with self.connection_factory() as c:rows=c.execute(f"SELECT {select} FROM {TABLES[kind]} ORDER BY id").fetchall()
  values=[{**x[0],"revision":x[1]} if kind=="branches" else x[0] for x in rows];return [x for x in values if all(x.get(k)==v for k,v in filters.items())]
 def link_project(self,project_id,workspace_id):
  with self.connection_factory() as c:
   row=c.execute("SELECT workspace_id FROM project_workspaces WHERE project_id=%s",(project_id,)).fetchone()
   if row and row[0]!=workspace_id:raise ValueError("project already belongs to another workspace")
   c.execute("INSERT INTO project_workspaces(project_id,workspace_id) VALUES (%s,%s) ON CONFLICT(project_id) DO NOTHING",(project_id,workspace_id));c.execute("UPDATE novels SET workspace_id=%s WHERE slug=%s",(workspace_id,project_id));c.commit()
  return {"id":project_id,"workspace_id":workspace_id}
 def project_workspace(self,project_id):
  with self.connection_factory() as c:row=c.execute("SELECT workspace_id FROM project_workspaces WHERE project_id=%s",(project_id,)).fetchone()
  return row[0] if row else None
 def compare_and_increment(self,scope,expected_revision,enforce=True):
  from ...collaboration import RevisionConflict
  with self.connection_factory() as c:
   if enforce and expected_revision is None:raise ValueError("expected_revision is required")
   if expected_revision is None:row=c.execute("UPDATE storyline_branches SET revision=revision+1 WHERE id=%s RETURNING revision",(scope.branch_id,)).fetchone()
   else:row=c.execute("UPDATE storyline_branches SET revision=revision+1 WHERE id=%s AND revision=%s RETURNING revision",(scope.branch_id,expected_revision)).fetchone()
   if not row:
    current=c.execute("SELECT revision FROM storyline_branches WHERE id=%s",(scope.branch_id,)).fetchone()
    if not current:raise KeyError(scope.branch_id)
    raise RevisionConflict(scope,expected_revision,current[0])
   c.commit();return row[0]
 def create_workspace(self,workspace_id,name,actor_id):
  now=datetime.now(timezone.utc);stamp=now.isoformat()
  scope={"kind":"WORKSPACE","workspace_id":workspace_id,"project_id":None,"storyline_id":None,"branch_id":None}
  workspace={"id":workspace_id,"name":name,"created_at":stamp,"updated_at":stamp}
  role={"id":f"admin:{workspace_id}:{actor_id}","principal_id":actor_id,"role":"ADMIN","domain":"NOVEL","scope":scope,"created_by":actor_id,"created_at":stamp}
  audit={"id":str(uuid4()),"actor_id":actor_id,"action":"WORKSPACE_CREATED","target_type":"Workspace","target_id":workspace_id,"scope":scope,"timestamp":stamp,"metadata":{"name":name}}
  with self.connection_factory() as c:
   try:
    c.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",(f"authorization:{workspace_id}",)).fetchone()
    row=c.execute("INSERT INTO workspaces(id,payload) VALUES (%s,%s::jsonb) ON CONFLICT DO NOTHING RETURNING payload",(workspace_id,json.dumps(workspace))).fetchone()
    if not row:raise FileExistsError(workspace_id)
    c.execute("INSERT INTO workspace_memberships(id,user_id,workspace_id,status,created_at,updated_at,metadata) VALUES (%s,%s,%s,'ACTIVE',%s,%s,NULL)",(f"membership:{workspace_id}:{actor_id}",actor_id,workspace_id,now,now))
    c.execute("INSERT INTO domain_role_assignments(id,payload) VALUES (%s,%s::jsonb)",(role["id"],json.dumps(role)))
    c.execute("INSERT INTO authorization_audit_events(id,payload) VALUES (%s,%s::jsonb)",(audit["id"],json.dumps(audit)))
    c.commit();return row[0]
   except Exception:
    c.rollback();raise
 def provision_initial_workspace(self,actor_id,workspace_id,workspace_name,actor_display_name):
  now=datetime.now(timezone.utc);stamp=now.isoformat()
  scope={"kind":"WORKSPACE","workspace_id":workspace_id,"project_id":None,"storyline_id":None,"branch_id":None}
  workspace={"id":workspace_id,"name":workspace_name,"created_at":stamp,"updated_at":stamp}
  membership_id=f"membership:{workspace_id}:{actor_id}";role_id=f"admin:{workspace_id}:{actor_id}"
  role={"id":role_id,"principal_id":actor_id,"role":"ADMIN","domain":"NOVEL","scope":scope,"created_by":actor_id,"created_at":stamp}
  audit={"id":str(uuid4()),"actor_id":actor_id,"action":"WORKSPACE_CREATED","target_type":"Workspace","target_id":workspace_id,"scope":scope,"timestamp":stamp,"metadata":{"name":workspace_name,"source":"PACKAGED_INITIAL_PROVISIONING"}}
  with self.connection_factory() as c:
   try:
    c.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",(f"initial-workspace:{actor_id}",)).fetchone()
    memberships=c.execute("SELECT id,user_id,workspace_id,status FROM workspace_memberships WHERE user_id=%s FOR UPDATE",(actor_id,)).fetchall()
    target=c.execute("SELECT payload FROM workspaces WHERE id=%s FOR UPDATE",(workspace_id,)).fetchone()
    admin=c.execute("SELECT payload FROM domain_role_assignments WHERE id=%s FOR UPDATE",(role_id,)).fetchone()
    if memberships:
     exact=len(memberships)==1 and memberships[0]==(membership_id,actor_id,workspace_id,"ACTIVE")
     expected_admin=bool(admin and admin[0].get("principal_id")==actor_id and admin[0].get("role")=="ADMIN" and admin[0].get("domain")=="NOVEL" and admin[0].get("scope")==scope)
     if not exact or not target or not expected_admin:raise PermissionError("initial workspace state mismatch")
     c.commit();return target[0]
    if target or admin:raise PermissionError("initial workspace target already exists")
    user=c.execute("SELECT id,status FROM users WHERE id=%s FOR UPDATE",(actor_id,)).fetchone()
    if user and user!=(actor_id,"ACTIVE"):raise PermissionError("trusted local user is inactive")
    if not user:c.execute("INSERT INTO users(id,display_name,status,created_at,updated_at,metadata) VALUES (%s,%s,'ACTIVE',%s,%s,NULL)",(actor_id,actor_display_name,now,now))
    c.execute("INSERT INTO workspaces(id,payload) VALUES (%s,%s::jsonb)",(workspace_id,json.dumps(workspace)))
    c.execute("INSERT INTO workspace_memberships(id,user_id,workspace_id,status,created_at,updated_at,metadata) VALUES (%s,%s,%s,'ACTIVE',%s,%s,NULL)",(membership_id,actor_id,workspace_id,now,now))
    c.execute("INSERT INTO domain_role_assignments(id,payload) VALUES (%s,%s::jsonb)",(role_id,json.dumps(role)))
    c.execute("INSERT INTO authorization_audit_events(id,payload) VALUES (%s,%s::jsonb)",(audit["id"],json.dumps(audit)))
    verify=c.execute("SELECT COUNT(*) FROM workspace_memberships WHERE user_id=%s",(actor_id,)).fetchone()[0]
    if verify!=1:raise PermissionError("initial workspace verification failed")
    c.commit();return workspace
   except Exception:
    c.rollback();raise
 def rename_workspace(self,workspace_id,name,actor_id):
  now=datetime.now(timezone.utc).isoformat();scope={"kind":"WORKSPACE","workspace_id":workspace_id,"project_id":None,"storyline_id":None,"branch_id":None}
  audit={"id":str(uuid4()),"actor_id":actor_id,"action":"WORKSPACE_RENAMED","target_type":"Workspace","target_id":workspace_id,"scope":scope,"timestamp":now,"metadata":{"name":name}}
  with self.connection_factory() as c:
   try:
    c.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",(f"authorization:{workspace_id}",)).fetchone()
    row=c.execute("SELECT payload FROM workspaces WHERE id=%s FOR UPDATE",(workspace_id,)).fetchone()
    if not row:raise KeyError(workspace_id)
    workspace={**row[0],"name":name,"updated_at":now}
    c.execute("UPDATE workspaces SET payload=%s::jsonb WHERE id=%s",(json.dumps(workspace),workspace_id))
    c.execute("INSERT INTO authorization_audit_events(id,payload) VALUES (%s,%s::jsonb)",(audit["id"],json.dumps(audit)))
    c.commit();return workspace
   except Exception:
    c.rollback();raise

class PostgresAuthorizationRepository:
 def __init__(self,connection_factory):self.connection_factory=connection_factory
 @staticmethod
 def _lock_workspace(c,workspace_id):
  c.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",(f"authorization:{workspace_id}",)).fetchone()
 def _save(self,table,item):
  with self.connection_factory() as c:
   row=c.execute(f"INSERT INTO {table}(id,payload) VALUES (%s,%s::jsonb) ON CONFLICT(id) DO UPDATE SET id=EXCLUDED.id WHERE {table}.payload=EXCLUDED.payload RETURNING payload",(item["id"],json.dumps(item))).fetchone()
   if not row:raise ValueError(f"assignment id already exists: {item['id']}")
   c.commit();return row[0]
 def save_role_assignment(self,item):return self._save("domain_role_assignments",item)
 def save_permission_assignment(self,item):return self._save("permission_assignments",item)
 def _save_with_audit(self,table,item,audit):
  with self.connection_factory() as c:
   workspace_id=item["scope"]["workspace_id"]
   self._lock_workspace(c,workspace_id)
   semantic_field="role" if table=="domain_role_assignments" else "permission"
   duplicate=c.execute(f"SELECT id FROM {table} WHERE id<>%s AND payload->>'principal_id'=%s AND payload->>%s=%s AND payload->>'domain'=%s AND payload->'scope'=%s::jsonb",(item["id"],item["principal_id"],semantic_field,item[semantic_field],item["domain"],json.dumps(item["scope"]))).fetchone()
   if duplicate:raise ValueError("duplicate semantic assignment")
   row=c.execute(f"INSERT INTO {table}(id,payload) VALUES (%s,%s::jsonb) ON CONFLICT(id) DO UPDATE SET id=EXCLUDED.id WHERE {table}.payload=EXCLUDED.payload RETURNING payload",(item["id"],json.dumps(item))).fetchone()
   if not row:raise ValueError(f"assignment id already exists: {item['id']}")
   audit_row=c.execute("INSERT INTO authorization_audit_events(id,payload) VALUES (%s,%s::jsonb) ON CONFLICT(id) DO UPDATE SET id=EXCLUDED.id WHERE authorization_audit_events.payload=EXCLUDED.payload RETURNING payload",(audit["id"],json.dumps(audit))).fetchone()
   if not audit_row:raise ValueError(f"audit id already exists: {audit['id']}")
   c.commit();return row[0]
 def save_role_assignment_with_audit(self,item,audit):return self._save_with_audit("domain_role_assignments",item,audit)
 def save_permission_assignment_with_audit(self,item,audit):return self._save_with_audit("permission_assignments",item,audit)
 def _list(self,table,principal_id=None):
  query=f"SELECT payload FROM {table}";params=()
  if principal_id is not None:query+=" WHERE payload->>'principal_id'=%s";params=(principal_id,)
  query+=" ORDER BY id"
  with self.connection_factory() as c:return [x[0] for x in c.execute(query,params).fetchall()]
 def list_role_assignments(self,principal_id=None):return self._list("domain_role_assignments",principal_id)
 def list_permission_assignments(self,principal_id=None):return self._list("permission_assignments",principal_id)
 def _revoke_with_audit(self,table,assignment_id,audit,protect_last_admin=False):
  with self.connection_factory() as c:
   workspace_id=audit["scope"]["workspace_id"]
   self._lock_workspace(c,workspace_id)
   row=c.execute(f"SELECT payload FROM {table} WHERE id=%s FOR UPDATE",(assignment_id,)).fetchone()
   if not row:raise KeyError(assignment_id)
   item=row[0]
   if protect_last_admin:
    # Serialize ADMIN mutations in this workspace, then count distinct active admins.
    c.execute("SELECT id FROM domain_role_assignments WHERE payload->>'role'='ADMIN' AND payload->'scope'->>'workspace_id'=%s FOR UPDATE",(workspace_id,)).fetchall()
    count=c.execute("SELECT COUNT(DISTINCT r.payload->>'principal_id') FROM domain_role_assignments r JOIN workspace_memberships m ON m.user_id=r.payload->>'principal_id' AND m.workspace_id=%s AND m.status='ACTIVE' WHERE r.payload->>'role'='ADMIN' AND r.payload->'scope'->>'workspace_id'=%s",(workspace_id,workspace_id)).fetchone()[0]
    if count<=1:raise ValueError("LAST_ACTIVE_ADMIN")
   c.execute(f"DELETE FROM {table} WHERE id=%s",(assignment_id,))
   c.execute("INSERT INTO authorization_audit_events(id,payload) VALUES (%s,%s::jsonb)",(audit["id"],json.dumps(audit)))
   c.commit();return item
 def revoke_role_assignment_with_audit(self,assignment_id,audit,protect_last_admin=False):return self._revoke_with_audit("domain_role_assignments",assignment_id,audit,protect_last_admin)
 def revoke_permission_assignment_with_audit(self,assignment_id,audit):return self._revoke_with_audit("permission_assignments",assignment_id,audit)
 def append_audit_event(self,item):return self._save("authorization_audit_events",item)
 def list_audit_events(self,scope=None):
  values=self._list("authorization_audit_events")
  if scope is None:return values
  from dataclasses import asdict
  expected=asdict(scope);expected["kind"]=scope.kind.value
  return [x for x in values if x["scope"]==expected]
