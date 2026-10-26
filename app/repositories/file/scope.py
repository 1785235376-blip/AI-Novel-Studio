import json
from datetime import datetime,timezone
from uuid import UUID, uuid4
from copy import deepcopy
from pathlib import Path
from threading import RLock
from functools import wraps
from contextlib import contextmanager
from ...storage import atomic_write
from .mutation_coordinator import workspace_mutation

_authorization_locks={}
_authorization_locks_guard=RLock()
def authorization_file_lock(path):
 with _authorization_locks_guard:return _authorization_locks.setdefault(str(Path(path).resolve()),RLock())

def scope_file_mutation(method):
 @wraps(method)
 def coordinated(self,*args,**kwargs):
  with workspace_mutation(self.path.parent,"collaboration-scope"):
   return method(self,*args,**kwargs)
 return coordinated

def authorization_file_mutation(method):
 @wraps(method)
 def coordinated(self,*args,**kwargs):
  with self.mutation():return method(self,*args,**kwargs)
 return coordinated

# Original-owner same-file evidence. No read or ordinary legacy write migrates it.
_SCOPE_LIFECYCLE = "_scope_lifecycle_v1"
_GRANT_LIFECYCLE = "_grant_lifecycle_v1"
_BINDING_UNSUPPORTED = "COLLABORATION_BINDING_UNSUPPORTED"
_SCOPE_FIELDS = {
 "workspaces": ("id",),
 "project_workspaces": ("id", "workspace_id"),
 "storylines": ("id", "workspace_id", "project_id"),
 "branches": ("id", "workspace_id", "project_id", "storyline_id", "parent_branch_id"),
}

def _canonical(value):
 return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)

def _nonce(value):
 try:return isinstance(value,str) and str(UUID(value))==value and UUID(value).version==4
 except (ValueError,TypeError,AttributeError):return False

def _rows(data,kind):
 rows=data.get(kind,[])
 if not isinstance(rows,list):raise ValueError(_BINDING_UNSUPPORTED)
 result={}
 for row in rows:
  if not isinstance(row,dict) or not isinstance(row.get("id"),str) or not row["id"] or row["id"] in result:
   raise ValueError(_BINDING_UNSUPPORTED)
  result[row["id"]]=row
 return result

def _validate_lifecycle(data,key,kinds):
 if key not in data:return
 meta=data[key]
 if (not isinstance(meta,dict) or set(meta)!={"schema_version","incarnation","rows"}
     or type(meta["schema_version"]) is not int or meta["schema_version"]!=1
     or not _nonce(meta["incarnation"]) or not isinstance(meta["rows"],dict)
     or set(meta["rows"])!=set(kinds)):
  raise ValueError(_BINDING_UNSUPPORTED)
 for kind in kinds:
  values=meta["rows"][kind]
  if not isinstance(values,dict) or set(values)!=set(_rows(data,kind)) or not all(_nonce(v) for v in values.values()):
   raise ValueError(_BINDING_UNSUPPORTED)

def _advance_lifecycle(data,before,key,kinds,fresh,project):
 # Presence, not get(), rejects null injection into absent or legacy files.
 if ((key in data)!=(key in before) or (key in before and _canonical(data[key])!=_canonical(before[key]))):
  raise ValueError("collaboration lifecycle metadata is owner-managed")
 if key not in before and not fresh:return deepcopy(data)
 meta=deepcopy(before[key]) if key in before else {"schema_version":1,"incarnation":str(uuid4()),"rows":{k:{} for k in kinds}}
 result=deepcopy(data)
 for kind in kinds:
  old,new=_rows(before,kind),_rows(data,kind)
  meta["rows"][kind]={rid:(meta["rows"][kind][rid] if rid in old and project(kind,old[rid])==project(kind,row) else str(uuid4())) for rid,row in new.items()}
 result[key]=meta
 _validate_lifecycle(result,key,kinds)
 return result

def _scope_projection(kind,row):
 return {key:row.get(key) for key in _SCOPE_FIELDS[kind]}

