from __future__ import annotations
import json
from pathlib import Path
from ...storage import atomic_write


class FileNarrativeRepository:
    def __init__(self,root:Path): self.root=Path(root)
    def _path(self,project): return self.root/f"{project}.json"
    def _read(self,project):
        p=self._path(project)
        empty={"threads":[],"foreshadowing":[],"events":[],"expectations":[],"findings":[],"mysteries":[],"character_goals":[],"chapter_links":[],"proposals":[]}
        return {**empty,**json.loads(p.read_text(encoding="utf-8"))} if p.exists() else empty
    def _write(self,project,data): atomic_write(self._path(project),json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2))
    def create(self,project,kind,payload):
        data=self._read(project); rows=data[kind]
        old=next((x for x in rows if x["id"]==payload["id"]),None)
        if old:return old
        rows.append(payload);rows.sort(key=lambda x:x["id"]);self._write(project,data);return payload
    def get(self,project,kind,item_id):
        item=next((x for x in self._read(project)[kind] if x["id"]==item_id),None)
        if not item:raise KeyError(item_id)
        return item
    def list(self,project,kind):return self._read(project)[kind]
    def transition(self,project,kind,item_id,status,event):
        data=self._read(project);item=next((x for x in data[kind] if x["id"]==item_id),None)
        if not item:raise KeyError(item_id)
        if not any(x["id"]==event["id"] for x in data["events"]):data["events"].append(event);data["events"].sort(key=lambda x:(x.get("created_at",""),x["id"]))
        item["status"]=status
        if kind=="threads" and event["id"] not in item.setdefault("event_ids",[]):item["event_ids"].append(event["id"])
        if kind=="foreshadowing" and status=="PAYOFF":item["payoff_event_id"]=event["id"]
        self._write(project,data);return item
    def set_status(self,project,kind,item_id,status):
        data=self._read(project);item=next((x for x in data[kind] if x["id"]==item_id),None)
        if not item:raise KeyError(item_id)
        item["status"]=status;self._write(project,data);return item
    def update(self,project,kind,item_id,payload):
        data=self._read(project);item=next((x for x in data[kind] if x["id"]==item_id),None)
        if not item:raise KeyError(item_id)
        item.clear();item.update(payload);self._write(project,data);return item
    def record_progress(self,project,kind,item_id,updated,event,link):
        data=self._read(project);item=next((x for x in data[kind] if x["id"]==item_id),None)
        if not item:raise KeyError(item_id)
        old=next((x for x in data["chapter_links"] if x["id"]==link["id"]),None)
        if old:return old
        item.clear();item.update(updated)
        if not any(x["id"]==event["id"] for x in data["events"]):data["events"].append(event);data["events"].sort(key=lambda x:(x.get("created_at",""),x["id"]))
        data["chapter_links"].append(link);data["chapter_links"].sort(key=lambda x:x["id"]);self._write(project,data);return link
    def get_proposal_by_fingerprint(self,project,fingerprint):return next((x for x in self._read(project)["proposals"] if x["fingerprint"]==fingerprint),None)
    def accept_proposal_atomic(self,project,proposal_id,kind,item_id,updated,event,link,accepted):
        data=self._read(project);proposal=next((x for x in data["proposals"] if x["id"]==proposal_id),None);item=next((x for x in data[kind] if x["id"]==item_id),None)
        if not proposal or not item:raise KeyError(proposal_id if not proposal else item_id)
        if proposal["status"]!="PENDING":raise ValueError("proposal must be PENDING")
        item.clear();item.update(updated);data["events"].append(event);data["events"].sort(key=lambda x:(x.get("created_at",""),x["id"]));data["chapter_links"].append(link);data["chapter_links"].sort(key=lambda x:x["id"]);proposal.clear();proposal.update(accepted);self._write(project,data);return proposal
