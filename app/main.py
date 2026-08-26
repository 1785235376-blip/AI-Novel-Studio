from __future__ import annotations
from fastapi import FastAPI, HTTPException, Request
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from . import __version__
from .config import settings
from .dependencies import context_service,collaboration_read_service,collaboration_admin_service,packaged_bootstrap_registry,packaged_initial_workspace_provisioner,trusted_session_resolver,harness_process_service
from .collaboration_api import create_collaboration_router
from .collaboration_admin import create_collaboration_admin_router
from .packaging.bootstrap_api import create_packaged_bootstrap_router
from .packaging.local_session_bootstrap import BootstrapDenied
from .packaging.static_frontend import mount_packaged_frontend
from .packaging.control_pipe import start_packaged_control_reader
from pathlib import Path
import os
import re
import uuid
import ipaddress

from .api import router as api_router
@asynccontextmanager
async def app_lifespan(_app):
    yield
    harness_process_service.stop()

app=FastAPI(title="AI Novel Studio",version=__version__,lifespan=app_lifespan)
_packaged_control_reader = start_packaged_control_reader()

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

@app.exception_handler(HTTPException)
async def unified_http_error(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict):
        code = str(detail.get("code") or f"HTTP_{exc.status_code}")
        message = str(detail.get("message") or detail.get("detail") or code)
        details = detail.get("details", detail)
    else:
        code = f"HTTP_{exc.status_code}"
        message = str(detail)
        details = {}
    request_id = getattr(request.state, "request_id", "")
    return JSONResponse(status_code=exc.status_code, content={"detail": detail, "code": code, "message": message, "details": details, "request_id": request_id}, headers={"X-Request-ID": request_id})

def _normalized_api_path(path: str) -> str:
    """Use the legacy path shape for middleware checks on the v1 alias."""
    return "/api" + path[len("/api/v1"):] if path.startswith("/api/v1/") else path

