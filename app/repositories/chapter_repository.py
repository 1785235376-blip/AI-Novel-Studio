from __future__ import annotations
from ..runtime_events import committed_change
import json
from pathlib import Path
from datetime import datetime,timezone
from ..document import markdown_to_document,document_to_markdown,duplicate_document
from ..repository import FileRepository,read_json
from ..storage import atomic_write
from .. import chapter_identity
from ..file_project_lifecycle import guard_project, project_operation
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


def _file_save_lock(path: Path):
    """Keep audited chapter snapshot/rollback in the same lifecycle guard.

    Callers pass either a document package or the project chapter-order file.
    Lock order for audited operations is authorization lock, then project lock.
    """
    root = path.parent if path.name == "chapter_order.json" else path.parent.parent
    return project_operation(root.parent.parent, root.name)


class ChapterRepository:
    def __init__(self,backend:FileRepository):self.backend=backend
    @guard_project("cid", chapter=True)
    def _paths(self,cid):
        nid,token=cid.rsplit(":",1);root=self.backend.novels/nid;num=chapter_identity.resolve(root,token)
        return root,num,root/"documents"/f"chapter-{num:04d}.json"
    @guard_project("cid", chapter=True)
    def get(self,cid):
        chapter=self.backend.chapter(cid); root,num,path=self._paths(cid)
        if path.exists(): package=read_json(path,{})
        else: package={"chapter_id":cid,"version":1,"document":markdown_to_document(chapter["content"]),"updated_at":datetime.now(timezone.utc).isoformat(),"source":"MIGRATED"}; path.parent.mkdir(parents=True,exist_ok=True);atomic_write(path,json.dumps(package,ensure_ascii=False,indent=2))
        if package.get("chapter_id") != chapter["id"]:
            raise chapter_identity.ChapterIdentityConflict(f"CHAPTER_DOCUMENT_IDENTITY_MISMATCH: {cid}")
        return {**chapter,"content":document_to_markdown(package["document"]),"version":package["version"],"document":package["document"],"updated_at":package.get("updated_at")}
    @committed_change("CHAPTER")
    @guard_project("cid", chapter=True)
    def save(self,cid,document,expected_version,source="USER",operator="local-user",create_revision=True):
        root,num,path=self._paths(cid)
        current=self.get(cid)
        if expected_version!=current["version"]:
            raise VersionConflict(current,resource_id=cid,expected_version=expected_version)
        from ..revision_constraints import preserve_revision_constraints
        document = preserve_revision_constraints(current["document"], document, source)
        # Validate/project before touching history, JSON authority or markdown.
        markdown = document_to_markdown(document)
        if create_revision:
            history=root/"history"/f"chapter-{num:04d}";history.mkdir(parents=True,exist_ok=True)
            reason=source if source in {"MANUAL_SAVE","AI_ACCEPT","RESTORE","CHAPTER_SWITCH","EXPLICIT_CHECKPOINT"} else "MANUAL_SAVE"
            atomic_write(history/f"v{current['version']:06d}.json",json.dumps({"version":current["version"],"document":current["document"],"timestamp":current.get("updated_at"),"source":source,"reason":reason,"operator":operator},ensure_ascii=False,indent=2))
        package={"chapter_id":cid,"version":current["version"]+1,"document":document,"updated_at":datetime.now(timezone.utc).isoformat(),"source":source,"operator":operator};atomic_write(path,json.dumps(package,ensure_ascii=False,indent=2));self.backend.save_chapter(cid,{"content":markdown});return self.get(cid)
    @guard_project("cid", chapter=True)
    def history(self,cid):
        self.backend.chapter(cid)
        root,num,_=self._paths(cid)
        chapter_identity.require_history_owned(root,num)
        return [read_json(p,{}) for p in sorted((root/"history"/f"chapter-{num:04d}").glob("v*.json"),reverse=True)]
    @guard_project("cid", chapter=True)
    def restore(self,cid,version,expected_version):
        self.backend.chapter(cid)
        root,num,_=self._paths(cid)
        chapter_identity.require_history_owned(root,num)
        item=read_json(root/"history"/f"chapter-{num:04d}"/f"v{version:06d}.json",None)
        if not item:raise FileNotFoundError(version)
        return self.save(cid,item["document"],expected_version,"RESTORE")
    @committed_change("CHAPTER")
    @guard_project("cid", chapter=True)
    def delete(self,cid):
        self.backend.chapter(cid)
        root,num,path=self._paths(cid)
        chapter_identity.transition(root,num,"deleted")
        md=root/"chapters"/f"chapter-{num:04d}.md";md.unlink();path.unlink(missing_ok=True);self._remove_order(root,cid)
    @guard_project("cid", chapter=True)
    def duplicate(self,cid):
        current = self.get(cid)
        title = current["title"] + " Copy"
        document = duplicate_document(current["document"], title)
        markdown = document_to_markdown(document)
        created = self.backend.create_chapter(current["novel_id"], {"title": title, "content": ""})
        _, _, path = self._paths(created["id"])
        package = {"chapter_id": created["id"], "version": 1, "document": document,
                   "updated_at": datetime.now(timezone.utc).isoformat(), "source": "DUPLICATE"}
        atomic_write(path, json.dumps(package, ensure_ascii=False, indent=2))
        self.backend.save_chapter(created["id"], {"content": markdown})
        new = self.get(created["id"])
        root,oldnum,_=self._paths(cid);_,newnum,_=self._paths(new["id"]);summary=root/"summaries"/f"chapter-{oldnum:04d}.json"
        if summary.exists():
            copied=read_json(summary,{})
            if isinstance(copied,dict):
                if "chapter" in copied or ":~" in new["id"]:copied["chapter"]=newnum
                if "chapter_id" in copied or ":~" in new["id"]:copied["chapter_id"]=new["id"]
            atomic_write(root/"summaries"/f"chapter-{newnum:04d}.json",json.dumps(copied,ensure_ascii=False,indent=2))
        index=root/"summaries"/"index.json";items=read_json(index,[]);match=next((x for x in items if x.get("chapter")==oldnum),None)
        if match:
            copied={**match,"chapter":newnum}
            if "chapter_id" in copied or ":~" in new["id"]:copied["chapter_id"]=new["id"]
            items.append(copied);atomic_write(index,json.dumps(items,ensure_ascii=False,indent=2))
        return new
    @guard_project("cid", chapter=True)
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
    @guard_project("cid", chapter=True)
    def move(self,cid,direction):
        self.backend.chapter(cid)
        root,_,_=self._paths(cid);order=self._order(root)
        for c in self.backend.list_chapters(root.name):
            if c["id"] not in order:order.append(c["id"])
        i=order.index(cid);j=i+(-1 if direction=="up" else 1)
        if 0<=j<len(order):order[i],order[j]=order[j],order[i]
        atomic_write(root/"chapter_order.json",json.dumps(order,ensure_ascii=False,indent=2));return order
