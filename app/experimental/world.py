"""Reviewed world/character facts and deterministic, source-fenced continuity.

Canon here is an opt-in, branch-owned semantic collection. Nothing writes legacy
Canon, characters or manuscript. Rule findings are evidence-based examples, not
an assertion of model-level semantic understanding.
"""
from __future__ import annotations

from copy import deepcopy
import math
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from .common import DomainService, StaleSourceError, new_row, change_row
from .planning import StrictModel, collection, require_row, digest, entity_sources, scoped_sources
from ..services.v1_capability_service import CapabilityVersionConflict


class TemporalRelation(StrictModel):
    event_id: str = Field(min_length=1, max_length=160)
    relation: Literal["BEFORE", "AFTER", "SIMULTANEOUS", "CAUSES"]


class HistoryData(StrictModel):
    time: int
    end_time: int | None = None
    calendar: str = Field(default="story", min_length=1, max_length=80)
    description: str = Field(default="", max_length=12000)
    character_ids: list[str] = Field(default_factory=list, max_length=100)
    location_ids: list[str] = Field(default_factory=list, max_length=100)
    relations: list[TemporalRelation] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def valid_interval(self):
        if self.end_time is not None and self.end_time < self.time:
            raise ValueError("history event end cannot precede its start")
        return self


class LocationRelation(StrictModel):
    location_id: str = Field(min_length=1, max_length=160)
    relation: Literal["ADJACENT", "CONNECTED", "CONTAINS", "NEAR", "CUSTOM"]
    description: str = Field(default="", max_length=1000)


class GeographyData(StrictModel):
    location_id: str = Field(min_length=1, max_length=160)
    region_id: str | None = None
    owner_id: str | None = None
    relations: list[LocationRelation] = Field(default_factory=list, max_length=100)
    supersedes_id: str | None = None
    explanation: str = Field(default="", max_length=4000)


class CivilizationData(StrictModel):
    name: str = Field(min_length=1, max_length=240)
    organization_type: Literal["CIVILIZATION", "ORGANIZATION", "FACTION", "OTHER"] = "CIVILIZATION"
    parent_id: str | None = None
    location_ids: list[str] = Field(default_factory=list, max_length=100)
    principles: list[str] = Field(default_factory=list, max_length=100)


class AbilityData(StrictModel):
    name: str = Field(min_length=1, max_length=240)
    description: str = Field(default="", max_length=12000)
    limits: dict[str, float] = Field(default_factory=dict, max_length=100)
    forbidden_actions: list[str] = Field(default_factory=list, max_length=100)
    costs: dict[str, float] = Field(default_factory=dict, max_length=100)
    conflicts_with: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("limits", "costs")
    @classmethod
    def finite_metrics(cls, values):
        if any(not key or not math.isfinite(value) or value < 0 for key, value in values.items()):
            raise ValueError("ability limits/costs must be finite non-negative metrics")
        return values


class AbilityUseData(StrictModel):
    character_id: str = Field(min_length=1, max_length=160)
    rule_id: str = Field(min_length=1, max_length=160)
    metrics: dict[str, float] = Field(default_factory=dict, max_length=100)
    actions: list[str] = Field(default_factory=list, max_length=100)
    cost_paid: dict[str, float] = Field(default_factory=dict, max_length=100)
    explanation: str = Field(default="", max_length=4000)

    @field_validator("metrics", "cost_paid")
    @classmethod
    def finite_metrics(cls, values):
        return AbilityData.finite_metrics(values)


class PsychologyData(StrictModel):
    character_id: str = Field(min_length=1, max_length=160)
    state: str = Field(min_length=1, max_length=4000)
    from_state: str = Field(default="", max_length=4000)
    motivation: str = Field(default="", max_length=4000)
    arc_id: str = Field(default="default", min_length=1, max_length=160)
    arc_stage: int = Field(default=0, ge=0)
    arc_goal: str = Field(default="", max_length=4000)
    previous_snapshot_id: str | None = None
    explanation: str = Field(default="", max_length=4000)


class RelationshipData(StrictModel):
    source_character_id: str = Field(min_length=1, max_length=160)
    target_character_id: str = Field(min_length=1, max_length=160)
    state: str = Field(min_length=1, max_length=4000)
    from_state: str = Field(default="", max_length=4000)
    previous_record_id: str | None = None
    event_id: str | None = None
    explanation: str = Field(default="", max_length=4000)

    @model_validator(mode="after")
    def different_characters(self):
        if self.source_character_id == self.target_character_id:
            raise ValueError("a relationship needs two different characters")
        return self


