"""Trusted-host-only SDK v1: explicit finite contracts, never a plugin loader.

A host must supply an already trusted in-process adapter object. There is no
import path, entry point string, package installer, shell or registration API.
Model adapters require the original bound executor and A06 authority; this
minimal host only permits the original pure local recipe functions.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Protocol
import time
from .store import canonical
from ..workflow_recipes import execute_local_recipe_node


@dataclass(frozen=True)
class AdapterCapabilities:
    adapter_id: str
    version: str
    node_types: tuple[str, ...]
    network: bool = False
    applies_manuscript: bool = False
    retry_safe: bool = True
    max_input_bytes: int = 32000
    max_output_bytes: int = 128000
    model_capability: str = 'NONE'
    runtime_requirement: str = 'TRUSTED_IN_PROCESS_LOCAL'
    input_schema: dict | None = None
    output_schema: dict | None = None


@dataclass(frozen=True)
class AdapterRequest:
    node_type: str
    input: dict
    request_id: str
    scope_digest: str
    timeout_seconds: float = 10
    retry_limit: int = 0


@dataclass(frozen=True)
class AdapterReceipt:
    request_id: str
    scope_digest: str
    output: dict
    attempts: int
    external_calls: int = 0
    model_called: bool = False
    applied: bool = False


class TrustedAdapter(Protocol):
    capabilities: AdapterCapabilities
    def execute(self, request: AdapterRequest) -> dict: ...


class LocalRecipeAdapter:
    capabilities = AdapterCapabilities('builtin.local-recipes', '1.0.0', ('draft_prepare', 'knowledge_candidates', 'shot_proposals'))
    def execute(self, request):
        return execute_local_recipe_node(request.node_type, request.input, {}, {})


class TransientAdapterError(RuntimeError): pass
class AdapterCancelled(RuntimeError): pass


def run_trusted_local(adapter: TrustedAdapter, request: AdapterRequest, *, authorize: Callable[[], None],
                      cancelled: Callable[[], bool] = lambda: False, monotonic=time.monotonic):
    """Cooperative before/after fences; no claim of preempting arbitrary code.

    Retry is opt-in, max one, only for an explicit transient exception and a
    host-declared idempotent pure adapter. Output after cancellation/timeout is
    discarded. Neither cancellation nor a retry authorizes external data egress.
    """
    caps = adapter.capabilities
    # These declarations narrow the trusted host. They never load/register code.
    if caps.runtime_requirement != 'TRUSTED_IN_PROCESS_LOCAL' or caps.model_capability != 'NONE':
        raise ValueError('SDK_LOCAL_HOST_RUNTIME_CAPABILITY_MISMATCH')
    from .declarative_agents import validate_object
    if caps.input_schema is not None: validate_object(caps.input_schema, request.input)
    if caps.network or caps.applies_manuscript: raise ValueError('SDK_LOCAL_HOST_DENIES_EGRESS_AND_APPLY')
    if request.node_type not in caps.node_types: raise ValueError('SDK_UNREGISTERED_NODE')
    if request.retry_limit not in {0, 1} or not 0 < request.timeout_seconds <= 300: raise ValueError('SDK_INVALID_BOUNDS')
    if request.retry_limit and not caps.retry_safe: raise ValueError('SDK_RETRY_NOT_SAFE')
    if len(canonical(request.input).encode()) > caps.max_input_bytes: raise ValueError('SDK_INPUT_LIMIT')
    started = monotonic()
    def guard():
        authorize()
        if cancelled(): raise AdapterCancelled('SDK_CANCELLED_OUTPUT_DISCARDED')
        if monotonic() - started > request.timeout_seconds: raise TimeoutError('SDK_TIMEOUT_OUTPUT_DISCARDED')
    for attempt in range(1, request.retry_limit + 2):
        guard()
        try: output = adapter.execute(request)
        except TransientAdapterError:
            guard()
            if attempt > request.retry_limit: raise
            continue
        guard()
        if not isinstance(output, dict) or len(canonical(output).encode()) > caps.max_output_bytes: raise ValueError('SDK_OUTPUT_LIMIT')
        if caps.output_schema is not None:
            validate_object(caps.output_schema, output)
            guard()
        return AdapterReceipt(request.request_id, request.scope_digest, output, attempt)
    raise RuntimeError('unreachable bounded adapter loop')


@dataclass(frozen=True)
class BoundModelReceipt:
    """Opaque original-host authority references, never credentials or code."""
    run_id: str
    node_id: str
    definition_digest: str
    author_request_digest: str
    broker_preview_id: str
    reviewed_preview_digest: str
    source_strategy: str
    max_output_bytes: int
    deadline: str
    max_cost_microusd: int = 0
    automatic_retry: bool = False


class BoundModelHost(Protocol):
    """Only a shipped trusted coordinator may implement this protocol.

    Preview must rebuild the actual AuthorPreparer payload and broker decision.
    Dispatch must stage a durable original Workflow claim before reservation and
    call JobManager.start_prepared once. Refresh must check current authority and
    exact source before admitting the original job's bounded draft into review.
    Cancel fences future admission and cooperatively cancels that same job.
    Missing/uncertain receipts never authorize replay or an alternative route.
    """
    def preview(self, ctx, run_id: str, value, guard: Callable[[], None]) -> dict: ...
    def dispatch(self, ctx, run_id: str, value, guard: Callable[[], None]) -> dict: ...
    def refresh(self, ctx, run_id: str, value, guard: Callable[[], None]) -> dict: ...
    def cancel(self, ctx, run_id: str) -> None: ...


def definition_contract(definition):
    """Serializable SDK seam over the persisted original agent schema.

    Capabilities describe requirements, not grants. Original broker/runtime
    authority is rechecked by the existing service before every dispatch.
    No adapter registry, installer, import path or executable payload exists.
    """
    from .declarative_agents import WorkflowAuthoring
    agent = WorkflowAuthoring.model_validate(definition).agent
    model = bool(agent.model_route)
    return {'schema_version': 1, 'model_capability': 'TEXT' if model else 'NONE',
        'capability_requirements': sorted(set(agent.capability_requirements) | ({'TEXT'} if model else {'LOCAL_RULES'})),
        'runtime_requirement': agent.runtime_requirement or ('ORIGINAL_BOUND_LOCAL_MODEL' if model else 'TRUSTED_IN_PROCESS_LOCAL'),
        'input_schema': agent.input_schema.model_dump(), 'output_schema': agent.output_schema.model_dump(),
        'schema_subset': 'FINITE_SCALAR_OBJECT', 'max_input_bytes': 32000, 'max_output_bytes': agent.max_output_bytes,
        'review_required': True, 'executable_plugins': 'DENY_ALL', 'permission_grants': [],
        'automatic_install': False, 'automatic_model_enable': False, 'cloud_fallback': False,
        'verification': 'CONTRACT_VERIFIED', 'real_model_verification': 'NOT_RUN'}
