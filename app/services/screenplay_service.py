from datetime import datetime,timezone,timedelta
from uuid import uuid4
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

def validate_visual_continuity(shots: list[dict]) -> list[dict]:
    findings=[]
    for previous,current in zip(shots,shots[1:]):
        if previous.get('location') and current.get('location') and previous.get('location') != current.get('location') and not current.get('transition'):
            findings.append({'code':'LOCATION_JUMP','severity':'WARNING','from_shot_id':previous.get('id'),'to_shot_id':current.get('id'),'message':'相邻镜头地点发生变化，但未配置转场。'})
        if previous.get('time') and current.get('time') and previous.get('time') != current.get('time') and str(current.get('transition','')).upper() == 'CUT':
            findings.append({'code':'TIME_JUMP_CUT','severity':'INFO','from_shot_id':previous.get('id'),'to_shot_id':current.get('id'),'message':'时间发生变化，当前使用直接剪切。'})
        if previous.get('emotion') and current.get('emotion') and previous.get('emotion') != current.get('emotion') and not current.get('action'):
            findings.append({'code':'EMOTION_DISCONTINUITY','severity':'WARNING','from_shot_id':previous.get('id'),'to_shot_id':current.get('id'),'message':'情绪发生跳变，建议补充动作或转场说明。'})
    return findings

def require_motion_frames(task: dict) -> None:
    if not task.get('start_frame') or not task.get('end_frame'):
        raise ValueError('motion task requires start_frame and end_frame before execution')

