from ..collaboration import DEFAULT_WORKSPACE_ID,default_storyline_id,main_branch_id
from hashlib import sha256

class ScopedNarrativeRepository:
    """A validated branch-local view over the existing narrative repository contract."""
    def __init__(self,repository,scope,scope_repository=None,expected_revision=None,enforce=False):self.repository=repository;self.scope=scope;self.scope_repository=scope_repository;self.expected_revision=expected_revision;self.enforce=enforce
    def with_revision(self,expected_revision=None,enforce=False):return ScopedNarrativeRepository(self.repository,self.scope,self.scope_repository,expected_revision,enforce)
    def _revision(self):return (self.scope.branch_id,self.expected_revision,self.enforce,self.scope)
    def _file_bump(self):
        if self.scope_repository:self.scope_repository.compare_and_increment(self.scope,self.expected_revision,self.enforce)
    def _file_check(self):
        if not self.scope_repository:return
        from ..collaboration import RevisionConflict
        current=int(self.scope_repository.get("branches",self.scope.branch_id).get("revision",0))
        if self.enforce and self.expected_revision is None:raise ValueError("expected_revision is required")
        if self.expected_revision is not None and self.expected_revision!=current:raise RevisionConflict(self.scope,self.expected_revision,current)
    def _file_mutate(self,operation):
        self._file_check();before=self.repository._read(self.project_key)
        result=operation()
        try:self._file_bump()
        except Exception:
            self.repository._write(self.project_key,before);raise
        return self._out(result)
    @property
    def project_key(self):
        legacy=self.scope.workspace_id==DEFAULT_WORKSPACE_ID and self.scope.storyline_id==default_storyline_id(self.scope.project_id) and self.scope.branch_id==main_branch_id(self.scope.project_id)
        identity=f"{self.scope.workspace_id}|{self.scope.project_id}|{self.scope.storyline_id}|{self.scope.branch_id}"
        return self.scope.project_id if legacy else f"{self.scope.project_id}--scope-{sha256(identity.encode()).hexdigest()[:20]}"
    def _payload(self,payload):return {**payload,"project_id":self.scope.project_id,"workspace_id":self.scope.workspace_id,"storyline_id":self.scope.storyline_id,"branch_id":self.scope.branch_id}
    def _out(self,payload):return {**{k:v for k,v in payload.items() if k not in {"workspace_id","storyline_id","branch_id"}},"project_id":self.scope.project_id}
    def create(self,project,kind,payload):self._guard(project);return self._out(self.repository.create(self.project_key,kind,self._payload(payload)))
    def get(self,project,kind,item_id):self._guard(project);return self._out(self.repository.get(self.project_key,kind,item_id))
    def list(self,project,kind):self._guard(project);return [self._out(x) for x in self.repository.list(self.project_key,kind)]
    def update(self,project,kind,item_id,payload):
        self._guard(project)
        if kind=="proposals":return self._out(self.repository.update(self.project_key,kind,item_id,self._payload(payload)))
        if self.repository.__class__.__name__.startswith("Postgres"):return self._out(self.repository.update(self.project_key,kind,item_id,self._payload(payload),self._revision()))
        return self._file_mutate(lambda:self.repository.update(self.project_key,kind,item_id,self._payload(payload)))
    def set_status(self,project,kind,item_id,status):self._guard(project);return self.repository.set_status(self.project_key,kind,item_id,status)
    def transition(self,project,kind,item_id,status,event):
        self._guard(project)
        if self.repository.__class__.__name__.startswith("Postgres"):return self._out(self.repository.transition(self.project_key,kind,item_id,status,self._payload(event),self._revision()))
        return self._file_mutate(lambda:self.repository.transition(self.project_key,kind,item_id,status,self._payload(event)))
    def record_progress(self,project,kind,item_id,updated,event,link):
        self._guard(project)
        if self.repository.__class__.__name__.startswith("Postgres"):return self._out(self.repository.record_progress(self.project_key,kind,item_id,self._payload(updated),self._payload(event),self._payload(link),self._revision()))
        return self._file_mutate(lambda:self.repository.record_progress(self.project_key,kind,item_id,self._payload(updated),self._payload(event),self._payload(link)))
    def get_proposal_by_fingerprint(self,project,fingerprint):self._guard(project);return self.repository.get_proposal_by_fingerprint(self.project_key,fingerprint)
    def accept_proposal_atomic(self,project,proposal_id,kind,item_id,updated,event,link,accepted):
        self._guard(project)
        if self.repository.__class__.__name__.startswith("Postgres"):return self._out(self.repository.accept_proposal_atomic(self.project_key,proposal_id,kind,item_id,self._payload(updated),self._payload(event),self._payload(link),self._payload(accepted),self._revision()))
        return self._file_mutate(lambda:self.repository.accept_proposal_atomic(self.project_key,proposal_id,kind,item_id,self._payload(updated),self._payload(event),self._payload(link),self._payload(accepted)))
    def _guard(self,project):
        if project!=self.scope.project_id:raise ValueError("project is outside collaboration scope")
