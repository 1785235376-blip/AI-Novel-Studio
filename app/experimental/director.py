"""A08 camera-grammar drafts over the existing screenplay/version authority.

No text-only spatial inference, model call, asset generation, or new shot store.
"""
from __future__ import annotations
import copy
from fractions import Fraction
from typing import Literal
from pydantic import ConfigDict, Field, model_validator
from ..source_privacy import source_privacy_status
from .common import DomainService, StaleSourceError, check_version
from .media import StrictModel, digest, scene_sources


class Point(StrictModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    x: float = Field(ge=-1000000, le=1000000)
    y: float = Field(ge=-1000000, le=1000000)


class Movement(StrictModel):
    start: Point
    end: Point


class CameraGrammar(StrictModel):
    scene_purpose: str = Field(default="", max_length=2000)
    viewpoint: str = Field(default="", max_length=500)
    screen_direction: Literal["UNKNOWN", "LEFT_TO_RIGHT", "RIGHT_TO_LEFT", "STATIONARY"] = "UNKNOWN"
    coordinate_system: str = Field(default="", max_length=120)
    character_positions: dict[str, Point] = Field(default_factory=dict, max_length=30)
    axis: list[str] = Field(default_factory=list, max_length=2)
    camera_position: Point | None = None
    subject_movement: Movement | None = None
    intentional_axis_crossing: bool = False
    intentions: list[Literal["LONG_TAKE", "JUMP_CUT"]] = Field(default_factory=list, max_length=2)
    override_reason: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def complete_axis(self):
        if self.axis and (len(self.axis) != 2 or len(set(self.axis)) != 2 or any(key not in self.character_positions for key in self.axis)):
            raise ValueError("DIRECTOR_AXIS_REQUIRES_TWO_POSITIONED_CHARACTERS")
        if (self.intentional_axis_crossing or self.intentions) and not self.override_reason:
            raise ValueError("DIRECTOR_INTENTIONAL_CHOICE_REQUIRES_REASON")
        return self


class ShotDirection(StrictModel):
    shot_id: str = Field(min_length=1, max_length=240)
    shot_size: str = Field(min_length=1, max_length=80)
    camera_angle: str = Field(min_length=1, max_length=80)
    camera_motion: str = Field(min_length=1, max_length=80)
    duration_seconds: int = Field(ge=1, le=600, strict=True)
    director: CameraGrammar = Field(default_factory=CameraGrammar)


class DirectorPlanIn(StrictModel):
    screenplay_id: str = Field(min_length=1, max_length=240)
    expected_screenplay_version: int = Field(ge=1, strict=True)
    title: str = Field(min_length=1, max_length=240)
    shots: list[ShotDirection] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def distinct(self):
        if len({row.shot_id for row in self.shots}) != len(self.shots):
            raise ValueError("DIRECTOR_DUPLICATE_SHOT")
        return self


def _point(value):
    return Fraction(str(value["x"])), Fraction(str(value["y"]))


def _geometry(shot):
    data = shot.get("director") or {}
    axis = data.get("axis") or []
    positions = data.get("character_positions") or {}
    if len(axis) != 2 or not data.get("coordinate_system") or not data.get("camera_position") or any(a not in positions for a in axis):
        return None
    a, b, camera = _point(positions[axis[0]]), _point(positions[axis[1]]), _point(data["camera_position"])
    dx, dy = b[0] - a[0], b[1] - a[1]
    if dx == dy == 0:
        return None
    cross = dx * (camera[1] - a[1]) - dy * (camera[0] - a[0])
    if cross == 0:
        return None  # Camera on the axis cannot establish a reliable side.
    return data, axis, a, b, camera, cross


def camera_checks(shots):
    """Exact rational cross products; no visual/aesthetic confidence score."""
    findings = []
    for previous, current in zip(shots, shots[1:]):
        item = {"from_shot_id": previous["id"], "to_shot_id": current["id"], "kind": "AXIS"}
        first, second = _geometry(previous), _geometry(current)
        if (previous.get("scene_id") != current.get("scene_id") or first is None or second is None
            or first[0]["coordinate_system"] != second[0]["coordinate_system"] or first[1:4] != second[1:4]):
            findings.append({**item, "state": "INSUFFICIENT_EVIDENCE", "message": "信息不足：需要同场景、同坐标系、稳定人物位置和轴线两侧的明确机位。"})
            continue
        crossed = (first[-1] > 0) != (second[-1] > 0)
        overridden = crossed and second[0].get("intentional_axis_crossing") and bool(second[0].get("override_reason"))
        findings.append({**item, "state": "INTENTIONAL_OVERRIDE" if overridden else "AXIS_CROSSING" if crossed else "SAME_SIDE",
                         "cross_products": [str(first[-1]), str(second[-1])],
                         "message": "已记录有意越轴及理由。" if overridden else "明确几何显示越轴；这是可覆盖的建议。" if crossed else "明确几何显示两机位位于轴线同侧。"})
    for shot in shots:
        geo = _geometry(shot); data = shot.get("director") or {}; movement = data.get("subject_movement")
        item = {"shot_id": shot["id"], "kind": "SCREEN_DIRECTION"}
        if geo is None or not movement or data.get("screen_direction", "UNKNOWN") == "UNKNOWN":
            findings.append({**item, "state": "INSUFFICIENT_EVIDENCE", "message": "信息不足：未提供可计算的移动轨迹、机位或明确屏幕方向。"})
            continue
        _, _, a, b, camera, _ = geo
        start, end = _point(movement["start"]), _point(movement["end"])
        forward = ((a[0] + b[0]) / 2 - camera[0], (a[1] + b[1]) / 2 - camera[1])
        projection = forward[1] * (end[0] - start[0]) - forward[0] * (end[1] - start[1])
        computed = "LEFT_TO_RIGHT" if projection > 0 else "RIGHT_TO_LEFT" if projection < 0 else "STATIONARY"
        findings.append({**item, "state": "CONSISTENT" if computed == data["screen_direction"] else "DIRECTION_MISMATCH",
                         "computed": computed, "projection": str(projection), "message": "按机位朝向轴线中点、世界坐标 x 向右 y 向上的声明几何复算；不分析实际画面。"})
    return findings


def screenplay_projection(row, *, enabled=False):
    """Legacy HTTP response filter, including nested history/conflict payloads.

    Experimental drafts never live here. Applied camera metadata is hidden
    while OFF/V1; stale output archives always remain internal.
    """
    if isinstance(row, list):
        return [screenplay_projection(item, enabled=enabled) for item in row]
    if not isinstance(row, dict):
        return row
    return {key: screenplay_projection(value, enabled=enabled) for key, value in row.items()
            if not key.startswith("director_") and (enabled or key != "director")}


class DirectorService(DomainService):
    PLANS = "director_plans_v2"

    def __init__(self, store, novels, chapters, screenplays):
        super().__init__(store, novels, chapters)
        self.screenplays = screenplays

    def screenplay(self, nid, scope, sid):
        self.novels.get(nid)
        row = next((r for r in self.screenplays.list(nid) if r["id"] == sid and r.get("branch_id") == scope.get("branch_id")), None)
        if row is None:
            raise FileNotFoundError(sid)
        return copy.deepcopy(row)

    def evidence(self, nid, scope, screenplay):
        sources = {}
        for scene in screenplay.get("scenes", []):
            sources.update(scene_sources(nid, scope, scene, self.chapters))
        privacy = {cid: source_privacy_status(self.chapters.get(cid), scope.get("branch_id"), self.store.root) for cid in sources}
        return {"sources": sources, "privacy": privacy}

    def _character_sources(self, nid, scope, ids):
        rows = {row['id']: row for row in self.novels.data_set(nid, 'characters') if row.get('branch_id') == scope.get('branch_id')}
        if set(ids) - rows.keys():
            raise FileNotFoundError('director character source unavailable')
        return {cid: digest(rows[cid]) for cid in ids}

    def _metadata_current(self, row):
        binding = row.get('director_source_evidence')
        if not isinstance(binding, dict):
            return False
        try:
            scope = binding['scope']
            if not isinstance(scope, dict) or not isinstance(binding.get('character_sources'), dict):
                return False
            return (row.get('branch_id') == scope.get('branch_id') and row.get('novel_id') == scope.get('novel_id')
                    and self.evidence(row['novel_id'], scope, row) == binding['evidence']
                    and self._character_sources(row['novel_id'], scope, binding['character_sources']) == binding['character_sources'])
        except (FileNotFoundError, KeyError, ValueError):
            return False

    def project_screenplay(self, value, *, enabled=False):
        # Historical bytes remain in the repository, but already invalidated
        # outputs must not escape through generic history/conflict responses.
        stale_revisions = set()
        def gather(node):
            if isinstance(node, list):
                for item in node: gather(item)
            elif isinstance(node, dict):
                if node.get('novel_id') and node.get('id'):
                    for receipt in node.get('director_stale_outputs', []) if isinstance(node.get('director_stale_outputs'), list) else []:
                        if not isinstance(receipt, dict): continue
                        stale_revisions.add((node['novel_id'], node['id'], receipt.get('shot_revision')))
                for item in node.values(): gather(item)
        gather(value)
        downstream = {'storyboard', 'transitions', 'asset_requirements', 'asset_tasks', 'motion_tasks'}
        def project(node, show):
            if isinstance(node, list):
                return [project(item, show) for item in node]
            if not isinstance(node, dict):
                return node
            is_screenplay = 'shots' in node and 'novel_id' in node
            if is_screenplay:
                show = show and self._metadata_current(node)
            stale_outputs = is_screenplay and (node.get('novel_id'), node.get('id'), node.get('shot_revision')) in stale_revisions
            result = {key: project(item, show) for key, item in node.items()
                      if not key.startswith('director_') and (show or key != 'director') and not (stale_outputs and key in downstream)}
            if stale_outputs: result['downstream_review_state'] = 'STALE_PENDING_REVIEW'
            return result
        return project(value, enabled)

    def _current(self, nid, scope, plan):
        row = self.screenplay(nid, scope, plan["screenplay_id"])
        if (row["edit_version"] != plan["screenplay_version"] or self.evidence(nid, scope, row) != plan["evidence"]
            or self._character_sources(nid, scope, plan.get('character_sources', {})) != plan.get('character_sources', {})):
            raise StaleSourceError("DIRECTOR_SOURCE_CHANGED")
        return row

    def _visible(self, nid, scope, plan):
        try:
            row = self.screenplay(nid, scope, plan["screenplay_id"])
            for cid in plan["evidence"]["sources"]:
                chapter = self.chapters.get(cid)
                if chapter.get("novel_id") != nid or chapter.get("branch_id") != scope.get("branch_id"):
                    return None
            characters = self._character_sources(nid, scope, plan.get('character_sources', {}))
            stale = (row["edit_version"] != plan["screenplay_version"] or self.evidence(nid, scope, row) != plan["evidence"]
                     or characters != plan.get('character_sources', {}))
        except (FileNotFoundError, KeyError):
            return None
        except StaleSourceError:
            stale = True
        safe = {key: plan[key] for key in ("id", "title", "version", "status", "screenplay_id", "screenplay_version")}
        safe.update(stale=stale, privacy_level="LOCAL_ONLY", model_called=False)
        if not stale:
            safe["shots"] = plan["shots"]
            safe["checks"] = camera_checks(self._candidate(row, plan))
        return safe

    def _candidate(self, screenplay, plan):
        patches = {r["shot_id"]: r for r in plan["shots"]}
        rows = self.project_screenplay(screenplay, enabled=True).get('shots', [])
        return [{**row, **{k: v for k, v in patches.get(row["id"], {}).items() if k != "shot_id"}} for row in rows]

    def catalog(self, nid, scope, actor):
        rows = []
        for screenplay in self.screenplays.list(nid):
            if screenplay.get("branch_id") != scope.get("branch_id"):
                continue
            try:
                self.evidence(nid, scope, screenplay)
            except (StaleSourceError, FileNotFoundError, KeyError):
                continue
            shots = [{k: shot[k] for k in ("id", "number", "scene_id", "shot_size", "camera_angle", "camera_motion", "duration_seconds", "director") if k in shot} for shot in self.project_screenplay(screenplay, enabled=True).get("shots", [])]
            rows.append({"id": screenplay["id"], "title": screenplay["title"], "edit_version": screenplay["edit_version"],
                         "shot_status": screenplay.get("shot_status", "DRAFT"), "shots": shots, "checks": camera_checks(shots)})
        # Character IDs are reused; no secret/world text becomes camera context.
        characters = [{"id": r["id"], "name": r.get("name", r["id"])} for r in self.novels.data_set(nid, "characters")
                      if r.get("branch_id") == scope.get("branch_id")]
        return {"screenplays": rows, "characters": characters, "model_called": False, "automatic_generation": False}

    def plans(self, nid, scope, actor):
        items = [view for row in self.list(nid, scope, self.PLANS) if row["created_by"] == actor
                 if (view := self._visible(nid, scope, row)) is not None]
        return {"items": items}

    def create_plan(self, nid, scope, actor, value, guard=lambda: None):
        body = DirectorPlanIn.model_validate(value)
        row = self.screenplay(nid, scope, body.screenplay_id)
        if row["edit_version"] != body.expected_screenplay_version:
            raise StaleSourceError("DIRECTOR_SCREENPLAY_CHANGED")
        actual = {r["id"] for r in row.get("shots", [])}
        if any(shot.shot_id not in actual for shot in body.shots):
            raise ValueError("DIRECTOR_UNKNOWN_SHOT")
        characters = {r["id"] for r in self.catalog(nid, scope, actor)["characters"]}
        if any(set(shot.director.character_positions) - characters for shot in body.shots):
            raise ValueError("DIRECTOR_UNKNOWN_CHARACTER")
        evidence = self.evidence(nid, scope, row)
        character_sources = self._character_sources(nid, scope, {cid for shot in body.shots for cid in shot.director.character_positions})
        payload = {"character_sources": character_sources, "title": body.title, "screenplay_id": row["id"], "screenplay_version": row["edit_version"],
                   "shots": [r.model_dump() for r in body.shots], "evidence": evidence}
        guard(); self._current(nid, scope, payload)
        saved = self.create(nid, scope, actor, self.PLANS, payload)
        return self._visible(nid, scope, saved)

    def _plan(self, nid, scope, actor, rid):
        plan = self.get(nid, scope, self.PLANS, rid)
        if plan["created_by"] != actor or self._visible(nid, scope, plan) is None:
            raise FileNotFoundError(rid)
        return plan

    def compare(self, nid, scope, actor, ids):
        if not 1 <= len(ids) <= 4 or len(set(ids)) != len(ids):
            raise ValueError("DIRECTOR_SELECT_ONE_TO_FOUR_PLANS")
        plans = [self._plan(nid, scope, actor, rid) for rid in ids]
        if len({(r["screenplay_id"], r["screenplay_version"]) for r in plans}) != 1 or any(r["status"] != "DRAFT" for r in plans):
            raise ValueError("DIRECTOR_COMPARE_SAME_CURRENT_SCREENPLAY_DRAFTS")
        screenplay = self._current(nid, scope, plans[0])
        originals = [{k: shot[k] for k in ("id", "number", "scene_id", "shot_size", "camera_angle", "camera_motion", "duration_seconds", "director") if k in shot} for shot in self.project_screenplay(screenplay, enabled=True).get("shots", [])]
        result = {"screenplay_id": screenplay["id"], "screenplay_version": screenplay["edit_version"], "original": originals,
                  "candidates": [self._visible(nid, scope, row) for row in plans], "review_action": "APPLY_AS_SHOT_DRAFT_THEN_ORIGINAL_SHOT_APPROVAL"}
        result["comparison_digest"] = digest({"actor": actor, "scope": scope, "comparison": result})
        result["application_digests"] = {row["id"]: digest({"actor": actor, "scope": scope, "plan": row, "screenplay_version": screenplay["edit_version"]}) for row in plans}
        return result

    def apply(self, nid, scope, actor, rid, expected_version, comparison_digest, guard=lambda: None):
        plan = self._plan(nid, scope, actor, rid)
        check_version(plan, expected_version)
        # A failed receipt write can be reconciled using the atomic screenplay
        # marker. The screenplay is never written twice for the same plan.
        screenplay = self.screenplay(nid, scope, plan["screenplay_id"])
        if screenplay.get("director_applied_plan_id") == rid:
            guard()
            if plan["status"] != "APPLIED":
                self.mutate(nid, scope, actor, self.PLANS, rid, expected_version,
                            lambda row: row.update(status="APPLIED", result_screenplay_version=screenplay["edit_version"]))
            return {"screenplay_id": screenplay["id"], "edit_version": screenplay["edit_version"], "shot_status": screenplay.get("shot_status"), "recovered": True}
        comparison = self.compare(nid, scope, actor, [rid])
        if comparison["application_digests"][rid] != comparison_digest:
            raise StaleSourceError("DIRECTOR_COMPARISON_CHANGED")
        guard(); self._current(nid, scope, plan)
        def final_guard():
            guard()
            current_plan = self._plan(nid, scope, actor, rid)
            check_version(current_plan, expected_version)
            if current_plan['status'] != 'DRAFT':
                raise StaleSourceError('DIRECTOR_PLAN_DECISION_CHANGED')
            self._current(nid, scope, plan)
        saved = self.screenplays.apply_director_plan(nid, screenplay["id"], plan["shots"], expected_version=plan["screenplay_version"],
                                                    plan_id=rid, actor=actor, source_evidence={'scope': scope, 'evidence': plan['evidence'], 'character_sources': plan.get('character_sources', {})}, guard=final_guard)
        self.mutate(nid, scope, actor, self.PLANS, rid, expected_version,
                    lambda row: row.update(status="APPLIED", result_screenplay_version=saved["edit_version"]))
        return {"screenplay_id": saved["id"], "edit_version": saved["edit_version"], "shot_status": saved["shot_status"], "recovered": False}

    def reject(self, nid, scope, actor, rid, expected_version, guard=lambda: None):
        plan = self._plan(nid, scope, actor, rid)
        if plan["status"] != "DRAFT":
            raise ValueError("DIRECTOR_DRAFT_REQUIRED")
        guard()
        saved = self.mutate(nid, scope, actor, self.PLANS, rid, expected_version, lambda row: row.update(status="REJECTED"))
        return self._visible(nid, scope, saved)
