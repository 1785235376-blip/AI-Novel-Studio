from __future__ import annotations
import json
import csv
import io
import inspect
import re
import threading
import hashlib
import uuid
import os
import hmac
from urllib.parse import quote
from .idempotency import IdempotencyStore
from fastapi import APIRouter,HTTPException,Query,Header
from fastapi.responses import StreamingResponse,Response
from pydantic import BaseModel,Field,field_validator
from .config import settings
from .jobs import jobs
from .runtime import runtime
from .repositories import VersionConflict
from .config import settings
from .collaboration import RevisionConflict
from .dependencies import novel_service,chapter_service,canon_service,context_service,agent_context_service,agent_job_service,adaptation_service,screenplay_service,asset_task_worker,asset_library_service,export_job_service,import_review_service,continuity_finding_service,narrative_state_service,narrative_finding_service,narrative_proposal_service,collaboration_scope_service,collaboration_application_service,collaboration_admin_service,authorization_service,trusted_session_resolver,membership_authorization_service,audit_service,refresh_asset_provider
from .dependencies import lore_service, memory_service, v1_capability_service, user_preference_service, harness_process_service
from .services.harness_context_adapter import harness_context_adapter
from .services.harness_access_audit_service import harness_access_audit_service
from .authorization import AuthorizationScope,ScopeKind,ModalityDomain,DomainRole,DomainRoleAssignment
from .document import markdown_to_document
from .credential_vault import VaultUnavailableError, credential_vault
from .asset_providers import DEFAULT_IMAGE_ENDPOINTS,DEFAULT_IMAGE_MODELS,IMAGE_PROVIDER_CATALOG
from .net_safety import OutboundURLRejected, validate_outbound_url
from .asset_provider_config import load as load_asset_provider_config, save as save_asset_provider_config, delete as delete_asset_provider_config
from .model_runtime import TextGenerationRequest, TextGenerationParameters, TextModelNodeInput, ModelRuntimeError
from .asset_worker_config import load as load_asset_worker_config, save as save_asset_worker_config
from .audio_production_store import audio_production_store
from .audio_provider_config import load as load_audio_provider_config, save as save_audio_provider_config, delete as delete_audio_provider_config
from .provider_support import is_canonical_provider_id, provider_support_registry
from .storage import atomic_write
from .services.export_job_service import (
    ExportJobNotCancellable,
    ExportJobNotRetryable,
    ExportJobResultInvalid,
    ExportJobUnavailable,
)
from .plugin_discovery import discover_installed_plugins
from .plugin_catalog import get_plugin_resource, list_plugin_resources
from .plugin_contracts import (
    PLUGIN_ID_DUPLICATE,
    PLUGIN_MANIFEST_DRIFT,
    PluginContractError,
    SAFE_ERROR_MESSAGES,
)
from .services.v1_capability_service import (
    AssetDerivativeIn,
    CapabilityVersionConflict,
    CharacterEvolutionIn,
    PluginManifestIn,
    PluginPermissionIn,
    ReleaseGateIn,
    ResearchRecordIn,
    VisualMemoryIn,
    WorkflowDefinitionIn,
    WorkflowRunIn,
)

router=APIRouter()
_idempotency_store=IdempotencyStore(settings.data_path()/"idempotency.json")
_idempotency_execution_lock=threading.Lock()
def _cached_idempotent(key:str|None, operation:str):
    if not key:return None
    return _idempotency_store.get(f"{operation}:{key}")
def _store_idempotent(key:str|None, operation:str, value):
    if key: return _idempotency_store.put(f"{operation}:{key}",value)
    return value
class NovelIn(BaseModel): title:str=Field(min_length=1,max_length=200); genre:str=""; id:str|None=None
class NovelUpdate(BaseModel): title:str|None=None; genre:str|None=None; status:str|None=None; long_term_summary:str|None=None
class WritingGoalIn(BaseModel):
    target_words:int=Field(default=0,ge=0)
    target_chapters:int=Field(default=0,ge=0)
    deadline:str=""
class ChapterIn(BaseModel): title:str=""; content:str=""; number:int|None=None
class ChapterUpdate(BaseModel): title:str|None=None; content:str|None=None; document:dict|None=None; version:int|None=None; status:str|None=None; source:str="USER"
class GenerateIn(BaseModel):
    novel_id:str
    chapter_id:str
    instruction:str=""
    profile:str="LOCAL_ONLY"
    provider_id:str|None=None
    model_id:str|None=None
    source:str=""
    selected_text:str=""
    style:str=""
    @field_validator("style")
    @classmethod
    def validate_style(cls,value:str)->str:
        if len(value)>120 or any(ord(char)<32 and char not in "\t" for char in value):
            raise ValueError("style must be at most 120 characters")
        return value.strip()
class GenerateVariantsIn(GenerateIn): count:int=Field(default=3,ge=2,le=3)
class CharacterIn(BaseModel): name:str=Field(min_length=1,max_length=120);age:int|None=None;role:str="";personality:str="";goal:str="";current_location:str="";status:str="ALIVE";privacy_level:str="CLOUD_ALLOWED"
class CharacterConsistencyIn(BaseModel): draft:str="";chapter:int=Field(default=1,ge=1);characters:list[dict]=[];forbidden_secrets:list[dict]=[]

def normalize_world_rule_payload(payload: dict) -> dict:
    payload = dict(payload or {})
    if not payload.get("statement"):
        raise ValueError("world rule statement is required")
    terms = payload.get("forbidden_terms", payload.get("forbidden", []))
    if isinstance(terms, str): terms = [terms]
    if not isinstance(terms, list) or len(terms) > 100:
        raise ValueError("forbidden_terms must contain at most 100 items")
    normalized = []
    for term in terms:
        value = str(term).strip()
        if value and len(value) <= 200 and value not in normalized: normalized.append(value)
    payload.pop("forbidden", None)
    if normalized: payload["forbidden_terms"] = normalized
    else: payload.pop("forbidden_terms", None)
    return payload

def world_rule_violations(project_id: str, haystack: str, rules: list[dict]) -> list[dict]:
    serialized = (haystack or "").casefold()
    findings = []
    for rule in rules:
        payload = rule.get("payload") or rule
        terms = payload.get("forbidden_terms") or payload.get("forbidden") or []
        if isinstance(terms, str):
            terms = [terms]
        hits = [str(term) for term in terms if str(term) and str(term).casefold() in serialized]
        if hits:
            findings.append({
                "id": f"WORLD_RULE:{rule.get('id', 'unknown')}",
                "project_id": project_id,
                "finding_type": "WORLD_RULE_VIOLATION",
                "severity": "HIGH",
                "description": f"内容触发世界规则：{payload.get('statement', '未命名规则')}",
                "rule_id": rule.get("id"),
                "subject_type": "WORLD_RULE",
                "subject_id": rule.get("id"),
                "evidence_ids": hits,
            })
    return findings

def summarize_foreshadowing(rows: list[dict], chapter: int) -> dict:
    pending = [row for row in rows if row.get("status") in {"OPEN", "PLANTED"}]
    overdue = [row for row in pending if row.get("target_chapter") and int(row["target_chapter"]) <= chapter]
    return {"chapter": chapter, "pending": pending, "overdue": overdue, "paid_off": [row for row in rows if row.get("status") == "PAID_OFF"]}
class LocationIn(BaseModel): name:str=Field(min_length=1,max_length=160);location_type:str="";description:str="";rules:str="";atmosphere:str="";status:str="ACTIVE";privacy_level:str="CLOUD_ALLOWED"
class TimelineEventIn(BaseModel): title:str=Field(min_length=1,max_length=200);sequence:int=Field(default=1,ge=0);time:str="";description:str="";location:str="";characters:list[str]=[];chapter_id:str="";status:str="CONFIRMED";privacy_level:str="CLOUD_ALLOWED"
class ForeshadowingIn(BaseModel): title:str=Field(min_length=1,max_length=200);description:str="";planted_chapter:int|None=Field(default=None,ge=1);target_chapter:int|None=Field(default=None,ge=1);status:str="OPEN";characters:list[str]=[];events:list[str]=[];privacy_level:str="CLOUD_ALLOWED"
class RelationshipIn(BaseModel): source_character_id:str=Field(min_length=1);target_character_id:str=Field(min_length=1);relationship_type:str=Field(min_length=1,max_length=80);description:str="";status:str="ACTIVE";valid_from_event_id:str="";valid_to_event_id:str="";certainty:str="CONFIRMED";privacy_level:str="CLOUD_ALLOWED"
class OutlineIn(BaseModel): theme:str="";premise:str="";structure:str="THREE_ACT";beginning:str="";middle:str="";ending:str="";main_conflict:str="";climax:str="";status:str="DRAFT"
class VolumeIn(BaseModel): title:str=Field(min_length=1,max_length=200);sequence:int=Field(default=1,ge=1);goal:str="";summary:str="";start_chapter:int|None=Field(default=None,ge=1);end_chapter:int|None=Field(default=None,ge=1);status:str="PLANNED"
class SceneIn(BaseModel): title:str=Field(min_length=1,max_length=200);sequence:int=Field(default=1,ge=1);volume_id:str="";chapter_id:str="";location_id:str="";characters:list[str]=[];purpose:str="";conflict:str="";outcome:str="";status:str="PLANNED"
class StoryRouteIn(BaseModel): title:str=Field(min_length=1,max_length=200);route_type:str="ORIGINAL";parent_route_id:str="";divergence_chapter:int|None=Field(default=None,ge=1);divergence_summary:str="";summary:str="";status:str="DRAFT";shared_until_chapter:int|None=Field(default=None,ge=1)
class AcceptIn(BaseModel): content:str|None=None;expected_version:int|None=None
class CredentialIn(BaseModel): provider:str; credential:str
class UserPreferenceIn(BaseModel): key:str=Field(min_length=1,max_length=120); content:str=Field(min_length=1,max_length=2000); source:str="explicit"; confidence:float=Field(default=1.0,ge=0,le=1)
class AgentChatIn(BaseModel):
    message:str=Field(min_length=1,max_length=12000)
    provider_id:str|None=None
    model_id:str|None=None
    context:dict[str,object]={}
class AssetProviderConfigIn(BaseModel):
    endpoint:str
    default_model:str=""
    api_style:str="openai"
    local:bool=False
    enabled:bool=True
    requires_credential:bool=True
    display_name:str=""
class AssetUploadIn(BaseModel): novel_id:str; filename:str; content_base64:str; media_type:str|None=None; kind:str="image"; character_id:str|None=None; scene_id:str|None=None
class VisionAnalyzeIn(BaseModel): provider_id:str="openai"; model_id:str="gpt-4o-mini"; prompt:str; image_url:str; novel_id:str|None=None; character_id:str|None=None; scene_id:str|None=None
class ImageGenerateIn(BaseModel): provider_id:str="ddshub"; model_id:str="gpt-image-2"; prompt:str=Field(min_length=1); novel_id:str|None=None; character_id:str|None=None; scene_id:str|None=None; constraints:dict[str,object]={}
class ImageEditIn(ImageGenerateIn):
    images:list[str]=Field(min_length=1,max_length=5)
    size:str="auto"
    quality:str="auto"
    output_format:str="png"
class SpeechSynthesizeIn(BaseModel): provider_id:str="auto"; model_id:str=""; voice:str="alloy"; text:str=Field(min_length=1); novel_id:str|None=None; character_id:str|None=None; chapter_id:str|None=None; emotion:str="neutral"
class AudioGenerateIn(BaseModel):
    provider_id:str="auto"
    model_id:str=""
    capability:str=Field(pattern="^(TEXT_TO_AUDIO|AUDIO_EDIT|VIDEO_TO_AUDIO|SFX|FOLEY|MUSIC)$")
    prompt:str=Field(min_length=1)
    source_audio_uri:str|None=None
    source_video_uri:str|None=None
    duration_seconds:float|None=Field(default=None,gt=0,le=600)
    novel_id:str|None=None
    parameters:dict[str,object]=Field(default_factory=dict)
class AudioProviderConfigIn(BaseModel):
    endpoint:str
    default_model:str=Field(min_length=1,max_length=200)
    display_name:str=""
    local:bool=False
    enabled:bool=True
    requires_credential:bool=True
    capabilities:list[str]=Field(min_length=1,max_length=7)
class AudiobookJobIn(BaseModel):
    provider_id:str="auto"
    model_id:str=""
    voice:str="alloy"
    emotion:str="neutral"
    character_id:str|None=None
    speech_rate:float=Field(default=1.0,ge=0.5,le=2.0)
    pause_ms:int=Field(default=280,ge=0,le=3000)
class VoiceBindingIn(BaseModel):
    character_id:str=Field(min_length=1,max_length=160)
    provider_id:str="openai"
    model_id:str="gpt-4o-mini-tts"
    voice:str=Field(default="alloy",min_length=1,max_length=120)
    emotion:str=Field(default="neutral",max_length=80)
class PronunciationEntryIn(BaseModel):
    term:str=Field(min_length=1,max_length=160)
    pronunciation:str=Field(min_length=1,max_length=240)
class AudioProductionSettingsIn(BaseModel):
    voice_bindings:list[VoiceBindingIn]=Field(default_factory=list)
    pronunciation_dictionary:list[PronunciationEntryIn]=Field(default_factory=list)
class AudiobookConsumeIn(BaseModel):
    limit:int=Field(default=1,ge=1,le=20)
    recover_stale:bool=True
    stale_after_seconds:int=Field(default=900,ge=60,le=86400)

def _spoken_chapter_text(text:str)->str:
    return re.sub(r"\A\s*#{1,6}\s+[^\r\n]*(?:\r?\n)+","",text).strip()

def _estimated_subtitle_segments(text:str,speech_rate:float=1.0,pause_ms:int=280)->list[dict]:
    spoken_text=_spoken_chapter_text(text)
    parts=[part.strip() for part in re.split(r"(?<=[。！？!?；;])|\n+",spoken_text) if part.strip()]
    cursor=0;segments=[]
    for index,part in enumerate(parts,1):
        units=len(re.sub(r"\s+","",part));duration=max(600,round(units*180/max(0.5,speech_rate)))
        segments.append({'id':f'segment-{index:04d}','text':part,'subtitle':part,'start_ms':cursor,'end_ms':cursor+duration})
        cursor+=duration+pause_ms
    return segments

def _subtitle_timestamp(milliseconds:int,webvtt:bool=False)->str:
    value=max(0,int(milliseconds));hours,remainder=divmod(value,3600000);minutes,remainder=divmod(remainder,60000);seconds,millis=divmod(remainder,1000)
    separator='.' if webvtt else ','
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{separator}{millis:03d}"

def _render_subtitles(segments:list[dict],format:str)->str:
    webvtt=format=='vtt';blocks=[]
    for index,segment in enumerate(segments,1):
        start=_subtitle_timestamp(segment.get('start_ms',0),webvtt);end=_subtitle_timestamp(segment.get('end_ms',0),webvtt);text=str(segment.get('subtitle') or segment.get('text') or '').strip()
        blocks.append(f"{index}\n{start} --> {end}\n{text}")
    content='\n\n'.join(blocks)
    return f"WEBVTT\n\n{content}\n" if webvtt else f"{content}\n"
class AssetWorkerConfigIn(BaseModel): limit:int|None=None; interval_seconds:float|None=None; timeout_seconds:int|None=None; execute:bool|None=None
class RenameIn(BaseModel): title:str; version:int
class MoveIn(BaseModel): direction:str
class PendingEditIn(BaseModel): proposals:list[dict]
class ImportIn(BaseModel): format:str; content:str=""; content_base64:str|None=None; confirm:bool=False
class ImportKnowledgeReviewIn(BaseModel):
    decision:str
    candidates:dict[str,list[dict]]={}
    review_id:str|None=None
    note:str=""
    selected:dict[str,list[bool]]|None=None
class ImportKnowledgeReviewUpdateIn(BaseModel):
    candidates:dict[str,list[dict]]
    selected:dict[str,list[bool]]|None=None
class ImportAiReviewIn(BaseModel):
    provider_id:str|None=None
    model_id:str|None=None
class ExportCreateIn(BaseModel): format:str="json"
class AdaptationProposalIn(BaseModel): target:str; title:str=""; instruction:str=""
class AdaptationBlueprintUpdateIn(BaseModel): focus:str; pacing:str; format:str; constraints:list[str]=[]; chapter_map:list[dict]=[]
class AdaptationDraftReviewIn(BaseModel): decision:str; note:str=""
class AdaptationDraftGenerateIn(BaseModel): mode:str="deterministic"; provider_id:str|None=None; model_id:str|None=None
class ScreenplayIn(BaseModel): title:str=""
class ScreenplaySceneIn(BaseModel): heading:str; time:str=""; location:str=""; characters:list[str]=[]; action:str=""; dialogue:list[dict]=[]; emotion:str=""
class ShotIn(BaseModel): shot_size:str; camera_angle:str; camera_motion:str; subject_position:str; action:str; dialogue:list[dict]=[]; sound_effect:str; duration_seconds:int=5
class StoryboardCardIn(BaseModel): frame_prompt:str=""; composition:str=""; color:str=""
class TransitionIn(BaseModel): type:str="CUT"; duration_seconds:int=0; note:str=""; prompt:str=""
class AssetRequirementIn(BaseModel): kind:str="IMAGE"; description:str=""; status:str="PENDING"; notes:str=""
class AssetTaskIn(BaseModel): status:str="PENDING"; provider_id:str|None=None; model_id:str|None=None; error:str|None=None
class ContinuityCheckIn(BaseModel): events:list[dict]=[]; locations:list[dict]=[]; knowledge:list[dict]=[]; used_subject_ids:list[str]=[]; world_rules:list[dict]=[]
class ContinuityScanChapterIn(BaseModel): chapter_id:str|None=None; chapter:int|None=Field(default=None,ge=1)
class NarrativeThreadIn(BaseModel): id:str; title:str; description:str=""
class NarrativeForeshadowingIn(BaseModel): id:str; title:str; thread_id:str|None=None
class NarrativeTransitionIn(BaseModel): status:str; event_id:str; event_type:str; chapter_version_id:str; evidence_ids:list[str]=[]; payload:dict={};expected_revision:int|None=None
class NarrativeExpectationIn(BaseModel): id:str; subject_type:str; subject_id:str; expectation_type:str; deadline_chapter:int; evidence_ids:list[str]=[]; source_chapter_version_id:str|None=None;active:bool=True
class NarrativeCheckIn(BaseModel): current_chapter:int; thread_last_progress:dict[str,int]={}; foreshadowing_payoff_chapter:dict[str,int]={}
class MysteryIn(BaseModel): id:str;title:str;description:str="";opened_chapter_version_id:str|None=None
class CharacterGoalIn(BaseModel): id:str;character_id:str;title:str;description:str="";started_chapter_version_id:str|None=None
class NarrativeStatusIn(BaseModel): status:str;chapter_version_id:str|None=None;expected_revision:int|None=None
class ChapterNarrativeProgressIn(BaseModel): id:str;chapter_id:str;chapter_version:int;entity_type:str;entity_id:str;progress_type:str;summary:str="";evidence_ids:list[str]=[];event_id:str;expected_revision:int|None=None
class NarrativeProposalIn(BaseModel): id:str;proposal_type:str;subject_type:str;subject_id:str;chapter_version_id:str;payload:dict;summary:str="";evidence_ids:list[str]=[]
class WorkspaceIn(BaseModel): id:str;name:str
class StorylineIn(BaseModel): id:str;name:str;description:str=""
class BranchIn(BaseModel): id:str;name:str;parent_branch_id:str|None=None
class RevisionWriteIn(BaseModel): expected_revision:int|None=None
class RevisionStatusIn(RevisionWriteIn): status:str;chapter_version_id:str|None=None
class AgentJobIn(BaseModel): agent_id:str;novel_id:str;chapter:int=Field(ge=1);instruction:str="";target:str="local";provider_id:str|None=None;model_id:str|None=None;execution_mode:str="deterministic";timeout_seconds:int=Field(default=120,ge=1,le=3600);branch_id:str|None=None
class AgentJobReviewIn(BaseModel): decision:str;reviewed_by:str=Field(min_length=1);note:str="";actions:list[dict]=[]
class AgentJobApplyIn(BaseModel): applied_by:str=Field(min_length=1)
class LoreEvidenceApiIn(BaseModel):
    id:str|None=None
    source_type:str="USER_ACTION"
    source_id:str=Field(min_length=1,max_length=240)
    chapter_id:str|None=None
    chapter_version:int|None=Field(default=None,ge=1)
    generation_job_id:str|None=None
    excerpt:str|None=None
    locator:dict={}
    content_hash:str|None=None
    privacy:str="LOCAL_ONLY"
class LoreProposalApiIn(BaseModel):
    id:str|None=None
    proposal_type:str="CHARACTER_MEMORY"
    payload:dict={}
    relations:list[dict]=[]
    source_chapter_id:str|None=None
    source_version:int|None=Field(default=None,ge=1)
    agent_name:str|None=None
    generation_job_id:str|None=None
    confidence:float|None=Field(default=None,ge=0,le=1)
class LoreProposalReviewIn(BaseModel):
    approved_payload:dict={}
    reviewer:str=Field(min_length=1,max_length=160)
    reason:str|None=None
class MemoryApproveApiIn(BaseModel):
    character_id:str
    memory_type:str="EXPERIENCE"
    content:dict={}
    valid_from_chapter:int|None=Field(default=None,ge=1)
    valid_to_chapter:int|None=Field(default=None,ge=1)
    reviewer:str=Field(min_length=1,max_length=160)
    memory_id:str|None=None
    business_id:str|None=None
class MemoryRetractApiIn(BaseModel): reason:str=Field(min_length=1,max_length=2000)
class MemorySupersedeApiIn(BaseModel):
    memory_type:str="EXPERIENCE"
    content:dict={}
    valid_from_chapter:int|None=Field(default=None,ge=1)
    valid_to_chapter:int|None=Field(default=None,ge=1)
    proposal_id:str
    business_id:str|None=None
class MemorySnapshotApiIn(BaseModel):
    scope:str="NOVEL"
    scope_key:str="novel"
    created_by:str=Field(default="local-author",min_length=1,max_length=160)
    range_start:int|None=Field(default=None,ge=1)
    range_end:int|None=Field(default=None,ge=1)

def _collaboration_context(chapter_id:str,session_token:str|None,branch_id:str|None):
    if not session_token:raise HTTPException(401,{"code":"SESSION_REQUIRED"})
    try:
        actor=trusted_session_resolver.resolve(session_token)
        if not branch_id:raise HTTPException(400,{"code":"BRANCH_SCOPE_REQUIRED"})
        chapter=chapter_service.get(chapter_id)
        project_id=chapter["novel_id"]
        workspace_id=collaboration_scope_service.repository.project_workspace(project_id)
        if workspace_id is None:raise PermissionError("project collaboration scope is not configured")
        branch=collaboration_scope_service.repository.get("branches",branch_id)
        if branch.get("workspace_id")!=workspace_id or branch.get("project_id")!=project_id:
            raise PermissionError("branch does not contain this chapter project")
        scope=AuthorizationScope(ScopeKind.BRANCH,workspace_id,project_id,branch["storyline_id"],branch["id"])
        return actor,scope,chapter
    except KeyError:raise HTTPException(401,{"code":"INVALID_SESSION"})
    except PermissionError as exc:raise HTTPException(403,{"code":"FORBIDDEN","detail":str(exc)})

def _collaboration_unavailable():
    raise HTTPException(501,{"code":"COLLABORATION_MUTATION_NOT_SUPPORTED"})

def _adaptation_context(novel_id:str,branch_id:str|None,session_token:str|None,permission:str):
    if not branch_id:return None,None
    if not session_token:raise HTTPException(401,{"code":"SESSION_REQUIRED"})
    try:actor=trusted_session_resolver.resolve(session_token);branch=collaboration_scope_service.repository.get("branches",branch_id)
    except KeyError:raise HTTPException(401,{"code":"INVALID_SESSION_OR_BRANCH"})
    workspace_id=collaboration_scope_service.repository.project_workspace(novel_id)
    if not workspace_id or actor.workspace_id!=workspace_id or branch.get("workspace_id")!=workspace_id or branch.get("project_id")!=novel_id:raise HTTPException(403,{"code":"ADAPTATION_SCOPE_FORBIDDEN"})
    scope=AuthorizationScope(ScopeKind.BRANCH,workspace_id,novel_id,branch.get("storyline_id"),branch_id)
    try:membership_authorization_service.require(actor,permission,ModalityDomain.NOVEL,scope)
    except PermissionError as exc:raise HTTPException(403,{"code":"ADAPTATION_CAPABILITY_FORBIDDEN","detail":str(exc)})
    return actor,scope

