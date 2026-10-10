"""A12 bounded OTIO exchange receipts, not another editor/timeline authority.

Only the official native JSON serializer/parser is called, lazily. No adapters,
media URL reads, filesystem paths from input, rendering or runtime installation.
All timeline arithmetic is fractions; binary floats occur only at OTIO's API.
"""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import importlib.metadata
import json
import math
from fractions import Fraction
from pathlib import PurePosixPath
from typing import Literal
from urllib.parse import urlsplit
from pydantic import Field
from .common import DomainService, StaleSourceError, check_version
from .director import DirectorService
from .media import StrictModel

MAX_BYTES = 2 * 1024 * 1024
NS = "ai_novel_studio_exchange_v1"


def parser_status():
    try:
        installed = importlib.metadata.version("opentimelineio")
    except importlib.metadata.PackageNotFoundError:
        installed = None
    return {"available": installed == "0.18.1" and importlib.util.find_spec("opentimelineio") is not None, "installed_version": installed,
            "required_version": "0.18.1", "runtime_install": False, "target_applications": {"Resolve": "NOT_RUN", "Premiere": "NOT_RUN"}}


def _otio():
    try:
        import opentimelineio as otio
    except ImportError:
        raise ValueError("OTIO_PARSER_NOT_INSTALLED_INSTALL_OPTIONAL_EXTRA_OFFLINE") from None
    if otio.__version__ != "0.18.1":
        raise ValueError("OTIO_PARSER_VERSION_NOT_VERIFIED")
    return otio


def rational(value):
    value = value if isinstance(value, Fraction) else Fraction(str(value))
    return {"numerator": value.numerator, "denominator": value.denominator}


def fraction(value):
    if not isinstance(value, dict) or set(value) != {"numerator", "denominator"} or any(type(value[k]) is not int for k in value):
        raise ValueError("OTIO_INVALID_RATIONAL")
    if abs(value["numerator"]) > 10**15 or not 1 <= value["denominator"] <= 10**12:
        raise ValueError("OTIO_RATIONAL_LIMIT")
    return Fraction(value["numerator"], value["denominator"])


def seconds(time):
    return fraction(time["frames"]) / fraction(time["rate"])


def time_value(frames, rate=24):
    return {"frames": rational(frames), "rate": rational(rate)}


def _native_time(value):
    rate = Fraction(str(value.rate)).limit_denominator(1000000)
    frames = Fraction(str(value.value))
    if not 0 < rate <= 1000000 or abs(float(rate) - value.rate) > 1e-8 or abs(frames) > 10**12:
        raise ValueError("OTIO_TIME_OUTSIDE_SUPPORTED_RANGE")
    return time_value(frames, rate)


def _to_native(value):
    otio = _otio()
    rate, frames = fraction(value["rate"]), fraction(value["frames"])
    if not 0 < rate <= 1000000 or abs(frames) > 10**12:
        raise ValueError("OTIO_TIME_OUTSIDE_SUPPORTED_RANGE")
    return otio.opentime.RationalTime(float(frames), float(rate))


def _read_time(item, key, native):
    fallback = _native_time(native)
    metadata = item.metadata.get(NS, {}) if hasattr(item, "metadata") else {}
    if metadata and not hasattr(metadata, "get"):
        raise ValueError("OTIO_EXACT_TIME_METADATA_INVALID")
    try:
        exact = dict(metadata.get(key, {})) if metadata else {}
    except (TypeError, ValueError):
        raise ValueError("OTIO_EXACT_TIME_METADATA_INVALID") from None
    if exact:
        try:
            exact = {k: dict(v) for k, v in exact.items()}
            normalized = time_value(fraction(exact["frames"]), fraction(exact["rate"]))
            expected = _to_native(normalized)
            if expected.value != native.value or expected.rate != native.rate:
                raise ValueError("OTIO_EXACT_TIME_METADATA_MISMATCH")
            return normalized
        except (KeyError, TypeError, ZeroDivisionError):
            raise ValueError("OTIO_EXACT_TIME_METADATA_INVALID") from None
    return fallback


