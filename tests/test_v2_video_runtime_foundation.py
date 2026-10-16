"""Synthetic Comfy wire and real CPU WEBM; original File/PG owners, no model."""
from copy import deepcopy
from types import SimpleNamespace
import base64
import shutil
import subprocess

import httpx
import pytest

from app.asset_providers import AssetProviderRegistry, HttpVideoProvider, VideoGenerationRequest
from app.creative.production_execution import ProductionExecutionService
from app.creative.production_execution_models import MediaCommand, MediaCreate, MediaJobAction, MediaReview
from app.model_center.discovery_bridge import LocalDiscoveryBridge, LocalVideoAdapter
from app.model_runtime import ModelRegistry, ProviderRegistry
from app.services.image_job_service import ImageJobService
from app.services.video_assembly_service import VideoAssemblyService
from app.services.studio_video_provider import ComfyUIVideoProvider
from app.services.studio_video_provider_recipes import project_comfy_video_recipe, build_workflow, timing
from app.services.studio_image_provider_recipes import validate_workflow
from test_local_ai_discovery import service, scan, approve_license
from test_v2_independent_workspace import rig, import_asset, reopened, declaration
from app.experimental.common import StaleSourceError
from test_v2_image_provider_recipes import inline
from test_v2_media_probe_lifecycle import stall, assert_reaped
from contextlib import contextmanager
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event, get_ident

MODELS = {"WAN": "wan2.2_ti2v_5B_fp16.safetensors", "LTX": "ltx-video-2b-v0.9.5.safetensors",
    "HUNYUAN_VIDEO": "hunyuan_video_t2v_720p_bf16.safetensors"}


def object_info():
    def node(fields, outputs, optional=None):
        return {"input": {"required": {key: [value] for key, value in fields.items()},
            "optional": {key: [value] for key, value in (optional or {}).items()}}, "output": outputs}
    return {
        "UNETLoader": node({"unet_name": [MODELS['WAN'], MODELS['HUNYUAN_VIDEO']], "weight_dtype": ["default"]}, ["MODEL"]),
        "CheckpointLoaderSimple": node({"ckpt_name": [MODELS['LTX']]}, ["MODEL", "CLIP", "VAE"]),
        "CLIPLoader": node({"clip_name": ["umt5_xxl_fp8_e4m3fn_scaled.safetensors", "t5xxl_fp16.safetensors"], "type": ["wan", "ltxv"]}, ["CLIP"], {"device": ["default"]}),
        "DualCLIPLoader": node({"clip_name1": ["clip_l.safetensors"], "clip_name2": ["llava_llama3_fp8_scaled.safetensors"], "type": ["hunyuan_video"]}, ["CLIP"], {"device": ["default"]}),
        "VAELoader": node({"vae_name": ["wan2.2_vae.safetensors", "hunyuan_video_vae_bf16.safetensors"]}, ["VAE"]),
        "CLIPTextEncode": node({"text": "STRING", "clip": "CLIP"}, ["CONDITIONING"]),
        "ModelSamplingSD3": node({"model": "MODEL", "shift": "FLOAT"}, ["MODEL"]),
        "Wan22ImageToVideoLatent": node({"vae": "VAE", "width": "INT", "height": "INT", "length": "INT", "batch_size": "INT"}, ["LATENT"], {"start_image": "IMAGE"}),
        "EmptyHunyuanLatentVideo": node({"width": "INT", "height": "INT", "length": "INT", "batch_size": "INT"}, ["LATENT"]),
        "EmptyLTXVLatentVideo": node({"width": "INT", "height": "INT", "length": "INT", "batch_size": "INT"}, ["LATENT"]),
        "LTXVConditioning": node({"positive": "CONDITIONING", "negative": "CONDITIONING", "frame_rate": "FLOAT"}, ["CONDITIONING", "CONDITIONING"]),
        "LTXVScheduler": node({"steps": "INT", "max_shift": "FLOAT", "base_shift": "FLOAT", "stretch": "BOOLEAN", "terminal": "FLOAT"}, ["SIGMAS"], {"latent": "LATENT"}),
        "LTXVPreprocess": node({"image": "IMAGE", "img_compression": "INT"}, ["IMAGE"]),
        "LTXVImgToVideo": node({"positive": "CONDITIONING", "negative": "CONDITIONING", "vae": "VAE", "image": "IMAGE", "width": "INT", "height": "INT", "length": "INT", "batch_size": "INT", "strength": "FLOAT"}, ["CONDITIONING", "CONDITIONING", "LATENT"]),
        "KSampler": node({"model": "MODEL", "positive": "CONDITIONING", "negative": "CONDITIONING", "latent_image": "LATENT", "seed": "INT", "steps": "INT", "cfg": "FLOAT", "sampler_name": ["uni_pc"], "scheduler": ["simple"], "denoise": "FLOAT"}, ["LATENT"]),
        "KSamplerSelect": node({"sampler_name": ["euler"]}, ["SAMPLER"]),
        "SamplerCustom": node({"add_noise": "BOOLEAN", "noise_seed": "INT", "cfg": "FLOAT", "model": "MODEL", "positive": "CONDITIONING", "negative": "CONDITIONING", "sampler": "SAMPLER", "sigmas": "SIGMAS", "latent_image": "LATENT"}, ["LATENT", "LATENT"]),
        "FluxGuidance": node({"conditioning": "CONDITIONING", "guidance": "FLOAT"}, ["CONDITIONING"]),
        "BasicScheduler": node({"model": "MODEL", "scheduler": ["simple"], "steps": "INT", "denoise": "FLOAT"}, ["SIGMAS"]),
        "BasicGuider": node({"model": "MODEL", "conditioning": "CONDITIONING"}, ["GUIDER"]),
        "RandomNoise": node({"noise_seed": "INT"}, ["NOISE"]),
        "SamplerCustomAdvanced": node({"noise": "NOISE", "guider": "GUIDER", "sampler": "SAMPLER", "sigmas": "SIGMAS", "latent_image": "LATENT"}, ["LATENT", "LATENT"]),
        "VAEDecode": node({"samples": "LATENT", "vae": "VAE"}, ["IMAGE"]),
        "LoadImage": node({"image": ["source.png"]}, ["IMAGE", "MASK"]),
        "SaveWEBM": node({"images": "IMAGE", "filename_prefix": "STRING", "codec": ["vp9", "av1"], "fps": "FLOAT", "crf": "FLOAT"}, ["IMAGE"]),
    }


