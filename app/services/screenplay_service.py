from datetime import datetime,timezone,timedelta
from uuid import uuid4
from ..repositories.screenplay_versions import check_screenplay_version
import copy
import threading
import hashlib
import json
from ..asset_providers import AssetGenerationRequest,AssetProviderRegistry,VideoGenerationRequest,VideoProvider,DeterministicVideoProvider

def utc():return datetime.now(timezone.utc).isoformat()

def suggest_transition_type(source: dict, target: dict) -> tuple[str, str]:
    vocabulary=('推开','关上','拔剑','挥手','转身','奔跑','跳跃','抬头','低头','坐下','站起','拥抱','击打','开门','关门','凝视','回头','拿起','放下')
    def action_words(value):
        text=str(value or '').replace('，','').replace('。','').replace('！','').replace('？','').replace(',','').replace('.','')
        found={word for word in vocabulary if word in text}
        found.update(word for word in text.split() if len(word)>=2)
        return found
    source_words=action_words(source.get('action')); target_words=action_words(target.get('action'))
    if source_words & target_words: return 'MATCH','前后镜头存在共同动作关键词，适合使用动作匹配转场。'
    if source.get('location') and target.get('location') and source.get('location') != target.get('location'): return 'DISSOLVE','地点变化适合用叠化保持叙事连贯。'
    if source.get('time') and target.get('time') and source.get('time') != target.get('time'): return 'FADE','时间发生变化，建议使用渐隐渐显。'
    if source.get('emotion') and target.get('emotion') and source.get('emotion') != target.get('emotion'): return 'MATCH','情绪或动作存在转折，建议用匹配转场强化连接。'
    return 'CUT','场景连续，直接剪切最简洁。'

def _effective_transition_type(value) -> str:
    if value is None:
        return "CUT"
    text = str(value).strip()
    if not text:
        return "CUT"
    return text.upper()


def _present_visual_field(value) -> bool:
    return value is not None and str(value).strip() != ""


def _visual_continuity_shots(screenplay: dict) -> list[dict]:
    scenes = {row.get("id"): row for row in screenplay.get("scenes") or []}
    view = []
    for shot in screenplay.get("shots") or []:
        row = dict(shot)
        scene = scenes.get(shot.get("scene_id")) or {}
        for key in ("time", "location", "emotion"):
            if not _present_visual_field(row.get(key)) and _present_visual_field(scene.get(key)):
                row[key] = scene[key]
        view.append(row)
    planned = screenplay.get("transitions") or []
    by_pair = {(row.get("from_shot_id"), row.get("to_shot_id")): row for row in planned}
    for previous, current in zip(view, view[1:]):
        match = by_pair.get((previous.get("id"), current.get("id")))
        if match is not None:
            current["transition"] = match.get("type")
    return view


def validate_visual_continuity(shots: list[dict]) -> list[dict]:
    findings=[]
    for previous,current in zip(shots,shots[1:]):
        if previous.get('location') and current.get('location') and previous.get('location') != current.get('location') and not current.get('transition'):
            findings.append({'code':'LOCATION_JUMP','severity':'WARNING','from_shot_id':previous.get('id'),'to_shot_id':current.get('id'),'message':'相邻镜头地点发生变化，但未配置转场。'})
        if previous.get('time') and current.get('time') and previous.get('time') != current.get('time') and _effective_transition_type(current.get('transition')) == 'CUT':
            findings.append({'code':'TIME_JUMP_CUT','severity':'INFO','from_shot_id':previous.get('id'),'to_shot_id':current.get('id'),'message':'时间发生变化，当前使用直接剪切。'})
        if previous.get('emotion') and current.get('emotion') and previous.get('emotion') != current.get('emotion') and not current.get('action'):
            findings.append({'code':'EMOTION_DISCONTINUITY','severity':'WARNING','from_shot_id':previous.get('id'),'to_shot_id':current.get('id'),'message':'情绪发生跳变，建议补充动作或转场说明。'})
    return findings

def is_traceable_frame(value) -> bool:
    text=str(value or "").strip()
    if not text: return False
    lowered=text.lower()
    if lowered.startswith("placeholder://"): return False
    if lowered.startswith(("http://","https://","asset:","shot:","storyboard:")): return True
    return False

def require_motion_frames(task: dict) -> None:
    if not is_traceable_frame(task.get("start_frame")) or not is_traceable_frame(task.get("end_frame")):
        raise ValueError("motion task requires traceable start_frame and end_frame before execution")

