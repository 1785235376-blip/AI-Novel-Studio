import json
from datetime import datetime,timezone
from uuid import uuid4
from pathlib import Path
from threading import RLock
from ...storage import atomic_write
from .mutation_coordinator import workspace_mutation

_authorization_locks={}
_authorization_locks_guard=RLock()
def authorization_file_lock(path):
 with _authorization_locks_guard:return _authorization_locks.setdefault(str(Path(path).resolve()),RLock())

class FileScopeRepository:
 def __init__(self,root:Path):self.path=Path(root)/"collaboration_scope.json"
 def _read(self):
  if not self.path.exists():return {"workspaces":[],"project_workspaces":[],"storylines":[],"branches":[]}
  return json.loads(self.path.read_text(encoding="utf-8"))
 def _write(self,data):atomic_write(self.path,json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2))
 def create(self,kind,item):
  if kind=="branches":item={**item,"revision":int(item.get("revision",0))}
  data=self._read();old=next((x for x in data[kind] if x["id"]==item["id"]),None)
  if old:return old
  data[kind].append(item);data[kind].sort(key=lambda x:x["id"]);self._write(data);return item
 def get(self,kind,item_id):
  item=next((x for x in self._read()[kind] if x["id"]==item_id),None)
  if not item:raise KeyError(item_id)
  return item
 def list(self,kind,**filters):return [x for x in self._read()[kind] if all(x.get(k)==v for k,v in filters.items())]
 def link_project(self,project_id,workspace_id):
  data=self._read();old=next((x for x in data["project_workspaces"] if x["id"]==project_id),None)
  if old and old["workspace_id"]!=workspace_id:raise ValueError("project already belongs to another workspace")
  if not old:data["project_workspaces"].append({"id":project_id,"workspace_id":workspace_id});data["project_workspaces"].sort(key=lambda x:x["id"]);self._write(data)
  return {"id":project_id,"workspace_id":workspace_id}
 def project_workspace(self,project_id):
  return next((x["workspace_id"] for x in self._read()["project_workspaces"] if x["id"]==project_id),None)
 def compare_and_increment(self,scope,expected_revision,enforce=True):
  from ...collaboration import RevisionConflict
  data=self._read();branch=next((x for x in data["branches"] if x["id"]==scope.branch_id),None)
  if not branch:raise KeyError(scope.branch_id)
  current=int(branch.get("revision",0))
  if enforce and expected_revision is None:raise ValueError("expected_revision is required")
  if expected_revision is not None and expected_revision!=current:raise RevisionConflict(scope,expected_revision,current)
  branch["revision"]=current+1;self._write(data);return current+1
 def create_workspace(self,workspace_id,name,actor_id):
  from .identity import FileIdentityRepository
  now=datetime.now(timezone.utc).isoformat();root=self.path.parent
  paths=(self.path,root/"identity.json",root/"authorization.json")
  before={path:(path.read_bytes() if path.exists() else None) for path in paths}
  scope={"kind":"WORKSPACE","workspace_id":workspace_id,"project_id":None,"storyline_id":None,"branch_id":None}
  workspace={"id":workspace_id,"name":name,"created_at":now,"updated_at":now}
  membership={"id":f"membership:{workspace_id}:{actor_id}","user_id":actor_id,"workspace_id":workspace_id,"status":"ACTIVE","created_at":now,"updated_at":now,"metadata":None}
  role={"id":f"admin:{workspace_id}:{actor_id}","principal_id":actor_id,"role":"ADMIN","domain":"NOVEL","scope":scope,"created_by":actor_id,"created_at":now}
  audit={"id":str(uuid4()),"actor_id":actor_id,"action":"WORKSPACE_CREATED","target_type":"Workspace","target_id":workspace_id,"scope":scope,"timestamp":now,"metadata":{"name":name}}
  with workspace_mutation(root,workspace_id):
   try:
    if any(x["id"]==workspace_id for x in self._read()["workspaces"]):raise FileExistsError(workspace_id)
    self.create("workspaces",workspace)
    FileIdentityRepository(root).save_membership(membership)
    FileAuthorizationRepository(root).save_role_assignment_with_audit(role,audit)
    return workspace
   except Exception:
    for path,value in before.items():
     if value is None:path.unlink(missing_ok=True)
     else:atomic_write(path,value.decode("utf-8"))
    raise
 def provision_initial_workspace(self,actor_id,workspace_id,workspace_name,actor_display_name):
  from .identity import FileIdentityRepository
  root=self.path.parent;identity=FileIdentityRepository(root);authorization=FileAuthorizationRepository(root)
  paths=(self.path,identity.path,authorization.path)
  with workspace_mutation(root,f"initial-workspace:{actor_id}"):
   before={path:(path.read_bytes() if path.exists() else None) for path in paths}
   try:
    memberships=identity.list_memberships(user_id=actor_id)
    target=next((item for item in self._read()["workspaces"] if item["id"]==workspace_id),None)
    membership_id=f"membership:{workspace_id}:{actor_id}";role_id=f"admin:{workspace_id}:{actor_id}"
    role=next((item for item in authorization.list_role_assignments(actor_id) if item["id"]==role_id),None)
    if memberships:
     exact=len(memberships)==1 and memberships[0]["id"]==membership_id and memberships[0]["workspace_id"]==workspace_id and memberships[0]["status"]=="ACTIVE"
     expected_role=bool(role and role["principal_id"]==actor_id and role["role"]=="ADMIN" and role["domain"]=="NOVEL" and role["scope"]=={"kind":"WORKSPACE","workspace_id":workspace_id,"project_id":None,"storyline_id":None,"branch_id":None})
     if not exact or target is None or not expected_role:raise PermissionError("initial workspace state mismatch")
     return target
    if target is not None or role is not None:raise PermissionError("initial workspace target already exists")
    users=[item for item in identity.list_users() if item["id"]==actor_id]
    if users and users[0]["status"]!="ACTIVE":raise PermissionError("trusted local user is inactive")
    if not users:
     now=datetime.now(timezone.utc).isoformat()
     identity.save_user({"id":actor_id,"display_name":actor_display_name,"status":"ACTIVE","created_at":now,"updated_at":now,"metadata":None})
    result=self.create_workspace(workspace_id,workspace_name,actor_id)
    if len(identity.list_memberships(user_id=actor_id))!=1:raise PermissionError("initial workspace verification failed")
    return result
   except Exception:
    for path,value in before.items():
     if value is None:path.unlink(missing_ok=True)
     else:atomic_write(path,value.decode("utf-8"))
    raise
 def rename_workspace(self,workspace_id,name,actor_id):
  now=datetime.now(timezone.utc).isoformat();root=self.path.parent;auth_path=root/"authorization.json"
  before={path:(path.read_bytes() if path.exists() else None) for path in (self.path,auth_path)}
  scope={"kind":"WORKSPACE","workspace_id":workspace_id,"project_id":None,"storyline_id":None,"branch_id":None}
  audit={"id":str(uuid4()),"actor_id":actor_id,"action":"WORKSPACE_RENAMED","target_type":"Workspace","target_id":workspace_id,"scope":scope,"timestamp":now,"metadata":{"name":name}}
  with workspace_mutation(root,workspace_id):
   try:
    data=self._read();workspace=next((x for x in data["workspaces"] if x["id"]==workspace_id),None)
    if workspace is None:raise KeyError(workspace_id)
    workspace.update(name=name,updated_at=now);self._write(data)
    FileAuthorizationRepository(root).append_audit_event(audit)
    return workspace
   except Exception:
    for path,value in before.items():
     if value is None:path.unlink(missing_ok=True)
     else:atomic_write(path,value.decode("utf-8"))
    raise

