"""Explainable live routing and a scope-atomic cost ledger, never an executor.

Runtime registries and the Model Center remain the only model/configuration
owners. Prices are estimates, not invoices. Unknown upstream outcomes retain
holds; neither cancellations nor replays silently create fresh budgets.
"""
from __future__ import annotations

import copy
import hashlib
from types import CodeType
import platform
import math
import os
import hmac
import secrets
import threading
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..config import settings
from ..model_runtime import LegacyTextProviderAdapter, Modality
from ..providers import MockProvider, OllamaProvider
from ..source_privacy import effective_source_privacy, assert_current_manuscript_egress
from .common import DomainService, StaleSourceError, check_version, change_row, new_row, now
from .store import canonical

FEATURE = 'model_broker_v2'

# Routing recipes reference the existing owners; they are never model entries.
NARRATIVE_TASK_CAPABILITIES = {
    'NOVEL_WRITING': 'TEXT', 'SCREENPLAY_ADAPTATION': 'TEXT',
    'DIRECTOR_NOTES': 'TEXT', 'FRAME_ANALYSIS': 'VISION',
    'STORYBOARD_IMAGE': 'IMAGE', 'VIDEO_CLIP': 'VIDEO',
    'DIALOGUE_AUDIO': 'AUDIO',
}
NarrativeTask = Literal['NOVEL_WRITING', 'SCREENPLAY_ADAPTATION', 'DIRECTOR_NOTES',
                        'FRAME_ANALYSIS', 'STORYBOARD_IMAGE', 'VIDEO_CLIP', 'DIALOGUE_AUDIO']


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def implementation_hash(cls):
    # Frozen desktop packages need not ship source. Normalize code objects rather
    # than marshal (whose interned-reference representation can change after a
    # function executes). No source, file path, or executable data is exposed.
    def stable(value):
        if isinstance(value, CodeType):
            return {'bytecode': value.co_code.hex(), 'constants': [stable(v) for v in value.co_consts],
                    'names': value.co_names, 'variables': value.co_varnames,
                    'free': value.co_freevars, 'cell': value.co_cellvars,
                    'flags': value.co_flags, 'argc': value.co_argcount,
                    'posonly': value.co_posonlyargcount, 'kwonly': value.co_kwonlyargcount}
        if isinstance(value, (tuple, frozenset)):
            values = [stable(v) for v in value]
            return sorted(values, key=canonical) if isinstance(value, frozenset) else values
        if isinstance(value, bytes): return {'bytes': value.hex()}
        if value is None or type(value) in {str, int, bool}: return value
        return {'type': type(value).__name__, 'literal': repr(value)}
    methods = []
    for base in reversed(cls.__mro__):
        for name, value in sorted(vars(base).items()):
            value = getattr(value, '__func__', value)
            code = getattr(value, '__code__', None)
            if code is not None:
                methods.append([base.__module__, base.__qualname__, name, stable(code)])
    if not methods: raise ValueError('BROKER_ADAPTER_CODE_FINGERPRINT_UNAVAILABLE')
    return digest(methods)


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class BrokerRequest(Strict):
    capability: Literal['TEXT', 'VISION', 'IMAGE', 'VIDEO', 'AUDIO', 'EMBEDDING'] = 'TEXT'
    task_type: NarrativeTask | None = None
    chapter_ids: list[str] = Field(default_factory=list, max_length=20)
    policy: Literal['LOCAL_FIRST', 'COST', 'QUALITY', 'SPEED', 'CUSTOM', 'PRIVACY_FIRST', 'BALANCED', 'COST_FIRST', 'QUALITY_FIRST', 'SPEED_FIRST'] = 'LOCAL_FIRST'
    profile: Literal['LOCAL_ONLY', 'HYBRID', 'QUALITY'] = 'LOCAL_ONLY'
    preferred_route: str | None = Field(default=None, max_length=160)
    excluded_providers: list[str] = Field(default_factory=list, max_length=50)
    context_tokens: int = Field(default=0, ge=0, le=10000000)
    max_latency_ms: int | None = Field(default=None, ge=1, le=3600000)
    max_cost_microusd: int | None = Field(default=None, ge=0, le=10**12)
    allow_synthetic: bool = False
    allow_cloud_fallback: bool = False
    require_confirmed_license: bool = False
    min_host_ram_mib: int | None = Field(default=None, ge=1, le=10**7)
    min_host_vram_mib: int | None = Field(default=None, ge=1, le=10**7)


    @model_validator(mode='after')
    def task_capability_matches(self):
        if self.task_type and NARRATIVE_TASK_CAPABILITIES[self.task_type] != self.capability:
            raise ValueError('BROKER_TASK_CAPABILITY_MISMATCH')
        return self


class NarrativeTaskRequest(Strict):
    task_type: NarrativeTask
    chapter_ids: list[str] = Field(default_factory=list, max_length=20)
    preferred_route: str | None = Field(default=None, max_length=160)
    context_tokens: int = Field(default=0, ge=0, le=10000000)
    allow_synthetic: bool = False
    # This workbench is explicitly local-only and carries no payment authority.
    max_cost_microusd: Literal[0] = 0


class BudgetInput(Strict):
    expected_version: int = Field(ge=0)
    limit_microusd: int | None = Field(default=None, ge=0, le=10**12)
    max_inflight: int = Field(default=1, ge=1, le=8)
    require_known_estimate: bool = True


class ReconcileInput(Strict):
    expected_version: int = Field(ge=1)
    actual_microusd: int = Field(ge=0, le=10**12)
    upstream_terminal_confirmed: Literal[True]
    original_executor_stopped_confirmed: bool = False
    evidence_note: str = Field(min_length=1, max_length=500)


