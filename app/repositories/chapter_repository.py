from __future__ import annotations
import json,shutil
from threading import RLock
from datetime import datetime,timezone
from pathlib import Path
from ..document import markdown_to_document,document_to_markdown
from ..repository import FileRepository,read_json
from ..storage import atomic_write
class VersionConflict(RuntimeError):
    """Backend-neutral optimistic concurrency conflict."""
    conflict_type = "VERSION_CONFLICT"

    def __init__(self, current, *, resource_id=None, expected_version=None):
        self.current = current
        self.resource_id = resource_id or current.get("id")
        self.expected_version = expected_version
        self.actual_version = current.get("version")
        super().__init__(
            f"Document version conflict for {self.resource_id}: "
            f"expected {self.expected_version}, actual {self.actual_version}"
        )

    def as_dict(self):
        return {"resource_id": self.resource_id, "expected_version": self.expected_version,
                "actual_version": self.actual_version, "type": self.conflict_type}


_FILE_SAVE_LOCKS: dict[str, RLock] = {}
_FILE_SAVE_LOCKS_GUARD = RLock()


def _file_save_lock(path: Path) -> RLock:
    key = str(path.resolve())
    with _FILE_SAVE_LOCKS_GUARD:
        return _FILE_SAVE_LOCKS.setdefault(key, RLock())
class ChapterRepository:
    def __init__(self,backend:FileRepository):self.backend=backend
    def _paths(self,cid):
        nid,num=cid.rsplit(":",1); root=self.backend.novels/nid; return root,int(num),root/"documents"/f"chapter-{int(num):04d}.json"
    def get(self,cid):
        chapter=self.backend.chapter(cid); root,num,path=self._paths(cid)
        if path.exists(): package=read_json(path,{})
        else: package={"chapter_id":cid,"version":1,"document":markdown_to_document(chapter["content"]),"updated_at":datetime.now(timezone.utc).isoformat(),"source":"MIGRATED"}; path.parent.mkdir(parents=True,exist_ok=True);atomic_write(path,json.dumps(package,ensure_ascii=False,indent=2))
        return {**chapter,"content":document_to_markdown(package["document"]),"version":package["version"],"document":package["document"],"updated_at":package.get("updated_at")}
    def save(self,cid,document,expected_version,source="USER",operator="local-user",create_revision=True):
        root,num,path=self._paths(cid)
        with _file_save_lock(path):
            current=self.get(cid)
            if expected_version!=current["version"]:
                raise VersionConflict(current,resource_id=cid,expected_version=expected_version)
            if create_revision:
                history=root/"history"/f"chapter-{num:04d}";history.mkdir(parents=True,exist_ok=True)
                reason=source if source in {"MANUAL_SAVE","AI_ACCEPT","RESTORE","CHAPTER_SWITCH","EXPLICIT_CHECKPOINT"} else "MANUAL_SAVE"
                atomic_write(history/f"v{current['version']:06d}.json",json.dumps({"version":current["version"],"document":current["document"],"timestamp":current.get("updated_at"),"source":source,"reason":reason,"operator":operator},ensure_ascii=False,indent=2))
            package={"chapter_id":cid,"version":current["version"]+1,"document":document,"updated_at":datetime.now(timezone.utc).isoformat(),"source":source,"operator":operator};atomic_write(path,json.dumps(package,ensure_ascii=False,indent=2));self.backend.save_chapter(cid,{"content":document_to_markdown(document)});return self.get(cid)
    def history(self,cid):
        root,num,_=self._paths(cid);return [read_json(p,{}) for p in sorted((root/"history"/f"chapter-{num:04d}").glob("v*.json"),reverse=True)]
    def restore(self,cid,version,expected_version):
        root,num,_=self._paths(cid);item=read_json(root/"history"/f"chapter-{num:04d}"/f"v{version:06d}.json",None)
        if not item:raise FileNotFoundError(version)
        return self.save(cid,item["document"],expected_version,"RESTORE")
    def delete(self,cid):
        root,num,path=self._paths(cid);md=root/"chapters"/f"chapter-{num:04d}.md";md.unlink();path.unlink(missing_ok=True);self._remove_order(root,cid)
    def duplicate(self,cid):
        current=self.get(cid);created=self.backend.create_chapter(current["novel_id"],{"title":current["title"]+" Copy","content":current["content"]});new=self.get(created["id"])
        root,oldnum,_=self._paths(cid);_,newnum,_=self._paths(new["id"]);summary=root/"summaries"/f"chapter-{oldnum:04d}.json"
        if summary.exists():atomic_write(root/"summaries"/f"chapter-{newnum:04d}.json",summary.read_text(encoding="utf-8"))
        index=root/"summaries"/"index.json";items=read_json(index,[]);match=next((x for x in items if x.get("chapter")==oldnum),None)
        if match:items.append({**match,"chapter":newnum});atomic_write(index,json.dumps(items,ensure_ascii=False,indent=2))
        return new
    def rename(self,cid,title,expected_version):
        current=self.get(cid);doc=dict(current["document"]);nodes=list(doc.get("content",[]))
        heading={"type":"heading","attrs":{"level":1},"content":[{"type":"text","text":title}]}
        if nodes and nodes[0].get("type")=="heading":nodes[0]=heading
        else:nodes.insert(0,heading)
        doc["content"]=nodes;return self.save(cid,doc,expected_version,"USER")
    def _order(self,root):
        path=root/"chapter_order.json";default=[c["id"] for c in self.backend.list_chapters(root.name)];return read_json(path,default)
    def _remove_order(self,root,cid):
        order=[x for x in self._order(root) if x!=cid];atomic_write(root/"chapter_order.json",json.dumps(order,ensure_ascii=False,indent=2))
    def move(self,cid,direction):
        root,_,_=self._paths(cid);order=self._order(root)
        for c in self.backend.list_chapters(root.name):
            if c["id"] not in order:order.append(c["id"])
        i=order.index(cid);j=i+(-1 if direction=="up" else 1)
        if 0<=j<len(order):order[i],order[j]=order[j],order[i]
        atomic_write(root/"chapter_order.json",json.dumps(order,ensure_ascii=False,indent=2));return order