def enabled(tmp_path, family="WAN"):
    original, videos = service(tmp_path), {}
    endpoint = "http://127.0.0.1:8188"
    original.client.payloads[(endpoint, "/system_stats")] = {"system": {}}
    original.client.payloads[(endpoint, "/object_info")] = object_info()
    images = AssetProviderRegistry()
    original.route_bridge = LocalDiscoveryBridge(original, SimpleNamespace(provider_registry=ProviderRegistry(), model_registry=ModelRegistry()), images, videos)
    candidate = next(c for c in scan(original)['candidates'] if c['model_name'] == MODELS[family])
    validated = original.validate(candidate['id'])
    original.register(candidate['id']); approve_license(original, candidate['id']); original.enable(candidate['id'])
    return original, images, videos, videos[candidate['provider_id']], validated


class Wire:
    def __init__(self, data=b""):
        self.calls, self.info, self.data = [], object_info(), data
        self.after_upload = self.after_history = self.before_download = None
        self.receipt = {"filename": "studio-fixture.webm", "subfolder": "", "type": "output"}
        self.complete = True

    def get(self, url, **kw):
        self.calls.append((url, kw))
        if url.endswith('/object_info'): value = self.info
        elif '/history/' in url:
            value = {"prompt-1": {"status": {"completed": self.complete, "status_str": "success" if self.complete else "running"}, "outputs": {"9": {"images": [self.receipt]}} if self.complete else {}}}
            if self.after_history: self.after_history()
        elif url.endswith('/view'):
            if self.before_download: self.before_download()
            return httpx.Response(200, content=self.data, request=httpx.Request('GET', url))
        else: value = {"system": {}}
        return httpx.Response(200, json=value, request=httpx.Request('GET', url))

    def post(self, url, **kw):
        self.calls.append((url, kw))
        if url.endswith('/upload/image'):
            if self.after_upload: self.after_upload()
            value = {"name": "source.png", "type": "input", "subfolder": ""}
        else: value = {"prompt_id": "prompt-1", "id": "prompt-1"}
        return httpx.Response(200, json=value, request=httpx.Request('POST', url))


