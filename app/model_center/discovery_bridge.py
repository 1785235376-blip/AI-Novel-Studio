"""Explicit-enable bridge to the application's existing text/image registries.

Discovery/enable never calls generation or starts processes. The live guard is
checked again by the adapter at dispatch, so disabled registrations cannot route.
"""
from __future__ import annotations

import threading
import time
from dataclasses import replace
from urllib.parse import urlsplit

from ..asset_providers import Automatic1111ImageProvider, ComfyUIImageProvider
from ..model_runtime import (GenerationEvent, GenerationUsage, ModelDescriptor, ModelRuntimeError, Modality,
    ProviderDescriptor, RuntimeErrorCode, TextGenerationResponse)
from .discovery_probes import LocalProbeClient, ProbeFailure
from .discovery_types import LocalRuntimeInput, local_endpoint
from .domain import Capability, RuntimeDefinition, RuntimeManagement, RuntimeType
from .runtime_profiles import resynthesize_runtime_argv


class _LocalImageTransport:
    def __init__(self, endpoint): self.endpoint = local_endpoint(endpoint)
    def _request(self, method, url, **kwargs):
        import httpx
        # All dynamic ComfyUI paths remain on the same already-approved origin.
        parsed, origin = urlsplit(url), urlsplit(self.endpoint)
        if (parsed.scheme, parsed.netloc) != (origin.scheme, origin.netloc) or parsed.username or parsed.password:
            raise ValueError('LOCAL_AI_DESTINATION_REJECTED')
        with httpx.Client(trust_env=False, follow_redirects=False, timeout=kwargs.pop('timeout', 30)) as client:
            with client.stream(method, url, **kwargs) as response:
                if response.is_redirect: raise ValueError('LOCAL_AI_REDIRECT_REJECTED')
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > 64 * 1024 * 1024: raise ValueError('LOCAL_AI_RESPONSE_TOO_LARGE')
                return httpx.Response(response.status_code, headers=response.headers, content=bytes(body), request=response.request)
    def get(self, url, **kwargs): return self._request('GET', url, **kwargs)
    def post(self, url, **kwargs): return self._request('POST', url, **kwargs)