class CharacterEventData(StrictModel):
    character_id: str = Field(min_length=1, max_length=160)
    event: Literal["DEATH", "APPEARANCE", "REVIVAL"]
    explanation: str = Field(default="", max_length=4000)
    location_id: str | None = None


DATA_MODELS = {"HISTORY": HistoryData, "GEOGRAPHY": GeographyData,
               "CIVILIZATION": CivilizationData, "ABILITY": AbilityData,
               "ABILITY_USE": AbilityUseData, "PSYCHOLOGY": PsychologyData,
               "RELATIONSHIP": RelationshipData, "CHARACTER_EVENT": CharacterEventData}


class WorldRecordIn(StrictModel):
    kind: Literal["HISTORY", "GEOGRAPHY", "CIVILIZATION", "ABILITY", "ABILITY_USE", "PSYCHOLOGY", "RELATIONSHIP", "CHARACTER_EVENT"]
    title: str = Field(min_length=1, max_length=240)
    chapter_id: str | None = None
    event_order: int = Field(default=0, ge=0)
    data: dict[str, Any]

    @model_validator(mode="after")
    def typed_data(self):
        self.data = DATA_MODELS[self.kind].model_validate(self.data).model_dump()
        if self.kind in {"ABILITY_USE", "PSYCHOLOGY", "RELATIONSHIP", "CHARACTER_EVENT"} and not self.chapter_id:
            raise ValueError(f"{self.kind} requires a real chapter reference")
        return self


class WorldRecordEditIn(WorldRecordIn):
    expected_version: int = Field(ge=1)


