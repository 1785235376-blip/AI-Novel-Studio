"""Durable user-triggered audiobook execution with attempt fencing.

All generated media is verified before it is marked successful. Generation does
not imply approval, and no unsupported emotion tags are inserted into speech.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone, timedelta
import hashlib
import json
import re
from uuid import uuid4

from ..audio_production_store import AudioProductionStore
from ..audio_providers import AudioGenerationRequest
from ..media_files import fetch_media_bytes, inspect_media, concatenate_wav, MediaValidationError
from ..privacy import merge_privacy
from ..source_privacy import effective_source_privacy,content_digest


def timestamp():
    return datetime.now(timezone.utc).isoformat()


class AudiobookError(ValueError):
    def __init__(self, code, message, status=409):
        super().__init__(message)
        self.code, self.status = code, status


class AudiobookService:
    def __init__(self, store: AudioProductionStore, assets, branch_id=None):
        self.store, self.assets, self.branch_id = store, assets, branch_id

    @staticmethod
    def find(state, job_id):
        for job in state["jobs"]:
            if job["id"] == job_id:
                return job
        raise AudiobookError("AUDIOBOOK_JOB_NOT_FOUND", "有声章节任务不存在", 404)

    def queue(self, novel_id, chapter, config, segments, idempotency_key=None, source_chapter=None):
        source_chapter=source_chapter or chapter
        text = re.sub(r"\A\s*#{1,6}\s+[^\r\n]*(?:\r?\n)+", "", str(chapter.get("content", ""))).strip()
        if not text:
            raise AudiobookError("AUDIOBOOK_TEXT_EMPTY", "章节没有可朗读正文", 400)
        def add(state):
            actual = dict(config)
            binding = next((item for item in state["voice_bindings"] if actual.get("character_id") and item.get("character_id") == actual["character_id"]), None)
            if binding: actual.update(binding)
            request_sha=hashlib.sha256(json.dumps({'text':text,'version':chapter.get('version'),'config':actual,'dictionary':state['pronunciation_dictionary']},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            existing=next((row for row in state['jobs'] if idempotency_key and row.get('idempotency_key')==idempotency_key),None)
            if existing:
                if existing.get('request_sha256')!=request_sha:raise AudiobookError('AUDIOBOOK_IDEMPOTENCY_CONFLICT','幂等键已用于另一项章节请求')
                return existing
            stamp = timestamp()
            job = {"id": "audio-" + str(uuid4()), "chapter_id": chapter["id"], "owner_actor_id": getattr(self.store,"owner_actor_id",None), **actual,
                   "status": "QUEUED", "attempt": 0, "text_length": len(text), "idempotency_key":idempotency_key, "request_sha256":request_sha,
                   "source_text": text, "source_version": source_chapter.get("version"),
                   "source_content_sha256":content_digest(source_chapter),
                   "source_sha256": hashlib.sha256(text.encode()).hexdigest(),
                   "privacy_level": effective_source_privacy(source_chapter,self.branch_id),
                   "pronunciation_dictionary": list(state["pronunciation_dictionary"]),
                   "segments": segments, "timing_status": "ESTIMATED",
                   "estimated_duration_ms": segments[-1]["end_ms"] if segments else 0,
                   "created_at": stamp, "updated_at": stamp, "error": None, "error_code": None,
                   "approval_status": "PENDING", "voice_authorization": actual.get("license_note") or "PROVIDER_LICENSE_REVIEW_REQUIRED"}
            state["jobs"].append(job)
            return job
        return self.store.mutate(novel_id, add)

    def transition(self, novel_id, job_id, target):
        def change(state):
            job = self.find(state, job_id)
            allowed = {"QUEUED": {"FAILED", "CANCELLED"}, "CANCELLED": {"QUEUED", "RUNNING"}}
            if job["status"] not in allowed[target]:
                code = "AUDIOBOOK_JOB_NOT_RETRYABLE" if target == "QUEUED" else "AUDIOBOOK_JOB_NOT_CANCELLABLE"
                raise AudiobookError(code, "当前任务不能执行该操作")
            job.update(status=target, updated_at=timestamp(), error=None, error_code=None, execution_token=None)
            if target=="CANCELLED":job["cancellation_mode"]="LOCAL_RESULT_DISCARD"
            return job
        return self.store.mutate(novel_id, change)

    def recover(self, novel_id, stale_after_seconds):
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=stale_after_seconds)
        def change(state):
            recovered = []
            for job in state["jobs"]:
                if job.get("status") != "RUNNING": continue
                try: updated = datetime.fromisoformat(job["updated_at"].replace("Z", "+00:00"))
                except (ValueError, KeyError): continue
                if updated.tzinfo is None: continue
                if updated <= cutoff:
                    job.update(status="QUEUED", execution_token=None, updated_at=timestamp(), recovery_count=int(job.get("recovery_count", 0)) + 1)
                    recovered.append(job["id"])
            return recovered
        return self.store.mutate(novel_id, change)

    def execute(self, novel_id, job_id, chapter, resolve, load_current_source=None):
        def claim(state):
            job = self.find(state, job_id)
            if job["status"] != "QUEUED":
                raise AudiobookError("AUDIOBOOK_JOB_NOT_EXECUTABLE", "只有排队中的任务可以执行")
            # Legacy jobs have no immutable text snapshot. Require explicit requeue.
            if not job.get("source_text"):
                raise AudiobookError("AUDIOBOOK_SNAPSHOT_MISSING", "旧任务缺少正文快照，请重新创建任务")
            job.update(status="RUNNING", attempt=int(job.get("attempt", 0)) + 1, execution_token=str(uuid4()), started_at=timestamp(), updated_at=timestamp())
            return job
        job = self.store.mutate(novel_id, claim)
        try:
            try: provider_id, default_model, provider = resolve(job.get("provider_id") or "auto")
            except ValueError as exc: raise AudiobookError("SPEECH_PROVIDER_UNAVAILABLE", "语音 Provider 未配置", 503) from exc
            if load_current_source is not None: chapter=load_current_source()
            if not getattr(provider, "local", False):
                if job.get('source_version')!=chapter.get('version') or job.get('source_content_sha256')!=content_digest(chapter):
                    raise AudiobookError('AUDIOBOOK_SOURCE_CHANGED','正文版本已改变，请重新审核隐私并创建任务',409)
                if merge_privacy(job.get("privacy_level"),effective_source_privacy(chapter,self.branch_id)) != "CLOUD_ALLOWED":
                    raise AudiobookError("AUDIOBOOK_PRIVACY_BLOCKED", "章节隐私策略不允许向远端语音服务发送正文", 403)
            text = job["source_text"]
            for entry in job.get("pronunciation_dictionary", []):
                if entry.get("term"): text = text.replace(str(entry["term"]), str(entry.get("pronunciation", "")))
            model_id = str(job.get("model_id") or default_model)
            result = provider.generate(AudioGenerationRequest(provider_id, model_id, "TTS", text, job_id + ":" + str(job["attempt"]), voice=str(job.get("voice") or "alloy"), parameters={"emotion": job.get("emotion") or "neutral", "speed": float(job.get("speech_rate") or 1.0), "response_format": "wav"}))
            if result.status != "SUCCEEDED" or not result.audio_uri:
                raise AudiobookError("AUDIOBOOK_ASYNC_UNSUPPORTED", "该语音服务未返回完成的音频；异步任务仍需 Provider 轮询适配", 502)
            if result.audio_uri.startswith("data:audio/"):
                match = re.fullmatch(r"data:audio/[A-Za-z0-9.+-]+;base64,([A-Za-z0-9+/=]+)", result.audio_uri)
                if not match: raise MediaValidationError("invalid audio data URI")
                if len(match[1]) > self.assets.MAX_BYTES * 4 // 3 + 8: raise MediaValidationError("audio exceeds asset limit")
                content = base64.b64decode(match[1], validate=True)
            else:
                content = fetch_media_bytes(result.audio_uri, self.assets.MAX_BYTES, configured_provider_endpoint=getattr(provider, "endpoint", None))
            measured = inspect_media(content, "audio")
            def complete(state):
                current = self.find(state, job_id)
                if current.get("execution_token") != job["execution_token"] or current["status"] != "RUNNING":
                    return current
                asset = self.assets.create(novel_id, f"{job_id}.{measured['extension']}", base64.b64encode(content).decode(), measured["media_type"], "audio", f"audiobook:{job_id}:{job['source_sha256']}", branch_id=self.branch_id)
                asset = self.assets.update_metadata(asset['id'], {'source_job_id':job_id,'provider_id':provider_id,'model_id':model_id,'character_id':job.get('character_id')}, branch_id=self.branch_id)
                stamp = timestamp()
                uri = f"/api/assets/{asset['id']}/download?novel_id={novel_id}"
                current.update(status="SUCCEEDED", audio_uri=uri, asset_id=asset["id"], provider_id=provider_id, model_id=model_id, completed_at=stamp, updated_at=stamp, duration_ms=measured["duration_ms"], media_validation=measured["validation"], error=None, error_code=None)
                speech = {"job_id": job_id, "chapter_id": job["chapter_id"], "character_id": job.get("character_id"), "provider_id": provider_id, "model_id": model_id, "voice": job.get("voice"), "audio_uri": uri, "asset_id": asset["id"], "created_at": stamp, "duration_ms": measured["duration_ms"], "source_sha256": job["source_sha256"], "source_version": job.get("source_version"), "group_id":job.get("group_id"), "segment_index":job.get("segment_index",0), "segment_count":job.get("segment_count",1)}
                state["generations"] = [row for row in state["generations"] if row.get("job_id") != job_id] + [speech]
                return current
            return self.store.mutate(novel_id, complete)
        except Exception as exc:
            if isinstance(exc, AudiobookError): error = exc
            elif isinstance(exc, ValueError) and "AUDIO_PARAMETER_UNSUPPORTED" in str(exc): error = AudiobookError("AUDIO_PARAMETER_UNSUPPORTED", "该 Provider 不支持所选情绪参数", 400)
            else: error = AudiobookError("SPEECH_SYNTHESIS_FAILED", "语音合成或音频验证失败", 502)
            def fail(state):
                current = self.find(state, job_id)
                if current.get("execution_token") != job["execution_token"] or current["status"] != "RUNNING": return current
                current.update(status="FAILED", error=str(error), error_code=error.code, updated_at=timestamp())
                return current
            current = self.store.mutate(novel_id, fail)
            if current.get("execution_token") != job["execution_token"] or current["status"] != "FAILED": return current
            raise error from exc

    def export_chapter(self, novel_id, chapter_id, job_ids):
        if not job_ids or len(job_ids) != len(set(job_ids)):
            raise AudiobookError("AUDIOBOOK_EXPORT_SELECTION_INVALID", "请选择互不重复的音频任务", 400)
        state = self.store.load(novel_id)
        jobs = [self.find(state, job_id) for job_id in job_ids]
        if any(job.get("chapter_id") != chapter_id or job.get("status") != "SUCCEEDED" or not job.get("asset_id") for job in jobs):
            raise AudiobookError("AUDIOBOOK_EXPORT_NOT_READY", "只能导出本章节已验证的完成音频")
        parts = [self.assets.content(job["asset_id"], branch_id=self.branch_id) for job in jobs]
        if len(parts) == 1:
            output, offsets = parts[0], [{"sequence": 1, "start_ms": 0, "duration_ms": jobs[0]["duration_ms"]}]
            measured = inspect_media(output, "audio")
        else:
            pauses={int(job.get('pause_ms') or 0) for job in jobs}
            if len(pauses)!=1:raise AudiobookError('AUDIOBOOK_TIMING_MISMATCH','请选择使用相同分段停顿配置的音频任务')
            output, offsets = concatenate_wav(parts,pause_ms=pauses.pop())
            measured = inspect_media(output, "audio")
        return output, {"chapter_id": chapter_id, "media_type": measured["media_type"], "extension": measured["extension"], "duration_ms": measured["duration_ms"], "sha256": hashlib.sha256(output).hexdigest(), "segments": [{**offset, "job_id": job["id"], "asset_id": job["asset_id"], "source_sha256": job["source_sha256"], "voice_authorization": job.get("voice_authorization")} for offset, job in zip(offsets, jobs)]}