class LocalTextAdapter:
    def __init__(self, bridge, candidate):
        self.bridge, self.candidate = bridge, candidate
        self.provider_id = candidate['provider_id']
        self.client = LocalProbeClient(timeout=120)
        self.execution_lock = threading.Lock()

    def health_check(self):
        try:
            self.bridge.guard(self.candidate['id'])
            config = self.candidate['runtime_config']
            if config['management'] == 'MANAGED': return bool(config.get('executable'))
            path = '/api/tags' if config['type'] == 'OLLAMA' else '/v1/models'
            self.bridge.service.client.json(config['endpoint'], path)
            return True
        except (ValueError, KeyError, ModelRuntimeError): return False

    def generate_text(self, request):
        with self.execution_lock:
            candidate = self.bridge.guard(self.candidate['id'])
            config = candidate['runtime_config']
            if request.cancellation and request.cancellation.is_set():
                raise ModelRuntimeError(RuntimeErrorCode.CANCELLED, '已停止生成')
            managed = None
            started = time.monotonic()
            try:
                if config['type'] == 'LLAMA_CPP' and config['management'] == 'MANAGED':
                    managed = self.bridge.launch_on_demand(candidate)
                self.bridge.guard(candidate['id'])
                # Waiting for a managed process is preparation, not dispatch.
                # Re-authorize after startup and reject cancellation before any prompt leaves.
                if request.dispatch_guard is not None:
                    request.dispatch_guard()
                if request.cancellation and request.cancellation.is_set():
                    raise ModelRuntimeError(RuntimeErrorCode.CANCELLED, '已停止生成')
                if config['type'] == 'OLLAMA':
                    options = {}
                    if request.parameters.temperature is not None: options['temperature'] = request.parameters.temperature
                    if request.parameters.max_output_tokens is not None: options['num_predict'] = request.parameters.max_output_tokens
                    if request.parameters.stop_sequences: options['stop'] = list(request.parameters.stop_sequences)
                    body = {'model': candidate['model_name'], 'prompt': request.prompt, 'stream': False, 'options': options}
                    if request.system_instruction: body['system'] = request.system_instruction
                    data = self.client.json(config['endpoint'], '/api/generate', body=body)
                    text = data.get('response'); usage = GenerationUsage(data.get('prompt_eval_count'), data.get('eval_count'))
                else:
                    messages = [{'role':'user', 'content':request.prompt}]
                    if request.system_instruction: messages.insert(0, {'role':'system', 'content':request.system_instruction})
                    body = {'model': candidate['model_name'], 'messages': messages, 'stream': False}
                    if request.parameters.temperature is not None: body['temperature'] = request.parameters.temperature
                    if request.parameters.max_output_tokens is not None: body['max_tokens'] = request.parameters.max_output_tokens
                    if request.parameters.stop_sequences: body['stop'] = list(request.parameters.stop_sequences)
                    path = '/chat/completions' if config['endpoint'].endswith('/v1') else '/v1/chat/completions'
                    data = self.client.json(config['endpoint'], path, body=body)
                    text = ((data.get('choices') or [{}])[0].get('message') or {}).get('content')
                    usage = None
                if request.cancellation and request.cancellation.is_set():
                    raise ModelRuntimeError(RuntimeErrorCode.CANCELLED, '已停止生成')
                if not isinstance(text, str) or not text.strip():
                    raise ModelRuntimeError(RuntimeErrorCode.GENERATION_FAILED, '本地模型未返回正文')
                return TextGenerationResponse(text, 'completed', request.provider_id, request.model_id, usage,
                    int((time.monotonic()-started)*1000), execution_mode='real')
            except ProbeFailure as exc:
                raise ModelRuntimeError(RuntimeErrorCode.PROVIDER_UNAVAILABLE, '本地模型暂时不可用', retryable=True) from exc
            finally:
                if managed: self.bridge.service.center.lifecycle.stop(managed)

    def stream_text(self, request):
        yield GenerationEvent('generation.started', request.job_id)
        response = self.generate_text(request)
        yield GenerationEvent('generation.delta', request.job_id, delta=response.text)
        yield GenerationEvent('generation.completed', request.job_id, response=response)


class LocalImageAdapter:
    def __init__(self, bridge, candidate):
        self.bridge, self.candidate = bridge, candidate
        self.endpoint = candidate['runtime_config']['endpoint']
        self.default_model = candidate['id']
        cls = Automatic1111ImageProvider if candidate['runtime_type'] == 'AUTOMATIC1111' else ComfyUIImageProvider
        self.delegate = cls(_LocalImageTransport(self.endpoint), self.endpoint)
    def health_check(self):
        try: self.bridge.guard(self.candidate['id']); return self.delegate.health_check()
        except (ValueError, KeyError, ModelRuntimeError): return False
    def generate(self, request):
        candidate = self.bridge.guard(self.candidate['id'])
        if request.model_id not in {'', candidate['id'], candidate['model_name']}:
            raise ValueError('LOCAL_AI_MODEL_MISMATCH')
        result = self.delegate.generate(replace(request, model_id=candidate['model_name']))
        return replace(result, model_id=candidate['id'])


