from __future__ import annotations
import json, uuid
from pathlib import Path
from .context import build_context
from .review import deterministic_review
from .storage import atomic_write, append_pending

class NovelWorkflow:
    def __init__(self,data_root:Path,router=None): self.data_root=data_root; self.router=router
    def run(self,novel_id:str,chapter:int,instruction:str,profile:str="LOCAL_ONLY",draft_override:str|None=None)->dict:
        context=build_context(self.data_root,novel_id,chapter,instruction,cloud=profile!="LOCAL_ONLY")
        if draft_override is not None: draft=draft_override; generation={"provider":"test_override","model":"none"}
        elif not self.router: raise RuntimeError("No model router configured")
        else:
            beats=self.router.generate("planner",json.dumps(context,ensure_ascii=False)).text
            result=self.router.generate("writer",json.dumps({"context":context,"beats":beats},ensure_ascii=False)); draft=result.text; generation={"provider":result.provider,"model":result.model,"input_tokens":result.input_tokens,"output_tokens":result.output_tokens}
        issues=deterministic_review(draft,context); root=self.data_root/"novels"/novel_id
        chapter_path=root/"chapters"/f"chapter-{chapter:04d}.md"; atomic_write(chapter_path,draft)
        summary={"chapter":chapter,"summary":draft[:240],"status":"DRAFT_SAVED"}; atomic_write(root/"summaries"/f"chapter-{chapter:04d}.json",json.dumps(summary,ensure_ascii=False,indent=2))
        pending={"id":str(uuid.uuid4()),"novel_id":novel_id,"chapter":chapter,"status":"PENDING","proposals":[],"source":"archivist"}; append_pending(root,pending)
        return {"status":"NEEDS_REVISION" if issues else "COMPLETED","chapter_path":str(chapter_path),"issues":issues,"pending_canon_id":pending["id"],"generation":generation,"context":context}

