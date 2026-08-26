from ..config import settings
from ..context import build_context_from_sources
from ..lore.context_view import ContextEnvelope, LoreContextBuilder
from ..repositories.interfaces import ChapterRepositoryProtocol, NovelRepositoryProtocol
from .context_snapshot_service import ContextSnapshotService
from ..narrative_context import NarrativeContextBuilder
from ..context_policy import ContextPolicy,ContextPolicyItem,ContextSourceType
from ..context_pack_v2 import ContextPackV2Builder


class ContextService:
    def __init__(self, novels: NovelRepositoryProtocol, chapters: ChapterRepositoryProtocol,
                 lore=None, enable_lore_context=None,narrative_repository=None,enable_narrative_context=None,narrative_token_budget=None,context_policy_token_budget=None,enable_context_pack_v2=None):
        self.novels = novels
        self.chapters = chapters
        self.lore = lore
        self.enable_lore_context = settings.enable_lore_context if enable_lore_context is None else enable_lore_context
        self.narrative_repository=narrative_repository
        self.enable_narrative_context=settings.enable_narrative_context if enable_narrative_context is None else enable_narrative_context
        self.narrative_token_budget=settings.narrative_context_token_budget if narrative_token_budget is None else narrative_token_budget
        self.context_policy_token_budget=settings.context_policy_token_budget if context_policy_token_budget is None else context_policy_token_budget
        self.enable_context_pack_v2=settings.enable_context_pack_v2 if enable_context_pack_v2 is None else enable_context_pack_v2

    def _attach_context_pack_v2(self,result,cloud=False,instruction=""):
        if not self.enable_context_pack_v2:return result
        state=result.get("current_story_state",{})
        candidates=ContextPackV2Builder.extract_candidates(
            characters=[{"id":str(x),"content":x} for x in state.get("active_characters",[])],
            lore=[entry for section in result.get("lore_memory",{}).values() if isinstance(section,list) for entry in section],
            timeline=state.get("timeline",[]),
            recent_chapters=[{"id":f"{result.get('novel_id')}:{result.get('chapter')}","content":state,"chapter_number":result.get("chapter")}],
        )
        result["context_pack_v2"]=ContextPackV2Builder(self.context_policy_token_budget).build(candidates,enabled=True,cloud=cloud,query=instruction,character_ids=state.get("active_characters",[]),current_chapter=result.get("chapter")).model_dump(mode="json")
        return result

    def _narrative_context(self,base,novel_id,chapter_number):
        if not self.enable_narrative_context or self.narrative_repository is None:return None
        chapter=self.chapters.get(f"{novel_id}:{chapter_number}");active=base.get("current_story_state",{}).get("active_characters",[])
        return NarrativeContextBuilder(self.narrative_repository,self.narrative_token_budget).build(novel_id,chapter["id"],chapter["version"],active)

    def _context_policy(self,base,narrative=None,lore_memory=None,cloud=False):
        if not self.enable_lore_context and not self.enable_narrative_context:return None
        policy=ContextPolicy(self.context_policy_token_budget);project=base["novel_id"];chapter_id=f"{project}:{base['chapter']}";chapter=self.chapters.get(chapter_id);chapter_version_id=f"{chapter_id}:v{chapter['version']}";items=[]
        state=base.get("current_story_state",{})
        if state:items.append(ContextPolicyItem(metadata=policy.metadata(ContextSourceType.ACCEPTED_CHAPTER,chapter_id,project,chapter_version_id=chapter_version_id,selection_reasons=["CURRENT_CHAPTER"],fact_key="accepted_chapter_state"),value=state))
        if lore_memory is not None:
            for section in ("short_memory","medium_memory","long_memory"):
                for index,memory in enumerate(lore_memory.get(section,[])):
                    source_id=str(memory.get("id",f"{section}:{index}"));items.append(ContextPolicyItem(metadata=policy.metadata(ContextSourceType.LORE_MEMORY,source_id,project,selection_reasons=[section.upper()]),value=memory))
        if narrative is not None:
            for section in ("plot_threads","foreshadowing","mysteries","character_goals"):
                for entry in narrative.get(section,[]):items.append(ContextPolicyItem(metadata=policy.metadata(ContextSourceType.NARRATIVE_STATE,entry["id"],project,chapter_version_id=(entry.get("latest_progress") or {}).get("chapter_version_id"),evidence_ids=(entry.get("latest_progress") or {}).get("evidence_ids",[]),selection_reasons=[entry["selection_reason"]]),value=entry))
            for finding in narrative.get("findings",[]):items.append(ContextPolicyItem(metadata=policy.metadata(ContextSourceType.NARRATIVE_FINDING,finding["finding_id"],project,chapter_version_id=finding.get("chapter_version_id"),evidence_ids=finding.get("evidence_ids",[]),selection_reasons=[finding["selection_reason"]]),value=finding))
        return policy.apply(items,cloud)

    def build_envelope(self, novel_id, chapter_number, instruction="", cloud=False, operation=""):
        base = build_context_from_sources(
            self.novels.get_context_sources(novel_id), novel_id, chapter_number, instruction, cloud
        )
        if not self.lore:return None
        envelope=LoreContextBuilder(self.lore).build(
            base, chapter_number, cloud, instruction=instruction, operation=operation
        )
        envelope.narrative_context=self._narrative_context(base,novel_id,chapter_number);envelope.context_policy=self._context_policy(base,envelope.narrative_context.model_dump(mode="json") if envelope.narrative_context else None,envelope.lore_memory.model_dump(mode="json") if self.enable_lore_context else None,cloud);return envelope

    def context_from_envelope(self, envelope: ContextEnvelope | None, base: dict | None = None, cloud=False, instruction=""):
        if envelope is None:
            return base or {}
        result=dict(envelope.base_context)
        if self.enable_lore_context:result["lore_memory"]=envelope.lore_memory.model_dump(mode="json")
        if envelope.narrative_context is not None:result["narrative_context"]=envelope.narrative_context.model_dump(mode="json")
        if envelope.context_policy is not None:result["context_policy"]=envelope.context_policy.model_dump(mode="json")
        return self._attach_context_pack_v2(result,cloud,instruction)

    def build(self, novel_id, chapter_number, instruction="", cloud=False, operation=""):
        envelope = self.build_envelope(novel_id, chapter_number, instruction, cloud, operation)
        if envelope is not None:
            return self.context_from_envelope(envelope,cloud=cloud,instruction=instruction)
        base=build_context_from_sources(
            self.novels.get_context_sources(novel_id), novel_id, chapter_number, instruction, cloud
        )
        narrative=self._narrative_context(base,novel_id,chapter_number)
        narrative_data=narrative.model_dump(mode="json") if narrative is not None else None;policy=self._context_policy(base,narrative_data,None,cloud);result=dict(base)
        if narrative_data is not None:result["narrative_context"]=narrative_data
        if policy is not None:result["context_policy"]=policy.model_dump(mode="json")
        return self._attach_context_pack_v2(result,cloud,instruction)

    def for_chapter(self, chapter_id, instruction="", cloud=False, operation=""):
        chapter = self.chapters.get(chapter_id)
        return self.build(chapter["novel_id"], chapter["number"], instruction, cloud, operation)

    def save_snapshot(self, chapter_id, chapter_version, context, prompt_version, model, **metadata):
        if not self.lore:
            return None
        return ContextSnapshotService(self.lore.repository).create(
            chapter_id, chapter_version, context, prompt_version, model, **metadata
        )
