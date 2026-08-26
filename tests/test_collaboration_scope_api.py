from fastapi.testclient import TestClient
from app.dependencies import collaboration_scope_service
from app.main import app
from app.repositories.file.scope import FileScopeRepository
from app.collaboration import Workspace
import pytest

class Novels:
 def get(self,p):
  if p!="p":raise FileNotFoundError(p)
  return {"id":p}
@pytest.mark.file_backend_only
def test_scope_api_and_ownership(tmp_path):
 old=(collaboration_scope_service.repository,collaboration_scope_service.novels);collaboration_scope_service.repository=FileScopeRepository(tmp_path);collaboration_scope_service.novels=Novels();client=TestClient(app)
 try:
  legacy=client.post("/api/workspaces",json={"id":"w","name":"W"})
  assert legacy.status_code==410 and legacy.json()["detail"]["code"]=="LEGACY_WORKSPACE_MUTATION_DISABLED"
  collaboration_scope_service.create_workspace(Workspace("w","W"))
  assert client.post("/api/workspaces/w/projects/p/storylines",json={"id":"s","name":"S"}).status_code==201
  assert client.post("/api/workspaces/w/projects/p/storylines/s/branches",json={"id":"b","name":"B"}).status_code==201
  assert [x["id"] for x in client.get("/api/workspaces/w/projects/p/storylines").json()]==["s"]
  assert [x["id"] for x in client.get("/api/workspaces/w/projects/p/storylines/s/branches").json()]==["b"]
  assert client.get("/api/workspaces/other/projects/p/storylines").status_code==400
 finally:collaboration_scope_service.repository,collaboration_scope_service.novels=old
