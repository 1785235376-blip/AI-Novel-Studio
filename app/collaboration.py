from dataclasses import dataclass,field
from datetime import datetime,timezone

DEFAULT_WORKSPACE_ID="default-workspace"
def default_storyline_id(project_id):return f"default-storyline:{project_id}"
def main_branch_id(project_id):return f"main:{default_storyline_id(project_id)}"
def utcnow():return datetime.now(timezone.utc).isoformat()

@dataclass(frozen=True)
class Workspace:id:str;name:str;created_at:str=field(default_factory=utcnow);updated_at:str=field(default_factory=utcnow)
@dataclass(frozen=True)
class Storyline:id:str;workspace_id:str;project_id:str;name:str;description:str="";created_at:str=field(default_factory=utcnow);updated_at:str=field(default_factory=utcnow)
@dataclass(frozen=True)
class Branch:id:str;workspace_id:str;project_id:str;storyline_id:str;name:str;parent_branch_id:str|None=None;created_at:str=field(default_factory=utcnow);updated_at:str=field(default_factory=utcnow);revision:int=0
@dataclass(frozen=True)
class CollaborationScope:workspace_id:str;project_id:str;storyline_id:str;branch_id:str
@dataclass(frozen=True)
class BranchRevision:
 workspace_id:str;project_id:str;storyline_id:str;branch_id:str;revision:int
 def __post_init__(self):
  if self.revision<0:raise ValueError("revision must be non-negative")
@dataclass(frozen=True)
class RevisionRef:id:str;scope:CollaborationScope;revision:int=0
@dataclass(frozen=True)
class ContextSnapshotRef:id:str;scope:CollaborationScope;revision:BranchRevision|RevisionRef|None=None

class RevisionConflict(RuntimeError):
 def __init__(self,scope,expected_revision,current_revision):
  super().__init__("STALE_REVISION");self.scope=scope;self.expected_revision=expected_revision;self.current_revision=current_revision