@app.middleware("http")
async def collaboration_fail_closed(request,call_next):
    packaged = bool(getattr(settings, "enable_packaged_runtime", False))
    collaboration = bool(getattr(settings, "enable_collaboration_runtime", False))
    if not packaged and not collaboration:
        remote_host=request.client.host if request.client else ''
        try: local_client=ipaddress.ip_address(remote_host).is_loopback
        except ValueError: local_client=remote_host=='testclient'
        if not local_client:
            return JSONResponse({"detail":{"code":"LOCAL_RUNTIME_LOOPBACK_REQUIRED"}},status_code=403)
    if packaged:
        path = request.url.path
        normalized_path = _normalized_api_path(path)
        method = request.method

        # The launcher performs this one POST before the WebView has a session.
        if normalized_path == "/api/packaged/bootstrap" and method == "POST":
            return await call_next(request)

        # Keep the packaged control namespace fail-closed for unsupported
        # methods and unknown endpoints; the browser-facing application API
        # below is handled by the session gate.
        if normalized_path.startswith("/api/packaged/") and normalized_path not in {
            "/api/packaged/bootstrap",
            "/api/packaged/initial-workspace",
        }:
            return JSONResponse({"detail": {"code": "COLLABORATION_ROUTE_NOT_ENABLED"}}, status_code=501)
        if normalized_path == "/api/packaged/bootstrap" and method != "POST":
            return JSONResponse({"detail": {"code": "COLLABORATION_ROUTE_NOT_ENABLED"}}, status_code=501)

        # A packaged process without the trusted collaboration boundary is a
        # misconfiguration. Keep the historical fail-closed response instead
        # of accidentally turning it into a development runtime.
        if not collaboration:
            return JSONResponse({"detail": {"code": "COLLABORATION_ROUTE_NOT_ENABLED"}}, status_code=501)

        # The local UI shell and health probes must be reachable before the
        # host has injected the opaque session header. All other routes,
        # including legacy top-level routes, are protected by the same gate.
        public = (
            (normalized_path in {"/health", "/api/health"} and method in {"GET", "HEAD"})
            or (method in {"GET", "HEAD"} and (path in {"/", "/index.html"} or path.startswith("/assets/")))
        )
        if not public:
            token = request.headers.get("X-Session-Token")
            if not token:
                return JSONResponse({"detail": {"code": "SESSION_REQUIRED"}}, status_code=401)
            manager = packaged_bootstrap_registry.current()
            try:
                # In packaged mode only the current launcher bootstrap may
                # mint sessions. This prevents development-session fallback.
                if manager is None:
                    raise BootstrapDenied("PACKAGED_SESSION_REQUIRED", "本地安全会话无效或已过期。")
                manager.resolve_issued_session(token)
            except (BootstrapDenied, KeyError, ValueError):
                return JSONResponse({"detail": {"code": "INVALID_SESSION"}}, status_code=401)
        return await call_next(request)

    if collaboration:
        path=request.url.path; normalized_path=_normalized_api_path(path); method=request.method
        # V1 metadata capabilities are available to the collaboration runtime
        # only after resolving an opaque trusted session.  This keeps the
        # expanded allowlist from turning research/plugin/workflow records into
        # anonymous development endpoints.  Packaged mode has already applied
        # its stronger bootstrap-issued session gate above.
        capability_route = any(re.fullmatch(pattern, normalized_path) is not None for pattern in (
            r"/api/novels/[^/]+/overview",
            r"/api/novels/[^/]+/research(?:/[^/]+)?",
            r"/api/research",
            r"/api/novels/[^/]+/character-evolution(?:/[^/]+)?",
            r"/api/novels/[^/]+/characters/[^/]+/evolution",
            r"/api/novels/[^/]+/visual-memory(?:/[^/]+)?",
            r"/api/memory",
            r"/api/assets/[^/]+/derivatives",
            r"/api/novels/[^/]+/lore/(?:evidence|proposals(?:/[^/]+/(?:approve|reject|approve-memory))?)",
            r"/api/novels/[^/]+/(?:memories(?:/[^/]+/retract)?|characters/[^/]+/memories|memory-snapshots)",
            r"/api/plugins(?:/[^/]+(?:/(?:permissions|enable|disable))?)?",
            r"/api/workflows(?:/[^/]+(?:/runs)?)?",
            r"/api/workflow-runs/[^/]+(?:/(?:pause|resume|cancel|retry)|/nodes/[^/]+/approve)?",
            r"/api/release-gates(?:/[^/]+)?",
            r"/api/audit",
        ))
        if capability_route:
            token = request.headers.get("X-Session-Token")
            if not token:
                return JSONResponse({"detail": {"code": "SESSION_REQUIRED"}}, status_code=401)
            try:
                trusted_session_resolver.resolve(token)
            except (KeyError, ValueError):
                return JSONResponse({"detail": {"code": "INVALID_SESSION"}}, status_code=401)
        if normalized_path.startswith("/api/collaboration/admin/") and method not in {"GET","HEAD"}:
            token = request.headers.get("X-Session-Token")
            if not token:
                return JSONResponse({"detail": {"code": "SESSION_REQUIRED"}}, status_code=401)
            try:
                trusted_session_resolver.resolve(token)
            except (KeyError, ValueError):
                return JSONResponse({"detail": {"code": "INVALID_SESSION"}}, status_code=401)
        allowed=(normalized_path=="/health" and method=="GET") or (normalized_path.startswith("/api/") and (
            (method=="GET" and normalized_path in {"/api/health","/api/providers","/api/models","/api/text-models"}) or
            (normalized_path.startswith("/api/collaboration/admin/") and method in {"GET","POST","PATCH","DELETE"}) or
            (method=="GET" and normalized_path.startswith("/api/collaboration/")) or
            (method=="GET" and re.fullmatch(r"/api/novels/[^/]+/chapters/archived",normalized_path) is not None) or
            (method=="POST" and re.fullmatch(r"/api/collaboration/workspaces/[^/]+/projects/[^/]+/storylines/[^/]+/branches/[^/]+/chapters",normalized_path) is not None) or
            re.fullmatch(r"/api/chapters/[^/]+(?:/history)?",normalized_path) is not None and method=="GET" or
            re.fullmatch(r"/api/chapters/[^/]+",normalized_path) is not None and method=="PUT" or
            re.fullmatch(r"/api/chapters/[^/]+/(?:rename|archive|restore-archive|history/\d+/restore)",normalized_path) is not None and method=="POST" or
            re.fullmatch(r"/api/generate/[^/]+",normalized_path) is not None and method=="POST" or
            normalized_path=="/api/agent/chat" and method=="POST" or
            normalized_path in {"/api/user-preferences","/api/user-preferences-enabled","/api/user-preferences-share-enabled","/api/harness-enabled"} and method in {"GET","PUT"} or
            normalized_path=="/api/harness/status" and method=="GET" or
            normalized_path=="/api/harness/launch-readiness" and method=="GET" or
            normalized_path in {"/api/harness/process","/api/harness/process/start","/api/harness/process/stop"} and method in {"GET","POST"} or
            re.fullmatch(r"/api/user-preferences/[^/]+",normalized_path) is not None and method in {"PUT","DELETE"} or
            re.fullmatch(r"/api/generation/[^/]+(?:/events)?",normalized_path) is not None and method=="GET" or
            re.fullmatch(r"/api/generation/[^/]+/(?:cancel|accept|reject)",normalized_path) is not None and method=="POST" or
            re.fullmatch(r"/api/exports",normalized_path) is not None and method=="POST" or
            re.fullmatch(r"/api/exports/[^/]+/(?:cancel|retry)",normalized_path) is not None and method=="POST" or
            re.fullmatch(r"/api/exports/[^/]+(?:/download)?",normalized_path) is not None and method=="GET" or
            re.fullmatch(r"/api/novels/[^/]+/export",normalized_path) is not None and method=="GET" or
            re.fullmatch(r"/api/novels/[^/]+/assets",normalized_path) is not None and method in {"GET","POST"} or
            re.fullmatch(r"/api/assets/[^/]+(?:/download)?",normalized_path) is not None and method in {"GET","DELETE"} or
            normalized_path=="/api/asset-providers" and method=="GET" or
            re.fullmatch(r"/api/asset-providers/[^/]+",normalized_path) is not None and method in {"PUT","DELETE"} or
            normalized_path in {"/api/images/generate","/api/vision/analyze","/api/speech/synthesize"} and method=="POST" or
            re.fullmatch(r"/api/novels/[^/]+/(?:image-generations|speech-generations)(?:/import)?",normalized_path) is not None and method in {"GET","POST"} or
            re.fullmatch(r"/api/novels/[^/]+/import/knowledge-base/review",normalized_path) is not None and method in {"GET","POST"} or
            re.fullmatch(r"/api/novels/[^/]+/import/knowledge-base/review/[^/]+",normalized_path) is not None and method in {"GET","PUT"} or
            re.fullmatch(r"/api/novels/[^/]+/import/knowledge-base/review/[^/]+/ai-analyze",normalized_path) is not None and method=="POST" or
            capability_route and method in {"GET","POST","PUT","PATCH","DELETE"}))
        if not allowed:
            return JSONResponse({"detail":{"code":"COLLABORATION_ROUTE_NOT_ENABLED"}},status_code=501)
        public_metadata = (
            (normalized_path == "/health" and method in {"GET", "HEAD"})
            or (normalized_path in {"/api/health", "/api/providers", "/api/models", "/api/text-models"} and method in {"GET", "HEAD"})
        )
        if not public_metadata:
            token = request.headers.get("X-Session-Token")
            if not token:
                return JSONResponse({"detail": {"code": "SESSION_REQUIRED"}}, status_code=401)
            try:
                trusted_session_resolver.resolve(token)
            except (KeyError, ValueError):
                return JSONResponse({"detail": {"code": "INVALID_SESSION"}}, status_code=401)
    return await call_next(request)
