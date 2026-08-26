from __future__ import annotations
from dataclasses import asdict
from uuid import uuid4
from ..authorization import *

ROLE_PERMISSIONS = {
    DomainRole.ADMIN: {"*"},
    DomainRole.DOMAIN_LEAD: {"domain.read", "domain.write", "domain.review", "proposal.create", "proposal.review"},
}

def serialize(item):
    value=asdict(item);value["scope"]["kind"]=item.scope.kind.value
    for key in ("role","domain"):
        if key in value:value[key]=getattr(item,key).value
    return value

def deserialize_scope(value):return AuthorizationScope(ScopeKind(value["kind"]),value["workspace_id"],value.get("project_id"),value.get("storyline_id"),value.get("branch_id"))

class AuthorizationService:
 def __init__(self,repository,scope_service):self.repository=repository;self.scope_service=scope_service
 def _validate_scope(self,scope):
  self.scope_service.get_workspace(scope.workspace_id)
  if scope.project_id is None:return scope
  if scope.storyline_id is None:
   if self.scope_service.repository.project_workspace(scope.project_id)!=scope.workspace_id:raise ValueError("project does not belong to workspace")
   return scope
  self.scope_service.validate_scope_parent(scope.workspace_id,scope.project_id,scope.storyline_id)
  if scope.branch_id is not None:self.scope_service.validate_scope(__import__("app.collaboration",fromlist=["CollaborationScope"]).CollaborationScope(scope.workspace_id,scope.project_id,scope.storyline_id,scope.branch_id))
  return scope
 def assign_role(self,item):
  self._validate_scope(item.scope)
  candidate=serialize(item)
  existing=next((x for x in self.repository.list_role_assignments(item.principal_id) if x["role"]==candidate["role"] and x["domain"]==candidate["domain"] and x["scope"]==candidate["scope"]),None)
  if existing:return existing
  audit=self._audit_event(item.created_by,"ROLE_ASSIGNED","DomainRoleAssignment",item.id,item.scope,{"principal_id":item.principal_id,"role":item.role.value,"domain":item.domain.value});return self.repository.save_role_assignment_with_audit(candidate,audit)
 def assign_permission(self,item):
  self._validate_scope(item.scope)
  candidate=serialize(item)
  existing=next((x for x in self.repository.list_permission_assignments(item.principal_id) if x["permission"]==candidate["permission"] and x["domain"]==candidate["domain"] and x["scope"]==candidate["scope"]),None)
  if existing:return existing
  audit=self._audit_event(item.created_by,"PERMISSION_ASSIGNED","PermissionAssignment",item.id,item.scope,{"principal_id":item.principal_id,"permission":item.permission,"domain":item.domain.value});return self.repository.save_permission_assignment_with_audit(candidate,audit)
 def is_allowed(self,principal_id,permission,domain,scope):
  self._validate_scope(scope)
  direct=any(x["domain"]==domain.value and x["permission"] in {permission,"*"} and deserialize_scope(x["scope"]).contains(scope) for x in self.repository.list_permission_assignments(principal_id))
  if direct:return True
  return any((DomainRole(x["role"]) is DomainRole.ADMIN or x["domain"]==domain.value) and (permission in ROLE_PERMISSIONS[DomainRole(x["role"])] or "*" in ROLE_PERMISSIONS[DomainRole(x["role"])]) and deserialize_scope(x["scope"]).contains(scope) for x in self.repository.list_role_assignments(principal_id))
 def require(self,principal_id,permission,domain,scope):
  if not self.is_allowed(principal_id,permission,domain,scope):raise PermissionError(f"{principal_id} lacks {permission}")
 def explain(self,principal_id,permission,domain,scope):
  """Return server-derived authorization evidence; callers must not infer access."""
  self._validate_scope(scope)
  sources=[]
  for item in self.repository.list_permission_assignments(principal_id):
   if item["domain"]==domain.value and item["permission"] in {permission,"*"} and deserialize_scope(item["scope"]).contains(scope):
    sources.append({"source_type":"DIRECT_PERMISSION","assignment_id":item["id"],"scope":item["scope"],"domain":item["domain"]})
  for item in self.repository.list_role_assignments(principal_id):
   role=DomainRole(item["role"])
   if (role is DomainRole.ADMIN or item["domain"]==domain.value) and (permission in ROLE_PERMISSIONS[role] or "*" in ROLE_PERMISSIONS[role]) and deserialize_scope(item["scope"]).contains(scope):
    sources.append({"source_type":"ADMIN_OVERRIDE" if role is DomainRole.ADMIN else "DOMAIN_ROLE","assignment_id":item["id"],"role":role.value,"scope":item["scope"],"domain":item["domain"]})
  return {"principal_id":principal_id,"permission":permission,"domain":domain.value,"allowed":bool(sources),"sources":sources}
 def revoke_role(self,assignment_id,actor_id):
  rows=[x for x in self.repository.list_role_assignments() if x["id"]==assignment_id]
  if not rows:raise KeyError(assignment_id)
  item=rows[0];scope=deserialize_scope(item["scope"]);self._validate_scope(scope)
  audit=self._audit_event(actor_id,"ROLE_REVOKED","DomainRoleAssignment",assignment_id,scope,{"principal_id":item["principal_id"],"role":item["role"],"domain":item["domain"]})
  return self.repository.revoke_role_assignment_with_audit(assignment_id,audit,protect_last_admin=item["role"]==DomainRole.ADMIN.value)
 def revoke_permission(self,assignment_id,actor_id):
  rows=[x for x in self.repository.list_permission_assignments() if x["id"]==assignment_id]
  if not rows:raise KeyError(assignment_id)
  item=rows[0];scope=deserialize_scope(item["scope"]);self._validate_scope(scope)
  audit=self._audit_event(actor_id,"PERMISSION_REVOKED","PermissionAssignment",assignment_id,scope,{"principal_id":item["principal_id"],"permission":item["permission"],"domain":item["domain"]})
  return self.repository.revoke_permission_assignment_with_audit(assignment_id,audit)
 def _audit_event(self,actor,action,target_type,target_id,scope,metadata):return serialize(AuditEvent(str(uuid4()),actor,action,target_type,target_id,scope,metadata=metadata))