class FileAuthorizationRepository:
 def __init__(self,root:Path):self.path=Path(root)/"authorization.json";self.lock=authorization_file_lock(self.path)
 def _read(self):
  if not self.path.exists():return {"role_assignments":[],"permission_assignments":[],"audit_events":[]}
  data=json.loads(self.path.read_text(encoding="utf-8"))
  return {key:list(data.get(key,[])) for key in ("role_assignments","permission_assignments","audit_events")}
 def _write(self,data):atomic_write(self.path,json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2))
 def _save(self,key,item):
  data=self._read();old=next((x for x in data[key] if x["id"]==item["id"]),None)
  if old:
   if old!=item:raise ValueError(f"assignment id already exists: {item['id']}")
   return old
  data[key].append(item);data[key].sort(key=lambda x:x["id"]);self._write(data);return item
 def save_role_assignment(self,item):
  with self.lock:return self._save("role_assignments",item)
 def save_permission_assignment(self,item):
  with self.lock:return self._save("permission_assignments",item)
 def _save_with_audit(self,key,item,audit):
  data=self._read();old=next((x for x in data[key] if x["id"]==item["id"]),None)
  if old and old!=item:raise ValueError(f"assignment id already exists: {item['id']}")
  if not old:data[key].append(item);data[key].sort(key=lambda x:x["id"])
  old_audit=next((x for x in data["audit_events"] if x["id"]==audit["id"]),None)
  if old_audit and old_audit!=audit:raise ValueError(f"assignment id already exists: {audit['id']}")
  if not old_audit:data["audit_events"].append(audit);data["audit_events"].sort(key=lambda x:x["id"])
  self._write(data);return item
 def save_role_assignment_with_audit(self,item,audit):
  with self.lock:return self._save_with_audit("role_assignments",item,audit)
 def save_permission_assignment_with_audit(self,item,audit):
  with self.lock:return self._save_with_audit("permission_assignments",item,audit)
 def list_role_assignments(self,principal_id=None):return [x for x in self._read()["role_assignments"] if principal_id is None or x["principal_id"]==principal_id]
 def list_permission_assignments(self,principal_id=None):return [x for x in self._read()["permission_assignments"] if principal_id is None or x["principal_id"]==principal_id]
 def _revoke_with_audit(self,key,assignment_id,audit,protect_last_admin=False):
  data=self._read();item=next((x for x in data[key] if x["id"]==assignment_id),None)
  if item is None:raise KeyError(assignment_id)
  workspace_id=item.get("scope",{}).get("workspace_id")
  if protect_last_admin and workspace_id:
   return self._revoke_with_workspace_lock(key, assignment_id, audit, workspace_id)
  with self.lock:return self._revoke_unlocked(self._read(),key,assignment_id,audit,protect_last_admin)

 def _revoke_with_workspace_lock(self,key,assignment_id,audit,workspace_id):
  with workspace_mutation(self.path.parent, workspace_id):
   with self.lock:return self._revoke_unlocked(self._read(),key,assignment_id,audit,True)

 def _revoke_unlocked(self,data,key,assignment_id,audit,protect_last_admin):
   item=next((x for x in data[key] if x["id"]==assignment_id),None)
   if item is None:raise KeyError(assignment_id)
   if protect_last_admin:
    workspace_id=item["scope"]["workspace_id"]
    admins=[x for x in data["role_assignments"] if x["role"]=="ADMIN" and x["scope"]["workspace_id"]==workspace_id]
    identity_path=self.path.with_name("identity.json")
    identity=json.loads(identity_path.read_text(encoding="utf-8")) if identity_path.exists() else {"memberships":[]}
    active={x["user_id"] for x in identity.get("memberships",[]) if x["workspace_id"]==workspace_id and x["status"]=="ACTIVE"}
    if len({x["principal_id"] for x in admins}&active)<=1:raise ValueError("LAST_ACTIVE_ADMIN")
   data[key]=[x for x in data[key] if x["id"]!=assignment_id]
   if not any(x["id"]==audit["id"] for x in data["audit_events"]):data["audit_events"].append(audit);data["audit_events"].sort(key=lambda x:x["id"])
   self._write(data);return item
 def revoke_role_assignment_with_audit(self,assignment_id,audit,protect_last_admin=False):return self._revoke_with_audit("role_assignments",assignment_id,audit,protect_last_admin)
 def revoke_permission_assignment_with_audit(self,assignment_id,audit):return self._revoke_with_audit("permission_assignments",assignment_id,audit)
 def append_audit_event(self,item):
  with self.lock:return self._save("audit_events",item)
 def list_audit_events(self,scope=None):
  values=self._read()["audit_events"]
  return values if scope is None else [x for x in values if x["scope"]==_scope_dict(scope)]

def _scope_dict(scope):
 from dataclasses import asdict
 value=asdict(scope);value["kind"]=scope.kind.value;return value
