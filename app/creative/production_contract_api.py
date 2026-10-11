"""Read-only production catalog through the original Studio invocation guard."""
from fastapi import APIRouter, Header, HTTPException

from ..experimental.production_lineage_api import PrivateProductionRoute
from .production_contracts import ProductionCatalog, production_catalog


def create_production_contract_router(service, invoke):
    """The parent supplies original access, flag, actor/scope/incarnation guards."""
    router = APIRouter(tags=["Studio Production Contracts V2"], route_class=PrivateProductionRoute)

    @router.get("/projects/{nid}/studio/production-contracts", response_model=ProductionCatalog)
    def contracts(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        def view(actor, scope, guard):
            guard()
            project = service.project(nid, scope)
            owner = project.get("project", {})
            if owner.get("id") != nid:
                raise HTTPException(403, {"code": "CREATIVE_PRODUCTION_OWNER_CHANGED"})
            if owner.get("entry_kind") != "NEUTRAL_STUDIO":
                raise HTTPException(409, {"code": "CREATIVE_STUDIO_ACTIVATION_REQUIRED"})
            result = production_catalog(nid, scope)
            guard()
            return result

        return invoke(nid, x_session_token, x_branch_id, "domain.read", view)

    return router