class ScreenplayService:
    def __init__(self,novels,chapters,asset_providers=None,video_providers=None):self.novels=novels;self.chapters=chapters;self.asset_providers=asset_providers or AssetProviderRegistry();self.video_providers=video_providers or {'deterministic':DeterministicVideoProvider()};self._motion_lock=threading.RLock();self.asset_library=None
    def _save_screenplay(self,novel_id,screenplay):
        return self.novels.save_screenplay(novel_id,screenplay,expected_version=int(screenplay.get("edit_version",0)))

    def history(self,novel_id,screenplay_id):
        current=next((row for row in self.list(novel_id) if row["id"]==screenplay_id),None)
        if current is None: raise KeyError(screenplay_id)
        rows=[*current.get("version_history",[]),{k:v for k,v in current.items() if k!="version_history"}]
        return {"screenplay_id":screenplay_id,"current_version":current.get("edit_version",0),"items":rows}

    def register_video_provider(self,provider_id,provider):
        if not str(provider_id).strip() or not hasattr(provider,'generate'): raise ValueError('invalid video provider')
        self.video_providers[str(provider_id).strip()]=provider
    def list(self,novel_id,*,branch_id=None):
        rows=self.novels.list_screenplays(novel_id)
        return rows if branch_id is None else [row for row in rows if row.get("branch_id")==branch_id]
    def create(self,novel_id,title="",*,branch_id=None):
        novel=self.novels.get(novel_id);chapters=self.chapters.list(novel_id);now=utc();scenes=[]
        for sequence,summary in enumerate(chapters,1):
            chapter=self.chapters.get(summary["id"]);scenes.append({"id":str(uuid4()),"sequence":sequence,"source_chapter_id":chapter["id"],"source_version":chapter["version"],"heading":chapter["title"],"time":"未设定","location":"未设定","characters":[],"action":"待从章节提炼可见行动","dialogue":[],"emotion":"待设定","status":"DRAFT"})
        screenplay={"id":str(uuid4()),"novel_id":novel_id,"source_title":novel["title"],"title":title.strip() or f"{novel['title']} 影视剧本","status":"DRAFT","revision":1,"scenes":scenes,"created_at":now,"updated_at":now}
        if branch_id is not None: screenplay["branch_id"]=branch_id
        return self._save_screenplay(novel_id,screenplay)
    def update_scene(self,novel_id,screenplay_id,scene_id,payload):
        screenplay=next((row for row in self.list(novel_id) if row["id"]==screenplay_id),None)
        if screenplay is None:raise KeyError(screenplay_id)
        check_screenplay_version(screenplay,payload.get("expected_version"))
        if screenplay["status"]!="DRAFT":raise ValueError("approved screenplay is frozen")
        scenes=list(screenplay["scenes"]);index=next((i for i,row in enumerate(scenes) if row["id"]==scene_id),None)
        if index is None:raise KeyError(scene_id)
        immutable={key:scenes[index][key] for key in ("id","sequence","source_chapter_id","source_version")};scenes[index]={**immutable,"heading":payload["heading"].strip(),"time":payload["time"].strip(),"location":payload["location"].strip(),"characters":[str(x).strip() for x in payload.get("characters",[]) if str(x).strip()],"action":payload["action"].strip(),"dialogue":payload.get("dialogue",[]),"emotion":payload["emotion"].strip(),"status":"DRAFT"}
        updated={**screenplay,"scenes":scenes,"revision":screenplay["revision"]+1,"updated_at":utc()};return self._save_screenplay(novel_id,updated)
    def approve(self,novel_id,screenplay_id,expected_version=None):
        screenplay=next((row for row in self.list(novel_id) if row["id"]==screenplay_id),None)
        if screenplay is None:raise KeyError(screenplay_id)
        check_screenplay_version(screenplay,expected_version)
        if screenplay["status"]!="DRAFT":raise ValueError("screenplay is already decided")
        return self._save_screenplay(novel_id,{**screenplay,"status":"APPROVED","updated_at":utc()})
    def revise(self,novel_id,screenplay_id,expected_version=None,source_version=None):
        """Fork an approved screenplay without modifying any approved assets.

        A new draft starts from captured scenes, retaining chapter provenance.
        Downstream shot/storyboard/transition and generation tasks stay on the
        approved original; they must be reviewed/planned anew for this draft.
        """
        original=next((row for row in self.list(novel_id) if row["id"]==screenplay_id),None)
        if original is None: raise KeyError(screenplay_id)
        if original.get("status")!="APPROVED": raise ValueError("only approved screenplays can be revised")
        check_screenplay_version(original,expected_version)
        source=original
        if source_version is not None:
            source=next((row for row in self.history(novel_id,screenplay_id)["items"] if row.get("edit_version",0)==source_version),None)
            if source is None: raise KeyError(source_version)
        now=utc()
        scenes=copy.deepcopy(source.get("scenes",[]))
        for scene in scenes: scene["status"]="DRAFT"
        revised={"id":str(uuid4()),"novel_id":novel_id,"title":original["title"],
                 "source_title":original.get("source_title", ""),"status":"DRAFT","revision":1,
                 "scenes":scenes,"created_at":now,"updated_at":now,
                 "derived_from":{"screenplay_id":screenplay_id,"revision":source.get("revision"),"edit_version":source.get("edit_version",0),
                                 "shot_revision":original.get("shot_revision"),"created_at":now}}
        if original.get("branch_id") is not None: revised["branch_id"]=original["branch_id"]
        return self._save_screenplay(novel_id,revised)
    def plan_shots(self,novel_id,screenplay_id,expected_version=None):
        screenplay=next((row for row in self.list(novel_id) if row["id"]==screenplay_id),None)
        if screenplay is None:raise KeyError(screenplay_id)
        check_screenplay_version(screenplay,expected_version)
        if screenplay["status"]!="APPROVED":raise ValueError("screenplay must be approved before shot planning")
        if screenplay.get("shots"):return screenplay
        shots=[]
        for scene in screenplay["scenes"]:
            shots.append({"id":str(uuid4()),"number":scene["sequence"]*10+1,"scene_id":scene["id"],"source_chapter_id":scene["source_chapter_id"],"shot_size":"MEDIUM","camera_angle":"EYE_LEVEL","camera_motion":"STATIC","subject_position":"待设计","action":scene["action"],"dialogue":scene["dialogue"],"sound_effect":"待设计","duration_seconds":5,"status":"DRAFT"})
        return self._save_screenplay(novel_id,{**screenplay,"shots":shots,"shot_revision":1,"updated_at":utc()})
    def update_shot(self,novel_id,screenplay_id,shot_id,payload):
        screenplay=next((row for row in self.list(novel_id) if row["id"]==screenplay_id),None)
        if screenplay is None:raise KeyError(screenplay_id)
        check_screenplay_version(screenplay,payload.get("expected_version"))
        if screenplay.get("shot_status")=="APPROVED":raise ValueError("approved shot plan is frozen")
        shots=list(screenplay.get("shots",[]));index=next((i for i,row in enumerate(shots) if row["id"]==shot_id),None)
        if index is None:raise KeyError(shot_id)
        immutable={key:shots[index][key] for key in ("id","number","scene_id","source_chapter_id")};shots[index]={**immutable,"shot_size":payload["shot_size"],"camera_angle":payload["camera_angle"],"camera_motion":payload["camera_motion"],"subject_position":payload["subject_position"],"action":payload["action"],"dialogue":payload.get("dialogue",[]),"sound_effect":payload["sound_effect"],"duration_seconds":max(1,min(600,int(payload["duration_seconds"]))),"status":"DRAFT"}
        return self._save_screenplay(novel_id,{**screenplay,"shots":shots,"shot_revision":int(screenplay.get("shot_revision",1))+1,"updated_at":utc()})
    def approve_shots(self,novel_id,screenplay_id,expected_version=None):
        screenplay=next((row for row in self.list(novel_id) if row["id"]==screenplay_id),None)
        if screenplay is None:raise KeyError(screenplay_id)
        check_screenplay_version(screenplay,expected_version)
        if not screenplay.get("shots"):raise ValueError("shot plan is empty")
        if screenplay.get("shot_status")=="APPROVED":raise ValueError("shot plan is already approved")
        return self._save_screenplay(novel_id,{**screenplay,"shot_status":"APPROVED","updated_at":utc()})
    def plan_storyboard(self,novel_id,screenplay_id,expected_version=None):
        screenplay=next((row for row in self.list(novel_id) if row["id"]==screenplay_id),None)
        if screenplay is None:raise KeyError(screenplay_id)
        check_screenplay_version(screenplay,expected_version)
        if screenplay.get("shot_status")!="APPROVED":raise ValueError("shot plan must be approved before storyboard")
        if screenplay.get("storyboard"):return screenplay
        cards=[{"id":str(uuid4()),"number":shot["number"],"shot_id":shot["id"],"scene_id":shot["scene_id"],"source_chapter_id":shot["source_chapter_id"],"frame_prompt":"待设计画面","composition":"待设计构图","color":"待设计色彩","status":"DRAFT"} for shot in screenplay.get("shots",[])]
        return self._save_screenplay(novel_id,{**screenplay,"storyboard":cards,"storyboard_revision":1,"updated_at":utc()})
    def update_storyboard_card(self,novel_id,screenplay_id,card_id,payload):
        screenplay=next((row for row in self.list(novel_id) if row["id"]==screenplay_id),None)
        if screenplay is None:raise KeyError(screenplay_id)
        check_screenplay_version(screenplay,payload.get("expected_version"))
        if screenplay.get("storyboard_status")=="APPROVED":raise ValueError("storyboard is frozen")
        cards=list(screenplay.get("storyboard",[]));index=next((i for i,row in enumerate(cards) if row["id"]==card_id),None)
        if index is None:raise KeyError(card_id)
        immutable={k:cards[index][k] for k in ("id","number","shot_id","scene_id","source_chapter_id")};cards[index]={**immutable,"frame_prompt":str(payload.get("frame_prompt","")).strip(),"composition":str(payload.get("composition","")).strip(),"color":str(payload.get("color","")).strip(),"status":"DRAFT"}
        return self._save_screenplay(novel_id,{**screenplay,"storyboard":cards,"storyboard_revision":int(screenplay.get("storyboard_revision",1))+1,"updated_at":utc()})
    def approve_storyboard(self,novel_id,screenplay_id,expected_version=None):
        screenplay=next((row for row in self.list(novel_id) if row["id"]==screenplay_id),None)
        if screenplay is None:raise KeyError(screenplay_id)
        check_screenplay_version(screenplay,expected_version)
        if not screenplay.get("storyboard"):raise ValueError("storyboard is empty")
        if screenplay.get("storyboard_status")=="APPROVED":raise ValueError("storyboard is already approved")
        return self._save_screenplay(novel_id,{**screenplay,"storyboard_status":"APPROVED","updated_at":utc()})
    def plan_transitions(self,novel_id,screenplay_id,expected_version=None):
        screenplay=next((r for r in self.list(novel_id) if r["id"]==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        check_screenplay_version(screenplay,expected_version)
        if screenplay.get("shot_status")!="APPROVED": raise ValueError("shot plan must be approved before transitions")
        if screenplay.get("transitions") is not None: return screenplay
        shots=screenplay.get("shots",[]); transitions=[]
        for prev,nxt in zip(shots,shots[1:]):
            transitions.append({"id":str(uuid4()),"from_shot_id":prev["id"],"to_shot_id":nxt["id"],"type":"CUT","duration_seconds":0,"note":"待设计","status":"DRAFT"})
        return self._save_screenplay(novel_id,{**screenplay,"transitions":transitions,"transition_revision":1,"updated_at":utc()})
    def update_transition(self,novel_id,screenplay_id,transition_id,payload):
        screenplay=next((r for r in self.list(novel_id) if r["id"]==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        check_screenplay_version(screenplay,payload.get("expected_version"))
        if screenplay.get("transition_status")=="APPROVED": raise ValueError("transitions are frozen")
        rows=list(screenplay.get("transitions",[])); i=next((i for i,r in enumerate(rows) if r["id"]==transition_id),None)
        if i is None: raise KeyError(transition_id)
        immutable={k:rows[i][k] for k in ("id","from_shot_id","to_shot_id")}; new_prompt=str(payload.get("prompt",rows[i].get("prompt", ""))).strip(); history=list(rows[i].get("prompt_history",[])); old_prompt=str(rows[i].get("prompt","")).strip();
        if old_prompt and old_prompt != new_prompt: history.append({"prompt":old_prompt,"saved_at":utc()})
        rows[i]={**immutable,"type":str(payload.get("type","CUT")).strip() or "CUT","duration_seconds":max(0,min(30,int(payload.get("duration_seconds",0)))),"note":str(payload.get("note","")).strip(),"prompt":new_prompt,"prompt_history":history[-10:],"prompt_status":"EDITED","status":"DRAFT"}
        return self._save_screenplay(novel_id,{**screenplay,"transitions":rows,"transition_revision":int(screenplay.get("transition_revision",1))+1,"updated_at":utc()})
    def transition_prompt(self,novel_id,screenplay_id,transition_id):
        screenplay=next((r for r in self.list(novel_id) if r["id"]==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        transition=next((r for r in screenplay.get("transitions",[]) if r["id"]==transition_id),None)
        if transition is None: raise KeyError(transition_id)
        kind=str(transition.get("type","CUT")).upper(); note=str(transition.get("note","")).strip()
        guidance={"CUT":"直接剪切，保持动作和视线方向连续。","DISSOLVE":"柔和叠化，强调时间或情绪的自然过渡。","FADE":"渐隐渐显，明确场景段落或时间跨度变化。","MATCH":"以相似动作、构图或形状匹配两个镜头。","WIPE":"通过画面运动完成空间切换。"}.get(kind,"自然完成镜头衔接，保持视觉连续性。")
        prompt=f"Transition {kind}: from shot {transition['from_shot_id']} to shot {transition['to_shot_id']}. {guidance}"
        if kind == "MATCH":
            prompt += " Preserve the shared action direction, body momentum, screen position, and timing across the cut."
        elif kind == "DISSOLVE":
            prompt += " Blend the outgoing and incoming images smoothly; preserve recognizable characters and locations during the overlap."
        elif kind == "FADE":
            prompt += " Use a controlled fade with a clear visual breath between scenes; signal the passage of time without abrupt motion."
        elif kind == "CUT":
            prompt += " Keep eyelines, screen direction, and action continuity stable; avoid a jarring jump in framing."
        elif kind == "WIPE":
            prompt += " Use a deliberate screen-direction wipe with a clean edge; keep the outgoing motion readable until the new shot fully replaces it."
        else:
            prompt += " Follow the creative note precisely while preserving subject identity, screen direction, and temporal coherence."
        if transition.get("duration_seconds"): prompt+=f" Duration about {transition['duration_seconds']} seconds."
        if note: prompt+=f" Creative note: {note}"
        return {"transition_id":transition_id,"type":kind,"prompt":prompt,"status":"DRAFT","template_version":"transition-prompt-v1","generated_at":utc()}
    def transition_suggestion(self,novel_id,screenplay_id,transition_id):
        screenplay=next((r for r in self.list(novel_id) if r["id"]==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        transition=next((r for r in screenplay.get("transitions",[]) if r["id"]==transition_id),None)
        if transition is None: raise KeyError(transition_id)
        shots=screenplay.get("shots",[]); by_id={str(row.get("id")):row for row in shots}; source=by_id.get(str(transition.get("from_shot_id")),{}); target=by_id.get(str(transition.get("to_shot_id")),{})
        source_text=' '.join(str(source.get(key,'')) for key in ('time','location','emotion','action')); target_text=' '.join(str(target.get(key,'')) for key in ('time','location','emotion','action'))
        kind,reason=suggest_transition_type(source,target)
        return {'transition_id':transition_id,'suggested_type':kind,'reason':reason,'source_context':source_text[:500],'target_context':target_text[:500]}
    def motion_prompt(self,novel_id,screenplay_id,transition_id):
        screenplay=next((r for r in self.list(novel_id) if r['id']==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        transition=next((r for r in screenplay.get('transitions',[]) if r['id']==transition_id),None)
        if transition is None: raise KeyError(transition_id)
        motion=f"Generate a controlled {transition.get('type','CUT')} transition from {transition.get('from_shot_id')} to {transition.get('to_shot_id')}. {transition.get('prompt','')} Keep camera motion smooth and preserve visual continuity."
        return {'transition_id':transition_id,'prompt':transition.get('prompt',''),'motion_prompt':motion,'status':transition.get('motion_status','DRAFT')}
    def save_motion_prompt(self,novel_id,screenplay_id,transition_id,motion_prompt):
        screenplay=next((r for r in self.list(novel_id) if r['id']==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        if screenplay.get('transition_status')=='APPROVED': raise ValueError('transitions are frozen')
        rows=list(screenplay.get('transitions',[])); index=next((i for i,r in enumerate(rows) if r['id']==transition_id),None)
        if index is None: raise KeyError(transition_id)
        rows[index]={**rows[index],'motion_prompt':str(motion_prompt).strip(),'motion_status':'PENDING'}
        return self._save_screenplay(novel_id,{**screenplay,'transitions':rows,'transition_revision':int(screenplay.get('transition_revision',1))+1,'updated_at':utc()})
    def create_motion_tasks(self,novel_id,screenplay_id):
        screenplay=next((r for r in self.list(novel_id) if r['id']==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        tasks=list(screenplay.get('motion_tasks',[])); existing={task.get('transition_id') for task in tasks}
        for row in screenplay.get('transitions',[]):
            if row.get('motion_prompt') and row.get('id') not in existing:
                configured=next(((provider_id,getattr(provider,'default_model','')) for provider_id,provider in self.video_providers.items() if provider_id!='deterministic' and getattr(provider,'health_check',lambda:False)()),(None,None))
                start_frame,end_frame=self._frames_for_transition(screenplay,row)
                tasks.append({'id':str(uuid4()),'transition_id':row['id'],'prompt':row['motion_prompt'],'privacy_level':'LOCAL_ONLY','provider_id':configured[0],'model_id':configured[1],'start_frame':start_frame,'end_frame':end_frame,'status':'PENDING','progress':0,'error':None if configured[0] else 'VIDEO_PROVIDER_NOT_CONFIGURED','created_at':utc()})
        return self._save_screenplay(novel_id,{**screenplay,'motion_tasks':tasks,'motion_task_revision':int(screenplay.get('motion_task_revision',0))+1,'updated_at':utc()})
    def _frames_for_transition(self,screenplay,transition):
        from_id=str(transition.get('from_shot_id') or '')
        to_id=str(transition.get('to_shot_id') or '')
        shots={str(row.get('id')):row for row in screenplay.get('shots') or []}
        cards={str(row.get('shot_id')):row for row in screenplay.get('storyboard') or []}
        def ref(shot_id):
            shot=shots.get(shot_id) or {}
            card=cards.get(shot_id) or {}
            for candidate in (shot.get('frame_asset_id'),shot.get('asset_id'),card.get('asset_id'),card.get('frame_asset_id')):
                if candidate:
                    text=str(candidate).strip()
                    return text if is_traceable_frame(text) else f'asset:{text}'
            return f'shot:{shot_id}' if shot_id else None
        start,end=ref(from_id),ref(to_id)
        return start,end
    def update_motion_task(self,novel_id,screenplay_id,task_id,status):
        screenplay=next((r for r in self.list(novel_id) if r['id']==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        rows=list(screenplay.get('motion_tasks',[])); index=next((i for i,r in enumerate(rows) if r['id']==task_id),None)
        if index is None: raise KeyError(task_id)
        current=rows[index].get('status','PENDING'); allowed={'PENDING':{'CANCELLED'},'RUNNING':{'CANCELLED'},'FAILED':{'PENDING','CANCELLED'},'CANCELLED':{'PENDING'},'SUCCEEDED':set()}
        if status!=current and status not in allowed.get(current,set()): raise ValueError(f'invalid motion task transition: {current} -> {status}')
        if status == 'CANCELLED' and status != current: return self.cancel_motion_task(novel_id,screenplay_id,task_id)
        if status == 'PENDING' and status != current: return self.retry_motion_task(novel_id,screenplay_id,task_id)
        rows[index]={**rows[index],'status':status,'updated_at':utc()}
        return self._save_screenplay(novel_id,{**screenplay,'motion_tasks':rows,'motion_task_revision':int(screenplay.get('motion_task_revision',0))+1,'updated_at':utc()})
    def update_motion_frames(self,novel_id,screenplay_id,task_id,start_frame=None,end_frame=None,constraints=None):
        with self._motion_lock:
            screenplay=next((r for r in self.list(novel_id) if r['id']==screenplay_id),None)
            if screenplay is None: raise KeyError(screenplay_id)
            rows=list(screenplay.get('motion_tasks',[])); index=next((i for i,r in enumerate(rows) if r['id']==task_id),None)
            if index is None: raise KeyError(task_id)
            if rows[index].get('status') not in {'PENDING','FAILED','CANCELLED'} or rows[index].get('remote_task_id'): raise ValueError('motion configuration is frozen during or after execution')
            def validate(value):
                if value is None or value == '': return value
                value=str(value).strip()
                if not is_traceable_frame(value): raise ValueError('frame must be an http(s) URL or a traceable asset/shot/storyboard reference')
                return value
            if constraints is not None:
                if not isinstance(constraints,dict) or set(constraints)-{'duration_seconds','fps','aspect_ratio','camera_motion'}:raise ValueError('unsupported motion parameter')
                if 'duration_seconds' in constraints and (isinstance(constraints['duration_seconds'],bool) or not isinstance(constraints['duration_seconds'],(int,float)) or not 0.1<=constraints['duration_seconds']<=120):raise ValueError('invalid motion duration')
                if 'fps' in constraints and constraints['fps'] not in {12,24,25,30,60}:raise ValueError('invalid motion frame rate')
                if 'aspect_ratio' in constraints and constraints['aspect_ratio'] not in {'16:9','9:16','1:1'}:raise ValueError('invalid motion aspect ratio')
                if 'camera_motion' in constraints and (not isinstance(constraints['camera_motion'],str) or len(constraints['camera_motion'])>2000):raise ValueError('invalid camera motion')
            row=rows[index]; new_start=validate(start_frame) if start_frame is not None else row.get('start_frame'); new_end=validate(end_frame) if end_frame is not None else row.get('end_frame'); frame_history=list(row.get('frame_history',[]));
            if row.get('start_frame')!=new_start or row.get('end_frame')!=new_end: frame_history.append({'start_frame':row.get('start_frame'),'end_frame':row.get('end_frame'),'changed_at':utc()})
            rows[index]={**row,'start_frame':new_start,'end_frame':new_end,'frame_history':frame_history[-10:],'constraints':constraints if constraints is not None else row.get('constraints',{}),'updated_at':utc()}
            return self._save_screenplay(novel_id,{**screenplay,'motion_tasks':rows,'motion_task_revision':int(screenplay.get('motion_task_revision',0))+1,'updated_at':utc()})

    def update_motion_provider(self,novel_id,screenplay_id,task_id,provider_id,model_id):
        with self._motion_lock:
            screenplay=next((r for r in self.list(novel_id) if r['id']==screenplay_id),None)
            if screenplay is None: raise KeyError(screenplay_id)
            if provider_id not in self.video_providers: raise ValueError(f'video provider is not configured: {provider_id}')
            rows=list(screenplay.get('motion_tasks',[])); index=next((i for i,r in enumerate(rows) if r['id']==task_id),None)
            if index is None: raise KeyError(task_id)
            if rows[index].get('status') not in {'PENDING','FAILED','CANCELLED'} or rows[index].get('remote_task_id'): raise ValueError('motion configuration is frozen during or after execution')
            rows[index]={**rows[index],'privacy_level':'LOCAL_ONLY','cloud_approval_prompt_sha256':None,'provider_id':provider_id,'model_id':str(model_id).strip() or 'video-placeholder','updated_at':utc()}
            return self._save_screenplay(novel_id,{**screenplay,'motion_tasks':rows,'motion_task_revision':int(screenplay.get('motion_task_revision',0))+1,'updated_at':utc()})

    def _motion_record(self, novel_id, screenplay_id, task_id):
        screenplay=next((row for row in self.list(novel_id) if row['id']==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        rows=list(screenplay.get('motion_tasks',[])); index=next((i for i,row in enumerate(rows) if row['id']==task_id),None)
        if index is None: raise KeyError(task_id)
        return screenplay,rows,index

    def _motion_save(self, novel_id, screenplay, rows):
        return self._save_screenplay(novel_id,{**screenplay,'motion_tasks':rows,'motion_task_revision':int(screenplay.get('motion_task_revision',0))+1,'updated_at':utc()})

    @staticmethod
    def _media_owner(screenplay,novel_id):
        if screenplay.get('novel_id',novel_id)!=novel_id:
            raise ValueError('MEDIA_OWNER_CHANGED')
        return (screenplay.get('id'),screenplay.get('novel_id',novel_id),screenplay.get('branch_id'),
                screenplay.get('actor_id'),screenplay.get('owner_actor_id'),screenplay.get('workspace_id'),
                json.dumps(screenplay.get('owner'),sort_keys=True))

    @staticmethod
    def _require_media_authorization(reauthorize):
        if not callable(reauthorize):raise ValueError('MEDIA_DISPATCH_AUTHORIZATION_REQUIRED')
        reauthorize()

    def _motion_request_digest(self,task,screenplay,novel_id):
        provider=self.video_providers.get(task.get('provider_id'))
        payload={key:task.get(key) for key in ('provider_id','model_id','prompt','start_frame','end_frame')}
        payload['constraints']=task.get('constraints') or {}
        payload['endpoint']=getattr(provider,'endpoint',None)
        payload['owner']=self._media_owner(screenplay,novel_id)
        return hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

    def _require_motion_review(self,task,provider,screenplay,novel_id):
        from ..media_frames import provider_is_local
        if provider_is_local(provider):return
        from ..source_privacy import assert_project_source_policies
        from ..privacy import normalize_privacy
        assert_project_source_policies(self.novels,novel_id)
        if any(key in screenplay and normalize_privacy(screenplay[key])!='CLOUD_ALLOWED' for key in ('privacy_level','privacy')):
            raise ValueError('VIDEO_SCREENPLAY_PRIVACY_REVIEW_REQUIRED')
        digest=hashlib.sha256(str(task.get('prompt','')).encode()).hexdigest()
        if (task.get('privacy_level')!='CLOUD_ALLOWED' or task.get('cloud_approval_prompt_sha256')!=digest
            or task.get('cloud_approval_provider_id')!=task.get('provider_id')
            or task.get('cloud_approval_model_id')!=task.get('model_id')
            or task.get('cloud_approval_request_sha256')!=self._motion_request_digest(task,screenplay,novel_id)):
            raise ValueError('VIDEO_CLOUD_PROMPT_REVIEW_REQUIRED')

    def _verify_motion_frame_sources(self,sources,screenplay,novel_id,provider):
        from ..media_frames import provider_is_local
        from ..privacy import normalize_privacy
        for source in sources:
            if source.get('kind')!='ASSET':continue
            if self.asset_library is None:raise ValueError('MEDIA_FRAME_CHANGED')
            asset=self.asset_library.get(source['asset_id'],branch_id=screenplay.get('branch_id'))
            if (asset.get('novel_id')!=novel_id or asset.get('sha256')!=source['asset_sha256']
                or asset.get('version',1)!=source['asset_version']):raise ValueError('MEDIA_FRAME_CHANGED')
            if not provider_is_local(provider) and normalize_privacy(asset.get('privacy_level'))!='CLOUD_ALLOWED':
                raise ValueError('FRAME_CLOUD_PRIVACY_REVIEW_REQUIRED')

    def motion_privacy(self,novel_id,screenplay_id,task_id):
        with self._motion_lock:
            screenplay,rows,index=self._motion_record(novel_id,screenplay_id,task_id);task=rows[index]
            return {'task_id':task_id,'prompt':task.get('prompt',''),'prompt_sha256':hashlib.sha256(str(task.get('prompt','')).encode()).hexdigest(),
                    'request_sha256':self._motion_request_digest(task,screenplay,novel_id),'start_frame':task.get('start_frame'),'end_frame':task.get('end_frame'),
                    'constraints':copy.deepcopy(task.get('constraints') or {}),'privacy_level':task.get('privacy_level','LOCAL_ONLY'),
                    'provider_id':task.get('provider_id'),'model_id':task.get('model_id'),'status':task.get('status'),
                    'local_frames_require_separate_privacy_review':True}

    def update_motion_privacy(self,novel_id,screenplay_id,task_id,privacy_level,prompt_sha256,request_sha256=None):
        with self._motion_lock:
            screenplay,rows,index=self._motion_record(novel_id,screenplay_id,task_id);task=rows[index]
            if task.get('status') not in {'PENDING','FAILED','CANCELLED'} or task.get('remote_task_id'):raise ValueError('motion privacy can only change before execution')
            actual=hashlib.sha256(str(task.get('prompt','')).encode()).hexdigest()
            if actual!=prompt_sha256:raise ValueError('motion prompt changed; review it again')
            if privacy_level not in {'LOCAL_ONLY','CLOUD_ALLOWED'}:raise ValueError('invalid motion privacy policy')
            request_digest=self._motion_request_digest(task,screenplay,novel_id)
            if privacy_level=='CLOUD_ALLOWED' and request_sha256!=request_digest:
                raise ValueError('motion request changed or was not reviewed; review frames and parameters again')
            rows[index]={**task,'privacy_level':privacy_level,'cloud_approval_prompt_sha256':actual if privacy_level=='CLOUD_ALLOWED' else None,
                         'cloud_approval_request_sha256':request_digest if privacy_level=='CLOUD_ALLOWED' else None,
                         'cloud_approval_provider_id':task.get('provider_id') if privacy_level=='CLOUD_ALLOWED' else None,
                         'cloud_approval_model_id':task.get('model_id') if privacy_level=='CLOUD_ALLOWED' else None,'privacy_reviewed_at':utc()}
            self._motion_save(novel_id,screenplay,rows)
            return self.motion_privacy(novel_id,screenplay_id,task_id)

    def execute_motion_task(self,novel_id,screenplay_id,task_id,*,reauthorize=None):
        with self._motion_lock:
            screenplay,rows,index=self._motion_record(novel_id,screenplay_id,task_id)
            task=copy.deepcopy(rows[index]);owner=self._media_owner(screenplay,novel_id)
            if task.get('status')!='PENDING' or task.get('remote_task_id'): raise ValueError('motion task must be PENDING without a remote submission before execution')
            require_motion_frames(task)
            provider_id=task.get('provider_id')
            if not provider_id or provider_id=='deterministic' or not str(task.get('model_id') or '').strip():
                rows[index]={**task,'error':'VIDEO_PROVIDER_NOT_CONFIGURED','progress':0,'updated_at':utc()}
                return self._motion_save(novel_id,screenplay,rows)
            provider=self.video_providers.get(provider_id)
            if provider is None: raise ValueError(f'video provider is not configured: {provider_id}')
            self._require_motion_review(task,provider,screenplay,novel_id)
            request_digest=self._motion_request_digest(task,screenplay,novel_id)
            token=str(uuid4()); submission_key=task.get('submission_key') or task_id; started=utc();attempt=int(task.get('attempts',0))+1
            rows[index]={**task,'status':'RUNNING','execution_token':token,'progress':0,'error':None,'attempts':attempt,
                         'submission_key':submission_key,'history':list(task.get('history',[]))+[{'status':'RUNNING','phase':'SUBMITTING','at':started}],'updated_at':started}
            self._motion_save(novel_id,screenplay,rows)
        try:
            from ..media_frames import resolve_motion_frame
            start_frame,start_source=resolve_motion_frame(task['start_frame'],screenplay,novel_id,provider,self.asset_library)
            end_frame,end_source=resolve_motion_frame(task['end_frame'],screenplay,novel_id,provider,self.asset_library)
            with self._motion_lock:
                # Preparation can be expensive. Recheck authority and every captured
                # outbound byte after it, immediately before the provider boundary.
                self._require_media_authorization(reauthorize)
                current_screenplay,current_rows,current_index=self._motion_record(novel_id,screenplay_id,task_id);current=copy.deepcopy(current_rows[current_index])
                if (self._media_owner(current_screenplay,novel_id)!=owner or current.get('status')!='RUNNING'
                    or current.get('execution_token')!=token or current.get('attempts')!=attempt
                    or current.get('submission_key')!=submission_key or current.get('remote_task_id')
                    or self.video_providers.get(provider_id) is not provider
                    or self._motion_request_digest(current,current_screenplay,novel_id)!=request_digest):
                    raise ValueError('MEDIA_DISPATCH_STATE_CHANGED')
                self._require_motion_review(current,provider,current_screenplay,novel_id)
                checked_start,checked_start_source=resolve_motion_frame(current['start_frame'],current_screenplay,novel_id,provider,self.asset_library)
                checked_end,checked_end_source=resolve_motion_frame(current['end_frame'],current_screenplay,novel_id,provider,self.asset_library)
                if (checked_start,checked_end,checked_start_source,checked_end_source)!=(start_frame,end_frame,start_source,end_source):
                    raise ValueError('MEDIA_FRAME_CHANGED')
                # A source resolver must not be able to invalidate permission or
                # swap the attempt between the final read and dispatch.
                self._require_media_authorization(reauthorize)
                latest,latest_rows,latest_index=self._motion_record(novel_id,screenplay_id,task_id);last=latest_rows[latest_index]
                if (self._media_owner(latest,novel_id)!=owner or last!=current
                    or any(latest.get(key)!=current_screenplay.get(key) for key in ('shots','storyboard'))):
                    raise ValueError('MEDIA_DISPATCH_STATE_CHANGED')
                if self.video_providers.get(provider_id) is not provider or self._motion_request_digest(last,latest,novel_id)!=request_digest:
                    raise ValueError('MEDIA_DISPATCH_STATE_CHANGED')
                self._require_motion_review(last,provider,latest,novel_id)
                self._verify_motion_frame_sources((start_source,end_source),latest,novel_id,provider)
            generated=provider.generate(VideoGenerationRequest(provider_id,task.get('model_id') or 'video-model',task.get('prompt',''),start_frame,end_frame,task_id,submission_key,dict(task.get('constraints') or {})))
            if str(generated.video_uri or '').lower().startswith('placeholder://'): raise ValueError('placeholder video URI is not allowed')
        except Exception as exc:
            with self._motion_lock:
                screenplay,rows,index=self._motion_record(novel_id,screenplay_id,task_id); current=rows[index]
                if current.get('execution_token')!=token or current.get('status')!='RUNNING': return screenplay
                error=str(exc) if isinstance(exc,ValueError) and str(exc).startswith(('MEDIA_','VIDEO_','FRAME_')) else 'VIDEO_PROVIDER_REQUEST_FAILED'
                stamp=utc();rows[index]={**current,'status':'FAILED','error':error,'history':list(current.get('history',[]))+[{'status':'FAILED','phase':'SUBMITTING','at':stamp,'error':error}],'updated_at':stamp}
                self._motion_save(novel_id,screenplay,rows)
            raise
        with self._motion_lock:
            screenplay,rows,index=self._motion_record(novel_id,screenplay_id,task_id); current=rows[index]
            if (current.get('execution_token')!=token or current.get('status')!='RUNNING'
                or current.get('attempts')!=attempt or self._media_owner(screenplay,novel_id)!=owner):
                if generated.remote_task_id and hasattr(provider,'cancel'):
                    try: provider.cancel(generated.remote_task_id)
                    except Exception: pass
                return screenplay
            status=str(generated.status or 'RUNNING').upper()
            if status not in {'PENDING','RUNNING','SUCCEEDED'}: status='RUNNING'
            if generated.video_uri: status='SUCCEEDED'
            if status=='SUCCEEDED' and not generated.video_uri: raise ValueError('successful video response requires a result URL')
            stamp=utc();result={'kind':'VIDEO','task_id':task_id,'prompt':task.get('prompt',''),'url':generated.video_uri,'provider_id':generated.provider_id,'model_id':generated.model_id,'created_at':stamp}
            asset_import={'task_id':task_id,'url':generated.video_uri,'filename':f'motion-{task_id}.mp4','import_status':'READY_TO_IMPORT','created_at':stamp} if generated.video_uri else None
            rows[index]={**current,'status':status,'frame_provenance':{'start':start_source,'end':end_source},'progress':100 if status=='SUCCEEDED' else 0,'remote_task_id':generated.remote_task_id,'result':result,'asset_import':asset_import,'history':list(current.get('history',[]))+[{'status':status,'phase':'SUBMITTED','at':stamp}],'updated_at':stamp}
            return self._motion_save(novel_id,screenplay,rows)
    def cancel_motion_task(self,novel_id,screenplay_id,task_id):
        with self._motion_lock:
            screenplay=next((r for r in self.list(novel_id) if r['id']==screenplay_id),None)
            if screenplay is None: raise KeyError(screenplay_id)
            rows=list(screenplay.get('motion_tasks',[])); index=next((i for i,r in enumerate(rows) if r['id']==task_id),None)
            if index is None: raise KeyError(task_id)
            task=rows[index]; status=task.get('status','PENDING')
            if status in {'SUCCEEDED','FAILED','CANCELLED'}: raise ValueError(f'motion task cannot be cancelled from {status}')
            remote=task.get('remote_task_id'); provider=self.video_providers.get(task.get('provider_id',''))
            if remote:
                if not provider or not hasattr(provider,'cancel'): raise ValueError('video provider does not support cancellation')
                provider.cancel(remote)
            stamp=utc(); history=list(task.get('history',[])); history.append({'status':'CANCELLED','phase':'CANCELLED','at':stamp,'error':None})
            rows[index]={**task,'status':'CANCELLED','error':None,'history':history,'updated_at':stamp}
            return self._save_screenplay(novel_id,{**screenplay,'motion_tasks':rows,'motion_task_revision':int(screenplay.get('motion_task_revision',0))+1,'updated_at':stamp})

    def retry_motion_task(self,novel_id,screenplay_id,task_id):
        with self._motion_lock:
            screenplay=next((r for r in self.list(novel_id) if r['id']==screenplay_id),None)
            if screenplay is None: raise KeyError(screenplay_id)
            rows=list(screenplay.get('motion_tasks',[])); index=next((i for i,r in enumerate(rows) if r['id']==task_id),None)
            if index is None: raise KeyError(task_id)
            task=rows[index]; status=task.get('status')
            if status not in {'FAILED','CANCELLED'}: raise ValueError(f'motion task cannot be retried from {status}')
            stamp=utc(); history=list(task.get('history',[])); history.append({'status':'PENDING','phase':'RETRY_QUEUED','at':stamp,'error':None})
            results=list(task.get('result_history',[])); previous=task.get('result')
            if previous: results.append({**previous,'replaced_at':stamp})
            next_attempt=int(task.get('attempts',0))+1
            rows[index]={**task,'status':'PENDING','progress':0,'error':None,'remote_task_id':None,'execution_token':None,'submission_key':f'{task_id}:attempt:{next_attempt}','result':None,'asset_import':None,'result_history':results[-10:],'history':history,'updated_at':stamp}
            return self._save_screenplay(novel_id,{**screenplay,'motion_tasks':rows,'motion_task_revision':int(screenplay.get('motion_task_revision',0))+1,'updated_at':stamp})

    def attach_motion_result(self,novel_id,screenplay_id,task_id,url,media_type='video/mp4'):
        with self._motion_lock:
            screenplay=next((r for r in self.list(novel_id) if r['id']==screenplay_id),None)
            if screenplay is None: raise KeyError(screenplay_id)
            rows=list(screenplay.get('motion_tasks',[])); index=next((i for i,r in enumerate(rows) if r['id']==task_id),None)
            if index is None: raise KeyError(task_id)
            if rows[index].get('status') == 'CANCELLED': raise ValueError('cancelled motion task cannot accept a result')
            if str(url).lower().startswith('placeholder://'): raise ValueError('placeholder video URI is not allowed')
            stamp=utc(); result={**rows[index].get('result',{}),'url':str(url).strip(),'media_type':media_type,'attached_at':stamp}
            history=list(rows[index].get('result_history',[])); previous=rows[index].get('result');
            if previous: history.append({**previous,'replaced_at':stamp})
            asset_import={'task_id':task_id,'url':result['url'],'filename':f'motion-{task_id}.mp4','import_status':'READY_TO_IMPORT','created_at':stamp}
            rows[index]={**rows[index],'status':'SUCCEEDED','progress':100,'result':result,'asset_import':asset_import,'result_history':history[-10:],'updated_at':stamp}
            return self._save_screenplay(novel_id,{**screenplay,'motion_tasks':rows,'motion_task_revision':int(screenplay.get('motion_task_revision',0))+1,'updated_at':utc()})

    def motion_callback(self,novel_id,screenplay_id,task_id,status,progress=0,url=None,error=None):
        with self._motion_lock:
            screenplay=next((r for r in self.list(novel_id) if r['id']==screenplay_id),None)
            if screenplay is None: raise KeyError(screenplay_id)
            rows=list(screenplay.get('motion_tasks',[])); index=next((i for i,r in enumerate(rows) if r['id']==task_id),None)
            if index is None: raise KeyError(task_id)
            if status not in {'PENDING','RUNNING','SUCCEEDED','FAILED','CANCELLED'}: raise ValueError('invalid motion callback status')
            row=rows[index]; current=row.get('status','PENDING')
            if current in {'SUCCEEDED','FAILED','CANCELLED'} and status != current: raise ValueError(f'terminal motion task cannot transition: {current} -> {status}')
            if current in {'SUCCEEDED','FAILED','CANCELLED'} and status == current:
                if url and url != (row.get('result') or {}).get('url'): raise ValueError('terminal motion result cannot be replaced by a callback')
                return screenplay
            allowed={'PENDING':{'PENDING','RUNNING','SUCCEEDED','FAILED','CANCELLED'},'RUNNING':{'RUNNING','SUCCEEDED','FAILED','CANCELLED'}}
            if current not in {'SUCCEEDED','FAILED','CANCELLED'} and status not in allowed.get(current,set()): raise ValueError(f'invalid motion callback transition: {current} -> {status}')
            if status=='SUCCEEDED' and not (url or (row.get('result') or {}).get('url')): raise ValueError('successful motion callback requires a video URL')
            if url and str(url).lower().startswith('placeholder://'): raise ValueError('placeholder video URI is not allowed')
            stamp=utc(); history=list(row.get('history',[])); history.append({'status':status,'phase':'PROVIDER_UPDATE','at':stamp,'error':error})
            updated={**row,'status':status,'progress':100 if status=='SUCCEEDED' else max(int(row.get('progress') or 0),max(0,min(100,int(progress)))),'error':error,'history':history,'updated_at':stamp}
            if url:
                previous=row.get('result'); result={**(previous or {}),'url':url,'media_type':'video/mp4','attached_at':stamp}; result_history=list(row.get('result_history',[]))
                if previous and previous.get('url') and previous.get('url') != url: result_history.append({**previous,'replaced_at':stamp})
                updated['result']=result; updated['result_history']=result_history[-10:]
                updated['asset_import']={'task_id':task_id,'url':url,'filename':f'motion-{task_id}.mp4','import_status':'READY_TO_IMPORT','created_at':stamp}
            rows[index]=updated
            return self._save_screenplay(novel_id,{**screenplay,'motion_tasks':rows,'motion_task_revision':int(screenplay.get('motion_task_revision',0))+1,'updated_at':utc()})

    def sync_motion_provider_status(self,novel_id,screenplay_id,task_id,remote_task_id,provider):
        state=provider.get_status(remote_task_id); status=str(state.get('status','RUNNING')).upper(); status={'COMPLETED':'SUCCEEDED','COMPLETE':'SUCCEEDED','IN_PROGRESS':'RUNNING'}.get(status,status)
        if status not in {'PENDING','RUNNING','SUCCEEDED','FAILED','CANCELLED'}: status='RUNNING'
        return self.motion_callback(novel_id,screenplay_id,task_id,status,state.get('progress',0),state.get('url'),state.get('error'))
    def set_remote_motion_task_id(self,novel_id,screenplay_id,task_id,remote_task_id):
        screenplay=next((r for r in self.list(novel_id) if r['id']==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        rows=list(screenplay.get('motion_tasks',[])); index=next((i for i,r in enumerate(rows) if r['id']==task_id),None)
        if index is None: raise KeyError(task_id)
        rows[index]={**rows[index],'remote_task_id':str(remote_task_id).strip(),'updated_at':utc()}
        return self._save_screenplay(novel_id,{**screenplay,'motion_tasks':rows,'motion_task_revision':int(screenplay.get('motion_task_revision',0))+1,'updated_at':utc()})
    def sync_motion_task(self,novel_id,screenplay_id,task_id):
        screenplay=next((r for r in self.list(novel_id) if r['id']==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        task=next((r for r in screenplay.get('motion_tasks',[]) if r['id']==task_id),None)
        if task is None: raise KeyError(task_id)
        remote=task.get('remote_task_id');
        if not remote: raise ValueError('remote_task_id is not configured')
        provider=self.video_providers.get(task.get('provider_id',''))
        if not provider or not hasattr(provider,'get_status'): raise ValueError('video provider does not support polling')
        return self.sync_motion_provider_status(novel_id,screenplay_id,task_id,remote,provider)
    def motion_result_history(self,novel_id,screenplay_id,task_id):
        screenplay=next((r for r in self.list(novel_id) if r['id']==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        task=next((r for r in screenplay.get('motion_tasks',[]) if r['id']==task_id),None)
        if task is None: raise KeyError(task_id)
        return {'task_id':task_id,'current':task.get('result'),'history':task.get('result_history',[])}
    def motion_asset_reference(self,novel_id,screenplay_id,task_id):
        screenplay=next((r for r in self.list(novel_id) if r['id']==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        task=next((r for r in screenplay.get('motion_tasks',[]) if r['id']==task_id),None)
        if task is None: raise KeyError(task_id)
        result=task.get('result') or {}
        asset_id=result.get('asset_id'); return {'novel_id':novel_id,'screenplay_id':screenplay_id,'task_id':task_id,'asset_id':asset_id,'download_path':f'/api/assets/{asset_id}/download?novel_id={novel_id}' if asset_id else None,'url':result.get('url'),'kind':result.get('kind','VIDEO'),'provider_id':result.get('provider_id'),'model_id':result.get('model_id')}
    def import_motion_asset_reference(self,novel_id,screenplay_id,task_id):
        ref=self.motion_asset_reference(novel_id,screenplay_id,task_id)
        if not ref.get('url'): raise ValueError('motion result does not have a downloadable URL')
        screenplay=next(r for r in self.list(novel_id) if r['id']==screenplay_id); rows=list(screenplay.get('motion_tasks',[])); index=next(i for i,r in enumerate(rows) if r['id']==task_id); job={**ref,'import_status':'PENDING_DOWNLOAD','filename':f"{ref.get('asset_id') or task_id}.mp4",'created_at':utc()}; rows[index]={**rows[index],'asset_import':job,'updated_at':utc()}; self._save_screenplay(novel_id,{**screenplay,'motion_tasks':rows,'updated_at':utc()}); return job
    def motion_asset_import_status(self,novel_id,screenplay_id,task_id):
        screenplay=next((r for r in self.list(novel_id) if r['id']==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        task=next((r for r in screenplay.get('motion_tasks',[]) if r['id']==task_id),None)
        if task is None: raise KeyError(task_id)
        return task.get('asset_import') or {'task_id':task_id,'import_status':'NOT_REQUESTED'}
    def list_motion_asset_imports(self,novel_id,screenplay_id):
        screenplay=next((r for r in self.list(novel_id) if r['id']==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        return {'screenplay_id':screenplay_id,'items':[r['asset_import'] for r in screenplay.get('motion_tasks',[]) if r.get('asset_import')]}
    def retry_failed_motion_asset_imports(self,novel_id,screenplay_id):
        screenplay=next((r for r in self.list(novel_id) if r['id']==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        rows=list(screenplay.get('motion_tasks',[])); count=0
        for i,row in enumerate(rows):
            job=row.get('asset_import')
            if job and job.get('import_status')=='FAILED': rows[i]={**row,'asset_import':{**job,'import_status':'PENDING_DOWNLOAD','error':None,'retry_at':utc()},'updated_at':utc()}; count+=1
        if count: self._save_screenplay(novel_id,{**screenplay,'motion_tasks':rows,'updated_at':utc()})
        return {'screenplay_id':screenplay_id,'retried':count}
    def download_motion_asset(self,novel_id,screenplay_id,task_id,asset_library):
        import base64
        import hashlib
        from ..media_files import fetch_media_bytes,inspect_media
        with self._motion_lock:
            screenplay,rows,index=self._motion_record(novel_id,screenplay_id,task_id); task=rows[index]; job=task.get('asset_import') or {}
            if task.get('status')!='SUCCEEDED': raise ValueError('only successful motion tasks can import assets')
            if not job.get('url'): raise ValueError('asset import URL is missing')
            if job.get('import_status')=='COMPLETED': return job
            token=task.get('execution_token'); url=job['url']; provider=self.video_providers.get(task.get('provider_id'))
        try:
            data=fetch_media_bytes(url,asset_library.MAX_BYTES,30,configured_provider_endpoint=getattr(provider,'endpoint',None))
            measured=inspect_media(data,'video')
            with self._motion_lock:
                screenplay,rows,index=self._motion_record(novel_id,screenplay_id,task_id); current=rows[index]
                if current.get('status')!='SUCCEEDED' or current.get('execution_token')!=token or (current.get('asset_import') or {}).get('url')!=url:
                    return {'task_id':task_id,'import_status':'CANCELLED','error':'MOTION_RESULT_CHANGED'}
                asset=asset_library.create(novel_id,f"motion-{task_id}.{measured['extension']}",base64.b64encode(data).decode('ascii'),measured['media_type'],'video',f"motion-import:{task_id}:{hashlib.sha256(data).hexdigest()}",branch_id=screenplay.get("branch_id"))
                asset=asset_library.update_metadata(asset['id'],{'source_job_id':task_id,'provider_id':current.get('provider_id'),'model_id':current.get('model_id')},branch_id=screenplay.get('branch_id'))
                updated={**job,'import_status':'COMPLETED','asset':asset,'duration_ms':measured['duration_ms'],'validation':measured['validation'],'completed_at':utc()}
                rows[index]={**current,'result':{**(current.get('result') or {}),'asset_id':asset['id'],'media_type':measured['media_type'],'duration_ms':measured['duration_ms']},'asset_import':updated,'updated_at':utc()}
                self._motion_save(novel_id,screenplay,rows)
                return updated
        except Exception:
            with self._motion_lock:
                screenplay,rows,index=self._motion_record(novel_id,screenplay_id,task_id); current=rows[index]
                if current.get('execution_token')!=token or (current.get('asset_import') or {}).get('url')!=url: return current.get('asset_import') or {}
                updated={**job,'import_status':'FAILED','error':'MEDIA_DOWNLOAD_OR_VALIDATION_FAILED'}
                rows[index]={**current,'asset_import':updated,'updated_at':utc()};self._motion_save(novel_id,screenplay,rows)
                return updated
    def _save_motion_import(self,novel_id,screenplay_id,task_id,job):
        screenplay=next(r for r in self.list(novel_id) if r['id']==screenplay_id); rows=list(screenplay.get('motion_tasks',[])); index=next(i for i,r in enumerate(rows) if r['id']==task_id); rows[index]={**rows[index],'asset_import':job,'updated_at':utc()}; self._save_screenplay(novel_id,{**screenplay,'motion_tasks':rows,'updated_at':utc()})
    def retry_motion_asset_import(self,novel_id,screenplay_id,task_id):
        screenplay=next((r for r in self.list(novel_id) if r['id']==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        rows=list(screenplay.get('motion_tasks',[])); index=next((i for i,r in enumerate(rows) if r['id']==task_id),None)
        if index is None: raise KeyError(task_id)
        job=rows[index].get('asset_import')
        if not job: raise ValueError('asset import has not been requested')
        updated={**job,'import_status':'PENDING_DOWNLOAD','error':None,'retry_at':utc()}; rows[index]={**rows[index],'asset_import':updated,'updated_at':utc()}
        self._save_screenplay(novel_id,{**screenplay,'motion_tasks':rows,'updated_at':utc()}); return updated
    def motion_frame_history(self,novel_id,screenplay_id,task_id):
        screenplay=next((r for r in self.list(novel_id) if r['id']==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        task=next((r for r in screenplay.get('motion_tasks',[]) if r['id']==task_id),None)
        if task is None: raise KeyError(task_id)
        return {'task_id':task_id,'current':{'start_frame':task.get('start_frame'),'end_frame':task.get('end_frame')},'history':task.get('frame_history',[])}
    def validate_visual_continuity(self,novel_id,screenplay_id):
        screenplay=next((r for r in self.list(novel_id) if r['id']==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        return {'screenplay_id':screenplay_id,'findings':validate_visual_continuity(_visual_continuity_shots(screenplay))}
    def pipeline_status(self,novel_id,screenplay_id):
        screenplay=next((r for r in self.list(novel_id) if r['id']==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        stages=[('screenplay',screenplay.get('status')=='APPROVED'),('shots',screenplay.get('shot_status')=='APPROVED'),('storyboard',screenplay.get('storyboard_status')=='APPROVED'),('transitions',screenplay.get('transition_status')=='APPROVED')]
        tasks=screenplay.get('motion_tasks',[]); motion_total=len(tasks); motion_done=sum(1 for task in tasks if task.get('status')=='SUCCEEDED')
        next_stage=next((name for name,done in stages if not done),'motion' if motion_total and motion_done<motion_total else 'complete')
        return {'screenplay_id':screenplay_id,'stages':[{'id':name,'complete':done} for name,done in stages],'motion':{'total':motion_total,'completed':motion_done},'next_stage':next_stage}
    def advance_pipeline(self,novel_id,screenplay_id):
        status=self.pipeline_status(novel_id,screenplay_id); stage=status['next_stage']
        if stage=='shots': return {'action':'PLAN_SHOTS','screenplay':self.plan_shots(novel_id,screenplay_id)}
        if stage=='storyboard': return {'action':'PLAN_STORYBOARD','screenplay':self.plan_storyboard(novel_id,screenplay_id)}
        if stage=='transitions': return {'action':'PLAN_TRANSITIONS','screenplay':self.plan_transitions(novel_id,screenplay_id)}
        if stage=='motion': return {'action':'CREATE_MOTION_TASKS','screenplay':self.create_motion_tasks(novel_id,screenplay_id)}
        return {'action':'MANUAL_APPROVAL_REQUIRED' if stage=='screenplay' else 'NO_ACTION','stage':stage}
    def advance_pipeline_until_gate(self,novel_id,screenplay_id,max_steps=10):
        actions=[]
        for _ in range(max(1,min(20,int(max_steps)))):
            result=self.advance_pipeline(novel_id,screenplay_id); actions.append(result.get('action'))
            if result.get('action') in {'MANUAL_APPROVAL_REQUIRED','NO_ACTION'}: break
            status=self.pipeline_status(novel_id,screenplay_id)
            if status['next_stage'] in {'screenplay','complete'}: break
        return {'screenplay_id':screenplay_id,'actions':actions,'status':self.pipeline_status(novel_id,screenplay_id)}
    def approve_transitions(self,novel_id,screenplay_id,expected_version=None):
        screenplay=next((r for r in self.list(novel_id) if r["id"]==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        check_screenplay_version(screenplay,expected_version)
        if screenplay.get("transitions") is None: raise ValueError("transitions are not planned")
        if screenplay.get("transition_status")=="APPROVED": raise ValueError("transitions already approved")
        transitions=[{**row,"prompt_status":"FROZEN"} for row in screenplay.get("transitions",[])]
        return self._save_screenplay(novel_id,{**screenplay,"transitions":transitions,"transition_status":"APPROVED","updated_at":utc()})
    def plan_assets(self,novel_id,screenplay_id,expected_version=None):
        screenplay=next((r for r in self.list(novel_id) if r["id"]==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        check_screenplay_version(screenplay,expected_version)
        if screenplay.get("storyboard_status")!="APPROVED": raise ValueError("storyboard must be approved before asset planning")
        if screenplay.get("asset_requirements") is not None: return screenplay
        assets=[{"id":str(uuid4()),"storyboard_id":card["id"],"shot_id":card["shot_id"],"kind":"IMAGE","description":card["frame_prompt"],"status":"PENDING","notes":"待准备"} for card in screenplay.get("storyboard",[])]
        return self._save_screenplay(novel_id,{**screenplay,"asset_requirements":assets,"asset_revision":1,"updated_at":utc()})
    def update_asset(self,novel_id,screenplay_id,asset_id,payload):
        screenplay=next((r for r in self.list(novel_id) if r["id"]==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        check_screenplay_version(screenplay,payload.get("expected_version"))
        if screenplay.get("asset_status")=="APPROVED": raise ValueError("asset requirements are frozen")
        rows=list(screenplay.get("asset_requirements",[])); i=next((i for i,r in enumerate(rows) if r["id"]==asset_id),None)
        if i is None: raise KeyError(asset_id)
        immutable={k:rows[i][k] for k in ("id","storyboard_id","shot_id")}; rows[i]={**immutable,"kind":str(payload.get("kind","IMAGE")).strip() or "IMAGE","description":str(payload.get("description","")).strip(),"status":str(payload.get("status","PENDING")).strip() or "PENDING","notes":str(payload.get("notes","")).strip()}
        return self._save_screenplay(novel_id,{**screenplay,"asset_requirements":rows,"asset_revision":int(screenplay.get("asset_revision",1))+1,"updated_at":utc()})
    def approve_assets(self,novel_id,screenplay_id,expected_version=None):
        screenplay=next((r for r in self.list(novel_id) if r["id"]==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        check_screenplay_version(screenplay,expected_version)
        if screenplay.get("asset_requirements") is None: raise ValueError("asset requirements are not planned")
        if screenplay.get("asset_status")=="APPROVED": raise ValueError("asset requirements already approved")
        return self._save_screenplay(novel_id,{**screenplay,"asset_status":"APPROVED","updated_at":utc()})
    def create_asset_tasks(self,novel_id,screenplay_id):
        screenplay=next((r for r in self.list(novel_id) if r["id"]==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        if screenplay.get("asset_status")!="APPROVED": raise ValueError("assets must be approved before generation")
        if screenplay.get("asset_tasks") is not None: return screenplay
        preferred=next(((provider_id,provider) for provider_id,provider in self.asset_providers._providers.items() if getattr(provider,'health_check',lambda:True)()),(None,None))
        default_provider,provider=preferred
        default_model=getattr(provider,"default_model",None) if provider else None
        tasks=[{"id":str(uuid4()),"asset_id":a["id"],"provider_id":default_provider,"model_id":default_model,"privacy_level":"LOCAL_ONLY","status":"PENDING","error":None,"attempts":0,"history":[{"status":"PENDING","at":utc()}]} for a in screenplay["asset_requirements"]]
        return self._save_screenplay(novel_id,{**screenplay,"asset_tasks":tasks,"task_revision":1,"updated_at":utc()})
    def _asset_record(self,novel_id,screenplay_id,task_id):
        screenplay=next((r for r in self.list(novel_id) if r['id']==screenplay_id),None)
        if screenplay is None:raise KeyError(screenplay_id)
        rows=list(screenplay.get('asset_tasks',[]));index=next((i for i,r in enumerate(rows) if r['id']==task_id),None)
        if index is None:raise KeyError(task_id)
        return screenplay,rows,index

    def _asset_save(self,novel_id,screenplay,rows):
        return self._save_screenplay(novel_id,{**screenplay,'asset_tasks':rows,'task_revision':int(screenplay.get('task_revision',0))+1,'updated_at':utc()})

    def update_asset_task(self,novel_id,screenplay_id,task_id,payload):
        with self._motion_lock:
            screenplay,rows,i=self._asset_record(novel_id,screenplay_id,task_id);row=rows[i]
            status=str(payload.get('status',row['status']))
            if status not in {'PENDING','RUNNING','SUCCEEDED','FAILED','CANCELLED'}:raise ValueError('invalid task status')
            current=row['status']
            allowed={'PENDING':{'RUNNING','CANCELLED'},'RUNNING':{'SUCCEEDED','FAILED','CANCELLED'},'FAILED':{'PENDING','CANCELLED'},'CANCELLED':{'PENDING'},'SUCCEEDED':set()}
            if status!=current and status not in allowed.get(current,set()):raise ValueError(f'invalid task transition: {current} -> {status}')
            provider_id=payload.get('provider_id',row.get('provider_id'));model_id=payload.get('model_id',row.get('model_id'))
            if current in {'RUNNING','SUCCEEDED'} and (provider_id!=row.get('provider_id') or model_id!=row.get('model_id')):
                raise ValueError('asset provider configuration is frozen during or after execution')
            history=list(row.get('history',[]));history.append({'status':status,'at':utc(),'error':payload.get('error')})
            attempts=int(row.get('attempts',0))+(1 if status=='RUNNING' and current!='RUNNING' else 0)
            rows[i]={**row,'status':status,'provider_id':provider_id,'model_id':model_id,'error':payload.get('error'),
                     'attempts':attempts,'history':history,'execution_token':row.get('execution_token') if status==current=='RUNNING' else None}
            return self._asset_save(novel_id,screenplay,rows)

    def execute_asset_task(self,novel_id,screenplay_id,task_id,*,reauthorize=None):
        with self._motion_lock:
            screenplay,rows,index=self._asset_record(novel_id,screenplay_id,task_id);task=copy.deepcopy(rows[index])
            owner=self._media_owner(screenplay,novel_id)
            if task['status']!='RUNNING':raise ValueError('task must be RUNNING before execution')
            if task.get('execution_token'):raise ValueError('asset task is already executing')
            if not task.get('provider_id') or not task.get('model_id'):raise ValueError('provider and model are required')
            asset=copy.deepcopy(next((a for a in screenplay.get('asset_requirements',[]) if a['id']==task['asset_id']),None))
            token=str(uuid4());attempt=task.get('attempts',0)
            rows[index]={**task,'execution_token':token}
            self._asset_save(novel_id,screenplay,rows)
        try:
            provider=self.asset_providers.get(task['provider_id']);endpoint=getattr(provider,'endpoint',None)
            from ..media_frames import provider_is_local
            # Legacy source-derived descriptions have no exact outbound review UI.
            # Approval of a screenplay/storyboard never grants cloud permission.
            if not provider_is_local(provider):raise ValueError('IMAGE_CLOUD_PROMPT_REVIEW_REQUIRED')
            if asset is None or not str(asset.get('description') or '').strip():raise ValueError('IMAGE_PROMPT_REQUIRED')
            request=AssetGenerationRequest(task['provider_id'],task['model_id'],asset['description'],task_id)
            with self._motion_lock:
                self._require_media_authorization(reauthorize)
                current_screenplay,current_rows,current_index=self._asset_record(novel_id,screenplay_id,task_id);current=current_rows[current_index]
                current_asset=next((a for a in current_screenplay.get('asset_requirements',[]) if a['id']==task['asset_id']),None)
                if (self._media_owner(current_screenplay,novel_id)!=owner or current.get('status')!='RUNNING'
                    or current.get('execution_token')!=token or current.get('attempts',0)!=attempt
                    or current.get('provider_id')!=task['provider_id'] or current.get('model_id')!=task['model_id']
                    or current.get('asset_id')!=task['asset_id'] or current_asset!=asset
                    or self.asset_providers.get(task['provider_id']) is not provider or getattr(provider,'endpoint',None)!=endpoint):
                    raise ValueError('MEDIA_DISPATCH_STATE_CHANGED')
                if not provider_is_local(provider):raise ValueError('IMAGE_CLOUD_PROMPT_REVIEW_REQUIRED')
            result=provider.generate(request)
            if not result.asset_uri or str(result.asset_uri).lower().startswith('placeholder://'):
                raise ValueError('IMAGE_PROVIDER_RESULT_INVALID')
            with self._motion_lock:
                screenplay,rows,index=self._asset_record(novel_id,screenplay_id,task_id);current=rows[index]
                if (current.get('status')!='RUNNING' or current.get('execution_token')!=token
                    or current.get('attempts',0)!=attempt or self._media_owner(screenplay,novel_id)!=owner):return screenplay
                rows[index]={**current,'status':'SUCCEEDED','asset_uri':result.asset_uri,'error':None,
                             'history':list(current.get('history',[]))+[{'status':'SUCCEEDED','at':utc()}]}
                return self._asset_save(novel_id,screenplay,rows)
        except Exception as exc:
            with self._motion_lock:
                screenplay,rows,index=self._asset_record(novel_id,screenplay_id,task_id);current=rows[index]
                if current.get('status')!='RUNNING' or current.get('execution_token')!=token or current.get('attempts',0)!=attempt:return screenplay
                error=str(exc) if isinstance(exc,ValueError) and str(exc).startswith(('MEDIA_','IMAGE_','asset provider is not configured:')) else 'IMAGE_PROVIDER_REQUEST_FAILED'
                rows[index]={**current,'status':'FAILED','error':error,'history':list(current.get('history',[]))+[{'status':'FAILED','at':utc(),'error':error}]}
                return self._asset_save(novel_id,screenplay,rows)
    def retry_asset_task(self,novel_id,screenplay_id,task_id):
        screenplay=next((r for r in self.list(novel_id) if r["id"]==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        task=next((r for r in screenplay.get("asset_tasks",[]) if r["id"]==task_id),None)
        if task is None: raise KeyError(task_id)
        return self.update_asset_task(novel_id,screenplay_id,task_id,{**task,"status":"PENDING","error":None})
    def recover_asset_tasks(self,novel_id,screenplay_id):
        screenplay=next((r for r in self.list(novel_id) if r["id"]==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        rows=list(screenplay.get("asset_tasks",[])); changed=False
        for i,row in enumerate(rows):
            if row.get("status")!="RUNNING": continue
            history=list(row.get("history",[])); history.append({"status":"PENDING","at":utc(),"error":"recovered after restart"})
            rows[i]={**row,"status":"PENDING","execution_token":None,"error":"recovered after restart","history":history}; changed=True
        if not changed: return screenplay
        return self._save_screenplay(novel_id,{**screenplay,"asset_tasks":rows,"task_revision":int(screenplay.get("task_revision",1))+1,"updated_at":utc()})
    def recover_all_asset_tasks(self,novel_id):
        results=[]
        for screenplay in self.list(novel_id):
            if screenplay.get("asset_tasks") is not None:
                results.append(self.recover_asset_tasks(novel_id, screenplay["id"]))
        return {"novel_id":novel_id,"screenplays":results}
    def cleanup_asset_tasks(self,novel_id,screenplay_id):
        screenplay=next((r for r in self.list(novel_id) if r["id"]==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        rows=list(screenplay.get("asset_tasks",[])); kept=[r for r in rows if r.get("status") not in {"SUCCEEDED","CANCELLED"}]
        removed=len(rows)-len(kept)
        if not removed: return {"screenplay":screenplay,"removed":0}
        updated=self._save_screenplay(novel_id,{**screenplay,"asset_tasks":kept,"task_revision":int(screenplay.get("task_revision",1))+1,"updated_at":utc()})
        return {"screenplay":updated,"removed":removed}
    def asset_task_stats(self,novel_id,screenplay_id=None):
        screenplays=self.list(novel_id)
        if screenplay_id is not None:
            screenplays=[r for r in screenplays if r.get("id")==screenplay_id]
            if not screenplays: raise KeyError(screenplay_id)
        statuses={"PENDING":0,"RUNNING":0,"SUCCEEDED":0,"FAILED":0,"CANCELLED":0}
        total=0; latest=None
        for screenplay in screenplays:
            for task in screenplay.get("asset_tasks",[]):
                status=task.get("status","PENDING"); statuses[status]=statuses.get(status,0)+1; total+=1
                stamp=task.get("history",[])[-1].get("at") if task.get("history") else None
                if stamp and (latest is None or stamp>latest): latest=stamp
        return {"novel_id":novel_id,"screenplay_id":screenplay_id,"total":total,"by_status":statuses,"latest_at":latest}
    def claim_asset_tasks(self,novel_id,limit=10,provider_id=None):
        limit=max(1,min(100,int(limit)))
        claimed=[]
        for screenplay in self.list(novel_id):
            rows=list(screenplay.get("asset_tasks",[])); changed=False
            for i,row in enumerate(rows):
                if len(claimed)>=limit: break
                if row.get("status")!="PENDING" or (provider_id and row.get("provider_id")!=provider_id): continue
                history=list(row.get("history",[])); history.append({"status":"RUNNING","at":utc(),"error":None})
                rows[i]={**row,"status":"RUNNING","error":None,"attempts":int(row.get("attempts",0))+1,"history":history}; claimed.append({"screenplay_id":screenplay["id"],"task":rows[i]}); changed=True
            if changed: self._save_screenplay(novel_id,{**screenplay,"asset_tasks":rows,"task_revision":int(screenplay.get("task_revision",1))+1,"updated_at":utc()})
            if len(claimed)>=limit: break
        return {"novel_id":novel_id,"claimed":claimed,"count":len(claimed)}
    def dispatch_asset_tasks(self,novel_id,limit=10,execute=False,provider_id=None):
        claimed=self.claim_asset_tasks(novel_id,limit,provider_id)["claimed"]
        if not execute:
            return {"novel_id":novel_id,"dry_run":True,"dispatched":claimed,"count":len(claimed)}
        results=[]
        for item in claimed:
            results.append(self.execute_asset_task(novel_id,item["screenplay_id"],item["task"]["id"]))
        return {"novel_id":novel_id,"dry_run":False,"dispatched":results,"count":len(results)}
    def timeout_asset_tasks(self,novel_id,timeout_seconds=3600):
        cutoff=datetime.now(timezone.utc)-timedelta(seconds=max(1,int(timeout_seconds)))
        changed=0; results=[]
        for screenplay in self.list(novel_id):
            rows=list(screenplay.get("asset_tasks",[])); dirty=False
            for i,row in enumerate(rows):
                if row.get("status")!="RUNNING": continue
                stamp=(row.get("history") or [{}])[-1].get("at")
                try: started=datetime.fromisoformat(stamp.replace("Z","+00:00"))
                except (AttributeError,ValueError): continue
                if started>cutoff: continue
                history=list(row.get("history",[])); history.append({"status":"FAILED","at":utc(),"error":"task execution timed out"})
                rows[i]={**row,"status":"FAILED","error":"task execution timed out","history":history}; changed+=1; dirty=True
            if dirty:
                results.append(self._save_screenplay(novel_id,{**screenplay,"asset_tasks":rows,"task_revision":int(screenplay.get("task_revision",1))+1,"updated_at":utc()}))
        return {"novel_id":novel_id,"timed_out":changed,"screenplays":results}
