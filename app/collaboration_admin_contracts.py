from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class WorkspaceAdminView(BaseModel):
    id: str
    name: str


class WorkspaceAdminList(BaseModel):
    items: list[WorkspaceAdminView]


class WorkspaceCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str


class WorkspaceRenameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str


class WorkspaceNavigationPath(BaseModel):
    workspace_id: str
    project_id: str
    storyline_id: str
    branch_id: str
    project_name: str
    storyline_name: str
    branch_name: str


class ProjectCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    genre: str = ""


class ProjectAdminView(BaseModel):
    id: str
    title: str
    genre: str = ""


class StorylineCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)


class StorylineAdminView(BaseModel):
    id: str
    workspace_id: str
    project_id: str
    name: str


class BranchCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)


class BranchAdminView(BaseModel):
    id: str
    workspace_id: str
    project_id: str
    storyline_id: str
    name: str
    revision: int = 0


class WorkspaceNavigationContext(BaseModel):
    workspace_id: str
    eligible_paths: list[WorkspaceNavigationPath] = Field(default_factory=list)
    default_path: WorkspaceNavigationPath | None = None


class MemberAdminView(BaseModel):
    user_id: str
    display_name: str
    membership_id: str
    status: str
    roles: list[dict[str, Any]] = Field(default_factory=list)
    permissions: list[dict[str, Any]] = Field(default_factory=list)


class MemberStatusRequest(BaseModel):
    status: str


class RoleGrantRequest(BaseModel):
    id: str
    principal_id: str
    role: str
    domain: str
    scope: dict[str, Any]


class PermissionGrantRequest(BaseModel):
    id: str
    principal_id: str
    permission: str
    domain: str
    scope: dict[str, Any]


class PermissionExplanationView(BaseModel):
    principal_id: str
    permission: str
    domain: str
    allowed: bool
    sources: list[dict[str, Any]]