def _loss(report, path, code, severity="LOSS"):
    report.append({"path": path, "code": code, "severity": severity})


def _name(value, path, report):
    value = str(value)
    if len(value) > 240:
        _loss(report, path, 'NAME_TRUNCATED_TO_240_CHARACTERS')
    return value[:240]


def _extras(item, path, report):
    for effect in getattr(item, "effects", []):
        code = "SPEED_EFFECT_NOT_REPRESENTED_TIMING_UNVERIFIED" if "Time" in effect.schema_name() or effect.schema_name() == "FreezeFrame" else "EFFECT_NOT_REPRESENTED"
        _loss(report, path, code)
    if getattr(item, "markers", []):
        _loss(report, path, "MARKERS_NOT_REPRESENTED")
    extension = getattr(item, "metadata", {}).get(NS, {})
    supported = {"in_offset", "out_offset"} if getattr(item, "schema_name", lambda: "")() == "Transition" else {"start", "duration"} if getattr(item, "schema_name", lambda: "")() in {"Clip", "Gap"} else set()
    if extension and (not hasattr(extension, "keys") or set(extension.keys()) - supported):
        _loss(report, path, "UNKNOWN_EXCHANGE_METADATA_NOT_REPRESENTED")
    if any(key != NS for key in getattr(item, "metadata", {})):
        _loss(report, path, "APPLICATION_METADATA_MIX_SUBTITLES_NOT_REPRESENTED")


def _url(value):
    if not isinstance(value, str) or len(value) > 4096 or any(ord(c) < 32 for c in value):
        raise ValueError("OTIO_INVALID_MEDIA_REFERENCE")
    parsed = urlsplit(value)
    if parsed.scheme and parsed.scheme.lower() not in {"file", "http", "https"}:
        raise ValueError("OTIO_UNSUPPORTED_MEDIA_SCHEME")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("OTIO_CREDENTIAL_OR_QUERY_REFERENCE_REJECTED")
    return value  # Opaque reference, never opened/fetched by this module.


def _bounded_json(text):
    if not isinstance(text, str) or not 0 < len(text.encode("utf-8")) <= MAX_BYTES:
        raise ValueError("OTIO_FILE_SIZE_LIMIT_2_MIB")
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result: raise ValueError("OTIO_DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    try:
        raw = json.loads(text, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("OTIO_NONFINITE_JSON")))
    except (json.JSONDecodeError, RecursionError):
        raise ValueError("OTIO_INVALID_JSON") from None
    count = 0
    stack = [(raw, 0)]
    while stack:
        value, depth = stack.pop(); count += 1
        if depth > 32 or count > 40000:
            raise ValueError("OTIO_DOCUMENT_COMPLEXITY_LIMIT")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError('OTIO_NONFINITE_JSON')
        if isinstance(value, dict): stack.extend((v, depth + 1) for v in value.values())
        elif isinstance(value, list): stack.extend((v, depth + 1) for v in value)
    return raw