def _agent_job_read_actor(session_token:str|None):
    if not session_token:
        raise HTTPException(401,{"code":"SESSION_REQUIRED"})
    try:
        return trusted_session_resolver.resolve(session_token)
    except KeyError:
        raise HTTPException(401,{"code":"INVALID_SESSION"})

def _agent_job_scope(actor, novel_id: str, branch_id: str | None):
    """Resolve and validate a branch scope for an Agent Job.

    Branch IDs are not globally trusted identifiers: the project mapping and
    the actor workspace must all agree before a capability check is attempted.
    Returning the resolved scope lets callers apply the operation-specific
    permission without duplicating these checks.
    """
    if not branch_id:
        return None
    try:
        workspace_id = collaboration_scope_service.repository.project_workspace(novel_id)
        branch = collaboration_scope_service.repository.get("branches", branch_id)
        if not workspace_id or actor.workspace_id != workspace_id:
            raise PermissionError("actor workspace does not match project scope")
        if (
            branch.get("workspace_id") != workspace_id
            or branch.get("project_id") != novel_id
        ):
            raise PermissionError("branch does not contain this project")
        scope = AuthorizationScope(
            ScopeKind.BRANCH,
            workspace_id,
            novel_id,
            branch.get("storyline_id"),
            branch_id,
        )
        collaboration_scope_service.validate_scope(scope)
        return scope
    except (KeyError, ValueError, PermissionError) as exc:
        raise HTTPException(
            403,
            {"code": "AGENT_JOB_SCOPE_FORBIDDEN", "detail": str(exc)},
        ) from exc


def _validate_agent_job_branch(
    actor,
    novel_id: str,
    branch_id: str | None,
    permission: str | None = None,
):
    scope = _agent_job_scope(actor, novel_id, branch_id)
    if scope is not None and permission:
        try:
            membership_authorization_service.require(
                actor, permission, ModalityDomain.NOVEL, scope
            )
        except PermissionError as exc:
            raise HTTPException(
                403,
                {"code": "AGENT_JOB_CAPABILITY_FORBIDDEN", "detail": str(exc)},
            ) from exc
    return scope


def _validate_agent_job_filter(
    actor,
    novel_id: str | None,
    branch_id: str | None,
    permission: str = "domain.read",
):
    """Validate list/export filters, resolving project from branch when needed."""
    if not branch_id:
        return None
    try:
        branch = collaboration_scope_service.repository.get("branches", branch_id)
    except KeyError as exc:
        raise HTTPException(
            403, {"code": "AGENT_JOB_SCOPE_FORBIDDEN", "detail": "unknown branch"}
        ) from exc
    resolved_novel_id = novel_id or branch.get("project_id")
    if not resolved_novel_id or branch.get("project_id") != resolved_novel_id:
        raise HTTPException(
            403,
            {"code": "AGENT_JOB_SCOPE_FORBIDDEN", "detail": "branch/project mismatch"},
        )
    return _validate_agent_job_branch(actor, resolved_novel_id, branch_id, permission)


def _agent_job_actor_for_record(actor_token, job, permission: str = "domain.read"):
    actor = _agent_job_read_actor(actor_token)
    _validate_agent_job_branch(actor, job.get("novel_id"), job.get("branch_id"), permission)
    return actor


def _require_agent_job_capability(actor_token, job, permission):
    return _agent_job_actor_for_record(actor_token, job, permission)

def _generation_context(jid:str,session_token:str|None):
    if not session_token:raise HTTPException(401,{"code":"SESSION_REQUIRED"})
    try:actor=trusted_session_resolver.resolve(session_token)
    except KeyError:raise HTTPException(401,{"code":"INVALID_SESSION"})
    try:job=jobs.get(jid)
    except KeyError:raise HTTPException(404,"Generation job not found")
    if not job.actor_id or actor.actor_id!=job.actor_id or actor.workspace_id!=job.workspace_id:
        raise HTTPException(403,{"code":"FORBIDDEN"})
    if not job.scope:raise HTTPException(403,{"code":"UNSCOPED_LEGACY_JOB"})
    raw=job.scope;scope=AuthorizationScope(ScopeKind(raw["kind"]),raw["workspace_id"],raw.get("project_id"),raw.get("storyline_id"),raw.get("branch_id"))
    try:membership_authorization_service.require(actor,"domain.read",ModalityDomain.NOVEL,scope)
    except PermissionError as exc:raise HTTPException(403,{"code":"FORBIDDEN","detail":str(exc)})
    return actor,scope,job

def guard(fn,*args):
    try:return fn(*args)
    except VersionConflict as exc:raise HTTPException(409,{"code":"VERSION_CONFLICT","server":exc.current,"conflict":exc.as_dict()})
    except RevisionConflict as exc:raise _revision_error(exc)
    except FileNotFoundError as exc:raise HTTPException(404,f"Not found: {exc}")
    except FileExistsError as exc:raise HTTPException(409,f"Already exists: {exc}")
    except (ValueError,KeyError) as exc:raise HTTPException(400,str(exc))

def _authorize_media_novel(novel_id:str,session_token:str|None,permission:str):
    if settings.enable_collaboration_runtime:
        _authorize_novel_project(novel_id,session_token,permission)

def capability_guard(fn,*args,**kwargs):
    """Map capability-service failures to the shared API error contract."""
    try:
        return fn(*args,**kwargs)
    except PluginContractError as exc:
        status = 409 if exc.code in {PLUGIN_MANIFEST_DRIFT, PLUGIN_ID_DUPLICATE} else 400
        raise HTTPException(status, {
            "code": exc.code,
            "error_code": exc.code,
            "message": exc.message,
            "error": SAFE_ERROR_MESSAGES.get(exc.code, exc.message),
        }) from None
    except CapabilityVersionConflict as exc:
        raise HTTPException(409, {"code": "VERSION_CONFLICT", "current": exc.current}) from exc
    except FileNotFoundError as exc:
        raise HTTPException(404, {"code": "NOT_FOUND", "resource": str(exc)}) from exc
    except FileExistsError as exc:
        raise HTTPException(409, {"code": "ALREADY_EXISTS", "resource": str(exc)}) from exc
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(400, {"code": "INVALID_CAPABILITY_REQUEST", "message": str(exc)}) from exc


def plugin_catalog_guard(fn, *args, **kwargs):
    """Map catalog failures without leaking paths, stacks, or raw exceptions."""
    try:
        return fn(*args, **kwargs)
    except PluginContractError as exc:
        if exc.code in {PLUGIN_MANIFEST_DRIFT, PLUGIN_ID_DUPLICATE}:
            status = 409
        elif exc.code in {"PLUGIN_RESOURCE_TOO_LARGE", "PLUGIN_RESOURCE_INVALID_JSON"}:
            status = 400
        elif exc.code.startswith("PLUGIN_RESOURCE_"):
            status = 404
        else:
            status = 400
        raise HTTPException(status, {
            "code": exc.code,
            "error_code": exc.code,
            "message": exc.message,
            "error": SAFE_ERROR_MESSAGES.get(exc.code, exc.message),
        }) from None
    except RecursionError:
        raise HTTPException(400, {
            "code": "PLUGIN_RESOURCE_INVALID_JSON",
            "error_code": "PLUGIN_RESOURCE_INVALID_JSON",
            "message": SAFE_ERROR_MESSAGES.get("PLUGIN_RESOURCE_INVALID_JSON"),
            "error": SAFE_ERROR_MESSAGES.get("PLUGIN_RESOURCE_INVALID_JSON"),
        }) from None
    except FileNotFoundError:
        raise HTTPException(404, {
            "code": "NOT_FOUND",
            "error_code": "NOT_FOUND",
            "message": "插件或声明式资源不可用。",
            "error": "插件或声明式资源不可用。",
        }) from None
    except (ValueError, KeyError, TypeError):
        raise HTTPException(400, {
            "code": "INVALID_CAPABILITY_REQUEST",
            "error_code": "INVALID_CAPABILITY_REQUEST",
            "message": "插件资源请求无效。",
            "error": "插件资源请求无效。",
        }) from None
def _legacy_revision_state(project_id,expected_revision):
    from .services.narrative_state_service import NarrativeStateService
    try:
        collaboration_scope_service.novels.get(project_id);scope=collaboration_scope_service.ensure_default_scope(project_id);repository=collaboration_scope_service.scoped_narrative(scope,narrative_state_service.repository).with_revision(expected_revision,settings.enable_optimistic_concurrency);return NarrativeStateService(repository,narrative_state_service.chapters,narrative_state_service.novels,narrative_state_service.lore)
    except (FileNotFoundError,KeyError):return narrative_state_service
@router.get("/health")
def health():
    from .packaging.control_pipe import get_packaged_control_reader_status
    return {"backend":"Healthy","database":"Unavailable (file runtime active)" if settings.storage_backend=="file" else "Configured","storage":settings.storage_backend,"providers":runtime.provider_status(),"control_reader":get_packaged_control_reader_status(),"version":"0.4.8.1","profile":settings.profile}
@router.get("/text-models")
def text_models(): return {"items":runtime.text_models()}
@router.get("/agents")
def agents():
    from .agent_catalog import public_agent_catalog
    return public_agent_catalog()
@router.get("/user-preferences")
def user_preferences(): return user_preference_service.list()
@router.get("/harness/status")
def harness_status():
    """Probe only the explicitly configured local DeepSeek Harness endpoint."""
    endpoint=os.getenv("DEEPSEEK_HARNESS_URL", "http://127.0.0.1:3080").rstrip("/")
    from urllib.parse import urlparse
    parsed=urlparse(endpoint)
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        return {"configured":False,"reachable":False,"reason":"本地地址限制"}
    try:
        import httpx
        response=httpx.get(endpoint+"/api/health", timeout=0.8)
        if response.status_code < 500:
            payload=response.json() if "application/json" in response.headers.get("content-type","") else {}
            version=payload.get("version")
            minimum=os.getenv("DEEPSEEK_HARNESS_MIN_VERSION", "")
            def parts(value):
                try: return tuple(int(x) for x in str(value).lstrip("v").split(".")[:3])
                except (TypeError,ValueError): return ()
            compatible=not minimum or (bool(parts(version)) and parts(version) >= parts(minimum))
            return {"configured":True,"reachable":True,"endpoint":endpoint,"version":version,"compatible":compatible,"minimum_version":minimum or None}
    except Exception:
        pass
    return {"configured":True,"reachable":False,"endpoint":endpoint,"compatible":False}
@router.get("/harness/launch-readiness")
def harness_launch_readiness():
    from urllib.parse import urlparse
    endpoint=os.getenv("DEEPSEEK_HARNESS_URL", "http://127.0.0.1:3080").rstrip("/")
    parsed=urlparse(endpoint); authorized=user_preference_service.list()["harness_enabled"]
    local=parsed.hostname in {"127.0.0.1","localhost","::1"}
    if not authorized: return {"ready":False,"authorized":False,"local_endpoint":local,"reason":"用户尚未授权"}
    if not local: return {"ready":False,"authorized":True,"local_endpoint":False,"reason":"仅允许本地 Harness"}
    status=harness_status()
    return {"ready":not status.get("reachable",False),"authorized":True,"local_endpoint":True,"endpoint":endpoint,"port_available":not status.get("reachable",False),"reason":"可启动检查通过" if not status.get("reachable",False) else ("Harness 版本不兼容" if status.get("compatible") is False else "端口已有服务")}
@router.get("/harness/process")
def harness_process_status(): return harness_process_service.status()
@router.get("/harness/context-contract")
def harness_context_contract(): return harness_context_adapter.contract()
@router.get("/harness/access-audit")
def harness_access_audit(limit: int = Query(default=20, ge=1, le=100), novel_id: str | None = None, agent_id: str | None = None, outcome: str | None = None):
    return {"items": harness_access_audit_service.list(limit, novel_id, agent_id, outcome)}
@router.get("/harness/access-audit.csv")
def harness_access_audit_csv(limit: int = Query(default=100, ge=1, le=100), novel_id: str | None = None, agent_id: str | None = None, outcome: str | None = None):
    import csv
    from io import StringIO
    output = StringIO(); writer = csv.DictWriter(output, fieldnames=["at", "novel_id", "chapter", "agent_id", "scopes", "outcome"])
    writer.writeheader()
    for item in harness_access_audit_service.list(limit, novel_id, agent_id, outcome):
        writer.writerow({**item, "scopes": ";".join(item.get("scopes", []))})
    return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=harness-access-audit.csv"})
@router.delete("/harness/access-audit")
def clear_harness_access_audit(confirm: bool = Query(default=False)):
    if not confirm:
        raise HTTPException(400, {"code": "AUDIT_CLEAR_CONFIRMATION_REQUIRED"})
    return harness_access_audit_service.clear()
@router.get("/harness/context")
def harness_context(novel_id: str, chapter: int, agent_id: str = "writer", instruction: str = ""):
    """Expose the existing Agent Context to an authorized local Harness as read-only data."""
    if not user_preference_service.list()["harness_enabled"]:
        raise HTTPException(403, {"code": "HARNESS_NOT_AUTHORIZED"})
    try:
        context = agent_context_service.build(agent_id, novel_id, chapter, instruction, False)
    except KeyError as exc:
        harness_access_audit_service.append(novel_id=novel_id, chapter=chapter, agent_id=agent_id, scopes=[], outcome="not_found")
        raise HTTPException(404, {"code": "CONTEXT_NOT_FOUND", "field": str(exc)}) from exc
    # The Harness receives the generated context, never the caller instruction as a
    # separate field; the contract remains the authoritative access declaration.
    context.pop("instruction", None)
    contract = harness_context_adapter.contract()
    harness_access_audit_service.append(novel_id=novel_id, chapter=chapter, agent_id=agent_id, scopes=contract["read_scopes"])
    return {"contract": contract, "accessed_scopes": contract["read_scopes"], "context": context}
@router.post("/harness/process/start")
def harness_process_start():
    if not user_preference_service.list()["harness_enabled"]: raise HTTPException(403,{"code":"HARNESS_NOT_AUTHORIZED"})
    readiness=harness_launch_readiness()
    if not readiness["ready"]: raise HTTPException(409,{"code":"HARNESS_NOT_READY","reason":readiness["reason"]})
    return harness_process_service.start()
@router.post("/harness/process/stop")
def harness_process_stop(): return harness_process_service.stop()
@router.put("/user-preferences/{key}")
def user_preference_set(key: str, body: UserPreferenceIn):
    if key != body.key: raise HTTPException(400, {"code":"PREFERENCE_KEY_MISMATCH"})
    if not user_preference_service.list()["enabled"]: raise HTTPException(409, {"code":"PREFERENCES_DISABLED"})
    return user_preference_service.upsert(key, body.content, body.source, body.confidence)
@router.delete("/user-preferences/{key}")
def user_preference_delete(key: str): user_preference_service.delete(key); return {"deleted":True,"key":key}
@router.put("/user-preferences-enabled")
def user_preferences_enabled(enabled: bool = Query(...)): return {"enabled":user_preference_service.set_enabled(enabled)}
@router.put("/user-preferences-share-enabled")
def user_preferences_share_enabled(enabled: bool = Query(...)): return {"share_enabled":user_preference_service.set_share_enabled(enabled)}
@router.put("/harness-enabled")
def harness_enabled(enabled: bool = Query(...)): return {"harness_enabled":user_preference_service.set_harness_enabled(enabled)}
@router.post("/agent/chat")
def agent_chat(body:AgentChatIn):
    """Read-only control-center conversation; no mutation tools are exposed."""
    provider_id=body.provider_id or "deepseek"
    model_id=body.model_id or "deepseek-chat"
    safe_context={str(k): v for k,v in body.context.items() if str(k) in {"novel_id","chapter_id","chapter_number","title","summary"}}
    preferences_used=False
    preference_state=user_preference_service.list()
    if preference_state["share_enabled"]:
        safe_preferences=[{"key": item["key"], "content": item["content"]} for item in preference_state["items"][:20]]
        if safe_preferences:
            safe_context["user_preferences"]=safe_preferences
            preferences_used=True
    prompt=body.message
    if safe_context:
        prompt += "\n\n当前工作区只读上下文：" + json.dumps(safe_context,ensure_ascii=False)[:8000]
    request=TextGenerationRequest(provider_id=provider_id,model_id=model_id,prompt=prompt,
        system_instruction="你是 AI-Novel-Studio 的只读主控助手。只能回答问题、解释软件能力和提出建议，不得声称已经执行任何写入、删除、发布或外部操作。",
        parameters=TextGenerationParameters(temperature=0.2,max_output_tokens=1200),metadata={"surface":"control_center","mode":"read_only"})
    if not runtime.packaged_author_route_ready(provider_id):
        raise HTTPException(503,{"code":"TEXT_PROVIDER_NOT_CONFIGURED","message":"未配置可用文本模型，未调用 DeepSeek。","retryable":False})
    try:
        result=runtime.generation_runtime.text_node.execute(TextModelNodeInput(request))
    except ModelRuntimeError as exc:
        raise HTTPException(503,{"code":exc.code.value,"message":exc.safe_message,"retryable":exc.retryable}) from exc
    return {"message":result.generated_text,"provider_id":result.response.provider_id,"model_id":result.response.model_id,"read_only":True,"preferences_used":preferences_used}
@router.get("/agents/{agent_id}/context-preview")
def agent_context_preview(agent_id:str,novel_id:str,chapter:int,instruction:str="",target:str="local"):
    if target not in {"local","cloud"}:raise HTTPException(400,"target must be local or cloud")
    return guard(agent_context_service.build,agent_id,novel_id,chapter,instruction,target=="cloud")
@router.post("/agent-jobs",status_code=202)
def create_agent_job(body:AgentJobIn,x_session_token:str|None=Header(default=None,alias="X-Session-Token")):
    actor=_agent_job_read_actor(x_session_token)
    _validate_agent_job_branch(actor,body.novel_id,body.branch_id,"domain.write")
    if body.target not in {"local","cloud"}:raise HTTPException(400,"target must be local or cloud")
    result=guard(agent_job_service.create,body.agent_id,body.novel_id,body.chapter,body.instruction,body.target,body.provider_id,body.model_id,body.execution_mode,body.timeout_seconds)
    if body.branch_id:
        result={**result,"branch_id":body.branch_id};agent_job_service.generations.save(result)
    return result
@router.get("/agent-jobs/export.csv")
def export_agent_jobs(novel_id:str|None=None,agent_id:str|None=None,status:str|None=None,created_after:str|None=None,created_before:str|None=None,branch_id:str|None=None,x_session_token:str|None=Header(default=None,alias="X-Session-Token")):
    actor=_agent_job_read_actor(x_session_token)
    scope=_validate_agent_job_filter(actor,novel_id,branch_id,"domain.read")
    content=guard(agent_job_service.export_csv,novel_id,agent_id,status,created_after,created_before,branch_id)
    if scope is not None:
        summary=agent_job_service.export_summary(novel_id,agent_id,status,created_after,created_before,branch_id)
        audit_service.append(audit_service.build(actor,"AGENT_JOB_EXPORT","AgentJobExport",novel_id or scope.project_id,scope,summary))
    return Response(content=content,media_type="text/csv",headers={"Content-Disposition":"attachment; filename=agent-jobs.csv"})
@router.get("/agent-jobs/audit")
def agent_job_audit(novel_id:str,branch_id:str,created_after:str|None=None,created_before:str|None=None,page:int=Query(default=1,ge=1),page_size:int=Query(default=20,ge=1,le=100),x_session_token:str|None=Header(default=None,alias="X-Session-Token")):
    actor=_agent_job_read_actor(x_session_token);scope=_validate_agent_job_filter(actor,novel_id,branch_id,"domain.read")
    # Audit events live in the authorization repository behind AuditService;
    # the scope repository only stores workspace/project/branch metadata.
    events=[event for event in audit_service.repository.list_audit_events(scope) if event.get("action")=="AGENT_JOB_EXPORT"]
    if created_after: events=[event for event in events if str(event.get("timestamp", "")) >= created_after]
    if created_before: events=[event for event in events if str(event.get("timestamp", "")) <= created_before]
    events=sorted(events,key=lambda event:str(event.get("timestamp", "")),reverse=True)
    total=len(events);start=(page-1)*page_size
    return {"items":events[start:start+page_size],"page":page,"page_size":page_size,"total":total,"has_more":start+page_size<total}