class WorldService(DomainService):
    RECORDS = "world_records"
    CANON = "world_canon"
    supports_graph = False

    def _validate_create_capacity(self, state):
        pass

    def _after_record_mutation(self, state, row, actor):
        pass

    def _visible_kind(self, row):
        return not row.get("research_sources") and (self.supports_graph or row["kind"] in DATA_MODELS)

    @staticmethod
    def _promotes_canon(row):
        return row["kind"] in DATA_MODELS or (row["kind"] == "STORY_RELATION" and row["data"]["layer"] == "WORLD_FACT")

    def _payload(self, value):
        return WorldRecordIn.model_validate(value.model_dump() if isinstance(value, WorldRecordIn) else value).model_dump()

    def _chapter(self, nid, scope, cid):
        scoped_sources(self, nid, scope, [cid])
        chapter = self.chapters.get(cid)
        number = chapter.get("number")
        if type(number) is not int or number < 1:
            raise ValueError("chapter has no valid narrative sequence")
        ordered = self.chapters.list(nid)
        ids = [row["id"] for row in ordered]
        if cid not in ids or len(ids) != len(set(ids)):
            raise ValueError("chapter is archived or narrative order is ambiguous")
        return {**chapter, "narrative_sequence": ids.index(cid) + 1}

    def _references(self, nid, scope, payload, state):
        data, kind = payload["data"], payload["kind"]
        characters, locations, dependencies = [], [], []
        if kind == "HISTORY":
            characters += data["character_ids"]
            locations += data["location_ids"]
            dependencies += [(r["event_id"], "HISTORY") for r in data["relations"]]
        elif kind == "GEOGRAPHY":
            locations += [data["location_id"]]
            locations += [data["region_id"]] if data["region_id"] else []
            locations += [r["location_id"] for r in data["relations"]]
            if data["owner_id"]: dependencies.append((data["owner_id"], "CIVILIZATION"))
            if data["supersedes_id"]: dependencies.append((data["supersedes_id"], "GEOGRAPHY"))
            if data["region_id"] == data["location_id"]:
                raise ValueError("a location cannot contain itself")
        elif kind == "CIVILIZATION":
            locations += data["location_ids"]
            if data["parent_id"]: dependencies.append((data["parent_id"], "CIVILIZATION"))
        elif kind == "ABILITY":
            dependencies += [(rid, "ABILITY") for rid in data["conflicts_with"]]
        elif kind == "ABILITY_USE":
            characters.append(data["character_id"])
            dependencies.append((data["rule_id"], "ABILITY"))
        elif kind == "PSYCHOLOGY":
            characters.append(data["character_id"])
            if data["previous_snapshot_id"]: dependencies.append((data["previous_snapshot_id"], "PSYCHOLOGY"))
        elif kind == "RELATIONSHIP":
            characters += [data["source_character_id"], data["target_character_id"]]
            if data["previous_record_id"]: dependencies.append((data["previous_record_id"], "RELATIONSHIP"))
            if data["event_id"]: dependencies.append((data["event_id"], "HISTORY"))
        else:
            characters.append(data["character_id"])
            if data["location_id"]: locations.append(data["location_id"])
        links = {"character_ids": sorted(set(characters)), "location_ids": sorted(set(locations))}
        entities = entity_sources(self, nid, scope, links, state)
        refs = {}
        for rid, expected_kind in dependencies:
            row = require_row(state, self.RECORDS, rid)
            if not self._visible_kind(row): raise FileNotFoundError(rid)
            if row["status"] != "APPROVED" or row["kind"] != expected_kind:
                raise ValueError("semantic references require an approved record of the correct kind")
            if row.get("id") == payload.get("id"):
                raise ValueError("self-referential semantic record")
            refs[rid] = {"version": row["version"], "digest": digest({k: v for k, v in row.items() if k != "history"})}
        if kind == "PSYCHOLOGY" and data["previous_snapshot_id"]:
            prior = require_row(state, self.RECORDS, data["previous_snapshot_id"])["data"]
            if prior["character_id"] != data["character_id"] or prior["arc_id"] != data["arc_id"]:
                raise ValueError("psychology predecessor must be the same character and arc")
        if kind == "RELATIONSHIP" and data["previous_record_id"]:
            prior = require_row(state, self.RECORDS, data["previous_record_id"])["data"]
            if (prior["source_character_id"], prior["target_character_id"]) != (data["source_character_id"], data["target_character_id"]):
                raise ValueError("relationship predecessor must identify the same directed pair")
        if kind == "GEOGRAPHY" and data["supersedes_id"]:
            if require_row(state, self.RECORDS, data["supersedes_id"])["data"]["location_id"] != data["location_id"]:
                raise ValueError("geography predecessor must identify the same location")
        return links, entities, refs

    def _capture(self, nid, scope, payload, state):
        if payload["kind"] not in DATA_MODELS:
            from .story_graph import capture_graph
            return capture_graph(self, nid, scope, payload, state)
        sources = scoped_sources(self, nid, scope, [payload["chapter_id"]] if payload["chapter_id"] else [])
        number = self._chapter(nid, scope, payload["chapter_id"])["narrative_sequence"] if payload["chapter_id"] else 0
        links, entities, refs = self._references(nid, scope, payload, state)
        return {"sources": sources, "effective_chapter": number, "links": links, "entity_sources": entities, "semantic_sources": refs}

    def _assert_fresh(self, nid, scope, row, state, seen=None):
        # Research-derived drafts are visible only through the current-author
        # A10 projection. Generic world/graph/context cannot promote or reuse.
        if row.get("research_sources"):
            raise StaleSourceError("research draft requires current research authority")
        seen = set(seen or ())
        if len(seen) >= 128:
            raise StaleSourceError("semantic source chain exceeds bounded depth")
        if row["id"] in seen:
            raise StaleSourceError("cyclic semantic source chain")
        seen.add(row["id"])
        self.assert_sources(nid, row["sources"])
        try:
            capture = self._capture(nid, scope, row, state)
        except (ValueError, FileNotFoundError, KeyError) as exc:
            raise StaleSourceError("world reference changed or is no longer approved") from exc
        for field in ("effective_chapter", "entity_sources", "semantic_sources", *(["effective_until"] if "effective_until" in row else [])):
            if capture[field] != row[field]:
                raise StaleSourceError("world source or narrative order changed")
        for rid in row["semantic_sources"]:
            self._assert_fresh(nid, scope, require_row(state, self.RECORDS, rid), state, seen)

    def _decorate(self, nid, scope, row, state):
        result = deepcopy(row)
        try:
            self._assert_fresh(nid, scope, row, state)
            result["stale"] = False
        except (ValueError, FileNotFoundError):
            result["stale"] = True
        return result

    def records(self, nid, scope):
        self.novels.get(nid)
        state = self.store.read(nid, scope)
        return [self._decorate(nid, scope, row, state) for row in collection(state, self.RECORDS).values() if self._visible_kind(row)]

    def record(self, nid, scope, rid):
        self.novels.get(nid)
        state = self.store.read(nid, scope)
        row = require_row(state, self.RECORDS, rid)
        if not self._visible_kind(row): raise FileNotFoundError(rid)
        return self._decorate(nid, scope, row, state)

    def create_record(self, nid, scope, actor, value, *, reauthorize=lambda: None):
        payload = self._payload(value)
        self.novels.get(nid)
        with self.store.transaction(nid, scope) as state:
            reauthorize()
            self._validate_create_capacity(state)
            captured = self._capture(nid, scope, payload, state)
            row = new_row(nid, scope, actor, {**payload, **captured, "status": "REVIEW", "canon_state": "CANDIDATE", "privacy_state": "LOCAL_ONLY"})
            self._assert_fresh(nid, scope, row, state)
            collection(state, self.RECORDS)[row["id"]] = row
            self._after_record_mutation(state, row, actor)
            reauthorize()
            return deepcopy(row)

    def create_research_draft(self, nid, scope, actor, value, refs, *, guard, validate):
        """Use this native world transaction, with transient caller authority.

        No callback or session is persisted. These private candidates are not
        generic world-review inputs and can never become Canon through it.
        """
        payload = self._payload(value)
        if payload["kind"] != "ABILITY":
            raise ValueError("research adoption supports original setting drafts only")
        self.novels.get(nid)
        with self.store.transaction(nid, scope) as state:
            guard(); validate(state)
            if sum(bool(item.get("research_sources")) for item in collection(state, self.RECORDS).values()) >= 1000:
                raise ValueError("RESEARCH_DRAFT_LIMIT")
            self._validate_create_capacity(state)
            captured = self._capture(nid, scope, payload, state)
            row = new_row(nid, scope, actor, {**payload, **captured, "status": "REVIEW",
                "canon_state": "CANDIDATE", "privacy_state": "LOCAL_ONLY"})
            self._assert_fresh(nid, scope, row, state)
            row["research_sources"] = deepcopy(refs)
            collection(state, self.RECORDS)[row["id"]] = row
            guard(); validate(state)
            return {**deepcopy(row), "layer": "SETTING_DRAFT", "canon_promotion_available": False}

    def edit_record(self, nid, scope, actor, rid, value, *, reauthorize=lambda: None):
        raw = value.model_dump() if isinstance(value, WorldRecordEditIn) else dict(value)
        expected = raw.pop("expected_version")
        payload = self._payload(raw)
        with self.store.transaction(nid, scope) as state:
            reauthorize()
            row = require_row(state, self.RECORDS, rid)
            if not self._visible_kind(row): raise FileNotFoundError(rid)
            if row["kind"] != payload["kind"]: raise ValueError("record kind is immutable")
            if row["status"] == "APPROVED":
                raise ValueError("approved Canon is immutable; create a new candidate")
            captured = self._capture(nid, scope, payload, state)
            change_row(row, actor, expected, lambda target: target.update(payload, **captured, status="REVIEW", canon_state="CANDIDATE"))
            self._after_record_mutation(state, row, actor)
            reauthorize()
            return deepcopy(row)

    def review(self, nid, scope, actor, item_id, action, expected_version, *, reauthorize=lambda: None):
        with self.store.transaction(nid, scope) as state:
            reauthorize()
            row = require_row(state, self.RECORDS, item_id)
            if not self._visible_kind(row): raise FileNotFoundError(item_id)
            if row["version"] != expected_version:
                raise CapabilityVersionConflict(deepcopy(row))
            transitions = {"approve": ({"REVIEW"}, "APPROVED"), "reject": ({"REVIEW"}, "REJECTED"), "reopen": ({"REJECTED", "ARCHIVED"}, "REVIEW"), "archive": ({"REVIEW", "REJECTED", "APPROVED"}, "ARCHIVED")}
            if action not in transitions or row["status"] not in transitions[action][0]:
                raise ValueError("invalid world review transition")
            if action == "approve":
                self._assert_fresh(nid, scope, row, state)
            def update(target):
                target.update(status=transitions[action][1], canon_state=("CANON" if self._promotes_canon(row) else "REVIEWED") if action == "approve" else "CANDIDATE")
            change_row(row, actor, expected_version, update)
            canon_rows = collection(state, self.CANON)
            if action == "approve" and self._promotes_canon(row):
                content = {key: deepcopy(row[key]) for key in ("kind", "title", "chapter_id", "event_order", "data", "sources", "effective_chapter", "links", "entity_sources", "semantic_sources")}
                content.update(source_record_id=row["id"], source_record_version=row["version"], status="ACTIVE")
                previous = next((entry for entry in canon_rows.values() if entry["source_record_id"] == row["id"]), None)
                if previous:
                    change_row(previous, actor, previous["version"], lambda target: target.update(content))
                    row["canon_id"] = previous["id"]
                else:
                    canon = new_row(nid, scope, actor, content)
                    canon_rows[canon["id"]] = canon
                    row["canon_id"] = canon["id"]
            elif row.get("canon_id"):
                canon = canon_rows[row["canon_id"]]
                if canon["status"] == "ACTIVE":
                    change_row(canon, actor, canon["version"], lambda target: target.update(status="ARCHIVED"))
            self._after_record_mutation(state, row, actor)
            reauthorize()
            return deepcopy(row)

    def history(self, nid, scope, rid):
        return self.record(nid, scope, rid)["history"]

    def canon(self, nid, scope):
        self.novels.get(nid)
        state = self.store.read(nid, scope)
        rows = []
        for canon in collection(state, self.CANON).values():
            if canon["status"] != "ACTIVE" or not self._visible_kind(canon):
                continue
            source = require_row(state, self.RECORDS, canon["source_record_id"])
            rows.append({**deepcopy(canon), "stale": self._decorate(nid, scope, source, state)["stale"]})
        return rows

    @staticmethod
    def _order(row):
        return row["effective_chapter"], row["event_order"], row["created_at"], row["id"]

    def character_state(self, nid, scope, character_id, chapter_id):
        entity_sources(self, nid, scope, {"character_ids": [character_id]})
        chapter = self._chapter(nid, scope, chapter_id)
        canonical_rows = self.canon(nid, scope)
        rows = [row for row in canonical_rows if not row["stale"] and row["effective_chapter"] <= chapter["narrative_sequence"]]
        rows.sort(key=self._order)
        state = {"character_id": character_id, "chapter_id": chapter_id, "chapter_number": chapter["narrative_sequence"], "life_state": "UNSPECIFIED", "psychology": None, "arcs": {}, "relationships": {}, "evidence_record_ids": [], "verification": "DETERMINISTIC_RULES"}
        for row in rows:
            data, kind = row["data"], row["kind"]
            relevant = False
            if kind == "CHARACTER_EVENT" and data["character_id"] == character_id:
                if data["event"] == "DEATH": state["life_state"] = "DEAD"
                elif data["event"] == "REVIVAL": state["life_state"] = "ALIVE"
                elif state["life_state"] == "UNSPECIFIED": state["life_state"] = "ALIVE"
                relevant = True
            elif kind == "PSYCHOLOGY" and data["character_id"] == character_id:
                state["psychology"] = deepcopy(data)
                state["arcs"].setdefault(data["arc_id"], []).append({"chapter_id": row["chapter_id"], "record_id": row["source_record_id"], **deepcopy(data)})
                relevant = True
            elif kind == "RELATIONSHIP" and character_id in {data["source_character_id"], data["target_character_id"]}:
                pair = f"{data['source_character_id']}->{data['target_character_id']}"
                state["relationships"][pair] = deepcopy(data)
                relevant = True
            if relevant: state["evidence_record_ids"].append(row["source_record_id"])
        state["excluded_stale_records"] = [row["source_record_id"] for row in canonical_rows if row["stale"] and row["effective_chapter"] <= chapter["narrative_sequence"] and character_id in row["links"]["character_ids"]]
        return state

    def continuity(self, nid, scope, include_candidates=False):
        """Pure deterministic evaluation. Candidate findings do not promote Canon."""
        records = self.records(nid, scope)
        selected = [row for row in records if row["status"] == "APPROVED" or (include_candidates and row["status"] == "REVIEW")]
        selected.sort(key=self._order)
        approved = {row["id"]: row for row in records if row["status"] == "APPROVED" and not row["stale"]}
        findings = []

        def finding(code, row, message, related=None):
            findings.append({"id": digest([code, row["id"], related or []])[:24], "code": code, "severity": "WARNING", "record_id": row["id"], "chapter_id": row["chapter_id"], "related_record_ids": related or [], "message": message, "candidate": row["status"] != "APPROVED", "sources": row["sources"], "verification": "DETERMINISTIC_RULES"})

        deaths, geography, psychology, relationships, uses = {}, {}, {}, {}, {}
        for row in selected:
            data, kind = row["data"], row["kind"]
            if row["stale"]:
                finding("STALE_SOURCE", row, "Record evidence changed; excluded from continuity state.")
                continue
            if kind == "HISTORY":
                for relation in data["relations"]:
                    other = approved[relation["event_id"]]
                    if other["data"]["calendar"] != data["calendar"]:
                        finding("TIMELINE_CALENDAR_UNCOMPARABLE", row, "Events use different calendars.", [other["id"]])
                        continue
                    earlier = data["time"] < other["data"]["time"]
                    later = data["time"] > other["data"]["time"]
                    valid = {"BEFORE": earlier, "AFTER": later, "SIMULTANEOUS": not earlier and not later, "CAUSES": earlier}
                    if not valid[relation["relation"]]: finding("HISTORY_TEMPORAL_CONFLICT", row, "Event relation contradicts its recorded time.", [other["id"]])
            elif kind == "CHARACTER_EVENT":
                cid = data["character_id"]
                if data["event"] == "DEATH": deaths[cid] = row
                elif data["event"] == "REVIVAL":
                    if not data["explanation"]: finding("UNEXPLAINED_REVIVAL", row, "Revival needs an explanation.", [deaths[cid]["id"]] if cid in deaths else [])
                    else: deaths.pop(cid, None)
                elif cid in deaths and not data["explanation"]:
                    finding("DEAD_CHARACTER_APPEARANCE", row, "Character appears after recorded death without explanation.", [deaths[cid]["id"]])
            elif kind == "GEOGRAPHY":
                prior = geography.get(data["location_id"])
                if prior and any(prior["data"].get(key) != data.get(key) for key in ("owner_id", "region_id")):
                    explained = data["supersedes_id"] == prior["id"] and bool(data["explanation"]) and self._order(prior) < self._order(row)
                    if not explained: finding("LOCATION_OWNERSHIP_CONFLICT", row, "Location ownership or region changes without an explained transition.", [prior["id"]])
                geography[data["location_id"]] = row
            elif kind == "ABILITY_USE":
                rule = approved[data["rule_id"]]
                spec = rule["data"]
                violations = [key for key, maximum in spec["limits"].items() if key in data["metrics"] and data["metrics"][key] > maximum]
                violations += sorted(set(spec["forbidden_actions"]) & set(data["actions"]))
                violations += [f"cost:{key}" for key, minimum in spec["costs"].items() if data["cost_paid"].get(key, 0) < minimum]
                if violations: finding("ABILITY_LIMIT_VIOLATION", row, "Approved ability constraints violated: " + ", ".join(violations), [rule["id"]])
                key = data["character_id"], row["chapter_id"], row["event_order"]
                for prior in uses.get(key, []):
                    other = approved[prior["data"]["rule_id"]]
                    if other["id"] in spec["conflicts_with"] or rule["id"] in other["data"]["conflicts_with"]:
                        finding("ABILITY_RULE_CONFLICT", row, "Mutually exclusive abilities are used at the same event.", [prior["id"], rule["id"], other["id"]])
                uses.setdefault(key, []).append(row)
            elif kind in {"PSYCHOLOGY", "RELATIONSHIP"}:
                if kind == "PSYCHOLOGY":
                    key, state_map, previous_key = (data["character_id"], data["arc_id"]), psychology, "previous_snapshot_id"
                else:
                    key, state_map, previous_key = (data["source_character_id"], data["target_character_id"]), relationships, "previous_record_id"
                explicit = approved.get(data[previous_key])
                prior = state_map.get(key)
                reversal = explicit is not None and self._order(explicit) >= self._order(row)
                mismatch = prior is not None and bool(data["from_state"]) and data["from_state"] != prior["data"]["state"]
                regression = kind == "PSYCHOLOGY" and prior is not None and data["arc_stage"] < prior["data"]["arc_stage"]
                if reversal or ((mismatch or regression) and not data["explanation"]):
                    finding("CHARACTER_STATE_TIME_REVERSAL", row, "Character state reverses recorded chronology or its predecessor state.", [item["id"] for item in (explicit, prior) if item is not None])
                state_map[key] = row
        return {"items": findings, "evaluated_records": len(selected), "include_candidates": include_candidates, "verification": "DETERMINISTIC_RULES", "mutates_canon": False}

    def list_review_items(self, nid, scope):
        return [{**row, "domain": "world", "source": "world_semantic_engine", "preview": row["title"], "target": {"kind": row["kind"], "chapter_id": row["chapter_id"]}, "source_versions": row["sources"], "risk": "EXPERIMENTAL_CANON", "safe_batch": False, "allowed_actions": ["approve", "reject"] if row["status"] == "REVIEW" else ["reopen"] if row["status"] in {"REJECTED", "ARCHIVED"} else []} for row in self.records(nid, scope)]
