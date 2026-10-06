"""Audiobook preparation with reviewable attribution and measured-only timing.

No TTS quality, phoneme alignment, precise lip sync, or word alignment is
claimed. A plan can be approved before audio exists; measured durations and
subtitles become available only after verified audio assets are bound.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import io
import re
import wave
from fractions import Fraction
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import uuid4

from pydantic import Field, model_validator

from ..media_files import inspect_media
from ..source_privacy import content_digest
from .common import DomainService, StaleSourceError, check_version, now, snapshot, new_row, change_row
from .media import StrictModel, digest, checkpoint_promotion_asset


class VoiceProfileIn(StrictModel):
    display_name: str = Field(min_length=1, max_length=240)
    provider_id: str = Field(min_length=1, max_length=240)
    model_id: str = Field(min_length=1, max_length=240)
    voice_id: str = Field(min_length=1, max_length=240)
    license_note: str = Field(min_length=1, max_length=2000)
    language: str = Field(default="zh", max_length=40)
    supports_emotion: bool = False
    supports_style: bool = False


class VoiceMappingIn(StrictModel):
    character_id: str = Field(min_length=1, max_length=240)
    profile_id: str = Field(min_length=1, max_length=240)
    expected_version: int | None = Field(default=None, ge=1)


class AudiobookPlanIn(StrictModel):
    chapter_id: str = Field(min_length=1, max_length=240)
    title: str = Field(default="", max_length=240)


class SegmentUpdateIn(StrictModel):
    expected_version: int = Field(ge=1)
    character_id: str | None = Field(default=None, max_length=240)
    profile_id: str | None = Field(default=None, max_length=240)
    emotion: str = Field(default="neutral", min_length=1, max_length=80)
    speaking_style: str = Field(default="", max_length=240)
    attribution_reviewed: bool = False


class SegmentAudioIn(StrictModel):
    expected_version: int = Field(ge=1)
    asset_id: str = Field(min_length=1, max_length=240)


class AudioTrackIn(StrictModel):
    expected_version: int = Field(ge=1)
    kind: Literal["MUSIC", "AMBIENCE", "SFX"]
    label: str = Field(min_length=1, max_length=240)
    asset_id: str | None = Field(default=None, max_length=240)
    start_ms: int | None = Field(default=None, ge=0)
    gain_db: float = Field(default=0, ge=-60, le=12)
    end_ms: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def range(self):
        if self.end_ms is not None and (self.start_ms is None or self.end_ms <= self.start_ms):
            raise ValueError("track end must follow its start")
        return self


@dataclass(frozen=True)
class DialogueAttribution:
    character_id: str | None
    status: str
    evidence: str


class DialogueAttributionAdapter(Protocol):
    def attribute(self, preceding_text: str, quoted_text: str, characters: list[dict]) -> DialogueAttribution: ...


class RuleDialogueAttribution:
    """Only exact named speech prefixes are accepted, never pronoun guesses."""
    def attribute(self, preceding_text, quoted_text, characters):
        matches = []
        evidence = preceding_text[-160:]
        for character in characters:
            names = [character.get("name", ""), *character.get("aliases", [])]
            for name in names:
                if not isinstance(name, str) or not name.strip():
                    continue
                # Adjacent named prefix avoids assuming the last mentioned
                # character is the speaker. Names inside names do not match.
                pattern = r"(?:^|[\s，。！？;；])" + re.escape(name) + r"\s*(?:(?:说|问|答|喊|低声说|说道|回答|said|asked)\s*)?[：:]\s*$"
                if re.search(pattern, evidence, flags=re.IGNORECASE):
                    matches.append(character["id"])
                    break
        matches = list(dict.fromkeys(matches))
        return DialogueAttribution(matches[0], "RULE_CONFIRMED", evidence) if len(matches) == 1 else DialogueAttribution(None, "NEEDS_REVIEW", evidence)


@dataclass(frozen=True)
class MixerRequest:
    request_id: str
    speech: list[dict]
    tracks: list[dict]
    sample_timing: str = "MEASURED_SEGMENTS"


@dataclass(frozen=True)
class MixerResult:
    content: bytes
    media_type: str
    verification: str


class MixerAdapter(Protocol):
    adapter_id: str
    local: bool

    def mix(self, request: MixerRequest) -> MixerResult: ...


class LocalPcmMixer:
    """Small, bounded PCM16 WAV mixer. No TTS or alignment inference."""
    adapter_id, local = "local-pcm16-wav-v1", True

    def mix(self, request):
        import array
        import sys
        if sum(len(item["content"]) for item in [*request.speech, *request.tracks]) > 64 * 1024 * 1024:
            raise ValueError("AUDIO_MIX_INPUT_TOO_LARGE")
        sources = []
        parameters = None
        for item in [*request.speech, *request.tracks]:
            content = item["content"]
            if content[:4] != b"RIFF" or content[8:12] != b"WAVE":
                raise ValueError("AUDIO_MIX_PCM16_REQUIRED")
            inspect_media(content, "audio")
            with wave.open(io.BytesIO(content), "rb") as wav:
                config = (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype())
                if config[1] != 2 or config[0] not in (1, 2) or config[3] != "NONE":
                    raise ValueError("AUDIO_MIX_PCM16_REQUIRED")
                if parameters is not None and parameters != config:
                    raise ValueError("AUDIO_MIX_FORMAT_MISMATCH")
                parameters = config
                samples = array.array("h", wav.readframes(wav.getnframes()))
                if sys.byteorder != "little":
                    samples.byteswap()
                start = round(item["start_ms"] * config[2] / 1000) * config[0]
                if item.get("end_ms") is not None:
                    samples = samples[:max(0, round((item["end_ms"] - item["start_ms"]) * config[2] / 1000) * config[0])]
                sources.append((start, samples, 10 ** (item.get("gain_db", 0) / 20)))
        if not parameters or not sources:
            raise ValueError("AUDIO_MIX_INPUT_REQUIRED")
        length = max(start + len(samples) for start, samples, _ in sources)
        if length * 2 > 25 * 1024 * 1024:
            raise ValueError("AUDIO_MIX_OUTPUT_TOO_LARGE")
        mixed = [0.0] * length
        for start, samples, gain in sources:
            for offset, sample in enumerate(samples):
                mixed[start + offset] += sample * gain
        output = array.array("h", [max(-32768, min(32767, round(v))) for v in mixed])
        if __import__("sys").byteorder != "little":
            output.byteswap()
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(parameters[0]); wav.setsampwidth(2); wav.setframerate(parameters[2]); wav.writeframes(output.tobytes())
        return MixerResult(buffer.getvalue(), "audio/wav", "CONTRACT_VERIFIED")


class AudiobookV2Service(DomainService):
    PROFILES, MAPPINGS, PLANS, MIXES = "audio_v2_profiles", "audio_v2_mappings", "audio_v2_plans", "audio_v2_mix_proposals"

    def __init__(self, store, novels, chapters, assets=None, attribution=None, mixer=None):
        super().__init__(store, novels, chapters)
        self.assets = assets
        self.attribution = attribution or RuleDialogueAttribution()
        self.mixer = mixer

    def capabilities(self):
        return {"dialogue_attribution": "RULE_BASED", "uncertain_attribution": "NEEDS_REVIEW", "tts_execution": "NOT_CONFIGURED",
                "mixer": "NOT_CONFIGURED" if self.mixer is None else self.mixer.adapter_id,
                "timestamps": "MEASURED_SEGMENT_ONLY", "phoneme_alignment": "NOT_CONFIGURED", "lip_sync": "NOT_CONFIGURED"}

    def _characters(self, nid, scope):
        rows = self.novels.data_set(nid, "characters")
        if scope.get("mode") == "collaboration":
            return [r for r in rows if r.get("branch_id") == scope.get("branch_id")]
        return [r for r in rows if r.get("branch_id") is None]

    def _character(self, nid, scope, cid):
        if cid == "__narrator__":
            return {"id": cid, "name": "Narrator"}
        row = next((r for r in self._characters(nid, scope) if r["id"] == cid), None)
        if row is None:
            raise FileNotFoundError(cid)
        return row

    def _source(self, nid, scope, chapter_id):
        chapter = self.chapters.get(chapter_id)
        if chapter.get("novel_id") != nid:
            raise FileNotFoundError(chapter_id)
        if chapter.get("branch_id") != scope.get("branch_id"):
            raise StaleSourceError("BRANCH_SOURCE_ADAPTER_REQUIRED")
        return chapter

    def create_profile(self, nid, scope, actor, body):
        return self.create(nid, scope, actor, self.PROFILES, {**VoiceProfileIn.model_validate(body).model_dump(),
            "status": "ACTIVE", "verification": "NOT_RUN", "voice_quality": "NOT_RUN"})

    def map_voice(self, nid, scope, actor, body):
        data = VoiceMappingIn.model_validate(body).model_dump()
        self._character(nid, scope, data["character_id"])
        profile = self.get(nid, scope, self.PROFILES, data["profile_id"])
        expected = data.pop("expected_version")
        with self.store.transaction(nid, scope) as doc:
            rows = doc["collections"].setdefault(self.MAPPINGS, {})
            previous = next((r for r in rows.values() if r["character_id"] == data["character_id"]), None)
            data.update(profile_version=profile["version"], status="ACTIVE")
            if previous:
                change_row(previous, actor, expected, lambda row: row.update(data))
                return copy.deepcopy(previous)
            if expected is not None:
                raise ValueError("AUDIO_MAPPING_NOT_CREATED")
            row = new_row(nid, scope, actor, data)
            rows[row["id"]] = row
            return copy.deepcopy(row)

    def _segment(self, text, start, end, kind, attribution, mappings, profiles):
        original = text[start:end]
        lead = len(original) - len(original.lstrip())
        tail = len(original.rstrip())
        start, end = start + lead, start + tail
        if start >= end:
            return None
        cid = "__narrator__" if kind == "NARRATION" else attribution.character_id
        mapping = mappings.get(cid)
        profile = profiles.get(mapping["profile_id"]) if mapping else None
        return {"id": str(uuid4()), "kind": kind, "text": text[start:end], "source_start": start, "source_end": end,
            "source_text_digest": hashlib.sha256(text[start:end].encode()).hexdigest(), "character_id": cid,
            "attribution_status": "NARRATION" if kind == "NARRATION" else attribution.status if cid else "NEEDS_REVIEW",
            "attribution_evidence": "" if kind == "NARRATION" else attribution.evidence,
            "profile_id": profile["id"] if profile else None, "profile_version": profile["version"] if profile else None,
            "mapping_id": mapping["id"] if mapping else None, "mapping_version": mapping["version"] if mapping else None,
            "emotion": "neutral", "speaking_style": "", "start_ms": None, "end_ms": None, "duration_ms": None,
            "timing_status": "UNMEASURED", "audio_asset_id": None}

    def create_plan(self, nid, scope, actor, body):
        data = AudiobookPlanIn.model_validate(body).model_dump()
        chapter = self._source(nid, scope, data["chapter_id"])
        text = chapter.get("content", "")
        source_snapshot = {chapter["id"]: {"version": chapter["version"], "digest": content_digest(chapter)}}
        if not text.strip():
            raise ValueError("AUDIO_CHAPTER_EMPTY")
        if len(text) > 200000:
            raise ValueError("AUDIO_CHAPTER_REQUIRES_CHUNKING")
        characters = self._characters(nid, scope)
        mappings = {r["character_id"]: r for r in self.list(nid, scope, self.MAPPINGS)}
        profiles = {r["id"]: r for r in self.list(nid, scope, self.PROFILES)}
        segments, position = [], 0
        quote_pattern = re.compile(r'“[^”]*”|「[^」]*」|『[^』]*』|"[^"\n]+"')
        for match in quote_pattern.finditer(text):
            if match.start() > position:
                segment = self._segment(text, position, match.start(), "NARRATION", None, mappings, profiles)
                if segment:
                    segments.append(segment)
            attribution = self.attribution.attribute(text[position:match.start()], match.group()[1:-1], characters)
            if attribution.character_id and attribution.character_id not in {r["id"] for r in characters}:
                raise ValueError("AUDIO_ATTRIBUTION_REFERENCE_INVALID")
            if attribution.status not in {"RULE_CONFIRMED", "NEEDS_REVIEW"}:
                raise ValueError("AUDIO_ATTRIBUTION_STATUS_INVALID")
            segment = self._segment(text, match.start() + 1, match.end() - 1, "DIALOGUE", attribution, mappings, profiles)
            if segment:
                segments.append(segment)
            position = match.end()
        if position < len(text):
            segment = self._segment(text, position, len(text), "NARRATION", None, mappings, profiles)
            if segment:
                segments.append(segment)
        if not segments:
            raise ValueError("AUDIO_NO_SPEECH_SEGMENTS")
        if len(segments) > 2000:
            raise ValueError("AUDIO_SEGMENT_LIMIT_REQUIRES_CHUNKING")
        data.update(title=data["title"] or chapter.get("title", "Audiobook"), sources=source_snapshot,
            segments=segments, tracks=[], status="PENDING_REVIEW", timing_status="UNMEASURED",
            character_snapshots={r["id"]: digest(r) for r in characters}, verification="CONTRACT_VERIFIED",
            inference_performed=False, duration_ms=None)
        self.assert_sources(nid, source_snapshot)
        return self.create(nid, scope, actor, self.PLANS, data)

    def _assert_plan(self, nid, scope, plan):
        chapter = self._source(nid, scope, plan["chapter_id"])
        self.assert_sources(nid, plan["sources"])
        source = plan["sources"].get(plan["chapter_id"], {})
        if chapter.get("version") != source.get("version") or content_digest(chapter) != source.get("digest"):
            raise StaleSourceError("AUDIO_CHAPTER_SNAPSHOT_CHANGED")
        current_characters = {r["id"]: digest(r) for r in self._characters(nid, scope)}
        for segment in plan["segments"]:
            text = chapter.get("content", "")
            start, end = segment.get("source_start"), segment.get("source_end")
            if (not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= len(text)
                    or text[start:end] != segment.get("text")
                    or hashlib.sha256(text[start:end].encode()).hexdigest() != segment.get("source_text_digest")):
                raise StaleSourceError("AUDIO_SEGMENT_EVIDENCE_CHANGED")
            cid = segment.get("character_id")
            if cid and cid != "__narrator__" and current_characters.get(cid) != plan["character_snapshots"].get(cid):
                raise StaleSourceError("AUDIO_CHARACTER_CHANGED")
            if segment.get("profile_id"):
                profile = self.get(nid, scope, self.PROFILES, segment["profile_id"])
                if profile["version"] != segment["profile_version"]:
                    raise StaleSourceError("AUDIO_VOICE_PROFILE_CHANGED")
            if segment.get("mapping_id"):
                mapping = self.get(nid, scope, self.MAPPINGS, segment["mapping_id"])
                if mapping["version"] != segment["mapping_version"]:
                    raise StaleSourceError("AUDIO_VOICE_MAPPING_CHANGED")
            if segment.get("audio_asset_id"):
                asset, _ = self._audio_asset(nid, scope, segment["audio_asset_id"])
                if {"version": asset["version"], "digest": asset["sha256"]} != segment["audio_source"]:
                    raise StaleSourceError("AUDIO_SEGMENT_ASSET_CHANGED")
        for track in plan["tracks"]:
            if track.get("asset_id"):
                asset, _ = self._audio_asset(nid, scope, track["asset_id"])
                if {"version": asset["version"], "digest": asset["sha256"]} != track["audio_source"]:
                    raise StaleSourceError("AUDIO_TRACK_ASSET_CHANGED")

    def plans(self, nid, scope):
        rows = self.list(nid, scope, self.PLANS)
        for row in rows:
            try:
                self._assert_plan(nid, scope, row)
                row["stale"] = False
            except (StaleSourceError, FileNotFoundError):
                row["stale"] = True
            row["needs_review_count"] = sum(s["attribution_status"] == "NEEDS_REVIEW" for s in row["segments"])
        return rows

    @staticmethod
    def _editable(row):
        if row["status"] != "PENDING_REVIEW":
            raise ValueError("AUDIO_PLAN_REOPEN_REQUIRED")

    def update_segment(self, nid, scope, actor, rid, sid, body):
        data = SegmentUpdateIn.model_validate(body)
        def change(row):
            self._editable(row)
            self._source(nid, scope, row["chapter_id"])
            self.assert_sources(nid, row["sources"])
            segment = next((s for s in row["segments"] if s["id"] == sid), None)
            if segment is None:
                raise FileNotFoundError(sid)
            cid = "__narrator__" if segment["kind"] == "NARRATION" else data.character_id
            if cid:
                character = self._character(nid, scope, cid)
                row["character_snapshots"][cid] = digest(character)
            if segment["kind"] == "DIALOGUE" and data.attribution_reviewed and not cid:
                raise ValueError("AUDIO_REVIEWED_SPEAKER_REQUIRED")
            profile = self.get(nid, scope, self.PROFILES, data.profile_id) if data.profile_id else None
            segment.update(character_id=cid, profile_id=profile["id"] if profile else None,
                profile_version=profile["version"] if profile else None, mapping_id=None, mapping_version=None,
                emotion=data.emotion, speaking_style=data.speaking_style,
                attribution_status="NARRATION" if segment["kind"] == "NARRATION" else "REVIEWED" if data.attribution_reviewed else "NEEDS_REVIEW")
            # Changing a speaker or delivery invalidates previously rendered speech.
            segment.update(audio_asset_id=None, audio_source=None, duration_ms=None, frame_timing=None, timing_status="UNMEASURED")
            self._timeline(row)
        return self.mutate(nid, scope, actor, self.PLANS, rid, data.expected_version, change)

    def _audio_asset(self, nid, scope, aid):
        if self.assets is None:
            raise ValueError("AUDIO_ASSET_SERVICE_NOT_CONFIGURED")
        asset = self.assets.get(aid, branch_id=scope.get("branch_id"))
        if asset.get("novel_id") != nid or asset.get("branch_id") != scope.get("branch_id") or asset.get("kind") != "audio":
            raise FileNotFoundError(aid)
        content = self.assets.content(aid, branch_id=scope.get("branch_id"))
        return asset, content

    @staticmethod
    def _timeline(plan):
        position, measured = Fraction(0), 0
        for segment in plan["segments"]:
            duration = segment.get("duration_ms")
            frames = segment.get("frame_timing")
            if duration is not None:
                measured += 1
                duration = Fraction(frames["frames"] * 1000, frames["sample_rate"]) if frames else Fraction(str(duration))
            end = position + duration if position is not None and duration is not None else None
            segment["start_ms"] = float(position) if position is not None else None
            segment["end_ms"] = float(end) if end is not None else None
            # Preserve measured frame arithmetic internally; display milliseconds
            # are only a projection, never ASR/word/phoneme alignment.
            position = end
        plan["duration_ms"] = float(position) if position is not None else None
        plan["timing_status"] = "MEASURED" if measured == len(plan["segments"]) else "PARTIAL" if measured else "UNMEASURED"

    def bind_audio(self, nid, scope, actor, rid, sid, body):
        data = SegmentAudioIn.model_validate(body)
        asset, content = self._audio_asset(nid, scope, data.asset_id)
        measured = inspect_media(content, "audio")
        if not isinstance(measured.get("duration_ms"), (int, float)) or measured["duration_ms"] <= 0:
            raise ValueError("AUDIO_DURATION_UNAVAILABLE")
        frame_timing = None
        if measured["media_type"] == "audio/wav":
            with wave.open(io.BytesIO(content), "rb") as audio:
                frame_timing = {"frames": audio.getnframes(), "sample_rate": audio.getframerate()}
        def change(row):
            self._editable(row)
            self._assert_plan(nid, scope, row)
            segment = next((s for s in row["segments"] if s["id"] == sid), None)
            if segment is None:
                raise FileNotFoundError(sid)
            segment.update(audio_asset_id=asset["id"], audio_source={"version": asset["version"], "digest": asset["sha256"]},
                           duration_ms=measured["duration_ms"], timing_status="MEASURED", media_validation=measured["validation"],
                           frame_timing=frame_timing)
            self._timeline(row)
        return self.mutate(nid, scope, actor, self.PLANS, rid, data.expected_version, change)

    def add_track(self, nid, scope, actor, rid, body):
        data = AudioTrackIn.model_validate(body).model_dump()
        expected = data.pop("expected_version")
        data.update(id=str(uuid4()), status="PLANNED")
        if data["asset_id"]:
            asset, content = self._audio_asset(nid, scope, data["asset_id"])
            measured = inspect_media(content, "audio")
            data.update(duration_ms=measured["duration_ms"], audio_source={"version": asset["version"], "digest": asset["sha256"]})
        def change(row):
            self._editable(row)
            self._assert_plan(nid, scope, row)
            if len(row["tracks"]) >= 100:
                raise ValueError("AUDIO_TRACK_LIMIT")
            row["tracks"].append(data)
        return self.mutate(nid, scope, actor, self.PLANS, rid, expected, change)

    def remove_track(self, nid, scope, actor, rid, tid, expected_version):
        def change(row):
            self._editable(row)
            if tid not in {t["id"] for t in row["tracks"]}:
                raise FileNotFoundError(tid)
            row["tracks"] = [t for t in row["tracks"] if t["id"] != tid]
        return self.mutate(nid, scope, actor, self.PLANS, rid, expected_version, change)

    def duration_manifest(self, nid, scope, rid):
        plan = self.get(nid, scope, self.PLANS, rid)
        self._assert_plan(nid, scope, plan)
        return {"plan_id": rid, "plan_version": plan["version"], "timing_status": plan["timing_status"],
                "duration_ms": plan["duration_ms"], "precision": "MEASURED_SEGMENT_BOUNDARIES" if plan["timing_status"] == "MEASURED" else "PARTIAL_SEGMENT_BOUNDARIES" if plan["timing_status"] == "PARTIAL" else "UNMEASURED",
                "alignment_model": None, "word_alignment": "NOT_CONFIGURED",
                "segments": [{k: s.get(k) for k in ("id", "audio_asset_id", "start_ms", "end_ms", "duration_ms", "timing_status", "frame_timing")} for s in plan["segments"]]}

    def subtitles(self, nid, scope, rid):
        plan = self.get(nid, scope, self.PLANS, rid)
        self._assert_plan(nid, scope, plan)
        if plan["timing_status"] != "MEASURED":
            raise ValueError("AUDIO_MEASURED_TIMING_REQUIRED")
        return {"plan_id": rid, "plan_version": plan["version"], "precision": "SEGMENT_ONLY", "alignment_model": None,
                "phoneme_alignment": "NOT_CONFIGURED", "cues": [{"segment_id": s["id"], "text": s["text"],
                    "start_ms": s["start_ms"], "end_ms": s["end_ms"]} for s in plan["segments"]]}

    def review(self, nid, scope, actor, item_id, action, expected_version):
        collection = self.PLANS
        try:
            self.get(nid, scope, collection, item_id)
        except FileNotFoundError:
            collection = self.MIXES
        if collection == self.MIXES and action == "approve":
            return self._approve_mix(nid, scope, actor, item_id, expected_version)
        def change(row):
            if action == "reopen" and row["status"] in {"APPROVED", "REJECTED"}:
                if collection == self.MIXES and row.get("asset_id"):
                    raise ValueError("AUDIO_APPROVED_MIX_IMMUTABLE")
                row.update(status="PENDING_REVIEW")
                return
            if row["status"] != "PENDING_REVIEW" or action not in {"approve", "reject"}:
                raise ValueError("AUDIO_REVIEW_TRANSITION_INVALID")
            if action == "reject":
                row.update(status="REJECTED")
                return
            self._assert_plan(nid, scope, row)
            if any(s["attribution_status"] == "NEEDS_REVIEW" for s in row["segments"]):
                raise ValueError("AUDIO_ATTRIBUTION_NEEDS_REVIEW")
            if any(not s.get("profile_id") for s in row["segments"]):
                raise ValueError("AUDIO_VOICE_MAPPING_REQUIRED")
            row.update(status="APPROVED", approved_at=now(), approved_by=actor)
        result = self.mutate(nid, scope, actor, collection, item_id, expected_version, change)
        result.pop("content_base64", None)
        return result

    def _mix_plan(self, nid, scope, proposal):
        plan = self.get(nid, scope, self.PLANS, proposal["plan_id"])
        if plan["version"] != proposal["plan_version"] or plan["status"] != "APPROVED":
            raise StaleSourceError("AUDIO_MIX_PLAN_CHANGED")
        self._assert_plan(nid, scope, plan)
        return plan

    def _approve_mix(self, nid, scope, actor, item_id, expected_version):
        current = self.get(nid, scope, self.MIXES, item_id)
        check_version(current, expected_version)
        if current["status"] == "PENDING_REVIEW":
            def claim(row):
                self._mix_plan(nid, scope, row)
                row.update(status="APPROVING", promotion_token=str(uuid4()), promotion_started_at=now(), promotion_actor=actor)
            current = self.mutate(nid, scope, actor, self.MIXES, item_id, expected_version, claim)
        elif current["status"] != "APPROVING":
            raise ValueError("AUDIO_REVIEW_TRANSITION_INVALID")
        plan = self._mix_plan(nid, scope, current)
        content = base64.b64decode(current["content_base64"], validate=True)
        if hashlib.sha256(content).hexdigest() != current["content_sha256"]:
            raise ValueError("AUDIO_MIX_INTEGRITY_FAILED")
        measured = inspect_media(content, "audio")
        asset = self.assets.create(nid, f"r3-mix-{item_id}.{measured['extension']}", current["content_base64"],
            measured["media_type"], "audio", "r3-audio-mix:" + item_id, branch_id=scope.get("branch_id"),
            **self._mix_asset_options(nid, scope, plan, current))
        current = checkpoint_promotion_asset(self, nid, scope, actor, self.MIXES, current, asset)
        self.assets.update_metadata(asset["id"], {"source_job_id": item_id, "parameters": {
            "experimental_audio_lineage": {"plan_id": plan["id"], "plan_version": plan["version"],
                "sources": plan["sources"], "mixer_id": current["mixer_id"], "verification": current["verification"],
                **({"timeline": current["timeline"]} if "timeline" in current else {})}},
            "source_asset_ids": current["source_asset_ids"], "approved_at": current["promotion_started_at"]}, branch_id=scope.get("branch_id"))
        with self.store.transaction(nid, scope) as doc:
            row = doc["collections"][self.MIXES][item_id]
            if row.get("promotion_token") != current["promotion_token"]:
                raise ValueError("AUDIO_PROMOTION_CHANGED")
            if row["status"] == "APPROVED":
                return {k: copy.deepcopy(v) for k, v in row.items() if k != "content_base64"}
            check_version(row, current["version"])
            if row["status"] != "APPROVING":
                raise ValueError("AUDIO_PROMOTION_CHANGED")
            self._mix_plan(nid, scope, row)
            row.setdefault("history", []).append(snapshot(row))
            row.update(status="APPROVED", asset_id=asset["id"], approved_at=current["promotion_started_at"],
                approved_by=current["promotion_actor"], version=row["version"] + 1, updated_at=now(), updated_by=actor)
            return {k: copy.deepcopy(v) for k, v in row.items() if k != "content_base64"}

    def _mix_origin(self, nid, scope, plan, source_ids):
        return {}

    def _mix_asset_options(self, nid, scope, plan, proposal):
        return {}

    def mix(self, nid, scope, actor, rid, expected_version, check_authority=None):
        if self.mixer is None:
            raise ValueError("AUDIO_MIXER_NOT_CONFIGURED")
        if not self.mixer.local:
            raise ValueError("AUDIO_REMOTE_MIXER_NOT_AUTHORIZED")
        mixer = self.mixer
        mixer_id = mixer.adapter_id
        plan = self.get(nid, scope, self.PLANS, rid)
        check_version(plan, expected_version)
        self._assert_plan(nid, scope, plan)
        if plan["status"] != "APPROVED" or plan["timing_status"] != "MEASURED":
            raise ValueError("AUDIO_APPROVED_MEASURED_PLAN_REQUIRED")
        speech, tracks, source_ids = [], [], []
        for segment in plan["segments"]:
            asset, content = self._audio_asset(nid, scope, segment["audio_asset_id"])
            speech.append({"content": content, "start_ms": segment["start_ms"], "gain_db": 0})
            source_ids.append(asset["id"])
        for track in plan["tracks"]:
            if not track.get("asset_id") or track.get("start_ms") is None:
                raise ValueError("AUDIO_TRACK_SLOT_INCOMPLETE")
            asset, content = self._audio_asset(nid, scope, track["asset_id"])
            tracks.append({**track, "content": content})
            source_ids.append(asset["id"])
        if len(set(source_ids)) > 100:
            raise ValueError("AUDIO_MIX_SOURCE_LIMIT")
        if sum(len(item["content"]) for item in [*speech, *tracks]) > 64 * 1024 * 1024:
            raise ValueError("AUDIO_MIX_INPUT_TOO_LARGE")
        if scope.get("mode") == "collaboration" and check_authority is None:
            raise ValueError("AUDIO_MIX_AUTHORITY_REQUIRED")
        if check_authority:
            check_authority()
        current = self.get(nid, scope, self.PLANS, rid)
        if current["version"] != plan["version"]:
            raise StaleSourceError("AUDIO_MIX_PLAN_CHANGED")
        self._assert_plan(nid, scope, current)
        if self.mixer is not mixer or not mixer.local or mixer.adapter_id != mixer_id:
            raise StaleSourceError("AUDIO_MIXER_CHANGED")
        result = mixer.mix(MixerRequest(str(uuid4()), speech, tracks))
        if self.mixer is not mixer or not mixer.local or mixer.adapter_id != mixer_id:
            raise StaleSourceError("AUDIO_MIXER_CHANGED")
        if not isinstance(result, MixerResult) or result.verification not in {"MOCK_ONLY", "CONTRACT_VERIFIED"}:
            raise ValueError("AUDIO_MIX_RESULT_INVALID")
        if len(result.content) > self.assets.MAX_BYTES:
            raise ValueError("AUDIO_MIX_OUTPUT_TOO_LARGE")
        measured = inspect_media(result.content, "audio")
        if measured["media_type"] != result.media_type:
            raise ValueError("AUDIO_MIX_RESULT_TYPE_MISMATCH")
        if check_authority:
            check_authority()
        with self.store.transaction(nid, scope) as doc:
            current = doc["collections"][self.PLANS][rid]
            if current["version"] != plan["version"] or current["status"] != "APPROVED":
                raise StaleSourceError("AUDIO_MIX_PLAN_CHANGED")
            self._assert_plan(nid, scope, current)
            row = new_row(nid, scope, actor, {"plan_id": rid, "plan_version": plan["version"], "sources": plan["sources"],
                "source_asset_ids": list(dict.fromkeys(source_ids)), "status": "PENDING_REVIEW", "mixer_id": mixer_id,
                "content_base64": base64.b64encode(result.content).decode(), "content_sha256": hashlib.sha256(result.content).hexdigest(),
                "verification": result.verification, "media": measured, "asset_id": None,
                **self._mix_origin(nid, scope, plan, source_ids)})
            doc["collections"].setdefault(self.MIXES, {})[row["id"]] = row
            return {k: copy.deepcopy(v) for k, v in row.items() if k != "content_base64"}

    def list_review_items(self, nid, scope):
        plans = self.plans(nid, scope)
        mixes = self.list(nid, scope, self.MIXES)
        plan_map = {p["id"]: p for p in plans}
        for row in mixes:
            row.pop("content_base64", None)
            plan = plan_map.get(row["plan_id"])
            row["stale"] = not plan or plan["stale"] or plan["version"] != row["plan_version"] or plan["status"] != "APPROVED"
        return [{**row, "domain": "audiobook", "source": row.get("chapter_id", row.get("plan_id")),
            "target": {"plan_id": row.get("plan_id", row["id"])}, "preview": row.get("title", "Mixed audiobook candidate"),
            "risk": "ATTRIBUTION_AND_VOICE_REVIEW", "privacy_state": "LOCAL_ONLY", "batch_allowed": False,
            "allowed_actions": ["approve", "reject"] if row["status"] == "PENDING_REVIEW" else ["approve"] if row["status"] == "APPROVING" else ["reopen"] if row["status"] == "REJECTED" or (row["status"] == "APPROVED" and "segments" in row) else [],
            "recovery_required": row["status"] == "APPROVING",
            "recovery_state": "SOURCE_CHANGED_RECONCILIATION_REQUIRED" if row["status"] == "APPROVING" and row["stale"] else "RESUME_APPROVAL" if row["status"] == "APPROVING" else None,
            "promotion_asset_id": row.get("promotion_asset_id")} for row in [*plans, *mixes]]
