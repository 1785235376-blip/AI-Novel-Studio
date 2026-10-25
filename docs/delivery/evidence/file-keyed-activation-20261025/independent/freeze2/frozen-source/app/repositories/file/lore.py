from __future__ import annotations
from ...services.ordinary_writer_ports import writer_file_port, current_writer_ports

import json
from datetime import datetime, timezone

from ...lore.file_memory_ports import memory_file_port
from ...lore.schemas import Evidence, LoreProposal, ProposalEvidenceRelation,CharacterMemory,MemorySnapshot
from ...lore.validators import require_evidence_transition, require_proposal_transition
from ...repository import FileRepository, read_json
from ...storage import atomic_write


def _dump(model) -> dict:
    return model.model_dump(mode="json")


class FileLoreRepository:
    def __init__(self, backend: FileRepository):
        self.backend = backend

    @writer_file_port
    def _novel_root(self, novel_id: str):
        expected = current_writer_ports()
        if expected is not None and novel_id != expected.binding["project_id"]:
            raise ValueError("GENERATION_WRITER_PROJECT_CHANGED")
        root = self.backend.novels / novel_id
        if not root.is_dir():
            raise FileNotFoundError(novel_id)
        return root

    @writer_file_port
    def _lore_root(self, novel_id: str):
        root = self._novel_root(novel_id) / "lore"
        for name in ("evidence", "proposals", "relations", "memories", "snapshots"):
            expected = current_writer_ports()
            if expected is not None:
                expected.check_owner(self)
                expected.source()
            (root / name).mkdir(parents=True, exist_ok=True)
        return root

    @writer_file_port
    def _find(self, collection: str, object_id: str):
        expected = current_writer_ports()
        novels = [self.backend.novels / expected.binding["project_id"]] if expected is not None else self.backend.novels.iterdir()
        for novel in novels:
            path = novel / "lore" / collection / f"{object_id}.json"
            if path.is_file():
                return path
        raise FileNotFoundError(object_id)

    @staticmethod
    def _write_new(path, item: dict):
        if path.exists():
            raise FileExistsError(path.stem)
        atomic_write(path, json.dumps(item, ensure_ascii=False, indent=2))

    @memory_file_port
    def create_evidence(self, item: dict, *, _file_memory=None) -> dict:
        owner = {"_file_memory": _file_memory} if _file_memory is not None else {}
        model = Evidence.model_validate(item)
        output = _dump(model)
        path = self._lore_root(model.novel_id) / "evidence" / f"{model.id}.json"
        self._write_new(path, output)
        return output

    @memory_file_port
    @writer_file_port
    def get_evidence(self, evidence_id: str, *, _file_memory=None) -> dict:
        owner = {"_file_memory": _file_memory} if _file_memory is not None else {}
        return _dump(Evidence.model_validate(read_json(self._find("evidence", evidence_id), {})))

    @writer_file_port
    def list_evidence(self, novel_id: str) -> list[dict]:
        root = self._lore_root(novel_id) / "evidence"
        return [_dump(Evidence.model_validate(read_json(path, {}))) for path in sorted(root.glob("*.json"))]

    def invalidate_evidence(self, evidence_id: str, reason: str) -> dict:
        path = self._find("evidence", evidence_id)
        current = self.get_evidence(evidence_id)
        require_evidence_transition(current["status"], "INVALIDATED")
        updated = Evidence.model_validate({**current, "status": "INVALIDATED", "invalidation_reason": reason, "updated_at": datetime.now(timezone.utc)})
        output = _dump(updated)
        atomic_write(path, json.dumps(output, ensure_ascii=False, indent=2))
        return output

    @memory_file_port
    def create_proposal(self, item: dict, *, _file_memory=None) -> dict:
        owner = {"_file_memory": _file_memory} if _file_memory is not None else {}
        model = LoreProposal.model_validate(item)
        output = _dump(model)
        path = self._lore_root(model.novel_id) / "proposals" / f"{model.id}.json"
        self._write_new(path, output)
        return output

    @memory_file_port
    @writer_file_port
    def get_proposal(self, proposal_id: str, *, _file_memory=None) -> dict:
        owner = {"_file_memory": _file_memory} if _file_memory is not None else {}
        return _dump(LoreProposal.model_validate(read_json(self._find("proposals", proposal_id), {})))

    @writer_file_port
    def list_proposals(self, novel_id: str, status: str | None = None) -> list[dict]:
        root = self._lore_root(novel_id) / "proposals"
        items = [_dump(LoreProposal.model_validate(read_json(path, {}))) for path in sorted(root.glob("*.json"))]
        return [item for item in items if status is None or item["status"] == status]

    @memory_file_port
    def link_evidence(self, relation: dict, *, _file_memory=None) -> dict:
        owner = {"_file_memory": _file_memory} if _file_memory is not None else {}
        model = ProposalEvidenceRelation.model_validate(relation)
        proposal = self.get_proposal(model.proposal_id, **owner)
        evidence = self.get_evidence(model.evidence_id, **owner)
        if proposal["novel_id"] != evidence["novel_id"]:
            raise ValueError("proposal and evidence must belong to the same novel")
        output = _dump(model)
        path = self._lore_root(proposal["novel_id"]) / "relations" / f"{model.proposal_id}__{model.evidence_id}.json"
        self._write_new(path, output)
        return output

    @memory_file_port
    @writer_file_port
    def list_proposal_evidence(self, proposal_id: str, *, _file_memory=None) -> list[dict]:
        owner = {"_file_memory": _file_memory} if _file_memory is not None else {}
        proposal = self.get_proposal(proposal_id, **owner)
        root = self._lore_root(proposal["novel_id"]) / "relations"
        return [_dump(ProposalEvidenceRelation.model_validate(read_json(path, {}))) for path in sorted(root.glob(f"{proposal_id}__*.json"))]

    def approve_proposal(self, proposal_id: str, approved_payload: dict, reviewer: str) -> dict:
        path = self._find("proposals", proposal_id)
        current = self.get_proposal(proposal_id)
        require_proposal_transition(current["status"], "APPROVED")
        now = datetime.now(timezone.utc)
        updated = LoreProposal.model_validate({**current, "status": "APPROVED", "approved_payload": approved_payload, "reviewed_by": reviewer, "reviewed_at": now, "updated_at": now})
        output = _dump(updated)
        atomic_write(path, json.dumps(output, ensure_ascii=False, indent=2))
        return output

    def reject_proposal(self, proposal_id: str, reviewer: str, reason: str | None = None) -> dict:
        path = self._find("proposals", proposal_id)
        current = self.get_proposal(proposal_id)
        require_proposal_transition(current["status"], "REJECTED")
        now = datetime.now(timezone.utc)
        updated = LoreProposal.model_validate({**current, "status": "REJECTED", "reviewed_by": reviewer, "reviewed_at": now, "rejection_reason": reason, "updated_at": now})
        output = _dump(updated)
        atomic_write(path, json.dumps(output, ensure_ascii=False, indent=2))
        return output

    def create_memory(self,item):
        model=CharacterMemory.model_validate(item);proposal=self.get_proposal(model.proposal_id)
        if proposal["status"]!="APPROVED":raise ValueError("memory requires APPROVED proposal")
        if proposal["novel_id"]!=model.novel_id:raise ValueError("memory and proposal must belong to same novel")
        chars=read_json(self._novel_root(model.novel_id)/"characters"/"characters.json",[])
        if not any(x.get("id")==model.character_id for x in chars):raise FileNotFoundError(model.character_id)
        output=_dump(model);path=self._lore_root(model.novel_id)/"memories"/f"{model.id}.json";self._write_new(path,output);return output
    def get_memory(self,memory_id):return _dump(CharacterMemory.model_validate(read_json(self._find("memories",memory_id),{})))
    def list_character_memories(self,character_id,status=None):
        out=[]
        for novel in self.backend.novels.iterdir():
            for path in sorted((novel/"lore"/"memories").glob("*.json")):
                item=_dump(CharacterMemory.model_validate(read_json(path,{})))
                if item["character_id"]==character_id and (status is None or item["status"]==status):out.append(item)
        return out
    @writer_file_port
    def list_memories(self,novel_id,status=None):
        root=self._lore_root(novel_id)/"memories";items=[_dump(CharacterMemory.model_validate(read_json(p,{}))) for p in sorted(root.glob("*.json"))];return [x for x in items if status is None or x["status"]==status]
    def approve_proposal_with_memory(self,proposal_id,approved_payload,reviewer,memory):
        proposal=self.get_proposal(proposal_id)
        if proposal["status"]!="PENDING":raise ValueError("proposal must be PENDING")
        candidate=CharacterMemory.model_validate({**memory,"proposal_id":proposal_id,"novel_id":proposal["novel_id"]})
        path=self._lore_root(candidate.novel_id)/"memories"/f"{candidate.id}.json"
        try:
            approved=self.approve_proposal(proposal_id,approved_payload,reviewer);created=self.create_memory(candidate.model_dump(mode="json"));return approved,created
        except Exception:
            if path.exists():path.unlink()
            ppath=self._find("proposals",proposal_id);atomic_write(ppath,json.dumps(proposal,ensure_ascii=False,indent=2));raise
    def supersede_memory(self,memory_id,replacement):
        old=self.get_memory(memory_id)
        if old["status"]!="ACTIVE":raise ValueError("only ACTIVE memory can be superseded")
        new=CharacterMemory.model_validate({**replacement,"novel_id":old["novel_id"],"character_id":old["character_id"],"supersedes_id":memory_id})
        created=self.create_memory(new.model_dump(mode="json"));path=self._find("memories",memory_id);old["status"]="SUPERSEDED";old["updated_at"]=datetime.now(timezone.utc).isoformat();atomic_write(path,json.dumps(old,ensure_ascii=False,indent=2));return created
    def retract_memory(self,memory_id,reason):
        item=self.get_memory(memory_id)
        if item["status"]!="ACTIVE":raise ValueError("only ACTIVE memory can be retracted")
        updated=CharacterMemory.model_validate({**item,"status":"RETRACTED","retraction_reason":reason,"updated_at":datetime.now(timezone.utc)});out=_dump(updated);atomic_write(self._find("memories",memory_id),json.dumps(out,ensure_ascii=False,indent=2));return out
    def create_snapshot(self,item):
        model=MemorySnapshot.model_validate(item);output=_dump(model);path=self._lore_root(model.novel_id)/"snapshots"/f"{model.id}.json";self._write_new(path,output);return output
    @memory_file_port
    @writer_file_port
    def list_snapshots(self,novel_id,scope=None, *, _file_memory=None):
        owner = {"_file_memory": _file_memory} if _file_memory is not None else {}
        root=self._lore_root(novel_id)/"snapshots";items=[_dump(MemorySnapshot.model_validate(read_json(p,{}))) for p in sorted(root.glob("*.json"))];return [x for x in items if scope is None or x["scope"]==scope]
    @memory_file_port
    @writer_file_port
    def get_latest_snapshot(self,novel_id,scope,scope_key, *, _file_memory=None):
        owner = {"_file_memory": _file_memory} if _file_memory is not None else {}
        rows=[x for x in self.list_snapshots(novel_id,scope, **owner) if x["scope_key"]==scope_key];return max(rows,key=lambda x:x["version"],default=None)
