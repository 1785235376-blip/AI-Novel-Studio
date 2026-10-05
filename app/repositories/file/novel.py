from __future__ import annotations
import json
from ...repository import FileRepository,read_json,slug
from ...storage import atomic_write
from ...file_project_lifecycle import guard_project
from ...privacy import privacy_for_update, privacy_record
from .mutation_coordinator import workspace_mutation
from ..screenplay_versions import versioned_screenplay
from ..structured_cas import UNGUARDED, assert_record_cas

class FileNovelRepository:
    def __init__(self,backend:FileRepository):self.backend=backend
    def compare_and_swap_record(self,novel_id,kind,record_id,payload,expected_digest):
        methods={"characters":self.upsert_character,"locations":self.upsert_location,"relationships":self.upsert_relationship}
        if kind not in methods: raise ValueError("unsupported structured record kind")
        return methods[kind](novel_id,record_id,payload,expected_digest=expected_digest)
    def list(self):return self.backend.list_novels()
    def create(self,payload):return self.backend.create_novel(payload)
    def get(self,novel_id):return self.backend.get_novel(novel_id)
    def update(self,novel_id,payload):return self.backend.update_novel(novel_id,payload)
    def delete(self,novel_id):return self.backend.delete_novel(novel_id)
    @guard_project("novel_id")
    def get_data_set(self,novel_id,name):
        rows=self.backend.data_set(novel_id,name)
        return [privacy_record(row) for row in rows] if name in {"characters","locations","canon","foreshadowing","timeline","relationships"} else rows
    @guard_project("novel_id")
    def upsert_character(self,novel_id,character_id,payload,*,expected_digest=UNGUARDED):
        root=self.backend.novels/novel_id
        if not root.exists():raise FileNotFoundError(novel_id)
        path=root/'characters/characters.json';rows=read_json(path,[]);cid=slug(character_id or payload['name'])
        item={"id":cid,"name":payload["name"],"age":payload.get("age"),"role":payload.get("role",""),"personality":payload.get("personality",""),"goal":payload.get("goal",""),"current_location":payload.get("current_location",""),"status":payload.get("status","ALIVE"),"privacy_level":payload.get("privacy_level","CLOUD_ALLOWED")}
        index=next((i for i,row in enumerate(rows) if str(row.get('id'))==cid),None)
        assert_record_cas("characters", cid, privacy_record(rows[index]) if index is not None else None, payload, expected_digest)
        item["privacy_level"]=privacy_for_update(payload, rows[index] if index is not None else None)
        if "privacy_level" not in payload and (index is None or "privacy_level" not in rows[index] or rows[index].get("privacy_status") == "UNKNOWN"):item["privacy_status"]="UNKNOWN"
        if index is None:rows.append(item)
        else:rows[index]=item
        atomic_write(path,__import__('json').dumps(rows,ensure_ascii=False,indent=2));return item
    @guard_project("novel_id")
    def upsert_location(self,novel_id,location_id,payload,*,expected_digest=UNGUARDED):
        root=self.backend.novels/novel_id
        if not root.exists():raise FileNotFoundError(novel_id)
        path=root/'locations/locations.json';rows=read_json(path,[]);lid=slug(location_id or payload['name'])
        item={"id":lid,"name":payload["name"],"location_type":payload.get("location_type",""),"description":payload.get("description",""),"rules":payload.get("rules",""),"atmosphere":payload.get("atmosphere",""),"status":payload.get("status","ACTIVE"),"privacy_level":payload.get("privacy_level","CLOUD_ALLOWED")}
        index=next((i for i,row in enumerate(rows) if str(row.get('id'))==lid),None)
        assert_record_cas("locations", lid, privacy_record(rows[index]) if index is not None else None, payload, expected_digest)
        item["privacy_level"]=privacy_for_update(payload, rows[index] if index is not None else None)
        if "privacy_level" not in payload and (index is None or "privacy_level" not in rows[index] or rows[index].get("privacy_status") == "UNKNOWN"):item["privacy_status"]="UNKNOWN"
        if index is None:rows.append(item)
        else:rows[index]=item
        atomic_write(path,__import__('json').dumps(rows,ensure_ascii=False,indent=2));return item
    @guard_project("novel_id")
    def upsert_timeline_event(self,novel_id,event_id,payload):
        root=self.backend.novels/novel_id
        if not root.exists():raise FileNotFoundError(novel_id)
        path=root/'timeline/events.json';rows=read_json(path,[]);eid=slug(event_id or payload['title'])
        item={"id":eid,"sequence":payload.get("sequence",len(rows)+1),"time":payload.get("time",""),"title":payload["title"],"description":payload.get("description",""),"location":payload.get("location",""),"characters":payload.get("characters",[]),"chapter_id":payload.get("chapter_id",""),"status":payload.get("status","CONFIRMED"),"privacy_level":payload.get("privacy_level","CLOUD_ALLOWED")}
        index=next((i for i,row in enumerate(rows) if str(row.get('id'))==eid),None)
        item["privacy_level"]=privacy_for_update(payload, rows[index] if index is not None else None)
        if "privacy_level" not in payload and (index is None or "privacy_level" not in rows[index] or rows[index].get("privacy_status") == "UNKNOWN"):item["privacy_status"]="UNKNOWN"
        if index is None:rows.append(item)
        else:rows[index]=item
        rows.sort(key=lambda row:int(row.get('sequence',0)));atomic_write(path,__import__('json').dumps(rows,ensure_ascii=False,indent=2));return item
    @guard_project("novel_id")
    def upsert_foreshadowing(self,novel_id,foreshadowing_id,payload):
        root=self.backend.novels/novel_id
        if not root.exists():raise FileNotFoundError(novel_id)
        path=root/'foreshadowing.json';rows=read_json(path,[]);fid=slug(foreshadowing_id or payload['title'])
        item={"id":fid,"title":payload["title"],"description":payload.get("description",""),"planted_chapter":payload.get("planted_chapter"),"target_chapter":payload.get("target_chapter"),"status":payload.get("status","OPEN"),"characters":payload.get("characters",[]),"events":payload.get("events",[]),"privacy_level":payload.get("privacy_level","CLOUD_ALLOWED")}
        index=next((i for i,row in enumerate(rows) if str(row.get('id'))==fid),None)
        item["privacy_level"]=privacy_for_update(payload, rows[index] if index is not None else None)
        if "privacy_level" not in payload and (index is None or "privacy_level" not in rows[index] or rows[index].get("privacy_status") == "UNKNOWN"):item["privacy_status"]="UNKNOWN"
        if index is None:rows.append(item)
        else:rows[index]=item
        rows.sort(key=lambda row:(row.get('planted_chapter') is None,row.get('planted_chapter') or 0));atomic_write(path,__import__('json').dumps(rows,ensure_ascii=False,indent=2));return item
    @guard_project("novel_id")
    def upsert_relationship(self,novel_id,relationship_id,payload,*,expected_digest=UNGUARDED):
        root=self.backend.novels/novel_id
        if not root.exists():raise FileNotFoundError(novel_id)
        path=root/'relationships.json';rows=read_json(path,[]);rid=slug(relationship_id or f"{payload['source_character_id']}-{payload['target_character_id']}")
        item={"id":rid,**payload}
        index=next((i for i,row in enumerate(rows) if str(row.get('id'))==rid),None)
        assert_record_cas("relationships", rid, privacy_record(rows[index]) if index is not None else None, payload, expected_digest)
        item["privacy_level"]=privacy_for_update(payload, rows[index] if index is not None else None)
        if "privacy_level" not in payload and (index is None or "privacy_level" not in rows[index] or rows[index].get("privacy_status") == "UNKNOWN"):item["privacy_status"]="UNKNOWN"
        if index is None:rows.append(item)
        else:rows[index]=item
        atomic_write(path,__import__('json').dumps(rows,ensure_ascii=False,indent=2));return item
    @guard_project("novel_id")
    def get_outline(self,novel_id):
        root=self.backend.novels/novel_id
        if not root.exists():raise FileNotFoundError(novel_id)
        return read_json(root/'outline.json',{})
    @guard_project("novel_id")
    def update_outline(self,novel_id,payload):
        root=self.backend.novels/novel_id
        if not root.exists():raise FileNotFoundError(novel_id)
        item={**payload};atomic_write(root/'outline.json',__import__('json').dumps(item,ensure_ascii=False,indent=2));return item
    @guard_project("novel_id")
    def upsert_volume(self,novel_id,volume_id,payload):
        root=self.backend.novels/novel_id
        if not root.exists():raise FileNotFoundError(novel_id)
        path=root/'volumes.json';rows=read_json(path,[]);vid=slug(volume_id or payload['title']);item={"id":vid,**payload}
        index=next((i for i,row in enumerate(rows) if str(row.get('id'))==vid),None)
        if index is None:rows.append(item)
        else:rows[index]=item
        rows.sort(key=lambda row:int(row.get('sequence',0)));atomic_write(path,__import__('json').dumps(rows,ensure_ascii=False,indent=2));return item
    @guard_project("novel_id")
    def upsert_scene(self,novel_id,scene_id,payload):
        root=self.backend.novels/novel_id
        if not root.exists():raise FileNotFoundError(novel_id)
        path=root/'scenes.json';rows=read_json(path,[]);sid=slug(scene_id or payload['title']);item={"id":sid,**payload}
        index=next((i for i,row in enumerate(rows) if str(row.get('id'))==sid),None)
        if index is None:rows.append(item)
        else:rows[index]=item
        rows.sort(key=lambda row:(str(row.get('chapter_id','')),int(row.get('sequence',0))));atomic_write(path,__import__('json').dumps(rows,ensure_ascii=False,indent=2));return item
    @guard_project("novel_id")
    def upsert_story_route(self,novel_id,route_id,payload):
        root=self.backend.novels/novel_id
        if not root.exists():raise FileNotFoundError(novel_id)
        path=root/'story_routes.json';rows=read_json(path,[]);rid=slug(route_id or payload['title']);item={"id":rid,**payload};parent=item.get('parent_route_id')
        if parent and not any(str(row.get('id'))==parent for row in rows):raise KeyError(parent)
        index=next((i for i,row in enumerate(rows) if str(row.get('id'))==rid),None)
        if index is None:rows.append(item)
        else:rows[index]=item
        atomic_write(path,__import__('json').dumps(rows,ensure_ascii=False,indent=2));return item
    @guard_project("novel_id")
    def get_public_secrets(self,novel_id):return self.backend.secrets_public(novel_id)
    @guard_project("novel_id")
    def list_adaptation_proposals(self,novel_id):
        root=self.backend.novels/novel_id
        if not root.exists():raise FileNotFoundError(novel_id)
        return read_json(root/'adaptations.json',[])
    @guard_project("novel_id")
    def save_adaptation_proposal(self,novel_id,proposal):
        root=self.backend.novels/novel_id
        if not root.exists():raise FileNotFoundError(novel_id)
        path=root/'adaptations.json';rows=read_json(path,[]);index=next((i for i,row in enumerate(rows) if row.get('id')==proposal['id']),None)
        if index is None:rows.append(proposal)
        else:rows[index]=proposal
        atomic_write(path,__import__('json').dumps(rows,ensure_ascii=False,indent=2));return proposal
    @guard_project("novel_id")
    def list_screenplays(self,novel_id):
        root=self.backend.novels/novel_id
        if not root.exists():raise FileNotFoundError(novel_id)
        return read_json(root/'screenplays.json',[])
    @guard_project("novel_id")
    def save_screenplay(self,novel_id,screenplay,*,expected_version=None):
        root=self.backend.novels/novel_id
        if not root.exists():raise FileNotFoundError(novel_id)
        with workspace_mutation(root,"screenplay-records"):
            path=root/'screenplays.json';rows=read_json(path,[]);index=next((i for i,row in enumerate(rows) if row.get('id')==screenplay['id']),None)
            saved=versioned_screenplay(rows[index] if index is not None else None,screenplay,expected_version)
            if index is None:rows.append(saved)
            else:rows[index]=saved
            atomic_write(path,__import__('json').dumps(rows,ensure_ascii=False,indent=2));return saved
    @guard_project("novel_id")
    def get_context_sources(self,novel_id):
        root=self.backend.novels/novel_id
        if not root.exists():raise FileNotFoundError(novel_id)
        return {"novel":read_json(root/"novel.json",{}),"characters":[privacy_record(row) for row in read_json(root/"characters/characters.json",[])],"locations":[privacy_record(row) for row in read_json(root/"locations/locations.json",[])],"story_state":read_json(root/"story_state.json",{}),"secrets":[privacy_record(row) for row in read_json(root/"secrets.json",[])],"foreshadowing":[privacy_record(row) for row in read_json(root/"foreshadowing.json",[])],"summaries":read_json(root/"summaries/index.json",[]),"style_profile":read_json(root/"style/profile.json",{})}