class PriceInput(Strict):
    route_id: str = Field(min_length=1, max_length=160)
    route_fingerprint: str = Field(pattern=r'^[0-9a-f]{64}$')
    currency: Literal['USD'] = 'USD'
    reserve_microusd: int = Field(ge=0, le=10**12)
    input_per_million_microusd: int | None = Field(default=None, ge=0, le=10**12)
    output_per_million_microusd: int | None = Field(default=None, ge=0, le=10**12)
    source: str = Field(min_length=1, max_length=240)
    as_of: datetime
    expires_at: datetime
    applicability: Literal['per_request'] = 'per_request'
    expected_version: int = Field(ge=0)

    @model_validator(mode='after')
    def valid_dates(self):
        if not self.as_of.tzinfo or not self.expires_at.tzinfo or self.expires_at <= self.as_of:
            raise ValueError('BROKER_PRICE_DATES_INVALID')
        if self.as_of > datetime.now(timezone.utc):
            raise ValueError('BROKER_PRICE_FUTURE_SOURCE')
        return self


class ModelBrokerService(DomainService):
    DECISIONS = 'broker_decisions_v2'
    LEDGER = 'broker_ledger_v2'
    BUDGET = 'broker_budget_v2'
    PRICES = 'broker_prices_v2'

    def __init__(self, store, novels, chapters, *, runtime, model_center=None, media_registry=None, audio_resolver=None, vision_resolver=None):
        super().__init__(store, novels, chapters)
        self.runtime, self.model_center, self.media_registry = runtime, model_center, media_registry
        self.audio_resolver = audio_resolver
        self.vision_resolver = vision_resolver
        self.evidence_reader = None
        self._credential_salt = secrets.token_bytes(32)
        self._credential_bindings = {}
        self._credential_lock = threading.Lock()

    def _credential_binding(self, provider_id, secret):
        # In-memory equality detector only. No secret or secret-derived digest is
        # persisted/returned. Rotation mints an opaque receipt fence; restart
        # conservatively invalidates old remote receipts.
        marker = hmac.new(self._credential_salt, (secret or '').encode(), hashlib.sha256).digest()
        with self._credential_lock:
            old = self._credential_bindings.get(provider_id)
            if old is None or not hmac.compare_digest(old[0], marker):
                old = (marker, secrets.token_hex(16))
                self._credential_bindings[provider_id] = old
            return old[1]

    def _adapter_facts(self, adapter, model):
        """Only shipped, host-registered adapters; no executable imports from HTTP."""
        from ..model_center.discovery_bridge import LocalTextAdapter
        from ..openai_compatible import OpenAICompatibleTextProvider
        from ..native_text_providers import AnthropicTextProvider, GeminiTextProvider
        facts = {'adapter': f'{type(adapter).__module__}.{type(adapter).__qualname__}',
                 'adapter_hash': implementation_hash(type(adapter)),
                 'model_version': None, 'quantization': None, 'runtime_version': None,
                 'workflow_hash': digest({'node': 'builtin.text_model', 'contract': 1}),
                 'hardware_hash': None, 'synthetic': False}
        reasons = []
        if isinstance(adapter, LegacyTextProviderAdapter):
            facts['delegate_hash'] = implementation_hash(type(adapter.provider))
        if isinstance(adapter, LocalTextAdapter):
            candidate = adapter.bridge.guard(adapter.candidate['id'])
            if candidate['id'] != model.model_id:
                raise ValueError('BROKER_MODEL_BINDING_CHANGED')
            # Reuse the Model Center's bounded metadata/artifact check; this is
            # not inference and never installs or starts a runtime.
            adapter.bridge.service.check_model_dispatch(candidate)
            candidate = adapter.bridge.guard(adapter.candidate['id'])
            facts.update(license_confirmed=bool(candidate.get('license_confirmed')), license_state='USER_CONFIRMED_LOCAL_USE' if candidate.get('license_confirmed') else 'REVIEW_REQUIRED', runtime_hash=candidate.get('runtime_fingerprint'), model_version=candidate.get('model_evidence_fingerprint'),
                         quantization=candidate.get('evidence', {}).get('general.file_type'),
                         runtime_version=candidate.get('evidence', {}).get('runtime_version'),
                         config_hash=digest(candidate['runtime_config']), enabled_at=candidate.get('enabled_at'),
                         source_locality=candidate.get('source_locality', 'LOCAL_VERIFIED' if candidate.get('local') else 'NOT_VERIFIED'))
            if not facts['model_version']: reasons.append('MODEL_VERSION_EVIDENCE_MISSING')
            if facts['source_locality'] != 'LOCAL_VERIFIED': reasons.append('LOCALITY_NOT_VERIFIED')
        elif isinstance(adapter, LegacyTextProviderAdapter) and type(adapter.provider) is MockProvider:
            facts.update(synthetic=True, license_confirmed=True, license_state='BUILTIN_SYNTHETIC_ONLY', model_version='synthetic-protocol-v1', runtime_version='python-' + platform.python_version(),
                         config_hash=digest({'delay': getattr(adapter.provider, 'delay_ms', None), 'failure': getattr(adapter.provider, 'failure', None)}),
                         source_locality='LOCAL_VERIFIED')
        elif isinstance(adapter, LegacyTextProviderAdapter) and isinstance(adapter.provider, OllamaProvider):
            # Listing a name is not enablement or local-inference evidence. Use
            # the explicit discovery/enable bridge for real Ollama routes.
            facts.update(config_hash=digest({'endpoint': adapter.provider.base_url}), source_locality='NOT_VERIFIED')
            reasons.append('EXPLICIT_MODEL_CENTER_ENABLE_REQUIRED')
        elif type(adapter) in {OpenAICompatibleTextProvider, AnthropicTextProvider, GeminiTextProvider}:
            from ..credential_vault import credential_vault
            secret = credential_vault.resolve(model.provider_id) or (os.getenv(adapter.config.api_key_env) if not settings.enable_packaged_runtime else None)
            configured = bool(secret)
            credential_binding = self._credential_binding(model.provider_id, secret)
            if not configured: reasons.append('CREDENTIAL_UNAVAILABLE')
            facts.update(config_hash=digest(asdict(adapter.config)), source_locality='REMOTE',
                         runtime_version='provider-api-version-unreported', credential_available=bool(configured), credential_binding=credential_binding)
        else:
            reasons.append('VERIFIED_ADAPTER_REQUIRED')
        center_model = getattr(self.model_center, 'models', {}).get(model.model_id)
        if center_model is not None:
            facts['model_center_hash'] = digest({k: str(getattr(center_model, k, '')) for k in ('version', 'quantization', 'precision', 'model_format', 'status', 'license')})
            facts['catalog_license'] = center_model.license
            facts.setdefault('license_state', 'CATALOG_CLAIM_NOT_CONFIRMATION')
            facts['quantization'] = center_model.quantization or facts['quantization']
            profiles = getattr(self.model_center, 'profiles', {})
            facts['hardware_hash'] = digest([asdict(profiles[pid]) for pid in center_model.hardware_profiles if pid in profiles]) if isinstance(profiles, dict) and center_model.hardware_profiles else None
        return facts, reasons

    def candidates(self):
        providers = {row.provider_id: row for row in self.runtime.provider_registry.descriptors()}
        items = []
        for model in self.runtime.model_registry.descriptors():
            provider = providers.get(model.provider_id)
            reasons, facts = [], {}
            if model.modality is not Modality.TEXT: continue
            if not model.enabled: reasons.append('MODEL_DISABLED')
            if not provider or not provider.configured: reasons.append('PROVIDER_NOT_CONFIGURED')
            if not provider or not provider.available: reasons.append('PROVIDER_UNAVAILABLE')
            adapter = None
            if not reasons:
                try:
                    adapter = self.runtime.provider_registry.resolve(model.provider_id)
                    facts, adapter_reasons = self._adapter_facts(adapter, model)
                    reasons.extend(adapter_reasons)
                    self.runtime.prepare_text_route(model.provider_id, model.model_id)
                except Exception:
                    reasons.append('CURRENT_RUNTIME_AUTHORITY_UNAVAILABLE')
            cloud = self.runtime.is_remote_text_provider(model.provider_id)
            if cloud and not settings.enable_cloud: reasons.append('HOST_CLOUD_DISABLED')
            if settings.enable_packaged_runtime and facts.get('synthetic'): reasons.append('PACKAGED_SYNTHETIC_DISABLED')
            if 'generate' not in model.capabilities or not model.streaming: reasons.append('TEXT_STREAM_CAPABILITY_REQUIRED')
            identity = {'provider_id': model.provider_id, 'model_id': model.model_id,
                        'execution_node_id': str(self.runtime.execution_node_identity.store.get('execution_node', 'local') or ''),
                        'provider_identity': str(getattr(provider, 'identity_id', '') or ''), 'model_identity': str(model.identity_id or ''),
                        'capabilities': sorted(model.capabilities), 'context_window': model.context_window,
                        'enabled': model.enabled, 'configured': bool(provider and provider.configured),
                        'available': bool(provider and provider.available), 'cloud': cloud, **facts}
            items.append({'route_id': digest([model.provider_id, model.model_id]),
                          'provider_id': model.provider_id, 'model_id': model.model_id, 'display_name': model.display_name,
                          'capability': 'TEXT', 'context_window': model.context_window, 'cloud': cloud,
                          'synthetic': bool(facts.get('synthetic')), 'fingerprint': digest(identity),
                          'binding_hash': digest([id(adapter), digest(identity)]), 'identity': identity,
                          'available': not reasons, 'reasons': list(dict.fromkeys(reasons)),
                          'verification': 'SYNTHETIC_PROTOCOL_ONLY' if facts.get('synthetic') else 'ADAPTER_CONTRACT_ONLY'})
        if self.media_registry is not None:
            from .media import MockImageWorkflowAdapter, RegisteredLocalImageWorkflowAdapter, production_environment
            for definition in self.media_registry.definitions()['items']:
                adapter = self.media_registry._adapters.get(definition['adapter_id'])
                if adapter is None: continue  # Family contracts are not available models.
                synthetic = type(adapter) is MockImageWorkflowAdapter
                reasons = []
                if not definition['runnable']: reasons.append('MEDIA_ADAPTER_UNAVAILABLE')
                if not definition['local']: reasons.append('MEDIA_CLOUD_AUTHORITY_NOT_INTEGRATED')
                identity = {'adapter': f'{type(adapter).__module__}.{type(adapter).__qualname__}',
                    'adapter_hash': implementation_hash(type(adapter)),
                    'execution_node_id': str(self.runtime.execution_node_identity.store.get('execution_node', 'local') or ''),
                    'adapter_version': definition['adapter_version'], 'model_id': definition['model_id'],
                    'model_version': definition['adapter_version'] if synthetic else None,
                    'workflow_hash': digest(definition), 'runtime_version': 'python-' + platform.python_version() if synthetic else None,
                    'quantization': None, 'hardware_hash': None, 'definition': definition}
                if type(adapter) is RegisteredLocalImageWorkflowAdapter:
                    try:
                        environment = production_environment(adapter)
                        identity['registered_environment'] = environment
                        identity['workflow_hash'] = digest([definition, environment['workflow_digest'], environment['registration']['delegate_digest']])
                    except (ValueError, RuntimeError): reasons.append('ORIGINAL_IMAGE_REGISTRATION_UNAVAILABLE')
                items.append({'route_id': digest(['media', definition['adapter_id'], definition['model_id']]),
                    'adapter_id': definition['adapter_id'], 'provider_id': 'media:' + definition['adapter_id'],
                    'model_id': definition['model_id'], 'display_name': definition['family'],
                    'capability': definition['modality'], 'context_window': None, 'cloud': not definition['local'],
                    'synthetic': synthetic, 'fingerprint': digest(identity), 'binding_hash': digest([id(adapter), digest(identity)]),
                    'identity': identity, 'available': not reasons, 'reasons': reasons,
                    'verification': 'SYNTHETIC_PROTOCOL_ONLY' if synthetic else 'ADAPTER_CONTRACT_ONLY'})
        if self.audio_resolver is not None:
            from ..audio_providers import provider_catalog
            for config in provider_catalog():
                if 'TTS' not in config['capabilities']: continue
                pid = config['provider_id']
                if pid == 'auto': continue  # Resolving auto may health-check; catalog reads never do.
                try:
                    resolved_id, model_id, adapter = self.audio_resolver(pid)
                    if resolved_id != pid: continue  # An explicit route cannot silently fall back.
                    identity = self.audio_identity(pid, model_id, adapter)
                    local = bool(getattr(adapter, 'local', False))
                    reasons = [] if local else ['AUDIO_CLOUD_BUDGET_EGRESS_NOT_INTEGRATED']
                    items.append({'route_id': digest(['audio', pid, model_id]), 'audio_provider_id': pid,
                        'provider_id': 'audio:' + pid, 'model_id': model_id, 'display_name': config['display_name'],
                        'capability': 'AUDIO', 'context_window': None, 'cloud': not local, 'synthetic': False,
                        'fingerprint': digest(identity), 'binding_hash': digest(identity), 'identity': identity,
                        'available': not reasons, 'reasons': reasons, 'verification': 'ADAPTER_CONFIG_ONLY_RUNTIME_NOT_PROBED'})
                except (ValueError, RuntimeError):
                    continue  # Missing credentials/configuration are never a runnable route.
        if self.vision_resolver is not None:
            # Original ResearchLibrary owns this provider and its guarded jobs.
            # Discovery metadata or VISION in a filename cannot create a route.
            from .research_vision import ResearchVisionCapability, SyntheticResearchVisionProvider
            try:
                adapter = self.vision_resolver()
                if adapter is not None:
                    capability = ResearchVisionCapability.model_validate(adapter.capability)
                    synthetic = type(adapter) is SyntheticResearchVisionProvider
                    reasons = []
                    if not callable(getattr(adapter, 'analyze', None)):
                        reasons.append('VISION_EXECUTOR_UNAVAILABLE')
                    if not capability.local:
                        reasons.append('VISION_CLOUD_BUDGET_EGRESS_NOT_INTEGRATED')
                    if capability.verification == 'MOCK_ONLY' and not synthetic:
                        reasons.append('VISION_SYNTHETIC_ADAPTER_NOT_VERIFIED')
                    identity = {'adapter': f'{type(adapter).__module__}.{type(adapter).__qualname__}',
                        'adapter_hash': implementation_hash(type(adapter)),
                        'model_version': capability.model_revision,
                        'capability': capability.model_dump(),
                        'execution_node_id': str(self.runtime.execution_node_identity.store.get('execution_node', 'local') or ''),
                        'workflow_hash': digest({'executor': 'original.research_analysis', 'contract': 1})}
                    items.append({'route_id': digest(['vision', capability.provider_id, capability.model_id]),
                        'provider_id': 'vision:' + capability.provider_id, 'model_id': capability.model_id,
                        'display_name': capability.model_id, 'capability': 'VISION', 'context_window': None,
                        'cloud': not capability.local, 'synthetic': synthetic,
                        'fingerprint': digest(identity), 'binding_hash': digest([id(adapter), digest(identity)]),
                        'identity': identity, 'available': not reasons, 'reasons': reasons,
                        'verification': 'SYNTHETIC_PROTOCOL_ONLY' if synthetic else 'ADAPTER_CONTRACT_ONLY',
                        'executor': 'original.research_analysis'})
            except (ValueError, RuntimeError, AttributeError, TypeError):
                # Invalid/missing host registration stays unavailable.
                pass
        return items

    def preview_task(self, nid, scope, actor, value, guard=lambda: None):
        body = NarrativeTaskRequest.model_validate(value)
        request = BrokerRequest(**body.model_dump(),
            capability=NARRATIVE_TASK_CAPABILITIES[body.task_type],
            profile='LOCAL_ONLY', policy='CUSTOM' if body.preferred_route else 'LOCAL_FIRST',
            allow_cloud_fallback=False)
        return self.preview(nid, scope, actor, request, guard)

    def audio_identity(self, provider_id, model_id, adapter):
        """Metadata-only identity of the original resolver, never a health call.

        No endpoint, path or credential is returned, and no fee is inferred from
        locality. Original configure_price remains the sole estimate authority.
        """
        from ..audio_providers import HttpAudioProvider
        if type(adapter) is not HttpAudioProvider: raise ValueError('BROKER_ORIGINAL_AUDIO_ADAPTER_REQUIRED')
        return {'provider_id': provider_id, 'model_id': model_id, 'adapter_hash': implementation_hash(type(adapter)),
            'endpoint_hash': digest(adapter.endpoint), 'local': adapter.local,
            'emotion_values': list(adapter.emotion_values),
            'credential_binding': self._credential_binding('audio:' + provider_id, adapter.api_key) if adapter.api_key else 'NONE_CONFIGURED',
            'model_version': None, 'runtime_version': None, 'hardware_hash': None,
            'workflow_hash': digest({'executor': 'original.audiobook', 'contract': 1})}

    def hardware_capacity(self):
        from ..provider_runtime_v2_host_hardware_inventory import collect_host_hardware_snapshot
        try:
            snapshot = collect_host_hardware_snapshot(self.runtime.execution_node_identity, self.model_center)
            return {'state': 'HOST_TOTAL_CAPACITY', 'ram_mib': snapshot.ram_mib,
                    'vram_mib': snapshot.vram_mib, 'free_memory': None,
                    'warning': 'Total capacity is not currently free memory or an inference fit guarantee.'}
        except Exception:
            return {'state': 'UNAVAILABLE', 'ram_mib': None, 'vram_mib': None, 'free_memory': None}

    def current_route(self, route_id):
        route = next((r for r in self.candidates() if r['route_id'] == route_id), None)
        if not route: raise ValueError('BROKER_ROUTE_NOT_REGISTERED')
        return route

    def budget(self, nid, scope):
        doc = self.store.read(nid, scope)
        config = copy.deepcopy(doc['collections'].get(self.BUDGET, {}).get('budget', {'version': 0, 'limit_microusd': None, 'max_inflight': 1, 'require_known_estimate': True}))
        return {**config, **self._totals(doc), 'currency': 'USD', 'accounting_unit': 'microusd',
                'boundary': 'Reservation admission limit; upstream charges can exceed an estimate.'}

    def _totals(self, doc):
        rows = list(doc['collections'].get(self.LEDGER, {}).values())
        return {'committed_microusd': sum(r.get('accounted_microusd') or 0 for r in rows),
                'inflight': sum(r['status'] in {'RESERVED', 'DISPATCHED', 'UNKNOWN_UPSTREAM'} for r in rows),
                'unknown_count': sum(r['status'] == 'UNKNOWN_UPSTREAM' for r in rows),
                'unpriced_count': sum(r['status'] in {'RESERVED', 'DISPATCHED', 'UNKNOWN_UPSTREAM'} and r.get('reserve_microusd') is None for r in rows),
                'overrun_count': sum(r.get('overrun', False) and not r.get('overrun_acknowledged', False) for r in rows)}

    def configure_budget(self, nid, scope, actor, value, guard=lambda: None):
        body = BudgetInput.model_validate(value)
        self.novels.get(nid)
        with self.store.transaction(nid, scope) as doc:
            guard()
            rows = doc['collections'].setdefault(self.BUDGET, {})
            row = rows.get('budget')
            if body.expected_version != (row['version'] if row else 0):
                from ..services.v1_capability_service import CapabilityVersionConflict
                raise CapabilityVersionConflict(row or {'version': 0})
            if body.limit_microusd is not None and body.limit_microusd < self._totals(doc)['committed_microusd']:
                raise ValueError('BROKER_BUDGET_BELOW_COMMITTED')
            payload = body.model_dump(exclude={'expected_version'})
            if row: change_row(row, actor, row['version'], lambda r: r.update(payload))
            else: rows['budget'] = new_row(nid, scope, actor, payload)
        return self.budget(nid, scope)

    def configure_price(self, nid, scope, actor, value, guard=lambda: None):
        body = PriceInput.model_validate(value)
        self.novels.get(nid)
        route = self.current_route(body.route_id)
        if route['fingerprint'] != body.route_fingerprint: raise StaleSourceError('BROKER_ROUTE_CHANGED')
        if body.expires_at <= datetime.now(timezone.utc): raise ValueError('BROKER_PRICE_EXPIRED')
        with self.store.transaction(nid, scope) as doc:
            guard()
            rows = doc['collections'].setdefault(self.PRICES, {})
            row = rows.get(body.route_id)
            if body.expected_version != (row['version'] if row else 0):
                from ..services.v1_capability_service import CapabilityVersionConflict
                raise CapabilityVersionConflict(row or {'version': 0})
            payload = body.model_dump(mode='json', exclude={'expected_version'})
            if row: change_row(row, actor, row['version'], lambda r: r.update(payload))
            else: rows[body.route_id] = new_row(nid, scope, actor, payload)
            return copy.deepcopy(rows[body.route_id])

    def _price(self, route, prices):
        if route['synthetic']:
            return {'reserve_microusd': 0, 'currency': 'USD', 'source': 'Builtin deterministic adapter; no provider invoice',
                    'applicability': 'synthetic_provider_fee_only', 'actual_known_zero': True}
        row = prices.get(route['route_id'])
        if row and row['route_fingerprint'] == route['fingerprint'] and datetime.fromisoformat(row['expires_at']) > datetime.now(timezone.utc):
            return copy.deepcopy({k: v for k, v in row.items() if k not in {'history', 'scope'}})
        return None

    def _sources(self, nid, scope, ids):
        result = {}
        for cid in dict.fromkeys(ids):
            chapter = self.chapters_for(scope).get(cid)
            if chapter.get('novel_id') != nid or chapter.get('branch_id') != scope.get('branch_id'):
                raise ValueError('BROKER_SOURCE_SCOPE_MISMATCH')
            result[cid] = {**self.sources(nid, [cid], scope)[cid],
                           'privacy_level': effective_source_privacy(chapter, scope.get('branch_id'))}
        return result

    def preview(self, nid, scope, actor, value, guard=lambda: None, route_guard=None):
        body = BrokerRequest.model_validate(value)
        self.novels.get(nid)
        guard()
        sources = self._sources(nid, scope, body.chapter_ids)
        budget = self.budget(nid, scope)
        doc = self.store.read(nid, scope)
        prices = doc['collections'].get(self.PRICES, {})
        candidates = self.candidates()
        hardware = self.hardware_capacity() if body.min_host_ram_mib or body.min_host_vram_mib else {'state': 'NOT_REQUESTED', 'free_memory': None}
        evidence = self.evidence_reader(nid, scope) if callable(self.evidence_reader) else []
        for route in candidates:
            reasons = list(route['reasons'])
            if body.capability != route['capability']: reasons.append('CAPABILITY_EXECUTOR_NOT_INTEGRATED')
            required_operation = {'FRAME_ANALYSIS': 'IMAGE_UNDERSTANDING',
                'VIDEO_CLIP': 'text_to_video', 'STORYBOARD_IMAGE': 'storyboard_card_generation'}.get(body.task_type)
            if required_operation and body.capability == route['capability']:
                identity = route.get('identity', {})
                operations = identity.get('capability', {}).get('operations', []) if body.capability == 'VISION' else identity.get('definition', {}).get('operations', [])
                if required_operation not in operations:
                    reasons.append('TASK_OPERATION_NOT_SUPPORTED')
            if route['provider_id'] in body.excluded_providers: reasons.append('EXCLUDED_BY_USER')
            if body.policy == 'CUSTOM' and body.preferred_route != route['route_id']: reasons.append('CUSTOM_ROUTE_NOT_SELECTED')
            if route['synthetic'] and not body.allow_synthetic: reasons.append('SYNTHETIC_NOT_REQUESTED')
            route['license_state'] = route.get('identity', {}).get('license_state', 'UNKNOWN')
            route['license_confirmed'] = bool(route['synthetic'] or route.get('identity', {}).get('license_confirmed'))
            if body.require_confirmed_license and not route['license_confirmed']: reasons.append('LICENSE_CONFIRMATION_REQUIRED')
            if route['cloud']:
                if body.policy == 'PRIVACY_FIRST': reasons.append('PRIVACY_FIRST_LOCAL_ONLY')
                if body.policy == 'LOCAL_FIRST' and not body.allow_cloud_fallback: reasons.append('LOCAL_TO_CLOUD_FALLBACK_NOT_APPROVED')
                if body.profile == 'LOCAL_ONLY': reasons.append('LOCAL_ONLY_POLICY')
                for cid in sources:
                    try:
                        assert_current_manuscript_egress(self.chapters_for(scope), self.novels, nid, self.chapters_for(scope).get(cid), scope.get('branch_id'))
                    except (ValueError, FileNotFoundError): reasons.append('CURRENT_SOURCE_PRIVACY_BLOCKS_CLOUD')
            for required, available in ((body.min_host_ram_mib, hardware.get('ram_mib')), (body.min_host_vram_mib, hardware.get('vram_mib'))):
                if required and (route['cloud'] or available is None or available < required): reasons.append('HOST_CAPACITY_UNKNOWN_OR_INSUFFICIENT')
            if body.context_tokens and (route['context_window'] is None or route['context_window'] < body.context_tokens):
                reasons.append('CONTEXT_CAPACITY_UNKNOWN_OR_INSUFFICIENT')
            matched = [r for r in evidence if r.get('route_fingerprint') == route['fingerprint'] and r.get('evidence_state') == 'CURRENT' and r.get('origin') == 'EXECUTED' and r.get('metrics', {}).get('error_count') == 0]
            route['evidence_ids'] = [r['id'] for r in matched]
            metrics = [r.get('metrics', {}).get('latency_ms') for r in matched]
            metrics = [v for v in metrics if isinstance(v, (int, float)) and math.isfinite(v)]
            route['latency_ms'] = round(sum(metrics) / len(metrics), 3) if metrics else None
            # No literary score from HTTP success or unreviewed imported data.
            route['quality_score'] = None
            if body.max_latency_ms and (route['latency_ms'] is None or route['latency_ms'] > body.max_latency_ms):
                reasons.append('LATENCY_EVIDENCE_UNKNOWN_OR_OVER_LIMIT')
            route['price'] = self._price(route, prices)
            cost = route['price']['reserve_microusd'] if route['price'] else None
            route['cost_state'] = 'ESTIMATE' if route['price'] and not route['synthetic'] else 'KNOWN_SYNTHETIC_ZERO' if route['synthetic'] else 'UNKNOWN'
            if cost is None and (budget['require_known_estimate'] or budget['limit_microusd'] is not None or body.max_cost_microusd is not None): reasons.append('PRICE_ESTIMATE_REQUIRED')
            if body.max_cost_microusd is not None and cost is not None and cost > body.max_cost_microusd: reasons.append('TASK_BUDGET_EXCEEDED')
            if budget['limit_microusd'] is not None and cost is not None and budget['committed_microusd'] + cost > budget['limit_microusd']: reasons.append('PROJECT_BUDGET_EXCEEDED')
            if budget['unpriced_count']: reasons.append('UNPRICED_UPSTREAM_REQUIRES_RECONCILIATION')
            if budget['overrun_count']: reasons.append('UPSTREAM_OVERRUN_REQUIRES_RECONCILIATION')
            if route_guard and not reasons:
                try: route_guard(route)
                except Exception: reasons.append('AUTHOR_CONTEXT_OR_AUTHORITY_BLOCKED')
            route['reasons'] = list(dict.fromkeys(reasons))
            route['eligible'] = not route['reasons']
        eligible = [r for r in candidates if r['eligible']]
        # Balanced uses ranks only across currently eligible routes. Missing
        # facts rank last, and quality is never manufactured from transport success.
        def ordinal(route, key):
            known = sorted({key(value) for value in eligible if key(value) is not None})
            value = key(route)
            return known.index(value) if value is not None else len(known) + 1
        def rank(route):
            preferred = 0 if route['route_id'] == body.preferred_route else 1
            cost = route['price']['reserve_microusd'] if route['price'] else float('inf')
            if body.policy in {'COST', 'COST_FIRST'}: return (cost, preferred, route['cloud'], route['route_id'])
            if body.policy in {'SPEED', 'SPEED_FIRST'}: return (route['latency_ms'] if route['latency_ms'] is not None else float('inf'), preferred, route['cloud'], route['route_id'])
            if body.policy == 'BALANCED':
                points = ordinal(route, lambda r: r['price']['reserve_microusd'] if r['price'] else None) + ordinal(route, lambda r: r['latency_ms']) + int(route['cloud'])
                return (points, preferred, route['synthetic'], route['route_id'])
            if body.policy in {'LOCAL_FIRST', 'PRIVACY_FIRST'}:
                return (route['cloud'], preferred, route['synthetic'], route['route_id'])
            return (preferred, route['cloud'], route['synthetic'], route['route_id'])
        chosen = sorted(eligible, key=rank)[0] if eligible else None
        guard()
        if sources != self._sources(nid, scope, body.chapter_ids): raise StaleSourceError('BROKER_SOURCES_CHANGED')
        payload = {'request': body.model_dump(), 'sources': sources, 'budget_version': budget['version'],
                   'chosen': chosen, 'candidates': candidates, 'status': 'PREVIEW' if chosen else 'NO_LEGAL_ROUTE',
                   'decision_reason': 'CURRENT_ELIGIBLE_ROUTE_WITH_POLICY_ORDER' if chosen else 'NO_REGISTERED_ROUTE_SATISFIES_CURRENT_CONSTRAINTS',
                   'warnings': (['QUALITY_EVIDENCE_UNAVAILABLE_NO_QUALITY_RANKING'] if body.policy in {'QUALITY', 'QUALITY_FIRST'} else []),
                   'will_send': {'source_chapter_ids': list(sources), 'source_versions': sources, 'target': 'cloud' if chosen and chosen['cloud'] else 'local' if chosen else None,
                                 'author_request_preview_required': True},
                   'execution_authorized': False, 'automatic_fallback': False, 'hardware': hardware,
                   'policy_explanation': {'policy': body.policy, 'quality': 'NOT_MEASURED_NOT_RANKED',
                       'balanced_factors': ['CURRENT_COST_RANK', 'CURRENT_LATENCY_RANK', 'CLOUD_PENALTY'] if body.policy == 'BALANCED' else [],
                       'unknown_metrics': 'RANK_LAST', 'cloud_fallback_preapproved': body.allow_cloud_fallback,
                       'license_confirmation_required': body.require_confirmed_license}}
        with self.store.transaction(nid, scope) as doc:
            guard()
            row = new_row(nid, scope, actor, payload)
            doc['collections'].setdefault(self.DECISIONS, {})[row['id']] = row
            return copy.deepcopy(row)

    def decisions(self, nid, scope, actor):
        return sorted((r for r in self.list(nid, scope, self.DECISIONS) if r['created_by'] == actor), key=lambda r: r['created_at'], reverse=True)[:100]

    def _assert_preview(self, nid, scope, actor, row):
        if row['created_by'] != actor: raise ValueError('BROKER_ACTOR_MISMATCH')
        if row['status'] != 'PREVIEW' or not row.get('chosen'): raise ValueError('BROKER_LEGAL_PREVIEW_REQUIRED')
        if row['sources'] != self._sources(nid, scope, row['request']['chapter_ids']): raise StaleSourceError('BROKER_SOURCES_CHANGED')
        current = self.current_route(row['chosen']['route_id'])
        if not current['available'] or current['fingerprint'] != row['chosen']['fingerprint'] or current['binding_hash'] != row['chosen']['binding_hash']:
            raise StaleSourceError('BROKER_ROUTE_CHANGED')
        constraints = row['request']
        if constraints.get('min_host_ram_mib') or constraints.get('min_host_vram_mib'):
            capacity = self.hardware_capacity()
            for required, available in ((constraints.get('min_host_ram_mib'), capacity.get('ram_mib')), (constraints.get('min_host_vram_mib'), capacity.get('vram_mib'))):
                if required and (current['cloud'] or available is None or available < required): raise StaleSourceError('BROKER_HOST_CAPACITY_CHANGED')
        if constraints.get('require_confirmed_license') and not (current['synthetic'] or current.get('identity', {}).get('license_confirmed')):
            raise StaleSourceError('BROKER_LICENSE_AUTHORITY_CHANGED')
        if current['cloud']:
            if constraints.get('policy') == 'PRIVACY_FIRST': raise ValueError('BROKER_PRIVACY_FIRST_LOCAL_ONLY')
            if constraints.get('policy') == 'LOCAL_FIRST' and not constraints.get('allow_cloud_fallback'): raise ValueError('BROKER_CLOUD_FALLBACK_NOT_APPROVED')
            if row['request']['profile'] == 'LOCAL_ONLY': raise ValueError('BROKER_LOCAL_ONLY')
            for cid in row['sources']:
                assert_current_manuscript_egress(self.chapters_for(scope), self.novels, nid, self.chapters_for(scope).get(cid), scope.get('branch_id'))
        return current

    def reserve(self, nid, scope, actor, preview_id, expected_version, idempotency_key, job_id, guard=lambda: None, authorization_digest=None):
        if not idempotency_key or len(idempotency_key) > 160 or not job_id or len(job_id) > 160: raise ValueError('BROKER_RESERVATION_ID_REQUIRED')
        row = self.get(nid, scope, self.DECISIONS, preview_id)
        check_version(row, expected_version)
        self._assert_preview(nid, scope, actor, row)
        guard()
        key = digest([actor, idempotency_key])
        with self.store.transaction(nid, scope) as doc:
            guard()
            ledger = doc['collections'].setdefault(self.LEDGER, {})
            old = ledger.get(key)
            if old:
                if old['preview_id'] != preview_id or old.get('authorization_digest') != authorization_digest or (authorization_digest is None and old['job_id'] != job_id): raise ValueError('BROKER_IDEMPOTENCY_MISMATCH')
                return copy.deepcopy(old)
            budget = self.budget(nid, scope)
            if budget['version'] != row['budget_version']: raise StaleSourceError('BROKER_BUDGET_CHANGED')
            price = self._price(row['chosen'], doc['collections'].get(self.PRICES, {}))
            if price != row['chosen']['price']: raise StaleSourceError('BROKER_PRICE_CHANGED')
            amount = price['reserve_microusd'] if price else None
            if amount is None and (budget['require_known_estimate'] or budget['limit_microusd'] is not None): raise ValueError('BROKER_PRICE_ESTIMATE_REQUIRED')
            if budget['inflight'] >= budget['max_inflight']: raise ValueError('BROKER_CONCURRENCY_LIMIT')
            if budget['unpriced_count'] or budget['overrun_count']: raise ValueError('BROKER_UPSTREAM_RECONCILIATION_REQUIRED')
            if budget['limit_microusd'] is not None and budget['committed_microusd'] + (amount or 0) > budget['limit_microusd']: raise ValueError('BROKER_BUDGET_EXCEEDED')
            entry = new_row(nid, scope, actor, {'preview_id': preview_id, 'job_id': job_id, 'authorization_digest': authorization_digest, 'status': 'RESERVED',
                'route_id': row['chosen']['route_id'], 'route_fingerprint': row['chosen']['fingerprint'],
                'provider_id': row['chosen']['provider_id'], 'model_id': row['chosen']['model_id'],
                'reserve_microusd': amount, 'accounted_microusd': amount, 'actual_microusd': None,
                'currency': 'USD', 'price': price, 'cost_state': 'RESERVED_ESTIMATE' if amount is not None else 'UNKNOWN',
                'dispatched': False, 'overrun': False})
            entry['id'] = key
            ledger[key] = entry
            return copy.deepcopy(entry)

    def guard_dispatch(self, nid, scope, actor, reservation_id, job_id, guard=lambda: None):
        entry = self.get(nid, scope, self.LEDGER, reservation_id)
        if entry['job_id'] != job_id or entry['created_by'] != actor: raise ValueError('BROKER_RESERVATION_AUTHORITY_MISMATCH')
        row = self.get(nid, scope, self.DECISIONS, entry['preview_id'])
        self._assert_preview(nid, scope, actor, row)
        with self.store.transaction(nid, scope) as doc:
            guard()
            entry = doc['collections'][self.LEDGER][reservation_id]
            if entry['status'] not in {'RESERVED', 'DISPATCHED'}: raise ValueError('BROKER_RESERVATION_TERMINAL')
            current_price = self._price(row['chosen'], doc['collections'].get(self.PRICES, {}))
            if current_price != entry['price']: raise StaleSourceError('BROKER_PRICE_CHANGED')
            if entry['status'] == 'RESERVED':
                change_row(entry, actor, entry['version'], lambda r: r.update(status='DISPATCHED', dispatched=True, dispatched_at=now()))
            return copy.deepcopy(entry)

    def finalize(self, nid, scope, actor, reservation_id, job_id, status, usage=None):
        """Host job-completion seam. Never exposed as a caller-supplied bill API.

        May finish accounting after permission/feature revocation, but cannot
        dispatch or release an ambiguous upstream hold under that exception.
        """
        if status not in {'COMPLETED', 'CANCELLED', 'FAILED', 'UNKNOWN'}: raise ValueError('BROKER_FINAL_STATUS_INVALID')
        with self.store.transaction(nid, scope) as doc:
            entry = doc['collections'].get(self.LEDGER, {}).get(reservation_id)
            if not entry or entry['job_id'] != job_id or entry['created_by'] != actor: raise ValueError('BROKER_RESERVATION_AUTHORITY_MISMATCH')
            if entry['status'] not in {'RESERVED', 'DISPATCHED'}: return copy.deepcopy(entry)
            actual = None
            price = entry['price'] or {}
            if not entry['dispatched']: actual = 0
            elif price.get('actual_known_zero'): actual = 0
            elif status == 'COMPLETED' and usage and all(isinstance(usage.get(k), int) and not isinstance(usage[k], bool) and usage[k] >= 0 for k in ('input_tokens', 'output_tokens')) and all(price.get(k) is not None for k in ('input_per_million_microusd', 'output_per_million_microusd')):
                actual = (usage['input_tokens'] * price['input_per_million_microusd'] + usage['output_tokens'] * price['output_per_million_microusd'] + 999999) // 1000000
            values = {'status': 'RELEASED' if not entry['dispatched'] else 'SETTLED' if actual is not None else 'UNKNOWN_UPSTREAM',
                      'job_status': status, 'actual_microusd': actual,
                      'accounted_microusd': actual if actual is not None else entry['reserve_microusd'],
                      'cost_state': 'KNOWN_SYNTHETIC_ZERO' if entry['dispatched'] and price.get('actual_known_zero') else 'CALCULATED_FROM_REPORTED_USAGE' if actual is not None and entry['dispatched'] else 'NOT_DISPATCHED' if not entry['dispatched'] else 'UNKNOWN_UPSTREAM',
                      'overrun': actual is not None and entry['reserve_microusd'] is not None and actual > entry['reserve_microusd']}
            change_row(entry, actor, entry['version'], lambda r: r.update(values))
            return copy.deepcopy(entry)

    def ledger(self, nid, scope, actor):
        return sorted((r for r in self.list(nid, scope, self.LEDGER) if r['created_by'] == actor), key=lambda r: r['created_at'], reverse=True)[:100]


    def reconcile(self, nid, scope, actor, rid, value, guard=lambda: None, allow_orphan=False):
        body = ReconcileInput.model_validate(value)
        def update(row):
            guard()
            if row['created_by'] != actor: raise ValueError('BROKER_RESERVATION_AUTHORITY_MISMATCH')
            orphan = row['status'] in {'RESERVED', 'DISPATCHED'} and allow_orphan and body.original_executor_stopped_confirmed
            if not orphan and row['status'] != 'UNKNOWN_UPSTREAM' and not (row['status'] == 'SETTLED' and row.get('overrun')):
                raise ValueError('BROKER_UPSTREAM_RECONCILIATION_NOT_ALLOWED')
            row.update(status='RECONCILED', actual_microusd=body.actual_microusd,
                accounted_microusd=body.actual_microusd, cost_state='USER_REPORTED_UPSTREAM_BILL',
                reconciliation_note=body.evidence_note, upstream_terminal_confirmed=True, original_executor_stopped_confirmed=body.original_executor_stopped_confirmed, reconciled_orphan=orphan,
                overrun=body.actual_microusd > (row['reserve_microusd'] or 0), overrun_acknowledged=True)
        return self.mutate(nid, scope, actor, self.LEDGER, rid, body.expected_version, update)
