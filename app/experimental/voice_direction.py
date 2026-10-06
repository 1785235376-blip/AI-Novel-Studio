"""B03: directed edits on R3 audiobook plans and the original audio executor.

No separate queue, asset library or TTS implementation. References/cloning and
remote spending are deliberately unavailable until their separate authorities
are integrated. Local runtime capability is discovered only on explicit send.
"""
from __future__ import annotations
import copy
import base64
from contextvars import ContextVar
from fractions import Fraction
import hashlib
import re
from typing import Literal
from uuid import uuid4
from pydantic import Field, model_validator
from .audiobook import AudiobookV2Service
from .common import StaleSourceError, check_version
from .flags import enabled_flags, require_flag
from .media import StrictModel, digest
from ..source_privacy import content_digest, effective_source_privacy

VOICE_FLAG = "voice_direction_v2"
_actor_context = ContextVar("voice_direction_actor", default=None)


class PronunciationRule(StrictModel):
    term: str = Field(min_length=1, max_length=160)
    pronunciation: str = Field(min_length=1, max_length=240)

    @model_validator(mode="after")
    def plain(self):
        if any(re.search(r"[<>\x00-\x1f\x7f]", value) for value in (self.term, self.pronunciation)):
            raise ValueError("VOICE_PRONUNCIATION_PLAIN_TEXT_REQUIRED")
        return self


def spoken_text(text, rules):
    """Literal, simultaneous replacements; no regex/SSML or cascading edits."""
    mapping = {row["term"]: row["pronunciation"] for row in rules}
    if len(mapping) != len(rules):
        raise ValueError("VOICE_PRONUNCIATION_DUPLICATE")
    if not mapping:
        return text
    pattern = re.compile("|".join(re.escape(term) for term in sorted(mapping, key=len, reverse=True)))
    return pattern.sub(lambda match: mapping[match.group()], text)


class DirectionEditIn(StrictModel):
    expected_version: int = Field(ge=1)
    kind: Literal["NARRATION", "DIALOGUE"]
    character_id: str | None = Field(default=None, max_length=240)
    profile_id: str | None = Field(default=None, max_length=240)
    reviewed_text: str = Field(min_length=1, max_length=20000)
    attribution_reviewed: bool = False
    text_reviewed: bool = False
    voice_authorized: bool = False
    emotion: str = Field(default="neutral", min_length=1, max_length=80)
    speech_rate: float = Field(default=1, ge=.5, le=2)
    pause_ms: int = Field(default=280, ge=0, le=3000)
    pronunciation_rules: list[PronunciationRule] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def safe(self):
        if not self.reviewed_text.strip() or re.search(r"[<>\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", self.reviewed_text):
            raise ValueError("VOICE_REVIEWED_PLAIN_TEXT_REQUIRED")
        if self.kind == "DIALOGUE" and self.attribution_reviewed and not self.character_id:
            raise ValueError("VOICE_UNKNOWN_SPEAKER_CANNOT_BE_REVIEWED")
        spoken_text(self.reviewed_text, [r.model_dump() for r in self.pronunciation_rules])
        return self


class VersionIn(StrictModel):
    expected_version: int = Field(ge=1)


class LockIn(VersionIn):
    locked: bool


class ReorderIn(VersionIn):
    segment_ids: list[str] = Field(min_length=1, max_length=2000)


class QueueSegmentsIn(VersionIn):
    segment_ids: list[str] = Field(min_length=1, max_length=100)
    max_cost: Literal[0] = 0
    local_only: Literal[True] = True
    approve_selected: Literal[True]