@router.get("/agent-jobs/audit.csv")
def export_agent_job_audit(novel_id:str,branch_id:str,created_after:str|None=None,created_before:str|None=None,x_session_token:str|None=Header(default=None,alias="X-Session-Token")):
    result=agent_job_audit(novel_id,branch_id,created_after,created_before,1,100,x_session_token)
    out=io.StringIO(); writer=csv.writer(out); writer.writerow(["id","actor_id","action","target_type","target_id","timestamp","result_count","filters"])
    for event in result["items"]:
        metadata=event.get("metadata") or {}; writer.writerow([event.get("id",""),event.get("actor_id",""),event.get("action",""),event.get("target_type",""),event.get("target_id",""),event.get("timestamp",""),metadata.get("result_count",0),json.dumps(metadata.get("filters") or {},ensure_ascii=False,sort_keys=True)])
    return Response(content=out.getvalue(),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=agent-job-audit.csv"})
@router.get("/agent-jobs/{job_id}")
def get_agent_job(job_id:str,x_session_token:str|None=Header(default=None,alias="X-Session-Token")):
    job=guard(agent_job_service.get,job_id)
    _agent_job_actor_for_record(x_session_token,job)
    return job
@router.get("/agent-jobs")
def list_agent_jobs(novel_id:str|None=None,agent_id:str|None=None,status:str|None=None,created_after:str|None=None,created_before:str|None=None,branch_id:str|None=None,page:int=Query(default=1,ge=1),page_size:int=Query(default=20,ge=1,le=100),x_session_token:str|None=Header(default=None,alias="X-Session-Token")):
    actor=_agent_job_read_actor(x_session_token)
    _validate_agent_job_filter(actor,novel_id,branch_id,"domain.read")
    return guard(agent_job_service.list,novel_id,agent_id,status,page,page_size,created_after,created_before,branch_id)
@router.post("/agent-jobs/{job_id}/execute")
def execute_agent_job(job_id:str,x_session_token:str|None=Header(default=None,alias="X-Session-Token")):
    _agent_job_actor_for_record(x_session_token,guard(agent_job_service.get,job_id),"domain.write")
    return guard(agent_job_service.execute,job_id)
@router.post("/agent-jobs/{job_id}/start",status_code=202)
def start_agent_job(job_id:str,x_session_token:str|None=Header(default=None,alias="X-Session-Token")):
    _agent_job_actor_for_record(x_session_token,guard(agent_job_service.get,job_id),"domain.write")
    return guard(agent_job_service.start,job_id)
@router.post("/agent-jobs/{job_id}/cancel")
def cancel_agent_job(job_id:str,x_session_token:str|None=Header(default=None,alias="X-Session-Token")):
    _agent_job_actor_for_record(x_session_token,guard(agent_job_service.get,job_id),"domain.write")
    return guard(agent_job_service.cancel,job_id)
@router.post("/agent-jobs/{job_id}/retry",status_code=202)
def retry_agent_job(job_id:str,x_session_token:str|None=Header(default=None,alias="X-Session-Token")):
    _agent_job_actor_for_record(x_session_token,guard(agent_job_service.get,job_id),"domain.write")
    return guard(agent_job_service.retry,job_id)
@router.post("/agent-jobs/{job_id}/review")
def review_agent_job(job_id:str,body:AgentJobReviewIn,x_session_token:str|None=Header(default=None,alias="X-Session-Token")):
    _require_agent_job_capability(x_session_token,guard(agent_job_service.get,job_id),"domain.review")
    return guard(agent_job_service.review,job_id,body.decision,body.reviewed_by,body.note,body.actions)
@router.post("/agent-jobs/{job_id}/apply")
def apply_agent_job(job_id:str,body:AgentJobApplyIn,x_session_token:str|None=Header(default=None,alias="X-Session-Token")):
    _require_agent_job_capability(x_session_token,guard(agent_job_service.get,job_id),"domain.write")
    return guard(agent_job_service.apply,job_id,body.applied_by)
@router.post("/workspaces",status_code=201)
def create_workspace(body:WorkspaceIn):
    raise HTTPException(410,{"code":"LEGACY_WORKSPACE_MUTATION_DISABLED","detail":"Use /api/collaboration/admin/workspaces with a trusted session"})
@router.get("/workspaces")
def list_workspaces():return collaboration_scope_service.list_workspaces()
@router.post("/workspaces/{workspace_id}/projects/{project_id}/storylines",status_code=201)
def create_storyline(workspace_id:str,project_id:str,body:StorylineIn):
    from .collaboration import Storyline
    try:
        if collaboration_scope_service.repository.project_workspace(project_id) is None:collaboration_scope_service.link_project(workspace_id,project_id)
        return collaboration_scope_service.create_storyline(Storyline(body.id,workspace_id,project_id,body.name,body.description))
    except (KeyError,FileNotFoundError):raise HTTPException(404,"Scope dependency not found")
    except ValueError as exc:raise HTTPException(400,str(exc))
@router.get("/workspaces/{workspace_id}/projects/{project_id}/storylines")
def list_storylines(workspace_id:str,project_id:str):
    try:return collaboration_scope_service.list_storylines(workspace_id,project_id)
    except (KeyError,FileNotFoundError):raise HTTPException(404,"Scope dependency not found")
    except ValueError as exc:raise HTTPException(400,str(exc))
@router.post("/workspaces/{workspace_id}/projects/{project_id}/storylines/{storyline_id}/branches",status_code=201)
def create_branch(workspace_id:str,project_id:str,storyline_id:str,body:BranchIn):
    from .collaboration import Branch
    try:return collaboration_scope_service.create_branch(Branch(body.id,workspace_id,project_id,storyline_id,body.name,body.parent_branch_id))
    except KeyError:raise HTTPException(404,"Scope dependency not found")
    except ValueError as exc:raise HTTPException(400,str(exc))
@router.get("/workspaces/{workspace_id}/projects/{project_id}/storylines/{storyline_id}/branches")
def list_branches(workspace_id:str,project_id:str,storyline_id:str):
    try:return collaboration_scope_service.list_branches(workspace_id,project_id,storyline_id)
    except KeyError:raise HTTPException(404,"Scope dependency not found")
    except ValueError as exc:raise HTTPException(400,str(exc))
@router.get("/workspaces/{workspace_id}/projects/{project_id}/storylines/{storyline_id}/branches/{branch_id}")
def get_branch(workspace_id:str,project_id:str,storyline_id:str,branch_id:str):
    from .collaboration import CollaborationScope
    try:
        scope=CollaborationScope(workspace_id,project_id,storyline_id,branch_id);collaboration_scope_service.validate_scope(scope);return collaboration_scope_service.repository.get("branches",branch_id)
    except KeyError:raise HTTPException(404,"Branch not found")
    except ValueError as exc:raise HTTPException(400,str(exc))
def _revision_error(exc):
    return HTTPException(409,{"error":"STALE_REVISION","expected_revision":exc.expected_revision,"current_revision":exc.current_revision})
@router.post("/workspaces/{workspace_id}/projects/{project_id}/storylines/{storyline_id}/branches/{branch_id}/narrative/mysteries/{item_id}/transition")
def scoped_mystery_transition(workspace_id:str,project_id:str,storyline_id:str,branch_id:str,item_id:str,body:RevisionStatusIn):
    from .collaboration import CollaborationScope,RevisionConflict
    from .services.narrative_state_service import NarrativeStateService
    scope=CollaborationScope(workspace_id,project_id,storyline_id,branch_id)
    try:
        repository=collaboration_scope_service.scoped_narrative(scope,narrative_state_service.repository).with_revision(body.expected_revision,True);service=NarrativeStateService(repository,narrative_state_service.chapters,narrative_state_service.novels,narrative_state_service.lore);result=service.transition_mystery(project_id,item_id,body.status,body.chapter_version_id);return {"result":result,"current_revision":collaboration_scope_service.get_branch_revision(scope).revision}
    except RevisionConflict as exc:raise _revision_error(exc)
    except KeyError:raise HTTPException(404,"Scoped narrative dependency not found")
    except ValueError as exc:raise HTTPException(400,str(exc))
@router.post("/workspaces/{workspace_id}/projects/{project_id}/storylines/{storyline_id}/branches/{branch_id}/narrative/proposals/{proposal_id}/accept")
def scoped_proposal_accept(workspace_id:str,project_id:str,storyline_id:str,branch_id:str,proposal_id:str,body:RevisionWriteIn):
    from .collaboration import CollaborationScope,RevisionConflict
    from .services.narrative_state_service import NarrativeStateService
    from .services.narrative_proposal_service import NarrativeProposalService
    scope=CollaborationScope(workspace_id,project_id,storyline_id,branch_id)
    try:
        repository=collaboration_scope_service.scoped_narrative(scope,narrative_state_service.repository).with_revision(body.expected_revision,True);state=NarrativeStateService(repository,narrative_state_service.chapters,narrative_state_service.novels,narrative_state_service.lore);result=NarrativeProposalService(repository,state).accept_proposal(project_id,proposal_id);return {"result":result,"current_revision":collaboration_scope_service.get_branch_revision(scope).revision}
    except RevisionConflict as exc:raise _revision_error(exc)
    except KeyError:raise HTTPException(404,"Scoped proposal not found")
    except (FileNotFoundError,ValueError) as exc:raise HTTPException(400,str(exc))
@router.get("/providers")
def providers(): return runtime.provider_status()
@router.get("/asset-providers")
def asset_providers():
    from .dependencies import asset_provider_registry
    saved = load_asset_provider_config()
    provider_ids = list(dict.fromkeys([*IMAGE_PROVIDER_CATALOG, *saved]))
    items = []
    for pid in provider_ids:
        catalog=IMAGE_PROVIDER_CATALOG.get(pid,{})
        cfg = saved.get(pid) or {}
        effective={**catalog,**cfg};local=bool(effective.get("local"));requires_credential=bool(effective.get("requires_credential",True));enabled=bool(effective.get("enabled",True))
        endpoint = effective.get("endpoint", "");model = effective.get("default_model", "")
        credential_configured=not requires_credential or (credential_vault.supports_provider(pid) and credential_vault.has(pid))
        configured=bool(enabled and endpoint and credential_configured and (not local or bool(cfg)));registered=pid in asset_provider_registry._providers
        adapter=asset_provider_registry._providers.get(pid);probe=getattr(adapter,'health_check',None);reachable=bool(registered and callable(probe) and probe())
        items.append({"provider_id":pid,"display_name":effective.get("display_name") or pid,"endpoint":endpoint,"default_model":model,"api_style":effective.get("api_style","openai"),"local":local,"enabled":enabled,"requires_credential":requires_credential,"credential_configured":credential_configured,"configured":configured,"registered":registered,"reachable":reachable,"secret":None})
    items.sort(key=lambda item:(not item["local"],not item["reachable"],item["display_name"]))
    return {"items":items,"routing_policy":"LOCAL_FIRST"}

@router.put("/asset-providers/{provider_id}")
def asset_provider_config_set(provider_id: str, body: AssetProviderConfigIn):
    try:
        result = save_asset_provider_config(provider_id, body.endpoint, body.default_model,api_style=body.api_style,local=body.local,enabled=body.enabled,requires_credential=body.requires_credential,display_name=body.display_name)
        provider_support_registry.replace_source("asset", load_asset_provider_config())
        return {"provider_id": provider_id, **body.model_dump(), **result, "registered": refresh_asset_provider(provider_id)}
    except ValueError as exc:
        raise HTTPException(400, {"code": "INVALID_PROVIDER_CONFIG", "message": str(exc)}) from exc

@router.delete("/asset-providers/{provider_id}")
def asset_provider_config_delete(provider_id: str):
    if provider_id in DEFAULT_IMAGE_ENDPOINTS:
        raise HTTPException(400, {"code": "DEFAULT_PROVIDER_CANNOT_BE_DELETED"})
    from .dependencies import asset_provider_registry
    asset_provider_registry.unregister(provider_id)
    if credential_vault.supports_provider(provider_id) and provider_id in load_asset_provider_config() and not provider_support_registry.supports_after_removing("asset", provider_id):
        try: credential_vault.clear(provider_id)
        except VaultUnavailableError as exc: raise HTTPException(503,{"code":exc.code,"message":"系统凭据库不可用"}) from exc
    deleted = delete_asset_provider_config(provider_id)
    if deleted: provider_support_registry.remove("asset", provider_id)
    return {"provider_id": provider_id, "deleted": deleted}
def _credential_guard(provider: str, session_token: str | None):
    if not credential_vault.supports_provider(provider):
        raise HTTPException(400, {"code": "UNSUPPORTED_PROVIDER", "message": "不支持的服务商"})
    if settings.enable_packaged_runtime:
        if not session_token: raise HTTPException(401, {"code": "SESSION_REQUIRED"})
        try: trusted_session_resolver.resolve(session_token)
        except KeyError as exc: raise HTTPException(401, {"code": "SESSION_INVALID"}) from exc
    elif settings.enable_collaboration_runtime:
        if not session_token: raise HTTPException(401, {"code": "SESSION_REQUIRED"})
        try: trusted_session_resolver.resolve(session_token)
        except KeyError as exc: raise HTTPException(401, {"code": "SESSION_INVALID"}) from exc

@router.get("/credentials/{provider}")
def credential_status(provider: str, x_session_token: str | None = Header(None)):
    _credential_guard(provider, x_session_token)
    try:return credential_vault.status(provider)
    except VaultUnavailableError as exc:raise HTTPException(503,{"code":exc.code,"message":"系统凭据库不可用"}) from exc

@router.put("/credentials/{provider}")
def credential_set(provider: str, body: CredentialIn, x_session_token: str | None = Header(None)):
    _credential_guard(provider, x_session_token)
    if body.provider != provider: raise HTTPException(400, {"code": "PROVIDER_MISMATCH"})
    try: credential_vault.set(provider, body.credential)
    except ValueError as exc: raise HTTPException(400, {"code": "INVALID_CREDENTIAL"}) from exc
    except VaultUnavailableError as exc: raise HTTPException(503,{"code":exc.code,"message":"系统凭据库不可用"}) from exc
    refresh_asset_provider(provider)
    if provider == "openai": refresh_asset_provider("custom")
    return credential_vault.status(provider)

@router.delete("/credentials/{provider}")
def credential_delete(provider: str, x_session_token: str | None = Header(None)):
    _credential_guard(provider, x_session_token)
    try:credential_vault.clear(provider)
    except VaultUnavailableError as exc:raise HTTPException(503,{"code":exc.code,"message":"系统凭据库不可用"}) from exc
    refresh_asset_provider(provider)
    if provider == "openai": refresh_asset_provider("custom")
    return credential_vault.status(provider)

@router.post("/credentials/{provider}/test")
def credential_test(provider: str, x_session_token: str | None = Header(None)):
    _credential_guard(provider, x_session_token)
    if not credential_vault.has(provider): return {"provider": provider, "configured": False, "reachable": False}
    configured = bool(credential_vault.resolve(provider))
    if not configured:
        return {"provider": provider, "configured": False, "reachable": False}
    transport = runtime.providers.get(provider)
    probe = getattr(transport, "probe", None)
    if probe is None:
        return {"provider": provider, "configured": True, "reachable": True, "verified": False}
    return {"provider": provider, **probe(), "verified": True}
@router.get("/models")
def models(): return runtime.models()
@router.get("/novels")
def novels(): return novel_service.list()
@router.post("/novels",status_code=201)
def create_novel(body:NovelIn): return guard(novel_service.create,body.model_dump(exclude_none=True))
@router.get("/novels/{nid}")
def get_novel(nid:str): return guard(novel_service.get,nid)
@router.put("/novels/{nid}")
def update_novel(nid:str,body:NovelUpdate): return guard(novel_service.update,nid,body.model_dump(exclude_none=True))
@router.delete("/novels/{nid}",status_code=204)
def delete_novel(nid:str,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    if settings.enable_collaboration_runtime:
        _authorize_novel_project(nid,x_session_token,"domain.write")
    guard(novel_service.delete,nid)
@router.get("/novels/{nid}/chapters")
def chapters(nid:str): return guard(chapter_service.list,nid)
@router.get("/novels/{nid}/chapters/archived")
def archived_chapters(nid:str): return guard(chapter_service.list_archived,nid)
@router.post("/novels/{nid}/chapters",status_code=201)
def create_chapter(nid:str,body:ChapterIn):
    if settings.enable_collaboration_runtime:_collaboration_unavailable()
    return guard(chapter_service.create,nid,body.model_dump(exclude_none=True))
@router.get("/chapters/{chapter_id}")
def chapter(chapter_id:str,x_session_token:str|None=Header(None),x_branch_id:str|None=Header(None)):
    if settings.enable_collaboration_runtime:
        actor,scope,_=_collaboration_context(chapter_id,x_session_token,x_branch_id)
        try:membership_authorization_service.require(actor,"domain.read",ModalityDomain.NOVEL,scope)
        except PermissionError as exc:raise HTTPException(403,{"code":"FORBIDDEN","detail":str(exc)})
    return guard(chapter_service.get,chapter_id)
@router.put("/chapters/{chapter_id}")
def update_chapter(chapter_id:str,body:ChapterUpdate,x_session_token:str|None=Header(None),x_branch_id:str|None=Header(None)):
    try:
        if settings.enable_collaboration_runtime:
            if body.version is None:raise HTTPException(428,{"code":"EXPECTED_VERSION_REQUIRED"})
            actor,scope,current=_collaboration_context(chapter_id,x_session_token,x_branch_id)
            document=body.document or markdown_to_document(body.content if body.content is not None else current["content"])
            reason=body.source if body.source in {"MANUAL_SAVE","AI_ACCEPT","RESTORE","CHAPTER_SWITCH","EXPLICIT_CHECKPOINT"} else "MANUAL_SAVE"
            return collaboration_application_service.update_chapter(actor=actor,scope=scope,chapter_id=chapter_id,document=document,expected_version=body.version,reason=reason)
        return chapter_service.save(chapter_id,body.model_dump(exclude_none=True))
    except PermissionError as exc:raise HTTPException(403,{"code":"FORBIDDEN","detail":str(exc)})
    except VersionConflict as exc: raise HTTPException(409,{"code":"VERSION_CONFLICT","server":exc.current,"conflict":exc.as_dict()})
@router.post("/chapters/{chapter_id}/archive")
def archive_chapter(chapter_id:str,expected_version:int|None=None,x_session_token:str|None=Header(None),x_branch_id:str|None=Header(None)):
    try:
        if settings.enable_collaboration_runtime:
            if expected_version is None: raise HTTPException(428,{"code":"EXPECTED_VERSION_REQUIRED"})
            actor,scope,_=_collaboration_context(chapter_id,x_session_token,x_branch_id)
            return collaboration_application_service.set_chapter_archived(actor=actor,scope=scope,chapter_id=chapter_id,expected_version=expected_version,archived=True)
        return chapter_service.archive(chapter_id,expected_version)
    except PermissionError as exc: raise HTTPException(403,{"code":"FORBIDDEN","detail":"Chapter archive is not authorized"})
    except VersionConflict as exc: raise HTTPException(409,{"code":"VERSION_CONFLICT","conflict":exc.as_dict()})
    except VersionConflict as exc: raise HTTPException(409,{"code":"VERSION_CONFLICT","conflict":exc.as_dict()})
@router.post("/chapters/{chapter_id}/restore-archive")
def restore_archived_chapter(chapter_id:str,expected_version:int|None=None,x_session_token:str|None=Header(None),x_branch_id:str|None=Header(None)):
    try:
        if settings.enable_collaboration_runtime:
            if expected_version is None: raise HTTPException(428,{"code":"EXPECTED_VERSION_REQUIRED"})
            actor,scope,_=_collaboration_context(chapter_id,x_session_token,x_branch_id)
            return collaboration_application_service.set_chapter_archived(actor=actor,scope=scope,chapter_id=chapter_id,expected_version=expected_version,archived=False)
        return chapter_service.restore_archive(chapter_id,expected_version)
    except PermissionError as exc: raise HTTPException(403,{"code":"FORBIDDEN","detail":"Chapter restore is not authorized"})
    except VersionConflict as exc: raise HTTPException(409,{"code":"VERSION_CONFLICT","conflict":exc.as_dict()})
    except VersionConflict as exc: raise HTTPException(409,{"code":"VERSION_CONFLICT","conflict":exc.as_dict()})
@router.delete("/chapters/{chapter_id}",status_code=204)
def delete_chapter(chapter_id:str,x_session_token:str|None=Header(None),x_branch_id:str|None=Header(None)):
    if settings.enable_collaboration_runtime:
        actor,scope,current=_collaboration_context(chapter_id,x_session_token,x_branch_id)
        try: membership_authorization_service.require(actor,"domain.write",ModalityDomain.NOVEL,scope)
        except PermissionError as exc: raise HTTPException(403,{"code":"FORBIDDEN","detail":str(exc)})
        if not current.get("is_archived"):
            raise HTTPException(409,{"code":"CHAPTER_ARCHIVE_REQUIRED","message":"永久删除前必须先归档章节。"})
    return guard(chapter_service.delete,chapter_id)
@router.post("/chapters/{chapter_id}/duplicate",status_code=201)
def duplicate_chapter(chapter_id:str):
    if settings.enable_collaboration_runtime:_collaboration_unavailable()
    return guard(chapter_service.duplicate,chapter_id)
@router.post("/chapters/{chapter_id}/rename")
def rename_chapter(chapter_id:str,body:RenameIn,x_session_token:str|None=Header(None),x_branch_id:str|None=Header(None)):
    if settings.enable_collaboration_runtime:
        actor,scope,current=_collaboration_context(chapter_id,x_session_token,x_branch_id)
        document=dict(current["document"]);nodes=list(document.get("content",[]));heading={"type":"heading","attrs":{"level":1},"content":[{"type":"text","text":body.title}]}
        if nodes and nodes[0].get("type")=="heading":nodes[0]=heading
        else:nodes.insert(0,heading)
        document["content"]=nodes
        try:return collaboration_application_service.update_chapter(actor=actor,scope=scope,chapter_id=chapter_id,document=document,expected_version=body.version)
        except PermissionError as exc:raise HTTPException(403,{"code":"FORBIDDEN","detail":str(exc)})
    return guard(chapter_service.rename,chapter_id,body.title,body.version)
@router.post("/chapters/{chapter_id}/move")
def move_chapter(chapter_id:str,body:MoveIn):
    if settings.enable_collaboration_runtime:_collaboration_unavailable()
    if body.direction not in {"up","down"}:raise HTTPException(400,"direction must be up or down")
    return {"order":guard(chapter_service.move,chapter_id,body.direction)}
@router.get("/chapters/{chapter_id}/history")
def chapter_history(chapter_id:str,x_session_token:str|None=Header(None),x_branch_id:str|None=Header(None)):
    if settings.enable_collaboration_runtime:
        actor,scope,_=_collaboration_context(chapter_id,x_session_token,x_branch_id)
        try:membership_authorization_service.require(actor,"domain.read",ModalityDomain.NOVEL,scope)
        except PermissionError as exc:raise HTTPException(403,{"code":"FORBIDDEN","detail":str(exc)})
    return guard(chapter_service.history,chapter_id)
@router.post("/chapters/{chapter_id}/history/{version}/restore")
def restore_chapter(chapter_id:str,version:int,expected_version:int,x_session_token:str|None=Header(None),x_branch_id:str|None=Header(None)):
    if settings.enable_collaboration_runtime:
        actor,scope,_=_collaboration_context(chapter_id,x_session_token,x_branch_id)
        item=next((x for x in chapter_service.history(chapter_id) if x["version"]==version),None)
        if item is None:raise HTTPException(404,"Revision not found")
        try:return collaboration_application_service.update_chapter(actor=actor,scope=scope,chapter_id=chapter_id,document=item["document"],expected_version=expected_version,reason="RESTORE")
        except PermissionError as exc:raise HTTPException(403,{"code":"FORBIDDEN","detail":str(exc)})
    return guard(chapter_service.restore,chapter_id,version,expected_version)
for resource in ("characters","locations","canon","foreshadowing","timeline","relationships","volumes","scenes","story_routes"):
    router.add_api_route(f"/novels/{{nid}}/{resource}",lambda nid,r=resource:guard(novel_service.data_set,nid,r),methods=["GET"],name=f"get_{resource}")
@router.put("/novels/{nid}/characters/{character_id}")
def upsert_character(nid:str,character_id:str,body:CharacterIn):return guard(novel_service.upsert_character,nid,character_id,body.model_dump())
@router.put("/novels/{nid}/locations/{location_id}")
def upsert_location(nid:str,location_id:str,body:LocationIn):return guard(novel_service.upsert_location,nid,location_id,body.model_dump())
@router.put("/novels/{nid}/timeline/{event_id}")
def upsert_timeline_event(nid:str,event_id:str,body:TimelineEventIn):return guard(novel_service.upsert_timeline_event,nid,event_id,body.model_dump())
@router.put("/novels/{nid}/foreshadowing/{foreshadowing_id}")
def upsert_foreshadowing(nid:str,foreshadowing_id:str,body:ForeshadowingIn):return guard(novel_service.upsert_foreshadowing,nid,foreshadowing_id,body.model_dump())
@router.get("/novels/{nid}/foreshadowing/reminders")
def foreshadowing_reminders(nid: str, chapter: int = Query(default=1, ge=1)):
    rows = guard(novel_service.data_set, nid, "foreshadowing")
    return summarize_foreshadowing(rows, chapter)
@router.put("/novels/{nid}/relationships/{relationship_id}")
def upsert_relationship(nid:str,relationship_id:str,body:RelationshipIn):return guard(novel_service.upsert_relationship,nid,relationship_id,body.model_dump())
@router.get("/novels/{nid}/outline")
def get_outline(nid:str):return guard(novel_service.outline,nid)
@router.put("/novels/{nid}/outline")
def update_outline(nid:str,body:OutlineIn):return guard(novel_service.update_outline,nid,body.model_dump())
@router.put("/novels/{nid}/volumes/{volume_id}")
def upsert_volume(nid:str,volume_id:str,body:VolumeIn):return guard(novel_service.upsert_volume,nid,volume_id,body.model_dump())
@router.put("/novels/{nid}/scenes/{scene_id}")
def upsert_scene(nid:str,scene_id:str,body:SceneIn):return guard(novel_service.upsert_scene,nid,scene_id,body.model_dump())
@router.put("/novels/{nid}/story-routes/{route_id}")
def upsert_story_route(nid:str,route_id:str,body:StoryRouteIn):return guard(novel_service.upsert_story_route,nid,route_id,body.model_dump())
@router.get("/novels/{nid}/story-routes")
def story_routes(nid:str):return guard(novel_service.data_set,nid,"story_routes")
@router.get("/novels/{nid}/secrets")
def secrets(nid:str): return guard(novel_service.public_secrets,nid)
@router.post("/generate/{operation}",status_code=202)
def generate(operation:str,body:GenerateIn,x_session_token:str|None=Header(None),x_branch_id:str|None=Header(None),idempotency_key:str|None=Header(None,alias="Idempotency-Key")):
    if operation not in {"continue","rewrite","polish","brainstorm","review"}: raise HTTPException(404,"Unknown generation operation")
    if idempotency_key:
        with _idempotency_execution_lock:
            cached=_cached_idempotent(idempotency_key,f"generate:{operation}")
            if cached:return cached
            result=_generate_once(operation,body,x_session_token,x_branch_id)
            return _store_idempotent(idempotency_key,f"generate:{operation}",result)
    return _generate_once(operation,body,x_session_token,x_branch_id)
def _generate_once(operation,body,x_session_token,x_branch_id):
    if settings.enable_collaboration_runtime:
        actor,scope,_=_collaboration_context(body.chapter_id,x_session_token,x_branch_id);membership_authorization_service.require(actor,"domain.read",ModalityDomain.NOVEL,scope);job=jobs.create(operation,body.model_dump(),actor=actor,scope=scope)
    else:job=jobs.create(operation,body.model_dump())
    return {"job_id":job.id,"status":job.status,"events_url":f"/api/generation/{job.id}/events","base_chapter_version":job.base_chapter_version}
@router.post("/generate/{operation}/variants",status_code=202)
def generate_variants(operation:str,body:GenerateVariantsIn,x_session_token:str|None=Header(None),x_branch_id:str|None=Header(None)):
    if operation not in {"continue","rewrite","polish","brainstorm"}: raise HTTPException(404,"Unknown generation operation")
    payload=body.model_dump(exclude={"count"});created=[];group_id=str(uuid.uuid4())
    actor=scope=None
    if settings.enable_collaboration_runtime:
        actor,scope,_=_collaboration_context(body.chapter_id,x_session_token,x_branch_id);membership_authorization_service.require(actor,"domain.read",ModalityDomain.NOVEL,scope)
    for index in range(body.count):
        item=dict(payload);item["variant_group_id"]=group_id;item["variant_index"]=index+1;item["instruction"]=(body.instruction+f"\n候选方案 {index+1}：请提供与其他候选明显不同但同样符合要求的方向。").strip()
        job=jobs.create(operation,item,actor=actor,scope=scope)
        created.append({"job_id":job.id,"status":job.status,"events_url":f"/api/generation/{job.id}/events","base_chapter_version":job.base_chapter_version,"variant_index":index+1})
    return {"operation":operation,"group_id":group_id,"count":len(created),"variants":created}
@router.get("/generation-groups/{group_id}")
def generation_group(group_id:str,x_session_token:str|None=Header(None)):
    variants=jobs.variants(group_id)
    if not variants: raise HTTPException(404,"Generation variant group not found")
    return {"group_id":group_id,"count":len(variants),"variants":[job.public() for job in variants]}
@router.get("/generation/{jid}")
def generation(jid:str,x_session_token:str|None=Header(None)):
    if settings.enable_collaboration_runtime:_generation_context(jid,x_session_token)
    job=guard(jobs.get,jid); return {**job.public(),"diff":jobs.diff(jid) if job.output else ""}
@router.get("/generation/{jid}/events")
def events(jid:str,x_session_token:str|None=Header(None)):
    if settings.enable_collaboration_runtime:_generation_context(jid,x_session_token)
    guard(jobs.get,jid); return StreamingResponse(jobs.events(jid),media_type="text/event-stream",headers={"Cache-Control":"no-cache"})
@router.post("/generation/{jid}/cancel")
def cancel(jid:str,x_session_token:str|None=Header(None)):
    if settings.enable_collaboration_runtime:_generation_context(jid,x_session_token)
    return guard(jobs.cancel,jid).public()
@router.post("/generation/{jid}/retry",status_code=202)
def retry_generation(jid:str,x_session_token:str|None=Header(None)):
    actor=scope=None
    if settings.enable_collaboration_runtime:
        actor,scope,job=_generation_context(jid,x_session_token)
    else:job=guard(jobs.get,jid)
    if job.status not in {"FAILED","CANCELLED"}:raise HTTPException(409,{"code":"GENERATION_NOT_RETRYABLE","status":job.status})
    payload={
        "novel_id":job.novel_id,"chapter_id":job.chapter_id,"instruction":job.instruction,
        "profile":job.profile,"provider_id":job.requested_provider,"model_id":job.requested_model,
        "source":job.source,"selected_text":job.source,"style":getattr(job,"style",""),
    }
    retried=guard(jobs.create,job.operation,payload,actor,scope)
    return {"job_id":retried.id,"status":retried.status,"events_url":f"/api/generation/{retried.id}/events","base_chapter_version":retried.base_chapter_version,"retry_of":jid}
@router.post("/generation/{jid}/accept")
def accept(jid:str,body:AcceptIn|None=None,x_session_token:str|None=Header(None)):
    if settings.enable_collaboration_runtime:
        actor,scope,job=_generation_context(jid,x_session_token)
        if body is None or body.expected_version is None:raise HTTPException(428,{"code":"EXPECTED_VERSION_REQUIRED"})
        if job.base_chapter_version is None or body.expected_version!=job.base_chapter_version:
            raise HTTPException(409,{"code":"GENERATION_BASE_VERSION_MISMATCH","generation_version":job.base_chapter_version,"expected_version":body.expected_version})
        return guard(jobs.accept,jid,body.content,actor,scope,body.expected_version)
    return guard(jobs.accept,jid,body.content if body else None)
@router.post("/generation/{jid}/reject")
def reject(jid:str,x_session_token:str|None=Header(None)):
    if settings.enable_collaboration_runtime:_generation_context(jid,x_session_token)
    return guard(jobs.reject,jid).public()
@router.get("/context-preview")
def context_preview(novel_id:str,chapter:int,instruction:str="",target:str="cloud"):
    ctx=guard(context_service.build,novel_id,chapter,instruction,target=="cloud"); return {**ctx,"token_estimate":len(json.dumps(ctx,ensure_ascii=False))//3,"secrets_policy":"Secrets excluded/redacted" if target=="cloud" else "Local-only context"}
@router.get("/pending-canon")
def pending(novel_id:str):
    return guard(canon_service.list_pending,novel_id)
@router.post("/pending-canon/{pid}/approve")
def approve(pid:str,body:PendingEditIn|None=None):
    return guard(canon_service.approve,pid,body.proposals if body else None)
@router.post("/pending-canon/{pid}/reject")
def reject_pending(pid:str): return guard(canon_service.reject,pid)
@router.get("/novels/{nid}/export")
def export_novel(nid:str,format:str="json"):
    return guard(novel_service.export,nid,format)

def _authorize_novel_project(
    novel_id: str,
    session_token: str | None,
    permission: str,
    *,
    branch_id: str | None = None,
    conceal: bool = False,
):
    if not session_token:
        raise HTTPException(401, {"code": "SESSION_REQUIRED"})
    try:
        actor = trusted_session_resolver.resolve(session_token)
    except KeyError:
        raise HTTPException(401, {"code": "INVALID_SESSION"})
    try:
        workspace_id = collaboration_scope_service.repository.project_workspace(novel_id)
        if not workspace_id or actor.workspace_id != workspace_id:
            raise PermissionError("project is outside the actor workspace")
        if branch_id:
            branch = collaboration_scope_service.repository.get("branches", branch_id)
            if branch.get("workspace_id") != workspace_id or branch.get("project_id") != novel_id:
                raise PermissionError("project branch does not contain the project")
            scope = AuthorizationScope(
                ScopeKind.BRANCH,
                workspace_id,
                novel_id,
                branch.get("storyline_id"),
                branch_id,
            )
        else:
            scope = AuthorizationScope(ScopeKind.PROJECT, workspace_id, novel_id)
        collaboration_scope_service.validate_scope(scope)
        membership_authorization_service.require(actor, permission, ModalityDomain.NOVEL, scope)
        return actor, scope
    except (KeyError, ValueError, PermissionError) as exc:
        if conceal:
            raise HTTPException(404, "export job not found") from exc
        raise HTTPException(403, {"code": "PROJECT_SCOPE_FORBIDDEN"}) from exc

def _authorize_export_project(
    novel_id: str,
    branch_id: str | None,
    session_token: str | None,
    permission: str,
    *,
    conceal: bool = False,
):
    try:
        return _authorize_novel_project(novel_id,session_token,permission,branch_id=branch_id,conceal=conceal)
    except HTTPException as exc:
        if exc.status_code == 403 and isinstance(exc.detail,dict) and exc.detail.get("code") == "PROJECT_SCOPE_FORBIDDEN":
            raise HTTPException(403,{"code":"EXPORT_SCOPE_FORBIDDEN"}) from exc
        raise

@router.post("/exports", status_code=202)
def create_export(
    body:ExportCreateIn,
    novel_id:str,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    branch_id: str | None = Query(default=None),
    x_branch_id: str | None = Header(default=None, alias="X-Branch-Id"),
    x_session_token: str | None = Header(default=None, alias="X-Session-Token"),
):
    try:
        requested_branch = branch_id or x_branch_id
        permission_context = {"mode": "local", "novel_id": novel_id}
        if settings.enable_collaboration_runtime:
            actor, scope = _authorize_export_project(
                novel_id, requested_branch, x_session_token, "domain.read"
            )
            permission_context = {
                "mode": "collaboration",
                "novel_id": novel_id,
                "branch_id": requested_branch,
                "workspace_id": scope.workspace_id,
                "storyline_id": scope.storyline_id,
                "actor_id": actor.actor_id,
                "permission": "domain.read",
            }
        elif requested_branch:
            actor, scope = _adaptation_context(novel_id, requested_branch, x_session_token, "domain.read")
            permission_context = {
                "mode": "collaboration",
                "novel_id": novel_id,
                "branch_id": requested_branch,
                "workspace_id": scope.workspace_id,
                "storyline_id": scope.storyline_id,
                "actor_id": actor.actor_id,
                "permission": "domain.read",
            }
        novel_service.get(novel_id)
        create_export_job = export_job_service.create
        try:
            parameters = inspect.signature(create_export_job).parameters
        except (TypeError, ValueError):
            parameters = {}
        if "permission_context" in parameters or any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()
        ):
            return create_export_job(novel_id, body.format, idempotency_key, permission_context=permission_context)
        return create_export_job(novel_id, body.format, idempotency_key)
    except FileNotFoundError: raise HTTPException(404, "novel not found")
    except ValueError as exc: raise HTTPException(400, str(exc))

def _authorize_export_job(
    job_id: str,
    session_token: str | None,
    permission: str,
):
    """Authorize an export record against its persisted project scope."""
    if not settings.enable_collaboration_runtime:
        return None
    try:
        job = export_job_service.get(job_id)
    except (FileNotFoundError, ExportJobResultInvalid):
        raise HTTPException(404, "export job not found")
    permission_context = job.get("permission_context")
    branch_id = permission_context.get("branch_id") if isinstance(permission_context, dict) else None
    _authorize_export_project(
        str(job.get("novel_id") or ""),
        branch_id,
        session_token,
        permission,
        conceal=True,
    )
    return job

@router.post("/exports/{job_id}/cancel")
def cancel_export(
    job_id: str,
    x_session_token: str | None = Header(default=None, alias="X-Session-Token"),
):
    """Cancel a queued/running export without exposing provider credentials."""
    try:
        _authorize_export_job(job_id, x_session_token, "domain.write")
        return export_job_service.cancel(job_id)
    except FileNotFoundError:
        raise HTTPException(404, "export job not found")
    except ExportJobNotCancellable as exc:
        raise HTTPException(
            409,
            {
                "code": "EXPORT_NOT_CANCELLABLE",
                "message": "export is no longer cancellable",
                "details": {"status": exc.status},
            },
        )

@router.post("/exports/{job_id}/retry", status_code=202)
def retry_export(
    job_id: str,
    x_session_token: str | None = Header(default=None, alias="X-Session-Token"),
):
    """Start a new attempt for a failed/cancelled export."""
    try:
        _authorize_export_job(job_id, x_session_token, "domain.write")
        return export_job_service.retry(job_id)
    except FileNotFoundError:
        raise HTTPException(404, "export job not found")
    except ExportJobNotRetryable as exc:
        raise HTTPException(
            409,
            {
                "code": "EXPORT_NOT_RETRYABLE",
                "message": "export is not retryable",
                "details": {"status": exc.status},
            },
        )

def _export_content_disposition(filename: str) -> str:
    """Build an RFC 6266 attachment header without exposing raw user data."""
    filename = str(filename or "export")
    ascii_name = filename.encode("ascii", "ignore").decode("ascii")
    ascii_name = re.sub(r"[^A-Za-z0-9._-]", "_", ascii_name).strip()
    if not re.search(r"[A-Za-z0-9]", ascii_name):
        ascii_name = "export"
    elif ascii_name.startswith("."):
        # Keep a useful extension when the original name contains only
        # non-ASCII characters before its suffix (for example, ``章节.md``).
        ascii_name = f"export{ascii_name}"
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename, safe='')}"