def cpu_video(tmp_path):
    assert shutil.which('ffmpeg'), 'real CPU media prerequisite ffmpeg required'
    assert shutil.which('ffprobe'), 'real CPU media prerequisite ffprobe required'
    path = tmp_path / 'fixture.webm'
    subprocess.run([shutil.which('ffmpeg'), '-nostdin', '-v', 'error', '-f', 'lavfi', '-i',
        'color=c=blue:s=64x64:r=8:d=0.5', '-c:v', 'libvpx-vp9', '-threads', '1', '-y', str(path)],
        check=True, capture_output=True, timeout=20)
    return path.read_bytes()


def configured(e, tmp_path, monkeypatch, family='WAN'):
    from app import asset_provider_config, audio_providers
    original, images, videos, adapter, validated = enabled(tmp_path, family)
    monkeypatch.setattr(asset_provider_config, 'load', lambda: {})
    monkeypatch.setattr(audio_providers, 'provider_catalog', lambda: [])
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,asset_lineage_v2,ai_execution_v2,model_broker_v2,author_context_inspector_v2')
    e.service.activate(e.nid, e.scope, e.actor)
    production = ProductionExecutionService(e.service, ImageJobService(e.root), images,
        VideoAssemblyService(e.root, e.assets), videos, {}, SimpleNamespace(), SimpleNamespace(), SimpleNamespace())
    wire = Wire(cpu_video(tmp_path)); adapter.delegate.transport = wire
    value = {'operation_id': 'm7.video.t2v', 'request_id': 'synthetic-video-phase4',
        'provider_id': adapter.candidate['provider_id'], 'model_id': adapter.candidate['id'],
        'prompt': 'SYNTHETIC PRIVATE VIDEO', 'parameters': {'width': 64, 'height': 64, 'duration_seconds': 1, 'frame_rate': 8, 'seed': 7}}
    return original, production, adapter, wire, value


def action(job):
    return MediaJobAction(expected_version=job['version'], expected_request_digest=job['request_digest'])


def queued(e, production, value):
    preview, _, _ = production.preview(e.nid, e.scope, e.actor, value, lambda: None)
    job = production.create(e.nid, e.scope, e.actor, MediaCreate(command=MediaCommand.model_validate(value), reviewed_preview_digest=preview['preview_digest']), lambda: None)
    return preview, job


@pytest.mark.parametrize('family', MODELS)
def test_exact_metadata_enable_routes_original_video_owner_without_inference(tmp_path, family):
    original, images, videos, adapter, validated = enabled(tmp_path, family)
    assert type(adapter) is LocalVideoAdapter and images._providers == {}
    assert validated['verified_capabilities'] == ['VIDEO'] and validated['verified'] is False
    config = adapter.studio_configuration()
    assert config['video_recipe']['inference_verified'] is False and config['video_recipe']['structural_only'] is True
    assert original.center.lifecycle.start.call_count == 0
    original.disable(adapter.candidate['id'])
    assert videos == {}
    with pytest.raises(ValueError): adapter.studio_configuration()


@pytest.mark.parametrize('family', MODELS)
@pytest.mark.parametrize('bad', ['missing_output', 'wrong_link', 'unknown_required', 'missing_component', 'wrong_model'])
def test_metadata_names_do_not_grant_recipe_capability(family, bad):
    info, model = object_info(), MODELS[family]
    if bad == 'missing_output': del info['SaveWEBM']
    elif bad == 'wrong_link': info['VAEDecode']['output'] = ['LATENT']
    elif bad == 'unknown_required': info['SaveWEBM']['input']['required']['command'] = ['STRING']
    elif bad == 'missing_component': del info['CLIPLoader' if family != 'HUNYUAN_VIDEO' else 'DualCLIPLoader']
    else: model = 'unknown-video-version.safetensors'
    assert project_comfy_video_recipe(info, model, family) is None


@pytest.mark.parametrize('family', MODELS)
def test_fixed_recipe_validated_before_manual_send_and_only_known_output_node(tmp_path, family):
    wire = Wire(b'not-used-until-original-owner-validates')
    recipe = project_comfy_video_recipe(wire.info, MODELS[family], family)
    provider = ComfyUIVideoProvider(wire, 'http://127.0.0.1:8188', recipe)
    guards = []
    request = VideoGenerationRequest('local', MODELS[family], 'synthetic', '', '', 'task', parameters={'width': 64, 'height': 64}, dispatch_guard=lambda: guards.append('guard'))
    result = provider.generate(request)
    assert result.status == 'RUNNING' and result.video_uri is None
    graph = next(kw['json']['prompt'] for url, kw in wire.calls if url.endswith('/prompt'))
    validate_workflow(wire.info, graph)
    assert graph['9']['class_type'] == 'SaveWEBM' and graph['9']['inputs']['codec'] == 'vp9' and len(guards) >= 4
    wire.receipt['filename'] = '../private.webm'
    with pytest.raises(ValueError, match='OUTPUT_RECEIPT_INVALID'): provider.get_status('prompt-1')
    assert not any(url.endswith('/view') for url, _ in wire.calls)


