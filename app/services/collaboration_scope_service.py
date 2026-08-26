from dataclasses import asdict
from ..collaboration import *

class CollaborationScopeService:
 def __init__(self,repository,novels):self.repository=repository;self.novels=novels
 def create_workspace(self,item):return self.repository.create("workspaces",asdict(item))
 def list_workspaces(self):return self.repository.list("workspaces")
 def get_workspace(self,item_id):return self.repository.get("workspaces",item_id)
 def navigation_paths(self,workspace_id):
  self.get_workspace(workspace_id)
  paths=[]
  for project in self.repository.list("project_workspaces",workspace_id=workspace_id):
   project_id=project["id"]
   for storyline in self.list_storylines(workspace_id,project_id):
    for branch in self.list_branches(workspace_id,project_id,storyline["id"]):
     try:project_name=self.novels.get(project_id).get("title") or "未命名小说"
     except (FileNotFoundError,KeyError):project_name="未命名小说"
     paths.append({"workspace_id":workspace_id,"project_id":project_id,"storyline_id":storyline["id"],"branch_id":branch["id"],"project_name":project_name,"storyline_name":storyline["name"],"branch_name":branch["name"]})
  return sorted(paths,key=lambda x:(x["project_id"],x["storyline_id"],x["branch_id"]))
 def ensure_default_workspace(self):return self.create_workspace(Workspace(DEFAULT_WORKSPACE_ID,"Default Workspace"))
 def link_project(self,workspace_id,project_id):self.get_workspace(workspace_id);self.novels.get(project_id);return self.repository.link_project(project_id,workspace_id)
 def create_storyline(self,item):
  if self.repository.project_workspace(item.project_id)!=item.workspace_id:raise ValueError("project does not belong to workspace")
  return self.repository.create("storylines",asdict(item))
 def list_storylines(self,workspace_id,project_id):
  if self.repository.project_workspace(project_id)!=workspace_id:raise ValueError("project does not belong to workspace")
  return self.repository.list("storylines",workspace_id=workspace_id,project_id=project_id)
 def create_branch(self,item):
  storyline=self.repository.get("storylines",item.storyline_id)
  if storyline["workspace_id"]!=item.workspace_id or storyline["project_id"]!=item.project_id:raise ValueError("storyline scope mismatch")
  if item.parent_branch_id:
   parent=self.repository.get("branches",item.parent_branch_id)
   if parent["storyline_id"]!=item.storyline_id:raise ValueError("parent branch scope mismatch")
  return self.repository.create("branches",asdict(item))
 def list_branches(self,workspace_id,project_id,storyline_id):
  self.validate_scope_parent(workspace_id,project_id,storyline_id)
  return self.repository.list("branches",workspace_id=workspace_id,project_id=project_id,storyline_id=storyline_id)
 def validate_scope_parent(self,workspace_id,project_id,storyline_id):
  if self.repository.project_workspace(project_id)!=workspace_id:raise ValueError("project does not belong to workspace")
  storyline=self.repository.get("storylines",storyline_id)
  if storyline["workspace_id"]!=workspace_id or storyline["project_id"]!=project_id:raise ValueError("storyline scope mismatch")
 def validate_scope(self,scope):
  self.get_workspace(scope.workspace_id);self.validate_scope_parent(scope.workspace_id,scope.project_id,scope.storyline_id);branch=self.repository.get("branches",scope.branch_id)
  if branch["workspace_id"]!=scope.workspace_id or branch["project_id"]!=scope.project_id or branch["storyline_id"]!=scope.storyline_id:raise ValueError("branch scope mismatch")
  return scope
 def ensure_default_scope(self,project_id):
  self.ensure_default_workspace();current=self.repository.project_workspace(project_id)
  if current is None:self.link_project(DEFAULT_WORKSPACE_ID,project_id)
  elif current!=DEFAULT_WORKSPACE_ID:raise ValueError("project belongs to a non-default workspace")
  sid=default_storyline_id(project_id);self.create_storyline(Storyline(sid,DEFAULT_WORKSPACE_ID,project_id,"Default Storyline"));bid=main_branch_id(project_id);self.create_branch(Branch(bid,DEFAULT_WORKSPACE_ID,project_id,sid,"main"));return CollaborationScope(DEFAULT_WORKSPACE_ID,project_id,sid,bid)
 def scoped_narrative(self,scope,narrative_repository):
  from ..repositories.scoped_narrative import ScopedNarrativeRepository
  self.validate_scope(scope);return ScopedNarrativeRepository(narrative_repository,scope,self.repository)
 def get_branch_revision(self,scope):
  self.validate_scope(scope);branch=self.repository.get("branches",scope.branch_id);return BranchRevision(scope.workspace_id,scope.project_id,scope.storyline_id,scope.branch_id,int(branch.get("revision",0)))
 def compare_and_increment(self,scope,expected_revision,enforce=True):
  self.validate_scope(scope);return self.repository.compare_and_increment(scope,expected_revision,enforce)
 def context_snapshot_ref(self,scope,snapshot_id):return ContextSnapshotRef(snapshot_id,scope,self.get_branch_revision(scope))