@router.get("/exports/{job_id}/download")
def download_export(
    job_id:str,
    x_session_token: str | None = Header(default=None, alias="X-Session-Token"),
):
    try:
        _authorize_export_job(job_id, x_session_token, "domain.read")
        payload = export_job_service.download(job_id)
        return Response(
            content=payload["content"],
            media_type=payload["media_type"],
            headers={"Content-Disposition": _export_content_disposition(payload["filename"])},
        )
    except FileNotFoundError:
        raise HTTPException(404, "export job not found")
    except ExportJobUnavailable as exc:
        raise HTTPException(
            409,
            {
                "code": "EXPORT_NOT_READY",
                "message": "export is not ready",
                "details": {"status": exc.status},
            },
        )
    except ExportJobResultInvalid:
        # Do not echo persisted result data; it may contain provider output or
        # implementation details that are not part of the public API contract.
        raise HTTPException(
            500,
            {
                "code": "EXPORT_RESULT_INVALID",
                "message": "export result is unavailable",
            },
        )

@router.get("/exports/{job_id}")
def get_export(
    job_id:str,
    x_session_token: str | None = Header(default=None, alias="X-Session-Token"),
):
    try:
        authorized_job = _authorize_export_job(job_id, x_session_token, "domain.read")
        return authorized_job if authorized_job is not None else export_job_service.get(job_id)
    except FileNotFoundError: raise HTTPException(404, "export job not found")
