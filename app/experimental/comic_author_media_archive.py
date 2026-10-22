"""Bounded private PAGE author archive carrying PNG panel assets.

This is an editable author interchange, never a reading/publication copy. It
reuses the original Comic page/book owner and original Asset owner; import
creates new unapproved draft page rows and new unapproved project assets. It
does not copy approvals, history, actors or project IDs.
"""
from __future__ import annotations
import base64, copy, hashlib, io, json, re, stat, zipfile
from pydantic import Field, ValidationError
from .media import StrictModel, digest
from .common import new_id, new_row, check_version, StaleSourceError
from .comic_collections import ComicBookIn
from .comic_layouts import LayoutIn
from .store import canonical

CONTRACT = "comic-author-media-page/1"
RECEIPTS = "comic_author_media_archive_receipts_v1"
MAX_ARCHIVE = 48_000_000
MAX_JSON = 180_000
MAX_PAGES = 10
MAX_ASSETS = 32
MAX_ASSET_BYTES = 8_000_000
MAX_TOTAL_PNG = 32_000_000
MAX_PIXELS = 20_000_000
MAX_TOTAL_JSON = 1_800_000
DISCLOSURE = "PRIVATE_AUTHOR_CONTENT_INCLUDES_PNG_ASSETS_AND_UNREVIEWED_DRAFTS_NOT_A_PUBLIC_READING_COPY"

class ExportPreviewIn(StrictModel):
    expected_version: int = Field(ge=1, strict=True)
class ExportIn(ExportPreviewIn):
    export_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    acknowledge_author_content: bool = Field(strict=True)