class LocalDiscoveryBridge:
    def __init__(self, service, runtime, asset_registry):
        self.service, self.runtime, self.asset_registry = service, runtime, asset_registry
        self.launch_lock = threading.RLock()
        # Reuse already-saved legacy runtime endpoints without probing them.
        # Non-loopback historical configurations are excluded, never broadened.
        providers = getattr(runtime, 'providers', {})
        ollama = providers.get('ollama')
        sources = []
        if ollama is not None:
            sources.append(('configured-ollama', 'Saved Ollama', 'OLLAMA', getattr(ollama, 'base_url', '')))
        for identifier, adapter in asset_registry._providers.items():
            if isinstance(adapter, ComfyUIImageProvider): kind = 'COMFYUI'
            elif isinstance(adapter, Automatic1111ImageProvider): kind = 'AUTOMATIC1111'
            else: continue
            sources.append(('configured-' + identifier, identifier, kind, getattr(adapter, 'endpoint', '')))
        for identifier, name, kind, endpoint in sources:
            try:
                config = LocalRuntimeInput(name=name, type=kind, endpoint=endpoint)
                service.configured_runtime_sources.append({'id': identifier, **config.model_dump()})
            except ValueError: continue

    def guard(self, identifier):
        with self.service.lock:
            candidate = self.service.registrations.get(identifier)
            if not candidate or not candidate.get('enabled') or not candidate.get('enable_eligible'):
                raise ModelRuntimeError(RuntimeErrorCode.MODEL_DISABLED, '本地模型尚未启用或需要重新验证')
            return candidate

    def __call__(self, candidate):
        provider_id = candidate['provider_id']
        enabled = bool(candidate.get('enabled'))
        if 'TEXT' in candidate.get('verified_capabilities', []) or self.runtime.model_registry.contains(provider_id, candidate['id']):
            adapter = LocalTextAdapter(self, candidate)
            self.runtime.provider_registry.register(ProviderDescriptor(provider_id, candidate['display_name'], 'local',
                frozenset({Modality.TEXT}), enabled, enabled, 'metadata_validated_inference_not_run' if enabled else 'disabled'), adapter, replace=True)
            self.runtime.model_registry.register(ModelDescriptor(candidate['id'], provider_id, candidate['display_name'],
                Modality.TEXT, frozenset({'generate', 'stream'}), candidate['runtime_config'].get('context_size'),
                streaming=False, enabled=enabled), replace=True)
        if enabled and 'IMAGE' in candidate['verified_capabilities']:
            if candidate['runtime_type'] not in {'COMFYUI','AUTOMATIC1111'}:
                raise ValueError('LOCAL_AI_IMAGE_ADAPTER_REQUIRED')
            self.asset_registry.register(provider_id, LocalImageAdapter(self, candidate))
        else:
            self.asset_registry.unregister(provider_id)

    def launch_on_demand(self, candidate):
        config = candidate['runtime_config']
        center = self.service.center
        runtime_id = 'local-managed-' + candidate['id']
        with self.launch_lock:
            if any(process.poll() is None for process in center.lifecycle._owned.values()):
                raise ModelRuntimeError(RuntimeErrorCode.PROVIDER_UNAVAILABLE, '已有托管模型运行，请先停止后重试')
            parsed = urlsplit(config['endpoint'])
            definition = RuntimeDefinition(runtime_id, RuntimeType.LLAMA_CPP, executable=config['executable'],
                base_url=config['endpoint'], bind_address=parsed.hostname or '127.0.0.1', port=parsed.port,
                health_endpoint='/v1/models', capabilities=(Capability.TEXT,), provider_adapter='OPENAI_COMPATIBLE_TEXT',
                management=RuntimeManagement.MANAGED, model_path=candidate['local_path'],
                context_size=config['context_size'], gpu_layers=config['gpu_layers'], threads=config.get('threads'), batch_size=config.get('batch_size'))
            definition = resynthesize_runtime_argv(definition)
            center.runtimes[runtime_id] = definition
            center.lifecycle.start(definition)
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                self.guard(candidate['id'])
                if center.lifecycle.health(definition).http_reachable: return runtime_id
                time.sleep(.25)
            raise ModelRuntimeError(RuntimeErrorCode.TIMEOUT, '本地运行时启动超时', retryable=True)
        except Exception:
            center.lifecycle.stop(runtime_id)
            raise
