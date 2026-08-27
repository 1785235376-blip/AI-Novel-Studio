from .repositories.factory import create_repository_bundle
from .services import NovelService,ChapterService,CanonService,ContextService,GenerationService,LoreService
from .services.agent_context_service import AgentContextService
from .services.agent_job_service import AgentJobService
from .services.continuity_finding_service import ContinuityFindingService
from .services.narrative_state_service import NarrativeStateService
from .services.narrative_finding_service import NarrativeFindingService
from .services.narrative_proposal_service import NarrativeProposalService
from .services.adaptation_service import AdaptationService
from .services.screenplay_service import ScreenplayService
from .services.collaboration_scope_service import CollaborationScopeService
from .services.authorization_service import AuthorizationService
from .services.identity_service import IdentityService
from .services.membership_authorization_service import MembershipAuthorizationService
from .application.audit_service import AuditService
from .application.collaboration_service import CollaborationApplicationService
from .application.persistence import AtomicPathMutationPort, create_atomic_chapter_audit_port
from .trusted_sessions import create_runtime_session_resolver
from .collaboration_api import CollaborationReadService
from .collaboration_admin import CollaborationAdminService
from .lore.memory_agent import MemoryAgentRunner
from .agents import agent_runner
from .runtime import runtime
from .asset_providers import AssetProviderRegistry,DEFAULT_IMAGE_ENDPOINTS,IMAGE_PROVIDER_CATALOG,HttpVideoProvider,ComfyUIImageProvider,Automatic1111ImageProvider
from .asset_providers import build_openai_compatible_from_vault
from .asset_provider_config import load as load_asset_provider_config
from .credential_vault import credential_vault
from .visual_workflow import VisualTextWorkflowAdapter
from .services.asset_task_worker import AssetTaskWorker
from .services.asset_library_service import AssetLibraryService
from .services.export_job_service import ExportJobService
from .services.import_review_service import ImportReviewService
from .services.memory_service import MemoryService
from .services.user_preference_service import UserPreferenceService
from .services.harness_process_service import HarnessProcessService
from .services.v1_capability_service import V1CapabilityService
from .runtime_diagnostics import TextRuntimeDiagnosticsAdapter
from .config import settings
from .packaging.bootstrap_api import PackagedBootstrapRegistry
from .packaging.local_session_bootstrap import LocalSessionBootstrap, TrustedLocalIdentity
from .packaging.initial_workspace import PackagedInitialWorkspaceProvisioner
from .packaging.runtime_identity import RuntimeIdentity
import os
import secrets
repositories=create_repository_bundle()
novel_service=NovelService(repositories.novels,repositories.chapters)
adaptation_service=AdaptationService(repositories.novels,repositories.chapters,runtime,agent_runner)
asset_provider_registry=AssetProviderRegistry()
_asset_endpoint=os.getenv("ASSET_OPENAI_ENDPOINT", "")
_saved_asset_configs = load_asset_provider_config()
_endpoints={**DEFAULT_IMAGE_ENDPOINTS,"openai":_asset_endpoint or DEFAULT_IMAGE_ENDPOINTS["openai"]}
_models={"ddshub":"gpt-image-2","openai":"gpt-image-1","custom":""}
for _provider, _cfg in _saved_asset_configs.items():
    if isinstance(_cfg, dict) and _cfg.get("endpoint"):
        _endpoints[_provider] = _cfg["endpoint"]
        _models[_provider] = _cfg.get("default_model", "")
for _provider,_endpoint in _endpoints.items():
    if not _endpoint: continue
    _cfg=_saved_asset_configs.get(_provider) or IMAGE_PROVIDER_CATALOG.get(_provider,{})
    if _cfg.get('local') and _provider not in _saved_asset_configs: continue
    if _cfg.get('enabled') is False: continue
    try:
        import httpx
        _style=_cfg.get('api_style','openai')
        if _style=='comfyui': _adapter=ComfyUIImageProvider(httpx,_endpoint)
        elif _style=='automatic1111': _adapter=Automatic1111ImageProvider(httpx,_endpoint)
        else: _adapter=build_openai_compatible_from_vault(httpx, _provider, _endpoint, credential_vault)
        _adapter.default_model=_cfg.get('default_model','')
        asset_provider_registry.register(_provider,_adapter)
    except (ImportError, ValueError):
        pass

def refresh_asset_provider(provider_id: str) -> bool:
    """Rebuild one image adapter after a runtime config or vault change."""
    saved = load_asset_provider_config()
    cfg = saved.get(provider_id) if isinstance(saved.get(provider_id), dict) else {}
    catalog=IMAGE_PROVIDER_CATALOG.get(provider_id,{})
    effective={**catalog,**cfg};endpoint=effective.get("endpoint","");style=effective.get("api_style","openai")
    if not cfg and effective.get("local"): asset_provider_registry.unregister(provider_id);return False
    legacy_vault_provider="openai" if provider_id=="custom" and cfg and "requires_credential" not in cfg else provider_id
    if effective.get("enabled") is False or not endpoint or (effective.get("requires_credential",True) and not credential_vault.has(legacy_vault_provider)):
        asset_provider_registry.unregister(provider_id)
        return False
    try:
        import httpx
        if style=="comfyui": adapter=ComfyUIImageProvider(httpx,endpoint)
        elif style=="automatic1111": adapter=Automatic1111ImageProvider(httpx,endpoint)
        else: adapter=build_openai_compatible_from_vault(httpx,legacy_vault_provider,endpoint,credential_vault)
        adapter.default_model=effective.get("default_model","")
        asset_provider_registry.register(provider_id,adapter)
    except (ImportError, ValueError):
        asset_provider_registry.unregister(provider_id)
        return False
    return True

