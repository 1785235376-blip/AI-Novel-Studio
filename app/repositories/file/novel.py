from __future__ import annotations
import json
from ...repository import FileRepository,read_json,slug
from ...storage import atomic_write
from ...chapter_identity import current_summaries
from ...file_project_lifecycle import guard_project
from ...privacy import privacy_for_update, privacy_record
from .mutation_coordinator import workspace_mutation
from ..screenplay_versions import versioned_screenplay
from ..adaptation_versions import versioned_adaptation, MAX_PROPOSALS
from ..structured_cas import UNGUARDED, assert_record_cas
from ..story_record_versions import META, KINDS, PATHS, public_record, envelope, prepare, finish, core_record

class FileNovelRepository:
    def __init__(self,backend:FileRepository):self.backend=backend
    def compare_and_swap_record(self,novel_id,kind,record_id,payload,expected_digest,*,mutation=None,check=None):
        methods={"characters":self.upsert_character,"locations":self.upsert_location,"relationships":self.upsert_relationship,"timeline":self.upsert_timeline_event,"foreshadowing":self.upsert_foreshadowing}
        if kind not in methods: raise ValueError("unsupported structured record kind")
        return methods[kind](novel_id,record_id,payload,expected_digest=expected_digest,**({"mutation":mutation,"check":check} if kind in KINDS else {}))
    def list(self):return self.backend.list_novels()
    def create(self,payload):return self.backend.create_novel(payload)
    def get(self,novel_id):return self.backend.get_novel(novel_id)
    def update(self,novel_id,payload):return self.backend.update_novel(novel_id,payload)
    def delete(self,novel_id):return self.backend.delete_novel(novel_id)
    @guard_project("novel_id")
    def get_data_set(self,novel_id,name):
        rows=self.backend.data_set(novel_id,name)
        return [privacy_record(public_record(row)) for row in rows] if name in {"characters","locations","canon","foreshadowing","timeline","relationships"} else rows
    def upsert_character(self,novel_id,character_id,payload,*,expected_digest=UNGUARDED,mutation=None,check=None):
        return self._upsert_story_record(novel_id,'characters',character_id,payload,expected_digest,mutation,check)

    def upsert_location(self,novel_id,location_id,payload,*,expected_digest=UNGUARDED,mutation=None,check=None):
        return self._upsert_story_record(novel_id,'locations',location_id,payload,expected_digest,mutation,check)

    @guard_project("novel_id")
    def story_record(self,novel_id,kind,record_id):
        if kind not in KINDS: raise ValueError("unsupported story record kind")
        rows=read_json(self.backend.novels/novel_id/PATHS[kind],[])
        row=next((row for row in rows if str(row.get('id'))==record_id),None)
        if row is None: raise FileNotFoundError(record_id)
        return envelope(privacy_record(public_record(row)),row.get(META))

    @guard_project("novel_id")
    def _upsert_story_record(self,novel_id,kind,record_id,payload,expected_digest,mutation,check):
        root=self.backend.novels/novel_id
        path=root/PATHS[kind]
        rows=read_json(path,[])
        # Older clients must address an existing exact identity before applying
        # historical slug creation rules, including imported/non-ASCII ids.
        exact=any(str(row.get('id'))==record_id for row in rows)
        creation_id=payload.get('name') or payload.get('title') or f"{payload.get('source_character_id','')}-{payload.get('target_character_id','')}"
        rid=record_id if expected_digest is not UNGUARDED or exact else slug(record_id or creation_id)
        index=next((i for i,row in enumerate(rows) if str(row.get('id'))==rid),None)
        raw=rows[index] if index is not None else None
        current=privacy_record(public_record(raw)) if raw is not None else None
        metadata=raw.get(META) if raw else None
        payload=prepare(kind,rid,current,metadata,payload,expected_digest,mutation)
        if kind in {'characters','locations','relationships'}:
            item=core_record(kind,rid,current,payload,mutation,legacy_defaults={} if kind=='relationships' else None)
        else:
            # Preserve imported extension fields even on writes from older clients.
            item={**(public_record(raw) if raw else {}),"id":rid,"title":payload["title"],
                  "description":payload.get("description",""),"characters":payload.get("characters",[]),
                  "privacy_level":privacy_for_update(payload,current)}
            if kind=='timeline':
                item.update(sequence=payload.get("sequence",len(rows)+1),time=payload.get("time",""),
                            location=payload.get("location",""),chapter_id=payload.get("chapter_id",""),status=payload.get("status","CONFIRMED"))
            else:
                item.update(planted_chapter=payload.get("planted_chapter"),target_chapter=payload.get("target_chapter"),
                            status=payload.get("status","OPEN"),events=payload.get("events",[]))
            if "privacy_level" not in payload and (current is None or current.get("privacy_status")=="UNKNOWN"):
                item["privacy_status"]="UNKNOWN"
            elif "privacy_level" in payload: item.pop("privacy_status",None)
            if mutation and mutation["action"] in {"RESTORE","FEEDBACK"}:item={"id":rid,**payload}
        meta=finish(current,metadata,privacy_record(item),mutation)
        if meta is not None: item[META]=meta
        if check: check()
        if index is None:rows.append(item)
        else:rows[index]=item
        if kind=='timeline':rows.sort(key=lambda row:int(row.get('sequence',0)))
        elif kind=='foreshadowing':rows.sort(key=lambda row:(row.get('planted_chapter') is None,row.get('planted_chapter') or 0))
        atomic_write(path,json.dumps(rows,ensure_ascii=False,indent=2))
        return envelope(privacy_record(public_record(item)),meta) if mutation is not None else public_record(item)

    def upsert_timeline_event(self,novel_id,event_id,payload,*,expected_digest=UNGUARDED,mutation=None,check=None):
        return self._upsert_story_record(novel_id,'timeline',event_id,payload,expected_digest,mutation,check)

    def upsert_foreshadowing(self,novel_id,foreshadowing_id,payload,*,expected_digest=UNGUARDED,mutation=None,check=None):
        return self._upsert_story_record(novel_id,'foreshadowing',foreshadowing_id,payload,expected_digest,mutation,check)
    def upsert_relationship(self,novel_id,relationship_id,payload,*,expected_digest=UNGUARDED,mutation=None,check=None):
        return self._upsert_story_record(novel_id,'relationships',relationship_id,payload,expected_digest,mutation,check)

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
    def save_adaptation_proposal(self,novel_id,proposal,*,expected_revision=None,check=None,finalize=False):
        root=self.backend.novels/novel_id
        path=root/'adaptations.json';rows=read_json(path,[])
        index=next((i for i,row in enumerate(rows) if row.get('id')==proposal['id']),None)
        if index is None and len(rows)>=MAX_PROPOSALS:raise ValueError('ADAPTATION_CAPACITY_PROPOSAL_LIMIT')
        saved=versioned_adaptation(rows[index] if index is not None else None,proposal,expected_revision,finalize=finalize)
        if check:check()
        if index is None:rows.append(saved)
        else:rows[index]=saved
        atomic_write(path,json.dumps(rows,ensure_ascii=False,indent=2));return saved
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
        return {"novel":read_json(root/"novel.json",{}),"characters":[privacy_record(row) for row in read_json(root/"characters/characters.json",[])],"locations":[privacy_record(row) for row in read_json(root/"locations/locations.json",[])],"story_state":read_json(root/"story_state.json",{}),"secrets":[privacy_record(row) for row in read_json(root/"secrets.json",[])],"foreshadowing":[privacy_record(public_record(row)) for row in read_json(root/"foreshadowing.json",[])],"summaries":current_summaries(root,read_json(root/"summaries/index.json",[])),"style_profile":read_json(root/"style/profile.json",{})}
