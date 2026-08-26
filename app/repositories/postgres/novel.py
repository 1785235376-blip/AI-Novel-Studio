from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select

from ...repository import slug
from .common import iso, novel_or_raise
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

    def update(self, novel_id, payload):
        with self.database.session() as session:
            model = novel_or_raise(session, novel_id)
            if payload.get("title") is not None:
                model.title = payload["title"]
            metadata = dict(model.metadata_json or {})
            for key in ("genre", "status", "long_term_summary"):
                if payload.get(key) is not None:
                    metadata[key] = payload[key]
            model.metadata_json = metadata
            model.updated_at = datetime.now(timezone.utc)
            session.flush()
            return self._meta(model)

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
                return [serialize_timeline(x) for x in sorted(rows, key=timeline_order)]
            if name == "relationships":
                rows=session.scalars(select(RelationshipStateModel).where(RelationshipStateModel.project_id==novel.slug).order_by(RelationshipStateModel.created_at)).all()
                return [{"id":dict(row.payload or {}).get("_source_id",row.id),"source_character_id":row.source_character_id,"target_character_id":row.target_character_id,**{key:value for key,value in dict(row.payload or {}).items() if not key.startswith("_")}} for row in rows]
            if name == "volumes":
                return sorted(list((novel.metadata_json or {}).get("volumes",[])),key=lambda row:int(row.get("sequence",0)))
            if name == "scenes":
                return sorted(list((novel.metadata_json or {}).get("scenes",[])),key=lambda row:(str(row.get("chapter_id","")),int(row.get("sequence",0))))
            if name == "story_routes":
                return list((novel.metadata_json or {}).get("story_routes",[]))
            raise KeyError(name)

    def upsert_character(self,novel_id,character_id,payload):
        with self.database.session() as session:
            novel=novel_or_raise(session,novel_id);character_slug=slug(character_id or payload["name"])
            model=session.scalar(select(CharacterModel).where(CharacterModel.novel_id==novel.id,CharacterModel.slug==character_slug))
            facts={key:payload.get(key,"") for key in ("role","personality","goal","current_location")}
            if model is None:
                model=CharacterModel(novel_id=novel.id,slug=character_slug,name=payload["name"],age=payload.get("age"),life_status=payload.get("status","ALIVE"),facts=facts,privacy=payload.get("privacy_level","CLOUD_ALLOWED"));session.add(model)
            else:
                model.name=payload["name"];model.age=payload.get("age");model.life_status=payload.get("status","ALIVE");model.facts=facts;model.privacy=payload.get("privacy_level","CLOUD_ALLOWED")
            session.flush();return serialize_character(model)

    def upsert_location(self,novel_id,location_id,payload):
        with self.database.session() as session:
            novel=novel_or_raise(session,novel_id);location_slug=slug(location_id or payload["name"])
            model=session.scalar(select(LocationModel).where(LocationModel.novel_id==novel.id,LocationModel.slug==location_slug))
            facts={key:payload.get(key,"") for key in ("location_type","description","rules","atmosphere","status")}
            if model is None:
                model=LocationModel(novel_id=novel.id,slug=location_slug,name=payload["name"],facts=facts,privacy=payload.get("privacy_level","CLOUD_ALLOWED"));session.add(model)
            else:model.name=payload["name"];model.facts=facts;model.privacy=payload.get("privacy_level","CLOUD_ALLOWED")
            session.flush();return serialize_location(model)

    def upsert_timeline_event(self,novel_id,event_id,payload):
        with self.database.session() as session:
            novel=novel_or_raise(session,novel_id);source_id=slug(event_id or payload["title"]);target_id=uuid.uuid5(uuid.NAMESPACE_URL,f"ai-novel-studio:{novel.slug}:timeline:{source_id}")
            model=session.get(TimelineModel,target_id);location_slug=payload.get("location");location=None
            if location_slug:location=session.scalar(select(LocationModel).where(LocationModel.novel_id==novel.id,LocationModel.slug==location_slug))
            details={key:payload.get(key,[] if key=="characters" else "") for key in ("description","characters","chapter_id","status")};details["_source_id"]=source_id
            values={"novel_id":novel.id,"event_time":payload.get("time",""),"sequence":payload.get("sequence",1),"location_id":location.id if location else None,"title":payload["title"],"details":details,"privacy":payload.get("privacy_level","CLOUD_ALLOWED")}
            if model is None:model=TimelineModel(id=target_id,**values);session.add(model)
            else:
                for key,value in values.items():setattr(model,key,value)
            session.flush();result=serialize_timeline(model);result["location"]=location_slug or "";return result

    def upsert_foreshadowing(self,novel_id,foreshadowing_id,payload):
        with self.database.session() as session:
            novel=novel_or_raise(session,novel_id);source_id=slug(foreshadowing_id or payload["title"]);target_id=uuid.uuid5(uuid.NAMESPACE_URL,f"ai-novel-studio:{novel.slug}:foreshadowing:{source_id}")
            model=session.get(ForeshadowingModel,target_id);details={key:payload.get(key,[] if key in ("characters","events") else "") for key in ("description","characters","events")};details["_source_id"]=source_id
            values={"novel_id":novel.id,"title":payload["title"],"planted_chapter":payload.get("planted_chapter"),"target_chapter":payload.get("target_chapter"),"status":payload.get("status","OPEN"),"details":details}
            if model is None:model=ForeshadowingModel(id=target_id,**values);session.add(model)
            else:
                for key,value in values.items():setattr(model,key,value)
            session.flush();result=serialize_foreshadowing(model);result["privacy_level"]=payload.get("privacy_level","CLOUD_ALLOWED");return result

    def upsert_relationship(self,novel_id,relationship_id,payload):
        with self.database.session() as session:
            novel=novel_or_raise(session,novel_id);source_id=slug(relationship_id or f"{payload['source_character_id']}-{payload['target_character_id']}");rid=f"{novel.slug}:{source_id}";model=session.get(RelationshipStateModel,rid)
            details={key:payload.get(key,"") for key in ("relationship_type","description","status","valid_from_event_id","valid_to_event_id","certainty","privacy_level")}
            details["_source_id"]=source_id
            values={"project_id":novel.slug,"source_character_id":payload["source_character_id"],"target_character_id":payload["target_character_id"],"payload":details}
            if model is None:model=RelationshipStateModel(id=rid,**values);session.add(model)
            else:
                if model.project_id!=novel.slug:raise KeyError(rid)
                for key,value in values.items():setattr(model,key,value)
            session.flush();return {"id":source_id,"source_character_id":model.source_character_id,"target_character_id":model.target_character_id,**{key:value for key,value in details.items() if not key.startswith("_")}}

    def get_outline(self,novel_id):
        with self.database.session() as session:
            model=novel_or_raise(session,novel_id);return dict((model.metadata_json or {}).get("outline",{}))

    def update_outline(self,novel_id,payload):
        with self.database.session() as session:
            model=novel_or_raise(session,novel_id);metadata=dict(model.metadata_json or {});metadata["outline"]={**payload};model.metadata_json=metadata;model.updated_at=datetime.now(timezone.utc);session.flush();return dict(metadata["outline"])

    def upsert_volume(self,novel_id,volume_id,payload):
        with self.database.session() as session:
            model=novel_or_raise(session,novel_id);metadata=dict(model.metadata_json or {});rows=list(metadata.get("volumes",[]));vid=slug(volume_id or payload["title"]);item={"id":vid,**payload};index=next((i for i,row in enumerate(rows) if str(row.get("id"))==vid),None)
            if index is None:rows.append(item)
            else:rows[index]=item
            metadata["volumes"]=sorted(rows,key=lambda row:int(row.get("sequence",0)));model.metadata_json=metadata;model.updated_at=datetime.now(timezone.utc);session.flush();return item

    def upsert_scene(self,novel_id,scene_id,payload):
        with self.database.session() as session:
            model=novel_or_raise(session,novel_id);metadata=dict(model.metadata_json or {});rows=list(metadata.get("scenes",[]));sid=slug(scene_id or payload["title"]);item={"id":sid,**payload};index=next((i for i,row in enumerate(rows) if str(row.get("id"))==sid),None)
            if index is None:rows.append(item)
            else:rows[index]=item
            metadata["scenes"]=sorted(rows,key=lambda row:(str(row.get("chapter_id","")),int(row.get("sequence",0))));model.metadata_json=metadata;model.updated_at=datetime.now(timezone.utc);session.flush();return item

    def upsert_story_route(self,novel_id,route_id,payload):
        with self.database.session() as session:
            model=novel_or_raise(session,novel_id);metadata=dict(model.metadata_json or {});rows=list(metadata.get("story_routes",[]));rid=slug(route_id or payload["title"]);item={"id":rid,**payload};parent=item.get("parent_route_id")
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

    def save_adaptation_proposal(self,novel_id,proposal):
        with self.database.session() as session:
            model=novel_or_raise(session,novel_id);metadata=dict(model.metadata_json or {});rows=list(metadata.get("adaptation_proposals",[]));index=next((i for i,row in enumerate(rows) if row.get("id")==proposal["id"]),None)
            if index is None:rows.append(proposal)
            else:rows[index]=proposal
            metadata["adaptation_proposals"]=rows;model.metadata_json=metadata;model.updated_at=datetime.now(timezone.utc);session.flush();return proposal

    def list_screenplays(self,novel_id):
        with self.database.session() as session:
            model=novel_or_raise(session,novel_id);return list((model.metadata_json or {}).get("screenplays",[]))

    def save_screenplay(self,novel_id,screenplay):
        with self.database.session() as session:
            model=novel_or_raise(session,novel_id);metadata=dict(model.metadata_json or {});rows=list(metadata.get("screenplays",[]));index=next((i for i,row in enumerate(rows) if row.get("id")==screenplay["id"]),None)
            if index is None:rows.append(screenplay)
            else:rows[index]=screenplay
            metadata["screenplays"]=rows;model.metadata_json=metadata;model.updated_at=datetime.now(timezone.utc);session.flush();return screenplay

    def get_context_sources(self, novel_id):
        with self.database.session() as session:
            novel = novel_or_raise(session, novel_id)
            characters = session.scalars(select(CharacterModel).where(CharacterModel.novel_id == novel.id)).all()
            locations = session.scalars(select(LocationModel).where(LocationModel.novel_id == novel.id)).all()
            state = session.scalar(select(StoryStateModel).where(StoryStateModel.novel_id == novel.id).order_by(StoryStateModel.chapter_number.desc()))
            secrets = session.scalars(select(SecretModel).where(SecretModel.novel_id == novel.id)).all()
            foreshadowing = session.scalars(select(ForeshadowingModel).where(ForeshadowingModel.novel_id == novel.id)).all()
            summaries = session.execute(select(ChapterSummaryModel, ChapterModel).join(ChapterModel).where(ChapterModel.novel_id == novel.id).order_by(ChapterModel.chapter_number, ChapterSummaryModel.created_at)).all()
            secret_mapping = dict((novel.metadata_json or {}).get("context_source_ids", {}).get("secrets", {}))
            return {
                "novel": self._meta(novel),
                "characters": [serialize_character(x) for x in sorted(characters, key=character_order)],
                "locations": [serialize_location(x) for x in sorted(locations, key=location_order)],
                "story_state": dict(state.state) if state else {"volume": 1, "chapter": 0, "active_characters": []},
                "secrets": [serialize_secret(x, secret_mapping) for x in sorted(secrets, key=lambda item: secret_order(item, secret_mapping))],
                "foreshadowing": [serialize_foreshadowing(x) for x in sorted(foreshadowing, key=foreshadowing_order)],
                "summaries": [{"chapter": chapter.chapter_number, "summary": summary.summary} for summary, chapter in summaries],
                "style_profile": dict((novel.metadata_json or {}).get("style_profile", {})),
            }