@router.post("/novels/{nid}/assets")
def upload_asset(nid:str, body:AssetUploadIn, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    if body.novel_id != nid: raise HTTPException(400, "novel_id does not match path")
    try:
        asset=asset_library_service.create(nid, body.filename, body.content_base64, body.media_type, body.kind, idempotency_key)
        if body.character_id or body.scene_id:
            asset.update({"character_id":body.character_id,"scene_id":body.scene_id})
            from .repository import atomic_write
            atomic_write(asset_library_service._meta_path(asset["id"]), __import__('json').dumps(asset,ensure_ascii=False,indent=2))
        return asset
    except ValueError as exc: raise HTTPException(400, str(exc))
@router.get("/novels/{nid}/assets")
def list_assets(nid:str,kind:str|None=None,character_id:str|None=None,scene_id:str|None=None):
    items=asset_library_service.list(nid)
    return [item for item in items if (not kind or item.get('kind')==kind) and (not character_id or item.get('character_id')==character_id) and (not scene_id or item.get('scene_id')==scene_id)]
def _scoped_asset(asset_id:str,novel_id:str):
    asset=asset_library_service.get(asset_id)
    if not hmac.compare_digest(str(asset.get('novel_id') or ''),str(novel_id)):
        raise FileNotFoundError(asset_id)
    return asset
def _authorize_asset_project(novel_id:str,session_token:str|None,branch_id:str|None,permission:str):
    if not settings.enable_collaboration_runtime:return
    if not branch_id:raise HTTPException(400,{"code":"BRANCH_SCOPE_REQUIRED"})
    _adaptation_context(novel_id,branch_id,session_token,permission)
@router.get("/assets/{asset_id}")
def get_asset(asset_id:str,novel_id:str=Query(min_length=1),x_session_token:str|None=Header(None),x_branch_id:str|None=Header(None)):
    try: _authorize_asset_project(novel_id,x_session_token,x_branch_id,"domain.read"); return _scoped_asset(asset_id,novel_id)
    except FileNotFoundError: raise HTTPException(404, "asset not found")
@router.get("/assets/{asset_id}/download")
def download_asset(asset_id:str,novel_id:str=Query(min_length=1),x_session_token:str|None=Header(None),x_branch_id:str|None=Header(None)):
    try:
        _authorize_asset_project(novel_id,x_session_token,x_branch_id,"domain.read");meta=_scoped_asset(asset_id,novel_id); return Response(asset_library_service.content(asset_id), media_type=meta["media_type"], headers={"Content-Disposition": _export_content_disposition(meta["filename"]), "X-Asset-SHA256": meta["sha256"]})
    except FileNotFoundError: raise HTTPException(404, "asset not found")
@router.delete("/assets/{asset_id}")
def delete_asset(asset_id:str,novel_id:str=Query(min_length=1),x_session_token:str|None=Header(None),x_branch_id:str|None=Header(None)):
    try: _authorize_asset_project(novel_id,x_session_token,x_branch_id,"domain.write");_scoped_asset(asset_id,novel_id); return asset_library_service.delete(asset_id)
    except FileNotFoundError: raise HTTPException(404, "asset not found")
@router.post("/novels/import")
def import_novel(body:ImportIn,idempotency_key:str|None=Header(None,alias="Idempotency-Key")):
    def attach_review(payload):
        if not isinstance(payload, dict) or not isinstance(payload.get("novel"), dict):
            return payload
        preview = payload.get("preview") if isinstance(payload.get("preview"), dict) else {}
        knowledge = preview.get("knowledge_base") if isinstance(preview.get("knowledge_base"), dict) else {}
        candidates = knowledge.get("candidates") if isinstance(knowledge.get("candidates"), dict) else {}
        if not any(isinstance(items, list) and items for items in candidates.values()):
            return payload
        review = import_review_service.ensure_pending(
            str(payload["novel"].get("id")),
            candidates,
            source_format=str(payload.get("plan", {}).get("format") or body.format),
            import_id=str(payload["novel"].get("id")),
        )
        return {**payload, "knowledge_review": review}

    try:
        if idempotency_key:
            with _idempotency_execution_lock:
                cached=_cached_idempotent(idempotency_key,"novel-import")
                if cached:return attach_review(cached)
                result = attach_review(novel_service.import_project(body.format,body.content,body.confirm,body.content_base64))
                return _store_idempotent(idempotency_key,"novel-import",result)
        return attach_review(novel_service.import_project(body.format,body.content,body.confirm,body.content_base64))
    except json.JSONDecodeError as exc:raise HTTPException(400,f"Invalid JSON: {exc}")
    except ValueError as exc:raise HTTPException(400,str(exc))
@router.post("/novels/{nid}/import/knowledge-base/review")
def review_import_knowledge(nid:str,body:ImportKnowledgeReviewIn):
    try:
        # Do not create an orphan review record for an unknown project.
        novel_service.get(nid)
        if body.review_id:
            review = import_review_service.get(body.review_id)
            if review.get("novel_id") != nid:
                raise HTTPException(403, {"code": "IMPORT_REVIEW_SCOPE_FORBIDDEN"})
        else:
            review = None
            pending = import_review_service.list_for_novel(nid, status="PENDING")
            # A confirmed import creates one full candidate set.  The desktop
            # review window may POST only the checked subset; attach that
            # decision to the existing pending record instead of creating a
            # second orphan review for the subset fingerprint.
            if pending:
                review = pending[0]
            else:
                review = import_review_service.ensure_pending(nid, body.candidates)
        decision = str(body.decision or "").upper().strip()
        if decision == "SKIPPED":
            record = import_review_service.decide(review["id"], "SKIPPED", note=body.note)
            return {"decision": "SKIPPED", "applied": {"characters": [], "locations": [], "timeline_events": [], "foreshadowing": []}, "review": record}
        applied = guard(novel_service.review_import_knowledge, nid, decision, body.candidates or review.get("candidates", {}))
        record = import_review_service.decide(
            review["id"],
            decision,
            selected=body.candidates or review.get("candidates", {}),
            applied=applied.get("applied") if isinstance(applied, dict) else {},
            note=body.note,
        )
        return {**applied, "review": record}
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(404, "import review not found")
    except ValueError as exc:
        raise HTTPException(400, str(exc))

@router.get("/novels/{nid}/import/knowledge-base/review")
def list_import_knowledge_reviews(nid: str, status: str | None = Query(default=None)):
    try:
        novel_service.get(nid)
        rows = import_review_service.list_for_novel(nid, status=status)
        pending = next((row for row in rows if row.get("status") == "PENDING"), None)
        return {"items": rows, "pending": pending}
    except FileNotFoundError:
        raise HTTPException(404, "novel not found")

@router.post("/novels/{nid}/knowledge-base/review", status_code=201)
def create_novel_knowledge_review(nid: str):
    try:
        novel_service.get(nid)
        chapters = chapter_service.list(nid)
        if not any(str(item.get("content") or "").strip() for item in chapters):
            raise HTTPException(409, {"code": "KNOWLEDGE_REVIEW_SOURCE_EMPTY", "message": "小说尚无可审查的章节正文"})
        return import_review_service.ensure_pending(nid, {}, source_format="project", import_id=f"project:{nid}")
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(404, "novel not found")

@router.post("/novels/{nid}/chapters/{chapter_id}/knowledge-base/review", status_code=201)
def create_chapter_knowledge_review(nid: str, chapter_id: str):
    try:
        novel_service.get(nid)
        chapter = chapter_service.get(chapter_id)
        if chapter.get("novel_id") != nid:
            raise HTTPException(404, "chapter not found")
        if not str(chapter.get("content") or "").strip():
            raise HTTPException(409, {"code": "KNOWLEDGE_REVIEW_SOURCE_EMPTY", "message": "当前章节尚无可审查的正文"})
        return import_review_service.ensure_pending(nid, {}, source_format="chapter", import_id=chapter_id)
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(404, "chapter not found")

@router.get("/novels/{nid}/import/knowledge-base/review/{review_id}")
def get_import_knowledge_review(nid: str, review_id: str):
    try:
        review = import_review_service.get(review_id)
        if review.get("novel_id") != nid:
            raise HTTPException(403, {"code": "IMPORT_REVIEW_SCOPE_FORBIDDEN"})
        return review
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(404, "import review not found")

@router.put("/novels/{nid}/import/knowledge-base/review/{review_id}")
def update_import_knowledge_review(nid: str, review_id: str, body: ImportKnowledgeReviewUpdateIn):
    try:
        review = import_review_service.get(review_id)
        if review.get("novel_id") != nid:
            raise HTTPException(403, {"code": "IMPORT_REVIEW_SCOPE_FORBIDDEN"})
        return import_review_service.update_candidates(review_id, body.candidates, selected=body.selected)
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(404, "import review not found")
    except ValueError as exc:
        raise HTTPException(409, str(exc))

def _import_ai_candidates(text: str) -> dict[str, list[dict]]:
    raw = str(text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL | re.IGNORECASE)
    if fenced:
        raw = fenced.group(1)
    else:
        start, end = raw.find("{"), raw.rfind("}")
        if start >= 0 and end > start:
            raw = raw[start:end + 1]
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("AI 未返回可审核的结构化结果") from exc
    if isinstance(payload, dict) and isinstance(payload.get("candidates"), dict):
        payload = payload["candidates"]
    allowed = {
        "characters": ("name",), "locations": ("name",),
        "timeline_events": ("title",), "foreshadowing": ("title", "description"),
    }
    result: dict[str, list[dict]] = {}
    for kind, required in allowed.items():
        items = payload.get(kind, []) if isinstance(payload, dict) else []
        if not isinstance(items, list):
            raise ValueError("AI 审查结果的数据分组无效")
        clean: list[dict] = []
        for value in items[:100]:
            if not isinstance(value, dict):
                continue
            item = {str(key)[:80]: field for key, field in value.items() if isinstance(field, (str, int, float, bool, list))}
            if not any(str(item.get(field, "")).strip() for field in required):
                continue
            item["analysis_source"] = "AI_REVIEW"
            clean.append(item)
        if clean:
            result[kind] = clean
    if not result:
        raise ValueError("AI 未识别出可审核的知识库候选")
    return result

@router.post("/novels/{nid}/import/knowledge-base/review/{review_id}/ai-analyze")
def ai_analyze_import_knowledge(nid: str, review_id: str, body: ImportAiReviewIn):
    try:
        novel = novel_service.get(nid)
        review = import_review_service.get(review_id)
        if review.get("novel_id") != nid:
            raise HTTPException(403, {"code": "IMPORT_REVIEW_SCOPE_FORBIDDEN"})
        if review.get("status") != "PENDING":
            raise HTTPException(409, {"code": "IMPORT_REVIEW_COMPLETED"})
        chapters = novel_service.chapters.list(nid)[:200]
        if review.get("source_format") == "chapter" and review.get("import_id"):
            chapters = [item for item in chapters if item.get("id") == review.get("import_id")]
            if not chapters:
                raise HTTPException(404, {"code": "KNOWLEDGE_REVIEW_SOURCE_NOT_FOUND"})
        excerpts, remaining = [], 48000
        per_chapter = min(6000, max(240, 48000 // max(1, len(chapters))))
        for chapter in chapters:
            content = str(chapter.get("content") or "")[:min(per_chapter, remaining)]
            excerpts.append({"number": chapter.get("number"), "title": chapter.get("title"), "content": content})
            remaining -= len(content)
        provider_id, model_id = body.provider_id or "deepseek", body.model_id or "deepseek-chat"
        prompt = (
            "请阅读小说项目的章节节选，提取并纠正资料库候选。只输出 JSON，不要 Markdown。\n"
            "JSON 顶层必须含 candidates，分组仅限 characters、locations、timeline_events、foreshadowing。"
            "人物和地点使用 name；时间线使用 title、sequence、description；伏笔使用 title、description。"
            "每项尽量提供 evidence 和 confidence；不确定或仅出现一次的普通词不要收录。\n\n"
            + json.dumps({"novel": {"title": novel.get("title")}, "chapter_excerpts": excerpts, "local_candidates": review.get("candidates", {})}, ensure_ascii=False)
        )
        request = TextGenerationRequest(provider_id=provider_id, model_id=model_id, prompt=prompt,
            system_instruction="你是小说导入资料库审查员。严格依据原文，不得臆造；只返回符合要求的 JSON。",
            parameters=TextGenerationParameters(temperature=0.1, max_output_tokens=5000),
            metadata={"surface": "novel_knowledge_review", "mode": "author_approval_required", "source_format": review.get("source_format")})
        result = runtime.generation_runtime.text_node.execute(TextModelNodeInput(request))
        candidates = _import_ai_candidates(result.generated_text)
        analysis = {"source": "AI_REVIEW", "provider_id": result.response.provider_id, "model_id": result.response.model_id,
            "chapter_count": len(excerpts), "content_characters": 48000 - remaining}
        saved = import_review_service.update_candidates(review_id, candidates, analysis=analysis)
        return {"review": saved, "analysis": analysis}
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(404, "import review not found")
    except ModelRuntimeError as exc:
        raise HTTPException(503, {"code": exc.code.value, "message": exc.safe_message, "retryable": exc.retryable}) from exc
    except ValueError as exc:
        raise HTTPException(422, {"code": "IMPORT_AI_REVIEW_INVALID", "message": str(exc)}) from exc
@router.get("/novels/{nid}/adaptations")
def adaptation_proposals(nid:str,branch_id:str|None=None,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    _adaptation_context(nid,branch_id,x_session_token,"domain.read");return guard(adaptation_service.list,nid)
@router.post("/novels/{nid}/adaptations",status_code=201)
def create_adaptation_proposal(nid:str,body:AdaptationProposalIn,branch_id:str|None=None,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    actor,scope=_adaptation_context(nid,branch_id,x_session_token,"domain.write");result=guard(adaptation_service.create,nid,body.target,body.title,body.instruction)
    if actor:audit_service.append(audit_service.build(actor,"ADAPTATION_PROPOSAL_CREATED","AdaptationProposal",result["id"],scope,{"novel_id":nid,"branch_id":branch_id,"target":result["target"],"status":result["status"]}))
    return result
@router.put("/novels/{nid}/adaptations/{proposal_id}/blueprint")
def update_adaptation_blueprint(nid:str,proposal_id:str,body:AdaptationBlueprintUpdateIn,branch_id:str|None=None,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    actor,scope=_adaptation_context(nid,branch_id,x_session_token,"domain.write");result=guard(adaptation_service.update_blueprint,nid,proposal_id,body.model_dump())
    if actor:audit_service.append(audit_service.build(actor,"ADAPTATION_BLUEPRINT_UPDATED","AdaptationProposal",proposal_id,scope,{"novel_id":nid,"branch_id":branch_id,"target":result["target"],"status":result["status"],"result_version":result["blueprint_revision"]}))
    return result
@router.post("/novels/{nid}/adaptations/{proposal_id}/approve")
def approve_adaptation_proposal(nid:str,proposal_id:str,branch_id:str|None=None,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    actor,scope=_adaptation_context(nid,branch_id,x_session_token,"domain.review");result=guard(adaptation_service.approve,nid,proposal_id)
    if actor:audit_service.append(audit_service.build(actor,"ADAPTATION_PROPOSAL_APPROVED","AdaptationProposal",proposal_id,scope,{"novel_id":nid,"branch_id":branch_id,"target":result["target"],"status":result["status"]}))
    return result
@router.post("/novels/{nid}/adaptations/{proposal_id}/materialize",status_code=201)
def materialize_adaptation(nid:str,proposal_id:str,branch_id:str|None=None,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    if branch_id:
        actor,source_scope=_adaptation_context(nid,branch_id,x_session_token,"domain.write");proposal=guard(adaptation_service.get,nid,proposal_id)
        if proposal.get("adapted_scope"):
            target=proposal["adapted_scope"]
        else:
            created=collaboration_admin_service.path_mutations.create_project(actor.workspace_id,proposal["title"],f"Adaptation:{proposal['target']}",actor)
            story=collaboration_scope_service.repository.list("storylines",workspace_id=actor.workspace_id,project_id=created["id"])[0];branch=collaboration_scope_service.repository.list("branches",workspace_id=actor.workspace_id,project_id=created["id"],storyline_id=story["id"])[0]
            target={"workspace_id":actor.workspace_id,"project_id":created["id"],"storyline_id":story["id"],"branch_id":branch["id"]};adaptation_service.record_team_materialization(nid,proposal_id,target)
            authorization_service.assign_role(DomainRoleAssignment(str(__import__('uuid').uuid4()),actor.actor_id,DomainRole.DOMAIN_LEAD,ModalityDomain.NOVEL,AuthorizationScope(ScopeKind.PROJECT,actor.workspace_id,created["id"]),actor.actor_id))
        target_scope=AuthorizationScope(ScopeKind.BRANCH,target["workspace_id"],target["project_id"],target["storyline_id"],target["branch_id"]);snapshots=guard(adaptation_service.snapshot_chapters,nid,proposal_id);existing=chapter_service.list(target["project_id"])
        for snapshot in snapshots[len(existing):]:
            created=collaboration_application_service.create_chapter(actor=actor,scope=target_scope,title=snapshot["title"]);collaboration_application_service.update_chapter(actor=actor,scope=target_scope,chapter_id=created["id"],document=snapshot["document"],expected_version=created["version"],reason="MANUAL_SAVE")
        target_chapters=chapter_service.list(target["project_id"]);adaptation_service.record_execution_manifest(nid,proposal_id,target_chapters);adaptation_service.record_team_materialization(nid,proposal_id,target,True);audit_service.append(audit_service.build(actor,"ADAPTATION_MATERIALIZED","AdaptationProposal",proposal_id,source_scope,{"novel_id":nid,"branch_id":branch_id,"target":proposal["target"],"status":"MATERIALIZED"}))
        return {"id":target["project_id"],"title":proposal["title"],"scope":target}
    return guard(adaptation_service.materialize,nid,proposal_id)
@router.post("/novels/{nid}/adaptations/{proposal_id}/tasks/{task_id}/generate")
def generate_adaptation_draft(nid:str,proposal_id:str,task_id:str,body:AdaptationDraftGenerateIn,branch_id:str|None=None,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    _adaptation_context(nid,branch_id,x_session_token,"domain.write");return guard(adaptation_service.generate_draft,nid,proposal_id,task_id,body.mode,body.provider_id,body.model_id)
@router.post("/novels/{nid}/adaptations/{proposal_id}/tasks/{task_id}/review")
def review_adaptation_draft(nid:str,proposal_id:str,task_id:str,body:AdaptationDraftReviewIn,branch_id:str|None=None,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    _adaptation_context(nid,branch_id,x_session_token,"domain.review");return guard(adaptation_service.review_draft,nid,proposal_id,task_id,body.decision,body.note)
@router.post("/novels/{nid}/adaptations/{proposal_id}/tasks/{task_id}/apply")
def apply_adaptation_draft(nid:str,proposal_id:str,task_id:str,branch_id:str|None=None,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    actor,source_scope=_adaptation_context(nid,branch_id,x_session_token,"domain.write")
    if not branch_id:return guard(adaptation_service.apply_draft,nid,proposal_id,task_id)
    item,tasks,index,task=guard(adaptation_service.prepare_apply,nid,proposal_id,task_id);target=item.get("adapted_scope")
    if not target:raise HTTPException(400,{"code":"ADAPTATION_TARGET_SCOPE_MISSING"})
    target_scope=AuthorizationScope(ScopeKind.BRANCH,target["workspace_id"],target["project_id"],target["storyline_id"],target["branch_id"]);current=chapter_service.get(task["target_chapter_id"]);body=re.sub(r"^#{1,6}\s+[^\n]+\n+","",task["draft"]["content"].strip(),count=1).strip();document=markdown_to_document(f"# {current['title']}\n\n{body}")
    saved=collaboration_application_service.update_chapter(actor=actor,scope=target_scope,chapter_id=current["id"],document=document,expected_version=current["version"],reason="AI_ACCEPT");result=adaptation_service.mark_applied(nid,proposal_id,tasks,index,saved["version"])
    audit_service.append(audit_service.build(actor,"ADAPTATION_DRAFT_APPLIED","AdaptationProposal",proposal_id,source_scope,{"novel_id":nid,"branch_id":branch_id,"status":"APPLIED","result_version":saved["version"]}));return result
@router.get("/novels/{nid}/screenplays")
def screenplays(nid:str):return guard(screenplay_service.list,nid)
@router.post("/novels/{nid}/screenplays",status_code=201)
def create_screenplay(nid:str,body:ScreenplayIn):return guard(screenplay_service.create,nid,body.title)
@router.put("/novels/{nid}/screenplays/{screenplay_id}/scenes/{scene_id}")
def update_screenplay_scene(nid:str,screenplay_id:str,scene_id:str,body:ScreenplaySceneIn):return guard(screenplay_service.update_scene,nid,screenplay_id,scene_id,body.model_dump())
@router.post("/novels/{nid}/screenplays/{screenplay_id}/approve")
def approve_screenplay(nid:str,screenplay_id:str):return guard(screenplay_service.approve,nid,screenplay_id)
@router.post("/novels/{nid}/screenplays/{screenplay_id}/shots",status_code=201)
def plan_screenplay_shots(nid:str,screenplay_id:str):return guard(screenplay_service.plan_shots,nid,screenplay_id)
@router.post("/novels/{nid}/screenplays/{screenplay_id}/shots/approve")
def approve_screenplay_shots(nid:str,screenplay_id:str):return guard(screenplay_service.approve_shots,nid,screenplay_id)
@router.put("/novels/{nid}/screenplays/{screenplay_id}/shots/{shot_id}")
def update_screenplay_shot(nid:str,screenplay_id:str,shot_id:str,body:ShotIn):return guard(screenplay_service.update_shot,nid,screenplay_id,shot_id,body.model_dump())
@router.post("/novels/{nid}/screenplays/{screenplay_id}/storyboard",status_code=201)
def plan_storyboard(nid:str,screenplay_id:str):return guard(screenplay_service.plan_storyboard,nid,screenplay_id)
@router.post("/novels/{nid}/screenplays/{screenplay_id}/storyboard/approve")
def approve_storyboard(nid:str,screenplay_id:str):return guard(screenplay_service.approve_storyboard,nid,screenplay_id)
@router.put("/novels/{nid}/screenplays/{screenplay_id}/storyboard/{card_id}")
def update_storyboard(nid:str,screenplay_id:str,card_id:str,body:StoryboardCardIn):return guard(screenplay_service.update_storyboard_card,nid,screenplay_id,card_id,body.model_dump())
@router.post("/novels/{nid}/screenplays/{screenplay_id}/transitions",status_code=201)
def plan_transitions(nid:str,screenplay_id:str):return guard(screenplay_service.plan_transitions,nid,screenplay_id)
@router.post("/novels/{nid}/screenplays/{screenplay_id}/transitions/approve")
def approve_transitions(nid:str,screenplay_id:str):return guard(screenplay_service.approve_transitions,nid,screenplay_id)
@router.put("/novels/{nid}/screenplays/{screenplay_id}/transitions/{transition_id}")
def update_transition(nid:str,screenplay_id:str,transition_id:str,body:TransitionIn):return guard(screenplay_service.update_transition,nid,screenplay_id,transition_id,body.model_dump())
@router.get("/novels/{nid}/screenplays/{screenplay_id}/transitions/{transition_id}/prompt")
def transition_prompt(nid:str,screenplay_id:str,transition_id:str):return guard(screenplay_service.transition_prompt,nid,screenplay_id,transition_id)
@router.get("/novels/{nid}/screenplays/{screenplay_id}/transitions/{transition_id}/suggestion")
def transition_suggestion(nid:str,screenplay_id:str,transition_id:str):return guard(screenplay_service.transition_suggestion,nid,screenplay_id,transition_id)
@router.get("/novels/{nid}/screenplays/{screenplay_id}/transitions/{transition_id}/motion-prompt")
def motion_prompt(nid:str,screenplay_id:str,transition_id:str):return guard(screenplay_service.motion_prompt,nid,screenplay_id,transition_id)
class MotionPromptIn(BaseModel): motion_prompt:str=Field(min_length=1,max_length=10000)
@router.put("/novels/{nid}/screenplays/{screenplay_id}/transitions/{transition_id}/motion-prompt")
def save_motion_prompt(nid:str,screenplay_id:str,transition_id:str,body:MotionPromptIn,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    _authorize_media_novel(nid,x_session_token,"domain.write");return guard(screenplay_service.save_motion_prompt,nid,screenplay_id,transition_id,body.motion_prompt)
@router.post("/novels/{nid}/screenplays/{screenplay_id}/motion-tasks",status_code=201)
def create_motion_tasks(nid:str,screenplay_id:str,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    _authorize_media_novel(nid,x_session_token,"domain.write");return guard(screenplay_service.create_motion_tasks,nid,screenplay_id)
@router.get("/video-providers")
def video_providers():
    items=[]
    for provider_id,base in VIDEO_PROVIDER_CATALOG.items():
        config={**base,**(_video_provider_configs.get(provider_id) or {})}
        if provider_id=='deterministic': continue
        requires=bool(config.get('requires_credential',True));credential_configured=not requires or (credential_vault.supports_provider(provider_id) and credential_vault.has(provider_id));configured=bool(config.get('enabled') and config.get('endpoint') and credential_configured)
        registered=provider_id in screenplay_service.video_providers;adapter=screenplay_service.video_providers.get(provider_id);reachable=bool(registered and adapter and adapter.health_check())
        capabilities=adapter.capabilities() if adapter and hasattr(adapter,'capabilities') else {}
        items.append({"id":provider_id,"display_name":config.get('display_name') or provider_id,"endpoint":config.get('endpoint',''),"model":config.get('model_id',''),"local":bool(config.get('local')),"requires_credential":requires,"credential_configured":credential_configured,"available":configured and reachable,"registered":registered,"reachable":reachable,"capabilities":capabilities,"mode":"http","health":"READY" if configured and reachable else "NOT_CONFIGURED"})
    for provider_id,config in _video_provider_configs.items():
        if provider_id in VIDEO_PROVIDER_CATALOG: continue
        requires=bool(config.get('requires_credential',True));credential_configured=not requires or (credential_vault.supports_provider(provider_id) and credential_vault.has(provider_id));configured=bool(config.get('enabled') and config.get('endpoint') and credential_configured);registered=provider_id in screenplay_service.video_providers;adapter=screenplay_service.video_providers.get(provider_id);reachable=bool(registered and adapter and adapter.health_check())
        capabilities=adapter.capabilities() if adapter and hasattr(adapter,'capabilities') else {}
        items.append({"id":provider_id,"display_name":config.get('display_name') or provider_id,"endpoint":config.get('endpoint',''),"model":config.get('model_id',''),"local":bool(config.get('local')),"requires_credential":requires,"credential_configured":credential_configured,"available":configured and reachable,"registered":registered,"reachable":reachable,"capabilities":capabilities,"mode":"http","health":"READY" if configured and reachable else "NOT_CONFIGURED"})
    items.sort(key=lambda item:(not item['local'],not item['available'],item['display_name']))
    return {"items":items,"routing_policy":"LOCAL_FIRST"}
class VideoProviderConfigIn(BaseModel):
    endpoint:str=''; model_id:str='video-placeholder'; enabled:bool=True;local:bool=False;requires_credential:bool=True;display_name:str=''
    @field_validator('endpoint')
    @classmethod
    def validate_endpoint(cls,value):
        value=value.strip()
        if value and not value.lower().startswith(('http://','https://')): raise ValueError('endpoint must use http or https')
        return value.rstrip('/')
    @field_validator('model_id')
    @classmethod
    def validate_model(cls,value):
        if not value.strip(): raise ValueError('model_id is required')
        return value.strip()
_video_provider_configs:dict[str,dict]={}
VIDEO_PROVIDER_CATALOG={
    'local-video':{'display_name':'本地视频 API','endpoint':'http://127.0.0.1:8189','model_id':'','local':True,'requires_credential':False,'enabled':False},
    'runway':{'display_name':'Runway','endpoint':'','model_id':'','local':False,'requires_credential':True,'enabled':False},
    'kling':{'display_name':'可灵 / Kling','endpoint':'','model_id':'','local':False,'requires_credential':True,'enabled':False},
    'minimax':{'display_name':'MiniMax / 海螺','endpoint':'','model_id':'','local':False,'requires_credential':True,'enabled':False},
    'seedance':{'display_name':'Seedance / 即梦','endpoint':'','model_id':'','local':False,'requires_credential':True,'enabled':False},
    'custom':{'display_name':'其他视频服务商','endpoint':'','model_id':'','local':False,'requires_credential':True,'enabled':False},
}
_video_provider_config_path=settings.data_path()/"video_providers.json"
def _load_video_provider_configs():
    global _video_provider_configs
    try: _video_provider_configs=json.loads(_video_provider_config_path.read_text(encoding='utf-8'))
    except (FileNotFoundError,ValueError): _video_provider_configs={}
_load_video_provider_configs()
provider_support_registry.replace_source("video", _video_provider_configs)
from .dependencies import refresh_video_provider
for _video_id,_video_cfg in sorted(_video_provider_configs.items(),key=lambda item:(not bool(item[1].get('local')),item[0])):
    if _video_cfg.get('enabled') and _video_cfg.get('endpoint'):
        refresh_video_provider(_video_id,_video_cfg['endpoint'],_video_cfg.get('model_id','video-placeholder'),bool(_video_cfg.get('requires_credential',True)))
@router.put("/video-providers/{provider_id}/config")
def configure_video_provider(provider_id:str,body:VideoProviderConfigIn):
    if not is_canonical_provider_id(provider_id):
        raise HTTPException(400,{'code':'INVALID_VIDEO_PROVIDER_CONFIG','message':'invalid video provider id'})
    updated={**_video_provider_configs,provider_id:{"provider_id":provider_id,**body.model_dump()}}
    _video_provider_config_path.parent.mkdir(parents=True,exist_ok=True); atomic_write(_video_provider_config_path,json.dumps(updated,ensure_ascii=False,indent=2))
    _video_provider_configs.clear();_video_provider_configs.update(updated)
    provider_support_registry.replace_source("video",_video_provider_configs)
    from .dependencies import refresh_video_provider
    registered=False
    if body.enabled and provider_id!='deterministic':
        registered=refresh_video_provider(provider_id,body.endpoint,body.model_id,body.requires_credential)
    elif provider_id!='deterministic':
        from .dependencies import screenplay_service
        screenplay_service.video_providers.pop(provider_id,None)
    return {**_video_provider_configs[provider_id],"registered":registered}
@router.delete("/video-providers/{provider_id}/config")
def delete_video_provider_config(provider_id:str):
    if provider_id in VIDEO_PROVIDER_CATALOG:
        raise HTTPException(400,{'code':'DEFAULT_PROVIDER_CANNOT_BE_DELETED'})
    screenplay_service.video_providers.pop(provider_id,None)
    if provider_id not in _video_provider_configs:
        return {'provider_id':provider_id,'deleted':False}
    if credential_vault.supports_provider(provider_id) and not provider_support_registry.supports_after_removing("video",provider_id):
        try: credential_vault.clear(provider_id)
        except VaultUnavailableError as exc: raise HTTPException(503,{'code':exc.code,'message':'系统凭据库不可用'}) from exc
    updated=dict(_video_provider_configs);updated.pop(provider_id,None)
    atomic_write(_video_provider_config_path,json.dumps(updated,ensure_ascii=False,indent=2))
    _video_provider_configs.clear();_video_provider_configs.update(updated)
    provider_support_registry.remove("video",provider_id)
    return {'provider_id':provider_id,'deleted':True}
@router.get("/video-providers/{provider_id}/config")
def get_video_provider_config(provider_id:str): return {"provider_id":provider_id,**VIDEO_PROVIDER_CATALOG.get(provider_id,{}),**_video_provider_configs.get(provider_id,{})}
@router.get("/video-providers/{provider_id}/health")
def video_provider_health(provider_id:str):
    if provider_id=='deterministic': return {"provider_id":provider_id,"health":"READY","available":True}
    config=_video_provider_configs.get(provider_id)
    config={**VIDEO_PROVIDER_CATALOG.get(provider_id,{}),**(_video_provider_configs.get(provider_id) or {})};registered=provider_id in screenplay_service.video_providers
    return {"provider_id":provider_id,"health":"READY" if registered else "NOT_CONFIGURED","available":registered,"local":bool(config.get('local'))}
@router.get("/video-providers/{provider_id}/credential-status")
def video_provider_credential_status(provider_id:str):
    if provider_id=='deterministic': return {"provider_id":provider_id,"configured":True,"secret_exposed":False}
    return {"provider_id":provider_id,"configured":credential_vault.has(provider_id),"secret_exposed":False}
@router.get("/multimodal/health")
def multimodal_health():
    from .dependencies import asset_provider_registry
    image_ids=list(asset_provider_registry._providers.keys())
    vision=[{'id':pid,'configured':bool(endpoint and credential_vault.has(pid))} for pid,endpoint in DEFAULT_IMAGE_ENDPOINTS.items() if pid!='custom']
    return {'image_providers':[{"id":pid,"registered":True} for pid in image_ids],"vision_providers":vision,"vision_credentials":any(item['configured'] for item in vision),"speech_credentials":any(item['configured'] for item in vision),"video_provider_configs":len(_video_provider_configs)}
@router.get("/video-callback/security")
def video_callback_security(): return {"configured":bool(os.getenv('VIDEO_CALLBACK_TOKEN','').strip()),"header":"X-Video-Callback-Token","secret_exposed":False}
@router.post("/vision/analyze")
def vision_analyze(body:VisionAnalyzeIn):
    from .asset_providers import OpenAICompatibleVisionProvider,VisionRequest
    from .dependencies import credential_vault
    endpoint=DEFAULT_IMAGE_ENDPOINTS.get(body.provider_id,'')
    secret=credential_vault.resolve(body.provider_id)
    if not endpoint or not secret: raise HTTPException(503,'vision provider is not configured')
    try: safe_image_url=validate_outbound_url(body.image_url)
    except OutboundURLRejected as exc: raise HTTPException(400,{'code':'OUTBOUND_URL_REJECTED','message':str(exc)})
    try:
        import httpx
        result=OpenAICompatibleVisionProvider(httpx,secret,endpoint).analyze(VisionRequest(body.provider_id,body.model_id,body.prompt,safe_image_url))
        payload={'provider_id':result.provider_id,'model_id':result.model_id,'text':result.text,'image_url':safe_image_url,'prompt':body.prompt,'character_id':body.character_id,'scene_id':body.scene_id}
        if body.novel_id:
            from .dependencies import repositories
            novel=repositories.novels.get(body.novel_id); memories=list(novel.get('visual_memories',[])); memories.append({**payload,'created_at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}); repositories.novels.update(body.novel_id,{**novel,'visual_memories':memories[-50:]})
        return payload
    except Exception:
        raise HTTPException(502,{'code':'VISION_ANALYZE_FAILED','message':'图片分析失败'})
@router.post("/images/generate")
def generate_image(body:ImageGenerateIn):
    from .asset_providers import AssetGenerationRequest
    from .dependencies import asset_provider_registry,repositories
    try:
        provider=asset_provider_registry.get(body.provider_id)
        result=provider.generate(AssetGenerationRequest(body.provider_id,body.model_id,body.prompt,str(__import__('uuid').uuid4())))
    except ValueError: raise HTTPException(503,{'code':'IMAGE_PROVIDER_UNAVAILABLE','message':'图片生成服务未配置或不可用'})
    except Exception: raise HTTPException(502,{'code':'IMAGE_PROVIDER_REQUEST_FAILED','message':'图片服务请求失败，请检查地址、模型和服务状态'})
    payload={'provider_id':result.provider_id,'model_id':result.model_id,'asset_uri':result.asset_uri,'prompt':body.prompt,'constraints':body.constraints,'character_id':body.character_id,'scene_id':body.scene_id,'created_at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}
    if body.novel_id:
        novel=repositories.novels.get(body.novel_id); rows=list(novel.get('image_generations',[])); rows.append({**payload,'asset_uri':'inline://generated-image'} if result.asset_uri.startswith('data:') else payload); repositories.novels.update(body.novel_id,{**novel,'image_generations':rows[-50:]})
    return payload
@router.post("/images/edits")
def edit_image(body:ImageEditIn,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    if body.novel_id: _authorize_media_novel(body.novel_id,x_session_token,"domain.write")
    from .dependencies import credential_vault
    from .asset_providers import AssetGenerationRequest,OpenAICompatibleImageProvider
    import httpx
    if body.provider_id != "ddshub":
        raise HTTPException(400,{"code":"IMAGE_EDIT_PROVIDER_UNSUPPORTED","message":"当前多参考图编辑仅支持 DDSHub OpenAI Image API。"})
    if any(not (value.startswith("http://") or value.startswith("https://") or value.startswith("data:image/")) for value in body.images):
        raise HTTPException(400,{"code":"IMAGE_REFERENCE_URI_UNSAFE","message":"参考图仅允许 http(s) 或 data:image URL。"})
    config={**IMAGE_PROVIDER_CATALOG[body.provider_id],**(load_asset_provider_config().get(body.provider_id) or {})}
    endpoint=str(config.get("endpoint") or "").rstrip("/"); secret=credential_vault.resolve(body.provider_id)
    if not endpoint or not secret: raise HTTPException(503,{"code":"IMAGE_PROVIDER_UNAVAILABLE","message":"图片 Provider 未配置"})
    try:
        result=OpenAICompatibleImageProvider(httpx,secret,endpoint).edit(AssetGenerationRequest(body.provider_id,body.model_id,body.prompt,str(uuid.uuid4())),body.images,size=body.size,quality=body.quality,output_format=body.output_format)
    except ValueError as exc: raise HTTPException(400,{"code":"IMAGE_EDIT_INVALID","message":str(exc)})
    except Exception: raise HTTPException(502,{"code":"IMAGE_EDIT_FAILED","message":"图片编辑失败，请检查 Provider 或参考图。"})
    return {"provider_id":result.provider_id,"model_id":result.model_id,"asset_uri":result.asset_uri,"prompt":body.prompt,"reference_count":len(body.images),"created_at":__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}
@router.post("/speech/synthesize")
def synthesize_speech(body:SpeechSynthesizeIn,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    if body.novel_id: _authorize_media_novel(body.novel_id,x_session_token,"domain.write")
    from .audio_providers import AudioGenerationRequest,resolve_provider
    from .dependencies import credential_vault
    try:
        import httpx
        provider_id,default_model,provider=resolve_provider(body.provider_id,'TTS',credential_vault,httpx);model_id=body.model_id.strip() or default_model
        result=provider.generate(AudioGenerationRequest(provider_id,model_id,'TTS',f"[emotion:{body.emotion}] {body.text}",str(uuid.uuid4()),voice=body.voice))
        payload={'provider_id':result.provider_id,'model_id':result.model_id,'voice':body.voice,'emotion':body.emotion,'audio_uri':result.audio_uri,'character_id':body.character_id,'chapter_id':body.chapter_id,'text':body.text,'created_at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}
        if body.novel_id:
            from .dependencies import repositories
            repositories.novels.get(body.novel_id); state=audio_production_store.load(body.novel_id); state['generations'].append(payload); audio_production_store.save(body.novel_id,state)
        return payload
    except ValueError: raise HTTPException(503,{'code':'SPEECH_PROVIDER_UNAVAILABLE','message':'语音 Provider 未配置'})
    except HTTPException: raise
    except Exception: raise HTTPException(502,{'code':'SPEECH_SYNTHESIS_FAILED','message':'语音合成失败'})
@router.get("/audio/providers")
def list_audio_providers():
    from .audio_providers import provider_catalog
    items=[]
    for item in provider_catalog():
        requires=bool(item.get('requires_credential',True));configured=not requires or (credential_vault.supports_provider(item['provider_id']) and credential_vault.has(item['provider_id']))
        items.append({**item,'credential_configured':configured,'configured':bool(item.get('endpoint') and item.get('default_model') and configured),'secret':None})
    return {'domain':'AUDIO','routing_policy':'LOCAL_FIRST','items':items}
@router.put("/audio/providers/{provider_id}")
def configure_audio_provider(provider_id:str,body:AudioProviderConfigIn):
    try:
        result=save_audio_provider_config(provider_id,**body.model_dump())
        provider_support_registry.replace_source("audio",load_audio_provider_config())
        return {'provider_id':provider_id,**result,'secret':None}
    except ValueError as exc:raise HTTPException(400,{'code':'INVALID_AUDIO_PROVIDER_CONFIG','message':str(exc)}) from exc
@router.delete("/audio/providers/{provider_id}")
def remove_audio_provider(provider_id:str):
    from .audio_providers import AUDIO_PROVIDER_CATALOG
    if provider_id in AUDIO_PROVIDER_CATALOG:raise HTTPException(400,{'code':'DEFAULT_PROVIDER_CANNOT_BE_DELETED'})
    if credential_vault.supports_provider(provider_id) and provider_id in load_audio_provider_config() and not provider_support_registry.supports_after_removing("audio",provider_id):
        try: credential_vault.clear(provider_id)
        except VaultUnavailableError as exc: raise HTTPException(503,{'code':exc.code,'message':'系统凭据库不可用'}) from exc
    deleted=delete_audio_provider_config(provider_id)
    if deleted:provider_support_registry.remove("audio",provider_id)
    return {'provider_id':provider_id,'deleted':deleted}
@router.post("/audio/generate",status_code=202)
def generate_audio(body:AudioGenerateIn,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    if body.novel_id: _authorize_media_novel(body.novel_id,x_session_token,"domain.write")
    from .audio_providers import AudioGenerationRequest,resolve_provider
    from .dependencies import credential_vault
    try:
        import httpx
        provider_id,default_model,provider=resolve_provider(body.provider_id,body.capability,credential_vault,httpx)
        model_id=body.model_id.strip() or default_model
        result=provider.generate(AudioGenerationRequest(provider_id,model_id,body.capability,body.prompt,str(uuid.uuid4()),source_audio_uri=body.source_audio_uri,source_video_uri=body.source_video_uri,duration_seconds=body.duration_seconds,parameters=body.parameters))
        return {'domain':'AUDIO','kind':body.capability,'provider_id':result.provider_id,'model_id':result.model_id,'audio_uri':result.audio_uri,'remote_task_id':result.remote_task_id,'status':result.status}
    except ValueError as exc: raise HTTPException(503,{'code':'AUDIO_PROVIDER_UNAVAILABLE','message':str(exc)})
    except Exception: raise HTTPException(502,{'code':'AUDIO_GENERATION_FAILED','message':'音频生成失败'})
@router.get("/novels/{nid}/image-generations")
def list_image_generations(nid:str,character_id:str|None=None,scene_id:str|None=None):
    from .dependencies import repositories
    novel=repositories.novels.get(nid); items=[item for item in novel.get('image_generations',[]) if (not character_id or item.get('character_id')==character_id) and (not scene_id or item.get('scene_id')==scene_id)]
    return {'novel_id':nid,'items':items[-50:]}
@router.get("/novels/{nid}/speech-generations")
def list_speech_generations(nid:str,character_id:str|None=None):
    from .dependencies import repositories
    repositories.novels.get(nid); items=[item for item in audio_production_store.load(nid)['generations'] if not character_id or item.get('character_id')==character_id]
    return {'novel_id':nid,'items':items[-50:]}
@router.get("/novels/{nid}/audio-production/settings")
def audio_production_settings(nid:str,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    _authorize_media_novel(nid,x_session_token,"domain.read")
    from .dependencies import repositories
    repositories.novels.get(nid); state=audio_production_store.load(nid)
    return {'novel_id':nid,'voice_bindings':state['voice_bindings'],'pronunciation_dictionary':state['pronunciation_dictionary']}
@router.put("/novels/{nid}/audio-production/settings")
def audio_production_settings_update(nid:str,body:AudioProductionSettingsIn,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    _authorize_media_novel(nid,x_session_token,"domain.write")
    from .dependencies import repositories
    repositories.novels.get(nid); payload=body.model_dump(); state=audio_production_store.load(nid); state.update(payload); audio_production_store.save(nid,state)
    return {'novel_id':nid,**payload}
@router.get("/novels/{nid}/audiobook/manifest")
def audiobook_manifest(nid:str,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    _authorize_media_novel(nid,x_session_token,"domain.read")
    from .dependencies import repositories
    chapters=repositories.chapters.list(nid); novel=repositories.novels.get(nid); production=audio_production_store.load(nid); speeches=production['generations']; jobs=production['jobs']
    items=[]
    for chapter in chapters:
        text=str(chapter.get('content','')).strip()
        chapter_speeches=[item for item in speeches if item.get('chapter_id')==chapter.get('id')]
        chapter_jobs=[job for job in jobs if job.get('chapter_id')==chapter.get('id')]; latest_job=chapter_jobs[-1] if chapter_jobs else None
        production_status=str(latest_job.get('status')) if latest_job else ('SUCCEEDED' if chapter_speeches else 'NOT_QUEUED')
        items.append({'chapter_id':chapter.get('id'),'title':chapter.get('title',''),'text_length':len(text),'audio_count':len(chapter_speeches),'audio':chapter_speeches,'production_status':production_status,'latest_job':latest_job})
    return {'novel_id':nid,'title':novel.get('title',''),'chapters':items,'total_chapters':len(items),'ready_chapters':sum(1 for item in items if item['audio_count']>0)}
@router.get("/novels/{nid}/audiobook/mix-plan")
def audiobook_mix_plan(nid:str,chapter_id:str|None=None,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    _authorize_media_novel(nid,x_session_token,"domain.read")
    from .dependencies import repositories
    repositories.novels.get(nid); rows=[item for item in audio_production_store.load(nid)['generations'] if not chapter_id or item.get('chapter_id')==chapter_id]
    tracks={}
    for item in rows:
        key=item.get('character_id') or 'narrator'; tracks.setdefault(key,[]).append({'audio_uri':item.get('audio_uri'),'voice':item.get('voice'),'emotion':item.get('emotion','neutral'),'created_at':item.get('created_at')})
    return {'novel_id':nid,'chapter_id':chapter_id,'tracks':[{'track_id':key,'clips':clips} for key,clips in tracks.items()],'mix_status':'PLAN_ONLY'}
@router.post("/novels/{nid}/audiobook/chapters/{chapter_id}/queue",status_code=202)
def queue_audiobook_chapter(nid:str,chapter_id:str,body:AudiobookJobIn|None=None,voice:str='alloy',x_session_token:str|None=Header(None,alias="X-Session-Token")):
    _authorize_media_novel(nid,x_session_token,"domain.write")
    from .dependencies import repositories
    repositories.novels.get(nid); state=audio_production_store.load(nid); chapters=repositories.chapters.list(nid); chapter=next((item for item in chapters if item.get('id')==chapter_id),None)
    if chapter is None: raise HTTPException(404,'chapter not found')
    config=(body or AudiobookJobIn(voice=voice)).model_dump(); now=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
    bindings=state['voice_bindings']; binding=next((item for item in bindings if config.get('character_id') and item.get('character_id')==config['character_id']),None)
    if binding: config={**config,**binding,'character_id':config['character_id']}
    text=_spoken_chapter_text(str(chapter.get('content','')));segments=_estimated_subtitle_segments(text,float(config.get('speech_rate') or 1),int(config.get('pause_ms') or 0));estimated_duration=segments[-1]['end_ms'] if segments else 0
    jobs=state['jobs']; job={'id':f"audio-{__import__('uuid').uuid4()}",'chapter_id':chapter_id,**config,'status':'QUEUED','attempt':0,'text_length':len(text),'segments':segments,'timing_status':'ESTIMATED','estimated_duration_ms':estimated_duration,'created_at':now,'updated_at':now,'error':None,'error_code':None}
    jobs.append(job); state['jobs']=jobs; audio_production_store.save(nid,state); return job
@router.get("/novels/{nid}/audiobook/jobs")
def list_audiobook_jobs(nid:str,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    _authorize_media_novel(nid,x_session_token,"domain.read")
    from .dependencies import repositories
    repositories.novels.get(nid); jobs=audio_production_store.load(nid)['jobs']; return {'novel_id':nid,'items':jobs,'total':len(jobs)}
@router.get("/novels/{nid}/media-tasks")
def list_media_tasks(nid:str,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    _authorize_media_novel(nid,x_session_token,"domain.read")
    from .dependencies import repositories
    repositories.novels.get(nid)
    audiobook=list(audio_production_store.load(nid)['jobs'])
    motion=[]
    for screenplay in screenplay_service.list(nid):
        for task in screenplay.get('motion_tasks',[]):
            motion.append({**task,'screenplay_id':screenplay.get('id')})
    return {'novel_id':nid,'audiobook':audiobook,'motion':motion}
@router.get("/novels/{nid}/audiobook/jobs/{job_id}/subtitles.{format}")
def audiobook_job_subtitles(nid:str,job_id:str,format:str,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    _authorize_media_novel(nid,x_session_token,"domain.read")
    from .dependencies import repositories
    repositories.novels.get(nid)
    if format not in {'srt','vtt'}: raise HTTPException(404,'subtitle format not found')
    job=next((item for item in audio_production_store.load(nid)['jobs'] if item.get('id')==job_id),None)
    if job is None: raise HTTPException(404,'audiobook job not found')
    segments=list(job.get('segments') or [])
    if not segments: raise HTTPException(409,{'code':'AUDIOBOOK_SUBTITLES_UNAVAILABLE','message':'该任务没有可导出的字幕分段'})
    media_type='text/vtt' if format=='vtt' else 'application/x-subrip';filename=f"{job.get('chapter_id') or 'chapter'}-{job_id[-8:]}.{format}"
    return Response(_render_subtitles(segments,format),media_type=f'{media_type}; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="{filename}"'})
@router.post("/novels/{nid}/audiobook/jobs/{job_id}/retry")
def retry_audiobook_job(nid:str,job_id:str,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    _authorize_media_novel(nid,x_session_token,"domain.write")
    from .dependencies import repositories
    repositories.novels.get(nid); state=audio_production_store.load(nid); jobs=state['jobs']; index=next((i for i,item in enumerate(jobs) if item.get('id')==job_id),None)
    if index is None: raise HTTPException(404,'audiobook job not found')
    if jobs[index].get('status') not in {'FAILED','CANCELLED'}: raise HTTPException(409,{'code':'AUDIOBOOK_JOB_NOT_RETRYABLE','message':'只有失败或已取消任务可以重试'})
    now=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(); jobs[index]={**jobs[index],'status':'QUEUED','error':None,'error_code':None,'retry_at':now,'updated_at':now}; state['jobs']=jobs; audio_production_store.save(nid,state); return jobs[index]
@router.post("/novels/{nid}/audiobook/jobs/{job_id}/cancel")
def cancel_audiobook_job(nid:str,job_id:str,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    _authorize_media_novel(nid,x_session_token,"domain.write")
    from .dependencies import repositories
    repositories.novels.get(nid); state=audio_production_store.load(nid); jobs=state['jobs']; index=next((i for i,item in enumerate(jobs) if item.get('id')==job_id),None)
    if index is None: raise HTTPException(404,'audiobook job not found')
    if jobs[index].get('status') not in {'QUEUED','RUNNING'}: raise HTTPException(409,{'code':'AUDIOBOOK_JOB_NOT_CANCELLABLE','message':'当前任务不能取消'})
    now=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(); jobs[index]={**jobs[index],'status':'CANCELLED','cancelled_at':now,'updated_at':now}; state['jobs']=jobs; audio_production_store.save(nid,state); return jobs[index]
@router.post("/novels/{nid}/audiobook/jobs/{job_id}/execute")
def execute_audiobook_job(nid:str,job_id:str,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    _authorize_media_novel(nid,x_session_token,"domain.write")
    from .dependencies import repositories,credential_vault
    from .audio_providers import AudioGenerationRequest,resolve_provider
    repositories.novels.get(nid); state=audio_production_store.load(nid); jobs=state['jobs']; index=next((i for i,item in enumerate(jobs) if item.get('id')==job_id),None)
    if index is None: raise HTTPException(404,'audiobook job not found')
    job=jobs[index]
    if job.get('status')!='QUEUED': raise HTTPException(409,{'code':'AUDIOBOOK_JOB_NOT_EXECUTABLE','message':'只有排队中的任务可以执行'})
    chapter=next((item for item in repositories.chapters.list(nid) if item.get('id')==job.get('chapter_id')),None)
    if chapter is None: raise HTTPException(404,'chapter not found')
    provider_id=str(job.get('provider_id') or 'auto')
    now=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(); jobs[index]={**job,'status':'RUNNING','attempt':int(job.get('attempt') or 0)+1,'started_at':now,'updated_at':now}; state['jobs']=jobs; audio_production_store.save(nid,state); job=jobs[index]
    try:
        import httpx
        resolved_provider,default_model,provider=resolve_provider(provider_id,'TTS',credential_vault,httpx);model_id=str(job.get('model_id') or default_model)
        text=_spoken_chapter_text(str(chapter.get('content',''))); dictionary=state['pronunciation_dictionary']
        for entry in dictionary: text=text.replace(str(entry.get('term','')),str(entry.get('pronunciation','')))
        prompt=f"[emotion:{job.get('emotion','neutral')}] {text}"; result=provider.generate(AudioGenerationRequest(resolved_provider,model_id,'TTS',prompt,job_id,voice=str(job.get('voice') or 'alloy')))
        latest=audio_production_store.load(nid); latest_index=next((i for i,item in enumerate(latest['jobs']) if item.get('id')==job_id),None)
        if latest_index is not None and latest['jobs'][latest_index].get('status')=='CANCELLED': return latest['jobs'][latest_index]
        state=latest; jobs=state['jobs']; index=latest_index if latest_index is not None else index
        completed=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(); speech={'provider_id':resolved_provider,'model_id':model_id,'voice':job.get('voice'),'emotion':job.get('emotion','neutral'),'audio_uri':result.audio_uri,'character_id':job.get('character_id'),'chapter_id':job['chapter_id'],'text':str(chapter.get('content','')),'created_at':completed}; state['generations'].append(speech); jobs[index]={**job,'provider_id':resolved_provider,'model_id':model_id,'status':'SUCCEEDED','audio_uri':result.audio_uri,'completed_at':completed,'updated_at':completed,'error':None,'error_code':None}; state['jobs']=jobs; audio_production_store.save(nid,state); return jobs[index]
    except ValueError:
        latest=audio_production_store.load(nid);latest_index=next((i for i,item in enumerate(latest['jobs']) if item.get('id')==job_id),index);failed=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat();latest['jobs'][latest_index]={**job,'status':'FAILED','error':'语音 Provider 未配置','error_code':'SPEECH_PROVIDER_UNAVAILABLE','updated_at':failed};audio_production_store.save(nid,latest);raise HTTPException(503,{'code':'SPEECH_PROVIDER_UNAVAILABLE','message':'语音 Provider 未配置'})
    except Exception:
        latest=audio_production_store.load(nid); latest_index=next((i for i,item in enumerate(latest['jobs']) if item.get('id')==job_id),None)
        if latest_index is not None and latest['jobs'][latest_index].get('status')=='CANCELLED': return latest['jobs'][latest_index]
        state=latest; jobs=state['jobs']; index=latest_index if latest_index is not None else index
        failed=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(); jobs[index]={**job,'status':'FAILED','error':'语音服务请求失败','error_code':'SPEECH_SYNTHESIS_FAILED','updated_at':failed}; state['jobs']=jobs; audio_production_store.save(nid,state); raise HTTPException(502,{'code':'SPEECH_SYNTHESIS_FAILED','message':'语音服务请求失败'})
@router.post("/novels/{nid}/audiobook/jobs/consume")
def consume_audiobook_jobs(nid:str,body:AudiobookConsumeIn|None=None,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    _authorize_media_novel(nid,x_session_token,"domain.write")
    from datetime import datetime,timezone,timedelta
    from .dependencies import repositories
    repositories.novels.get(nid); config=body or AudiobookConsumeIn(); state=audio_production_store.load(nid); now=datetime.now(timezone.utc); recovered=[]
    if config.recover_stale:
        cutoff=now-timedelta(seconds=config.stale_after_seconds)
        for index,job in enumerate(state['jobs']):
            if job.get('status')!='RUNNING': continue
            try: updated=datetime.fromisoformat(str(job.get('updated_at') or job.get('started_at')).replace('Z','+00:00'))
            except (TypeError,ValueError): continue
            if updated<=cutoff:
                state['jobs'][index]={**job,'status':'QUEUED','updated_at':now.isoformat(),'recovered_at':now.isoformat(),'recovery_count':int(job.get('recovery_count') or 0)+1,'error':None,'error_code':None}; recovered.append(str(job.get('id')))
        if recovered: audio_production_store.save(nid,state)
    queued=[str(job.get('id')) for job in audio_production_store.load(nid)['jobs'] if job.get('status')=='QUEUED'][:config.limit]; results=[]
    for queued_id in queued:
        try: execute_audiobook_job(nid,queued_id,x_session_token)
        except HTTPException: pass
        persisted=next(item for item in audio_production_store.load(nid)['jobs'] if item.get('id')==queued_id)
        results.append({'id':queued_id,'status':persisted.get('status'),'error_code':persisted.get('error_code')})
    remaining=sum(1 for job in audio_production_store.load(nid)['jobs'] if job.get('status')=='QUEUED')
    return {'novel_id':nid,'requested':config.limit,'processed':len(results),'recovered':recovered,'results':results,'remaining_queued':remaining,'execution':'SYNCHRONOUS_USER_TRIGGERED'}
@router.post("/novels/{nid}/speech-generations/import",status_code=202)
def import_generated_speech(nid:str,body:dict,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    _authorize_media_novel(nid,x_session_token,"domain.write")
    import base64
    from .net_safety import fetch_outbound_bytes,OutboundURLRejected
    url=str(body.get('audio_uri','')).strip()
    if not url: raise HTTPException(400,'audio_uri is required')
    try:
        data=fetch_outbound_bytes(url,asset_library_service.MAX_BYTES,30)
        asset=asset_library_service.create(nid,str(body.get('filename') or 'generated-speech.mp3'),base64.b64encode(data).decode('ascii'),'audio/mpeg','audio',f"speech-generation:{url}")
        if body.get('character_id'):
            asset['character_id']=body['character_id']
            from .repository import atomic_write
            atomic_write(asset_library_service._meta_path(asset['id']),__import__('json').dumps(asset,ensure_ascii=False,indent=2))
        return asset
    except OutboundURLRejected as exc: raise HTTPException(400,{'code':'OUTBOUND_URL_REJECTED','message':str(exc)})
    except Exception: raise HTTPException(502,{'code':'AUDIO_IMPORT_FAILED','message':'音频导入失败'})
@router.post("/novels/{nid}/image-generations/import",status_code=202)
def import_generated_image(nid:str,body:dict):
    import base64
    from .net_safety import fetch_outbound_bytes,OutboundURLRejected
    url=str(body.get('asset_uri','')).strip()
    if not url: raise HTTPException(400,'asset_uri is required')
    try:
        if url.startswith('data:image/'):
            match=re.fullmatch(r'data:(image/[A-Za-z0-9.+-]+);base64,([A-Za-z0-9+/=\r\n]+)',url)
            if not match: raise ValueError('invalid image data URI')
            data=base64.b64decode(match.group(2),validate=True)
            if not data or len(data)>asset_library_service.MAX_BYTES: raise ValueError('image data exceeds limit')
        else:data=fetch_outbound_bytes(url,asset_library_service.MAX_BYTES,30)
        source_key=hashlib.sha256(url.encode('utf-8')).hexdigest()
        asset=asset_library_service.create(nid,str(body.get('filename') or 'generated-image.png'),base64.b64encode(data).decode('ascii'),'image/png','image',f"image-generation:{source_key}")
        links={key:body.get(key) for key in ('character_id','scene_id') if body.get(key)}
        if links:
            asset.update(links)
            from .repository import atomic_write
            atomic_write(asset_library_service._meta_path(asset['id']),__import__('json').dumps(asset,ensure_ascii=False,indent=2))
        return asset
    except OutboundURLRejected as exc: raise HTTPException(400,{'code':'OUTBOUND_URL_REJECTED','message':str(exc)})
    except Exception: raise HTTPException(502,{'code':'IMAGE_IMPORT_FAILED','message':'图片导入失败'})
@router.get("/novels/{nid}/visual-memories")
def list_visual_memories(nid:str,character_id:str|None=None,scene_id:str|None=None):
    from .dependencies import repositories
    novel=repositories.novels.get(nid)
    items=[item for item in list(novel.get('visual_memories',[])) if (not character_id or item.get('character_id')==character_id) and (not scene_id or item.get('scene_id')==scene_id)]
    return {'novel_id':nid,'items':items[-50:]}
class MotionTaskStatusIn(BaseModel): status:str=Field(pattern="^(PENDING|CANCELLED)$")
class MotionFramesIn(BaseModel): start_frame:str|None=None; end_frame:str|None=None; constraints:dict[str,object]={}
class MotionProviderIn(BaseModel): provider_id:str=Field(min_length=1); model_id:str='video-placeholder'
@router.put("/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}")
def update_motion_task(nid:str,screenplay_id:str,task_id:str,body:MotionTaskStatusIn,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    _authorize_media_novel(nid,x_session_token,"domain.write");return guard(screenplay_service.update_motion_task,nid,screenplay_id,task_id,body.status)
@router.put("/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/frames")
def update_motion_frames(nid:str,screenplay_id:str,task_id:str,body:MotionFramesIn,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    _authorize_media_novel(nid,x_session_token,"domain.write")
    result=guard(screenplay_service.update_motion_frames,nid,screenplay_id,task_id,body.start_frame,body.end_frame)
    if isinstance(result,dict) and body.constraints: result={**result,"constraints":body.constraints}
    return result
@router.put("/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/provider")
def update_motion_provider(nid:str,screenplay_id:str,task_id:str,body:MotionProviderIn,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    _authorize_media_novel(nid,x_session_token,"domain.write");return guard(screenplay_service.update_motion_provider,nid,screenplay_id,task_id,body.provider_id,body.model_id)
@router.post("/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/execute")
def execute_motion_task(nid:str,screenplay_id:str,task_id:str,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    _authorize_media_novel(nid,x_session_token,"domain.write");return guard(screenplay_service.execute_motion_task,nid,screenplay_id,task_id)
@router.post("/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/cancel")
def cancel_motion_task(nid:str,screenplay_id:str,task_id:str,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    _authorize_media_novel(nid,x_session_token,"domain.write");return guard(screenplay_service.cancel_motion_task,nid,screenplay_id,task_id)
@router.post("/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/retry")
def retry_motion_task(nid:str,screenplay_id:str,task_id:str,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    _authorize_media_novel(nid,x_session_token,"domain.write");return guard(screenplay_service.retry_motion_task,nid,screenplay_id,task_id)
class MotionResultIn(BaseModel):
    url:str=Field(min_length=1,max_length=4000)
    media_type:str='video/mp4'
    @field_validator('url')
    @classmethod
    def validate_url(cls,value):
        if not value.strip().lower().startswith(('https://','http://')): raise ValueError('video result URL must use http or https')
        return value.strip()
    @field_validator('media_type')
    @classmethod
    def validate_media_type(cls,value):
        if not value.startswith('video/'): raise ValueError('media_type must be video/*')
        return value
class MotionCallbackIn(BaseModel): status:str; progress:int=Field(default=0,ge=0,le=100); url:str|None=None; error:str|None=None
@router.put("/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/result")
def attach_motion_result(nid:str,screenplay_id:str,task_id:str,body:MotionResultIn,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    _authorize_media_novel(nid,x_session_token,"domain.write");return guard(screenplay_service.attach_motion_result,nid,screenplay_id,task_id,body.url,body.media_type)
@router.post("/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/callback")
def motion_callback(nid:str,screenplay_id:str,task_id:str,body:MotionCallbackIn,x_video_callback_token:str|None=Header(None)):
    expected=os.getenv('VIDEO_CALLBACK_TOKEN','').strip()
    if not expected: raise HTTPException(401,{"code":"VIDEO_CALLBACK_TOKEN_REQUIRED"})
    if not x_video_callback_token or not hmac.compare_digest(x_video_callback_token,expected): raise HTTPException(401,{"code":"INVALID_VIDEO_CALLBACK_TOKEN"})
    return guard(screenplay_service.motion_callback,nid,screenplay_id,task_id,body.status,body.progress,body.url,body.error)
class RemoteMotionTaskIn(BaseModel): remote_task_id:str=Field(min_length=1,max_length=400)
@router.put("/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/remote-id")
def set_remote_motion_task_id(nid:str,screenplay_id:str,task_id:str,body:RemoteMotionTaskIn,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    _authorize_media_novel(nid,x_session_token,"domain.write");return guard(screenplay_service.set_remote_motion_task_id,nid,screenplay_id,task_id,body.remote_task_id)
@router.post("/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/sync")
def sync_motion_task(nid:str,screenplay_id:str,task_id:str,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    _authorize_media_novel(nid,x_session_token,"domain.write");return guard(screenplay_service.sync_motion_task,nid,screenplay_id,task_id)
@router.get("/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/result-history")
def motion_result_history(nid:str,screenplay_id:str,task_id:str):return guard(screenplay_service.motion_result_history,nid,screenplay_id,task_id)
@router.get("/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/asset-reference")
def motion_asset_reference(nid:str,screenplay_id:str,task_id:str):return guard(screenplay_service.motion_asset_reference,nid,screenplay_id,task_id)
@router.post("/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/import-asset",status_code=202)
def import_motion_asset(nid:str,screenplay_id:str,task_id:str,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    _authorize_media_novel(nid,x_session_token,"domain.write");return guard(screenplay_service.import_motion_asset_reference,nid,screenplay_id,task_id)
@router.get("/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/import-asset")
def motion_asset_import_status(nid:str,screenplay_id:str,task_id:str):return guard(screenplay_service.motion_asset_import_status,nid,screenplay_id,task_id)
@router.get("/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/import-assets")
def list_motion_asset_imports(nid:str,screenplay_id:str):return guard(screenplay_service.list_motion_asset_imports,nid,screenplay_id)
@router.post("/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/import-assets/retry")
def retry_failed_motion_asset_imports(nid:str,screenplay_id:str,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    _authorize_media_novel(nid,x_session_token,"domain.write");return guard(screenplay_service.retry_failed_motion_asset_imports,nid,screenplay_id)
@router.post("/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/import-asset/download",status_code=202)
def download_motion_asset(nid:str,screenplay_id:str,task_id:str,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    _authorize_media_novel(nid,x_session_token,"domain.write");return guard(screenplay_service.download_motion_asset,nid,screenplay_id,task_id,asset_library_service)
@router.post("/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/import-asset/retry")
def retry_motion_asset_import(nid:str,screenplay_id:str,task_id:str,x_session_token:str|None=Header(None,alias="X-Session-Token")):
    _authorize_media_novel(nid,x_session_token,"domain.write");return guard(screenplay_service.retry_motion_asset_import,nid,screenplay_id,task_id)
@router.get("/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}/frame-history")
def motion_frame_history(nid:str,screenplay_id:str,task_id:str):return guard(screenplay_service.motion_frame_history,nid,screenplay_id,task_id)
@router.get("/novels/{nid}/screenplays/{screenplay_id}/visual-continuity")
def visual_continuity(nid:str,screenplay_id:str):return guard(screenplay_service.validate_visual_continuity,nid,screenplay_id)
@router.get("/novels/{nid}/screenplays/{screenplay_id}/pipeline-status")
def screenplay_pipeline_status(nid:str,screenplay_id:str):return guard(screenplay_service.pipeline_status,nid,screenplay_id)
@router.post("/novels/{nid}/screenplays/{screenplay_id}/pipeline-advance")
def advance_screenplay_pipeline(nid:str,screenplay_id:str):return guard(screenplay_service.advance_pipeline,nid,screenplay_id)
@router.post("/novels/{nid}/screenplays/{screenplay_id}/pipeline-advance-until-gate")
def advance_screenplay_pipeline_until_gate(nid:str,screenplay_id:str,max_steps:int=10):return guard(screenplay_service.advance_pipeline_until_gate,nid,screenplay_id,max_steps)
@router.post("/novels/{nid}/screenplays/{screenplay_id}/assets",status_code=201)
def plan_assets(nid:str,screenplay_id:str):return guard(screenplay_service.plan_assets,nid,screenplay_id)
@router.post("/novels/{nid}/screenplays/{screenplay_id}/assets/approve")
def approve_assets(nid:str,screenplay_id:str):return guard(screenplay_service.approve_assets,nid,screenplay_id)
@router.put("/novels/{nid}/screenplays/{screenplay_id}/assets/{asset_id}")
def update_asset(nid:str,screenplay_id:str,asset_id:str,body:AssetRequirementIn):return guard(screenplay_service.update_asset,nid,screenplay_id,asset_id,body.model_dump())
@router.post("/novels/{nid}/screenplays/{screenplay_id}/asset-tasks",status_code=201)
def create_asset_tasks(nid:str,screenplay_id:str):return guard(screenplay_service.create_asset_tasks,nid,screenplay_id)
@router.put("/novels/{nid}/screenplays/{screenplay_id}/asset-tasks/{task_id}")
def update_asset_task(nid:str,screenplay_id:str,task_id:str,body:AssetTaskIn):return guard(screenplay_service.update_asset_task,nid,screenplay_id,task_id,body.model_dump())
@router.post("/novels/{nid}/screenplays/{screenplay_id}/asset-tasks/{task_id}/execute")
def execute_asset_task(nid:str,screenplay_id:str,task_id:str):return guard(screenplay_service.execute_asset_task,nid,screenplay_id,task_id)
@router.post("/novels/{nid}/screenplays/{screenplay_id}/asset-tasks/{task_id}/retry")
def retry_asset_task(nid:str,screenplay_id:str,task_id:str):return guard(screenplay_service.retry_asset_task,nid,screenplay_id,task_id)
@router.post("/novels/{nid}/screenplays/{screenplay_id}/asset-tasks/recover")
def recover_asset_tasks(nid:str,screenplay_id:str):return guard(screenplay_service.recover_asset_tasks,nid,screenplay_id)
@router.post("/novels/{nid}/asset-tasks/recover")
def recover_all_asset_tasks(nid:str):return guard(screenplay_service.recover_all_asset_tasks,nid)
@router.post("/novels/{nid}/screenplays/{screenplay_id}/asset-tasks/cleanup")
def cleanup_asset_tasks(nid:str,screenplay_id:str):return guard(screenplay_service.cleanup_asset_tasks,nid,screenplay_id)
@router.get("/novels/{nid}/asset-tasks/stats")
def asset_task_stats(nid:str):return guard(screenplay_service.asset_task_stats,nid)
@router.get("/novels/{nid}/screenplays/{screenplay_id}/asset-tasks/stats")
def screenplay_asset_task_stats(nid:str,screenplay_id:str):return guard(screenplay_service.asset_task_stats,nid,screenplay_id)
@router.post("/novels/{nid}/asset-tasks/claim")
def claim_asset_tasks(nid:str,limit:int=10,provider_id:str|None=None):return guard(screenplay_service.claim_asset_tasks,nid,limit,provider_id)
@router.post("/novels/{nid}/asset-tasks/dispatch")
def dispatch_asset_tasks(nid:str,limit:int=10,execute:bool=False,provider_id:str|None=None):return guard(screenplay_service.dispatch_asset_tasks,nid,limit,execute,provider_id)
@router.post("/novels/{nid}/asset-tasks/timeout")
def timeout_asset_tasks(nid:str,timeout_seconds:int=3600):return guard(screenplay_service.timeout_asset_tasks,nid,timeout_seconds)
@router.post("/novels/{nid}/asset-tasks/worker/run-once")
def run_asset_task_worker(nid:str,limit:int=10,execute:bool=False,provider_id:str|None=None,timeout_seconds:int=3600,x_session_token:str|None=Header(None)):
    if execute and settings.enable_packaged_runtime:
        if not x_session_token:
            raise HTTPException(401,{"code":"SESSION_REQUIRED"})
        try: trusted_session_resolver.resolve(x_session_token)
        except Exception as exc: raise HTTPException(401,{"code":"INVALID_SESSION"}) from exc
    return guard(asset_task_worker.run_once,nid,limit,execute,provider_id,timeout_seconds)
@router.post("/novels/{nid}/asset-tasks/worker/start")
def start_asset_task_worker(nid:str,limit:int|None=None,execute:bool|None=None,provider_id:str|None=None,timeout_seconds:int|None=None,interval_seconds:float|None=None,x_session_token:str|None=Header(None)):
    cfg=load_asset_worker_config(); limit=cfg["limit"] if limit is None else limit; execute=cfg["execute"] if execute is None else execute; timeout_seconds=cfg["timeout_seconds"] if timeout_seconds is None else timeout_seconds; interval_seconds=cfg["interval_seconds"] if interval_seconds is None else interval_seconds
    if execute and settings.enable_packaged_runtime:
        if not x_session_token:
            raise HTTPException(401,{"code":"SESSION_REQUIRED"})
        try: trusted_session_resolver.resolve(x_session_token)
        except Exception as exc: raise HTTPException(401,{"code":"INVALID_SESSION"}) from exc
    return guard(asset_task_worker.start,nid,limit=limit,execute=execute,provider_id=provider_id,timeout_seconds=timeout_seconds,interval_seconds=interval_seconds)
@router.post("/novels/{nid}/asset-tasks/worker/stop")
def stop_asset_task_worker(nid:str): return asset_task_worker.stop()
@router.get("/novels/{nid}/asset-tasks/worker/status")
def asset_task_worker_status(nid:str): return asset_task_worker.status()
@router.get("/asset-tasks/worker/config")
def asset_task_worker_config(): return load_asset_worker_config()
@router.put("/asset-tasks/worker/config")
def update_asset_task_worker_config(body:AssetWorkerConfigIn):
    try: return save_asset_worker_config(**{k:v for k,v in body.model_dump().items() if v is not None})
    except (TypeError, ValueError) as exc: raise HTTPException(400,{"code":"INVALID_WORKER_CONFIG","message":str(exc)}) from exc

@router.post("/projects/{project_id}/continuity/checks")
def continuity_checks(project_id:str, body:ContinuityCheckIn):
    if not settings.enable_continuity_rules:
        return {"status":"DISABLED","findings":[]}
    from .lore.continuity import TimelineEvent, CharacterLocationState, CharacterKnowledge
    findings=continuity_finding_service.run_checks(project_id, events=[TimelineEvent.model_validate(x) for x in body.events], locations=[CharacterLocationState.model_validate(x) for x in body.locations], knowledge=[CharacterKnowledge.model_validate(x) for x in body.knowledge], used_subject_ids=set(body.used_subject_ids))
    serialized=json.dumps([body.events,body.locations,body.knowledge],ensure_ascii=False)
    findings.extend(world_rule_violations(project_id, serialized, body.world_rules))
    normalized=[f.model_dump(mode="json") if hasattr(f,"model_dump") else f for f in findings]
    return {"status":"COMPLETED","findings":normalized}

@router.post("/novels/{nid}/continuity/scan-chapter")
def scan_chapter_continuity(nid:str, body:ContinuityScanChapterIn|None=None):
    payload = body or ContinuityScanChapterIn()
    try:
        novel_service.get(nid)
    except FileNotFoundError:
        raise HTTPException(404, "novel not found")
    chapters = chapter_service.list(nid)
    if payload.chapter_id:
        try:
            chapter = chapter_service.get(payload.chapter_id)
        except FileNotFoundError:
            raise HTTPException(404, {"code": "CHAPTER_NOT_FOUND"})
        if chapter.get("novel_id") != nid:
            raise HTTPException(404, {"code": "CHAPTER_NOT_FOUND"})
    elif payload.chapter is not None:
        listed = next((item for item in chapters if item.get("number") == payload.chapter), None)
        if listed is None:
            raise HTTPException(404, {"code": "CHAPTER_NOT_FOUND"})
        chapter = chapter_service.get(listed["id"])
    else:
        if not chapters:
            raise HTTPException(400, {"code": "CHAPTER_REQUIRED", "message": "请先新建或选择一个章节"})
        chapter = chapter_service.get(chapters[0]["id"])
    draft = chapter.get("content") or ""
    chapter_number = int(chapter.get("number") or 1)
    characters = novel_service.data_set(nid, "characters")
    locations = novel_service.data_set(nid, "locations")
    timeline = novel_service.data_set(nid, "timeline")
    foreshadowing_rows = novel_service.data_set(nid, "foreshadowing")
    world_rules = [
        row for row in lore_service.repository.list_proposals(nid)
        if row.get("proposal_type") == "WORLD_RULE" and not row.get("deleted_at")
    ]
    from .review import deterministic_review
    from .lore.continuity import TimelineEvent, CharacterLocationState
    findings: list[dict] = []
    findings.extend(world_rule_violations(nid, draft, world_rules))
    for index, item in enumerate(deterministic_review(draft, {"characters": characters, "chapter": chapter_number})):
        findings.append({
            "id": f"CHARACTER:{index}:{item.get('code')}",
            "project_id": nid,
            "finding_type": "CHARACTER_CONSISTENCY",
            "severity": item.get("severity", "ERROR"),
            "description": item.get("message", ""),
            "code": item.get("code"),
            "subject_type": "CHARACTER",
        })
    engine_status = "DISABLED"
    if settings.enable_continuity_rules:
        engine_status = "COMPLETED"
        events = []
        for row in timeline:
            start = row.get("start_time") or row.get("time") or None
            end = row.get("end_time") or None
            events.append(TimelineEvent.model_validate({
                "id": str(row.get("id") or uuid.uuid4()),
                "project_id": nid,
                "event_type": row.get("event_type") or "STORY",
                "title": row.get("title") or "untitled",
                "description": row.get("description") or "",
                "start_time": start or None,
                "end_time": end or None,
                "sequence_index": row.get("sequence"),
                "location_id": row.get("location_id") or row.get("location") or None,
                "certainty": "CONFIRMED" if row.get("status") in {"CONFIRMED", "ACTIVE"} else "UNKNOWN",
                "source_chapter_version_id": row.get("chapter_id") or None,
            }))
        loc_by_name = {str(item.get("name")): item.get("id") for item in locations if item.get("name")}
        location_states = []
        for person in characters:
            loc_name = person.get("current_location") or ""
            loc_id = person.get("location_id") or loc_by_name.get(loc_name)
            if not loc_id:
                continue
            location_states.append(CharacterLocationState.model_validate({
                "id": f"loc-{person.get('id')}",
                "project_id": nid,
                "character_id": person.get("id") or person.get("name"),
                "location_id": loc_id,
                "state": "PRESENT",
                "certainty": "ESTIMATED",
            }))
        used_subject_ids = {
            str(person.get("id") or person.get("name"))
            for person in characters
            if person.get("name") and person["name"] in draft
        }
        engine_findings = continuity_finding_service.run_checks(
            nid,
            events=events,
            locations=location_states,
            knowledge=[],
            used_subject_ids=used_subject_ids,
        )
        findings.extend(item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in engine_findings)
    reminders = summarize_foreshadowing(foreshadowing_rows, chapter_number)
    return {
        "status": "COMPLETED",
        "placeholder": False,
        "engine_status": engine_status,
        "execution_label": "契约校验，未调用模型",
        "model_called": False,
        "chapter": {
            "id": chapter["id"],
            "number": chapter_number,
            "title": chapter.get("title"),
            "word_count": chapter.get("word_count") or len(draft),
        },
        "scanned": {
            "characters": len(characters),
            "locations": len(locations),
            "timeline": len(timeline),
            "world_rules": len(world_rules),
            "foreshadowing": len(foreshadowing_rows),
        },
        "findings": findings,
        "foreshadowing": reminders,
    }

@router.post("/novels/{nid}/characters/consistency-check")
def character_consistency_check(nid: str, body: CharacterConsistencyIn):
    try:
        novel_service.get(nid)
    except FileNotFoundError:
        raise HTTPException(404, "novel not found")
    from .review import deterministic_review
    issues = deterministic_review(body.draft, {"characters": body.characters, "chapter": body.chapter, "forbidden_secrets": body.forbidden_secrets})
    return {"status": "COMPLETED", "findings": [{"id": f"CHARACTER:{index}:{item.get('code')}", "finding_type": "CHARACTER_CONSISTENCY", "severity": item.get("severity", "ERROR"), "description": item.get("message", ""), "code": item.get("code")} for index, item in enumerate(issues)]}

@router.get("/projects/{project_id}/continuity/findings")
def continuity_findings(project_id:str, character_id:str|None=None, finding_type:str|None=None):
    rows=continuity_finding_service.list_findings(project_id)
    if character_id: rows=[x for x in rows if x.get("subject_id")==character_id]
    if finding_type: rows=[x for x in rows if x.get("finding_type")==finding_type]
    return rows

@router.get("/projects/{project_id}/continuity/findings/{finding_id}")
def continuity_finding(project_id:str, finding_id:str):
    row=guard(continuity_finding_service.get_finding,finding_id)
    if row.get("project_id")!=project_id: raise HTTPException(404,"Finding not found")
    return row

@router.post("/projects/{project_id}/continuity/findings/{finding_id}/resolve")
def resolve_continuity_finding(project_id:str,finding_id:str):
    try:return continuity_finding_service.resolve(project_id,finding_id)
    except KeyError:raise HTTPException(404,"Finding not found")

@router.post("/projects/{project_id}/narrative/threads",status_code=201)
def create_narrative_thread(project_id:str,body:NarrativeThreadIn):
    from .narrative import PlotThread
    return guard(narrative_state_service.create_thread,PlotThread(body.id,project_id,body.title,description=body.description))

@router.post("/projects/{project_id}/narrative/foreshadowing",status_code=201)
def create_narrative_foreshadowing(project_id:str,body:NarrativeForeshadowingIn):
    from .narrative import Foreshadowing
    return guard(narrative_state_service.create_foreshadowing,Foreshadowing(body.id,project_id,body.title,thread_id=body.thread_id))

@router.get("/projects/{project_id}/narrative/state")
def narrative_state(project_id:str):return narrative_state_service.state(project_id)

@router.post("/projects/{project_id}/narrative/mysteries",status_code=201)
def create_mystery(project_id:str,body:MysteryIn):
    from .narrative import Mystery
    return guard(narrative_state_service.create_mystery,Mystery(body.id,project_id,body.title,body.description,opened_chapter_version_id=body.opened_chapter_version_id))
@router.get("/projects/{project_id}/narrative/mysteries")
def list_mysteries(project_id:str):return narrative_state_service.list_mysteries(project_id)
@router.get("/projects/{project_id}/narrative/mysteries/{item_id}")
def get_mystery(project_id:str,item_id:str):
    try:return narrative_state_service.get_mystery(project_id,item_id)
    except KeyError:raise HTTPException(404,"Mystery not found")
@router.post("/projects/{project_id}/narrative/mysteries/{item_id}/transition")
def transition_mystery_api(project_id:str,item_id:str,body:NarrativeStatusIn):
    try:return _legacy_revision_state(project_id,body.expected_revision).transition_mystery(project_id,item_id,body.status,body.chapter_version_id)
    except KeyError:raise HTTPException(404,"Mystery not found")
    except RevisionConflict as exc:raise _revision_error(exc)
    except ValueError as exc:raise HTTPException(400,str(exc))

@router.post("/projects/{project_id}/narrative/character-goals",status_code=201)
def create_character_goal(project_id:str,body:CharacterGoalIn):
    from .narrative import CharacterGoal
    return guard(narrative_state_service.create_character_goal,CharacterGoal(body.id,project_id,body.character_id,body.title,body.description,started_chapter_version_id=body.started_chapter_version_id))
@router.get("/projects/{project_id}/narrative/character-goals")
def list_character_goals(project_id:str):return narrative_state_service.list_character_goals(project_id)
@router.get("/projects/{project_id}/narrative/character-goals/{item_id}")
def get_character_goal(project_id:str,item_id:str):
    try:return narrative_state_service.get_character_goal(project_id,item_id)
    except KeyError:raise HTTPException(404,"Character goal not found")
@router.post("/projects/{project_id}/narrative/character-goals/{item_id}/transition")
def transition_character_goal_api(project_id:str,item_id:str,body:NarrativeStatusIn):
    try:return _legacy_revision_state(project_id,body.expected_revision).transition_character_goal(project_id,item_id,body.status,body.chapter_version_id)
    except KeyError:raise HTTPException(404,"Character goal not found")
    except RevisionConflict as exc:raise _revision_error(exc)
    except ValueError as exc:raise HTTPException(400,str(exc))

@router.post("/projects/{project_id}/narrative/chapter-progress",status_code=201)
def record_chapter_progress(project_id:str,body:ChapterNarrativeProgressIn):
    from .narrative import ChapterNarrativeLink,NarrativeEntityType,NarrativeProgressType
    try:return _legacy_revision_state(project_id,body.expected_revision).record_chapter_narrative_progress(ChapterNarrativeLink(body.id,project_id,body.chapter_id,body.chapter_version,NarrativeEntityType(body.entity_type),body.entity_id,NarrativeProgressType(body.progress_type),body.summary,tuple(body.evidence_ids),body.event_id))
    except (KeyError,FileNotFoundError):raise HTTPException(404,"Narrative progress dependency not found")
    except RevisionConflict as exc:raise _revision_error(exc)
    except ValueError as exc:raise HTTPException(400,str(exc))
@router.get("/projects/{project_id}/narrative/chapter-progress")
def list_chapter_progress(project_id:str,chapter_id:str|None=None,entity_type:str|None=None,entity_id:str|None=None):
    rows=narrative_state_service.list_chapter_progress(project_id)
    if chapter_id:rows=[x for x in rows if x["chapter_id"]==chapter_id]
    if entity_type:rows=[x for x in rows if x["entity_type"]==entity_type]
    if entity_id:rows=[x for x in rows if x["entity_id"]==entity_id]
    return rows

@router.post("/projects/{project_id}/narrative/proposals",status_code=201)
def create_narrative_proposal(project_id:str,body:NarrativeProposalIn):
    from .narrative import NarrativeChangeProposal,NarrativeEntityType,NarrativeProposalPayload,NarrativeProposalType
    try:return narrative_proposal_service.create_proposal(NarrativeChangeProposal(body.id,project_id,NarrativeProposalType(body.proposal_type),NarrativeEntityType(body.subject_type),body.subject_id,body.chapter_version_id,NarrativeProposalPayload(**body.payload),tuple(body.evidence_ids),body.summary))
    except (KeyError,FileNotFoundError):raise HTTPException(404,"Narrative proposal dependency not found")
    except (TypeError,ValueError) as exc:raise HTTPException(400,str(exc))
@router.get("/projects/{project_id}/narrative/proposals")
def list_narrative_proposals(project_id:str,status:str|None=None):
    try:return narrative_proposal_service.list_proposals(project_id,status)
    except ValueError as exc:raise HTTPException(400,str(exc))
@router.get("/projects/{project_id}/narrative/proposals/{proposal_id}")
def get_narrative_proposal(project_id:str,proposal_id:str):
    try:return narrative_proposal_service.get_proposal(project_id,proposal_id)
    except KeyError:raise HTTPException(404,"Narrative proposal not found")
@router.post("/projects/{project_id}/narrative/proposals/{proposal_id}/accept")
def accept_narrative_proposal(project_id:str,proposal_id:str,body:RevisionWriteIn|None=None):
    from .services.narrative_proposal_service import NarrativeProposalService
    try:
        state=_legacy_revision_state(project_id,body.expected_revision if body else None)
        service=narrative_proposal_service if state is narrative_state_service else NarrativeProposalService(state.repository,state)
        return service.accept_proposal(project_id,proposal_id)
    except KeyError:raise HTTPException(404,"Narrative proposal not found")
    except RevisionConflict as exc:raise _revision_error(exc)
    except (FileNotFoundError,ValueError) as exc:raise HTTPException(400,str(exc))
@router.post("/projects/{project_id}/narrative/proposals/{proposal_id}/reject")
def reject_narrative_proposal(project_id:str,proposal_id:str):
    try:return narrative_proposal_service.reject_proposal(project_id,proposal_id)
    except KeyError:raise HTTPException(404,"Narrative proposal not found")
    except ValueError as exc:raise HTTPException(400,str(exc))

def _narrative_event(project_id,subject_id,body):
    from .narrative import NarrativeEvent
    return NarrativeEvent(body.event_id,project_id,body.event_type,subject_id,body.chapter_version_id,tuple(body.evidence_ids),body.payload)

@router.post("/projects/{project_id}/narrative/threads/{thread_id}/transition")
def transition_narrative_thread(project_id:str,thread_id:str,body:NarrativeTransitionIn):return guard(_legacy_revision_state(project_id,body.expected_revision).transition_thread,project_id,thread_id,body.status,_narrative_event(project_id,thread_id,body))

@router.post("/projects/{project_id}/narrative/foreshadowing/{item_id}/transition")
def transition_narrative_foreshadowing(project_id:str,item_id:str,body:NarrativeTransitionIn):return guard(_legacy_revision_state(project_id,body.expected_revision).transition_foreshadowing,project_id,item_id,body.status,_narrative_event(project_id,item_id,body))

@router.post("/projects/{project_id}/narrative/expectations",status_code=201)
def create_narrative_expectation(project_id:str,body:NarrativeExpectationIn):
    from .narrative_detection import NarrativeExpectation
    try:narrative_state_service.get_subject(project_id,body.subject_type,body.subject_id)
    except KeyError:raise HTTPException(404,"Narrative subject not found")
    except ValueError as exc:raise HTTPException(400,str(exc))
    if body.expectation_type in {"MYSTERY_ANSWER_BY","CHARACTER_GOAL_PROGRESS_BY"}:
        try:narrative_state_service.validate_expectation_provenance(project_id,body.source_chapter_version_id,body.evidence_ids)
        except FileNotFoundError:raise HTTPException(404,"Expectation provenance not found")
        except ValueError as exc:raise HTTPException(400,str(exc))
    return guard(narrative_finding_service.create_expectation,NarrativeExpectation(body.id,project_id,body.subject_type,body.subject_id,body.expectation_type,body.deadline_chapter,tuple(body.evidence_ids),body.source_chapter_version_id,body.active))

@router.post("/projects/{project_id}/narrative/checks")
def check_narrative_findings(project_id:str,body:NarrativeCheckIn):
    from .narrative_detection import NarrativeExpectation,NarrativeRuleContext
    expectations=[NarrativeExpectation(**x) for x in narrative_finding_service.repository.list(project_id,"expectations")]
    state=narrative_state_service.state(project_id)
    findings=narrative_finding_service.run_checks(NarrativeRuleContext(project_id,body.current_chapter,expectations,thread_last_progress=body.thread_last_progress,foreshadowing_payoff_chapter=body.foreshadowing_payoff_chapter,mysteries=state["mysteries"],character_goals=state["character_goals"],narrative_events=state["events"]))
    return [vars(x) for x in findings]

@router.get("/projects/{project_id}/narrative/findings")
def list_narrative_findings(project_id:str):return narrative_finding_service.list_findings(project_id)

@router.get("/projects/{project_id}/narrative/findings/{finding_id}")
def get_narrative_finding(project_id:str,finding_id:str):
    try:return narrative_finding_service.get_finding(project_id,finding_id)
    except KeyError:raise HTTPException(404,"Finding not found")

@router.post("/projects/{project_id}/narrative/findings/{finding_id}/resolve")
def resolve_narrative_finding(project_id:str,finding_id:str):
    try:return narrative_finding_service.resolve(project_id,finding_id)
    except KeyError:raise HTTPException(404,"Finding not found")

# ---------------------------------------------------------------------------
# V1 capability closures (metadata-only, local-first)
# ---------------------------------------------------------------------------

@router.get("/novels/{nid}/overview")
def novel_overview(nid: str):
    return capability_guard(v1_capability_service.overview, nid)
@router.get("/novels/{nid}/writing-goal")
def writing_goal(nid:str): return guard(novel_service.writing_goal,nid)
@router.put("/novels/{nid}/writing-goal")
def update_writing_goal(nid:str,body:WritingGoalIn): return guard(novel_service.update_writing_goal,nid,body.model_dump())


@router.get("/novels/{nid}/research")
def novel_research(nid: str, status: str | None = None, source_type: str | None = None, tag: str | None = None):
    return capability_guard(v1_capability_service.list_research, nid, status, source_type, tag)


@router.post("/novels/{nid}/research", status_code=201)
def create_novel_research(nid: str, body: ResearchRecordIn,
                          idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    return capability_guard(v1_capability_service.create_research, nid, body, idempotency_key)


@router.get("/research")
def research_index(novel_id: str = Query(...), status: str | None = None, source_type: str | None = None,
                   tag: str | None = None):
    return capability_guard(v1_capability_service.list_research, novel_id, status, source_type, tag)


@router.get("/novels/{nid}/research/{research_id}")
def get_novel_research(nid: str, research_id: str):
    return capability_guard(v1_capability_service._get, "research", research_id, nid)


@router.put("/novels/{nid}/research/{research_id}")
def update_novel_research(nid: str, research_id: str, body: ResearchRecordIn,
                          expected_version: int | None = Query(default=None, ge=1)):
    return capability_guard(v1_capability_service.update_research, nid, research_id, body, expected_version)


@router.delete("/novels/{nid}/research/{research_id}")
def delete_novel_research(nid: str, research_id: str, expected_version: int | None = Query(default=None, ge=1)):
    return capability_guard(v1_capability_service.delete_research, nid, research_id, expected_version)


@router.get("/novels/{nid}/character-evolution")
def character_evolution(nid: str, character_id: str | None = None, status: str | None = None):
    return capability_guard(v1_capability_service.list_character_evolution, nid, character_id, status)


@router.post("/novels/{nid}/character-evolution", status_code=201)
def create_character_evolution(nid: str, body: CharacterEvolutionIn,
                               idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    return capability_guard(v1_capability_service.create_character_evolution, nid, body, idempotency_key)


@router.get("/novels/{nid}/character-evolution/{evolution_id}")
def get_character_evolution(nid: str, evolution_id: str):
    return capability_guard(v1_capability_service._get, "character_evolution", evolution_id, nid)


@router.put("/novels/{nid}/character-evolution/{evolution_id}")
def update_character_evolution(nid: str, evolution_id: str, body: CharacterEvolutionIn,
                               expected_version: int | None = Query(default=None, ge=1)):
    return capability_guard(v1_capability_service.update_character_evolution, nid, evolution_id, body, expected_version)


@router.delete("/novels/{nid}/character-evolution/{evolution_id}")
def delete_character_evolution(nid: str, evolution_id: str,
                               expected_version: int | None = Query(default=None, ge=1)):
    return capability_guard(v1_capability_service._delete, "character_evolution", evolution_id,
                            novel_id=nid, expected_version=expected_version,
                            action="CHARACTER_EVOLUTION_DELETED", target_type="CharacterEvolution")


@router.get("/novels/{nid}/characters/{character_id}/evolution")
def character_evolution_for_character(nid: str, character_id: str, status: str | None = None):
    return capability_guard(v1_capability_service.list_character_evolution, nid, character_id, status)


@router.post("/novels/{nid}/characters/{character_id}/evolution", status_code=201)
def create_character_evolution_for_character(nid: str, character_id: str, body: CharacterEvolutionIn,
                                             idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    if body.character_id != character_id:
        raise HTTPException(400, {"code": "CHARACTER_ID_MISMATCH"})
    return capability_guard(v1_capability_service.create_character_evolution, nid, body, idempotency_key)


@router.get("/novels/{nid}/visual-memory")
def visual_memory(nid: str, entity_type: str | None = None, entity_id: str | None = None, status: str | None = None):
    return capability_guard(v1_capability_service.list_visual_memory, nid, entity_type, entity_id, status)


@router.post("/novels/{nid}/visual-memory", status_code=201)
def create_visual_memory(nid: str, body: VisualMemoryIn,
                         idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    return capability_guard(v1_capability_service.create_visual_memory, nid, body, idempotency_key)


@router.get("/memory")
def memory_index(novel_id: str = Query(...), entity_type: str | None = None, entity_id: str | None = None):
    return capability_guard(v1_capability_service.list_visual_memory, novel_id, entity_type, entity_id, None)


@router.post("/memory", status_code=201)
def create_memory_index(novel_id: str = Query(...), body: VisualMemoryIn | None = None,
                        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    if body is None:
        raise HTTPException(400, {"code": "MEMORY_BODY_REQUIRED"})
    return capability_guard(v1_capability_service.create_visual_memory, novel_id, body, idempotency_key)


@router.get("/novels/{nid}/visual-memory/{memory_id}")
def get_visual_memory(nid: str, memory_id: str):
    return capability_guard(v1_capability_service._get, "visual_memory", memory_id, nid)


@router.put("/novels/{nid}/visual-memory/{memory_id}")
def update_visual_memory(nid: str, memory_id: str, body: VisualMemoryIn,
                         expected_version: int | None = Query(default=None, ge=1)):
    return capability_guard(v1_capability_service.update_visual_memory, nid, memory_id, body, expected_version)


@router.delete("/novels/{nid}/visual-memory/{memory_id}")
def delete_visual_memory(nid: str, memory_id: str, expected_version: int | None = Query(default=None, ge=1)):
    return capability_guard(v1_capability_service._delete, "visual_memory", memory_id,
                            novel_id=nid, expected_version=expected_version,
                            action="VISUAL_MEMORY_DELETED", target_type="VisualMemory")


@router.get("/assets/{asset_id}/derivatives")
def asset_derivatives(asset_id: str):
    return capability_guard(v1_capability_service.list_asset_derivatives, asset_id)


@router.post("/assets/{asset_id}/derivatives", status_code=201)
def create_asset_derivative(asset_id: str, body: AssetDerivativeIn,
                            idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    return capability_guard(v1_capability_service.create_asset_derivative, asset_id, body, idempotency_key)


# Existing lore/memory repositories are exposed directly so file and
# PostgreSQL profiles share the same evidence -> proposal -> approved-memory
# contract.  These routes do not infer or auto-approve AI output.
@router.get("/novels/{nid}/lore/evidence")
def list_lore_evidence(nid: str):
    try:
        novel_service.get(nid)
        return {"items": repositories_lore_list_evidence(nid), "storage": settings.storage_backend}
    except Exception as exc:
        return capability_guard(_raise_lore_error, exc)


def repositories_lore_list_evidence(nid: str):
    return lore_service.repository.list_evidence(nid)


def _raise_lore_error(exc):
    raise exc


@router.post("/novels/{nid}/lore/evidence", status_code=201)
def create_lore_evidence(nid: str, body: LoreEvidenceApiIn):
    try:
        novel_service.get(nid)
        evidence_id = body.id or str(uuid.uuid4())
        excerpt = body.excerpt or ""
        digest = body.content_hash or hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
        item = body.model_dump(exclude_none=True)
        item.update({"id": evidence_id, "novel_id": nid, "content_hash": digest})
        return lore_service.create_evidence(item)
    except Exception as exc:
        return capability_guard(_raise_lore_error, exc)


@router.get("/novels/{nid}/lore/proposals")
def list_lore_proposals(nid: str, status: str | None = None):
    try:
        novel_service.get(nid)
        return {"items": lore_service.repository.list_proposals(nid, status), "storage": settings.storage_backend}
    except Exception as exc:
        return capability_guard(_raise_lore_error, exc)

@router.get("/novels/{nid}/world-rules")
def list_world_rules(nid: str, status: str | None = None):
    """List structured world-rule proposals without auto-approving them."""
    try:
        novel_service.get(nid)
        rows = lore_service.repository.list_proposals(nid, status)
        return {"items": [row for row in rows if row.get("proposal_type") == "WORLD_RULE"], "storage": settings.storage_backend}
    except Exception as exc:
        return capability_guard(_raise_lore_error, exc)

@router.post("/novels/{nid}/world-rules", status_code=201)
def create_world_rule(nid: str, body: LoreProposalApiIn):
    try:
        novel_service.get(nid)
        proposal_id = body.id or str(uuid.uuid4())
        payload = normalize_world_rule_payload(body.payload)
        item = {"id": proposal_id, "novel_id": nid, "proposal_type": "WORLD_RULE", "payload": payload, "status": "PENDING", "confidence": body.confidence, "agent_name": "manual"}
        return lore_service.create_proposal(item, body.relations)
    except Exception as exc:
        return capability_guard(_raise_lore_error, exc)


@router.post("/novels/{nid}/lore/proposals", status_code=201)
def create_lore_proposal(nid: str, body: LoreProposalApiIn):
    try:
        novel_service.get(nid)
        proposal_id = body.id or str(uuid.uuid4())
        item = body.model_dump(exclude={"relations"})
        item.update({"id": proposal_id, "novel_id": nid, "status": "PENDING"})
        if item.get("generation_job_id") and not item.get("agent_name"):
            item["agent_name"] = "local-review"
        return lore_service.create_proposal(item, body.relations)
    except Exception as exc:
        return capability_guard(_raise_lore_error, exc)


@router.post("/novels/{nid}/lore/proposals/{proposal_id}/approve")
def approve_lore_proposal(nid: str, proposal_id: str, body: LoreProposalReviewIn):
    try:
        proposal = lore_service.repository.get_proposal(proposal_id)
        if proposal.get("novel_id") != nid:
            raise FileNotFoundError(proposal_id)
        return lore_service.approve_proposal(proposal_id, body.approved_payload, body.reviewer)
    except Exception as exc:
        return capability_guard(_raise_lore_error, exc)


@router.post("/novels/{nid}/lore/proposals/{proposal_id}/reject")
def reject_lore_proposal(nid: str, proposal_id: str, body: LoreProposalReviewIn):
    try:
        proposal = lore_service.repository.get_proposal(proposal_id)
        if proposal.get("novel_id") != nid:
            raise FileNotFoundError(proposal_id)
        return lore_service.reject_proposal(proposal_id, body.reviewer, body.reason)
    except Exception as exc:
        return capability_guard(_raise_lore_error, exc)


@router.post("/novels/{nid}/lore/proposals/{proposal_id}/approve-memory")
def approve_lore_memory(nid: str, proposal_id: str, body: MemoryApproveApiIn):
    try:
        proposal = lore_service.repository.get_proposal(proposal_id)
        if proposal.get("novel_id") != nid:
            raise FileNotFoundError(proposal_id)
        approved, memory = memory_service.approve_character_memory(
            proposal_id,
            {"character_id": body.character_id, "memory_type": body.memory_type, "content": body.content,
             "valid_from_chapter": body.valid_from_chapter, "valid_to_chapter": body.valid_to_chapter},
            body.reviewer, memory_id=body.memory_id, business_id=body.business_id,
        )
        return {"proposal": approved, "memory": memory}
    except Exception as exc:
        return capability_guard(_raise_lore_error, exc)


@router.get("/novels/{nid}/memories")
def list_character_memories(nid: str, character_id: str | None = None, status: str | None = None):
    try:
        novel_service.get(nid)
        if character_id:
            novel_service.data_set(nid, "characters")
            rows = [row for row in memory_service.repository.list_character_memories(character_id, status)
                    if row.get("novel_id") == nid]
        else:
            rows = memory_service.repository.list_memories(nid, status)
        return {"items": rows, "total": len(rows), "storage": settings.storage_backend}
    except Exception as exc:
        return capability_guard(_raise_lore_error, exc)


@router.get("/novels/{nid}/characters/{character_id}/memories")
def list_memories_for_character(nid: str, character_id: str, status: str | None = None):
    return list_character_memories(nid, character_id, status)


@router.post("/novels/{nid}/memories/{memory_id}/retract")
def retract_character_memory(nid: str, memory_id: str, body: MemoryRetractApiIn):
    try:
        current = memory_service.repository.get_memory(memory_id)
        if current.get("novel_id") != nid:
            raise FileNotFoundError(memory_id)
        return memory_service.retract(memory_id, body.reason)
    except Exception as exc:
        return capability_guard(_raise_lore_error, exc)


@router.get("/novels/{nid}/memory-snapshots")
def list_memory_snapshots(nid: str, scope: str | None = None):
    try:
        novel_service.get(nid)
        return {"items": memory_service.repository.list_snapshots(nid, scope), "storage": settings.storage_backend}
    except Exception as exc:
        return capability_guard(_raise_lore_error, exc)


@router.post("/novels/{nid}/memory-snapshots", status_code=201)
def create_memory_snapshot(nid: str, body: MemorySnapshotApiIn):
    try:
        novel_service.get(nid)
        return memory_service.create_snapshot(nid, body.scope, body.scope_key, body.created_by,
                                              body.range_start, body.range_end)
    except Exception as exc:
        return capability_guard(_raise_lore_error, exc)


# Plugin manifest / permission management.  Manifest activation does not run
# plugin code; every runtime capability remains denied until a future isolated
# executor is explicitly added.
@router.get("/plugins")
def list_plugins():
    return v1_capability_service.list_plugins()
@router.get("/plugins/discover")
def discover_plugins():
    return discover_installed_plugins(settings.data_path() / "plugins")
@router.get("/plugins/runtime-status")
def plugin_runtime_status():
    return {'execution_supported':False,'sandbox':'NOT_CONFIGURED','isolation':'DENY_ALL','reason':'plugin runtime execution is disabled until isolated worker is shipped'}
@router.get("/release/readiness")
def release_readiness():
    from .dependencies import asset_provider_registry, packaged_bootstrap_registry
    from .release_readiness import build_release_readiness
    return build_release_readiness(
        settings=settings,
        credential_vault=credential_vault,
        runtime=runtime,
        image_registry=asset_provider_registry,
        packaged_bootstrap=packaged_bootstrap_registry.current() is not None,
    )


@router.post("/plugins", status_code=201)
def register_plugin(body: PluginManifestIn,
                    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    return capability_guard(v1_capability_service.register_plugin, body, idempotency_key)


@router.get("/plugins/{plugin_id}")
def get_plugin(plugin_id: str):
    return capability_guard(v1_capability_service.get_plugin, plugin_id)


@router.put("/plugins/{plugin_id}/permissions")
def set_plugin_permissions(plugin_id: str, body: PluginPermissionIn,
                           expected_version: int | None = Query(default=None, ge=1)):
    return capability_guard(v1_capability_service.set_plugin_permissions, plugin_id, body, expected_version)


@router.post("/plugins/{plugin_id}/enable")
def enable_plugin(plugin_id: str, expected_version: int | None = Query(default=None, ge=1)):
    return capability_guard(v1_capability_service.set_plugin_enabled, plugin_id, True, expected_version)


@router.post("/plugins/{plugin_id}/disable")
def disable_plugin(plugin_id: str, expected_version: int | None = Query(default=None, ge=1)):
    return capability_guard(v1_capability_service.set_plugin_enabled, plugin_id, False, expected_version)


@router.get("/plugins/{plugin_id}/resources")
def list_declarative_plugin_resources(plugin_id: str):
    return plugin_catalog_guard(list_plugin_resources, plugin_id)


@router.get("/plugins/{plugin_id}/resources/{resource_id}")
def get_declarative_plugin_resource(plugin_id: str, resource_id: str):
    return plugin_catalog_guard(get_plugin_resource, plugin_id, resource_id)


# Durable, deterministic workflow metadata engine.
@router.get("/workflows")
def list_workflows(novel_id: str | None = None):
    return capability_guard(v1_capability_service.list_workflows, novel_id)


@router.post("/workflows", status_code=201)
def create_workflow(body: WorkflowDefinitionIn,
                    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    return capability_guard(v1_capability_service.create_workflow, body, idempotency_key)


@router.get("/workflows/{workflow_id}")
def get_workflow(workflow_id: str):
    return capability_guard(v1_capability_service.get_workflow, workflow_id)


@router.post("/workflows/{workflow_id}/runs", status_code=202)
def create_workflow_run(workflow_id: str, body: WorkflowRunIn,
                        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    return capability_guard(v1_capability_service.create_workflow_run, workflow_id, body, idempotency_key)


@router.get("/workflows/{workflow_id}/runs")
def list_workflow_runs(workflow_id: str):
    return capability_guard(v1_capability_service.list_workflow_runs, workflow_id)


@router.get("/workflow-runs/{run_id}")
def get_workflow_run(run_id: str):
    return capability_guard(v1_capability_service.get_workflow_run, run_id)


@router.post("/workflow-runs/{run_id}/nodes/{node_id}/approve")
def approve_workflow_node(run_id: str, node_id: str, approved_by: str = Query(...), note: str = Query(default="")):
    return capability_guard(v1_capability_service.approve_workflow_node, run_id, node_id, approved_by, note)
@router.post("/workflow-runs/{run_id}/nodes/{node_id}/trigger-agent")
def trigger_agent_node(run_id: str, node_id: str, triggered_by: str = Query(default="local-author")):
    return capability_guard(v1_capability_service.trigger_agent_node, run_id, node_id, triggered_by)
@router.get("/agent-queue")
def list_agent_queue(novel_id: str | None = None):
    return capability_guard(v1_capability_service.list_agent_queue, novel_id)
@router.post("/agent-queue/{run_id}/{node_id}/claim")
def claim_agent_task(run_id: str, node_id: str, claimed_by: str = Query(default="local-worker")):
    return capability_guard(v1_capability_service.claim_agent_task, run_id, node_id, claimed_by)
@router.post("/agent-queue/{run_id}/{node_id}/complete")
def complete_agent_task(run_id: str, node_id: str, status: str = Query(...), output: dict | None = None, error: str | None = None):
    return capability_guard(v1_capability_service.complete_agent_task, run_id, node_id, status, output, error)


@router.post("/workflow-runs/{run_id}/pause")
def pause_workflow_run(run_id: str):
    return capability_guard(v1_capability_service.set_workflow_run_state, run_id, "pause")


@router.post("/workflow-runs/{run_id}/resume")
def resume_workflow_run(run_id: str):
    return capability_guard(v1_capability_service.set_workflow_run_state, run_id, "resume")


@router.post("/workflow-runs/{run_id}/cancel")
def cancel_workflow_run(run_id: str):
    return capability_guard(v1_capability_service.set_workflow_run_state, run_id, "cancel")


@router.post("/workflow-runs/{run_id}/retry", status_code=202)
def retry_workflow_run(run_id: str,
                       idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    return capability_guard(v1_capability_service.retry_workflow_run, run_id, idempotency_key)


@router.get("/release-gates")
def list_release_gates(novel_id: str | None = None):
    return capability_guard(v1_capability_service.list_release_gates, novel_id)


@router.post("/release-gates", status_code=202)
def evaluate_release_gate(body: ReleaseGateIn,
                          idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    return capability_guard(v1_capability_service.evaluate_release_gate, body.novel_id, body.evidence, True, idempotency_key)


@router.get("/release-gates/{gate_id}")
def get_release_gate(gate_id: str):
    return capability_guard(v1_capability_service.get_release_gate, gate_id)


@router.get("/audit")
def list_capability_audit(novel_id: str | None = None, limit: int = Query(default=100, ge=1, le=500)):
    return capability_guard(v1_capability_service.list_audit, novel_id, limit)