def read_otio(text):
    """Read supported subset and a bounded, explicit normalization loss report."""
    _bounded_json(text)
    otio = _otio()
    try:
        timeline = otio.core.deserialize_json_from_string(text)
    except Exception:
        raise ValueError("OTIO_OFFICIAL_PARSER_REJECTED_FILE") from None
    if not isinstance(timeline, otio.schema.Timeline):
        raise ValueError("OTIO_TIMELINE_ROOT_REQUIRED")
    report = []
    _extras(timeline, "timeline", report); _extras(timeline.tracks, "tracks", report)
    if not timeline.tracks.enabled:
        raise ValueError("OTIO_DISABLED_ROOT_NOT_SUPPORTED")
    if timeline.tracks.source_range is not None:
        raise ValueError("OTIO_ROOT_TRIM_NOT_SUPPORTED")
    doc = {"name": _name(timeline.name, "timeline.name", report), "tracks": [], "global_start_time": _native_time(timeline.global_start_time) if timeline.global_start_time is not None else None}
    if len(timeline.tracks) > 16:
        raise ValueError("OTIO_TRACK_LIMIT_16")
    total_items = 0
    for ti, track in enumerate(timeline.tracks):
        path = f"tracks[{ti}]"
        if not isinstance(track, otio.schema.Track) or track.source_range is not None or not track.enabled:
            raise ValueError("OTIO_TOP_LEVEL_TRACK_REQUIRED_WITHOUT_TRIM")
        if track.kind not in {"Video", "Audio"}:
            _loss(report, path, "SUBTITLE_OR_UNKNOWN_TRACK_NOT_REPRESENTED")
            continue
        _extras(track, path, report)
        result = {"name": _name(track.name, path + ".name", report), "kind": track.kind, "items": []}
        for ii, item in enumerate(track):
            total_items += 1
            if total_items > 2000: raise ValueError("OTIO_ITEM_LIMIT_2000")
            ip = f"{path}.items[{ii}]"; _extras(item, ip, report)
            if isinstance(item, otio.schema.Transition):
                if item.transition_type != "SMPTE_Dissolve":
                    _loss(report, ip, "TRANSITION_NOT_REPRESENTED_CUT_USED")
                    continue
                result["items"].append({"kind": "Transition", "name": _name(item.name, ip + ".name", report), "transition_type": "SMPTE_Dissolve",
                                        "in_offset": _read_time(item, "in_offset", item.in_offset), "out_offset": _read_time(item, "out_offset", item.out_offset)})
                continue
            try:
                span = item.trimmed_range()
            except Exception:
                raise ValueError("OTIO_EXPLICIT_RESOLVABLE_DURATION_REQUIRED") from None
            start, duration = _read_time(item, "start", span.start_time), _read_time(item, "duration", span.duration)
            if seconds(duration) <= 0 or seconds(duration) > 86400 or seconds(start) < 0:
                raise ValueError("OTIO_CLIP_TIME_LIMIT")
            row = {"kind": "Clip" if isinstance(item, otio.schema.Clip) else "Gap", "name": _name(item.name, ip + ".name", report), "start": start, "duration": duration}
            if isinstance(item, otio.schema.Clip):
                ref = item.media_reference
                _extras(ref, ip + ".media_reference", report)
                if isinstance(ref, otio.schema.ExternalReference):
                    row["target_url"] = _url(ref.target_url)
                    row["media_state"] = "EXTERNAL_REFERENCE_NOT_OPENED"
                    if ref.available_range is not None:
                        row["available_range"] = {"start": _native_time(ref.available_range.start_time), "duration": _native_time(ref.available_range.duration)}
                elif isinstance(ref, otio.schema.MissingReference):
                    row["target_url"] = None; row["media_state"] = "MISSING"
                    _loss(report, ip, "MISSING_MEDIA", "WARNING")
                else:
                    row["target_url"] = None; row["media_state"] = "UNSUPPORTED_REFERENCE"
                    _loss(report, ip, "MEDIA_REFERENCE_TYPE_NOT_REPRESENTED")
                if len(item.media_references()) > 1:
                    _loss(report, ip, "ALTERNATE_MEDIA_REFERENCES_NOT_REPRESENTED")
            elif not isinstance(item, otio.schema.Gap):
                _loss(report, ip, "NESTED_COMPOSITION_REPLACED_WITH_GAP")
            if hasattr(item, "enabled") and not item.enabled:
                row = {**row, "kind": "Gap"}; row.pop("target_url", None); row.pop("media_state", None); row.pop("available_range", None)
                _loss(report, ip, "DISABLED_ITEM_REPLACED_WITH_GAP")
            result["items"].append(row)
        doc["tracks"].append(result)
    if not doc["tracks"]:
        raise ValueError("OTIO_NO_SUPPORTED_TRACKS")
    validate_document(doc)
    return doc, report


