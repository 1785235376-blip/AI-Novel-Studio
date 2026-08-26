from __future__ import annotations
import base64
import json
import re
import uuid
from datetime import datetime, timezone
from ..import_parsers import decode_base64,docx_to_text,pdf_to_text
from ..export_formats import novel_to_docx, novel_to_epub
from ..pdf_export import novel_to_pdf
from ..industry_export_formats import (
    screenplay_to_docx,
    screenplay_to_fountain,
    screenplay_to_markdown,
    screenplay_to_package,
    shot_list_to_csv,
    shot_list_to_package,
    storyboard_to_html,
    storyboard_to_package,
)
from ..repositories.interfaces import NovelRepositoryProtocol,ChapterRepositoryProtocol
class NovelService:
    def __init__(self,novels:NovelRepositoryProtocol,chapters:ChapterRepositoryProtocol):self.novels=novels;self.chapters=chapters
    def list(self):return self.novels.list()
    def create(self,payload):return self.novels.create(payload)
    def get(self,nid):return self.novels.get(nid)
    def update(self,nid,payload):return self.novels.update(nid,payload)
    def writing_goal(self,nid):
        novel=self.get(nid); chapters=self.chapters.list(nid)
        goal=novel.get("writing_goal") or {"target_words":0,"target_chapters":0,"deadline":""}
        words=sum(int(item.get("word_count") or len(str(item.get("content") or "").replace(" ",""))) for item in chapters)
        chapter_count=len(chapters)
        result={**goal,"target_words":int(goal.get("target_words") or 0),"target_chapters":int(goal.get("target_chapters") or 0),"current_words":words,"current_chapters":chapter_count}
        result["words_progress"]=round(min(words/result["target_words"],1),4) if result["target_words"] else 0
        result["chapters_progress"]=round(min(chapter_count/result["target_chapters"],1),4) if result["target_chapters"] else 0
        return result
    def update_writing_goal(self,nid,payload):
        target_words=int(payload.get("target_words") or 0); target_chapters=int(payload.get("target_chapters") or 0)
        if target_words<0 or target_chapters<0: raise ValueError("writing goals must be non-negative")
        self.update(nid,{"writing_goal":{"target_words":target_words,"target_chapters":target_chapters,"deadline":str(payload.get("deadline") or "")}})
        return self.writing_goal(nid)
    def delete(self,nid):return self.novels.delete(nid)
    def data_set(self,nid,name):return self.novels.get_data_set(nid,name)
    def upsert_character(self,nid,character_id,payload):return self.novels.upsert_character(nid,character_id,payload)
    def upsert_location(self,nid,location_id,payload):return self.novels.upsert_location(nid,location_id,payload)
    def upsert_timeline_event(self,nid,event_id,payload):return self.novels.upsert_timeline_event(nid,event_id,payload)
    def upsert_foreshadowing(self,nid,foreshadowing_id,payload):return self.novels.upsert_foreshadowing(nid,foreshadowing_id,payload)
    def upsert_relationship(self,nid,relationship_id,payload):return self.novels.upsert_relationship(nid,relationship_id,payload)
    def outline(self,nid):return self.novels.get_outline(nid)
    def update_outline(self,nid,payload):return self.novels.update_outline(nid,payload)
    def upsert_volume(self,nid,volume_id,payload):return self.novels.upsert_volume(nid,volume_id,payload)
    def upsert_scene(self,nid,scene_id,payload):return self.novels.upsert_scene(nid,scene_id,payload)
    def upsert_story_route(self,nid,route_id,payload):return self.novels.upsert_story_route(nid,route_id,payload)
    def public_secrets(self,nid):return self.novels.get_public_secrets(nid)
    def review_import_knowledge(self,nid,decision,candidates):
        if decision not in {"ACCEPTED","REJECTED"}: raise ValueError("invalid knowledge review decision")
        if decision == "REJECTED": return {"decision": decision, "applied": {"characters": [], "locations": [], "timeline_events": [], "foreshadowing": []}}
        applied={"characters": [], "locations": [], "timeline_events": [], "foreshadowing": []}
        for item in candidates.get("characters", []):
            name=str(item.get("name") or "").strip()
            if name:
                item_id=str(item.get("id") or uuid.uuid5(uuid.NAMESPACE_URL, f"import:character:{nid}:{name}"))
                applied["characters"].append(self.upsert_character(nid,item_id,{"name":name,"status":"ALIVE","source":"IMPORT_REVIEW"}))
        for item in candidates.get("locations", []):
            name=str(item.get("name") or "").strip()
            if name:
                item_id=str(item.get("id") or uuid.uuid5(uuid.NAMESPACE_URL, f"import:location:{nid}:{name}"))
                applied["locations"].append(self.upsert_location(nid,item_id,{"name":name,"status":"ACTIVE","source":"IMPORT_REVIEW"}))
        for item in candidates.get("timeline_events", []):
            title=str(item.get("title") or "").strip()
            if title:
                item_id=str(item.get("id") or uuid.uuid5(uuid.NAMESPACE_URL, f"import:event:{nid}:{title}:{item.get('chapter_number',0)}"))
                applied["timeline_events"].append(self.upsert_timeline_event(nid,item_id,{"title":title,"sequence":int(item.get("chapter_number") or 1),"description":str(item.get("description") or ""),"status":"CONFIRMED","source":"IMPORT_REVIEW"}))
        for item in candidates.get("foreshadowing", []):
            title=str(item.get("title") or "").strip()
            if title:
                item_id=str(item.get("id") or uuid.uuid5(uuid.NAMESPACE_URL, f"import:foreshadowing:{nid}:{title}"))
                applied["foreshadowing"].append(self.upsert_foreshadowing(nid,item_id,{"title":title,"description":str(item.get("evidence") or ""),"status":"OPEN","source":"IMPORT_REVIEW"}))
        return {"decision": decision, "applied": applied}

    @staticmethod
    def _knowledge_candidates(chapters):
        """Produce reviewable candidates; never writes entities during import."""
        characters, locations, events, foreshadowing = {}, {}, [], []
        name_pattern = re.compile(r"(?<![\u4e00-\u9fff])([\u4e00-\u9fff]{2,4})(?=(?:说|道|问|回答|看见|走向|转身|点头|摇头))")
        location_pattern = re.compile(r"([\u4e00-\u9fff]{2,12}(?:城|镇|村|港|岛|宫|府|山|河|学院|基地|大陆))")
        for number, chapter in enumerate(chapters, 1):
            text = chapter["content"]
            evidence = text[:240]
            for match in name_pattern.finditer(text):
                name = match.group(1).rstrip("说说道问回答看见走向转身点头摇头")
                if len(name) < 2: continue
                characters.setdefault(name, {"name": name, "evidence": evidence, "chapter_number": number, "confidence": 0.55})
            for match in location_pattern.finditer(text):
                raw_name = match.group(1)
                marker = re.search(r"(学院|基地|大陆|城|镇|村|港|岛|宫|府|山|河)$", raw_name)
                if not marker: continue
                width = len(marker.group(1)) + 2
                name = raw_name[-width:]
                name = name.lstrip("\u4e86\u5230\u5728\u4e8e\u5f80\u8fdb\u5165")
                locations.setdefault(name, {"name": name, "evidence": evidence, "chapter_number": number, "confidence": 0.5})
            if text:
                events.append({"title": chapter["title"], "description": text[:240], "chapter_number": number, "confidence": 0.35})
            for match in re.finditer(r"(?:总有一天|迟早|秘密|真相|未完|伏笔|线索)[^。！？\n]{0,80}", text):
                foreshadowing.append({"title": match.group(0)[:80], "evidence": evidence, "chapter_number": number, "confidence": 0.4})
        return {"characters": list(characters.values()), "locations": list(locations.values()), "timeline_events": events, "foreshadowing": foreshadowing}
    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _asset_references(value):
        """Collect explicit asset identifiers from a serialisable snapshot.

        Only fields whose names communicate an asset reference are inspected;
        arbitrary chapter prose is never scanned for UUID-like strings.
        """
        references = set()

        def visit(node, key=""):
            if isinstance(node, dict):
                for child_key, child in node.items():
                    lowered = str(child_key).lower()
                    if lowered in {"asset_id", "reference_asset_id", "source_asset_id", "target_asset_id"} and isinstance(child, str) and child.strip():
                        references.add(child.strip())
                    elif lowered in {"asset_ids", "reference_asset_ids", "asset_refs", "assets"} and isinstance(child, (list, tuple, set)):
                        for entry in child:
                            if isinstance(entry, str) and entry.strip():
                                references.add(entry.strip())
                            elif isinstance(entry, dict):
                                visit(entry, lowered)
                    visit(child, lowered)
            elif isinstance(node, (list, tuple)):
                for child in node:
                    visit(child, key)

        visit(value)
        return sorted(references)

    def export_snapshot(self, nid, *, asset_library=None, format: str | None = None):
        """Capture an immutable, provider-free export input snapshot.

        The snapshot contains only project data needed by deterministic
        exporters and asset metadata (never binary bytes).  It is persisted by
        :class:`ExportJobService` at queue creation, so edits made while a job
        is running cannot change its output.
        """
        meta = dict(self.get(nid))
        chapters = [dict(item) for item in self.chapters.list(nid)]
        datasets = {}
        for name in ("characters", "locations", "canon", "foreshadowing", "timeline", "relationships", "volumes", "scenes", "story_routes", "outline"):
            try:
                value = self.data_set(nid, name) if name != "outline" else self.outline(nid)
            except (FileNotFoundError, KeyError):
                value = {} if name == "outline" else []
            datasets[name] = value
        try:
            screenplays = [dict(item) for item in self.novels.list_screenplays(nid)]
        except (FileNotFoundError, AttributeError):
            screenplays = []
        source = {"novel": meta, "chapters": chapters, "datasets": datasets, "screenplays": screenplays}
        refs = self._asset_references(source)
        resources = []
        missing = []
        for asset_id in refs:
            if asset_library is None:
                missing.append({"id": asset_id, "reason": "asset library unavailable"})
                continue
            try:
                asset = asset_library.get(asset_id)
            except (FileNotFoundError, OSError):
                missing.append({"id": asset_id, "reason": "asset not found"})
                continue
            if str(asset.get("novel_id")) != str(nid):
                missing.append({"id": asset_id, "reason": "asset belongs to another project"})
                continue
            resources.append({
                "id": asset_id,
                "status": "AVAILABLE",
                "filename": asset.get("filename"),
                "media_type": asset.get("media_type"),
                "size": asset.get("size"),
                "sha256": asset.get("sha256"),
            })
        return {
            "schema_version": 1,
            "snapshot_id": str(uuid.uuid4()),
            "captured_at": self._now(),
            "novel_id": nid,
            "format": str(format or "").lower().strip() or None,
            "source": source,
            "source_versions": {
                "novel_updated_at": meta.get("updated_at"),
                "chapters": [{"id": c.get("id"), "version": c.get("version"), "updated_at": c.get("updated_at")} for c in chapters],
            },
            "resource_manifest": {
                "referenced": refs,
                "available": resources,
                "missing": missing,
                "missing_count": len(missing),
            },
        }

    def _export_data(self, nid, meta, chapters, format, *, screenplays=None, progress_callback=None, snapshot=None, resource_loader=None, resource_policy="allow_missing", screenplay_id=None):
        format = str(format or "json").lower().strip()
        if format=="markdown":return {"format":"markdown","filename":f"{nid}.md","content":"\n\n---\n\n".join(f"# {c.get('title','')}\n\n{c.get('content','')}" for c in chapters)}
        if format in {"txt", "text"}:
            content = "\n\n".join(f"{c.get('title','')}\n\n{c.get('content','')}" for c in chapters)
            return {"format":"txt","filename":f"{nid}.txt","content":content}
        if format in {"docx", "word"}:
            binary = novel_to_docx(meta.get("title", ""), chapters)
            return {
                "format": "docx",
                "filename": f"{nid}.docx",
                "media_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "content_base64": base64.b64encode(binary).decode("ascii"),
                "content_encoding": "base64",
            }
        if format == "pdf":
            binary = novel_to_pdf(
                meta.get("title", ""),
                chapters,
                progress_callback=progress_callback,
            )
            return {
                "format": "pdf",
                "filename": f"{nid}.pdf",
                "media_type": "application/pdf",
                "content_base64": base64.b64encode(binary).decode("ascii"),
                "content_encoding": "base64",
            }
        if format == "epub":
            binary = novel_to_epub(meta.get("title", ""), chapters, nid)
            return {
                "format": "epub",
                "filename": f"{nid}.epub",
                "media_type": "application/epub+zip",
                "content_base64": base64.b64encode(binary).decode("ascii"),
                "content_encoding": "base64",
            }
        if format in {"screenplay-standard", "screenplay-fountain", "screenplay-docx", "screenplay-package", "shot-list-package", "storyboard-html", "storyboard-package"}:
            rows = screenplays if screenplays is not None else self.novels.list_screenplays(nid)
            if not rows:
                raise ValueError("screenplay export requires a screenplay")
            if screenplay_id:
                screenplay = next((row for row in rows if str(row.get("id")) == str(screenplay_id)), None)
                if screenplay is None:
                    raise ValueError("screenplay not found")
            else:
                screenplay = rows[-1]
            snapshot_data = snapshot if isinstance(snapshot, dict) else {}
            resource_manifest = snapshot_data.get("resource_manifest") or {}
            industry_kwargs = {
                "title": screenplay.get("title", meta.get("title", "")),
                "novel_id": nid,
                "snapshot_id": snapshot_data.get("snapshot_id", ""),
                "source_versions": snapshot_data.get("source_versions", {}),
                "resource_manifest": resource_manifest,
                "resource_policy": resource_policy,
            }
            common_meta = {"schema_version": 1, "format_version": "1.0", "resource_manifest": resource_manifest}
            if format in {"screenplay-standard", "screenplay-fountain"}:
                return {"format": "screenplay-standard", "filename": f"{nid}-screenplay.fountain", "media_type": "text/x-fountain", "content": screenplay_to_fountain(screenplay, **industry_kwargs), "industry": {**common_meta, "format_version": "Fountain 1.1"}}
            if format == "screenplay-docx":
                binary = screenplay_to_docx(screenplay, **industry_kwargs)
                return {"format": "screenplay-docx", "filename": f"{nid}-screenplay.docx", "media_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "content_base64": base64.b64encode(binary).decode("ascii"), "content_encoding": "base64", "industry": common_meta}
            if format == "screenplay-package":
                binary = screenplay_to_package(screenplay, resource_loader=resource_loader, **industry_kwargs)
                return {"format": "screenplay-package", "filename": f"{nid}-screenplay-package.zip", "media_type": "application/zip", "content_base64": base64.b64encode(binary).decode("ascii"), "content_encoding": "base64", "industry": common_meta}
            if format == "shot-list-package":
                binary = shot_list_to_package(screenplay, resource_loader=resource_loader, **industry_kwargs)
                return {"format": "shot-list-package", "filename": f"{nid}-shot-list-package.zip", "media_type": "application/zip", "content_base64": base64.b64encode(binary).decode("ascii"), "content_encoding": "base64", "industry": common_meta}
            if format == "storyboard-html":
                content = storyboard_to_html(screenplay, **industry_kwargs).decode("utf-8")
                return {"format": "storyboard-html", "filename": f"{nid}-storyboard.html", "media_type": "text/html", "content": content, "industry": common_meta}
            binary = storyboard_to_package(screenplay, resource_loader=resource_loader, **industry_kwargs)
            return {"format": "storyboard-package", "filename": f"{nid}-storyboard-package.zip", "media_type": "application/zip", "content_base64": base64.b64encode(binary).decode("ascii"), "content_encoding": "base64", "industry": common_meta}
        if format in {"screenplay", "shot-list", "storyboard"}:
            rows = screenplays if screenplays is not None else self.novels.list_screenplays(nid)
            if not rows: raise ValueError("screenplay export requires a screenplay")
            screenplay = rows[-1]
            if format == "screenplay":
                content = "\n\n".join(f"INT./EXT. {scene.get('location') or '未设定'} - {scene.get('time') or '未设定'}\n{scene.get('action') or ''}\n" + "\n".join(f"{d.get('character','角色')}: {d.get('text','')}" for d in scene.get('dialogue',[])) for scene in screenplay.get('scenes',[]))
                return {"format":"screenplay","filename":f"{nid}-screenplay.md","content":f"# {screenplay.get('title',meta.get('title',''))}\n\n{content}"}
            if format == "shot-list":
                headers = "镜号,场景,景别,角度,运动,主体位置,动作,时长\n"
                body = "\n".join(",".join(str(shot.get(key,"" )).replace(",","，") for key in ("number","scene_id","shot_size","camera_angle","camera_motion","subject_position","action","duration_seconds")) for shot in screenplay.get("shots",[]))
                return {"format":"shot-list","filename":f"{nid}-shot-list.csv","content":headers+body}
            content = "\n\n".join(f"## 镜头 {card.get('number','')}\n\n画面：{card.get('frame_prompt','')}\n\n构图：{card.get('composition','')}\n\n色彩：{card.get('color','')}" for card in screenplay.get("storyboard",[]))
            return {"format":"storyboard","filename":f"{nid}-storyboard.md","content":content}
        if format not in {"json"}:
            raise ValueError("unsupported export format")
        return {"format":"json","filename":f"{nid}.json","content":json.dumps({"format":"ai-novel-studio","version":"0.4.5","novel":meta,"chapters":chapters},ensure_ascii=False,indent=2)}

    def export(self, nid, format, *, snapshot=None, progress_callback=None):
        """Export current project data or a previously captured snapshot."""
        if snapshot is not None:
            source = snapshot.get("source") if isinstance(snapshot, dict) else None
            if not isinstance(source, dict):
                raise ValueError("export snapshot is invalid")
            meta = source.get("novel") or {}
            chapters = source.get("chapters") or []
            screenplays = source.get("screenplays") or []
        else:
            meta = self.get(nid)
            chapters = self.chapters.list(nid)
            try:
                screenplays = self.novels.list_screenplays(nid)
            except (FileNotFoundError, AttributeError):
                screenplays = []
        if progress_callback:
            progress_callback(25, "读取快照")
        result = self._export_data(
            nid,
            meta,
            chapters,
            format,
            screenplays=screenplays,
            progress_callback=progress_callback,
        )
        if progress_callback:
            progress_callback(90, "生成文件")
        return result

    def export_snapshot_result(self, snapshot, format, *, progress_callback=None):
        """Explicit snapshot-oriented alias for exporter adapters."""
        if not isinstance(snapshot, dict):
            raise ValueError("export snapshot is invalid")
        return self.export(snapshot.get("novel_id", "export"), format, snapshot=snapshot, progress_callback=progress_callback)
    def import_project(self,format,content,confirm=False,content_base64=None):
        format=format.lower().strip()
        if format not in {"json","markdown","txt","docx","word","pdf"}:raise ValueError("unsupported import format")
        if content_base64 is not None:
            raw=decode_base64(content_base64)
            if format in {"docx","word"}: content=docx_to_text(raw); format="txt"
            elif format=="pdf": content=pdf_to_text(raw); format="txt"
            else: content=raw.decode("utf-8")
        elif format in {"docx","word","pdf"}: raise ValueError("binary import requires content_base64")
        if not content.strip():raise ValueError("import content is empty")
        if format=="json":
            data=json.loads(content);title=data.get("novel",{}).get("title","Imported Novel");chapters=data.get("chapters",[])
            if not isinstance(chapters,list):raise ValueError("chapters must be a list")
        else:
            lines=content.replace("\r\n","\n").replace("\r","\n").split("\n"); title="Imported Novel";chapters=[];current=None
            heading=re.compile(r"^(?:#{1,3}\s+)?(第[0-9零一二三四五六七八九十百千万两]+[章节卷回].*)$")
            markdown_heading=re.compile(r"^#{1,3}\s+(.+)$")
            for line in lines:
                if format=="markdown" and line.startswith("# ") and not current and not chapters:
                    title=line[2:].strip()[:200] or title;continue
                match=heading.match(line.strip()) or (markdown_heading.match(line.strip()) if format=="markdown" else None)
                if match:
                    if current:chapters.append(current)
                    current={"title":match.group(1).strip(),"content":""}
                elif current:current["content"]+=("\n" if current["content"] else "")+line
                elif line.strip() and title=="Imported Novel":title=line.lstrip("# ").strip()[:200]
            if current:chapters.append(current)
            if not chapters:chapters=[{"title":"第一章","content":content.strip()}]
        normalized=[{"title":str(c.get("title") or f"第{i}章")[:200],"content":str(c.get("content") or "").strip()} for i,c in enumerate(chapters,1)]
        warnings=[]
        if len(normalized)==1:warnings.append("未识别到多个章节标题，将按单章导入")
        if any(not c["content"] for c in normalized):warnings.append("部分章节没有正文")
        chapters=normalized
        preview={"title":title,"chapter_count":len(chapters),"word_count":sum(len(c["content"]) for c in chapters),"chapters":[{"number":i,"title":c["title"],"word_count":len(c["content"])} for i,c in enumerate(chapters,1)],"warnings":warnings}
        knowledge_base=self._knowledge_candidates(chapters)
        preview["knowledge_base"]={"status":"CANDIDATES_REVIEW_REQUIRED","candidates":knowledge_base}
        plan={"format":format,"title":title,"chapters":[{"number":i,"title":c["title"],"content":c["content"]} for i,c in enumerate(chapters,1)]}
        plan["knowledge_base_candidates"]=knowledge_base
        if not confirm:return {"preview":preview,"plan":plan}
        novel=self.create({"title":title,"genre":"Imported"})
        for c in chapters:self.chapters.create(novel["id"],{"title":c.get("title","Imported Chapter"),"content":c.get("content","")})
        return {"novel":novel,"preview":preview,"plan":plan}
