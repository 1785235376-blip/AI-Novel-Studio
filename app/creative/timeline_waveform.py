"""Ephemeral selected-clip PCM16 observations over original timeline/assets.

No job, cache, asset, history or timing authority is created. Unsupported media
and platforms fail closed; there is no native decoder or ordinary-open fallback.
"""
from __future__ import annotations

import copy
import io
import struct
import wave

from ..experimental.common import StaleSourceError
from ..services.pcm16_envelope import pcm16_envelope
from .production_execution_models import TimelineWaveformPreview

MAX_BYTES = 8 * 1024 * 1024


class TimelineWaveform:
    def __init__(self, service):
        self.service = service

    def _content(self, nid, scope, source, guard):
        try:
            return self.service.workspace.pinned_content(nid, scope, source, max_bytes=MAX_BYTES, guard=guard)
        except ValueError as exc:
            guard()
            mapped = {"ASSET_BOUNDED_READ_LIMIT": "STUDIO_WAVEFORM_LIMIT",
                      "ASSET_BOUNDED_READ_UNSUPPORTED": "STUDIO_WAVEFORM_PLATFORM_UNSUPPORTED"}
            if str(exc) in mapped:
                raise ValueError(mapped[str(exc)]) from None
            from ..services.asset_library_service import AssetIntegrityError
            if isinstance(exc, AssetIntegrityError):
                raise ValueError("STUDIO_WAVEFORM_CONTENT_UNAVAILABLE") from None
            raise

    @staticmethod
    def _measure(data, clip, guard, *, bounds_only=False):
        guard()
        if len(data) > MAX_BYTES:
            raise ValueError("STUDIO_WAVEFORM_LIMIT")
        if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
            raise ValueError("STUDIO_WAVEFORM_PCM16_REQUIRED")
        if struct.unpack_from("<I", data, 4)[0] + 8 != len(data):
            raise ValueError("STUDIO_WAVEFORM_INVALID")
        try:
            with wave.open(io.BytesIO(data), "rb") as wav:
                frames, rate, channels = wav.getnframes(), wav.getframerate(), wav.getnchannels()
                if wav.getsampwidth() != 2 or wav.getcomptype() != "NONE":
                    raise ValueError("STUDIO_WAVEFORM_PCM16_REQUIRED")
                if (channels not in (1, 2) or not 1 <= rate <= 192000 or frames <= 0
                        or frames > 600 * rate or frames * channels > 4194304):
                    raise ValueError("STUDIO_WAVEFORM_LIMIT")
                start = (clip["in_ms"] * rate + 999) // 1000
                end = (clip["out_ms"] * rate + 999) // 1000
                within = 0 <= start < end <= frames
                if not bounds_only and not within:
                    raise ValueError("STUDIO_WAVEFORM_CLIP_RANGE_INVALID")
                envelope = pcm16_envelope(wav, frame_start=0 if bounds_only else start, frame_end=frames if bounds_only else end, strict=True, guard=guard)
                result = {"frame_count": frames, "sample_rate": rate, "channels": channels,
                          "duration_seconds": {"num": frames, "den": rate},
                          "start_frame": start, "end_frame": end, **envelope}
                if bounds_only:
                    result = {"frame_count":frames,"sample_rate":rate,"channels":channels,
                        "duration_seconds":{"num":frames,"den":rate},"maximum_out_ms":frames*1000//rate,
                        "requested_start_frame":start,"requested_end_frame":end,"within_source":within}
        except (wave.Error, EOFError, struct.error):
            guard()
            raise ValueError("STUDIO_WAVEFORM_INVALID") from None
        guard()
        return result

    def preview(self, nid, scope, actor, tid, value, guard):
        # Include direct service callers as well as the mounted route's earlier
        # authority guards. A stale project ID must not provision a new identity.
        with self.service.store.existing_owner_only():
            return self._preview(nid, scope, actor, tid, value, guard)

    def source_bounds(self, nid, scope, actor, tid, value, guard):
        with self.service.store.existing_owner_only():
            return self._preview(nid, scope, actor, tid, value, guard, bounds_only=True)

    def _preview(self, nid, scope, actor, tid, value, guard, *, bounds_only=False):
        body = TimelineWaveformPreview.model_validate(value)
        service = self.service
        context = service._base(nid, scope, actor, guard)
        source = body.source_snapshot.model_dump()
        # Reuse the original raw scope -> asset -> project phase. Read-only
        # canonical checks and the complete raw transaction finish under leases.
        with service.timeline_inputs.phase(nid, scope, actor, guard) as document:
            if service.store.incarnation(nid) != context["incarnation"]:
                raise StaleSourceError("STUDIO_OWNER_CHANGED")
            row = service._owned_timeline(nid, scope, actor, tid, context, document)
            if (row["version"], row["timeline_digest"]) != (body.expected_version, body.reviewed_timeline_digest):
                raise StaleSourceError("STUDIO_TIMELINE_CHANGED")
            selected = [(track, clip) for track in row["timeline"]["tracks"] for clip in track["clips"]
                        if clip["id"] == body.clip_id]
            if len(selected) != 1:
                raise ValueError("STUDIO_WAVEFORM_CLIP_RANGE_INVALID")
            track, clip = selected[0]
            if track["kind"] != "AUDIO" or clip["source_snapshot"] != source:
                raise StaleSourceError("STUDIO_TIMELINE_SOURCE_CHANGED")
            _, data = self._content(nid, scope, source, guard)
            measured = self._measure(data, clip, guard, bounds_only=True) if bounds_only else self._measure(data, clip, guard)
            # Detect external binary/metadata replacement during measurement as
            # well as ordinary owner mutations (which the phase already fences).
            self._content(nid, scope, source, guard)
            latest = service._owned_timeline(nid, scope, actor, tid, context, document)
            if (latest["version"], latest["timeline_digest"]) != (body.expected_version, body.reviewed_timeline_digest):
                raise StaleSourceError("STUDIO_TIMELINE_CHANGED")
            guard()
            result = {"contract": "studio-timeline-waveform-preview/1", "novel_id": nid,
                      "branch_id": scope.get("branch_id"), "timeline_id": tid,
                      "timeline_version": row["version"], "timeline_digest": row["timeline_digest"],
                      "clip_id": body.clip_id, "source_snapshot": copy.deepcopy(source), "byte_count": len(data),
                      "status": "MEASURED_PCM16_PEAKS", "scope": "CLIP_SOURCE_ENVELOPE",
                      "clip": {key: clip.get(key, 1) for key in ("in_ms", "out_ms", "start_ms", "speed_num", "speed_den")},
                      **measured}
            if bounds_only:
                result.update(contract="studio-timeline-source-bounds/1", status="MEASURED_PCM16_SOURCE_BOUNDS", scope="SOURCE_DURATION_ONLY")
        # The original phase caches its leased owner. Check again only after
        # release so a same-thread injected retirement cannot hide in that cache.
        if service.store.incarnation(nid) != context["incarnation"]:
            raise StaleSourceError("STUDIO_OWNER_CHANGED")
        guard()
        return result
