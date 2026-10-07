"""B04: versioned captions bound to existing measured media and R3 speakers.

All times are integer ticks at a rational rate. Manual timings are explicitly
manual. Optional trusted processing adapters add reviewed ASR/alignment/burn-in
contracts; no real-model, phoneme, lip-sync or rendering quality claim.
"""
from __future__ import annotations
import array
import copy
from fractions import Fraction
import io
import re
import sys
import wave
from uuid import uuid4
from typing import Literal
from pydantic import Field, model_validator
from .common import DomainService, StaleSourceError, check_version
from .flags import require_flag
from .media import StrictModel, digest
from ..media_files import inspect_media
from .subtitle_processing import SubtitleProcessingMixin

SUBTITLE_FLAG = "subtitle_timeline_v2"


class Timebase(StrictModel):
    numerator: int = Field(default=1000, ge=1, le=192000)
    denominator: int = Field(default=1, ge=1, le=1001)


class Cue(StrictModel):
    id: str = Field(min_length=1, max_length=240)
    start_tick: int = Field(ge=0, le=2**53 - 1)
    end_tick: int = Field(ge=1, le=2**53 - 1)
    text: str = Field(min_length=1, max_length=10000)
    segment_id: str | None = Field(default=None, max_length=240)
    overlap_reason: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def valid(self):
        if self.end_tick <= self.start_tick: raise ValueError("CAPTION_REVERSED_TIME")
        if not self.text.strip() or re.search(r"[<>\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", self.text) or re.search(r"\n\s*\n", self.text):
            raise ValueError("CAPTION_PLAIN_NONEMPTY_TEXT_REQUIRED")
        return self


class CaptionCreateIn(StrictModel):
    asset_id: str = Field(min_length=1, max_length=240)
    title: str = Field(default="字幕", min_length=1, max_length=240)
    plan_id: str | None = Field(default=None, max_length=240)
    expected_plan_version: int | None = Field(default=None, ge=1)
    timebase: Timebase = Field(default_factory=Timebase)
    cues: list[Cue] = Field(default_factory=list, max_length=2000)
    language: str = Field(default="zh", min_length=1, max_length=40)


class CaptionUpdateIn(StrictModel):
    expected_version: int = Field(ge=1)
    cues: list[Cue] = Field(max_length=2000)


class CaptionSplitIn(StrictModel):
    expected_version: int = Field(ge=1)
    split_tick: int = Field(ge=1)
    left_text: str = Field(min_length=1, max_length=10000)
    right_text: str = Field(min_length=1, max_length=10000)


class CaptionMergeIn(StrictModel):
    expected_version: int = Field(ge=1)
    next_cue_id: str = Field(min_length=1, max_length=240)


def rational(value):
    return {"numerator": value.numerator, "denominator": value.denominator}


def cue_seconds(tick, base):
    return Fraction(tick * base["denominator"], base["numerator"])


def stamp(milliseconds, vtt):
    hours, rest = divmod(milliseconds, 3600000); minutes, rest = divmod(rest, 60000); seconds, millis = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{'.' if vtt else ','}{millis:03d}"


def read_captions(text, format):
    """Strict read-back of our documented SRT/WebVTT subset (no styling)."""
    if format not in {"srt", "vtt"}: raise ValueError("CAPTION_FORMAT_INVALID")
    if format == "vtt":
        if not text.startswith("WEBVTT\n\n"): raise ValueError("CAPTION_VTT_HEADER")
        text = text[8:]
    rows = []
    for block in text.strip().split("\n\n") if text.strip() else []:
        lines = block.splitlines()
        if len(lines) < 3 or not lines[0].isdigit(): raise ValueError("CAPTION_PARSE_BLOCK")
        match = re.fullmatch(r"(\d{2,}):(\d{2}):(\d{2})[,.](\d{3}) --> (\d{2,}):(\d{2}):(\d{2})[,.](\d{3})", lines[1])
        if not match: raise ValueError("CAPTION_PARSE_TIMING")
        values = list(map(int, match.groups()))
        start = ((values[0]*60 + values[1])*60 + values[2])*1000 + values[3]
        end = ((values[4]*60 + values[5])*60 + values[6])*1000 + values[7]
        if end <= start: raise ValueError("CAPTION_EXPORT_MILLISECOND_RESOLUTION")
        rows.append({"start_ms": start, "end_ms": end, "text": "\n".join(lines[2:])})
    return rows