app.add_middleware(CORSMiddleware,allow_origins=[settings.frontend_origin],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
app.include_router(api_router, prefix="/api")
app.include_router(api_router, prefix="/api/v1")
app.include_router(create_collaboration_router(collaboration_read_service))
app.include_router(create_collaboration_router(collaboration_read_service, prefix="/api/v1/collaboration"))
app.include_router(create_collaboration_admin_router(collaboration_admin_service))
app.include_router(create_collaboration_admin_router(collaboration_admin_service, prefix="/api/v1/collaboration/admin"))
app.include_router(create_packaged_bootstrap_router(
    packaged_bootstrap_registry, enabled=lambda: getattr(settings,"enable_packaged_runtime",False),
    initial_workspace_provisioner=packaged_initial_workspace_provisioner,
))
app.include_router(create_packaged_bootstrap_router(
    packaged_bootstrap_registry, enabled=lambda: getattr(settings,"enable_packaged_runtime",False),
    initial_workspace_provisioner=packaged_initial_workspace_provisioner,
    prefix="/api/v1/packaged",
))
class ContextRequest(BaseModel): novel_id:str; chapter:int; instruction:str; cloud:bool=False

@app.get("/health")
def health(): return {"status":"ok","version":__version__,"profile":settings.profile}
@app.get("/novels")
def novels():
    root=settings.data_path()/"novels"; return [{"id":p.name} for p in root.iterdir() if p.is_dir()] if root.exists() else []
@app.post("/context-packs")
def context_pack(req:ContextRequest):
    try: return context_service.build(req.novel_id,req.chapter,req.instruction,req.cloud)
    except Exception as exc: raise HTTPException(400,str(exc)) from exc

if settings.enable_packaged_runtime:
    mount_packaged_frontend(app, Path(os.environ.get("PACKAGED_FRONTEND_DIST", "")))
