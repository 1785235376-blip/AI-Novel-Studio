"""Resumable per-candidate knowledge acceptance with durable, bounded checkpoints.

Each existing repository upsert keeps its own atomic persistence contract. A
multi-entity apply is deliberately not advertised as one database transaction.
Ambiguous interrupted writes stop for review rather than overwriting later edits.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re
import uuid

from ..repositories.file.mutation_coordinator import workspace_mutation
from ..storage import atomic_write

KINDS = {"characters":"characters", "locations":"locations", "timeline_events":"timeline", "foreshadowing":"foreshadowing"}
MAX_CANDIDATES = 1000


def _digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


class ImportApplyInterrupted(RuntimeError):
    def __init__(self, detail):
        super().__init__(detail["code"])
        self.detail = detail


class ImportApplyService:
    def __init__(self, novel_service, data_root: Path):
        self.novels = novel_service
        self.root = Path(data_root)

    def _path(self, review_id):
        return self.root / "import_apply_journal" / (_digest(str(review_id)) + ".json")

    def _write(self, review_id, journal):
        atomic_write(self._path(review_id),json.dumps(journal,ensure_ascii=False,indent=2,allow_nan=False))

    def _current(self, nid, kind, target_id):
        return next((row for row in self.novels.data_set(nid,KINDS[kind]) if str(row.get("id"))==target_id),None)

    @staticmethod
    def _applied(journal):
        result = {kind:[] for kind in KINDS}
        for step in journal["steps"]:
            if step["status"] == "DONE":
                result[step["kind"]].append(copy.deepcopy(step["result"]))
        return result

    def status(self, review_id, nid):
        path=self._path(review_id)
        if not path.exists():
            return None
        journal=json.loads(path.read_text(encoding="utf-8"))
        if journal.get("novel_id") != nid or journal.get("review_id") != review_id:
            raise ValueError("import apply journal scope mismatch")
        return {"status":journal["status"],"applied":self._applied(journal),
                "completed":sum(step["status"]=="DONE" for step in journal["steps"]),
                "total":len(journal["steps"])}

    def _interrupt(self, review_id, journal, code, step=None):
        journal["status"]="REVIEW_REQUIRED" if code in {"IMPORT_APPLY_AMBIGUOUS","IMPORT_APPLIED_RECORD_CHANGED","IMPORT_TARGET_EXISTS"} else "PARTIAL"
        journal["error_code"]=code
        try:
            self._write(review_id,journal)
        except OSError:
            # An earlier APPLYING checkpoint is already durable. Never report a
            # success when the outcome checkpoint itself could not be persisted.
            pass
        detail={"code":code,"review_id":review_id,"status":journal["status"],
                "applied":self._applied(journal),"completed":sum(s["status"]=="DONE" for s in journal["steps"]),
                "total":len(journal["steps"])}
        if step is not None:detail["candidate_id"]=step["target_id"]
        raise ImportApplyInterrupted(detail)

    def apply(self, review_id: str, nid: str, candidates: dict, *, actor_id: str) -> dict:
        if not isinstance(candidates,dict) or set(candidates)-set(KINDS):
            raise ValueError("unsupported knowledge candidate group")
        if any(not isinstance(rows,list) for rows in candidates.values()):
            raise ValueError("knowledge candidate groups must be lists")
        if sum(map(len,candidates.values())) > MAX_CANDIDATES:
            raise ValueError("accept at most 1000 candidates per review")
        steps=[]; targets=set()
        for kind in KINDS:
            for ordinal,item in enumerate(candidates.get(kind,[])):
                key="name" if kind in {"characters","locations"} else "title"
                if not isinstance(item,dict) or not str(item.get(key) or "").strip():
                    raise ValueError(f"{kind} candidate requires {key}")
                source=str(item.get("id") or "")
                # Existing business IDs stay addressable. New candidate IDs are
                # deterministic across crashes, including non-Latin names.
                if source and re.fullmatch(r"[a-zA-Z0-9_-]+",source):
                    target=source.lower()
                else:
                    target=str(uuid.uuid5(uuid.NAMESPACE_URL,f"import-apply:{review_id}:{nid}:{kind}:{item.get('candidate_id') or ordinal}"))
                if (kind,target) in targets:
                    raise ValueError("duplicate target entity in review selection")
                targets.add((kind,target))
                steps.append({"kind":kind,"target_id":target,"candidate":{**item,"id":target},"status":"PENDING"})
        fingerprint=_digest(candidates)
        # Shared thread + OS lock survives separate service instances and avoids
        # competing acceptance calls inside this runtime-data directory.
        with workspace_mutation(self.root,"knowledge-import:"+str(review_id)):
            path=self._path(review_id)
            if path.exists():
                journal=json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(journal,dict) or journal.get("schema_version") != 1:
                    raise ValueError("import apply journal is corrupt")
                if journal.get("review_id") != review_id or journal.get("novel_id") != nid or journal.get("fingerprint") != fingerprint:
                    raise ValueError("review selection changed after acceptance began; inspect its existing checkpoints")
            else:
                journal={"schema_version":1,"review_id":review_id,"novel_id":nid,"fingerprint":fingerprint,
                         "status":"APPLYING","actor_id":actor_id,"steps":steps}
                self._write(review_id,journal)
            journal["last_actor_id"]=actor_id
            for step in journal["steps"]:
                current=self._current(nid,step["kind"],step["target_id"])
                current_digest=_digest(current)
                if step["status"]=="DONE":
                    if current_digest != step["result_digest"]:
                        self._interrupt(review_id,journal,"IMPORT_APPLIED_RECORD_CHANGED",step)
                    continue
                if step["status"]=="PENDING" and current is not None:
                    # This import has no version-bound authority to replace a
                    # previously existing fact. Have the user resolve the clash.
                    self._interrupt(review_id,journal,"IMPORT_TARGET_EXISTS",step)
                if step["status"] in {"APPLYING","FAILED"} and current_digest != step["before_digest"]:
                    self._interrupt(review_id,journal,"IMPORT_APPLY_AMBIGUOUS",step)
                step.update(status="APPLYING",before_digest=current_digest)
                self._write(review_id,journal)
                try:
                    result=self.novels.review_import_knowledge(nid,"ACCEPTED",{step["kind"]:[step["candidate"]]})
                    written=result.get("applied",{}).get(step["kind"],[])
                    if len(written)!=1 or written[0].get("id")!=step["target_id"]:
                        raise ValueError("repository did not confirm exactly one target")
                    current=self._current(nid,step["kind"],step["target_id"])
                    if current is None:
                        raise ValueError("written entity could not be read back")
                    step.update(status="DONE",result=copy.deepcopy(current),result_digest=_digest(current))
                    self._write(review_id,journal)
                except Exception:
                    if step["status"] != "DONE":step["status"]="FAILED"
                    self._interrupt(review_id,journal,"IMPORT_APPLY_PARTIAL",step)
            journal["status"]="COMPLETED";journal.pop("error_code",None)
            self._write(review_id,journal)
            return {"decision":"ACCEPTED","applied":self._applied(journal),
                    "apply_status":"COMPLETED","checkpoint_count":len(journal["steps"])}