@pytest.mark.parametrize('parameters', [{'width': 2048}, {'duration_seconds': 11}, {'frame_rate': 31}, {'seed': True}, {'width': 65}, {'command': 'bad'}])
def test_local_recipe_bounds_before_network(parameters):
    wire = Wire(); recipe = project_comfy_video_recipe(wire.info, MODELS['WAN'], 'WAN')
    provider = ComfyUIVideoProvider(wire, 'http://127.0.0.1:8188', recipe)
    with pytest.raises(ValueError): provider.generate(VideoGenerationRequest('p', MODELS['WAN'], 'synthetic', '', '', 'task', parameters=parameters))
    assert wire.calls == []


def test_original_file_pg_private_video_refresh_review_and_reopen(rig, tmp_path, monkeypatch):
    e = rig
    original, production, adapter, wire, value = configured(e, tmp_path, monkeypatch)
    before = list(original.client.calls)
    providers = production.providers(e.nid, e.scope, e.actor, lambda: None)
    assert {r['operation_id'] for r in providers['items']} == {'m7.video.t2v', 'm7.video.i2v'}
    assert original.client.calls == before and wire.calls == []
    preview, job = queued(e, production, value)
    assert preview['execution_recipe']['adapter'] == 'COMFYUI_BUILTIN_VIDEO'
    running = production.execute(e.nid, e.scope, e.actor, 'video', job['id'], action(job), lambda: None)
    assert running['status'] == 'REMOTE_RUNNING' and running['output_candidate'] is None
    ready = production.refresh_video(e.nid, e.scope, e.actor, job['id'], action(running), lambda: None)
    assert ready['status'] == 'AWAITING_REVIEW' and ready['approved_asset_version'] is None
    candidate = ready['output_candidate']
    with pytest.raises(FileNotFoundError): e.service.asset(e.nid, e.scope, candidate['id'])
    approved = production.review(e.nid, e.scope, e.actor, 'video', job['id'], MediaReview(
        expected_version=ready['version'], expected_request_digest=ready['request_digest'], reviewed_output_digest=candidate['digest']), lambda: None)
    assert approved['status'] == 'APPROVED' and approved['approved_asset_version'] == 2
    assert reopened(e).asset(e.nid, e.scope, candidate['id'])['media_type'] == 'video/webm'
    assert sum(url.endswith('/prompt') for url, _ in wire.calls) == 1 and original.center.lifecycle.start.call_count == 0


def test_disable_after_image_upload_prevents_video_submission(tmp_path):
    original, _, _, adapter, _ = enabled(tmp_path)
    wire = Wire(); adapter.delegate.transport = wire
    wire.after_upload = lambda: original.disable(adapter.candidate['id'])
    with pytest.raises(ValueError):
        adapter.generate(VideoGenerationRequest(adapter.candidate['provider_id'], adapter.candidate['id'], 'synthetic', inline(), '', 'task', parameters={'width': 64, 'height': 64}, dispatch_guard=lambda: None))
    assert not any(url.endswith('/prompt') for url, _ in wire.calls)


def test_disable_during_history_prevents_output_download(tmp_path):
    original, _, _, adapter, _ = enabled(tmp_path)
    wire = Wire(); adapter.delegate.transport = wire
    wire.after_history = lambda: original.disable(adapter.candidate['id'])
    with pytest.raises(ValueError): adapter.get_status('prompt-1', dispatch_guard=lambda: None)
    assert not any(url.endswith('/view') for url, _ in wire.calls)


