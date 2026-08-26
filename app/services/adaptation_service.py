from __future__ import annotations
from datetime import datetime,timezone
from uuid import uuid4
from ..document import document_to_markdown
import re
import json
import hashlib
from ..model_runtime import TextGenerationParameters,TextGenerationRequest,TextModelNodeInput,ModelRuntimeError

TARGETS={"COMMERCIAL","LITERARY","SCREEN","CUSTOM"}
PROFILES={
    "COMMERCIAL":{"focus":"强化冲突、悬念与章节钩子","pacing":"加快关键事件推进","format":"长篇商业小说","constraints":["保留核心人物关系","每章建立明确目标与转折"]},
    "LITERARY":{"focus":"深化人物心理、主题与语言质感","pacing":"允许内省与意象形成节奏","format":"文学小说","constraints":["保留主题核心","避免用情节压缩替代人物变化"]},
    "SCREEN":{"focus":"将叙述转换为可见行动、场景与对白","pacing":"按场景冲突和幕结构重组","format":"影视改编蓝图","constraints":["不可拍摄的内心叙述需外化","保留关键因果链"]},
    "CUSTOM":{"focus":"遵循用户指定的风格与结构要求","pacing":"由改编要求决定","format":"自定义版本","constraints":["未明确要求的核心事实保持不变"]},
}

