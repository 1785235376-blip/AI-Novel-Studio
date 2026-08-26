from __future__ import annotations
import json
from ...repository import FileRepository,read_json
from ...storage import atomic_write,append_pending

class FileCanonRepository:
    def __init__(self,backend:FileRepository):self.backend=backend
    def list(self,novel_id):return read_json(self.backend.novels/novel_id/"canon.json",[])
    def _find(self,pending_id):
        for root in self.backend.novels.iterdir():
            path=root/"pending_canon"/f"{pending_id}.json"
            if path.exists():return root,path,read_json(path,{})
        raise FileNotFoundError(pending_id)
    def list_pending(self,novel_id):
        root=self.backend.novels/novel_id/"pending_canon";return [item for p in root.glob("*.json") if (item:=read_json(p,{})).get("status")=="PENDING"]
    def get_pending(self,pending_id):return self._find(pending_id)[2]
    def save_pending(self,item):
        root=self.backend.novels/item["novel_id"]
        if "id" not in item:raise ValueError("pending canon id is required")
        append_pending(root,item);return item
    def approve(self,pending_id,proposals=None):
        root,path,item=self._find(pending_id)
        if proposals is not None:item["proposals"]=proposals
        item["status"]="APPROVED";atomic_write(path,json.dumps(item,ensure_ascii=False,indent=2))
        canon=read_json(root/"canon.json",[]);canon.extend([{**p,"source":f"pending:{pending_id}","confidence":"USER_APPROVED"} for p in item.get("proposals",[])]);atomic_write(root/"canon.json",json.dumps(canon,ensure_ascii=False,indent=2));return item
    def reject(self,pending_id):
        _,path,item=self._find(pending_id);item["status"]="REJECTED";atomic_write(path,json.dumps(item,ensure_ascii=False,indent=2));return item