def test_explicit_local_cancel_never_refreshes_or_promotes(rig, tmp_path, monkeypatch):
    e = rig; _, production, _, wire, value = configured(e, tmp_path, monkeypatch)
    _, job = queued(e, production, value)
    running = production.execute(e.nid, e.scope, e.actor, 'video', job['id'], action(job), lambda: None)
    cancelled = production.cancel(e.nid, e.scope, e.actor, 'video', job['id'], action(running), lambda: None)
    assert cancelled['status'] == 'CANCELLED' and cancelled['output_candidate'] is None
    before = len(wire.calls)
    with pytest.raises(ValueError): production.refresh_video(e.nid, e.scope, e.actor, job['id'], action(cancelled), lambda: None)
    assert len(wire.calls) == before


def test_reference_roles_are_opt_in_and_exact_original_asset_pin():
    source = {'kind': 'ASSET', 'id': 'video-source', 'version': 1, 'digest': 'a' * 64, 'asset_kind': 'video'}
    value = {'operation_id': 'm7.video.v2v', 'request_id': 'reference-video', 'provider_id': 'p', 'model_id': 'm', 'prompt': 'synthetic', 'source_snapshots': [source]}
    legacy = MediaCommand.model_validate(value).model_dump()
    assert 'video_reference' not in legacy
    rich = MediaCommand.model_validate({**value, 'video_reference': {'source': source, 'purpose': 'camera'}}).model_dump()
    assert rich['video_reference']['purpose'] == 'camera'
    with pytest.raises(ValueError): MediaCommand.model_validate({**value, 'video_reference': {'source': {**source, 'version': 2}, 'purpose': 'camera'}})
    wire = Wire(); provider = HttpVideoProvider(wire, 'http://127.0.0.1:9000', '', video_to_video=True)
    provider.generate(VideoGenerationRequest('p', 'm', 'synthetic', '', '', 'job', source_video_uri='data:video/webm;base64,AA==', reference_purpose='camera'))
    assert wire.calls[-1][1]['json']['reference_purpose'] == 'camera'


@pytest.mark.parametrize('status', [{'completed': False, 'status_str': 'running'}, {'completed': True, 'status_str': 'error'}, {'completed': True}])
def test_nonterminal_or_unproven_history_outputs_never_download(status):
    wire = Wire(b'not-publication-ready')
    recipe = project_comfy_video_recipe(wire.info, MODELS['WAN'], 'WAN')
    provider = ComfyUIVideoProvider(wire, 'http://127.0.0.1:8188', recipe)
    original_get = wire.get
    def get(url, **kw):
        if '/history/' in url:
            wire.calls.append((url, kw))
            return httpx.Response(200, json={'prompt-1': {'status': status,
                'outputs': {'9': {'images': [wire.receipt]}}}}, request=httpx.Request('GET', url))
        return original_get(url, **kw)
    wire.get = get
    if status == {'completed': True}:
        with pytest.raises(ValueError, match='TERMINAL_STATUS_INVALID'): provider.get_status('prompt-1')
    else:
        assert provider.get_status('prompt-1')['status'] in {'RUNNING', 'FAILED'}
    assert not any(url.endswith('/view') for url, _ in wire.calls)


