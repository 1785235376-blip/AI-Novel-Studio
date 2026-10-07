from __future__ import annotations
from ...runtime_events import committed_change

import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select

from ...repository import slug
from ...privacy import privacy_for_update
from ..screenplay_versions import versioned_screenplay
from ..adaptation_versions import versioned_adaptation, MAX_PROPOSALS
from ..structured_cas import UNGUARDED, assert_record_cas
from ..story_record_versions import META, KINDS, envelope, prepare, finish, core_record
from .common import chapter_external_id, iso, novel_or_raise
from .models import (CanonModel, ChapterModel, ChapterSummaryModel, CharacterModel,
                     ForeshadowingModel, LocationModel, NovelModel, SecretModel,
                     RelationshipStateModel, StoryStateModel, TimelineModel)
from .serialization import (character_order, foreshadowing_order, location_order,
                            secret_order, serialize_canon, serialize_character,
                            serialize_foreshadowing, serialize_location,
                            serialize_secret, serialize_timeline, timeline_order)


class PostgresNovelRepository:
    def __init__(self, database):
        self.database = database

    def compare_and_swap_record(self,novel_id,kind,record_id,payload,expected_digest,*,mutation=None,check=None):
        methods={"characters":self.upsert_character,"locations":self.upsert_location,"relationships":self.upsert_relationship,"timeline":self.upsert_timeline_event,"foreshadowing":self.upsert_foreshadowing}
        if kind not in methods: raise ValueError("unsupported structured record kind")
        return methods[kind](novel_id,record_id,payload,expected_digest=expected_digest,**({"mutation":mutation,"check":check} if kind in KINDS else {}))

    @staticmethod
    def _locked_metadata_model(session, novel_id):
        model=session.scalar(select(NovelModel).where(NovelModel.slug==novel_id).with_for_update())
        if model is None: raise FileNotFoundError(novel_id)
        return model

    @staticmethod
    def _meta(model: NovelModel) -> dict:
        extra = dict(model.metadata_json or {})
        return {
            "id": model.slug,
            "title": model.title,
            "genre": extra.get("genre", ""),
            "status": extra.get("status", "Writing"),
            "created_at": iso(model.created_at),
            "updated_at": iso(model.updated_at),
            **({"long_term_summary": extra["long_term_summary"]} if "long_term_summary" in extra else {}),
            **({"writing_goal": extra["writing_goal"]} if "writing_goal" in extra else {}),
        }

    def list(self):
        with self.database.session() as session:
            novels = session.scalars(select(NovelModel).order_by(NovelModel.created_at)).all()
            output = []
            for novel in novels:
                chapters = session.scalars(select(ChapterModel).where(ChapterModel.novel_id == novel.id)).all()
                word_count = sum(len(re.sub(r"\s+", "", self._markdown(chapter.document))) for chapter in chapters)
                output.append({**self._meta(novel), "chapter_count": len(chapters), "word_count": word_count})
            return output

    @staticmethod
    def _markdown(document: dict | None) -> str:
        from ...document import document_to_markdown
        return document_to_markdown(document or {"type": "doc", "content": []})

    @committed_change("PROJECT")
    def create(self, payload):
        novel_slug = slug(payload.get("id") or payload["title"])
        with self.database.session() as session:
            if session.scalar(select(NovelModel.id).where(NovelModel.slug == novel_slug)):
                raise FileExistsError(novel_slug)
            now = datetime.now(timezone.utc)
            model = NovelModel(slug=novel_slug, title=payload["title"], metadata_json={
                "genre": payload.get("genre", ""), "status": "Writing", "style_profile": {}
            }, created_at=now, updated_at=now)
            session.add(model); session.flush()
            session.add(StoryStateModel(novel_id=model.id, chapter_number=0, state={"volume": 1, "chapter": 0, "active_characters": []}))
            return self._meta(model)

    def get(self, novel_id):
        with self.database.session() as session:
            return self._meta(novel_or_raise(session, novel_id))

    @committed_change("PROJECT")
    def update(self, novel_id, payload):
        with self.database.session() as session:
            model = self._locked_metadata_model(session, novel_id)
            if payload.get("title") is not None:
                model.title = payload["title"]
            metadata = dict(model.metadata_json or {})
            for key in ("genre", "status", "long_term_summary", "writing_goal"):
                if payload.get(key) is not None:
                    metadata[key] = payload[key]
            model.metadata_json = metadata
            model.updated_at = datetime.now(timezone.utc)
            session.flush()
            return self._meta(model)

    @committed_change("PROJECT")
    def delete(self, novel_id):
        with self.database.session() as session:
            model = novel_or_raise(session, novel_id)
            session.delete(model)

    def get_data_set(self, novel_id, name):
        with self.database.session() as session:
            novel = novel_or_raise(session, novel_id)
            if name == "characters":
                rows = session.scalars(select(CharacterModel).where(CharacterModel.novel_id == novel.id)).all()
                return [serialize_character(x) for x in sorted(rows, key=character_order)]
            if name == "locations":
                rows = session.scalars(select(LocationModel).where(LocationModel.novel_id == novel.id)).all()
                return [serialize_location(x) for x in sorted(rows, key=location_order)]
            if name == "canon":
                return self._canon(session, novel.id)
            if name == "foreshadowing":
                rows = session.scalars(select(ForeshadowingModel).where(ForeshadowingModel.novel_id == novel.id)).all()
                return [serialize_foreshadowing(x) for x in sorted(rows, key=foreshadowing_order)]
            if name == "timeline":
                rows = session.scalars(select(TimelineModel).where(TimelineModel.novel_id == novel.id)).all()
                return [self._serialize_story(session,"timeline",x) for x in sorted(rows, key=timeline_order)]
            if name == "relationships":
                rows=session.scalars(select(RelationshipStateModel).where(RelationshipStateModel.project_id==novel.slug).order_by(RelationshipStateModel.created_at)).all()
                return [self._serialize_story(session,"relationships",row) for row in rows]
            if name == "volumes":
                return sorted(list((novel.metadata_json or {}).get("volumes",[])),key=lambda row:int(row.get("sequence",0)))
            if name == "scenes":
                return sorted(list((novel.metadata_json or {}).get("scenes",[])),key=lambda row:(str(row.get("chapter_id","")),int(row.get("sequence",0))))
            if name == "story_routes":
                return list((novel.metadata_json or {}).get("story_routes",[]))
            raise KeyError(name)

    def upsert_character(self,novel_id,character_id,payload,*,expected_digest=UNGUARDED,mutation=None,check=None):
        return self._upsert_story_record(novel_id,'characters',character_id,payload,expected_digest,mutation,check)

    def upsert_location(self,novel_id,location_id,payload,*,expected_digest=UNGUARDED,mutation=None,check=None):
        return self._upsert_story_record(novel_id,'locations',location_id,payload,expected_digest,mutation,check)

    @staticmethod
    def _serialize_story(session,kind,model):
        if kind=='characters':return serialize_character(model)
        if kind=='locations':return serialize_location(model)
        if kind=='relationships':
            from ...privacy import privacy_record
            return privacy_record({'id':dict(model.payload or {}).get('_source_id',model.id),
                                   'source_character_id':model.source_character_id,
                                   'target_character_id':model.target_character_id,
                                   **{key:value for key,value in dict(model.payload or {}).items() if not key.startswith('_')}})
        if kind=='foreshadowing': return serialize_foreshadowing(model)
        result=serialize_timeline(model)
        # Historical imports stored only a location FK. New rows retain the
        # original slug in JSONB too, so every write receipt equals public GET.
        if 'location' not in result:
            location=session.get(LocationModel,model.location_id) if model.location_id else None
            result['location']=location.slug if location is not None else ''
        return result

    @staticmethod
    def _story_model(session,novel,kind,rid):
        if kind in {'characters','locations'}:
            cls=CharacterModel if kind=='characters' else LocationModel
            return session.scalar(select(cls).where(cls.novel_id==novel.id,cls.slug==rid)),uuid.uuid5(uuid.NAMESPACE_URL,f'ai-novel-studio:{novel.slug}:{kind}:{rid}')
        if kind=='relationships':
            target=f'{novel.slug}:{rid}'
            model=session.scalar(select(RelationshipStateModel).where(RelationshipStateModel.project_id==novel.slug,
                                  RelationshipStateModel.payload['_source_id'].astext==rid))
            if model is None:
                model=session.get(RelationshipStateModel,target)
                if model is not None and model.project_id!=novel.slug:raise FileNotFoundError(rid)
            if model is None:
                candidate=session.get(RelationshipStateModel,rid)
                if candidate is not None and candidate.project_id==novel.slug:model=candidate
            return model,target
        cls=TimelineModel if kind=='timeline' else ForeshadowingModel
        target=uuid.uuid5(uuid.NAMESPACE_URL,f"ai-novel-studio:{novel.slug}:{kind}:{rid}")
        model=session.get(cls,target)
        if model is None:model=session.scalar(select(cls).where(cls.novel_id==novel.id,cls.details['_source_id'].astext==rid))
        if model is None:
            # Existing pre-migration UUID records remain addressable by GET id.
            try: candidate=session.get(cls,uuid.UUID(rid))
            except ValueError: candidate=None
            if candidate is not None and candidate.novel_id==novel.id:model=candidate
        return model,target

    def story_record(self,novel_id,kind,record_id):
        if kind not in KINDS: raise ValueError("unsupported story record kind")
        with self.database.session() as session:
            novel=novel_or_raise(session,novel_id);model,_=self._story_model(session,novel,kind,record_id)
            if model is None:raise FileNotFoundError(record_id)
            column='facts' if kind in {'characters','locations'} else 'payload' if kind=='relationships' else 'details'
            return envelope(self._serialize_story(session,kind,model),(getattr(model,column) or {}).get(META))

    def _upsert_story_record(self,novel_id,kind,record_id,payload,expected_digest,mutation,check):
        with self.database.session() as session:
            novel=novel_or_raise(session,novel_id,True)
            exact=self._story_model(session,novel,kind,record_id)[0] if expected_digest is UNGUARDED and record_id else None
            creation_id=payload.get('name') or payload.get('title') or f"{payload.get('source_character_id','')}-{payload.get('target_character_id','')}"
            rid=record_id if expected_digest is not UNGUARDED or exact is not None else slug(record_id or creation_id)
            if kind in {'characters','locations','relationships'}:
                return self._write_core_story(session,novel,kind,rid,payload,expected_digest,mutation,check)
            if mutation and mutation['action']!='RESTORE':
                # Keep captured chapter evidence stable through the same commit.
                # Timeline sources share the novel lock already held here.
                from .common import chapter_or_raise, require_chapter_identity
                from .chapter import PostgresChapterRepository
                from ..structured_cas import record_digest
                from ..chapter_repository import VersionConflict
                for source in sorted(mutation.get('source_versions',[]),key=lambda row:(row['kind'],row['id'])):
                    if source['kind']!='chapter':continue
                    try:
                        source_novel,chapter=chapter_or_raise(session,source['id'])
                        chapter=session.scalar(select(ChapterModel).where(ChapterModel.id==chapter.id).with_for_update().execution_options(populate_existing=True))
                        require_chapter_identity(chapter)
                        row=PostgresChapterRepository._external(source_novel,chapter)
                        fingerprint=record_digest({'id':row['id'],'version':row['version'],'document':row.get('document'),'content':row.get('content')})
                        if source_novel.id!=novel.id or row['is_archived'] or fingerprint!=source['digest']:raise FileNotFoundError(source['id'])
                    except FileNotFoundError:
                        raise VersionConflict({'id':rid,'version':mutation['expected_version']},resource_id=rid,expected_version=mutation['expected_version']) from None
            model,target=self._story_model(session,novel,kind,rid)
            current=self._serialize_story(session,kind,model) if model is not None else None
            details=dict(model.details or {}) if model is not None else {}
            metadata=details.get(META)
            payload=prepare(kind,rid,current,metadata,payload,expected_digest,mutation)
            snapshot=bool(mutation and mutation['action'] in {'RESTORE','FEEDBACK'})
            if snapshot:
                details={**{key:value for key,value in details.items() if key.startswith('_')},
                         **{key:value for key,value in payload.items() if key not in {'id','title','time','sequence','planted_chapter','target_chapter'}}}
            if not snapshot:
                details.update({key:payload.get(key,[] if key=='characters' else '') for key in ('description','characters')})
            details['_source_id']=rid
            if 'privacy_level' not in payload and (current is None or current.get('privacy_status')=='UNKNOWN'):
                details['privacy_status']='UNKNOWN'
            elif 'privacy_level' in payload and 'privacy_status' not in payload:details.pop('privacy_status',None)
            from ...privacy import privacy_for_update
            policy=privacy_for_update(payload,current)
            if kind=='timeline':
                location_slug=payload.get('location','');location=None
                if location_slug:location=session.scalar(select(LocationModel).where(LocationModel.novel_id==novel.id,LocationModel.slug==location_slug))
                if not snapshot:
                    details.update(location=location_slug,chapter_id=payload.get('chapter_id',''),status=payload.get('status','CONFIRMED'))
                # Clear stale imported policy after an explicit user change.
                if 'privacy_level' in details:details['privacy_level']=policy
                values={'novel_id':novel.id,'event_time':payload.get('time',''),'sequence':payload.get('sequence',1),
                        'location_id':location.id if location else None,'title':payload['title'],'details':details,'privacy':policy}
                cls=TimelineModel
            else:
                details['privacy_level']=policy
                if not snapshot:details['events']=payload.get('events',[])
                values={'novel_id':novel.id,'title':payload['title'],'planted_chapter':payload.get('planted_chapter'),
                        'target_chapter':payload.get('target_chapter'),'status':payload.get('status','OPEN'),'details':details}
                cls=ForeshadowingModel
            if model is None:model=cls(id=target,**values);session.add(model)
            else:
                for key,value in values.items():setattr(model,key,value)
            # Serialize the actual columns, not request data, for exact CAS.
            session.flush();result=self._serialize_story(session,kind,model)
            meta=finish(current,metadata,result,mutation)
            if meta is not None:model.details={**details,META:meta}
            if check:check()
            session.flush()
            return envelope(result,meta) if mutation is not None else result

    def upsert_timeline_event(self,novel_id,event_id,payload,*,expected_digest=UNGUARDED,mutation=None,check=None):
        return self._upsert_story_record(novel_id,'timeline',event_id,payload,expected_digest,mutation,check)

    def upsert_foreshadowing(self,novel_id,foreshadowing_id,payload,*,expected_digest=UNGUARDED,mutation=None,check=None):
        return self._upsert_story_record(novel_id,'foreshadowing',foreshadowing_id,payload,expected_digest,mutation,check)

    def upsert_relationship(self,novel_id,relationship_id,payload,*,expected_digest=UNGUARDED,mutation=None,check=None):
        return self._upsert_story_record(novel_id,'relationships',relationship_id,payload,expected_digest,mutation,check)

    def _write_core_story(self,session,novel,kind,rid,payload,expected_digest,mutation,check):
        # The caller holds the same novel row lock used by every original writer.
        model,target=self._story_model(session,novel,kind,rid)
        column='payload' if kind=='relationships' else 'facts'
        stored=dict(getattr(model,column) or {}) if model is not None else {}
        current=self._serialize_story(session,kind,model) if model is not None else None
        metadata=stored.get(META)
        payload=prepare(kind,rid,current,metadata,payload,expected_digest,mutation)
        legacy_defaults={key:'' for key in ('location_type','description','rules','atmosphere','status')} if kind=='locations' else {key:'' for key in ('relationship_type','description','status','valid_from_event_id','valid_to_event_id','certainty')} if kind=='relationships' else None
        item=core_record(kind,rid,current,payload,mutation,legacy_defaults=legacy_defaults)
        internal={key:value for key,value in stored.items() if key.startswith('_') and key!=META}
        if kind in {'characters','locations'}:
            columns={'id','name','age','privacy_level','privacy_status'} | ({'status'} if kind=='characters' else set())
            facts={**internal,**{key:value for key,value in item.items() if key not in columns}}
            if item.get('privacy_status')=='UNKNOWN':facts['_source_privacy_present']=False
            else:facts.pop('_source_privacy_present',None)
            values={'novel_id':novel.id,'slug':rid,'name':item['name'],'facts':facts,'privacy':item['privacy_level']}
            if kind=='characters':values.update(age=item.get('age'),life_status=item.get('status','ALIVE'))
            cls=CharacterModel if kind=='characters' else LocationModel
        else:
            facts={**internal,**{key:value for key,value in item.items() if key not in {'id','source_character_id','target_character_id'}},'_source_id':rid}
            values={'project_id':novel.slug,'source_character_id':item['source_character_id'],
                    'target_character_id':item['target_character_id'],'payload':facts}
            cls=RelationshipStateModel
        if model is None:model=cls(id=target,**values);session.add(model)
        else:
            for key,value in values.items():setattr(model,key,value)
        session.flush()
        result=self._serialize_story(session,kind,model)
        meta=finish(current,metadata,result,mutation)
        if meta is not None:setattr(model,column,{**facts,META:meta})
        if check:check()
        session.flush()
        return envelope(result,meta) if mutation is not None else result

    def get_outline(self,novel_id):
        with self.database.session() as session:
            model=novel_or_raise(session,novel_id);return dict((model.metadata_json or {}).get("outline",{}))

    def update_outline(self,novel_id,payload):
        with self.database.session() as session:
            model=self._locked_metadata_model(session,novel_id);metadata=dict(model.metadata_json or {});metadata["outline"]={**payload};model.metadata_json=metadata;model.updated_at=datetime.now(timezone.utc);session.flush();return dict(metadata["outline"])

    def upsert_volume(self,novel_id,volume_id,payload):
        with self.database.session() as session:
            model=self._locked_metadata_model(session,novel_id);metadata=dict(model.metadata_json or {});rows=list(metadata.get("volumes",[]));vid=slug(volume_id or payload["title"]);item={"id":vid,**payload};index=next((i for i,row in enumerate(rows) if str(row.get("id"))==vid),None)
            if index is None:rows.append(item)
            else:rows[index]=item
            metadata["volumes"]=sorted(rows,key=lambda row:int(row.get("sequence",0)));model.metadata_json=metadata;model.updated_at=datetime.now(timezone.utc);session.flush();return item

    def upsert_scene(self,novel_id,scene_id,payload):
        with self.database.session() as session:
            model=self._locked_metadata_model(session,novel_id);metadata=dict(model.metadata_json or {});rows=list(metadata.get("scenes",[]));sid=slug(scene_id or payload["title"]);item={"id":sid,**payload};index=next((i for i,row in enumerate(rows) if str(row.get("id"))==sid),None)
            if index is None:rows.append(item)
            else:rows[index]=item
            metadata["scenes"]=sorted(rows,key=lambda row:(str(row.get("chapter_id","")),int(row.get("sequence",0))));model.metadata_json=metadata;model.updated_at=datetime.now(timezone.utc);session.flush();return item

    def upsert_story_route(self,novel_id,route_id,payload):
        with self.database.session() as session:
            model=self._locked_metadata_model(session,novel_id);metadata=dict(model.metadata_json or {});rows=list(metadata.get("story_routes",[]));rid=slug(route_id or payload["title"]);item={"id":rid,**payload};parent=item.get("parent_route_id")
            if parent and not any(str(row.get("id"))==parent for row in rows):raise KeyError(parent)
            index=next((i for i,row in enumerate(rows) if str(row.get("id"))==rid),None)
            if index is None:rows.append(item)
            else:rows[index]=item
            metadata["story_routes"]=rows;model.metadata_json=metadata;model.updated_at=datetime.now(timezone.utc);session.flush();return item

    @staticmethod
    def _canon(session, novel_uuid):
        rows = session.scalars(select(CanonModel).where(CanonModel.novel_id == novel_uuid).order_by(CanonModel.approved_at)).all()
        return [serialize_canon(x) for x in rows]

    def get_public_secrets(self, novel_id):
        with self.database.session() as session:
            novel = novel_or_raise(session, novel_id)
            rows = session.scalars(select(SecretModel).where(SecretModel.novel_id == novel.id)).all()
            mapping = dict((novel.metadata_json or {}).get("context_source_ids", {}).get("secrets", {}))
            return [serialize_secret(x, mapping, public=True) for x in sorted(rows, key=lambda item: secret_order(item, mapping))]

    def list_adaptation_proposals(self,novel_id):
        with self.database.session() as session:
            model=novel_or_raise(session,novel_id);return list((model.metadata_json or {}).get("adaptation_proposals",[]))

    def save_adaptation_proposal(self,novel_id,proposal,*,expected_revision=None,check=None,finalize=False):
        with self.database.session() as session:
            model=self._locked_metadata_model(session,novel_id);metadata=dict(model.metadata_json or {})
            rows=list(metadata.get("adaptation_proposals",[]));index=next((i for i,row in enumerate(rows) if row.get("id")==proposal["id"]),None)
            if index is None and len(rows)>=MAX_PROPOSALS:raise ValueError('ADAPTATION_CAPACITY_PROPOSAL_LIMIT')
            saved=versioned_adaptation(rows[index] if index is not None else None,proposal,expected_revision,finalize=finalize)
            if check:check()
            if index is None:rows.append(saved)
            else:rows[index]=saved
            metadata["adaptation_proposals"]=rows;model.metadata_json=metadata;model.updated_at=datetime.now(timezone.utc);session.flush();return saved

    def list_screenplays(self,novel_id):
        with self.database.session() as session:
            model=novel_or_raise(session,novel_id);return list((model.metadata_json or {}).get("screenplays",[]))

    def save_screenplay(self,novel_id,screenplay,*,expected_version=None):
        with self.database.session() as session:
            model=self._locked_metadata_model(session,novel_id);metadata=dict(model.metadata_json or {});rows=list(metadata.get("screenplays",[]));index=next((i for i,row in enumerate(rows) if row.get("id")==screenplay["id"]),None)
            saved=versioned_screenplay(rows[index] if index is not None else None,screenplay,expected_version)
            if index is None:rows.append(saved)
            else:rows[index]=saved
            metadata["screenplays"]=rows;model.metadata_json=metadata;model.updated_at=datetime.now(timezone.utc);session.flush();return saved

    def get_context_sources(self, novel_id):
        with self.database.session() as session:
            novel = novel_or_raise(session, novel_id)
            characters = session.scalars(select(CharacterModel).where(CharacterModel.novel_id == novel.id)).all()
            locations = session.scalars(select(LocationModel).where(LocationModel.novel_id == novel.id)).all()
            state = session.scalar(select(StoryStateModel).where(StoryStateModel.novel_id == novel.id).order_by(StoryStateModel.chapter_number.desc()))
            secrets = session.scalars(select(SecretModel).where(SecretModel.novel_id == novel.id)).all()
            foreshadowing = session.scalars(select(ForeshadowingModel).where(ForeshadowingModel.novel_id == novel.id)).all()
            summaries = session.execute(select(ChapterSummaryModel, ChapterModel).join(ChapterModel).where(ChapterModel.novel_id == novel.id, ChapterModel.identity_status == "ACTIVE").order_by(func.coalesce(ChapterModel.sort_order, ChapterModel.chapter_number), ChapterSummaryModel.created_at)).all()
            secret_mapping = dict((novel.metadata_json or {}).get("context_source_ids", {}).get("secrets", {}))
            return {
                "novel": self._meta(novel),
                "characters": [serialize_character(x) for x in sorted(characters, key=character_order)],
                "locations": [serialize_location(x) for x in sorted(locations, key=location_order)],
                "story_state": dict(state.state) if state else {"volume": 1, "chapter": 0, "active_characters": []},
                "secrets": [serialize_secret(x, secret_mapping) for x in sorted(secrets, key=lambda item: secret_order(item, secret_mapping))],
                "foreshadowing": [serialize_foreshadowing(x) for x in sorted(foreshadowing, key=foreshadowing_order)],
                "summaries": [{"chapter": chapter.chapter_number, "summary": summary.summary, **({"chapter_id": chapter_external_id(novel, chapter)} if chapter.public_token else {})} for summary, chapter in summaries],
                "style_profile": dict((novel.metadata_json or {}).get("style_profile", {})),
            }