screenplay_service=ScreenplayService(repositories.novels,repositories.chapters,asset_provider_registry)
def refresh_video_provider(provider_id: str, endpoint: str, model_id: str, requires_credential: bool = True) -> bool:
    if provider_id == 'deterministic' or not endpoint or (requires_credential and not credential_vault.has(provider_id)):
        return False
    try:
        import httpx
        secret=credential_vault.resolve(provider_id) if requires_credential else None
        screenplay_service.register_video_provider(provider_id, HttpVideoProvider(httpx, endpoint, secret, model_id))
        return True
    except (ImportError, ValueError):
        return False
asset_task_worker=AssetTaskWorker(screenplay_service)
asset_library_service=AssetLibraryService(settings.data_path())
import_review_service=ImportReviewService(settings.data_path())

def _export_snapshot(novel_id: str, format: str):
    return novel_service.export_snapshot(novel_id, asset_library=asset_library_service, format=format)

export_job_service=ExportJobService(
    settings.data_path(),
    novel_service.export,
    snapshotter=_export_snapshot,
)
chapter_service=ChapterService(repositories.chapters)
memory_service=MemoryService(repositories.lore)
user_preference_service=UserPreferenceService(settings.data_path())
harness_process_service=HarnessProcessService()
# Research, character evolution, visual-memory lineage, plugin manifests,
# local DAG workflows, project overview and release-gate evidence share one
# durable metadata service.  The packaged DesktopHost uses the local sidecar;
# PostgreSQL profiles keep the same API contract while native migrations are
# introduced in a later schema revision.
v1_capability_service=V1CapabilityService(
    settings.data_path(),
    novel_service,
    chapter_service,
    asset_library_service,
    exports=export_job_service,
    project_root=settings.root,
)
canon_service=CanonService(repositories.canon)
generation_service=GenerationService(repositories.generations)
lore_service=LoreService(repositories.lore)
v1_capability_service.bind_lore(lore_service)
continuity_repository=repositories.continuity
continuity_finding_service=ContinuityFindingService(continuity_repository)
v1_capability_service.bind_continuity(continuity_finding_service)
narrative_state_service=NarrativeStateService(repositories.narrative,repositories.chapters,repositories.novels,repositories.lore)
narrative_finding_service=NarrativeFindingService(repositories.narrative)
narrative_proposal_service=NarrativeProposalService(repositories.narrative,narrative_state_service)
collaboration_scope_service=CollaborationScopeService(repositories.scope,repositories.novels)
authorization_service=AuthorizationService(repositories.authorization,collaboration_scope_service)
identity_service=IdentityService(repositories.identity,collaboration_scope_service)
membership_authorization_service=MembershipAuthorizationService(identity_service,authorization_service)
audit_service=AuditService(repositories.authorization)
atomic_chapter_audit_port=create_atomic_chapter_audit_port(repositories.chapters,repositories.authorization)
collaboration_application_service=CollaborationApplicationService(membership_authorization_service,atomic_chapter_audit_port,audit_service)
trusted_session_resolver=create_runtime_session_resolver(
    packaged_runtime=settings.enable_packaged_runtime,
    dev_sessions_json=settings.collaboration_dev_sessions_json,
    collaboration_runtime=settings.enable_collaboration_runtime,
)
packaged_bootstrap_registry=PackagedBootstrapRegistry(expected_origin=lambda: settings.frontend_origin)
if settings.enable_packaged_runtime:
    packaged_runtime_instance_id = os.environ.get("PACKAGED_RUNTIME_INSTANCE_ID", "")
    packaged_bootstrap_secret = os.environ.get("PACKAGED_BOOTSTRAP_SECRET", "")
    if not packaged_runtime_instance_id or not packaged_bootstrap_secret:
        raise RuntimeError("packaged bootstrap configuration is incomplete")
    packaged_bootstrap_registry.configure(LocalSessionBootstrap(
        runtime=RuntimeIdentity(
            runtime_instance_id=packaged_runtime_instance_id,
            ownership_nonce=secrets.token_urlsafe(32),
        ),
        sessions=trusted_session_resolver,
        trusted_identity=TrustedLocalIdentity("local-author", "workspace-a"),
        expected_origin=settings.frontend_origin,
        bootstrap_secret=packaged_bootstrap_secret,
    ))
collaboration_read_service=CollaborationReadService(
    sessions=trusted_session_resolver,
    membership_authorization=membership_authorization_service,
    identity=identity_service,
    authorization=authorization_service,
    scopes=collaboration_scope_service,
    chapters=repositories.chapters,
    generations=repositories.generations,
    lore_repository=repositories.lore,
    novels=repositories.novels,
    collaboration_application=collaboration_application_service,
    visual_workflows=VisualTextWorkflowAdapter(runtime.provider_registry, runtime.model_registry),
    runtime_diagnostics=TextRuntimeDiagnosticsAdapter(runtime.provider_registry, runtime.model_registry),
)
collaboration_admin_service=CollaborationAdminService(
    sessions=trusted_session_resolver,
    identity=identity_service,
    authorization=authorization_service,
    scopes=collaboration_scope_service,
    workspace_mutations=repositories.scope,
    path_mutations=AtomicPathMutationPort(repositories.novels,repositories.scope,repositories.authorization),
)
packaged_initial_workspace_provisioner=PackagedInitialWorkspaceProvisioner(repositories.scope)
context_service=ContextService(repositories.novels,repositories.chapters,lore_service,narrative_repository=repositories.narrative)
agent_context_service=AgentContextService(repositories.novels,repositories.chapters,context_service)
agent_job_service=AgentJobService(generation_service,agent_context_service,repositories.novels,runtime,agent_runner)
memory_agent_service=MemoryAgentRunner(repositories.novels,repositories.chapters,lore_service,generation_service,agent_runner,runtime)