@pytest.mark.parametrize('phase', ['probe', 'decode'])
def test_first_video_source_probe_cancel_is_outside_asset_lease(rig, tmp_path, monkeypatch, stall, phase):
    e = rig; _, production, _, wire, _ = configured(e, tmp_path, monkeypatch)
    provider = HttpVideoProvider(wire, 'http://127.0.0.1:9000', '', 'fixture-model', video_to_video=True)
    production.video_providers = {'fixture-provider': provider}
    production.video_configs = {'fixture-provider': {'enabled': True, 'local': True, 'requires_credential': False,
        'endpoint': provider.endpoint, 'model_id': 'fixture-model', 'video_to_video': True}}
    source = import_asset(e, data=wire.data, filename='reference.webm', kind='video')
    pin = {'kind': 'ASSET', 'asset_kind': 'video', 'id': source['id'], 'version': source['version'], 'digest': source['sha256']}
    value = {'operation_id': 'm7.video.v2v', 'request_id': 'cancel-video-probe-' + phase, 'provider_id': 'fixture-provider',
        'model_id': 'fixture-model', 'prompt': 'SYNTHETIC', 'source_snapshots': [pin], 'video_reference': {'source': pin, 'purpose': 'camera'}}
    _, job = queued(e, production, value)
    lease_depth, worker_thread = {}, []
    original_scope, original_read = e.service._asset_scope, production.video_owner._studio_read
    @contextmanager
    def asset_scope(*args, **kw):
        thread = get_ident()
        with original_scope(*args, **kw):
            lease_depth[thread] = lease_depth.get(thread, 0) + 1
            try: yield
            finally: lease_depth[thread] -= 1
    def read(*args, **kw):
        if worker_thread and get_ident() == worker_thread[0]:
            assert lease_depth.get(get_ident(), 0) == 0, 'video inspection task check under Asset lease would reverse the lock order'
        return original_read(*args, **kw)
    monkeypatch.setattr(e.service, '_asset_scope', asset_scope)
    monkeypatch.setattr(production.video_owner, '_studio_read', read)
    inspected = Event()
    def observed():
        assert lease_depth.get(get_ident(), 0) == 0
        inspected.set()
    processes, directories = stall(phase, observed)
    def execute():
        worker_thread.append(get_ident())
        return production.execute(e.nid, e.scope, e.actor, 'video', job['id'], action(job), lambda: None)
    with ThreadPoolExecutor(max_workers=1) as worker:
        result = worker.submit(execute)
        assert inspected.wait(3), 'source inspection did not start'
        started = time.monotonic()
        cancelled = production.cancel(e.nid, e.scope, e.actor, 'video', job['id'], action(job), lambda: None)
        assert cancelled['status'] == 'CANCELLED'
        with pytest.raises(ValueError, match='STUDIO_VIDEO_ATTEMPT_CHANGED'): result.result(timeout=5)
        assert time.monotonic() - started < 5
    assert_reaped(processes, directories)
    cancelled = production.get(e.nid, e.scope, e.actor, 'video', job['id'], lambda: None)
    assert cancelled['status'] == 'CANCELLED' and cancelled['output_candidate'] is None and wire.calls == []


@pytest.mark.parametrize('state', ['RUNNING', 'SEND_RESERVED'])
def test_other_thread_cancel_before_or_during_submission_discards_late_receipt_without_replay(rig, tmp_path, monkeypatch, state):
    e = rig; _, production, adapter, wire, value = configured(e, tmp_path, monkeypatch)
    _, job = queued(e, production, value)
    entered, release = Event(), Event()
    if state == 'RUNNING':
        original_generate = adapter.generate
        def generate(request):
            entered.set()
            assert release.wait(5)
            return original_generate(request)
        monkeypatch.setattr(adapter, 'generate', generate)
    else:
        original_post = wire.post
        def post(url, **kw):
            response = original_post(url, **kw)
            if url.endswith('/prompt'):
                entered.set()
                assert release.wait(5)
            return response
        wire.post = post
    with ThreadPoolExecutor(max_workers=1) as worker:
        result = worker.submit(production.execute, e.nid, e.scope, e.actor, 'video', job['id'], action(job), lambda: None)
        assert entered.wait(3)
        current = production.get(e.nid, e.scope, e.actor, 'video', job['id'], lambda: None)
        assert current['status'] == state
        cancelled = production.cancel(e.nid, e.scope, e.actor, 'video', job['id'], action(current), lambda: None)
        assert cancelled['status'] == 'CANCELLED' and cancelled['remote_compute_may_continue'] is True
        release.set()
        with pytest.raises((ValueError, RuntimeError)): result.result(timeout=5)
    after = production.get(e.nid, e.scope, e.actor, 'video', job['id'], lambda: None)
    assert after['status'] == 'CANCELLED' and after['output_candidate'] is None and after['automatic_replay'] is False
    count = sum(url.endswith('/prompt') for url, _ in wire.calls)
    assert count == (1 if state == 'SEND_RESERVED' else 0)
    with pytest.raises(ValueError): production.execute(e.nid, e.scope, e.actor, 'video', job['id'], action(after), lambda: None)
    with pytest.raises(ValueError): production.reconcile(e.nid, e.scope, e.actor, 'video', job['id'], action(after), lambda: None)
    assert sum(url.endswith('/prompt') for url, _ in wire.calls) == count


