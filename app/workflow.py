from __future__ import annotations
import json, uuid
from pathlib import Path
from .context import build_context
from .review import deterministic_review
from .storage import atomic_write, append_pending
from .file_project_lifecycle import project_operation

class NovelWorkflow:
    """Legacy synthetic fixture writer, not an author-generation entry point.

    Real generation must use JobManager's guarded Draft/Accept flow. This old
    file-format harness remains available only with explicit draft_override.
    """
    def __init__(self,data_root:Path,router=None): self.data_root=data_root; self.router=router
    def run(self,novel_id:str,chapter:int,instruction:str,profile:str="LOCAL_ONLY",draft_override:str|None=None)->dict:
        if draft_override is None:
            raise RuntimeError("LEGACY_WORKFLOW_DISABLED: use guarded generation Draft/Accept")
        with project_operation(self.data_root, novel_id):
            return self._run_fixture(novel_id, chapter, instruction, profile, draft_override)

    def _run_fixture(self, novel_id, chapter, instruction, profile, draft_override):
        from .repository import FileRepository
        from .repositories.file.chapter import FileChapterRepository
        from .services.chapter_service import ChapterService
        context=build_context(self.data_root,novel_id,chapter,instruction,cloud=profile!="LOCAL_ONLY")
        if draft_override is not None: draft=draft_override; generation={"provider":"test_override","model":"none"}
        issues=deterministic_review(draft,context); root=self.data_root/"novels"/novel_id
        chapter_path=root/"chapters"/f"chapter-{chapter:04d}.md"
        chapters=ChapterService(FileChapterRepository(FileRepository(self.data_root)))
        if chapter_path.exists():
            # A numeric fixture call may only update its original numeric owner.
            # In particular, a typed chapter at this storage slot is not an alias.
            current=chapters.get(f"{novel_id}:{chapter}")
            saved=chapters.save(current["id"], {"content":draft,"version":current["version"]})
        else:
            saved=chapters.create(novel_id,{"number":chapter,"content":draft})
        context["chapter_id"]=saved["id"]
        summary={**chapters.save_summary(novel_id,saved["id"],draft[:240]),"status":"DRAFT_SAVED"}
        atomic_write(root/"summaries"/f"chapter-{chapter:04d}.json",json.dumps(summary,ensure_ascii=False,indent=2))
        pending={"id":str(uuid.uuid4()),"novel_id":novel_id,"chapter":chapter,"chapter_id":saved["id"],"status":"PENDING","proposals":[],"source":"archivist"}; append_pending(root,pending)
        return {"status":"NEEDS_REVISION" if issues else "COMPLETED","chapter_path":str(chapter_path),"issues":issues,"pending_canon_id":pending["id"],"generation":generation,"context":context}

