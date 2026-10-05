"""Host-local declarative package management; no execute endpoint."""
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from .config import settings
from .plugin_package_manager import PluginPackageManager
from .dependencies import v1_capability_service

router=APIRouter()
_managers={}

class BundleIn(BaseModel):
    model_config=ConfigDict(extra="forbid")
    manifest:dict
    resources:dict[str,str]=Field(max_length=100)


def host(token):
    from .api import _agent_job_read_actor
    current=_agent_job_read_actor(token)
    if settings.enable_collaboration_runtime:
        raise HTTPException(403,{"code":"PLUGIN_HOST_ADMIN_REQUIRED","message":"Package mutations require a local host management session."})
    root=settings.data_path()/"plugins"
    return current,_managers.setdefault(str(root),PluginPackageManager(root))


def safe(fn,*args,**kwargs):
    from .api import capability_guard
    return capability_guard(fn,*args,**kwargs)


def register(manifest):
    record=v1_capability_service.register_plugin(manifest)
    # Identical bundles must not accidentally preserve earlier activation.
    v1_capability_service._update("plugins",record["id"],{"status":"REGISTERED","granted_permissions":[],"permission_review":None,"execution_supported":False},novel_id=None,expected_version=record["version"],action="PLUGIN_PACKAGE_REVIEW_REQUIRED",target_type="Plugin")


@router.post("/plugin-packages/install",status_code=201)
def install(body:BundleIn,update:bool=False,x_session_token:str|None=Header(default=None)):
    _,manager=host(x_session_token)
    return safe(manager.install,body.model_dump(),update=update,register=register)


@router.post("/plugin-packages/{plugin_id}/rollback")
def rollback(plugin_id:str,x_session_token:str|None=Header(default=None)):
    _,manager=host(x_session_token)
    return safe(manager.rollback,plugin_id,register=register)


@router.delete("/plugin-packages/{plugin_id}")
def remove(plugin_id:str,x_session_token:str|None=Header(default=None)):
    _,manager=host(x_session_token)
    # Revoke before moving files; a failure leaves the package safely disabled.
    safe(v1_capability_service.set_plugin_enabled,plugin_id,False)
    return safe(manager.remove,plugin_id)