def validate_document(doc):
    for track in doc["tracks"]:
        items = track["items"]
        for index, row in enumerate(items):
            if row["kind"] != "Transition": continue
            if index == 0 or index == len(items) - 1 or items[index - 1]["kind"] != "Clip" or items[index + 1]["kind"] != "Clip":
                raise ValueError("OTIO_DISSOLVE_REQUIRES_ADJACENT_CLIPS")
            incoming, outgoing = seconds(row["in_offset"]), seconds(row["out_offset"])
            if min(incoming, outgoing) < 0 or incoming + outgoing <= 0:
                raise ValueError("OTIO_INVALID_TRANSITION_OFFSETS")
            if incoming > seconds(items[index - 1]["duration"]) or outgoing > seconds(items[index + 1]["duration"]):
                raise ValueError("OTIO_TRANSITION_EXCEEDS_NEIGHBOR_DURATION")
        if sum((seconds(row["duration"]) for row in items if row["kind"] != "Transition"), Fraction()) > 86400:
            raise ValueError("OTIO_TRACK_DURATION_LIMIT_24_HOURS")


def write_otio(doc):
    """Produce a genuinely parsed native OTIO file; never use optional adapters."""
    validate_document(doc); otio = _otio()
    timeline = otio.schema.Timeline(name=doc["name"])
    if doc.get("global_start_time") is not None:
        timeline.global_start_time = _to_native(doc["global_start_time"])
    for row in doc["tracks"]:
        track = otio.schema.Track(name=row["name"], kind=row["kind"])
        for item in row["items"]:
            if item["kind"] == "Transition":
                native = otio.schema.Transition(name=item["name"], transition_type="SMPTE_Dissolve",
                    in_offset=_to_native(item["in_offset"]), out_offset=_to_native(item["out_offset"]))
                exact = {k: item[k] for k in ("in_offset", "out_offset")}
            else:
                span = otio.opentime.TimeRange(_to_native(item["start"]), _to_native(item["duration"]))
                if item["kind"] == "Clip":
                    ref = otio.schema.ExternalReference(target_url=_url(item["target_url"])) if item.get("target_url") else otio.schema.MissingReference()
                    if item.get("available_range") and item.get("target_url"):
                        ref.available_range = otio.opentime.TimeRange(_to_native(item["available_range"]["start"]), _to_native(item["available_range"]["duration"]))
                    native = otio.schema.Clip(name=item["name"], source_range=span, media_reference=ref)
                else:
                    native = otio.schema.Gap(name=item["name"], source_range=span)
                exact = {k: item[k] for k in ("start", "duration")}
            native.metadata[NS] = exact
            track.append(native)
        timeline.tracks.append(track)
    result = otio.core.serialize_json_to_string(timeline).encode("utf-8")
    if len(result) > MAX_BYTES:
        raise ValueError("OTIO_OUTPUT_SIZE_LIMIT")
    # The consumer re-parses bytes with the official parser. Verify media paths
    # and exact rational timings after normalization, not just valid JSON.
    reparsed, _ = read_otio(result.decode("utf-8"))
    if semantic_document(reparsed) != semantic_document(doc):
        raise ValueError("OTIO_ROUND_TRIP_SEMANTICS_MISMATCH")
    return result


def semantic_document(doc):
    result = copy.deepcopy(doc)
    for track in result["tracks"]:
        for row in track["items"]:
            row.pop("media_state", None)
    return result