class FileScopeRepository:
 def __init__(self,root:Path):self.path=Path(root)/"collaboration_scope.json"
 def _read(self):
  if not self.path.exists():return {"workspaces":[],"project_workspaces":[],"storylines":[],"branches":[]}
  data=json.loads(self.path.read_text(encoding="utf-8"))
  _validate_lifecycle(data,_SCOPE_LIFECYCLE,_SCOPE_FIELDS)
  return data
 @scope_file_mutation
 def _write(self,data):
  fresh=not self.path.exists();before=self._read()
  updated=_advance_lifecycle(data,before,_SCOPE_LIFECYCLE,_SCOPE_FIELDS,fresh,_scope_projection)
  atomic_write(self.path,json.dumps(updated,ensure_ascii=False,sort_keys=True,indent=2))
 @scope_file_mutation
 def binding_observation(self,scope):
  data=self._read()
  if _SCOPE_LIFECYCLE not in data:raise ValueError(_BINDING_UNSUPPORTED)
  ids={"workspaces":scope.workspace_id,"project_workspaces":scope.project_id,"storylines":scope.storyline_id,"branches":scope.branch_id}
  selected={kind:_rows(data,kind).get(rid) for kind,rid in ids.items()}
  if (not all(selected.values()) or selected["project_workspaces"]["workspace_id"]!=scope.workspace_id
      or selected["storylines"].get("workspace_id")!=scope.workspace_id
      or selected["storylines"].get("project_id")!=scope.project_id
      or selected["branches"].get("workspace_id")!=scope.workspace_id
      or selected["branches"].get("project_id")!=scope.project_id
      or selected["branches"].get("storyline_id")!=scope.storyline_id):raise ValueError(_BINDING_UNSUPPORTED)
  meta=data[_SCOPE_LIFECYCLE]
  return {"incarnation":meta["incarnation"],"rows":{kind:{"id":rid,"lifecycle":meta["rows"][kind][rid]} for kind,rid in ids.items()}}
 def revalidate_binding(self,scope,observation):
  return self.binding_observation(scope)==observation
 @scope_file_mutation
 def create(self,kind,item):
  if kind=="branches":item={**item,"revision":int(item.get("revision",0))}
  data=self._read();old=next((x for x in data[kind] if x["id"]==item["id"]),None)
  if old:return old
  data[kind].append(item);data[kind].sort(key=lambda x:x["id"]);self._write(data);return item
 @scope_file_mutation
 def get(self,kind,item_id):
  item=next((x for x in self._read()[kind] if x["id"]==item_id),None)
  if not item:raise KeyError(item_id)
  return item
 @scope_file_mutation
 def list(self,kind,**filters):return [x for x in self._read()[kind] if all(x.get(k)==v for k,v in filters.items())]
 @scope_file_mutation
 def link_project(self,project_id,workspace_id):
  data=self._read();old=next((x for x in data["project_workspaces"] if x["id"]==project_id),None)
  if old and old["workspace_id"]!=workspace_id:raise ValueError("project already belongs to another workspace")
  if not old:data["project_workspaces"].append({"id":project_id,"workspace_id":workspace_id});data["project_workspaces"].sort(key=lambda x:x["id"]);self._write(data)
  return {"id":project_id,"workspace_id":workspace_id}
 @scope_file_mutation
 def project_workspace(self,project_id):
  return next((x["workspace_id"] for x in self._read()["project_workspaces"] if x["id"]==project_id),None)
 @contextmanager
 def project_authority_lease(self,project_id):
  from ...file_project_lifecycle import project_operation
  with project_operation(self.path.parent,project_id,require_exists=False):yield
 def retire_project(self,project_id,workspace_id=None):
  # Project IDs are globally unique. Retire every descendant, including a
  # malformed old cross-workspace scope, without touching workspace records.
  with workspace_mutation(self.path.parent,"collaboration-scope"):
   data=self._read()
   data["project_workspaces"]=[row for row in data["project_workspaces"] if row["id"]!=project_id]
   for kind in ("storylines","branches"):
    data[kind]=[row for row in data[kind] if row.get("project_id")!=project_id]
   self._write(data)
 @scope_file_mutation
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
  scope={"kind":"WORKSPACE","workspace_id":workspace_id,"project_id":None,"storyline_id":None,"branch_id":None}
  workspace={"id":workspace_id,"name":name,"created_at":now,"updated_at":now}
  membership={"id":f"membership:{workspace_id}:{actor_id}","user_id":actor_id,"workspace_id":workspace_id,"status":"ACTIVE","created_at":now,"updated_at":now,"metadata":None}
  role={"id":f"admin:{workspace_id}:{actor_id}","principal_id":actor_id,"role":"ADMIN","domain":"NOVEL","scope":scope,"created_by":actor_id,"created_at":now}
  audit={"id":str(uuid4()),"actor_id":actor_id,"action":"WORKSPACE_CREATED","target_type":"Workspace","target_id":workspace_id,"scope":scope,"timestamp":now,"metadata":{"name":name}}
  with FileAuthorizationRepository(root).mutation(), workspace_mutation(root,workspace_id), workspace_mutation(root,"collaboration-scope"):
   before={path:(path.read_bytes() if path.exists() else None) for path in paths}
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
  with authorization.mutation(), workspace_mutation(root,f"initial-workspace:{actor_id}"), workspace_mutation(root,workspace_id), workspace_mutation(root,"collaboration-scope"):
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
  scope={"kind":"WORKSPACE","workspace_id":workspace_id,"project_id":None,"storyline_id":None,"branch_id":None}
  audit={"id":str(uuid4()),"actor_id":actor_id,"action":"WORKSPACE_RENAMED","target_type":"Workspace","target_id":workspace_id,"scope":scope,"timestamp":now,"metadata":{"name":name}}
  with FileAuthorizationRepository(root).mutation(), workspace_mutation(root,workspace_id), workspace_mutation(root,"collaboration-scope"):
   before={path:(path.read_bytes() if path.exists() else None) for path in (self.path,auth_path)}
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
 @contextmanager
 def mutation(self):
  with self.lock,workspace_mutation(self.path.parent,"authorization-store"):yield
 def _read(self):
  if not self.path.exists():return {"role_assignments":[],"permission_assignments":[],"audit_events":[]}
  data=json.loads(self.path.read_text(encoding="utf-8"))
  result={key:list(data.get(key,[])) for key in ("role_assignments","permission_assignments","audit_events")}
  if _GRANT_LIFECYCLE in data:result[_GRANT_LIFECYCLE]=data[_GRANT_LIFECYCLE]
  _validate_lifecycle(result,_GRANT_LIFECYCLE,("role_assignments","permission_assignments"))
  return result
 @authorization_file_mutation
 def _write(self,data):
  fresh=not self.path.exists();before=self._read()
  updated=_advance_lifecycle(data,before,_GRANT_LIFECYCLE,("role_assignments","permission_assignments"),fresh,lambda kind,row:row)
  atomic_write(self.path,json.dumps(updated,ensure_ascii=False,sort_keys=True,indent=2))
 @authorization_file_mutation
 def binding_observation(self,service,principal_id,permission,domain,scope):
  # AuthorizationService remains the only policy evaluator, including ADMIN.
  from ...services.authorization_service import AuthorizationService
  if type(service) is not AuthorizationService or service.repository is not self:raise ValueError(_BINDING_UNSUPPORTED)
  explanation=service.explain(principal_id,permission,domain,scope)
  if not explanation["allowed"]:raise PermissionError("authorization binding is not allowed")
  data=self._read()
  if _GRANT_LIFECYCLE not in data:raise ValueError(_BINDING_UNSUPPORTED)
  meta=data[_GRANT_LIFECYCLE];selected=[]
  for source in explanation["sources"]:
   kind="permission_assignments" if source["source_type"]=="DIRECT_PERMISSION" else "role_assignments"
   rid=source["assignment_id"];row=_rows(data,kind).get(rid)
   if row is None or row.get("principal_id")!=principal_id:raise ValueError(_BINDING_UNSUPPORTED)
   selected.append({"kind":kind,"id":rid,"lifecycle":meta["rows"][kind][rid]})
  return {"incarnation":meta["incarnation"],"principal_id":principal_id,"permission":permission,"domain":domain.value,"scope":_scope_dict(scope),"rows":sorted(selected,key=lambda row:(row["kind"],row["id"]))}
 def revalidate_binding(self,service,principal_id,permission,domain,scope,observation):
  return self.binding_observation(service,principal_id,permission,domain,scope)==observation
 @authorization_file_mutation
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
 @authorization_file_mutation
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
 def retire_project(self,project_id,workspace_id=None):
  with self.mutation():
   data=self._read()
   for key in ("role_assignments","permission_assignments"):
    data[key]=[row for row in data[key] if row.get("scope",{}).get("project_id")!=project_id]
   self._write(data)
 def _revoke_with_audit(self,key,assignment_id,audit,protect_last_admin=False):
  data=self._read();item=next((x for x in data[key] if x["id"]==assignment_id),None)
  if item is None:raise KeyError(assignment_id)
  workspace_id=item.get("scope",{}).get("workspace_id")
  if protect_last_admin and workspace_id:
   return self._revoke_with_workspace_lock(key, assignment_id, audit, workspace_id)
  with self.mutation():return self._revoke_unlocked(self._read(),key,assignment_id,audit,protect_last_admin)

 def _revoke_with_workspace_lock(self,key,assignment_id,audit,workspace_id):
  with self.mutation(),workspace_mutation(self.path.parent, workspace_id):
   return self._revoke_unlocked(self._read(),key,assignment_id,audit,True)

 @authorization_file_mutation
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
