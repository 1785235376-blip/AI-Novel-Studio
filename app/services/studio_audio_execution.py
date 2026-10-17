"""Studio operations over AudiobookService's original durable audio jobs.

There is no new queue or provider registry. The root supplies original scope,
source, dispatch and AssetLibrary publication/review owners as guarded callbacks.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
import threading
from urllib.parse import urlsplit
from uuid import uuid4

from ..audio_production_store import AudioStateVersionConflict
from ..audio_providers import AudioGenerationRequest
from ..media_files import MediaValidationError, fetch_media_bytes, inspect_media
from ..repositories.file.mutation_coordinator import workspace_mutation
from .audiobook_service import AudiobookError, timestamp

STUDIO_ORIGIN = "studio-audio-execution/1"
CAPABILITIES = {"m8.audio.speech": "TTS", "m8.audio.music": "MUSIC", "m8.audio.effects": "SFX", "m8.audio.trim": "TRIM"}
_ACTIVE: set[tuple[str, str, str]] = set()
_ACTIVE_LOCK = threading.RLock()
FADE_CONTROLS = {"fade_in_ms", "fade_out_ms"}
TRIM_CONTROLS = {"gain_db", "sample_rate", "channels", "output_format"} | FADE_CONTROLS
AUDIO_MP3_PROFILE = "studio-audio-mp3/1"


def trim_output_profile(parameters):
    if "output_format" in parameters and parameters["output_format"] not in ("FLAC", "MP3"):
        raise _error("STUDIO_AUDIO_TRIM_FORMAT_INVALID", "仅支持明确选择 FLAC 或 MP3，默认输出仍为 WAV", 400)
    if parameters.get("output_format") == "MP3":
        from .studio_audio_mp3_profile import SAMPLE_RATES
        if parameters["out_ms"] - parameters["in_ms"] < 10:
            raise _error("STUDIO_AUDIO_MP3_DURATION_INVALID", "MP3 片段至少 10 毫秒，以保留准确的解码时长", 400)
        if parameters.get("sample_rate", 48000) not in SAMPLE_RATES:
            raise _error("STUDIO_AUDIO_MP3_SAMPLE_RATE_INVALID", "MP3 采样率须明确选择编码器支持的值，不会自动降低采样率", 400)
    # Reserve bounded WAV header space before accepting a reviewed recipe.
    # Encoding never silently lowers requested rate, channels or duration.
    if (math.ceil((parameters["out_ms"] - parameters["in_ms"]) * parameters.get("sample_rate", 48000) / 1000)
            * parameters.get("channels", 2) * 2 + 4096 > 25 * 1024 * 1024):
        message = "所选压缩音频解码 PCM 参数超过原资产大小上限" if parameters.get("output_format") in ("FLAC", "MP3") else "所选 PCM WAV 参数超过原资产大小上限"
        raise _error("STUDIO_AUDIO_TRIM_BYTES_BUDGET_EXCEEDED", message, 400)
    channels = "MONO" if parameters.get("channels", 2) == 1 else "STEREO"
    if parameters.get("output_format") == "FLAC":
        return f"FLAC_S16_{parameters.get('sample_rate', 48000)}_{channels}_COMPRESSION5"
    if parameters.get("output_format") == "MP3":
        from .studio_audio_mp3_profile import bit_rate
        rate = parameters.get("sample_rate", 48000)
        return f"MP3_LIBMP3LAME_{rate}_{channels}_CBR{bit_rate(rate) // 1000}"
    return f"PCM_S16LE_WAV_{parameters.get('sample_rate', 48000)}_{channels}"



def _trim_filters(parameters):
    """Linear fades in trimmed-output time, after gain and before output conversion.

    No positive fade preserves the exact original gain-only (or empty) argv.
    Resampling, channel conversion and encoding remain the original output options.
    """
    filters = [f"volume={parameters['gain_db']:.17g}dB"] if "gain_db" in parameters else []
    fade_in, fade_out = parameters.get("fade_in_ms", 0), parameters.get("fade_out_ms", 0)
    if fade_in or fade_out:
        filters.append("asetpts=PTS-STARTPTS")
        if fade_in:
            filters.append(f"afade=t=in:st=0:d={fade_in / 1000:.3f}:curve=tri")
        if fade_out:
            start = parameters["out_ms"] - parameters["in_ms"] - fade_out
            filters.append(f"afade=t=out:st={start / 1000:.3f}:d={fade_out / 1000:.3f}:curve=tri")
    return ["-af", ",".join(filters)] if filters else []


def _trim_measurement(value, parameters):
    """Validate persisted actual-byte proof, never synthesize it from settings."""
    if parameters.get("output_format") == "FLAC":
        from .studio_audio_trim_profiles import validate_flac_measurement
        try:
            return validate_flac_measurement(value, parameters)
        except MediaValidationError:
            raise _error("STUDIO_AUDIO_MEASUREMENT_INVALID", "原 FLAC 实际输出证明不一致", 409) from None
    if parameters.get("output_format") == "MP3":
        from .studio_audio_mp3_profile import validate_mp3_measurement
        try:
            return validate_mp3_measurement(value, parameters)
        except MediaValidationError:
            raise _error("STUDIO_AUDIO_MEASUREMENT_INVALID", "原 MP3 实际输出证明不一致", 409) from None
    fields = {"duration_ms", "byte_count", "sample_rate", "channels", "sample_width", "container",
              "audio_codec", "profile_validation", "output_sha256"}
    if (not isinstance(value, dict) or set(value) != fields
            or any(type(value.get(key)) is not int for key in ("duration_ms", "byte_count", "sample_rate", "channels", "sample_width"))
            or not 0 < value["byte_count"] <= 25 * 1024 * 1024 or value["duration_ms"] < 1
            or abs(value["duration_ms"] - (parameters["out_ms"] - parameters["in_ms"])) > 2
            or value["sample_rate"] != parameters.get("sample_rate", 48000)
            or value["channels"] != parameters.get("channels", 2) or value["sample_width"] != 2
            or value["container"] != "wav" or value["audio_codec"] != "pcm_s16le"
            or value["profile_validation"] != "PCM_DECODED"):
        raise _error("STUDIO_AUDIO_MEASUREMENT_INVALID", "原音频实际输出证明不一致", 409)
    _sha(value["output_sha256"])
    return value


def _error(code, message, status=409):
    return AudiobookError(code, message, status)


def _canonical(value):
    try:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        raise _error("STUDIO_AUDIO_BINDING_INVALID", "音频请求或来源绑定无效", 400) from None
    if len(encoded) > 256 * 1024:
        raise _error("STUDIO_AUDIO_BINDING_LIMIT", "音频请求或来源绑定超过限制", 400)
    return encoded


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _name(value, limit=240):
    if not isinstance(value, str) or not 1 <= len(value) <= limit or value != value.strip() or any(ord(char) < 32 for char in value):
        raise _error("STUDIO_AUDIO_BINDING_INVALID", "音频标识或绑定无效", 400)
    return value


def _version(value):
    if type(value) is not int or value < 1:
        raise _error("STUDIO_AUDIO_VERSION_INVALID", "音频版本无效", 400)
    return value


def _sha(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
        raise _error("STUDIO_AUDIO_DIGEST_INVALID", "音频摘要无效", 400)
    return value


def _source_identity(value):
    if not isinstance(value, dict):
        raise _error("STUDIO_AUDIO_SOURCE_INVALID", "音频来源引用无效", 400)
    return (_name(value.get("id")), _version(value.get("version")), _sha(value.get("digest")), _name(value.get("kind")))


def _body(value):
    """Fresh owner admission; historical MP3 can never enter this path."""
    body = _body_shape(value)
    if body["parameters"].get("output_format") == "MP3" and "audio_profile" not in body:
        raise _error("STUDIO_AUDIO_PROFILE_REQUIRED", "MP3 须使用明确的版本化音频契约", 400)
    return body


def _body_shape(value):
    """Common strict shape, also used after stored owner/hash admission."""
    allowed = {"operation_id", "provider_id", "model_id", "prompt", "parameters", "source_snapshots", "audio_profile"}
    if not isinstance(value, dict) or set(value) - allowed or value.get("operation_id") not in CAPABILITIES:
        raise _error("STUDIO_AUDIO_OPERATION_UNSUPPORTED", "原音频 owner 不支持此操作", 400)
    operation = value["operation_id"]
    prompt = value.get("prompt", "")
    if not isinstance(prompt, str) or len(prompt) > 16_000 or "\x00" in prompt or (operation != "m8.audio.trim" and not prompt.strip()):
        raise _error("STUDIO_AUDIO_PROMPT_INVALID", "请提供有界且明确的音频文字输入", 400)
    parameters = value.get("parameters", {})
    if not isinstance(parameters, dict):
        raise _error("STUDIO_AUDIO_PARAMETERS_INVALID", "音频参数无效", 400)
    names = {"voice_id", "speech_rate"} if operation == "m8.audio.speech" else {"in_ms", "out_ms"} | TRIM_CONTROLS if operation == "m8.audio.trim" else {"duration_seconds", "seed"}
    if set(parameters) - names:
        raise _error("AUDIO_PARAMETER_UNSUPPORTED", "原音频操作不支持所选参数", 400)
    parameters = copy.deepcopy(parameters)
    if "audio_profile" in value and (value["audio_profile"] != AUDIO_MP3_PROFILE
            or operation != "m8.audio.trim" or parameters.get("output_format") != "MP3"):
        raise _error("STUDIO_AUDIO_PROFILE_INVALID", "音频版本化契约与原操作或格式不一致", 400)
    if operation == "m8.audio.speech":
        if "voice_id" in parameters: _name(parameters["voice_id"])
        rate = parameters.get("speech_rate", 1.0)
        if type(rate) not in {int, float} or not math.isfinite(rate) or not 0.5 <= rate <= 2.0:
            raise _error("AUDIO_PARAMETER_UNSUPPORTED", "原语音服务只支持 0.5 到 2.0 倍语速", 400)
        parameters["speech_rate"] = float(rate)
    elif operation == "m8.audio.trim":
        start, end = parameters.get("in_ms"), parameters.get("out_ms")
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= 600_000 or end - start > 120_000:
            raise _error("STUDIO_AUDIO_TRIM_RANGE_INVALID", "裁剪范围须在原音频内且最长 120 秒", 400)
        for key in FADE_CONTROLS.intersection(parameters):
            if type(parameters[key]) is not int or not 0 <= parameters[key] <= 120000:
                raise _error("STUDIO_AUDIO_FADE_INVALID", "淡入淡出须为非负整数毫秒", 400)
        if parameters.get("fade_in_ms", 0) + parameters.get("fade_out_ms", 0) > end - start:
            raise _error("STUDIO_AUDIO_FADE_RANGE_INVALID", "淡入淡出总时长不得超过裁剪后时长", 400)
        gain, rate, channels = parameters.get("gain_db", 0), parameters.get("sample_rate", 48000), parameters.get("channels", 2)
        if (type(gain) not in {int, float} or not math.isfinite(gain) or not -60 <= gain <= 12
                or type(rate) is not int or not 8000 <= rate <= 96000
                or type(channels) is not int or channels not in {1, 2}):
            raise _error("STUDIO_AUDIO_TRIM_PARAMETERS_INVALID", "音频增益、采样率或声道超出本地 WAV 参数范围", 400)
        if "output_format" in parameters and parameters["output_format"] not in ("FLAC", "MP3"):
            raise _error("STUDIO_AUDIO_TRIM_FORMAT_INVALID", "仅支持明确选择 FLAC 或 MP3，默认输出仍为 WAV", 400)
        trim_output_profile(parameters)
        if prompt:
            raise _error("STUDIO_AUDIO_TRIM_PROMPT_INVALID", "本地裁剪不使用生成提示词", 400)
    elif "duration_seconds" in parameters:
        duration = parameters["duration_seconds"]
        if type(duration) not in {int, float} or not math.isfinite(duration) or not 1 <= duration <= 600:
            raise _error("STUDIO_AUDIO_DURATION_INVALID", "音频生成时长须为 1 到 600 秒", 400)
    if "seed" in parameters and (type(parameters["seed"]) is not int or not 0 <= parameters["seed"] <= 2_147_483_647):
        raise _error("STUDIO_AUDIO_SEED_INVALID", "音频种子参数无效", 400)
    sources = value.get("source_snapshots", [])
    if not isinstance(sources, list) or len(sources) > 8:
        raise _error("STUDIO_AUDIO_SOURCE_INVALID", "音频来源数量无效", 400)
    identities = [_source_identity(source) for source in sources]
    if len({(source[0], source[3]) for source in identities}) != len(identities):
        raise _error("STUDIO_AUDIO_SOURCE_INVALID", "音频来源不得重复", 400)
    if operation == "m8.audio.trim" and (len(sources) != 1 or sources[0].get("kind") != "ASSET" or sources[0].get("asset_kind") != "audio"):
        raise _error("STUDIO_AUDIO_TRIM_SOURCE_REQUIRED", "裁剪须引用一个原音频资产", 400)
    if operation != "m8.audio.trim" and any(source.get("kind") != "CREATIVE_DOCUMENT" for source in sources):
        raise _error("STUDIO_AUDIO_GENERATION_SOURCE_UNSUPPORTED", "生成只接受原创作文本来源，不会假装消费音频引用", 400)
    return {"operation_id": operation, "provider_id": value.get("provider_id"), "model_id": value.get("model_id"),
            "prompt": prompt, "parameters": parameters, "source_snapshots": copy.deepcopy(sources),
            **({"audio_profile": value["audio_profile"]} if "audio_profile" in value else {})}


def _binding(value, body):
    required = {"scope_key", "incarnation", "actor", "request_id", "operation_id", "request_digest", "sources", "provider_binding", "rights"}
    optional = {"license_note", "command", "execution_recipe", "graph_binding"}
    if (not isinstance(value, dict) or not required.issubset(value) or set(value) - required - optional
            or value["operation_id"] != body["operation_id"]):
        raise _error("STUDIO_AUDIO_BINDING_REQUIRED", "须由原项目 owner 提供当前音频绑定", 403)
    for key in ("scope_key", "incarnation", "actor", "request_id"):
        _name(value[key], 2048 if key == "scope_key" else 240)
    _sha(value["request_digest"])
    if "graph_binding" in value:
        from ..creative.graph_media_binding import validate_graph_binding
        if value["graph_binding"] is None:
            raise ValueError("CREATIVE_GRAPH_MEDIA_BINDING_INVALID")
        validate_graph_binding(value["graph_binding"], value)
        if body["operation_id"] == "m8.audio.trim" and TRIM_CONTROLS.intersection(body["parameters"]):
            raise _error("STUDIO_AUDIO_CONTROLS_STANDALONE_ONLY", "新增音频控制仅支持独立音频制作入口", 400)
    if not isinstance(value["sources"], list) or value["sources"] != body["source_snapshots"]:
        raise _error("STUDIO_AUDIO_SOURCE_BINDING_MISMATCH", "当前来源与音频请求不一致", 409)
    if not isinstance(value["rights"], dict):
        raise _error("STUDIO_AUDIO_RIGHTS_BINDING_REQUIRED", "须保留当前原权限与许可声明", 403)
    provider = value["provider_binding"]
    if body["operation_id"] == "m8.audio.trim":
        if provider is not None or body["provider_id"] is not None or body["model_id"] is not None:
            raise _error("STUDIO_AUDIO_TRIM_PROVIDER_INVALID", "本地裁剪不使用生成 Provider", 400)
    else:
        fields = {"provider_id", "model_id", "endpoint", "local", "capability", "route_digest"}
        if not isinstance(provider, dict) or set(provider) != fields or type(provider.get("local")) is not bool:
            raise _error("STUDIO_AUDIO_PROVIDER_BINDING_REQUIRED", "须明确绑定原音频 Provider 与模型", 403)
        _name(provider["provider_id"]); _name(provider["model_id"]); _sha(provider["route_digest"])
        if provider["provider_id"] == "auto" or provider["provider_id"] != body["provider_id"] or provider["model_id"] != body["model_id"] or provider["capability"] != CAPABILITIES[body["operation_id"]]:
            raise _error("STUDIO_AUDIO_PROVIDER_BINDING_MISMATCH", "不得自动回退或更换已审核的原音频 Provider", 409)
        try:
            url = urlsplit(_name(provider["endpoint"], 2048))
            if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password or url.query or url.fragment:
                raise ValueError()
        except ValueError:
            raise _error("STUDIO_AUDIO_PROVIDER_ENDPOINT_INVALID", "原音频服务地址绑定无效", 400) from None
    # New profiles bind the exact same marker at every immutable layer. Old
    # marker-absent records keep their original bytes; null is never absence.
    if "audio_profile" in body and ("command" not in value or "execution_recipe" not in value):
        raise _error("STUDIO_AUDIO_PROFILE_BINDING_REQUIRED", "版本化音频请求缺少原命令或配方绑定", 403)
    for captured in (value.get("command"), value.get("execution_recipe")):
        if captured is not None and (not isinstance(captured, dict)
                or ("audio_profile" in captured) != ("audio_profile" in body)
                or captured.get("audio_profile") != body.get("audio_profile")):
            raise _error("STUDIO_AUDIO_PROFILE_BINDING_CHANGED", "音频命令、请求与配方的版本绑定不一致", 409)
    # Only fade-bearing requests gain this stricter existing-layer check.
    # Historical omitted controls retain their original bytes and admission.
    fade_bound = bool(FADE_CONTROLS.intersection(body["parameters"]))
    for captured in (value.get("command"), value.get("execution_recipe")):
        if isinstance(captured, dict) and isinstance(captured.get("parameters"), dict):
            fade_bound = fade_bound or bool(FADE_CONTROLS.intersection(captured["parameters"]))
    if fade_bound and ("command" not in value or "execution_recipe" not in value):
        raise _error("STUDIO_AUDIO_FADE_BINDING_REQUIRED", "淡入淡出缺少原命令或配方绑定", 403)
    if "audio_profile" in body or fade_bound:
        from ..creative.production_execution_models import MediaCommand
        try:
            command = MediaCommand.model_validate(value["command"])
            projected = command.model_dump(exclude={"request_id", "allow_cloud", "license_note"})
            projected["parameters"] = command.parameters.model_dump(exclude_none=True)
            projected["source_snapshots"] = [source.model_dump(exclude={"reference_only"}, exclude_none=True)
                for source in command.source_snapshots]
            from ..experimental.store import canonical
            command_context = {key: item for key, item in value.items() if key not in {"command", "request_digest"}}
            request_digest = hashlib.sha256(canonical({"context": command_context, "command": value["command"]}).encode("utf-8")).hexdigest()
            if (_body(projected) != body or command.request_id != value["request_id"]
                    or request_digest != value["request_digest"]):
                raise ValueError("versioned command binding")
        except (ValueError, TypeError, KeyError):
            raise _error("STUDIO_AUDIO_FADE_BINDING_CHANGED" if fade_bound else "STUDIO_AUDIO_PROFILE_BINDING_CHANGED",
                "音频命令与原请求摘要不一致", 409) from None
    if "execution_recipe" in value:
        recipe = value["execution_recipe"]
        fields = {"contract", "operation_id", "adapter", "parameters", "automatic_fallback", "recipe_digest"}
        trim = body["operation_id"] == "m8.audio.trim"
        if trim: fields.add("output_profile")
        if "audio_profile" in body: fields.add("audio_profile")
        if (not isinstance(recipe, dict) or set(recipe) != fields
                or recipe.get("contract") != "studio-execution-recipe/1"
                or recipe.get("operation_id") != body["operation_id"]
                or recipe.get("adapter") != ("LOCAL_FFMPEG" if trim else "ORIGINAL_HTTP_PROVIDER")
                or recipe.get("automatic_fallback") is not False
                or (trim and recipe.get("output_profile") != trim_output_profile(body["parameters"]))
                or len(_canonical(recipe)) > 16 * 1024):
            raise _error("STUDIO_AUDIO_RECIPE_INVALID", "音频执行配方必须使用已审核的原操作参数", 400)
        recipe_body = _body_shape({**body, "parameters": recipe["parameters"]})
        if (recipe_body != body or _sha(recipe["recipe_digest"]) !=
                _digest({key: item for key, item in recipe.items() if key != "recipe_digest"})):
            raise _error("STUDIO_AUDIO_RECIPE_CHANGED", "音频执行配方与保存的请求不一致", 409)
    _canonical(value)
    return copy.deepcopy(value)


class StudioAudioExecution:
    """An additive owner adapter using the supplied AudiobookService/store."""
    def __init__(self, audiobook_service):
        self.service, self.store, self.assets = audiobook_service, audiobook_service.store, audiobook_service.assets
        self.branch_id = audiobook_service.branch_id

    def _active_key(self, nid, job_id):
        return (str(self.store.root.resolve()), nid, job_id)

    def _lease(self, nid, job_id):
        return workspace_mutation(self.store.root, "studio-audio-execution:" + _name(nid) + ":" + _name(job_id))

    def _atomic_job(self, nid, job_id, context):
        """Read an original atomic queue snapshot without taking its mutex.

        Asset commit callbacks already hold the asset lease. Taking the audio
        mutex there would invert the unchanged V1 audio -> asset lock order.
        The per-job execution lease and exact immutable/token/version checks
        provide the Studio fence; concurrent queue replacement fails closed.
        """
        path = self.store._path(nid)
        limit = 32 * 1024 * 1024
        try:
            with path.open("rb") as stream:
                before = os.fstat(stream.fileno())
                if not 0 < before.st_size <= limit: raise ValueError("queue snapshot limit")
                data = stream.read(limit + 1)
                after = os.fstat(stream.fileno())
            current = path.stat()
            stamp = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)
            if len(data) != before.st_size or stamp(before) != stamp(after) or stamp(after) != stamp(current):
                raise ValueError("queue snapshot changed")
            state = json.loads(data.decode("utf-8"))
            if (not isinstance(state, dict) or set(state) != {"voice_bindings", "pronunciation_dictionary", "jobs", "generations"}
                    or any(not isinstance(state[key], list) for key in state)
                    or any(not isinstance(row, dict) for row in state["jobs"])):
                raise ValueError("queue snapshot shape")
        except (OSError, ValueError, UnicodeError):
            raise _error("STUDIO_AUDIO_ATOMIC_RECEIPT_UNAVAILABLE", "原音频队列回执不可核对，停止最终资产写入", 409) from None
        return copy.deepcopy(self._job(state, job_id, context))

    def _authority(self, context):
        if not isinstance(context, dict) or any(not isinstance(context.get(key), str) or not context[key] for key in ("actor", "scope_key", "incarnation")):
            raise _error("STUDIO_AUDIO_AUTHORITY_REQUIRED", "须使用原项目与会话音频 owner", 403)
        if getattr(self.store, "owner_actor_id", None) != context["actor"]:
            raise _error("STUDIO_AUDIO_ACTOR_STORE_REQUIRED", "须使用原 AudioProductionStore 的 actor 分区", 403)

    def _matches(self, row, context):
        binding = row.get("context", {})
        return row.get("studio_origin") == STUDIO_ORIGIN and row.get("owner_actor_id") == context["actor"] and all(
            binding.get(key) == context.get(key) for key in ("actor", "scope_key", "incarnation"))

    def _job(self, state, job_id, context):
        self._authority(context)
        return self._validated_job(self.service.find(state, job_id), context)

    def _validated_job(self, row, context):
        """Validate an already located original-owner row without rescanning."""
        if not self._matches(row, context):
            raise _error("STUDIO_AUDIO_JOB_NOT_FOUND", "当前原项目 owner 中没有此音频任务", 404)
        # Only original owner storage reaches this decoder. Verify the raw
        # immutable bytes before permitting the historical marker-absent shape.
        # Queue/preview still use the strict fresh-command admission path.
        if row.get("request_sha256") != _digest({"body": row.get("_studio_body"), "context": row.get("context")}):
            raise _error("STUDIO_AUDIO_JOB_BINDING_CHANGED", "原音频任务绑定已变化，不能继续执行", 409)
        body = _body_shape(row.get("_studio_body")); binding = _binding(row.get("context"), body)
        provider = binding["provider_binding"] or {}
        if (row.get("chapter_id") is not None or row.get("experimental_origin") != "narrative_production_v2"
                or row.get("operation_id") != body["operation_id"] or row.get("provider_id") != provider.get("provider_id")
                or row.get("model_id") != provider.get("model_id") or row.get("source_text") != body["prompt"]
                or row.get("source_sha256") != hashlib.sha256(body["prompt"].encode()).hexdigest()
                or row.get("request_digest") != binding["request_digest"]
                or row.get("branch_id") != self.branch_id
                or row.get("request_sha256") != _digest({"body": body, "context": binding})):
            raise _error("STUDIO_AUDIO_JOB_BINDING_CHANGED", "原音频任务绑定已变化，不能继续执行", 409)
        _version(row.get("version"))
        if body["parameters"].get("output_format") == "MP3" and "audio_profile" not in body:
            historical_receipt = copy.deepcopy(row)
            self._receipt(historical_receipt)
            if row.get("receipt_digest") != historical_receipt["receipt_digest"]:
                raise _error("STUDIO_AUDIO_JOB_BINDING_CHANGED", "原音频持久回执已变化，不能继续执行", 409)
        controlled_output = (body["operation_id"] == "m8.audio.trim" and TRIM_CONTROLS.intersection(body["parameters"])
            and (row.get("publication_ready") is not None or row.get("publication_state") in {"RESERVED", "VERIFIED"}
                 or row.get("output_asset_id") is not None or row.get("status") in {"AWAITING_REVIEW", "REVIEWING", "APPROVED"}))
        if controlled_output and "measured" not in row:
            raise _error("STUDIO_AUDIO_MEASUREMENT_INVALID", "新增音频控制的实际输出证明缺失", 409)
        if "measured" in row:
            if body["operation_id"] != "m8.audio.trim" or "graph_binding" in binding:
                raise _error("STUDIO_AUDIO_MEASUREMENT_INVALID", "音频输出证明不属于此原操作", 409)
            measured = _trim_measurement(row["measured"], body["parameters"])
            ready = row.get("publication_ready")
            receipt = copy.deepcopy(row); self._receipt(receipt)
            if (not isinstance(ready, dict) or ready.get("output_digest") != measured["output_sha256"]
                    or ready.get("output_bytes") != measured["byte_count"] or ready.get("media_type") != ("audio/mpeg" if measured["container"] == "mp3" else "audio/" + measured["container"])
                    or row.get("duration_ms") != measured["duration_ms"] or row.get("media_validation") != measured["profile_validation"]
                    or row.get("output_digest") not in {None, measured["output_sha256"]}
                    or row.get("receipt_digest") != receipt["receipt_digest"]):
                raise _error("STUDIO_AUDIO_MEASUREMENT_INVALID", "原音频实际输出证明与持久回执不一致", 409)
        return row

    @staticmethod
    def view(row):
        """HTTP consumers must use this projection; internal bindings remain private."""
        fields = ("id", "novel_id", "branch_id", "version", "studio_origin", "operation_id", "status", "approval_status", "review_state", "attempt",
                  "request_digest", "receipt_digest", "request_sha256", "source_sha256", "provider_id", "model_id", "created_at", "updated_at", "started_at",
                  "completed_at", "error_code", "error", "dispatch_state", "receipt_state", "remote_task_id", "provider_status",
                  "output_asset_id", "candidate_asset_version", "output_asset_version", "output_digest", "duration_ms", "media_validation", "cancellation_mode", "reviewed_at")
        return {key: copy.deepcopy(row[key]) for key in fields if key in row}

    def list(self, nid, context, guard):
        self._authority(context); guard()
        state = self.store.load(nid, include_studio=True)
        rows, first_by_id = [], {}
        missing_id = False
        # load() already applies the original feature/visibility rules. Keep
        # the complete history and validate every matching row, including the
        # tail, without the former per-row find() scan of this same snapshot.
        for row in state["jobs"]:
            missing_id = missing_id or "id" not in row
            job_id = row.get("id")
            first = first_by_id.setdefault(job_id, row) if isinstance(job_id, str) else None
            if not self._matches(row, context):
                continue
            # Owner-generated IDs are strings. Preserve the old lookup/error
            # behavior for malformed legacy IDs rather than add ID migration
            # or validation rules as part of this listing optimization.
            if missing_id or not isinstance(job_id, str):
                first = self._job(state, row["id"], context)
            else:
                self._validated_job(first, context)
            # Retain the existing denial when a foreign row owns the first
            # occurrence. A second matching receipt must not be silently
            # shadowed by that first occurrence, even if its bytes are equal.
            if first is not row:
                raise _error("STUDIO_AUDIO_JOB_BINDING_CHANGED", "原音频任务绑定已变化，不能继续执行", 409)
            rows.append(copy.deepcopy(row))
        guard(); return rows

    def get(self, nid, job_id, context, guard):
        guard(); row = copy.deepcopy(self._job(self.store.load(nid, include_studio=True), job_id, context)); guard(); return row

    @staticmethod
    def _sources(binding, source_guard):
        if not callable(source_guard):
            raise _error("STUDIO_AUDIO_SOURCE_AUTHORITY_REQUIRED", "缺少原来源 owner 校验", 403)
        return [source_guard(copy.deepcopy(snapshot)) for snapshot in binding["sources"]]

    @staticmethod
    def _bump(row, **fields):
        row.update(fields, version=row["version"] + 1, updated_at=timestamp())
        StudioAudioExecution._receipt(row)
        return row

    @staticmethod
    def _receipt(row):
        # This hashes durable owner state, never invents a provider receipt.
        proof = {key: row.get(key) for key in (
            "id", "version", "request_digest", "status", "attempt", "dispatch_state", "publication_state",
            "review_state", "remote_task_id", "provider_status", "output_asset_id", "candidate_asset_version",
            "output_digest", "duration_ms", "media_validation", "cancellation_mode", "error_code")}
        # No new null key: unchanged legacy receipts retain their exact digest.
        if "measured" in row: proof["measured"] = row["measured"]
        row["receipt_digest"] = _digest(proof)

    @staticmethod
    def _expected(row, expected_version, context, expected_request_digest=None):
        _version(expected_version)
        wanted = expected_request_digest if expected_request_digest is not None else context.get("request_digest")
        _sha(wanted)
        if row["version"] != expected_version or row["request_digest"] != wanted:
            raise _error("STUDIO_AUDIO_VERSION_CONFLICT", "音频版本或原请求摘要已变化", 409)

    def queue(self, nid, body, context, guard, source_guard):
        if isinstance(body, dict) and "source_snapshots" not in body and isinstance(context, dict):
            body = {**body, "source_snapshots": copy.deepcopy(context.get("sources"))}
        body = _body(body); context = _binding(context, body); self._authority(context)
        guard(); self._sources(context, source_guard); guard()
        request_sha = _digest({"body": body, "context": context})
        def add(state):
            guard()
            existing = next((row for row in state["jobs"] if self._matches(row, context) and row.get("idempotency_key") == context["request_id"]), None)
            if existing:
                self._job(state, existing["id"], context)
                if existing["request_sha256"] != request_sha:
                    raise _error("STUDIO_AUDIO_IDEMPOTENCY_CONFLICT", "原请求标识已绑定另一音频意图", 409)
                return existing
            provider = context["provider_binding"] or {}; stamp = timestamp()
            row = {"id": "audio-" + str(uuid4()), "novel_id": nid, "branch_id": self.branch_id, "chapter_id": None, "version": 1, "studio_origin": STUDIO_ORIGIN,
                   "experimental_origin": "narrative_production_v2", "owner_actor_id": context["actor"], "operation_id": body["operation_id"],
                   "_studio_body": body, "context": context, "request_digest": context["request_digest"], "request_sha256": request_sha, "idempotency_key": context["request_id"],
                   "source_text": body["prompt"], "source_sha256": hashlib.sha256(body["prompt"].encode()).hexdigest(),
                   "provider_id": provider.get("provider_id"), "model_id": provider.get("model_id"), "status": "QUEUED", "attempt": 0,
                   "approval_status": "PENDING", "review_state": "NOT_READY", "dispatch_state": "NOT_SENT", "receipt_state": "NOT_SENT", "execution_token": None,
                   "publication_state": "NOT_STARTED",
                   "timing_status": "UNMEASURED", "estimated_duration_ms": None, "segments": [], "created_at": stamp, "updated_at": stamp,
                   "error": None, "error_code": None}
            self._receipt(row); state["jobs"].append(row); return row
        return self.store.mutate(nid, add)

    def _attempt(self, nid, claim, context, guard, source_guard=None):
        guard()
        if source_guard is not None: self._sources(claim["context"], source_guard)
        current = self._job(self.store.load(nid, include_studio=True), claim["id"], context)
        return current if (current.get("status") == "RUNNING" and current.get("execution_token") == claim["execution_token"]
                           and current["request_sha256"] == claim["request_sha256"]) else None

    def _failure(self, nid, claim, context, guard, error):
        def fail(state):
            guard(); current = self._job(state, claim["id"], context)
            if current.get("status") != "RUNNING" or current.get("execution_token") != claim["execution_token"]: return current
            unknown = (current.get("dispatch_state") != "NOT_SENT" or current.get("publication_state") != "NOT_STARTED"
                       or current.get("output_asset_id") is not None)
            return self._bump(current, status="UNKNOWN" if unknown else "FAILED", receipt_state="UNKNOWN_NO_AUTOMATIC_REPLAY" if unknown else "NOT_SENT",
                              error_code=error.code, error=str(error), execution_token=None)
        return self.store.mutate(nid, fail)

    def execute(self, nid, job_id, expected_version, context, guard, source_guard, resolve, publish, before_send=None, *, expected_request_digest=None, inspect_source=None):
        self._authority(context); guard()
        with self._lease(nid, job_id):
            return self._execute(nid, job_id, expected_version, context, guard, source_guard, resolve, publish, before_send,
                                 expected_request_digest=expected_request_digest, inspect_source=inspect_source)

    def _execute(self, nid, job_id, expected_version, context, guard, source_guard, resolve, publish, before_send=None, *, expected_request_digest=None, inspect_source=None):
        _version(expected_version); self._authority(context)
        if (not callable(guard) or not callable(source_guard) or not callable(publish)
                or (inspect_source is not None and not callable(inspect_source))):
            raise _error("STUDIO_AUDIO_EXECUTION_AUTHORITY_REQUIRED", "缺少原执行、来源或资产发布 owner", 403)
        guard()
        key = self._active_key(nid, job_id)
        def claim_job(state):
            guard(); row = self._job(state, job_id, context)
            self._expected(row, expected_version, context, expected_request_digest)
            if row["status"] != "QUEUED" or row["dispatch_state"] != "NOT_SENT":
                raise _error("STUDIO_AUDIO_NOT_EXECUTABLE", "只有尚未发送的排队音频可以显式执行", 409)
            return self._bump(row, status="RUNNING", attempt=row["attempt"] + 1, execution_token=str(uuid4()), started_at=timestamp(), error=None, error_code=None)
        with _ACTIVE_LOCK:
            if key in _ACTIVE: raise _error("STUDIO_AUDIO_EXECUTION_ACTIVE", "原音频执行仍在进行", 409)
            claim = self.store.mutate(nid, claim_job); _ACTIVE.add(key)
        try:
            binding, body = claim["context"], claim["_studio_body"]
            def inspection_current():
                # Poll only original Host/attempt authority. Passing source_guard
                # here would recursively probe the same media on every poll.
                if self._attempt(nid, claim, context, guard) is None:
                    raise _error("STUDIO_AUDIO_ATTEMPT_SUPERSEDED", "当前音频执行已取消或失效", 409)
            if inspect_source is not None:
                # This optional original resolver runs the attempt fence only
                # after releasing its asset lease; legacy callbacks stay valid.
                source_guard = lambda snapshot: inspect_source(snapshot, inspection_guard=inspection_current)
            if body["operation_id"] == "m8.audio.trim":
                content, measured = self._trim(nid, claim, context, guard, source_guard, inspection_current)
            else:
                if not callable(resolve) or not callable(before_send):
                    raise _error("STUDIO_AUDIO_DISPATCH_AUTHORITY_REQUIRED", "缺少原 Provider 解析、外发审核或费用授权", 403)
                wanted = binding["provider_binding"]
                provider_id, default_model, provider = resolve(wanted["provider_id"], wanted["capability"])
                if (provider_id != wanted["provider_id"] or default_model != wanted["model_id"]
                        or getattr(provider, "endpoint", None) != wanted["endpoint"] or getattr(provider, "local", None) is not wanted["local"]):
                    raise _error("STUDIO_AUDIO_PROVIDER_CHANGED", "原音频 Provider 配置已变化", 409)
                if getattr(provider, "supports_dispatch_guard", False) is not True:
                    raise _error("STUDIO_AUDIO_DISPATCH_GUARD_UNSUPPORTED", "此 Provider 尚不支持原 owner 最后一刻校验", 501)
                def dispatch_guard():
                    if self._attempt(nid, claim, context, guard, source_guard) is None:
                        raise _error("STUDIO_AUDIO_ATTEMPT_SUPERSEDED", "当前音频执行已取消或失效", 409)
                    before_send(copy.deepcopy(claim), provider_id, default_model, provider)
                    def reserve(state):
                        guard(); row = self._job(state, job_id, context)
                        if row["status"] != "RUNNING" or row.get("execution_token") != claim["execution_token"] or row["dispatch_state"] != "NOT_SENT":
                            raise _error("STUDIO_AUDIO_SEND_ALREADY_RESERVED", "音频发送已取消、失效或预留，不得重复发送", 409)
                        return self._bump(row, dispatch_state="SEND_RESERVED", receipt_state="UNKNOWN_NO_AUTOMATIC_REPLAY")
                    self.store.mutate(nid, reserve)
                params = ({"emotion": "neutral", "speed": body["parameters"]["speech_rate"], "response_format": "wav"}
                          if wanted["capability"] == "TTS" else {key: body["parameters"][key] for key in ("seed",) if key in body["parameters"]})
                request = AudioGenerationRequest(provider_id, default_model, wanted["capability"], body["prompt"],
                    claim["id"] + ":" + claim["execution_token"], voice=body["parameters"].get("voice_id"),
                    duration_seconds=body["parameters"].get("duration_seconds"), parameters=params, dispatch_guard=dispatch_guard)
                if self._attempt(nid, claim, context, guard, source_guard) is None: return self.get(nid, job_id, context, guard)
                result = provider.generate(request)
                if self._attempt(nid, claim, context, guard, source_guard) is None: return self.get(nid, job_id, context, guard)
                current = self.get(nid, job_id, context, guard)
                if current["dispatch_state"] != "SEND_RESERVED":
                    # A claimed guarded adapter that returned without its send
                    # callback is uncertain; never permit another dispatch.
                    def unguarded(state):
                        row = self._job(state, job_id, context); guard()
                        if row["status"] == "RUNNING" and row.get("execution_token") == claim["execution_token"]:
                            return self._bump(row, dispatch_state="UNGUARDED_PROVIDER_RECEIPT")
                        return row
                    self.store.mutate(nid, unguarded)
                    raise _error("STUDIO_AUDIO_PROVIDER_GUARD_NOT_OBSERVED", "原 Provider 未产生最后一刻发送校验回执，禁止重放", 502)
                if result.provider_id != provider_id or result.model_id != default_model:
                    raise _error("STUDIO_AUDIO_PROVIDER_RECEIPT_MISMATCH", "原音频结果与已发送 Provider 不一致", 502)
                def receipt(state):
                    guard(); row = self._job(state, job_id, context)
                    if row["status"] != "RUNNING" or row.get("execution_token") != claim["execution_token"]: return row
                    return self._bump(row, remote_task_id=result.remote_task_id, provider_status=result.status)
                self.store.mutate(nid, receipt)
                if result.status != "SUCCEEDED" or not result.audio_uri:
                    raise _error("STUDIO_AUDIO_ASYNC_RECEIPT_UNSUPPORTED", "原 Provider 未返回可核验完成音频；保留回执，不会重放", 502)
                # The route, recipe, cloud consent and source policy can change
                # while the provider is running. Recheck outside owner locks
                # before fetching or publishing the returned private result.
                before_send(copy.deepcopy(claim), provider_id, default_model, provider)
                content = self._provider_bytes(result.audio_uri, provider)
                measured = inspect_media(content, "audio", guard=inspection_current)
            output_digest = hashlib.sha256(content).hexdigest()
            output_proof = {}
            if body["operation_id"] == "m8.audio.trim" and "graph_binding" not in binding:
                proof = {"duration_ms": measured["duration_ms"],
                    "byte_count": len(content), "sample_rate": measured["sample_rate"], "channels": measured["channels"],
                    "sample_width": measured["sample_width"], "container": "wav", "audio_codec": "pcm_s16le",
                    "profile_validation": measured["validation"], "output_sha256": output_digest}
                if body["parameters"].get("output_format") == "FLAC":
                    proof.update(container="flac", audio_codec="flac", **{key: measured[key] for key in
                        ("total_samples", "decoded_pcm_bytes", "streaminfo_md5", "decoded_pcm_sha256")})
                if body["parameters"].get("output_format") == "MP3":
                    proof.update(container="mp3", audio_codec="mp3", **{key: measured[key] for key in
                        ("total_samples", "decoded_pcm_bytes", "decoded_pcm_sha256", "bit_rate", "container_duration_ms")})
                output_proof["measured"] = _trim_measurement(proof, body["parameters"])
            # Persist uncertainty before crossing from the audio owner to the
            # original source/asset owners. Never acquire those leases while
            # holding AudioProductionStore's mutation lock.
            self._sources(binding, source_guard); guard()
            if body["operation_id"] != "m8.audio.trim":
                before_send(copy.deepcopy(claim), provider_id, default_model, provider)
            def reserve_output(state):
                guard(); row = self._job(state, job_id, context)
                if row["status"] != "RUNNING" or row.get("execution_token") != claim["execution_token"]:
                    return row
                return self._bump(row, publication_state="RESERVED", receipt_state="UNKNOWN_NO_AUTOMATIC_REPLAY",
                    publication_ready={"kind": "audio", "output_digest": output_digest,
                        "output_bytes": len(content), "media_type": measured["media_type"]},
                    duration_ms=measured["duration_ms"], media_validation=measured["validation"], timing_status="MEASURED", **output_proof)
            reserved = self.store.mutate(nid, reserve_output)
            if reserved["status"] != "RUNNING" or reserved.get("execution_token") != claim["execution_token"]:
                return reserved
            def job_current():
                current = self._atomic_job(nid, job_id, context)
                if (current["version"] != reserved["version"] or current["status"] != "RUNNING"
                        or current.get("execution_token") != claim["execution_token"] or current.get("publication_state") != "RESERVED"):
                    raise _error("STUDIO_AUDIO_ATTEMPT_SUPERSEDED", "原音频结果发布已取消或失效", 409)
            candidate = publish(content, "audio", f"{job_id}.{measured['extension']}", measured, job_id, job_current)
            provider_binding = binding["provider_binding"] or {}
            expected_origin = {"contract": "studio-production-result/1", "job_id": job_id,
                               **{key: copy.deepcopy(binding[key]) for key in ("actor", "scope_key", "incarnation", "request_digest", "operation_id", "sources")},
                               "provider_id": provider_binding.get("provider_id"), "model_id": provider_binding.get("model_id"),
                               "license_note": binding.get("license_note", "")}
            if "graph_binding" in binding:
                from ..creative.graph_media_binding import validate_graph_binding
                graph_binding = validate_graph_binding(binding["graph_binding"], binding)
                if graph_binding is None:
                    raise ValueError("CREATIVE_GRAPH_MEDIA_BINDING_INVALID")
                expected_origin["graph_binding"] = copy.deepcopy(graph_binding)
            expected_project = {"novel_id": nid, "branch_id": self.branch_id,
                                "scope_key": binding["scope_key"], "incarnation": binding["incarnation"]}
            if (not isinstance(candidate, dict) or candidate.get("novel_id") != nid or candidate.get("kind") != "audio"
                    or candidate.get("sha256") != output_digest or candidate.get("branch_id") != self.branch_id
                    or candidate.get("_owner_actor_id") != binding["actor"] or candidate.get("source_job_id") != job_id
                    or candidate.get("_required_features") != ["narrative_production_v2"]
                    or candidate.get("_project_binding") != expected_project or candidate.get("_studio_result_origin") != expected_origin
                    or candidate.get("size") != len(content) or candidate.get("media_type") != measured["media_type"]):
                raise _error("STUDIO_AUDIO_CANDIDATE_OWNER_INVALID", "原资产 owner 未返回私有且来源一致的候选", 409)
            _name(candidate.get("id")); _version(candidate.get("version")); guard()
            def complete(state):
                guard(); row = self._job(state, job_id, context)
                if (row["version"] != reserved["version"] or row["status"] != "RUNNING"
                        or row.get("execution_token") != claim["execution_token"]): return row
                stamp = timestamp()
                self._bump(row, status="AWAITING_REVIEW", review_state="VERIFIED_PRIVATE_CANDIDATE", publication_state="VERIFIED",
                           output_asset_id=candidate["id"], candidate_asset_version=candidate["version"], output_asset_version=candidate["version"], output_digest=output_digest,
                           duration_ms=measured["duration_ms"], media_validation=measured["validation"], timing_status="MEASURED",
                           completed_at=stamp, receipt_state="VERIFIED_PRIVATE_CANDIDATE", execution_token=None)
                generation = {"job_id": job_id, "chapter_id": None, "studio_origin": STUDIO_ORIGIN, "experimental_origin": "narrative_production_v2",
                              "operation_id": body["operation_id"], "owner_actor_id": binding["actor"], "asset_id": candidate["id"],
                              "provider_id": row["provider_id"], "model_id": row["model_id"], "created_at": stamp,
                              "duration_ms": row["duration_ms"], "source_sha256": row["source_sha256"], "approval_status": "PENDING"}
                state["generations"] = [item for item in state["generations"] if item.get("job_id") != job_id] + [generation]
                return row
            return self.store.mutate(nid, complete)
        except Exception as exc:
            error = (exc if isinstance(exc, AudiobookError) else
                     _error(exc.code, str(exc), exc.status) if isinstance(exc, AudioStateVersionConflict) else
                     _error("STUDIO_AUDIO_EXECUTION_FAILED", "原音频执行或结果验证未完成；请核对回执", 502))
            return self._failure(nid, claim, context, guard, error)
        finally:
            with _ACTIVE_LOCK: _ACTIVE.discard(key)

    def _provider_bytes(self, uri, provider):
        if not isinstance(uri, str): raise MediaValidationError("invalid audio URI")
        if uri.startswith("data:audio/"):
            match = re.fullmatch(r"data:audio/[A-Za-z0-9.+-]+;base64,([A-Za-z0-9+/=]+)", uri)
            if not match or len(match[1]) > self.assets.MAX_BYTES * 4 // 3 + 8: raise MediaValidationError("invalid or oversized audio data URI")
            data = base64.b64decode(match[1], validate=True)
        else:
            data = fetch_media_bytes(uri, self.assets.MAX_BYTES, configured_provider_endpoint=provider.endpoint)
        if not 0 < len(data) <= self.assets.MAX_BYTES: raise MediaValidationError("audio exceeds asset limit")
        return data

    def _trim(self, nid, claim, context, guard, source_guard, inspection_current):
        binding, parameters = claim["context"], claim["_studio_body"]["parameters"]
        source = binding["sources"][0]; value = source_guard(copy.deepcopy(source)); guard()
        if not isinstance(value, dict) or value.get("snapshot") != source or not isinstance(value.get("data"), bytes) or not isinstance(value.get("row"), dict):
            raise _error("STUDIO_AUDIO_TRIM_SOURCE_INVALID", "原资产 owner 未返回完整音频来源", 409)
        row, data = value["row"], value["data"]
        if (row.get("id") != source["id"] or row.get("version") != source["version"] or row.get("sha256") != source["digest"]
                or row.get("novel_id") != nid or row.get("kind") != "audio" or row.get("branch_id") != self.branch_id
                or not 0 < len(data) <= self.assets.MAX_BYTES or hashlib.sha256(data).hexdigest() != source["digest"]):
            raise _error("STUDIO_AUDIO_TRIM_SOURCE_CHANGED", "原音频资产或字节已变化", 409)
        measured = inspect_media(data, "audio", guard=inspection_current)
        if parameters["out_ms"] > measured["duration_ms"]: raise _error("STUDIO_AUDIO_TRIM_RANGE_INVALID", "裁剪终点超过原音频时长", 400)
        executable = shutil.which("ffmpeg")
        if not executable: raise _error("STUDIO_AUDIO_TRIM_TOOL_UNAVAILABLE", "本地裁剪需要原配置 ffmpeg", 501)
        if self._attempt(nid, claim, context, guard, source_guard) is None: raise _error("STUDIO_AUDIO_ATTEMPT_SUPERSEDED", "音频裁剪已取消或失效", 409)
        duration = parameters["out_ms"] - parameters["in_ms"]
        flac, mp3 = parameters.get("output_format") == "FLAC", parameters.get("output_format") == "MP3"
        container = "flac" if flac else "mp3" if mp3 else "wav"
        from ..media_files import _media_inspection_directory
        temporary = _media_inspection_directory() if flac or mp3 else tempfile.TemporaryDirectory(prefix="studio-audio-trim-")
        with temporary as directory:
            source_path, target = Path(directory) / ("source." + measured["extension"]), Path(directory) / ("candidate." + container)
            if mp3:
                from .studio_audio_mp3_profile import encoder_available
                if not encoder_available(executable, directory, inspection_current):
                    raise _error("STUDIO_AUDIO_MP3_TOOL_UNAVAILABLE", "MP3 输出需要本地 libmp3lame 编码器及 ffprobe；不会替换编码器或格式", 501)
            source_path.write_bytes(data)
            if self._attempt(nid, claim, context, guard, source_guard) is None: raise _error("STUDIO_AUDIO_ATTEMPT_SUPERSEDED", "音频裁剪已取消或失效", 409)
            from .studio_timeline_export import run_guarded_process
            filters = _trim_filters(parameters)
            codec = ["-c:a", "flac", "-sample_fmt", "s16", "-compression_level", "5"] if flac else ["-c:a", "pcm_s16le"]
            if mp3:
                from .studio_audio_mp3_profile import bit_rate
                codec = ["-c:a", "libmp3lame", "-sample_fmt", "s16p", "-b:a", str(bit_rate(parameters.get("sample_rate", 48000))),
                         "-abr", "0", "-write_xing", "1", "-id3v2_version", "3", "-map_metadata", "-1"]
            run_guarded_process([executable, "-nostdin", "-v", "error", "-xerror", "-threads", "1", "-protocol_whitelist", "file,pipe",
                "-ss", f"{parameters['in_ms'] / 1000:.3f}", "-i", str(source_path), "-map", "0:a:0", "-vn", "-sn", "-dn",
                "-t", f"{duration / 1000:.3f}", *filters, "-ar", str(parameters.get("sample_rate", 48000)),
                "-ac", str(parameters.get("channels", 2)), *codec, "-fs", str(self.assets.MAX_BYTES + 1),
                "-f", container, str(target)], cwd=directory, guard=inspection_current, timeout=50)
            inspection_current()
            if not target.is_file() or not 0 < target.stat().st_size <= self.assets.MAX_BYTES:
                raise MediaValidationError("trim output exceeds asset limit")
            with target.open("rb") as stream: output = stream.read(self.assets.MAX_BYTES + 1)
            if mp3:
                from .studio_audio_mp3_profile import prove_mp3
                result = prove_mp3(target, output, parameters, guard=inspection_current, max_bytes=self.assets.MAX_BYTES)
                inspection_current()
                return output, result
            if flac:
                from .studio_audio_trim_profiles import prove_flac
                result = prove_flac(target, output, parameters, guard=inspection_current, max_bytes=self.assets.MAX_BYTES)
                inspection_current()
                return output, result
        if not 0 < len(output) <= self.assets.MAX_BYTES: raise MediaValidationError("trim output exceeds asset limit")
        result = inspect_media(output, "audio", guard=inspection_current)
        if abs(result["duration_ms"] - duration) > 2: raise MediaValidationError("trim output duration does not match the reviewed interval")
        if (result.get("media_type") != "audio/wav" or result.get("validation") != "PCM_DECODED"
                or result.get("sample_rate") != parameters.get("sample_rate", 48000)
                or result.get("channels") != parameters.get("channels", 2) or result.get("sample_width") != 2):
            raise MediaValidationError("trim output does not match the reviewed PCM WAV profile")
        return output, result

    def cancel(self, nid, job_id, expected_version, context, guard, *, expected_request_digest=None):
        _version(expected_version); guard()
        def change(state):
            guard(); row = self._job(state, job_id, context)
            self._expected(row, expected_version, context, expected_request_digest)
            if row["status"] not in {"QUEUED", "RUNNING", "UNKNOWN", "AWAITING_REVIEW"}:
                raise _error("STUDIO_AUDIO_NOT_CANCELLABLE", "此音频任务不能取消", 409)
            return self._bump(row, status="CANCELLED", execution_token=None, cancellation_mode="LOCAL_RESULT_DISCARD",
                              review_state="DISCARDED_PRIVATE_CANDIDATE" if row.get("output_asset_id") else row["review_state"],
                              receipt_state=(row["receipt_state"] if row.get("output_asset_id") else
                                  "UNKNOWN_NO_AUTOMATIC_REPLAY" if row["dispatch_state"] != "NOT_SENT" or row["publication_state"] != "NOT_STARTED" else "NOT_SENT"))
        return self.store.mutate(nid, change)

    def reconcile(self, nid, job_id, expected_version, context, guard, *, expected_request_digest=None, recover_candidate=None, recover_review=None):
        """Explicit orphan receipt recovery; never polls, dispatches or requeues."""
        self._authority(context); guard()
        with self._lease(nid, job_id):
            return self._reconcile(nid, job_id, expected_version, context, guard,
                expected_request_digest=expected_request_digest, recover_candidate=recover_candidate, recover_review=recover_review)

    def _reconcile(self, nid, job_id, expected_version, context, guard, *, expected_request_digest=None, recover_candidate=None, recover_review=None):
        _version(expected_version); guard()
        captured = self.get(nid, job_id, context, guard)
        self._expected(captured, expected_version, context, expected_request_digest)
        with _ACTIVE_LOCK:
            active = self._active_key(nid, job_id) in _ACTIVE
        if captured["status"] == "REVIEWING" and not active:
            result = self._reconcile_review(nid, job_id, context, captured, recover_review)
            guard()
            return result
        if captured["status"] not in {"RUNNING", "UNKNOWN"} or active:
            return captured
        ready, candidate = captured.get("publication_ready"), None
        if callable(recover_candidate) and isinstance(ready, dict):
            try:
                _sha(ready.get("output_digest"))
                if (set(ready) != {"kind", "output_digest", "output_bytes", "media_type"} or ready["kind"] != "audio"
                        or type(ready["output_bytes"]) is not int or not 0 < ready["output_bytes"] <= self.assets.MAX_BYTES
                        or not isinstance(ready["media_type"], str)
                        or type(captured.get("duration_ms")) is not int or captured["duration_ms"] < 1
                        or not isinstance(captured.get("media_validation"), str)):
                    raise _error("STUDIO_AUDIO_PUBLICATION_READY_INVALID", "原音频结果持久证明无效", 409)
                asset = recover_candidate(copy.deepcopy(captured))
                if asset is not None:
                    candidate = self._recovered_candidate(nid, captured, asset, ready)
                guard()
            except Exception:
                guard()
                candidate = None
        def change(state):
            guard(); row = self._job(state, job_id, context)
            self._expected(row, expected_version, context, expected_request_digest)
            if (row["status"] != captured["status"] or row.get("execution_token") != captured.get("execution_token")
                    or row.get("publication_ready") != ready or row["context"] != captured["context"]):
                raise _error("STUDIO_AUDIO_RECONCILE_CHANGED", "原音频恢复回执已变化", 409)
            if candidate is not None:
                stamp = timestamp()
                self._bump(row, status="AWAITING_REVIEW", review_state="VERIFIED_PRIVATE_CANDIDATE", publication_state="VERIFIED",
                    output_asset_id=candidate["id"], candidate_asset_version=candidate["version"], output_asset_version=candidate["version"],
                    output_digest=ready["output_digest"], completed_at=stamp, receipt_state="VERIFIED_PRIVATE_CANDIDATE",
                    execution_token=None, error=None, error_code=None)
                generation = {"job_id": job_id, "chapter_id": None, "studio_origin": STUDIO_ORIGIN,
                    "experimental_origin": "narrative_production_v2", "operation_id": row["operation_id"],
                    "owner_actor_id": row["context"]["actor"], "asset_id": candidate["id"], "provider_id": row["provider_id"],
                    "model_id": row["model_id"], "created_at": stamp, "duration_ms": row["duration_ms"],
                    "source_sha256": row["source_sha256"], "approval_status": "PENDING"}
                state["generations"] = [item for item in state["generations"] if item.get("job_id") != job_id] + [generation]
                return row
            return self._bump(row, status="UNKNOWN", execution_token=None, receipt_state="UNKNOWN_NO_AUTOMATIC_REPLAY",
                error_code="STUDIO_AUDIO_ORPHANED_ATTEMPT", error="原音频执行回执中断；不会自动重放")
        return self.store.mutate(nid, change)

    def _reconcile_review(self, nid, job_id, context, captured, recover_review):
        """Release only an exact stopped review with original private proof.

        Entry authority and the original per-job lease are held by reconcile.
        This internal bookkeeping deliberately needs no current source grant
        and neither dispatches nor promotes an output.
        """
        if not callable(recover_review):
            return captured
        recovered = None
        try:
            _name(captured.get("output_asset_id")); _version(captured.get("candidate_asset_version"))
            _sha(captured.get("output_digest")); _sha(captured.get("receipt_digest"))
            if captured.get("review_token") is not None: _name(captured["review_token"])
            receipt = copy.deepcopy(captured)
            self._receipt(receipt)
            if (captured["receipt_digest"] != receipt["receipt_digest"] or captured.get("approval_status") != "PENDING"
                    or captured.get("output_asset_version") != captured["candidate_asset_version"]
                    or captured["version"] >= 2**53 - 1):
                raise _error("STUDIO_AUDIO_RECONCILE_REVIEW_CHANGED", "原音频审核恢复回执不可核对", 409)
            candidate = {"id": captured["output_asset_id"], "version": captured["candidate_asset_version"],
                "digest": captured["output_digest"], "kind": "audio"}
            def compensate():
                nonlocal recovered
                def change(state):
                    row = self._job(state, job_id, context)
                    self._expected(row, captured["version"], context, captured["request_digest"])
                    fields = ("context", "review_token", "execution_token", "receipt_digest", "approval_status",
                        "output_asset_id", "candidate_asset_version", "output_asset_version", "output_digest")
                    current_receipt = copy.deepcopy(row)
                    self._receipt(current_receipt)
                    if (row["status"] != "REVIEWING" or any(row.get(key) != captured.get(key) for key in fields)
                            or row["receipt_digest"] != current_receipt["receipt_digest"]):
                        raise _error("STUDIO_AUDIO_RECONCILE_REVIEW_CHANGED", "原音频审核恢复回执已变化", 409)
                    return self._bump(row, status="AWAITING_REVIEW", review_token=None, review_from_version=None,
                        review_state="VERIFIED_PRIVATE_CANDIDATE", error_code="STUDIO_AUDIO_REVIEW_RECOVERED_NOT_PROMOTED",
                        error="原候选仍为私有，已显式恢复审核或取消入口", recovery_state="EXACT_PRIVATE_REVIEW_RELEASED_NO_REPLAY",
                        review_reconciled_at=timestamp())
                recovered = self.store.mutate(nid, change)
                return recovered
            # Preserve the unchanged V1 queue -> asset order. Private proof and
            # this reentrant exact CAS both run before the asset lease ends.
            with self.store._lock:
                recover_review(candidate, compensate)
        except Exception:
            # A promoted/missing/changed candidate grants no recovery. Keep the
            # captured REVIEWING receipt unless the exact CAS already succeeded.
            pass
        return recovered if recovered is not None else captured

    def _recovered_candidate(self, nid, captured, asset, ready):
        binding = captured["context"]
        provider = binding["provider_binding"] or {}
        origin = {"contract": "studio-production-result/1", "job_id": captured["id"],
            **{key: copy.deepcopy(binding[key]) for key in ("actor", "scope_key", "incarnation", "request_digest", "operation_id", "sources")},
            "provider_id": provider.get("provider_id"), "model_id": provider.get("model_id"), "license_note": binding.get("license_note", "")}
        if "graph_binding" in binding:
            origin["graph_binding"] = copy.deepcopy(binding["graph_binding"])
        if (not isinstance(asset, dict) or asset.get("kind") != "audio" or asset.get("novel_id") != nid
                or asset.get("branch_id") != self.branch_id or asset.get("deleted_at") or asset.get("_owner_actor_id") != binding["actor"]
                or asset.get("source_job_id") != captured["id"] or asset.get("_required_features") != ["narrative_production_v2"]
                or asset.get("sha256") != ready["output_digest"] or asset.get("size") != ready["output_bytes"]
                or asset.get("media_type") != ready["media_type"] or asset.get("_studio_result_origin") != origin
                or asset.get("_project_binding") != {"novel_id": nid, "branch_id": self.branch_id,
                    "scope_key": binding["scope_key"], "incarnation": binding["incarnation"]}):
            raise _error("STUDIO_AUDIO_RECOVERY_CANDIDATE_INVALID", "原音频私有候选不能核对", 409)
        _name(asset.get("id")); _version(asset.get("version"))
        return copy.deepcopy(asset)

    def review(self, nid, job_id, expected_version, context, guard, source_guard, reviewed_output_digest, promote, *, expected_request_digest=None, recover_review=None):
        self._authority(context); guard()
        with self._lease(nid, job_id):
            return self._review(nid, job_id, expected_version, context, guard, source_guard, reviewed_output_digest, promote,
                                expected_request_digest=expected_request_digest, recover_review=recover_review)

    def _review(self, nid, job_id, expected_version, context, guard, source_guard, reviewed_output_digest, promote, *, expected_request_digest=None, recover_review=None):
        _version(expected_version); _sha(reviewed_output_digest)
        if not callable(promote): raise _error("STUDIO_AUDIO_REVIEW_OWNER_REQUIRED", "须使用原资产 promote_owned 审核入口", 403)
        guard()
        original = self.get(nid, job_id, context, guard)
        self._expected(original, expected_version, context, expected_request_digest)
        self._sources(original["context"], source_guard); guard()
        def claim_review(state):
            guard(); row = self._job(state, job_id, context)
            self._expected(row, expected_version, context, expected_request_digest)
            if row["status"] == "APPROVED" and row.get("output_digest") == reviewed_output_digest:
                return row
            if row["status"] not in {"AWAITING_REVIEW", "REVIEWING"} or row["approval_status"] != "PENDING" or not row.get("output_asset_id") or row.get("output_digest") != reviewed_output_digest:
                raise _error("STUDIO_AUDIO_REVIEW_NOT_READY", "须明确核对当前已验证私有音频及摘要", 409)
            return self._bump(row, status="REVIEWING", review_state="REVIEWING", review_token=str(uuid4()), error=None, error_code=None)
        claim = self.store.mutate(nid, claim_review)
        if claim["status"] == "APPROVED": return claim
        binding = claim["context"]
        # Stable provenance permits the original promote_owned owner to return
        # the same reviewed asset after promotion succeeds but job save fails.
        provenance = {"contract": "studio-production-review/1", "studio_origin": STUDIO_ORIGIN, "source_job_id": job_id,
                      "request_digest": binding["request_digest"], "actor": binding["actor"], "scope_key": binding["scope_key"],
                      "incarnation": binding["incarnation"], "source_snapshots": copy.deepcopy(binding["sources"]),
                      "output_digest": reviewed_output_digest, "candidate_version": claim["candidate_asset_version"],
                      "provider_binding": copy.deepcopy(binding["provider_binding"]), "rights": copy.deepcopy(binding["rights"])}
        def job_current():
            current = self._atomic_job(nid, job_id, context)
            if (current["version"] != claim["version"] or current["status"] != "REVIEWING" or current.get("review_token") != claim["review_token"]
                    or current.get("output_digest") != reviewed_output_digest):
                raise _error("STUDIO_AUDIO_REVIEW_CHANGED", "原音频审核已被其他操作取代", 409)
        try:
            asset = promote(claim["output_asset_id"], claim["candidate_asset_version"], provenance, job_current)
            if not isinstance(asset, dict) or asset.get("id") != claim["output_asset_id"] or asset.get("sha256") != reviewed_output_digest:
                raise _error("STUDIO_AUDIO_REVIEW_RECEIPT_INVALID", "原资产审核回执不一致", 409)
            _version(asset.get("version")); guard()
            def approve(state):
                guard(); row = self._job(state, job_id, context)
                if (row["version"] != claim["version"] or row["status"] != "REVIEWING" or row.get("review_token") != claim["review_token"]):
                    raise _error("STUDIO_AUDIO_REVIEW_CHANGED", "原音频审核已被其他操作取代", 409)
                self._bump(row, status="APPROVED", approval_status="APPROVED", review_state="ORIGINAL_OWNER_REVIEWED",
                           output_asset_version=asset["version"], review_token=None, reviewed_at=timestamp())
                for generation in state["generations"]:
                    if generation.get("job_id") == job_id: generation["approval_status"] = "APPROVED"
                return row
            return self.store.mutate(nid, approve)
        except Exception:
            restored = False
            if callable(recover_review):
                def compensate():
                    nonlocal restored
                    def change(state):
                        row = self._job(state, job_id, context)
                        self._expected(row, claim["version"], context, claim["request_digest"])
                        if (row["status"] != "REVIEWING" or row.get("review_token") != claim["review_token"]
                                or row["context"] != claim["context"] or row.get("receipt_digest") != claim.get("receipt_digest")
                                or row.get("output_asset_id") != claim["output_asset_id"]
                                or row.get("candidate_asset_version") != claim["candidate_asset_version"]
                                or row.get("output_digest") != reviewed_output_digest):
                            raise _error("STUDIO_AUDIO_REVIEW_CHANGED", "原音频审核已被其他操作取代", 409)
                        return self._bump(row, status="AWAITING_REVIEW", review_token=None, review_state="VERIFIED_PRIVATE_CANDIDATE",
                            error_code="STUDIO_AUDIO_REVIEW_NOT_PROMOTED", error="原审核未提升候选；可重新核对或取消")
                    result = self.store.mutate(nid, change)
                    restored = True
                    return result
                try:
                    # Acquire the original audio queue mutex first, preserving
                    # V1's queue -> asset order. The private-proof callback then
                    # invokes the reentrant exact CAS while holding its leases.
                    with self.store._lock:
                        recover_review({"id": claim["output_asset_id"], "version": claim["candidate_asset_version"],
                            "digest": reviewed_output_digest, "kind": "audio"}, compensate)
                except Exception:
                    pass
            if not restored:
                try:
                    def uncertain(state):
                        row = self._job(state, job_id, context)
                        if (row["version"] == claim["version"] and row["status"] == "REVIEWING"
                                and row.get("review_token") == claim["review_token"] and row["context"] == claim["context"]):
                            return self._bump(row, review_token=None, review_state="REVIEW_UNCERTAIN_EXPLICIT_RECOVERY",
                                error_code="STUDIO_AUDIO_REVIEW_INCOMPLETE", error="原审核或回写未完成；保留最初候选版本，可显式核对后恢复审核")
                        return row
                    self.store.mutate(nid, uncertain)
                except Exception:
                    # Never replace the first failure with a bookkeeping error.
                    pass
            raise
