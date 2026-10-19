"""Playback cache admission over the original timeline export/job/Asset owners.

The durable cache is the original, immutable private render candidate. No second
queue, media directory or asset owner is introduced. A stable server-built
request identifies that exact candidate; UNKNOWN/failed jobs never render again.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

from ..experimental.common import StaleSourceError
from ..media_files import MediaValidationError
from .production_execution_models import TimelinePlaybackPreview, TimelinePlaybackBuild, TimelinePlaybackAttestation


def _digest(value):
    from .production_execution import digest
    return digest(value)


def _engines():
    """File proofs only; never run a native tool in a playback preview."""
    rows = []
    for name in ("ffmpeg", "ffprobe"):
        resolved = shutil.which(name)
        if not resolved:
            raise MediaValidationError("MEDIA_VALIDATOR_NOT_CONFIGURED")
        path = Path(resolved).resolve(strict=True)
        before = path.stat()
        if not path.is_file() or not 1 <= before.st_size <= 512 * 1024 * 1024:
            raise ValueError("STUDIO_PLAYBACK_ENGINE_INVALID")
        checksum = hashlib.sha256()
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                checksum.update(block)
        after = path.stat()
        identity = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
        if identity != (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns):
            raise StaleSourceError("STUDIO_PLAYBACK_ENGINE_CHANGED")
        rows.append({"name": name, "path": str(path), "identity": identity, "sha256": checksum.hexdigest()})
    return rows


def _engine_current(rows):
    for row in rows:
        resolved = shutil.which(row["name"])
        if not resolved or str(Path(resolved).resolve(strict=True)) != row["path"]:
            raise StaleSourceError("STUDIO_PLAYBACK_ENGINE_CHANGED")
        stat = Path(row["path"]).stat()
        if (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns) != row["identity"]:
            raise StaleSourceError("STUDIO_PLAYBACK_ENGINE_CHANGED")


class TimelinePlayback:
    def __init__(self, service):
        self.service = service

    def _prepare(self, nid, scope, actor, tid, value, guard):
        body = TimelinePlaybackPreview.model_validate(value)
        service = self.service
        context = service._base(nid, scope, actor, guard)
        row = service.timeline_get(nid, scope, actor, tid, guard)
        if (row["version"], row["timeline_digest"]) != (body.expected_version, body.reviewed_timeline_digest):
            raise StaleSourceError("STUDIO_TIMELINE_CHANGED")
        # H.264/AAC is the explicit browser-playback profile. Capacity is planned
        # beforehand; only an explicit proxy profile may scale the final picture.
        # The original authored timeline and ordinary delivery profiles stay intact.
        seconds = row["timeline"]["duration_ms"] / 1000
        budget = service.workspace.assets.MAX_BYTES
        video = min(1500, max(100, int((budget - 128000) * 8 / (seconds * 1.10) / 1000) - 97))
        profile = {"preset": "DELIVERY_H264_MP4", "video_bitrate_kbps": video, "audio_bitrate_kbps": 96, "crf": 28}
        resolution = getattr(body, "preview_resolution", None)
        if row["timeline"].get("schema_version") == 3:
            if resolution is not None:
                raise ValueError("STUDIO_PLAYBACK_VIDEO_RESOLUTION_REQUIRED")
            profile = {"preset": "AUDIO_WAV_PCM16"}
        elif resolution is not None:
            if resolution != "HALF":
                raise ValueError("STUDIO_PLAYBACK_RESOLUTION_INVALID")
            from ..services.studio_timeline_export import PREVIEW_SCALE
            profile["preview_scale"] = PREVIEW_SCALE
        preview = service.timeline_export_preview(nid, scope, actor, tid,
            {**body.model_dump(exclude={"preview_resolution"}), "export_profile": profile}, guard)
        engines = _engines()
        key = _digest(["studio-timeline-playback-cache/1", context, preview["preview_digest"],
            [{"name": item["name"], "sha256": item["sha256"]} for item in engines]])
        request_id = "playback_" + key
        jid = hashlib.sha256(json.dumps([context["scope_key"], context["incarnation"], actor, request_id],
            separators=(",", ":")).encode()).hexdigest()
        try:
            job = service.get(nid, scope, actor, "timeline", jid, guard)
        except FileNotFoundError:
            job = None
        if job is not None:
            if (job["request_id"] != request_id or job["timeline_snapshot"] != preview["timeline_snapshot"]
                    or job["execution_recipe"] != preview["execution_recipe"] or job["sources"] != preview["sources"]):
                raise StaleSourceError("STUDIO_PLAYBACK_ORIGINAL_CACHE_CHANGED")
        guard(); _engine_current(engines)
        result = {"contract": "studio-timeline-playback/1", "novel_id": nid, "branch_id": scope.get("branch_id"),
            "cache_key": key, "request_id": request_id, "job_id": jid,
            "export_preview": preview, "job": job, "cache_state": "RECORDED" if job else "MISSING",
            "model_called": False, "automatic_replay": False, "product_acceptance": "LOCAL_REQUIRED"}
        result["playback_digest"] = _digest([context, {key: result[key] for key in result if key not in {"job", "cache_state"}}])
        return result, engines

    def preview(self, nid, scope, actor, tid, value, guard):
        return self._prepare(nid, scope, actor, tid, value, guard)[0]

    def build(self, nid, scope, actor, tid, value, guard):
        body = TimelinePlaybackBuild.model_validate(value)
        result, engines = self._prepare(nid, scope, actor, tid, body.model_dump(exclude={"reviewed_playback_digest"}), guard)
        if body.reviewed_playback_digest != result["playback_digest"]:
            raise StaleSourceError("STUDIO_PLAYBACK_PREVIEW_CHANGED")
        def current():
            guard(); _engine_current(engines)
        # Existing original jobs are returned, including UNKNOWN/failed states.
        # Only an absent stable request enters the original one-render lease.
        preview = result["export_preview"]
        job = self.service.timeline_export(nid, scope, actor, tid,
            {"expected_version": body.expected_version, "reviewed_timeline_digest": body.reviewed_timeline_digest,
             "export_profile": preview["export_profile"], "request_id": result["request_id"],
             "reviewed_export_digest": preview["preview_digest"]}, current)
        current()
        final_engines = _engines()
        if final_engines != engines:
            raise StaleSourceError("STUDIO_PLAYBACK_ENGINE_CHANGED")
        if job["id"] != result["job_id"] or job["request_id"] != result["request_id"]:
            raise StaleSourceError("STUDIO_PLAYBACK_ORIGINAL_CACHE_CHANGED")
        return {**result, "job": job, "cache_state": "RECORDED"}

    def attest(self, nid, scope, actor, tid, value, guard):
        body = TimelinePlaybackAttestation.model_validate(value)
        result, engines = self._prepare(nid, scope, actor, tid,
            body.model_dump(exclude={"reviewed_playback_digest", "expected_job_version", "expected_request_digest"}), guard)
        job = result["job"]
        if (body.reviewed_playback_digest != result["playback_digest"] or job is None
                or (job["version"], job["request_digest"]) != (body.expected_job_version, body.expected_request_digest)
                or job["status"] not in {"SUCCEEDED", "AWAITING_REVIEW", "APPROVED"}):
            raise StaleSourceError("STUDIO_PLAYBACK_EXACT_CANDIDATE_REQUIRED")
        def current():
            guard(); _engine_current(engines)
        # This is the original candidate proof including current timeline,
        # formal inputs, actor/project binding, promotion proof and actual bytes.
        # A task GET alone cannot attest that old browser bytes remain readable.
        asset, data = self.service.candidate(nid, scope, actor, "timeline", result["job_id"], current)
        latest = self.service.get(nid, scope, actor, "timeline", result["job_id"], current)
        if any(latest[key] != job[key] for key in ("version", "request_digest", "receipt_digest", "status", "output_candidate")):
            raise StaleSourceError("STUDIO_PLAYBACK_EXACT_CANDIDATE_REQUIRED")
        current()
        return {"contract": "studio-timeline-playback-attestation/1", "cache_key": result["cache_key"],
            "playback_digest": result["playback_digest"], "job_id": job["id"], "job_version": job["version"],
            "request_digest": job["request_digest"], "asset_version": asset["version"], "sha256": asset["sha256"],
            "byte_count": len(data), "media_type": asset["media_type"], "product_acceptance": "LOCAL_REQUIRED"}