def summary(doc):
    tracks = []
    for track in doc["tracks"]:
        cursor = Fraction(); cuts = []
        for item in track["items"]:
            if item["kind"] == "Transition": continue
            cuts.append({"name": item["name"], "kind": item["kind"], "start_seconds": rational(cursor), "duration_seconds": rational(seconds(item["duration"])), "source_in_seconds": rational(seconds(item["start"])), "source_out_seconds": rational(seconds(item["start"]) + seconds(item["duration"]))})
            cursor += seconds(item["duration"])
        tracks.append({"name": track["name"], "kind": track["kind"], "duration_seconds": rational(cursor), "cuts": cuts})
    return {"name": doc["name"], "tracks": tracks, "duration_semantics": "EXACT_RATIONAL_HALF_OPEN_SOURCE_RANGES", "renders_media": False, "audio_video_relation": "INDEPENDENT_TRACK_TIMING_ONLY_NO_LINKED_CLIP_CONTRACT"}


class ImportOTIOIn(StrictModel):
    filename: str = Field(min_length=1, max_length=240)
    content: str = Field(min_length=1, max_length=MAX_BYTES)


class ShotMedia(StrictModel):
    shot_id: str = Field(min_length=1, max_length=240)
    asset_id: str | None = Field(default=None, min_length=1, max_length=240)


class ScreenplayOTIOIn(StrictModel):
    screenplay_id: str = Field(min_length=1, max_length=240)
    expected_screenplay_version: int = Field(ge=1, strict=True)
    rate_numerator: int = Field(default=24, ge=1, le=120000, strict=True)
    rate_denominator: int = Field(default=1, ge=1, le=1001, strict=True)
    shots: list[ShotMedia] = Field(min_length=1, max_length=200)