class AdaptationService:
    def __init__(self,novels,chapters,runtime=None,agent_runner=None):self.novels=novels;self.chapters=chapters;self.runtime=runtime;self.agent_runner=agent_runner
    def list(self,novel_id):return self.novels.list_adaptation_proposals(novel_id)
    def create(self,novel_id,target,title="",instruction=""):
        target=target.upper()
        if target not in TARGETS:raise ValueError("unsupported adaptation target")
        novel=self.novels.get(novel_id);chapters=self.chapters.list(novel_id);now=datetime.now(timezone.utc).isoformat()
        source_versions=[{"chapter_id":c["id"],"version":self.chapters.get(c["id"])["version"]} for c in chapters];profile=PROFILES[target]
        action={"COMMERCIAL":"强化本章冲突与结尾钩子","LITERARY":"深化本章视角人物与主题意象","SCREEN":"拆分为可拍摄场景并外化人物行动","CUSTOM":"按自定义要求改写并保持事实连续"}[target]
        blueprint={**profile,"chapter_map":[{"source_chapter_id":c["id"],"source_title":c["title"],"sequence":i,"action":action,"unit":f"第{((i-1)//3)+1}集" if target=="SCREEN" else f"第{i}章"} for i,c in enumerate(chapters,1)]}
        item={"id":str(uuid4()),"novel_id":novel_id,"source_title":novel["title"],"source_chapter_count":len(chapters),"source_versions":source_versions,"target":target,"title":title.strip() or f"{novel['title']} 改编方案","instruction":instruction.strip(),"blueprint":blueprint,"blueprint_revision":1,"blueprint_history":[],"status":"DRAFT","created_at":now,"updated_at":now}
        return self.novels.save_adaptation_proposal(novel_id,item)
    def approve(self,novel_id,proposal_id):
        item=next((row for row in self.list(novel_id) if row["id"]==proposal_id),None)
        if item is None:raise KeyError(proposal_id)
        if item["status"]!="DRAFT":raise ValueError("adaptation proposal is already decided")
        return self.novels.save_adaptation_proposal(novel_id,{**item,"status":"APPROVED","updated_at":datetime.now(timezone.utc).isoformat()})
    def update_blueprint(self,novel_id,proposal_id,payload):
        item=self.get(novel_id,proposal_id)
        if item["status"]!="DRAFT":raise ValueError("approved adaptation blueprint is frozen")
        current=item["blueprint"];incoming={row.get("source_chapter_id"):row for row in payload.get("chapter_map",[]) if row.get("source_chapter_id")}
        chapter_map=[{**row,"unit":str(incoming.get(row["source_chapter_id"],{}).get("unit",row["unit"]))[:120],"action":str(incoming.get(row["source_chapter_id"],{}).get("action",row["action"]))[:1000]} for row in current["chapter_map"]]
        next_blueprint={"focus":payload["focus"].strip()[:1000],"pacing":payload["pacing"].strip()[:1000],"format":payload["format"].strip()[:200],"constraints":[str(value).strip()[:500] for value in payload.get("constraints",[]) if str(value).strip()][:50],"chapter_map":chapter_map}
        revision=int(item.get("blueprint_revision",1))+1;history=[*item.get("blueprint_history",[]),{"revision":int(item.get("blueprint_revision",1)),"blueprint":current,"saved_at":item["updated_at"]}]
        return self.novels.save_adaptation_proposal(novel_id,{**item,"blueprint":next_blueprint,"blueprint_revision":revision,"blueprint_history":history,"updated_at":datetime.now(timezone.utc).isoformat()})
    def materialize(self,novel_id,proposal_id):
        item=next((row for row in self.list(novel_id) if row["id"]==proposal_id),None)
        if item is None:raise KeyError(proposal_id)
        if item.get("adapted_novel_id"):return self.novels.get(item["adapted_novel_id"])
        if item["status"]!="APPROVED":raise ValueError("adaptation proposal must be approved")
        adapted=self.novels.create({"title":item["title"],"genre":f"Adaptation:{item['target']}"})
        manifest=[]
        for index,source in enumerate(item["source_versions"],1):
            current=self.chapters.get(source["chapter_id"]);document=None
            if current["version"]==source["version"]:document=current["document"]
            else:
                revision=next((row for row in self.chapters.history(source["chapter_id"]) if row["version"]==source["version"]),None)
                if revision:document=revision.get("document")
            if document is None:raise ValueError("source chapter snapshot is unavailable")
            content=re.sub(r"^#{1,6}\s+[^\n]+\n+","",document_to_markdown(document).strip(),count=1).strip()
            created=self.chapters.create(adapted["id"],{"title":current["title"],"content":content,"number":index});mapping=item["blueprint"]["chapter_map"][index-1]
            manifest.append({"id":str(uuid4()),"source_chapter_id":source["chapter_id"],"source_version":source["version"],"target_chapter_id":created["id"],"unit":mapping["unit"],"action":mapping["action"],"status":"PENDING_REWRITE"})
        updated={**item,"status":"MATERIALIZED","adapted_novel_id":adapted["id"],"execution_manifest":manifest,"execution_status":"PENDING_REWRITE","materialized_at":datetime.now(timezone.utc).isoformat(),"updated_at":datetime.now(timezone.utc).isoformat()}
        self.novels.save_adaptation_proposal(novel_id,updated);return adapted
    def get(self,novel_id,proposal_id):
        item=next((row for row in self.list(novel_id) if row["id"]==proposal_id),None)
        if item is None:raise KeyError(proposal_id)
        return item
    def snapshot_chapters(self,novel_id,proposal_id):
        item=self.get(novel_id,proposal_id)
        if item["status"] not in {"APPROVED","MATERIALIZING","MATERIALIZED"}:raise ValueError("adaptation proposal must be approved")
        output=[]
        for source in item["source_versions"]:
            current=self.chapters.get(source["chapter_id"]);document=current["document"] if current["version"]==source["version"] else None
            if document is None:
                revision=next((row for row in self.chapters.history(source["chapter_id"]) if row["version"]==source["version"]),None);document=revision.get("document") if revision else None
            if document is None:raise ValueError("source chapter snapshot is unavailable")
            output.append({"title":current["title"],"document":document})
        return output
    def record_team_materialization(self,novel_id,proposal_id,target,complete=False):
        item=self.get(novel_id,proposal_id);status="MATERIALIZED" if complete else "MATERIALIZING"
        updated={**item,"status":status,"adapted_novel_id":target["project_id"],"adapted_scope":target,"updated_at":datetime.now(timezone.utc).isoformat()}
        if complete:updated["materialized_at"]=updated["updated_at"]
        return self.novels.save_adaptation_proposal(novel_id,updated)
    def record_execution_manifest(self,novel_id,proposal_id,target_chapters):
        item=self.get(novel_id,proposal_id);manifest=[]
        for index,(source,target) in enumerate(zip(item["source_versions"],target_chapters)):
            mapping=item["blueprint"]["chapter_map"][index]
            manifest.append({"id":str(uuid4()),"source_chapter_id":source["chapter_id"],"source_version":source["version"],"target_chapter_id":target["id"],"unit":mapping["unit"],"action":mapping["action"],"status":"PENDING_REWRITE"})
        return self.novels.save_adaptation_proposal(novel_id,{**item,"execution_manifest":manifest,"execution_status":"PENDING_REWRITE","updated_at":datetime.now(timezone.utc).isoformat()})
    def generate_draft(self,novel_id,proposal_id,task_id,mode="deterministic",provider=None,model=None):
        item=self.get(novel_id,proposal_id);tasks=list(item.get("execution_manifest",[]));index=next((i for i,row in enumerate(tasks) if row["id"]==task_id),None)
        if index is None:raise KeyError(task_id)
        task=tasks[index]
        if task["status"] not in {"PENDING_REWRITE","REJECTED","FAILED"}:raise ValueError("adaptation task is not ready for generation")
        source=self.chapters.get(task["source_chapter_id"]);document=source["document"] if source["version"]==task["source_version"] else None
        if document is None:
            revision=next((row for row in self.chapters.history(task["source_chapter_id"]) if row["version"]==task["source_version"]),None);document=revision.get("document") if revision else None
        if document is None:raise ValueError("source chapter snapshot is unavailable")
        source_text=re.sub(r"^#{1,6}\s+[^\n]+\n+","",document_to_markdown(document).strip(),count=1).strip()
        try:
            if mode=="model":
                if not provider or not model:raise ValueError("model generation requires provider and model")
                context={"adaptation_target":item["target"],"blueprint":item["blueprint"],"unit":task["unit"],"action":task["action"],"source_chapter_id":task["source_chapter_id"],"source_version":task["source_version"]}
                prompt=self.agent_runner.build_prompt("writer",context,"Rewrite the source chapter according to the approved adaptation blueprint. Return JSON only with keys: schema, summary, content, source_chapter_id, source_version.",source_text)
                node=self.runtime.prepare_text_route(provider,model,self.runtime.providers.get(provider));request=TextGenerationRequest(provider_id=provider,model_id=model,prompt=prompt,context=context,parameters=TextGenerationParameters(temperature=0.4),metadata={"purpose":"adaptation_rewrite"},job_id=task_id)
                response=node.execute(TextModelNodeInput(request)).response;parsed=json.loads(response.text)
                if parsed.get("schema")!="adaptation_chapter_draft" or parsed.get("source_chapter_id")!=task["source_chapter_id"] or parsed.get("source_version")!=task["source_version"] or not str(parsed.get("content","")).strip():raise ValueError("adaptation draft contract mismatch")
                draft={**parsed,"target_chapter_id":task["target_chapter_id"],"unit":task["unit"],"action":task["action"],"generation_mode":"model","provider":response.provider_id,"model":response.model_id}
            elif mode=="deterministic":draft={"schema":"adaptation_chapter_draft","source_chapter_id":task["source_chapter_id"],"source_version":task["source_version"],"target_chapter_id":task["target_chapter_id"],"unit":task["unit"],"action":task["action"],"content":source_text,"generation_mode":"deterministic-preparation","note":"当前草稿保留锁定原文，等待 Writer/Editor 模型按改编动作完成实质改写。"}
            else:raise ValueError("unsupported adaptation generation mode")
            tasks[index]={**task,"status":"AWAITING_REVIEW","draft":draft,"generated_at":datetime.now(timezone.utc).isoformat()}
        except Exception as exc:
            code=exc.code.value if isinstance(exc,ModelRuntimeError) else "INVALID_ADAPTATION_DRAFT" if isinstance(exc,(ValueError,json.JSONDecodeError)) else "ADAPTATION_GENERATION_FAILED"
            tasks[index]={**task,"status":"FAILED","error_code":code,"error":str(exc),"generated_at":datetime.now(timezone.utc).isoformat()}
        updated={**item,"execution_manifest":tasks,"execution_status":"AWAITING_REVIEW" if tasks[index]["status"]=="AWAITING_REVIEW" else "FAILED","updated_at":datetime.now(timezone.utc).isoformat()};self.novels.save_adaptation_proposal(novel_id,updated);return tasks[index]
    def review_draft(self,novel_id,proposal_id,task_id,decision,note=""):
        if decision not in {"ACCEPTED","REJECTED"}:raise ValueError("invalid adaptation review decision")
        item=self.get(novel_id,proposal_id);tasks=list(item.get("execution_manifest",[]));index=next((i for i,row in enumerate(tasks) if row["id"]==task_id),None)
        if index is None:raise KeyError(task_id)
        if tasks[index]["status"]!="AWAITING_REVIEW":raise ValueError("adaptation task is not awaiting review")
        draft=tasks[index]["draft"];draft_hash=hashlib.sha256(json.dumps(draft,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        tasks[index]={**tasks[index],"status":decision,"review_note":note.strip(),"reviewed_at":datetime.now(timezone.utc).isoformat(),"reviewed_draft_hash":draft_hash,"applied":False}
        statuses={row["status"] for row in tasks};overall="ACCEPTED" if statuses=={"ACCEPTED"} else ("AWAITING_REVIEW" if "AWAITING_REVIEW" in statuses else "IN_PROGRESS")
        updated={**item,"execution_manifest":tasks,"execution_status":overall,"updated_at":datetime.now(timezone.utc).isoformat()};self.novels.save_adaptation_proposal(novel_id,updated);return tasks[index]
    def prepare_apply(self,novel_id,proposal_id,task_id):
        item=self.get(novel_id,proposal_id);tasks=list(item.get("execution_manifest",[]));index=next((i for i,row in enumerate(tasks) if row["id"]==task_id),None)
        if index is None:raise KeyError(task_id)
        task=tasks[index]
        if task["status"]!="ACCEPTED" or task.get("applied"):raise ValueError("adaptation draft is not ready to apply")
        current_hash=hashlib.sha256(json.dumps(task["draft"],ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        if current_hash!=task.get("reviewed_draft_hash"):raise ValueError("adaptation draft changed after review")
        return item,tasks,index,task
    def apply_draft(self,novel_id,proposal_id,task_id):
        item,tasks,index,task=self.prepare_apply(novel_id,proposal_id,task_id);current=self.chapters.get(task["target_chapter_id"]);body=re.sub(r"^#{1,6}\s+[^\n]+\n+","",task["draft"]["content"].strip(),count=1).strip()
        from ..document import markdown_to_document
        saved=self.chapters.save(current["id"],markdown_to_document(f"# {current['title']}\n\n{body}"),current["version"],"ADAPTATION_ACCEPT")
        return self.mark_applied(novel_id,proposal_id,tasks,index,saved["version"])
    def mark_applied(self,novel_id,proposal_id,tasks,index,result_version):
        tasks[index]={**tasks[index],"applied":True,"applied_at":datetime.now(timezone.utc).isoformat(),"result_version":result_version,"status":"APPLIED"}
        overall="APPLIED" if all(row["status"]=="APPLIED" for row in tasks) else "IN_PROGRESS";item=self.get(novel_id,proposal_id)
        self.novels.save_adaptation_proposal(novel_id,{**item,"execution_manifest":tasks,"execution_status":overall,"updated_at":datetime.now(timezone.utc).isoformat()});return tasks[index]