class ArchiveIn(StrictModel):
    archive_base64: str = Field(max_length=4 * ((MAX_ARCHIVE + 2) // 3))
    archive_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
class RestoreIn(ArchiveIn):
    inspection_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    request_key: str = Field(pattern=r"^[a-f0-9]{32}$")
    acknowledge_restore_drafts: bool = Field(strict=True)

def _fail():
    raise ValueError("COMIC_AUTHOR_MEDIA_ARCHIVE_INVALID_OR_UNSUPPORTED")

def _json(raw):
    if not 1 <= len(raw) <= MAX_JSON: _fail()
    try:
        def pairs(items):
            d = {}
            for k, v in items:
                if k in d: _fail()
                d[k] = v
            return d
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=lambda _: _fail())
        pending=[value]; nodes=0
        while pending:
            item=pending.pop(); nodes += 1
            if nodes > 12000: _fail()
            if isinstance(item,dict): pending.extend(item.values())
            elif isinstance(item,list): pending.extend(item)
        return value
    except (UnicodeError, ValueError, RecursionError, TypeError): _fail()

def _document(value):
    try: body=LayoutIn.model_validate(value, strict=True)
    except ValidationError: _fail()
    if (body.source_mode != "INDEPENDENT" or body.preset != "PAGE" or body.screenplay_id is not None
            or body.expected_screenplay_version is not None): _fail()
    if body.layer_stack and any(item.kind == "RASTER" for item in body.layer_stack.items): _fail()
    for panel in body.panels:
        if (panel.shot_id is not None or panel.character_ids or panel.appearance_references
                or any(b.character_id is not None for b in panel.bubbles)): _fail()
        if (panel.asset_id is None) != (panel.expected_asset_version is None): _fail()
    document=body.model_dump()
    if document != value: _fail()
    if len(canonical(document).encode()) > MAX_JSON: _fail()
    return document

def _remap(document, portable, asset_map=None):
    document=copy.deepcopy(document); refs={}
    for pindex,panel in enumerate(document["panels"]):
        pid=f"panel_{pindex:03}" if portable else new_id()
        refs[("PANEL",panel["id"])]=pid; panel["id"]=pid
        for bindex,bubble in enumerate(panel["bubbles"]):
            bid=f"bubble_{pindex:03}_{bindex:03}" if portable else new_id()
            refs[("BUBBLE",bubble["id"])]=bid; bubble["id"]=bid
        if portable and panel.get("asset_id") is not None:
            panel["asset_id"]=asset_map[panel["asset_id"]]
            panel["expected_asset_version"]=1
    for index,layer in enumerate(document.get("layer_stack",{}).get("items",[])):
        layer["id"]=f"layer_{index:03}" if portable else "layer_"+new_id()
        layer["target_id"]=refs[("PANEL" if layer["kind"].startswith("PANEL_") else "BUBBLE",layer["target_id"])]
    return document

def _png(data):
    if not isinstance(data,bytes) or len(data) < 8 or data[:8] != bytes([137,80,78,71,13,10,26,10]): _fail()
    try:
        from PIL import Image
        image=Image.open(io.BytesIO(data)); image.verify()
        image=Image.open(io.BytesIO(data)); image.load()
        if image.format != "PNG" or image.width < 1 or image.height < 1 or image.width*image.height > MAX_PIXELS: _fail()
        return image.width,image.height
    except Exception: _fail()

def _portable(service,nid,scope,actor,book,pages,guard):
    aliases={}; assets=[]; allow_unapproved=any(p.get("_author_media_import") for p in pages)
    def alias(aid):
        if aid not in aliases:
            if len(aliases) >= MAX_ASSETS: _fail()
            aliases[aid]=f"asset_{len(aliases):03}"; assets.append(aid)
        return aliases[aid]
    entries=[]; blobs={}
    for index,row in enumerate(pages):
        document=_document(row["document"])
        for panel in document["panels"]:
            if panel.get("asset_id") is not None: alias(panel["asset_id"])
        document=_remap(document,True,{k:aliases[k] for k in aliases})
        name=f"pages/{index:03}.json"; raw=canonical(document).encode(); blobs[name]=raw
        entries.append({"alias":f"page_{index:03}","path":name,"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()})
    total=0; asset_entries={}
    for aid in assets:
        asset,data=service._asset(nid,scope,actor,aid,approved=not allow_unapproved,author_media=allow_unapproved)
        width,height=_png(data)
        name=f"assets/{len(asset_entries):03}.png"
        if len(data) > MAX_ASSET_BYTES or total+len(data) > MAX_TOTAL_PNG: _fail()
        total += len(data); blobs[name]=data; asset_entries[aliases[aid]]={"path":name,"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest(),"width":width,"height":height}
    page_alias={row["id"]:f"page_{i:03}" for i,row in enumerate(pages)}
    chapters=[{"id":f"chapter_{i:03}","title":c["title"],"pages":[page_alias[p] for p in c["pages"]]} for i,c in enumerate(book["document"]["chapters"])]
    manifest={"contract":CONTRACT,"book":{"title":book["document"]["title"],"chapters":chapters},"pages":entries,"assets":asset_entries}
    blobs["manifest.json"]=canonical(manifest).encode()
    return blobs

def decode(raw):
    if not isinstance(raw,bytes) or not 22 <= len(raw) <= MAX_ARCHIVE: _fail()
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            infos=archive.infolist()
            if not 3 <= len(infos) <= MAX_PAGES+MAX_ASSETS+1 or archive.comment: _fail()
            names=[i.filename for i in infos]
            if len(set(names)) != len(names) or "manifest.json" not in names: _fail()
            total=0
            for item in infos:
                mode=item.external_attr>>16
                if (item.is_dir() or item.flag_bits not in (0,2048) or item.compress_type != zipfile.ZIP_STORED
                        or item.file_size != item.compress_size or item.file_size < 1 or item.extra or item.comment
                        or stat.S_IFMT(mode) not in (0,stat.S_IFREG)): _fail()
                total += item.file_size
            if total > MAX_TOTAL_JSON + MAX_TOTAL_PNG: _fail()
            manifest=_json(archive.read("manifest.json"))
            if not isinstance(manifest,dict) or set(manifest) != {"contract","book","pages","assets"} or manifest["contract"] != CONTRACT: _fail()
            entries=manifest["pages"]; assets=manifest["assets"]
            if not isinstance(entries,list) or not 1 <= len(entries) <= MAX_PAGES: _fail()
            if not isinstance(assets,dict) or len(assets) > MAX_ASSETS: _fail()
            expected={"manifest.json"}|{e.get("path") for e in entries}|{a.get("path") for a in assets.values()}
            if expected != set(names): _fail()
            page_docs=[]; asset_data={}; total_png=0
            for alias,entry in assets.items():
                if not re.fullmatch(r"asset_[0-9]{3}",alias) or not isinstance(entry,dict) or set(entry) != {"path","bytes","sha256","width","height"}: _fail()
                if entry["path"] != f"assets/{int(alias[-3:]):03}.png": _fail()
                content=archive.read(entry["path"])
                if len(content) != entry["bytes"] or hashlib.sha256(content).hexdigest() != entry["sha256"]: _fail()
                w,h=_png(content)
                if (w,h) != (entry["width"],entry["height"]) or total_png+len(content) > MAX_TOTAL_PNG: _fail()
                total_png += len(content); asset_data[alias]={"bytes":content,"width":w,"height":h,"sha256":entry["sha256"]}
            book=ComicBookIn.model_validate(manifest["book"],strict=True).model_dump(exclude={"expected_page_versions"})
            if any(c["id"] != f"chapter_{i:03}" for i,c in enumerate(book["chapters"])): _fail()
            aliases=[f"page_{i:03}" for i in range(len(entries))]
            if [p for c in book["chapters"] for p in c["pages"]] != aliases: _fail()
            for index,entry in enumerate(entries):
                if not isinstance(entry,dict) or set(entry) != {"alias","path","bytes","sha256"} or entry["alias"] != aliases[index] or entry["path"] != f"pages/{index:03}.json": _fail()
                content=archive.read(entry["path"])
                if len(content) != entry["bytes"] or hashlib.sha256(content).hexdigest() != entry["sha256"]: _fail()
                page_docs.append(_document(_json(content)))
            return book,page_docs,asset_data
    except Exception: _fail()

def _snapshot(service,nid,scope,actor,rid,version,guard):
    guard()
    with service._independent_transaction(nid,scope) as state:
        guard(); book=service._book_row(nid,scope,actor,rid,state); check_version(book,version)
        ids=service._book_pages(book["document"])
        if not 1 <= len(ids) <= MAX_PAGES: _fail()
        pages=[service._book_page(nid,scope,actor,pid,state) for pid in ids]
        blobs=_portable(service,nid,scope,actor,book,pages,guard)
        pin=digest({"contract":CONTRACT,"actor":actor,"scope":scope,"incarnation":service._independent_identity(nid),
            "book":{k:book[k] for k in ("id","version","document")},"pages":[{k:p[k] for k in ("id","version","document")} for p in pages]})
        report={"contract":CONTRACT,"export_digest":pin,"book_version":book["version"],"page_count":len(pages),
                "asset_count":len({p["document"]["panels"][i]["asset_id"] for p in pages for i,panel in enumerate(p["document"]["panels"]) if panel.get("asset_id")}),
                "disclosure":DISCLOSURE,"pages":[{"id":p["id"],"version":p["version"]} for p in pages],
                "coverage":"INDEPENDENT_PAGE_WITH_PNG_PANEL_ASSETS","conveys_approval":False,"asset_approvals_copied":False}
        guard()
    return blobs,report

def export_preview(service,nid,scope,actor,rid,body,guard): return _snapshot(service,nid,scope,actor,rid,body.expected_version,guard)[1]
def export_archive(service,nid,scope,actor,rid,body,guard):
    blobs,report=_snapshot(service,nid,scope,actor,rid,body.expected_version,guard)
    if body.acknowledge_author_content is not True or body.export_digest != report["export_digest"]: raise StaleSourceError("COMIC_AUTHOR_MEDIA_EXPORT_PREVIEW_CHANGED")
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,"w",compression=zipfile.ZIP_STORED) as archive:
        for name,content in blobs.items():
            item=zipfile.ZipInfo(name); item.external_attr=(stat.S_IFREG|0o600)<<16; archive.writestr(item,content)
    raw=stream.getvalue(); decode(raw)
    if _snapshot(service,nid,scope,actor,rid,body.expected_version,guard)[1] != report: raise StaleSourceError("COMIC_AUTHOR_MEDIA_EXPORT_PREVIEW_CHANGED")
    guard(); return raw

def _receipt(row,key,actor,scope,incarnation):
    if (not isinstance(row,dict) or set(row) != {"contract","actor","scope","incarnation","request_key","archive_sha256","book_id","page_ids","asset_ids"}
            or row["contract"] != CONTRACT or row["actor"] != actor or row["scope"] != scope or row["incarnation"] != incarnation
            or not re.fullmatch(r"[a-f0-9]{32}",row.get("request_key","")) or not re.fullmatch(r"[a-f0-9]{64}",row.get("archive_sha256",""))
            or key != digest([actor,scope,incarnation,row.get("request_key")]) or not isinstance(row["book_id"],str)
            or not isinstance(row["page_ids"],list) or not 1 <= len(row["page_ids"]) <= MAX_PAGES or len(set(row["page_ids"])) != len(row["page_ids"])
            or not isinstance(row["asset_ids"],list) or not 1 <= len(row["asset_ids"]) <= MAX_ASSETS or len(set(row["asset_ids"])) != len(row["asset_ids"])): _fail()
    return row

def inspect_archive(service,nid,scope,actor,raw,guard):
    guard(); book,docs,assets=decode(raw); incarnation=service._independent_identity(nid)
    sha=hashlib.sha256(raw).hexdigest(); token=digest({"contract":CONTRACT,"archive_sha256":sha,"scope":scope,"actor":actor,"incarnation":incarnation})
    rows=service.store.read(nid,scope)["collections"].get(RECEIPTS,{})
    owned=[_receipt(r,k,actor,scope,incarnation) for k,r in rows.items() if isinstance(r,dict) and r.get("actor")==actor and r.get("incarnation")==incarnation]
    return {"completed_attempts":[{"request_key":r["request_key"],"result_state":"COMPLETED"} for r in owned if r["archive_sha256"]==sha],
        "receipt_capacity":20,"receipt_remaining":max(0,20-len(owned)),"contract":CONTRACT,"archive_sha256":sha,"inspection_digest":token,
        "title":book["title"],"page_count":len(docs),"asset_count":len(assets),"disclosure":DISCLOSURE,
        "restore_status":"READY_FOR_EXPLICIT_IMPORT_AS_UNREVIEWED_DRAFT","coverage":"INDEPENDENT_PAGE_WITH_PNG_PANEL_ASSETS","asset_approvals_copied":False}

def _create_assets(service,nid,scope,actor,sha,assets,guard):
    created={}
    with service._studio_asset_scope(nid,scope):
        for alias,info in sorted(assets.items()):
            guard()
            row=service.assets.create(nid,f"author-media-{alias}.png",base64.b64encode(info["bytes"]).decode(),"image/png","image",
                f"comic-media-author:{sha}:{alias}",branch_id=scope.get("branch_id"),guard=guard)
            if row["sha256"] != info["sha256"]: _fail()
            created[alias]=row
    return created

def restore_archive(service,nid,scope,actor,raw,body,guard):
    report=inspect_archive(service,nid,scope,actor,raw,guard)
    if body.acknowledge_restore_drafts is not True or body.archive_sha256 != report["archive_sha256"] or body.inspection_digest != report["inspection_digest"]:
        raise StaleSourceError("COMIC_AUTHOR_MEDIA_IMPORT_PREVIEW_CHANGED")
    book_document,docs,assets=decode(raw)
    created=_create_assets(service,nid,scope,actor,report["archive_sha256"],assets,guard)
    with service._independent_transaction(nid,scope) as state:
        guard()
        if inspect_archive(service,nid,scope,actor,raw,guard)["inspection_digest"] != report["inspection_digest"]: raise StaleSourceError("COMIC_AUTHOR_MEDIA_IMPORT_PREVIEW_CHANGED")
        incarnation=service._independent_identity(nid); key=digest([actor,scope,incarnation,body.request_key])
        rows=state["collections"].get(RECEIPTS,{})
        if key in rows:
            receipt=_receipt(rows[key],key,actor,scope,incarnation)
            if receipt["archive_sha256"] != body.archive_sha256: raise ValueError("COMIC_AUTHOR_MEDIA_IMPORT_REQUEST_CONFLICT")
            book=service._book_row(nid,scope,actor,receipt["book_id"],state); pages=[service._book_page(nid,scope,actor,pid,state) for pid in receipt["page_ids"]]
            return {"book":service._book_view(nid,scope,actor,book,state),"pages":[service._view(nid,scope,actor,p) for p in pages],
                "replayed":True,"request_key":body.request_key,"result_state":"CURRENT_EDITABLE_ROWS_FROM_COMPLETED_IMPORT"}
        owned=[r for r in rows.values() if r.get("actor")==actor and r.get("incarnation")==incarnation]
        if len(owned) >= 20: raise ValueError("COMIC_AUTHOR_MEDIA_IMPORT_RECEIPT_LIMIT")
        if len(service._book_owner_rows(nid,actor,state)) >= 20: raise ValueError("COMIC_BOOK_COUNT_LIMIT")
        pages=[]
        for doc in docs:
            doc=_remap(doc,False)
            new_assets={}
            for panel in doc["panels"]:
                if panel.get("asset_id") is not None:
                    alias=panel["asset_id"]
                    if alias not in created: _fail()
                    new_assets[alias]=created[alias]
                    panel["asset_id"]=created[alias]["id"]; panel["expected_asset_version"]=1
            body_doc=LayoutIn.model_validate(doc,strict=True).model_dump()
            asset_sources={}
            for asset in new_assets.values():
                observed,_=service._asset(nid,scope,actor,asset["id"],author_media=True)
                asset_sources[asset["id"]]=service._binding(observed)
            payload={"project_incarnation":incarnation,"document":body_doc,"screenplay_version":None,
                "source_evidence":{"sources":{},"privacy":{}},"character_sources":{},
                "asset_sources":asset_sources,
                "scene_ids":{p["id"]:None for p in body_doc["panels"]},"status":"DRAFT","approval":None,"_author_media_import":True}
            service._current(nid,scope,actor,payload)
            page=new_row(nid,scope,actor,payload); state["collections"].setdefault(service.RECORDS,{})[page["id"]]=page; pages.append(page)
        mapping={f"page_{i:03}":p["id"] for i,p in enumerate(pages)}
        for chapter in book_document["chapters"]: chapter["id"]=new_id(); chapter["pages"]=[mapping[p] for p in chapter["pages"]]
        book=new_row(nid,scope,actor,{"document":book_document,"project_incarnation":incarnation,"status":"DRAFT","snapshot_scope":"STRUCTURE_ONLY"})
        state["collections"].setdefault(service.BOOKS,{})[book["id"]]=book; service._book_bound(nid,actor,state)
        state["collections"].setdefault(RECEIPTS,{})[key]={"contract":CONTRACT,"actor":actor,"scope":copy.deepcopy(scope),"incarnation":incarnation,
            "request_key":body.request_key,"archive_sha256":body.archive_sha256,"book_id":book["id"],"page_ids":[p["id"] for p in pages],
            "asset_ids":[created[a]["id"] for a in sorted(created)]}
        result={"book":service._book_view(nid,scope,actor,book,state),"pages":[service._view(nid,scope,actor,p) for p in pages],
            "replayed":False,"request_key":body.request_key,"result_state":"UNREVIEWED_EDITABLE_DRAFTS","asset_approvals_copied":False}
        guard()
    return result
