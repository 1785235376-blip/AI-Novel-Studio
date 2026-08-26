from dataclasses import asdict
from ..narrative import (CharacterGoal,CharacterGoalStatus,ChapterNarrativeLink,Foreshadowing,ForeshadowingStatus,Mystery,MysteryStatus,NarrativeEntityType,NarrativeEvent,NarrativeProgressType,PlotThread,ThreadStatus,transition_character_goal,transition_foreshadowing,transition_mystery,transition_thread,validate_chapter_narrative_link)


class NarrativeStateService:
    def __init__(self,repository,chapters=None,novels=None,lore=None):self.repository=repository;self.chapters=chapters;self.novels=novels;self.lore=lore
    def create_thread(self,thread:PlotThread):return self.repository.create(thread.project_id,"threads",asdict(thread))
    def create_foreshadowing(self,item:Foreshadowing):return self.repository.create(item.project_id,"foreshadowing",asdict(item))
    def get_subject(self,project_id,subject_type,subject_id):
        kinds={"THREAD":"threads","PLOT_THREAD":"threads","FORESHADOWING":"foreshadowing","MYSTERY":"mysteries","CHARACTER_GOAL":"character_goals"}
        if subject_type not in kinds:raise ValueError(f"Unsupported narrative subject type: {subject_type}")
        return self.repository.get(project_id,kinds[subject_type],subject_id)
    def create_mystery(self,item:Mystery):return self.repository.create(item.project_id,"mysteries",asdict(item))
    def get_mystery(self,project_id,item_id):return self.repository.get(project_id,"mysteries",item_id)
    def list_mysteries(self,project_id):return self.repository.list(project_id,"mysteries")
    def transition_mystery(self,project_id,item_id,target,chapter_version_id=None):
        item=Mystery(**self.get_mystery(project_id,item_id));transition_mystery(item,MysteryStatus(target),chapter_version_id);return self.repository.update(project_id,"mysteries",item_id,asdict(item))
    def create_character_goal(self,item:CharacterGoal):
        if self.novels is not None and not any(x.get("id")==item.character_id for x in self.novels.get_data_set(item.project_id,"characters")):raise FileNotFoundError(item.character_id)
        return self.repository.create(item.project_id,"character_goals",asdict(item))
    def get_character_goal(self,project_id,item_id):return self.repository.get(project_id,"character_goals",item_id)
    def list_character_goals(self,project_id):return self.repository.list(project_id,"character_goals")
    def transition_character_goal(self,project_id,item_id,target,chapter_version_id=None):
        item=CharacterGoal(**self.get_character_goal(project_id,item_id));transition_character_goal(item,CharacterGoalStatus(target),chapter_version_id);return self.repository.update(project_id,"character_goals",item_id,asdict(item))
    def _validate_provenance(self,project_id,link):
        if self.chapters is not None:
            chapter=self.chapters.get(link.chapter_id)
            if chapter["novel_id"]!=project_id or chapter["version"]!=link.chapter_version:raise ValueError("chapter progress requires the current project chapter version")
        if self.lore is not None:
            for evidence_id in link.evidence_ids:
                if self.lore.get_evidence(evidence_id)["novel_id"]!=project_id:raise ValueError("evidence must belong to the same project")
    def validate_expectation_provenance(self,project_id,chapter_version_id,evidence_ids):
        if chapter_version_id:
            try:chapter_id,version=chapter_version_id.rsplit(":v",1);version=int(version)
            except (ValueError,TypeError):raise ValueError("invalid source_chapter_version_id")
            chapter=self.chapters.get(chapter_id)
            if chapter["novel_id"]!=project_id or chapter["version"]!=version:raise ValueError("expectation requires the current project chapter version")
        if self.lore is not None:
            for evidence_id in evidence_ids:
                if self.lore.get_evidence(evidence_id)["novel_id"]!=project_id:raise ValueError("evidence must belong to the same project")
    def record_chapter_narrative_progress(self,link:ChapterNarrativeLink):
        validate_chapter_narrative_link(link);self._validate_provenance(link.project_id,link)
        try:return self.repository.get(link.project_id,"chapter_links",link.id)
        except KeyError:pass
        kind,updated,event_payload=self._prepare_progress(link)
        return self.repository.record_progress(link.project_id,kind,link.entity_id,updated,event_payload,asdict(link))
    def _prepare_progress(self,link:ChapterNarrativeLink):
        validate_chapter_narrative_link(link);self._validate_provenance(link.project_id,link)
        kinds={NarrativeEntityType.PLOT_THREAD:"threads",NarrativeEntityType.FORESHADOWING:"foreshadowing",NarrativeEntityType.MYSTERY:"mysteries",NarrativeEntityType.CHARACTER_GOAL:"character_goals"};kind=kinds[link.entity_type]
        current=self.repository.get(link.project_id,kind,link.entity_id);updated=dict(current)
        chapter_version_id=f"{link.chapter_id}:v{link.chapter_version}"
        if link.entity_type is NarrativeEntityType.PLOT_THREAD:
            updated.setdefault("event_ids",[])
        elif link.entity_type is NarrativeEntityType.FORESHADOWING:
            item=Foreshadowing(**current);target=ForeshadowingStatus.DEVELOPING if link.progress_type is NarrativeProgressType.DEVELOPED else ForeshadowingStatus.PAYOFF;transition_foreshadowing(item,target,link.event_id if target is ForeshadowingStatus.PAYOFF else None);updated=asdict(item)
        elif link.entity_type is NarrativeEntityType.MYSTERY:
            item=Mystery(**current);target=MysteryStatus.DEVELOPING if link.progress_type is NarrativeProgressType.DEVELOPED else MysteryStatus.ANSWERED;transition_mystery(item,target,chapter_version_id);updated=asdict(item)
        else:
            item=CharacterGoal(**current)
            if link.progress_type is not NarrativeProgressType.ADVANCED:transition_character_goal(item,CharacterGoalStatus(link.progress_type.value),chapter_version_id)
            updated=asdict(item)
        event=NarrativeEvent(link.event_id,link.project_id,f"{link.entity_type}:{link.progress_type}",link.entity_id,chapter_version_id,link.evidence_ids,{"summary":link.summary,"link_id":link.id})
        if link.entity_type is NarrativeEntityType.PLOT_THREAD and event.id not in updated["event_ids"]:updated["event_ids"].append(event.id)
        event_payload=asdict(event);event_payload["fingerprint"]=event.fingerprint
        scope=getattr(self.repository,"scope",None)
        if scope:
            from hashlib import sha256
            from ..collaboration import DEFAULT_WORKSPACE_ID,default_storyline_id,main_branch_id
            if not (scope.workspace_id==DEFAULT_WORKSPACE_ID and scope.storyline_id==default_storyline_id(scope.project_id) and scope.branch_id==main_branch_id(scope.project_id)):
                event_payload["fingerprint"]=sha256(f"{event.fingerprint}|{scope.workspace_id}|{scope.storyline_id}|{scope.branch_id}".encode()).hexdigest()
        return kind,updated,event_payload
    def apply_proposal(self,proposal,link:ChapterNarrativeLink,accepted):
        kind,updated,event=self._prepare_progress(link)
        return self.repository.accept_proposal_atomic(link.project_id,proposal["id"],kind,link.entity_id,updated,event,asdict(link),accepted)
    def list_chapter_progress(self,project_id):return self.repository.list(project_id,"chapter_links")
    def transition_thread(self,project_id,thread_id,target,event:NarrativeEvent):
        current=self.repository.get(project_id,"threads",thread_id);transition_thread(PlotThread(**current),ThreadStatus(target));return self.repository.transition(project_id,"threads",thread_id,target,asdict(event))
    def transition_foreshadowing(self,project_id,item_id,target,event:NarrativeEvent):
        current=self.repository.get(project_id,"foreshadowing",item_id);transition_foreshadowing(Foreshadowing(**current),ForeshadowingStatus(target),event.id if target=="PAYOFF" else None);return self.repository.transition(project_id,"foreshadowing",item_id,target,asdict(event))
    def state(self,project_id):return {kind:self.repository.list(project_id,kind) for kind in ("threads","foreshadowing","events","mysteries","character_goals")}