class TimelineExchangeService(DomainService):
    RECORDS = "timeline_exchange_receipts_v2"

    def __init__(self, store, novels, chapters, screenplays, assets, *, lineage=None):
        super().__init__(store, novels, chapters)
        self.screenplays, self.assets, self.lineage = screenplays, assets, lineage

    def _director(self):
        return DirectorService(self.store, self.novels, self.chapters, self.screenplays)

    def _asset(self, nid, scope, aid):
        row = self.assets.get(aid, branch_id=scope.get("branch_id"))
        if row.get("novel_id") != nid or row.get("branch_id") != scope.get("branch_id"):
            raise FileNotFoundError(aid)
        if self.lineage is not None and self.lineage.asset(nid, scope, aid)["stale"]:
            raise StaleSourceError("OTIO_MEDIA_LINEAGE_NOT_CURRENT")
        if not row["media_type"].startswith(("video/", "audio/", "image/")):
            raise ValueError("OTIO_AUDIO_VISUAL_MEDIA_REQUIRED")
        content = self.assets.content(aid, branch_id=scope.get("branch_id"))
        if hashlib.sha256(content).hexdigest() != row["sha256"]:
            raise StaleSourceError("OTIO_MEDIA_CONTENT_CHANGED")
        return row

    def catalog(self, nid, scope, actor):
        catalog = self._director().catalog(nid, scope, actor)
        available = []
        for row in self.assets.list(nid, branch_id=scope.get("branch_id")):
            if row.get("branch_id") != scope.get("branch_id"): continue
            try: self._asset(nid, scope, row["id"])
            except (FileNotFoundError, ValueError): continue
            available.append({"id": row["id"], "filename": row["filename"], "media_type": row["media_type"], "version": row["version"]})
        return {"screenplays": [{**row, "shots": [{k: v for k, v in shot.items() if k != "director"} for shot in row["shots"]], "checks": []} for row in catalog["screenplays"]],
                "assets": available, "parser": parser_status(), "formats": ["OTIO_NATIVE_JSON_SUBSET_V1"],
                "limitations": ["FCPXML_NOT_IMPLEMENTED", "CMX_EDL_NOT_IMPLEMENTED", "NO_MEDIA_PACKAGING", "NO_RENDERING", "TARGET_APPLICATIONS_NOT_RUN"]}

    def _assert_current(self, nid, scope, row):
        if row.get("screenplay_id"):
            screenplay = self._director().screenplay(nid, scope, row["screenplay_id"])
            if screenplay["edit_version"] != row["screenplay_version"] or self._director().evidence(nid, scope, screenplay) != row["source_evidence"]:
                raise StaleSourceError("OTIO_SCREENPLAY_SOURCE_CHANGED")
        for aid, expected in row.get("asset_sources", {}).items():
            asset = self._asset(nid, scope, aid)
            if expected != {"version": asset["version"], "sha256": asset["sha256"]}:
                raise StaleSourceError("OTIO_MEDIA_SOURCE_CHANGED")

    def _view(self, nid, scope, row):
        safe = {k: row[k] for k in ("id", "version", "status", "origin", "created_at")}
        try:
            self._assert_current(nid, scope, row)
        except FileNotFoundError:
            return None
        except (StaleSourceError, KeyError, ValueError):
            return {**safe, "stale": True, "privacy_level": "LOCAL_ONLY"}
        return {**safe, "stale": False, "privacy_level": "LOCAL_ONLY", "summary": summary(row["document"]), "loss_report": row["loss_report"],
                "parser_version": "0.18.1", "filename": f"timeline-{row['id']}.otio", "target_applications": {"Resolve": "NOT_RUN", "Premiere": "NOT_RUN"},
                "media": [{"name": item["name"], "state": item.get("media_state", "MISSING"), "target_url": item.get("target_url")}
                          for track in row["document"]["tracks"] for item in track["items"] if item["kind"] == "Clip"]}

    def records(self, nid, scope, actor):
        return {"items": [view for row in self.list(nid, scope, self.RECORDS) if row["created_by"] == actor
                          if (view := self._view(nid, scope, row)) is not None], "parser": parser_status()}

    def import_file(self, nid, scope, actor, value, guard=lambda: None):
        body = ImportOTIOIn.model_validate(value)
        if not body.filename.lower().endswith(".otio") or "/" in body.filename or "\\" in body.filename:
            raise ValueError("OTIO_BASENAME_EXTENSION_REQUIRED")
        document, report = read_otio(body.content)
        output = write_otio(document)
        payload = {"origin": "IMPORTED_EXCHANGE_COPY", "document": document, "loss_report": report,
                   "input_sha256": hashlib.sha256(body.content.encode()).hexdigest(), "output_sha256": hashlib.sha256(output).hexdigest(),
                   "external_project_modified": False, "asset_sources": {}}
        guard()
        saved = self.create(nid, scope, actor, self.RECORDS, payload)
        return self._view(nid, scope, saved)

    def from_screenplay(self, nid, scope, actor, value, guard=lambda: None):
        body = ScreenplayOTIOIn.model_validate(value)
        screenplay = self._director().screenplay(nid, scope, body.screenplay_id)
        if screenplay["edit_version"] != body.expected_screenplay_version:
            raise StaleSourceError("OTIO_SCREENPLAY_SOURCE_CHANGED")
        ids = [row.shot_id for row in body.shots]
        shots = {row["id"]: row for row in screenplay.get("shots", [])}
        if len(set(ids)) != len(ids) or set(ids) - shots.keys():
            raise ValueError("OTIO_UNKNOWN_OR_DUPLICATE_SHOT")
        rate = Fraction(body.rate_numerator, body.rate_denominator)
        if not 1 <= rate <= 240:
            raise ValueError("OTIO_FRAME_RATE_LIMIT_1_TO_240")
        items, assets, report = [], {}, []
        transitions = {(row["from_shot_id"], row["to_shot_id"]): row for row in screenplay.get("transitions", [])}
        for index, binding in enumerate(body.shots):
            shot = shots[binding.shot_id]
            for fields, code in ((("shot_size", "camera_angle", "camera_motion", "director"), "CAMERA_GRAMMAR_NOT_REPRESENTED"),
                                 (("dialogue",), "DIALOGUE_SUBTITLES_NOT_REPRESENTED"),
                                 (("sound_effect",), "SOUND_DESIGN_NOT_RENDERED_OR_LINKED"),
                                 (("action", "subject_position"), "SHOT_DESCRIPTION_NOT_REPRESENTED")):
                if any(shot.get(key) for key in fields):
                    _loss(report, f"shots[{index}]", code)
            duration = Fraction(str(shot.get("duration_seconds", 0)))
            if not 0 < duration <= 600:
                raise ValueError("OTIO_SHOT_DURATION_REQUIRED")
            item = {"kind": "Clip", "name": f"Shot {shot.get('number', index + 1)}", "start": time_value(0, rate), "duration": time_value(duration * rate, rate),
                    "target_url": None, "media_state": "MISSING"}
            if binding.asset_id:
                asset = self._asset(nid, scope, binding.asset_id)
                if not asset['media_type'].startswith(('video/', 'image/')):
                    raise ValueError('OTIO_VIDEO_TRACK_VISUAL_MEDIA_REQUIRED')
                suffix = PurePosixPath(asset["filename"]).suffix.lower()
                suffix = suffix if suffix in {".mp4", ".mov", ".mkv", ".wav", ".mp3", ".png", ".jpg", ".webp"} else ".media"
                item.update(target_url=f"media/{asset['sha256']}{suffix}", media_state="REFERENCE_ONLY_NOT_PACKAGED")
                assets[asset["id"]] = {"version": asset["version"], "sha256": asset["sha256"]}
                _loss(report, f"shots[{index}]", "MEDIA_REFERENCE_ONLY_NOT_PACKAGED", "WARNING")
            else:
                _loss(report, f"shots[{index}]", "MISSING_MEDIA", "WARNING")
            if index:
                transition = transitions.get((ids[index - 1], binding.shot_id))
                if transition and transition.get("type") not in {None, "CUT"}:
                    if transition.get("type") == "DISSOLVE" and Fraction(str(transition.get("duration_seconds", 0))) > 0:
                        half = Fraction(str(transition["duration_seconds"])) / 2
                        items.append({"kind": "Transition", "name": "Dissolve", "transition_type": "SMPTE_Dissolve",
                                      "in_offset": time_value(half * rate, rate), "out_offset": time_value(half * rate, rate)})
                        _loss(report, f"shots[{index}]", "TRANSITION_MEDIA_HANDLES_NOT_VERIFIED", "WARNING")
                    else:
                        _loss(report, f"shots[{index}]", "TRANSITION_NOT_REPRESENTED_CUT_USED")
            items.append(item)
        document = {"name": screenplay["title"], "global_start_time": None, "tracks": [{"name": "Screenplay shots", "kind": "Video", "items": items}]}
        output = write_otio(document)
        payload = {"origin": "SCREENPLAY_EXCHANGE_SNAPSHOT", "document": document, "loss_report": report,
                   "screenplay_id": screenplay["id"], "screenplay_version": screenplay["edit_version"],
                   "source_evidence": self._director().evidence(nid, scope, screenplay), "asset_sources": assets,
                   "output_sha256": hashlib.sha256(output).hexdigest(), "external_project_modified": False}
        guard(); self._assert_current(nid, scope, payload)
        saved = self.create(nid, scope, actor, self.RECORDS, payload)
        return self._view(nid, scope, saved)

    def download(self, nid, scope, actor, rid, expected_version, acknowledge_losses, guard=lambda: None):
        row = self.get(nid, scope, self.RECORDS, rid)
        if row["created_by"] != actor or self._view(nid, scope, row) is None:
            raise FileNotFoundError(rid)
        check_version(row, expected_version); self._assert_current(nid, scope, row)
        if row["loss_report"] and not acknowledge_losses:
            raise ValueError("OTIO_REVIEW_LOSS_REPORT_REQUIRED")
        result = write_otio(row["document"])
        if hashlib.sha256(result).hexdigest() != row["output_sha256"]:
            raise ValueError("OTIO_STORED_OUTPUT_DIGEST_MISMATCH")
        guard(); self._assert_current(nid, scope, row)
        return result, f"timeline-{row['id']}.otio"