class DirectedAudiobookService(AudiobookV2Service):
    """Same R3 rows, fenced even through the inherited R3 read/review paths."""
    @staticmethod
    def as_actor(actor, callback, *args, **kwargs):
        token = _actor_context.set(actor)
        try: return callback(*args, **kwargs)
        finally: _actor_context.reset(token)

    @staticmethod
    def visible(row):
        return set(row.get("required_features", [])).issubset(enabled_flags()) and (
            not row.get("voice_direction") or (VOICE_FLAG in enabled_flags()
                and _actor_context.get() == row.get("created_by")))

    def list(self, nid, scope, collection):
        rows = [r for r in super().list(nid, scope, collection) if self.visible(r)]
        if collection == self.PLANS:
            for row in rows: self._timeline(row)
        return rows

    def get(self, nid, scope, collection, rid):
        row = super().get(nid, scope, collection, rid)
        if not self.visible(row):
            raise FileNotFoundError(rid)
        if collection == self.PLANS:
            self._timeline(row)
        return row

    @staticmethod
    def _timeline(plan):
        if not plan.get("voice_direction"):
            return AudiobookV2Service._timeline(plan)
        position, measured = Fraction(0), 0
        for index, segment in enumerate(plan["segments"]):
            duration = segment.get("duration_ms")
            frames = segment.get("frame_timing")
            if duration is not None:
                measured += 1
                duration = Fraction(frames["frames"] * 1000, frames["sample_rate"]) if frames else Fraction(duration)
            pause = segment.get("direction", {}).get("pause_ms", 0) if index + 1 < len(plan["segments"]) else 0
            if type(pause) is not int or not 0 <= pause <= 3000:
                raise ValueError("VOICE_PAUSE_INVALID")
            segment["start_ms"] = float(position) if position is not None else None
            end = position + duration if position is not None and duration is not None else None
            segment["end_ms"] = float(end) if end is not None else None
            segment["pause_after_ms"] = pause
            # No guessed start beyond an unmeasured segment. No final silence.
            silence = Fraction(round(Fraction(pause * frames["sample_rate"], 1000)) * 1000, frames["sample_rate"]) if frames else Fraction(pause)
            position = end + silence if end is not None else None
        plan["duration_ms"] = float(position) if position is not None else None
        plan["timing_status"] = "MEASURED" if measured == len(plan["segments"]) else "PARTIAL" if measured else "UNMEASURED"

    def mutate(self, nid, scope, actor, collection, rid, expected_version, callback):
        def guarded(row):
            if not self.visible(row):
                raise FileNotFoundError(rid)
            if row.get("voice_direction") and row.get("created_by") != actor:
                raise FileNotFoundError(rid)
            callback(row)
        return self.as_actor(actor, super().mutate, nid, scope, actor, collection, rid, expected_version, guarded)

    def create(self, nid, scope, actor, collection, payload):
        if collection == self.MIXES:
            plan = self.get(nid, scope, self.PLANS, payload["plan_id"])
            if plan.get("voice_direction"):
                payload = {**payload, "voice_direction": True}
        return super().create(nid, scope, actor, collection, payload)

    def owned_plan(self, nid, scope, actor, rid, current=True):
        row = self.as_actor(actor, self.get, nid, scope, self.PLANS, rid)
        if row.get("created_by") != actor:
            raise FileNotFoundError(rid)
        if current:
            self._assert_plan(nid, scope, row)
        return row

    def catalog(self, nid, scope, actor):
        require_flag(VOICE_FLAG)
        plans = [r for r in self.as_actor(actor, self.plans, nid, scope) if r["created_by"] == actor]
        for row in plans:
            if row["stale"]:
                row.pop("segments", None)
        mixes = [{k: v for k, v in r.items() if k != "history"} for r in
            self.as_actor(actor, self.list_review_items, nid, scope) if r.get("plan_id") and r.get("voice_direction")]
        return {"plans": plans, "mixes": mixes, "mixer": self.capabilities()["mixer"], "profiles": self.list(nid, scope, self.PROFILES),
                "characters": [{"id": "__narrator__", "name": "旁白"}, *[{"id": c["id"], "name": c.get("name", c["id"])} for c in self._characters(nid, scope)]],
                "tts": {"execution": "EXISTING_EXECUTOR_LOCAL_ONLY", "runtime": "CHECKED_ON_EXPLICIT_EXECUTE", "max_cost": 0,
                        "reference_voice": "UNAVAILABLE_SEPARATE_CONSENT_REQUIRED", "quality": "NOT_RUN", "alignment": "NOT_CONFIGURED"}}

    def edit_direction(self, nid, scope, actor, rid, sid, body):
        require_flag(VOICE_FLAG)
        data = DirectionEditIn.model_validate(body)
        self.owned_plan(nid, scope, actor, rid)
        def change(row):
            self._editable(row)
            self._assert_plan(nid, scope, row)
            segment = next((r for r in row["segments"] if r["id"] == sid), None)
            if not segment:
                raise FileNotFoundError(sid)
            if segment.get("locked"):
                raise ValueError("VOICE_SEGMENT_LOCKED")
            cid = "__narrator__" if data.kind == "NARRATION" else data.character_id
            if cid:
                row["character_snapshots"][cid] = digest(self._character(nid, scope, cid))
            profile = self.get(nid, scope, self.PROFILES, data.profile_id) if data.profile_id else None
            direction = data.model_dump(exclude={"expected_version", "kind", "character_id", "profile_id", "attribution_reviewed"})
            direction["pronunciation_mode"] = "LITERAL_SIMULTANEOUS"
            direction["spoken_text_digest"] = hashlib.sha256(spoken_text(data.reviewed_text, direction["pronunciation_rules"]).encode()).hexdigest()
            row.update(voice_direction=True, privacy_level="LOCAL_ONLY")
            segment.update(kind=data.kind, character_id=cid, profile_id=data.profile_id,
                profile_version=profile["version"] if profile else None, mapping_id=None, mapping_version=None,
                attribution_status="NARRATION" if data.kind == "NARRATION" else "REVIEWED" if data.attribution_reviewed else "NEEDS_REVIEW",
                emotion=data.emotion, direction=direction, direction_revision=segment.get("direction_revision", 0) + 1,
                audio_asset_id=None, audio_source=None, duration_ms=None, timing_status="UNMEASURED")
            self._timeline(row)
        return self.mutate(nid, scope, actor, self.PLANS, rid, data.expected_version, change)

    def update_segment(self, nid, scope, actor, rid, sid, body):
        row = self.get(nid, scope, self.PLANS, rid)
        if row.get("voice_direction"):
            raise ValueError("VOICE_USE_DIRECTION_EDITOR")
        return super().update_segment(nid, scope, actor, rid, sid, body)

    def lock(self, nid, scope, actor, rid, sid, body):
        require_flag(VOICE_FLAG); data = LockIn.model_validate(body)
        self.owned_plan(nid, scope, actor, rid)
        def change(row):
            segment = next((s for s in row["segments"] if s["id"] == sid), None)
            if not segment: raise FileNotFoundError(sid)
            if data.locked and not segment.get("audio_asset_id"):
                raise ValueError("VOICE_MEASURED_AUDIO_REQUIRED_TO_LOCK")
            row["voice_direction"] = True
            segment["locked"] = data.locked
        return self.mutate(nid, scope, actor, self.PLANS, rid, data.expected_version, change)

    def reorder(self, nid, scope, actor, rid, body):
        require_flag(VOICE_FLAG); data = ReorderIn.model_validate(body)
        self.owned_plan(nid, scope, actor, rid)
        def change(row):
            self._editable(row)
            self._assert_plan(nid, scope, row)
            if len(data.segment_ids) != len(set(data.segment_ids)) or set(data.segment_ids) != {s["id"] for s in row["segments"]}:
                raise ValueError("VOICE_REORDER_EXACT_SEGMENTS_REQUIRED")
            mapping = {s["id"]: s for s in row["segments"]}
            row.update(voice_direction=True, segments=[mapping[s] for s in data.segment_ids])
            self._timeline(row)
        return self.mutate(nid, scope, actor, self.PLANS, rid, data.expected_version, change)

    def bind_audio(self, nid, scope, actor, rid, sid, body):
        row = self.get(nid, scope, self.PLANS, rid)
        if next((s.get("locked") for s in row["segments"] if s["id"] == sid), False):
            raise ValueError("VOICE_SEGMENT_LOCKED")
        return super().bind_audio(nid, scope, actor, rid, sid, body)

    def review(self, nid, scope, actor, item_id, action, expected_version):
        row = self.get(nid, scope, self.PLANS, item_id) if any(p["id"] == item_id for p in self.list(nid, scope, self.PLANS)) else None
        if row and row.get("voice_direction") and action == "approve":
            if any(not s.get("direction", {}).get("text_reviewed") or not s.get("direction", {}).get("voice_authorized") for s in row["segments"]):
                raise ValueError("VOICE_TEXT_AND_VOICE_REVIEW_REQUIRED")
        return super().review(nid, scope, actor, item_id, action, expected_version)

    def mix(self, nid, scope, actor, rid, expected_version, check_authority=None):
        if self.get(nid, scope, self.PLANS, rid).get("voice_direction"):
            require_flag(VOICE_FLAG)
            plan = self.owned_plan(nid, scope, actor, rid)
            if any(not s.get("direction", {}).get("text_reviewed") or not s.get("direction", {}).get("voice_authorized") for s in plan["segments"]):
                raise ValueError("VOICE_TEXT_AND_VOICE_REVIEW_REQUIRED")
        return super().mix(nid, scope, actor, rid, expected_version, check_authority)

    def _mix_origin(self, nid, scope, plan, source_ids):
        options = self._mix_asset_options(nid, scope, plan, {"source_asset_ids":source_ids})
        origin = {"required_features": list(options["required_features"])} if options else {}
        if not plan.get("voice_direction"): return origin
        return {**origin, "voice_direction": True, "timeline": [{k: s.get(k) for k in
            ("id", "audio_asset_id", "start_ms", "end_ms", "pause_after_ms", "frame_timing")} for s in plan["segments"]]}

    def duration_manifest(self, nid, scope, rid):
        manifest = super().duration_manifest(nid, scope, rid)
        plan = self.get(nid, scope, self.PLANS, rid)
        if plan.get("voice_direction"):
            manifest["silence_policy"] = "BETWEEN_SEGMENTS_NO_TRAILING_SILENCE"
            for timing, segment in zip(manifest["segments"], plan["segments"]):
                timing.update(pause_after_ms=segment["pause_after_ms"], frame_timing=segment.get("frame_timing"))
        return manifest

    def _mix_asset_options(self, nid, scope, plan, proposal):
        features = {"audiobook_v2", VOICE_FLAG} if plan.get("voice_direction") else set()
        for aid in proposal["source_asset_ids"]:
            asset, _ = self._audio_asset(nid, scope, aid)
            features.update(asset.get("_required_features", []))
        # Explicit mix approval uses the original asset promotion lifecycle.
        # Persist every source origin at creation, before metadata is attached.
        return {"required_features": tuple(sorted(features))} if features else {}

    def mix_audio(self, nid, scope, actor, rid, expected_version):
        require_flag(VOICE_FLAG)
        row = self.get(nid, scope, self.MIXES, rid)
        if not row.get("voice_direction") or row["created_by"] != actor:
            raise FileNotFoundError(rid)
        check_version(row, expected_version)
        self._mix_plan(nid, scope, row)
        if row["status"] not in {"PENDING_REVIEW", "APPROVING", "APPROVED"}:
            raise ValueError("VOICE_MIX_PREVIEW_UNAVAILABLE")
        content = base64.b64decode(row["content_base64"], validate=True)
        if hashlib.sha256(content).hexdigest() != row["content_sha256"]:
            raise ValueError("AUDIO_MIX_INTEGRITY_FAILED")
        if row.get("asset_id"):
            _, content = self._audio_asset(nid, scope, row["asset_id"])
            if hashlib.sha256(content).hexdigest() != row["content_sha256"]:
                raise ValueError("AUDIO_MIX_INTEGRITY_FAILED")
        current = self.get(nid, scope, self.MIXES, rid)
        check_version(current, expected_version)
        self._mix_plan(nid, scope, current)
        if current["content_sha256"] != row["content_sha256"]:
            raise StaleSourceError("AUDIO_MIX_CONTENT_CHANGED")
        return content, row["media"]["media_type"]

    @staticmethod
    def segment_fingerprint(segment):
        return digest({k: segment.get(k) for k in ("id", "text", "source_text_digest", "kind", "character_id", "profile_id", "profile_version", "attribution_status", "direction", "direction_revision")})

    def queue_selected(self, nid, scope, actor, rid, body, executor, reauthorize, idempotency_key=None):
        require_flag(VOICE_FLAG); data = QueueSegmentsIn.model_validate(body)
        plan = self.owned_plan(nid, scope, actor, rid); check_version(plan, data.expected_version)
        if plan["status"] != "APPROVED" or not plan.get("voice_direction"):
            raise ValueError("VOICE_APPROVED_DIRECTION_REQUIRED")
        if len(set(data.segment_ids)) != len(data.segment_ids): raise ValueError("VOICE_DUPLICATE_SEGMENT")
        selected = [next((s for s in plan["segments"] if s["id"] == sid), None) for sid in data.segment_ids]
        if any(s is None for s in selected): raise FileNotFoundError("segment")
        if any(s.get("locked") for s in selected): raise ValueError("VOICE_SEGMENT_LOCKED")
        chapter = self._source(nid, scope, plan["chapter_id"])
        prepared = []
        for segment in selected:
            direction = segment.get("direction", {})
            if not direction.get("text_reviewed") or not direction.get("voice_authorized") or segment["attribution_status"] == "NEEDS_REVIEW":
                raise ValueError("VOICE_SEGMENT_REVIEW_REQUIRED")
            profile = self.get(nid, scope, self.PROFILES, segment["profile_id"])
            prepared.append((segment, direction, profile))
        reauthorize()
        current = self.owned_plan(nid, scope, actor, rid); check_version(current, data.expected_version)
        if idempotency_key is not None and (not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 240):
            raise ValueError("VOICE_IDEMPOTENCY_KEY_INVALID")
        group = digest([actor, scope, rid, idempotency_key]) if idempotency_key else str(uuid4())
        jobs = []
        for index, (segment, direction, profile) in enumerate(prepared):
            reauthorize()
            fresh = self.owned_plan(nid, scope, actor, rid)
            check_version(fresh, data.expected_version)
            config = {"provider_id": profile["provider_id"], "model_id": profile["model_id"], "voice": profile["voice_id"],
                "emotion": direction["emotion"], "speech_rate": direction["speech_rate"], "pause_ms": direction["pause_ms"],
                "character_id": segment["character_id"], "license_note": profile["license_note"], "group_id": group,
                "segment_index": index, "segment_count": len(prepared), "experimental_origin": VOICE_FLAG,
                "pronunciation_snapshot": direction["pronunciation_rules"], "direction_binding": {"plan_id": rid,
                    "segment_id": segment["id"], "fingerprint": self.segment_fingerprint(segment), "actor": actor, "scope": copy.deepcopy(scope)},
                "local_only": True, "max_cost": 0}
            # Existing durable queue snapshots this reviewed segment and the
            # original full chapter separately; timing is unknown, never guessed.
            jobs.append(executor.queue(nid, {**chapter, "content": direction["reviewed_text"]}, config, [], idempotency_key="voice-" + digest([group, segment["id"]]), source_chapter=chapter))
        return {"items": jobs, "approval_status": "PENDING", "execution": "QUEUED_NOT_SENT", "group_id": group}

    def execute_local_job(self, nid, scope, actor, jid, executor, resolver, guard, before_send=None):
        """One shared B03 execution authority for standalone and U16 callers."""
        from ..services.audiobook_service import AudiobookError
        job = executor.find(executor.store.load(nid), jid)
        provider_identity = None
        def identity(resolved):
            provider = resolved[2]
            return (resolved[0], resolved[1], getattr(provider, 'endpoint', None), bool(getattr(provider, 'local', False)), tuple(getattr(provider, 'emotion_values', ())))
        def check(current):
            guard(); source = self.assert_job(nid, scope, actor, current)
            if provider_identity is not None and identity(resolver(current.get('provider_id') or 'auto')) != provider_identity:
                raise AudiobookError('VOICE_PROVIDER_AUTHORITY_CHANGED', '声音 Provider 配置已变化，请重新核对', 409)
            return source
        chapter = check(job)
        def resolve(pid):
            nonlocal provider_identity
            resolved = resolver(pid)
            if not getattr(resolved[2], 'local', False): raise AudiobookError('VOICE_REMOTE_BUDGET_NOT_INTEGRATED', '仅允许显式本地零外部费用执行', 403)
            provider_identity = identity(resolved)
            return resolved
        return executor.execute(nid, jid, chapter, resolve, lambda: check(job), direction_guard=check, before_send=before_send)

    def assert_job(self, nid, scope, actor, job):
        require_flag(VOICE_FLAG)
        binding = job.get("direction_binding", {})
        if job.get("experimental_origin") != VOICE_FLAG or binding.get("actor") != actor or binding.get("scope") != scope:
            raise FileNotFoundError(job.get("id", "job"))
        plan = self.owned_plan(nid, scope, actor, binding["plan_id"])
        segment = next((s for s in plan["segments"] if s["id"] == binding["segment_id"]), None)
        if plan["status"] != "APPROVED" or not segment or segment.get("locked") or self.segment_fingerprint(segment) != binding["fingerprint"]:
            raise StaleSourceError("VOICE_APPROVED_SEGMENT_CHANGED")
        chapter = self._source(nid, scope, plan["chapter_id"])
        if chapter["version"] != job["source_version"] or content_digest(chapter) != job["source_content_sha256"]:
            raise StaleSourceError("VOICE_SOURCE_CHANGED")
        return chapter
