from __future__ import annotations
import json
from pathlib import Path
from ..storage import atomic_write
class GenerationRepository:
    def __init__(self,root:Path):self.root=root/"runtime/jobs";self.root.mkdir(parents=True,exist_ok=True)
    def save(self,item:dict):atomic_write(self.root/f"{item['id']}.json",json.dumps(item,ensure_ascii=False,indent=2))
    def load_all(self):
        out=[]
        for p in self.root.glob("*.json"):
            try:out.append(json.loads(p.read_text(encoding="utf-8")))
            except Exception:continue
        return out
    def get(self,jid):
        path=self.root/f"{jid}.json"
        if not path.exists():raise KeyError(jid)
        return json.loads(path.read_text(encoding="utf-8"))
