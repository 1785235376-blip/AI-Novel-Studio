from __future__ import annotations
import json
from ..repository import FileRepository,read_json
from ..storage import atomic_write
class CanonRepository:
    def __init__(self,backend:FileRepository):self.backend=backend
    def approve(self,nid,proposal):
        path=self.backend.novels/nid/"canon.json";items=read_json(path,[]);items.append(proposal);atomic_write(path,json.dumps(items,ensure_ascii=False,indent=2));return proposal