def test_cancel_cannot_overwrite_reserved_human_review_or_promoted_asset(rig, tmp_path, monkeypatch):
    from app.services.v1_capability_service import CapabilityVersionConflict
    e = rig; _, production, _, wire, value = configured(e, tmp_path, monkeypatch)
    _, job = queued(e, production, value)
    running = production.execute(e.nid, e.scope, e.actor, 'video', job['id'], action(job), lambda: None)
    ready = production.refresh_video(e.nid, e.scope, e.actor, job['id'], action(running), lambda: None)
    entered, release = Event(), Event()
    original_promote = e.assets.promote_owned
    def promote(*args, **kw):
        entered.set()
        assert release.wait(5)
        return original_promote(*args, **kw)
    monkeypatch.setattr(e.assets, 'promote_owned', promote)
    review = MediaReview(expected_version=ready['version'], expected_request_digest=ready['request_digest'],
        reviewed_output_digest=ready['output_candidate']['digest'])
    with ThreadPoolExecutor(max_workers=2) as worker:
        reviewing = worker.submit(production.review, e.nid, e.scope, e.actor, 'video', job['id'], review, lambda: None)
        assert entered.wait(3)
        cancelled = worker.submit(production.cancel, e.nid, e.scope, e.actor, 'video', job['id'], action(ready), lambda: None)
        # This caller cannot adopt a new REVIEWING version or erase promotion.
        release.set()
        approved = reviewing.result(timeout=5)
        with pytest.raises(CapabilityVersionConflict): cancelled.result(timeout=5)
    assert approved['status'] == 'APPROVED'
    asset = e.service.asset(e.nid, e.scope, approved['output_candidate']['id'])
    assert asset['version'] == 2 and asset['sha256'] == approved['output_candidate']['digest']
    with pytest.raises(ValueError): production.cancel(e.nid, e.scope, e.actor, 'video', job['id'], action(approved), lambda: None)


@pytest.mark.parametrize('phase', ['before_send', 'before_review'])
def test_exact_original_image_version_fences_video_dispatch_and_promotion(rig, tmp_path, monkeypatch, phase):
    e = rig; _, production, _, wire, value = configured(e, tmp_path, monkeypatch)
    source = import_asset(e)
    pin = {'kind': 'ASSET', 'asset_kind': 'image', 'id': source['id'], 'version': source['version'], 'digest': source['sha256']}
    value.update(operation_id='m7.video.i2v', request_id='stale-video-' + phase, source_snapshots=[pin])
    _, job = queued(e, production, value)
    if phase == 'before_review':
        running = production.execute(e.nid, e.scope, e.actor, 'video', job['id'], action(job), lambda: None)
        ready = production.refresh_video(e.nid, e.scope, e.actor, job['id'], action(running), lambda: None)
    e.service.annotate(e.nid, e.scope, e.actor, source['id'], declaration(source['version']))
    if phase == 'before_send':
        with pytest.raises(StaleSourceError): production.execute(e.nid, e.scope, e.actor, 'video', job['id'], action(job), lambda: None)
        assert wire.calls == []
    else:
        with pytest.raises(StaleSourceError):
            production.review(e.nid, e.scope, e.actor, 'video', job['id'], MediaReview(expected_version=ready['version'],
                expected_request_digest=ready['request_digest'], reviewed_output_digest=ready['output_candidate']['digest']), lambda: None)
        with pytest.raises(FileNotFoundError): e.service.asset(e.nid, e.scope, ready['output_candidate']['id'])
        assert production.get(e.nid, e.scope, e.actor, 'video', job['id'], lambda: None)['status'] == 'AWAITING_REVIEW'


def test_uncertain_local_submission_preserves_original_unknown_no_replay(rig, tmp_path, monkeypatch):
    e = rig; _, production, _, wire, value = configured(e, tmp_path, monkeypatch)
    _, job = queued(e, production, value)
    original_post = wire.post
    def post(url, **kw):
        result = original_post(url, **kw)
        if url.endswith('/prompt'): raise RuntimeError('synthetic response lost after accepted send')
        return result
    wire.post = post
    with pytest.raises(RuntimeError): production.execute(e.nid, e.scope, e.actor, 'video', job['id'], action(job), lambda: None)
    unknown = production.get(e.nid, e.scope, e.actor, 'video', job['id'], lambda: None)
    assert unknown['status'] == 'UNKNOWN' and unknown['output_candidate'] is None and unknown['automatic_replay'] is False
    assert sum(url.endswith('/prompt') for url, _ in wire.calls) == 1
    with pytest.raises(ValueError): production.execute(e.nid, e.scope, e.actor, 'video', job['id'], action(unknown), lambda: None)
    reconciled = production.reconcile(e.nid, e.scope, e.actor, 'video', job['id'], action(unknown), lambda: None)
    assert reconciled['status'] == 'UNKNOWN' and sum(url.endswith('/prompt') for url, _ in wire.calls) == 1