class ScreenplayService:
    def __init__(self,novels,chapters,asset_providers=None,video_providers=None):self.novels=novels;self.chapters=chapters;self.asset_providers=asset_providers or AssetProviderRegistry();self.video_providers=video_providers or {'deterministic':DeterministicVideoProvider()}
    def register_video_provider(self,provider_id,provider):
        if not str(provider_id).strip() or not hasattr(provider,'generate'): raise ValueError('invalid video provider')
        self.video_providers[str(provider_id).strip()]=provider
    def list(self,novel_id):return self.novels.list_screenplays(novel_id)
    def create(self,novel_id,title=""):
        novel=self.novels.get(novel_id);chapters=self.chapters.list(novel_id);now=utc();scenes=[]
        for sequence,summary in enumerate(chapters,1):
            chapter=self.chapters.get(summary["id"]);scenes.append({"id":str(uuid4()),"sequence":sequence,"source_chapter_id":chapter["id"],"source_version":chapter["version"],"heading":chapter["title"],"time":"未设定","location":"未设定","characters":[],"action":"待从章节提炼可见行动","dialogue":[],"emotion":"待设定","status":"DRAFT"})
        screenplay={"id":str(uuid4()),"novel_id":novel_id,"source_title":novel["title"],"title":title.strip() or f"{novel['title']} 影视剧本","status":"DRAFT","revision":1,"scenes":scenes,"created_at":now,"updated_at":now}
        return self.novels.save_screenplay(novel_id,screenplay)
    def update_scene(self,novel_id,screenplay_id,scene_id,payload):
        screenplay=next((row for row in self.list(novel_id) if row["id"]==screenplay_id),None)
        if screenplay is None:raise KeyError(screenplay_id)
        if screenplay["status"]!="DRAFT":raise ValueError("approved screenplay is frozen")
        scenes=list(screenplay["scenes"]);index=next((i for i,row in enumerate(scenes) if row["id"]==scene_id),None)
        if index is None:raise KeyError(scene_id)
        immutable={key:scenes[index][key] for key in ("id","sequence","source_chapter_id","source_version")};scenes[index]={**immutable,"heading":payload["heading"].strip(),"time":payload["time"].strip(),"location":payload["location"].strip(),"characters":[str(x).strip() for x in payload.get("characters",[]) if str(x).strip()],"action":payload["action"].strip(),"dialogue":payload.get("dialogue",[]),"emotion":payload["emotion"].strip(),"status":"DRAFT"}
        updated={**screenplay,"scenes":scenes,"revision":screenplay["revision"]+1,"updated_at":utc()};return self.novels.save_screenplay(novel_id,updated)
    def approve(self,novel_id,screenplay_id):
        screenplay=next((row for row in self.list(novel_id) if row["id"]==screenplay_id),None)
        if screenplay is None:raise KeyError(screenplay_id)
        if screenplay["status"]!="DRAFT":raise ValueError("screenplay is already decided")
        return self.novels.save_screenplay(novel_id,{**screenplay,"status":"APPROVED","updated_at":utc()})
    def plan_shots(self,novel_id,screenplay_id):
        screenplay=next((row for row in self.list(novel_id) if row["id"]==screenplay_id),None)
        if screenplay is None:raise KeyError(screenplay_id)
        if screenplay["status"]!="APPROVED":raise ValueError("screenplay must be approved before shot planning")
        if screenplay.get("shots"):return screenplay
        shots=[]
        for scene in screenplay["scenes"]:
            shots.append({"id":str(uuid4()),"number":scene["sequence"]*10+1,"scene_id":scene["id"],"source_chapter_id":scene["source_chapter_id"],"shot_size":"MEDIUM","camera_angle":"EYE_LEVEL","camera_motion":"STATIC","subject_position":"待设计","action":scene["action"],"dialogue":scene["dialogue"],"sound_effect":"待设计","duration_seconds":5,"status":"DRAFT"})
        return self.novels.save_screenplay(novel_id,{**screenplay,"shots":shots,"shot_revision":1,"updated_at":utc()})
    def update_shot(self,novel_id,screenplay_id,shot_id,payload):
        screenplay=next((row for row in self.list(novel_id) if row["id"]==screenplay_id),None)
        if screenplay is None:raise KeyError(screenplay_id)
        if screenplay.get("shot_status")=="APPROVED":raise ValueError("approved shot plan is frozen")
        shots=list(screenplay.get("shots",[]));index=next((i for i,row in enumerate(shots) if row["id"]==shot_id),None)
        if index is None:raise KeyError(shot_id)
        immutable={key:shots[index][key] for key in ("id","number","scene_id","source_chapter_id")};shots[index]={**immutable,"shot_size":payload["shot_size"],"camera_angle":payload["camera_angle"],"camera_motion":payload["camera_motion"],"subject_position":payload["subject_position"],"action":payload["action"],"dialogue":payload.get("dialogue",[]),"sound_effect":payload["sound_effect"],"duration_seconds":max(1,min(600,int(payload["duration_seconds"]))),"status":"DRAFT"}
        return self.novels.save_screenplay(novel_id,{**screenplay,"shots":shots,"shot_revision":int(screenplay.get("shot_revision",1))+1,"updated_at":utc()})
    def approve_shots(self,novel_id,screenplay_id):
        screenplay=next((row for row in self.list(novel_id) if row["id"]==screenplay_id),None)
        if screenplay is None:raise KeyError(screenplay_id)
        if not screenplay.get("shots"):raise ValueError("shot plan is empty")
        if screenplay.get("shot_status")=="APPROVED":raise ValueError("shot plan is already approved")
        return self.novels.save_screenplay(novel_id,{**screenplay,"shot_status":"APPROVED","updated_at":utc()})
    def plan_storyboard(self,novel_id,screenplay_id):
        screenplay=next((row for row in self.list(novel_id) if row["id"]==screenplay_id),None)
        if screenplay is None:raise KeyError(screenplay_id)
        if screenplay.get("shot_status")!="APPROVED":raise ValueError("shot plan must be approved before storyboard")
        if screenplay.get("storyboard"):return screenplay
        cards=[{"id":str(uuid4()),"number":shot["number"],"shot_id":shot["id"],"scene_id":shot["scene_id"],"source_chapter_id":shot["source_chapter_id"],"frame_prompt":"待设计画面","composition":"待设计构图","color":"待设计色彩","status":"DRAFT"} for shot in screenplay.get("shots",[])]
        return self.novels.save_screenplay(novel_id,{**screenplay,"storyboard":cards,"storyboard_revision":1,"updated_at":utc()})
    def update_storyboard_card(self,novel_id,screenplay_id,card_id,payload):
        screenplay=next((row for row in self.list(novel_id) if row["id"]==screenplay_id),None)
        if screenplay is None:raise KeyError(screenplay_id)
        if screenplay.get("storyboard_status")=="APPROVED":raise ValueError("storyboard is frozen")
        cards=list(screenplay.get("storyboard",[]));index=next((i for i,row in enumerate(cards) if row["id"]==card_id),None)
        if index is None:raise KeyError(card_id)
        immutable={k:cards[index][k] for k in ("id","number","shot_id","scene_id","source_chapter_id")};cards[index]={**immutable,"frame_prompt":str(payload.get("frame_prompt","")).strip(),"composition":str(payload.get("composition","")).strip(),"color":str(payload.get("color","")).strip(),"status":"DRAFT"}
        return self.novels.save_screenplay(novel_id,{**screenplay,"storyboard":cards,"storyboard_revision":int(screenplay.get("storyboard_revision",1))+1,"updated_at":utc()})
    def approve_storyboard(self,novel_id,screenplay_id):
        screenplay=next((row for row in self.list(novel_id) if row["id"]==screenplay_id),None)
        if screenplay is None:raise KeyError(screenplay_id)
        if not screenplay.get("storyboard"):raise ValueError("storyboard is empty")
        if screenplay.get("storyboard_status")=="APPROVED":raise ValueError("storyboard is already approved")
        return self.novels.save_screenplay(novel_id,{**screenplay,"storyboard_status":"APPROVED","updated_at":utc()})
    def plan_transitions(self,novel_id,screenplay_id):
        screenplay=next((r for r in self.list(novel_id) if r["id"]==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        if screenplay.get("shot_status")!="APPROVED": raise ValueError("shot plan must be approved before transitions")
        if screenplay.get("transitions") is not None: return screenplay
        shots=screenplay.get("shots",[]); transitions=[]
        for prev,nxt in zip(shots,shots[1:]):
            transitions.append({"id":str(uuid4()),"from_shot_id":prev["id"],"to_shot_id":nxt["id"],"type":"CUT","duration_seconds":0,"note":"待设计","status":"DRAFT"})
        return self.novels.save_screenplay(novel_id,{**screenplay,"transitions":transitions,"transition_revision":1,"updated_at":utc()})
    def update_transition(self,novel_id,screenplay_id,transition_id,payload):
        screenplay=next((r for r in self.list(novel_id) if r["id"]==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        if screenplay.get("transition_status")=="APPROVED": raise ValueError("transitions are frozen")
        rows=list(screenplay.get("transitions",[])); i=next((i for i,r in enumerate(rows) if r["id"]==transition_id),None)
        if i is None: raise KeyError(transition_id)
        immutable={k:rows[i][k] for k in ("id","from_shot_id","to_shot_id")}; new_prompt=str(payload.get("prompt",rows[i].get("prompt", ""))).strip(); history=list(rows[i].get("prompt_history",[])); old_prompt=str(rows[i].get("prompt","")).strip();
        if old_prompt and old_prompt != new_prompt: history.append({"prompt":old_prompt,"saved_at":utc()})
        rows[i]={**immutable,"type":str(payload.get("type","CUT")).strip() or "CUT","duration_seconds":max(0,min(30,int(payload.get("duration_seconds",0)))),"note":str(payload.get("note","")).strip(),"prompt":new_prompt,"prompt_history":history[-10:],"prompt_status":"EDITED","status":"DRAFT"}
        return self.novels.save_screenplay(novel_id,{**screenplay,"transitions":rows,"transition_revision":int(screenplay.get("transition_revision",1))+1,"updated_at":utc()})
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
        return self.novels.save_screenplay(novel_id,{**screenplay,'transitions':rows,'transition_revision':int(screenplay.get('transition_revision',1))+1,'updated_at':utc()})
    def create_motion_tasks(self,novel_id,screenplay_id):
        screenplay=next((r for r in self.list(novel_id) if r['id']==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        tasks=list(screenplay.get('motion_tasks',[])); existing={task.get('transition_id') for task in tasks}
        for row in screenplay.get('transitions',[]):
            if row.get('motion_prompt') and row.get('id') not in existing:
                configured=next(((provider_id,getattr(provider,'default_model','')) for provider_id,provider in self.video_providers.items() if provider_id!='deterministic' and getattr(provider,'health_check',lambda:False)()),(None,None))
                tasks.append({'id':str(uuid4()),'transition_id':row['id'],'prompt':row['motion_prompt'],'provider_id':configured[0],'model_id':configured[1],'start_frame':None,'end_frame':None,'status':'PENDING','progress':0,'error':None if configured[0] else 'VIDEO_PROVIDER_NOT_CONFIGURED','created_at':utc()})
        return self.novels.save_screenplay(novel_id,{**screenplay,'motion_tasks':tasks,'motion_task_revision':int(screenplay.get('motion_task_revision',0))+1,'updated_at':utc()})
    def update_motion_task(self,novel_id,screenplay_id,task_id,status):
        screenplay=next((r for r in self.list(novel_id) if r['id']==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        rows=list(screenplay.get('motion_tasks',[])); index=next((i for i,r in enumerate(rows) if r['id']==task_id),None)
        if index is None: raise KeyError(task_id)
        current=rows[index].get('status','PENDING'); allowed={'PENDING':{'CANCELLED'},'RUNNING':{'CANCELLED'},'FAILED':{'PENDING','CANCELLED'},'CANCELLED':{'PENDING'},'SUCCEEDED':set()}
        if status!=current and status not in allowed.get(current,set()): raise ValueError(f'invalid motion task transition: {current} -> {status}')
        rows[index]={**rows[index],'status':status,'updated_at':utc()}
        return self.novels.save_screenplay(novel_id,{**screenplay,'motion_tasks':rows,'motion_task_revision':int(screenplay.get('motion_task_revision',0))+1,'updated_at':utc()})
    def update_motion_frames(self,novel_id,screenplay_id,task_id,start_frame=None,end_frame=None):
        screenplay=next((r for r in self.list(novel_id) if r['id']==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        rows=list(screenplay.get('motion_tasks',[])); index=next((i for i,r in enumerate(rows) if r['id']==task_id),None)
        if index is None: raise KeyError(task_id)
        def validate(value):
            if value is None or value == '': return value
            value=str(value).strip()
            if not value.lower().startswith(('http://','https://')): raise ValueError('frame URL must use http or https')
            return value
        row=rows[index]; new_start=validate(start_frame) if start_frame is not None else row.get('start_frame'); new_end=validate(end_frame) if end_frame is not None else row.get('end_frame'); frame_history=list(row.get('frame_history',[]));
        if row.get('start_frame')!=new_start or row.get('end_frame')!=new_end: frame_history.append({'start_frame':row.get('start_frame'),'end_frame':row.get('end_frame'),'changed_at':utc()})
        rows[index]={**row,'start_frame':new_start,'end_frame':new_end,'frame_history':frame_history[-10:],'updated_at':utc()}
        return self.novels.save_screenplay(novel_id,{**screenplay,'motion_tasks':rows,'motion_task_revision':int(screenplay.get('motion_task_revision',0))+1,'updated_at':utc()})
    def update_motion_provider(self,novel_id,screenplay_id,task_id,provider_id,model_id):
        screenplay=next((r for r in self.list(novel_id) if r['id']==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        if provider_id not in self.video_providers: raise ValueError(f'video provider is not configured: {provider_id}')
        rows=list(screenplay.get('motion_tasks',[])); index=next((i for i,r in enumerate(rows) if r['id']==task_id),None)
        if index is None: raise KeyError(task_id)
        rows[index]={**rows[index],'provider_id':provider_id,'model_id':str(model_id).strip() or 'video-placeholder','updated_at':utc()}
        return self.novels.save_screenplay(novel_id,{**screenplay,'motion_tasks':rows,'motion_task_revision':int(screenplay.get('motion_task_revision',0))+1,'updated_at':utc()})
    def execute_motion_task(self,novel_id,screenplay_id,task_id):
        screenplay=next((r for r in self.list(novel_id) if r['id']==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        rows=list(screenplay.get('motion_tasks',[])); index=next((i for i,r in enumerate(rows) if r['id']==task_id),None)
        if index is None: raise KeyError(task_id)
        task=rows[index]
        if task.get('status')!='PENDING': raise ValueError('motion task must be PENDING before execution')
        require_motion_frames(task)
        provider_id=task.get('provider_id') or 'deterministic'; model_id=task.get('model_id') or 'video-placeholder'; provider=self.video_providers.get(provider_id)
        if provider is None: raise ValueError(f'video provider is not configured: {provider_id}')
        generated=provider.generate(VideoGenerationRequest(provider_id,model_id,task.get('prompt',''),task['start_frame'],task['end_frame'],task_id)); asynchronous=provider_id!='deterministic' and not str(generated.video_uri).lower().startswith(('http://','https://')); result={'kind':'VIDEO','task_id':task_id,'prompt':task.get('prompt',''),'asset_id':f"motion-{task_id}",'url':None if asynchronous else generated.video_uri,'provider_id':generated.provider_id,'model_id':generated.model_id,'created_at':utc()}
        rows[index]={**task,'status':'RUNNING' if asynchronous else 'SUCCEEDED','progress':0 if asynchronous else 100,'remote_task_id':generated.video_uri if asynchronous else task.get('remote_task_id'),'result':result,'updated_at':utc()}
        return self.novels.save_screenplay(novel_id,{**screenplay,'motion_tasks':rows,'motion_task_revision':int(screenplay.get('motion_task_revision',0))+1,'updated_at':utc()})
    def attach_motion_result(self,novel_id,screenplay_id,task_id,url,media_type='video/mp4'):
        screenplay=next((r for r in self.list(novel_id) if r['id']==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        rows=list(screenplay.get('motion_tasks',[])); index=next((i for i,r in enumerate(rows) if r['id']==task_id),None)
        if index is None: raise KeyError(task_id)
        result={**rows[index].get('result',{}),'url':str(url).strip(),'media_type':media_type,'attached_at':utc()}
        history=list(rows[index].get('result_history',[])); previous=rows[index].get('result');
        if previous: history.append({**previous,'replaced_at':utc()})
        rows[index]={**rows[index],'status':'SUCCEEDED','result':result,'result_history':history[-10:],'updated_at':utc()}
        return self.novels.save_screenplay(novel_id,{**screenplay,'motion_tasks':rows,'motion_task_revision':int(screenplay.get('motion_task_revision',0))+1,'updated_at':utc()})
    def motion_callback(self,novel_id,screenplay_id,task_id,status,progress=0,url=None,error=None):
        screenplay=next((r for r in self.list(novel_id) if r['id']==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        rows=list(screenplay.get('motion_tasks',[])); index=next((i for i,r in enumerate(rows) if r['id']==task_id),None)
        if index is None: raise KeyError(task_id)
        if status not in {'PENDING','RUNNING','SUCCEEDED','FAILED','CANCELLED'}: raise ValueError('invalid motion callback status')
        row=rows[index]; updated={**row,'status':status,'progress':max(0,min(100,int(progress))),'error':error,'updated_at':utc()}
        if url: updated['result']={**row.get('result',{}),'url':url,'media_type':'video/mp4','attached_at':utc()}
        rows[index]=updated
        return self.novels.save_screenplay(novel_id,{**screenplay,'motion_tasks':rows,'motion_task_revision':int(screenplay.get('motion_task_revision',0))+1,'updated_at':utc()})
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
        return self.novels.save_screenplay(novel_id,{**screenplay,'motion_tasks':rows,'motion_task_revision':int(screenplay.get('motion_task_revision',0))+1,'updated_at':utc()})
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
        screenplay=next(r for r in self.list(novel_id) if r['id']==screenplay_id); rows=list(screenplay.get('motion_tasks',[])); index=next(i for i,r in enumerate(rows) if r['id']==task_id); job={**ref,'import_status':'PENDING_DOWNLOAD','filename':f"{ref.get('asset_id') or task_id}.mp4",'created_at':utc()}; rows[index]={**rows[index],'asset_import':job,'updated_at':utc()}; self.novels.save_screenplay(novel_id,{**screenplay,'motion_tasks':rows,'updated_at':utc()}); return job
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
        if count: self.novels.save_screenplay(novel_id,{**screenplay,'motion_tasks':rows,'updated_at':utc()})
        return {'screenplay_id':screenplay_id,'retried':count}
    def download_motion_asset(self,novel_id,screenplay_id,task_id,asset_library):
        import base64
        from ..net_safety import fetch_outbound_bytes
        job=self.motion_asset_import_status(novel_id,screenplay_id,task_id)
        if not job.get('url'): raise ValueError('asset import URL is missing')
        try:
            data=fetch_outbound_bytes(job['url'],asset_library.MAX_BYTES,30)
            asset=asset_library.create(novel_id,job['filename'],base64.b64encode(data).decode('ascii'),'video/mp4','video',f"motion-import:{task_id}")
            updated={**job,'import_status':'COMPLETED','asset':asset,'completed_at':utc()}
            screenplay=next(r for r in self.list(novel_id) if r['id']==screenplay_id); task=next(r for r in screenplay.get('motion_tasks',[]) if r['id']==task_id); result={**(task.get('result') or {}),'asset_id':asset.get('id') if isinstance(asset,dict) else asset}; rows=list(screenplay.get('motion_tasks',[])); index=next(i for i,r in enumerate(rows) if r['id']==task_id); rows[index]={**task,'result':result,'asset_import':updated,'updated_at':utc()}; self.novels.save_screenplay(novel_id,{**screenplay,'motion_tasks':rows,'updated_at':utc()})
            return updated
        except Exception as exc:
            updated={**job,'import_status':'FAILED','error':str(exc)}
            self._save_motion_import(novel_id,screenplay_id,task_id,updated)
            return updated
    def _save_motion_import(self,novel_id,screenplay_id,task_id,job):
        screenplay=next(r for r in self.list(novel_id) if r['id']==screenplay_id); rows=list(screenplay.get('motion_tasks',[])); index=next(i for i,r in enumerate(rows) if r['id']==task_id); rows[index]={**rows[index],'asset_import':job,'updated_at':utc()}; self.novels.save_screenplay(novel_id,{**screenplay,'motion_tasks':rows,'updated_at':utc()})
    def retry_motion_asset_import(self,novel_id,screenplay_id,task_id):
        screenplay=next((r for r in self.list(novel_id) if r['id']==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        rows=list(screenplay.get('motion_tasks',[])); index=next((i for i,r in enumerate(rows) if r['id']==task_id),None)
        if index is None: raise KeyError(task_id)
        job=rows[index].get('asset_import')
        if not job: raise ValueError('asset import has not been requested')
        updated={**job,'import_status':'PENDING_DOWNLOAD','error':None,'retry_at':utc()}; rows[index]={**rows[index],'asset_import':updated,'updated_at':utc()}
        self.novels.save_screenplay(novel_id,{**screenplay,'motion_tasks':rows,'updated_at':utc()}); return updated
    def motion_frame_history(self,novel_id,screenplay_id,task_id):
        screenplay=next((r for r in self.list(novel_id) if r['id']==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        task=next((r for r in screenplay.get('motion_tasks',[]) if r['id']==task_id),None)
        if task is None: raise KeyError(task_id)
        return {'task_id':task_id,'current':{'start_frame':task.get('start_frame'),'end_frame':task.get('end_frame')},'history':task.get('frame_history',[])}
    def validate_visual_continuity(self,novel_id,screenplay_id):
        screenplay=next((r for r in self.list(novel_id) if r['id']==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        return {'screenplay_id':screenplay_id,'findings':validate_visual_continuity(screenplay.get('shots',[]))}
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
    def approve_transitions(self,novel_id,screenplay_id):
        screenplay=next((r for r in self.list(novel_id) if r["id"]==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        if screenplay.get("transitions") is None: raise ValueError("transitions are not planned")
        if screenplay.get("transition_status")=="APPROVED": raise ValueError("transitions already approved")
        transitions=[{**row,"prompt_status":"FROZEN"} for row in screenplay.get("transitions",[])]
        return self.novels.save_screenplay(novel_id,{**screenplay,"transitions":transitions,"transition_status":"APPROVED","updated_at":utc()})
    def plan_assets(self,novel_id,screenplay_id):
        screenplay=next((r for r in self.list(novel_id) if r["id"]==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        if screenplay.get("storyboard_status")!="APPROVED": raise ValueError("storyboard must be approved before asset planning")
        if screenplay.get("asset_requirements") is not None: return screenplay
        assets=[{"id":str(uuid4()),"storyboard_id":card["id"],"shot_id":card["shot_id"],"kind":"IMAGE","description":card["frame_prompt"],"status":"PENDING","notes":"待准备"} for card in screenplay.get("storyboard",[])]
        return self.novels.save_screenplay(novel_id,{**screenplay,"asset_requirements":assets,"asset_revision":1,"updated_at":utc()})
    def update_asset(self,novel_id,screenplay_id,asset_id,payload):
        screenplay=next((r for r in self.list(novel_id) if r["id"]==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        if screenplay.get("asset_status")=="APPROVED": raise ValueError("asset requirements are frozen")
        rows=list(screenplay.get("asset_requirements",[])); i=next((i for i,r in enumerate(rows) if r["id"]==asset_id),None)
        if i is None: raise KeyError(asset_id)
        immutable={k:rows[i][k] for k in ("id","storyboard_id","shot_id")}; rows[i]={**immutable,"kind":str(payload.get("kind","IMAGE")).strip() or "IMAGE","description":str(payload.get("description","")).strip(),"status":str(payload.get("status","PENDING")).strip() or "PENDING","notes":str(payload.get("notes","")).strip()}
        return self.novels.save_screenplay(novel_id,{**screenplay,"asset_requirements":rows,"asset_revision":int(screenplay.get("asset_revision",1))+1,"updated_at":utc()})
    def approve_assets(self,novel_id,screenplay_id):
        screenplay=next((r for r in self.list(novel_id) if r["id"]==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        if screenplay.get("asset_requirements") is None: raise ValueError("asset requirements are not planned")
        if screenplay.get("asset_status")=="APPROVED": raise ValueError("asset requirements already approved")
        return self.novels.save_screenplay(novel_id,{**screenplay,"asset_status":"APPROVED","updated_at":utc()})
    def create_asset_tasks(self,novel_id,screenplay_id):
        screenplay=next((r for r in self.list(novel_id) if r["id"]==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        if screenplay.get("asset_status")!="APPROVED": raise ValueError("assets must be approved before generation")
        if screenplay.get("asset_tasks") is not None: return screenplay
        preferred=next(((provider_id,provider) for provider_id,provider in self.asset_providers._providers.items() if getattr(provider,'health_check',lambda:True)()),(None,None))
        default_provider,provider=preferred
        default_model=getattr(provider,"default_model",None) if provider else None
        tasks=[{"id":str(uuid4()),"asset_id":a["id"],"provider_id":default_provider,"model_id":default_model,"status":"PENDING","error":None,"attempts":0,"history":[{"status":"PENDING","at":utc()}]} for a in screenplay["asset_requirements"]]
        return self.novels.save_screenplay(novel_id,{**screenplay,"asset_tasks":tasks,"task_revision":1,"updated_at":utc()})
    def update_asset_task(self,novel_id,screenplay_id,task_id,payload):
        screenplay=next((r for r in self.list(novel_id) if r["id"]==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        rows=list(screenplay.get("asset_tasks",[])); i=next((i for i,r in enumerate(rows) if r["id"]==task_id),None)
        if i is None: raise KeyError(task_id)
        status=str(payload.get("status",rows[i]["status"]))
        if status not in {"PENDING","RUNNING","SUCCEEDED","FAILED","CANCELLED"}: raise ValueError("invalid task status")
        current=rows[i]["status"]
        allowed={"PENDING":{"RUNNING","CANCELLED"},"RUNNING":{"SUCCEEDED","FAILED","CANCELLED"},"FAILED":{"PENDING","CANCELLED"},"CANCELLED":{"PENDING"},"SUCCEEDED":set()}
        if status!=current and status not in allowed.get(current,set()): raise ValueError(f"invalid task transition: {current} -> {status}")
        row=rows[i]; history=list(row.get("history",[])); history.append({"status":status,"at":utc(),"error":payload.get("error")}); attempts=int(row.get("attempts",0))+(1 if status=="RUNNING" else 0)
        rows[i]={**row,"status":status,"provider_id":payload.get("provider_id",row.get("provider_id")),"model_id":payload.get("model_id",row.get("model_id")),"error":payload.get("error"),"attempts":attempts,"history":history}
        return self.novels.save_screenplay(novel_id,{**screenplay,"asset_tasks":rows,"task_revision":int(screenplay.get("task_revision",1))+1,"updated_at":utc()})
    def execute_asset_task(self,novel_id,screenplay_id,task_id):
        screenplay=next((r for r in self.list(novel_id) if r["id"]==screenplay_id),None)
        if screenplay is None: raise KeyError(screenplay_id)
        task=next((r for r in screenplay.get("asset_tasks",[]) if r["id"]==task_id),None)
        if task is None: raise KeyError(task_id)
        if task["status"]!="RUNNING": raise ValueError("task must be RUNNING before execution")
        if not task.get("provider_id") or not task.get("model_id"): raise ValueError("provider and model are required")
        asset=next((a for a in screenplay.get("asset_requirements",[]) if a["id"]==task["asset_id"]),None)
        try:
            provider=self.asset_providers.get(task.get("provider_id"))
            result=provider.generate(AssetGenerationRequest(task["provider_id"],task["model_id"],asset["description"],task_id))
            rows=[{**r,"status":"SUCCEEDED","asset_uri":result.asset_uri,"error":None,"history":list(r.get("history",[]))+[{"status":"SUCCEEDED","at":utc()}]} if r["id"]==task_id else r for r in screenplay["asset_tasks"]]
            return self.novels.save_screenplay(novel_id,{**screenplay,"asset_tasks":rows,"updated_at":utc()})
        except Exception as exc:
            return self.update_asset_task(novel_id,screenplay_id,task_id,{**task,"status":"FAILED","error":str(exc)})
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
            rows[i]={**row,"status":"PENDING","error":"recovered after restart","history":history}; changed=True
        if not changed: return screenplay
        return self.novels.save_screenplay(novel_id,{**screenplay,"asset_tasks":rows,"task_revision":int(screenplay.get("task_revision",1))+1,"updated_at":utc()})
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
        updated=self.novels.save_screenplay(novel_id,{**screenplay,"asset_tasks":kept,"task_revision":int(screenplay.get("task_revision",1))+1,"updated_at":utc()})
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
            if changed: self.novels.save_screenplay(novel_id,{**screenplay,"asset_tasks":rows,"task_revision":int(screenplay.get("task_revision",1))+1,"updated_at":utc()})
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
                results.append(self.novels.save_screenplay(novel_id,{**screenplay,"asset_tasks":rows,"task_revision":int(screenplay.get("task_revision",1))+1,"updated_at":utc()}))
        return {"novel_id":novel_id,"timed_out":changed,"screenplays":results}