def render_captions(row, format):
    vtt = format == "vtt"
    if format not in {"srt", "vtt"}: raise ValueError("CAPTION_FORMAT_INVALID")
    blocks = []; expected = []
    for index, cue in enumerate(row["cues"], 1):
        start = int(cue_seconds(cue["start_tick"], row["timebase"]) * 1000)
        end = int(cue_seconds(cue["end_tick"], row["timebase"]) * 1000)
        if end <= start: raise ValueError("CAPTION_EXPORT_MILLISECOND_RESOLUTION")
        speaker = row.get("speakers", {}).get(cue.get("segment_id"), {}).get("name")
        text = f"[{speaker}] {cue['text']}" if speaker else cue["text"]
        blocks.append(f"{index}\n{stamp(start,vtt)} --> {stamp(end,vtt)}\n{text}")
        expected.append({"start_ms": start, "end_ms": end, "text": text})
    output = ("WEBVTT\n\n" if vtt else "") + "\n\n".join(blocks) + "\n"
    if read_captions(output, format) != expected: raise ValueError("CAPTION_ROUND_TRIP_FAILED")
    return output.encode("utf-8")


class SubtitleTimelineService(SubtitleProcessingMixin, DomainService):
    COLLECTION = "subtitle_timeline_v2"

    def __init__(self, store, novels, chapters, audiobook, assets, processing_adapters=()):
        super().__init__(store, novels, chapters)
        self.audiobook, self.assets = audiobook, assets
        self._initialize_processing(processing_adapters)

    def media(self, nid, scope, aid, waveform=False):
        asset = self.assets.get(aid, branch_id=scope.get("branch_id"))
        if asset.get("novel_id") != nid or asset.get("branch_id") != scope.get("branch_id") or asset.get("kind") not in {"audio", "video"}:
            raise FileNotFoundError(aid)
        content = self.assets.content(aid, branch_id=scope.get("branch_id"))
        info = inspect_media(content, asset["kind"])
        if not info.get("duration_ms"): raise ValueError("CAPTION_MEASURED_DURATION_REQUIRED")
        duration = Fraction(str(info["duration_ms"])) / 1000
        metadata = {"duration_seconds": rational(duration), "timing_origin": "MEASURED_MEDIA", "waveform": {"status": "UNAVAILABLE"}}
        if asset["kind"] == "audio":
            try:
                with wave.open(io.BytesIO(content), "rb") as wav:
                    frames, rate, channels, width = wav.getnframes(), wav.getframerate(), wav.getnchannels(), wav.getsampwidth()
                    duration = Fraction(frames, rate)
                    metadata.update(duration_seconds=rational(duration), frame_count=frames, sample_rate=rate, channels=channels)
                    if waveform and width == 2 and wav.getcomptype() == "NONE":
                        samples = array.array("h", wav.readframes(frames))
                        if sys.byteorder != "little": samples.byteswap()
                        stride = max(1, (frames + 511) // 512)
                        peaks = [max((abs(v) for v in samples[i*channels:min(frames,i+stride)*channels]), default=0) / 32768 for i in range(0, frames, stride)]
                        metadata["waveform"] = {"status": "MEASURED_PCM16_PEAKS", "samples_per_bucket": stride, "sample_rate": rate, "peaks": peaks}
            except (wave.Error, EOFError):
                pass
        return asset, metadata

    def _snapshot(self, nid, scope, actor, plan_id, cues):
        if not plan_id:
            if any(cue.get("segment_id") for cue in cues): raise ValueError("CAPTION_SPEAKER_PLAN_REQUIRED")
            return {}, {}, {}
        plan = self.audiobook.owned_plan(nid, scope, actor, plan_id)
        segments = {s["id"]: s for s in plan["segments"]}
        characters = {c["id"]: c.get("name", c["id"]) for c in self.audiobook._characters(nid, scope)}
        characters["__narrator__"] = "旁白"
        snapshots, speakers = {"_segment_order": digest([s["id"] for s in plan["segments"]])}, {}
        for cue in cues:
            sid = cue.get("segment_id")
            if not sid: continue
            if sid not in segments: raise FileNotFoundError(sid)
            segment = segments[sid]
            snapshots[sid] = digest({"direction": self.audiobook.segment_fingerprint(segment),
                "audio_asset_id": segment.get("audio_asset_id"), "audio_source": segment.get("audio_source"),
                "start_ms": segment.get("start_ms"), "end_ms": segment.get("end_ms")})
            name = characters.get(segment.get("character_id"), "未分配")
            if re.search(r"[<>\x00-\x1f\x7f]", name): raise ValueError("CAPTION_SPEAKER_LABEL_UNSAFE")
            speakers[sid] = {"character_id": segment.get("character_id"), "name": name, "attribution_status": segment["attribution_status"]}
        return snapshots, speakers, plan["sources"]

    def _validate(self, row):
        duration = Fraction(**row["media"]["duration_seconds"])
        warnings, previous_start, previous_end = [], -1, -1
        seen = set()
        for raw in row["cues"]:
            cue = Cue.model_validate(raw)
            if cue.id in seen: raise ValueError("CAPTION_DUPLICATE_ID")
            seen.add(cue.id)
            if cue.start_tick < previous_start: raise ValueError("CAPTION_ORDER_INVALID")
            if cue_seconds(cue.end_tick, row["timebase"]) > duration: raise ValueError("CAPTION_OUT_OF_MEDIA_RANGE")
            if cue.start_tick < previous_end and not cue.overlap_reason.strip(): raise ValueError("CAPTION_OVERLAP_REQUIRES_REASON")
            seconds = cue_seconds(cue.end_tick - cue.start_tick, row["timebase"])
            if len(cue.text.replace("\n", "")) / seconds > 21: warnings.append({"cue_id": cue.id, "code": "READING_SPEED_HEURISTIC", "boundary": "Uncalibrated multilingual characters/second hint"})
            if any(len(line) > 42 for line in cue.text.splitlines()): warnings.append({"cue_id": cue.id, "code": "LONG_LINE_HEURISTIC"})
            previous_start, previous_end = cue.start_tick, max(previous_end, cue.end_tick)
        return warnings

    def _current(self, nid, scope, actor, rid):
        require_flag(SUBTITLE_FLAG)
        row = self.get(nid, scope, self.COLLECTION, rid)
        if row["created_by"] != actor: raise FileNotFoundError(rid)
        asset, _ = self.media(nid, scope, row["asset_id"])
        if {"version": asset["version"], "digest": asset["sha256"]} != row["asset_snapshot"]:
            raise StaleSourceError("CAPTION_MEDIA_CHANGED")
        snapshots, speakers, sources = self._snapshot(nid, scope, actor, row.get("plan_id"), row["cues"])
        if snapshots != row["segment_snapshots"] or sources != row["sources"] or speakers != row["speakers"]:
            raise StaleSourceError("CAPTION_SPEAKER_SOURCE_CHANGED")
        self.assert_sources(nid, row["sources"], scope)
        return row

    def catalog(self, nid, scope, actor):
        require_flag(SUBTITLE_FLAG)
        assets = []
        for a in self.assets.list(nid, branch_id=scope.get("branch_id")):
            if a.get("branch_id") == scope.get("branch_id") and a.get("kind") in {"audio", "video"}:
                assets.append({k: a.get(k) for k in ("id", "filename", "kind", "version")})
        return {"assets": assets, "plans": self.audiobook.catalog(nid, scope, actor)["plans"], "alignment": "NOT_CONFIGURED", "burn_in": "NOT_CONFIGURED"}

    def records(self, nid, scope, actor):
        require_flag(SUBTITLE_FLAG); result = []
        for row in self.list(nid, scope, self.COLLECTION):
            if row["created_by"] != actor: continue
            try:
                self._current(nid, scope, actor, row["id"])
                row["stale"] = False
            except FileNotFoundError:
                continue
            except StaleSourceError:
                row = {k: row[k] for k in ("id", "version", "status", "created_at")}
                row["stale"] = True
            result.append(row)
        return {"items": result}

    def create_track(self, nid, scope, actor, body):
        require_flag(SUBTITLE_FLAG); data = CaptionCreateIn.model_validate(body)
        asset, media = self.media(nid, scope, data.asset_id, waveform=True)
        if data.plan_id:
            plan = self.audiobook.owned_plan(nid, scope, actor, data.plan_id)
            check_version(plan, data.expected_plan_version)
        cues = [c.model_dump() for c in data.cues]
        snapshots, speakers, sources = self._snapshot(nid, scope, actor, data.plan_id, cues)
        row = {**data.model_dump(exclude={"expected_plan_version"}), "cues": cues,
            "asset_snapshot": {"version": asset["version"], "digest": asset["sha256"]}, "media": media,
            "segment_snapshots": snapshots, "speakers": speakers, "sources": sources, "privacy_level": "LOCAL_ONLY",
            "timing_origin": "MANUAL", "alignment_model": None, "status": "DRAFT", "target_software_verification": "NOT_RUN"}
        row["warnings"] = self._validate(row)
        return self.create(nid, scope, actor, self.COLLECTION, row)

    def update(self, nid, scope, actor, rid, body):
        require_flag(SUBTITLE_FLAG); data = CaptionUpdateIn.model_validate(body)
        self._current(nid, scope, actor, rid)
        def change(row):
            self._current(nid, scope, actor, rid)
            row["cues"] = [c.model_dump() for c in data.cues]
            row["segment_snapshots"], row["speakers"], row["sources"] = self._snapshot(nid, scope, actor, row.get("plan_id"), row["cues"])
            row["warnings"] = self._validate(row)
            row["status"] = "DRAFT"
            row["timing_origin"] = "MANUAL"
            row["alignment_model"] = None
            row["processing_task_id"] = None
        return self.mutate(nid, scope, actor, self.COLLECTION, rid, data.expected_version, change)

    def split(self, nid, scope, actor, rid, cid, body):
        data = CaptionSplitIn.model_validate(body); row = self._current(nid, scope, actor, rid)
        check_version(row, data.expected_version)
        cues = copy.deepcopy(row["cues"]); index = next((i for i,c in enumerate(cues) if c["id"] == cid), None)
        if index is None: raise FileNotFoundError(cid)
        cue = cues[index]
        if not cue["start_tick"] < data.split_tick < cue["end_tick"]: raise ValueError("CAPTION_SPLIT_OUTSIDE_CUE")
        cues[index:index+1] = [{**cue, "end_tick": data.split_tick, "text": data.left_text}, {**cue, "id": str(uuid4()), "start_tick": data.split_tick, "text": data.right_text, "overlap_reason": ""}]
        return self.update(nid, scope, actor, rid, {"expected_version": row["version"], "cues": cues})

    def merge(self, nid, scope, actor, rid, cid, body):
        data = CaptionMergeIn.model_validate(body); row = self._current(nid, scope, actor, rid)
        check_version(row, data.expected_version)
        cues = copy.deepcopy(row["cues"]); index = next((i for i,c in enumerate(cues) if c["id"] == cid), None)
        if index is None or index + 1 >= len(cues) or cues[index+1]["id"] != data.next_cue_id: raise ValueError("CAPTION_MERGE_ADJACENT_REQUIRED")
        left, right = cues[index:index+2]
        if left.get("segment_id") != right.get("segment_id"): raise ValueError("CAPTION_MERGE_SPEAKER_MISMATCH")
        cues[index:index+2] = [{**left, "end_tick": max(left["end_tick"],right["end_tick"]), "text": left["text"] + "\n" + right["text"]}]
        return self.update(nid, scope, actor, rid, {"expected_version": row["version"], "cues": cues})

    def download(self, nid, scope, actor, rid, version, format, reauthorize=None):
        row = self._current(nid, scope, actor, rid); check_version(row, version)
        if not row["cues"]: raise ValueError("CAPTION_EMPTY_TRACK")
        self._validate(row)
        output = render_captions(row, format)
        if reauthorize: reauthorize()
        current = self._current(nid, scope, actor, rid); check_version(current, version)
        return output
