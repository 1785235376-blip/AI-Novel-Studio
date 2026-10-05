from __future__ import annotations
import json,re,shutil,uuid
from datetime import datetime,timezone
from pathlib import Path
from .storage import atomic_write
from .file_project_lifecycle import guard_project, project_operation

def now(): return datetime.now(timezone.utc).isoformat()
def read_json(path:Path,default):
    try:return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:return default
def slug(value:str)->str:
    clean=re.sub(r"[^a-zA-Z0-9_-]+","-",value.strip()).strip("-").lower(); return clean or str(uuid.uuid4())[:8]
class FileRepository:
    def __init__(self,data:Path): self.data=data; self.novels=data/"novels"; self.novels.mkdir(parents=True,exist_ok=True)
    def list_novels(self):
        out=[]
        for root in self.novels.iterdir():
            # AtomicPathMutationPort temporarily renames a project into this
            # reserved namespace. It is a rollback copy, never another project.
            # Do not reject generic dot directories or legacy missing metadata.
            if re.fullmatch(r"\..+\.delete-backup-[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", root.name):
                continue
            with project_operation(self.data, root.name, require_exists=False):
                # A concurrent delete may finish after directory enumeration.
                if not root.is_dir():continue
                meta=read_json(root/"novel.json",{}); chapters=self.list_chapters(root.name)
                out.append({"id":root.name,"title":meta.get("title",root.name),"genre":meta.get("genre",""),"status":meta.get("status","Writing"),"chapter_count":len(chapters),"word_count":sum(x["word_count"] for x in chapters),"updated_at":meta.get("updated_at")})
        return out
    def create_novel(self,payload):
        nid=slug(payload.get("id") or payload["title"]); root=self.novels/nid
        with project_operation(self.data, nid, require_exists=False):
            if root.exists(): raise FileExistsError(nid)
            for d in ("chapters","summaries","pending_canon","characters","locations","timeline","style","world","foreshadowing"):(root/d).mkdir(parents=True,exist_ok=True)
            meta={"id":nid,"title":payload["title"],"genre":payload.get("genre",""),"status":"Writing","created_at":now(),"updated_at":now()}; atomic_write(root/"novel.json",json.dumps(meta,ensure_ascii=False,indent=2))
            for path,value in ((root/"characters/characters.json",[]),(root/"locations/locations.json",[]),(root/"timeline/events.json",[]),(root/"foreshadowing.json",[]),(root/"relationships.json",[]),(root/"volumes.json",[]),(root/"scenes.json",[]),(root/"story_routes.json",[]),(root/"outline.json",{}),(root/"secrets.json",[]),(root/"canon.json",[]),(root/"summaries/index.json",[]),(root/"story_state.json",{"volume":1,"chapter":0,"active_characters":[]})): atomic_write(path,json.dumps(value,ensure_ascii=False,indent=2))
            return meta
    @guard_project("nid")
    def get_novel(self,nid):
        root=self.novels/nid
        if not root.exists(): raise FileNotFoundError(nid)
        return read_json(root/"novel.json",{})
    @guard_project("nid")
    def update_novel(self,nid,payload):
        meta=self.get_novel(nid); meta.update({k:v for k,v in payload.items() if k in {"title","genre","status","long_term_summary","writing_goal"}}); meta["updated_at"]=now(); atomic_write(self.novels/nid/"novel.json",json.dumps(meta,ensure_ascii=False,indent=2)); return meta
    @guard_project("nid")
    def delete_novel(self,nid): shutil.rmtree(self.novels/nid)
    @guard_project("nid")
    def list_chapters(self,nid):
        root=self.novels/nid/"chapters"; out=[]
        state=read_json(self.novels/nid/"chapter_state.json",{})
        for p in sorted(root.glob("chapter-*.md")):
            content=p.read_text(encoding="utf-8"); num=int(re.search(r"(\d+)",p.stem).group(1)); first=content.splitlines()[0].lstrip("# ") if content else f"Chapter {num}"
            cid=f"{nid}:{num}"
            out.append({"id":cid,"novel_id":nid,"number":num,"volume":1,"title":first,"word_count":len(re.sub(r"\s+","",content)),"status":"Draft","content":content,"is_archived":bool(state.get(cid,False))})
        order=read_json(self.novels/nid/"chapter_order.json",[]);rank={cid:i for i,cid in enumerate(order)};return sorted(out,key=lambda c:rank.get(c["id"],len(rank)+c["number"]))
    @guard_project("nid")
    def list_archived_chapters(self,nid):
        return [c for c in self.list_chapters(nid) if c.get("is_archived")]
    @guard_project("cid", chapter=True)
    def set_chapter_archived(self,cid,archived,expected_version):
        chapter=self.chapter(cid)
        state_path=self.novels/cid.rsplit(":",1)[0]/"chapter_state.json"
        state=read_json(state_path,{})
        current=bool(state.get(cid,False))
        _,num,path=cid.rsplit(":",1)[0],int(cid.rsplit(":",1)[1]),self.novels/cid.rsplit(":",1)[0]/"documents"/f"chapter-{int(cid.rsplit(':',1)[1]):04d}.json"
        package=read_json(path,{"version":1})
        if expected_version is not None and expected_version != package.get("version",1):
            raise ValueError("VERSION_CONFLICT")
        if current != archived:
            state[cid]=bool(archived); atomic_write(state_path,json.dumps(state,ensure_ascii=False,indent=2))
        return {**chapter,"is_archived":bool(archived)}
    @guard_project("cid", chapter=True)
    def chapter(self,cid):
        nid,num=cid.rsplit(":",1); matches=[x for x in self.list_chapters(nid) if x["number"]==int(num)]
        if not matches: raise FileNotFoundError(cid)
        return matches[0]
    @guard_project("cid", chapter=True)
    def save_chapter(self,cid,payload):
        chapter=self.chapter(cid); content=payload.get("content",chapter["content"]); atomic_write(self.novels/chapter["novel_id"]/"chapters"/f"chapter-{chapter['number']:04d}.md",content); return self.chapter(cid)
    @guard_project("nid")
    def create_chapter(self,nid,payload):
        existing=self.list_chapters(nid); num=payload.get("number") or (max([x["number"] for x in existing],default=0)+1); title=payload.get("title",f"第 {num} 章"); atomic_write(self.novels/nid/"chapters"/f"chapter-{num:04d}.md",f"# {title}\n\n{payload.get('content','')}"); return self.chapter(f"{nid}:{num}")
    @guard_project("nid")
    def data_set(self,nid,name):
        paths={"characters":"characters/characters.json","locations":"locations/locations.json","canon":"canon.json","foreshadowing":"foreshadowing.json","timeline":"timeline/events.json","relationships":"relationships.json","volumes":"volumes.json","scenes":"scenes.json","story_routes":"story_routes.json"}; return read_json(self.novels/nid/paths[name],[])
    @guard_project("nid")
    def secrets_public(self,nid): return [{**s,"content":None,"visibility":s.get("privacy_level","LOCAL_ONLY")} for s in read_json(self.novels/nid/"secrets.json",[])]
repo=FileRepository(__import__('app.config',fromlist=['settings']).settings.data_path())
