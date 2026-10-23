"""Media author archive service tests on the original Comic/Asset owners."""
import base64, copy, hashlib, io, json, uuid, zipfile
import pytest
from app.experimental import comic_author_media_archive as a
from app.experimental.media import digest
from app.experimental.comic_layouts import ComicLayoutsService
from app.experimental.store import ExperimentalStore
from app.creative.project_store import CreativeProjectStore
from test_comic_independent import original_independent_owner, blank, panel
from test_r5_comic_layouts import synthetic_png
from test_comic_collections import book_body
from test_r3_mounted_contracts import mounted, checked, prefix
from app.experimental.comic_author_media_archive_api import create_comic_author_media_archive_router

def source(e):
    s=e.experimental.comic_layouts_service
    s.save(e.nid,e.scope,"local-author",blank())
    asset=e.assets.create(e.nid,"author-media-source.png",base64.b64encode(synthetic_png()).decode(),"image/png")
    approved=checked(e.client.post(e.base+"/comic-layouts/images/"+asset["id"]+"/approve",json={"expected_version":asset["version"]}))
    asset=e.assets.get(approved["id"])
    doc=blank(); p=panel(); p["artwork_mode"]="IMAGE"; p["asset_id"]=asset["id"]; p["expected_asset_version"]=asset["version"]
    doc["panels"]=[p]; page=s.save(e.nid,e.scope,"local-author",doc)
    body=book_body([page["id"]]); body["expected_page_versions"]={page["id"]:1}; book=s.save_book(e.nid,e.scope,"local-author",body)
    return s,page,book,asset

def envelope(raw): return {"archive_base64":base64.b64encode(raw).decode(),"archive_sha256":hashlib.sha256(raw).hexdigest()}

def request(e,raw):
    env=envelope(raw); report=e.client.post(e.base+"/comic-layouts/author-media-archive/inspect",json=env)
    assert report.status_code==200,report.text
    return {**env,"inspection_digest":report.json()["inspection_digest"],"request_key":uuid.uuid4().hex,"acknowledge_restore_drafts":True}

def test_mounted_media_archive_api_both_prefixes(mounted):
    import app.api as api
    from app.experimental.flags import require_flag
    e=mounted; e=mounted; s,page,book,asset=source(e)
    router=create_comic_author_media_archive_router(e.experimental.comic_layouts_service, api._workbench_authorize,
        require_flag, authority_lease=api._workbench_authority_lease)
    e.client.app.include_router(router, prefix=e.prefix)
    base=e.prefix+f"/novels/{e.nid}/experimental/comic-layouts"
    preview=e.client.post(base+"/books/"+book["id"]+"/author-media-archive-preview",json={"expected_version":1})
    assert preview.status_code==200,preview.text
    raw=e.client.post(base+"/books/"+book["id"]+"/export-author-media-archive",json={"expected_version":1,
        "export_digest":preview.json()["export_digest"],"acknowledge_author_content":True})
    assert raw.status_code==200,raw.text; raw=raw.content
    env=envelope(raw)
    inspect=e.client.post(base+"/author-media-archive/inspect",json=env)
    assert inspect.status_code==200,inspect.text
    body={**env,"inspection_digest":inspect.json()["inspection_digest"],"request_key":uuid.uuid4().hex,"acknowledge_restore_drafts":True}
    restored=e.client.post(base+"/author-media-archive/restore",json=body)
    assert restored.status_code==200,restored.text
    assert restored.json()["result_state"]=="UNREVIEWED_EDITABLE_DRAFTS"


def _raw(e,s,book):
    preview=a.export_preview(s,e.nid,e.scope,"local-author",book["id"],a.ExportPreviewIn(expected_version=1),lambda:None)
    return a.export_archive(s,e.nid,e.scope,"local-author",book["id"],a.ExportIn(expected_version=1,export_digest=preview["export_digest"],acknowledge_author_content=True),lambda:None)
def _unpack(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as z: return {n:z.read(n) for n in z.namelist()}
def _pack(files):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,"w",compression=zipfile.ZIP_STORED) as z:
        for n,d in files.items(): z.writestr(zipfile.ZipInfo(n),d)
    return stream.getvalue()
def _refresh_page(files, mutator):
    doc=json.loads(files["pages/000.json"]); mutator(doc); files["pages/000.json"]=json.dumps(doc,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
    m=json.loads(files["manifest.json"]); m["pages"][0]["bytes"]=len(files["pages/000.json"]); m["pages"][0]["sha256"]=hashlib.sha256(files["pages/000.json"]).hexdigest(); files["manifest.json"]=json.dumps(m,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()

def test_f1_approval_and_export_reject_unreviewed_imported_assets(mounted):
    e=mounted; s,page,book,asset=source(e); raw=_raw(e,s,book)
    report=a.inspect_archive(s,e.nid,e.scope,"local-author",raw,lambda:None)
    body={"archive_base64":base64.b64encode(raw).decode(),"archive_sha256":hashlib.sha256(raw).hexdigest(),
          "inspection_digest":report["inspection_digest"],"request_key":uuid.uuid4().hex,"acknowledge_restore_drafts":True}
    result=a.restore_archive(s,e.nid,e.scope,"local-author",raw,a.RestoreIn.model_validate(body),lambda:None)
    rid=result["pages"][0]["id"]
    with pytest.raises(ValueError) as exc: s.preflight(e.nid,e.scope,"local-author",rid,1)
    assert str(exc.value)=="COMIC_AUTHOR_MEDIA_ASSET_REVIEW_REQUIRED"
    with pytest.raises(ValueError) as exc: s.export(e.nid,e.scope,"local-author",rid,1)
    assert str(exc.value)=="COMIC_AUTHOR_MEDIA_ASSET_REVIEW_REQUIRED"
    with pytest.raises(ValueError) as exc: s.approve(e.nid,e.scope,"local-author",rid,1,'0'*64,True)
    assert str(exc.value)=="COMIC_AUTHOR_MEDIA_ASSET_REVIEW_REQUIRED"
    assert all(x.get("approved_at") is None for x in e.assets.list(e.nid) if x["id"] not in {asset["id"]})

def test_legacy_empty_receipt_is_tolerated_and_does_not_poison_inspect(mounted):
    e=mounted; s,page,book,asset=source(e); raw=_raw(e,s,book)
    incarnation=s._independent_identity(e.nid); actor="local-author"; request_key=uuid.uuid4().hex
    key=digest([actor,e.scope,incarnation,request_key])
    with s.store.transaction(e.nid,e.scope) as state:
        state["collections"].setdefault(a.RECEIPTS,{})[key]={"contract":a.CONTRACT,"actor":actor,
            "scope":dict(e.scope),"incarnation":incarnation,"request_key":request_key,
            "archive_sha256":"0"*64,"book_id":book["id"],"page_ids":[page["id"]],"asset_ids":[]}
    report=a.inspect_archive(s,e.nid,e.scope,actor,raw,lambda:None)
    assert report["page_count"]==1 and report["asset_count"]==1
    before=s.store.read(e.nid,e.scope)
    fresh=ExperimentalStore(e.root,e.backend,e.url)
    cold=ComicLayoutsService(fresh,e.novels,e.chapters,e.screenplays,e.assets,independent_store=CreativeProjectStore(fresh))
    assert a.inspect_archive(cold,e.nid,e.scope,actor,raw,lambda:None)["page_count"]==1
    assert s.store.read(e.nid,e.scope)==before
    assert any(r.get("asset_ids")==[] for r in before["collections"][a.RECEIPTS].values())


def test_f3_f4_limits_and_alias_preflight_without_staging(mounted):
    e=mounted; s,page,book,asset=source(e); raw=_raw(e,s,book); files=_unpack(raw)
    # F3: a PNG over the per-asset limit must be rejected in decode/inspect.
    big=b"\x89PNG\r\n\x1a\n" + b"x"*(a.MAX_ASSET_BYTES+1)
    files2=dict(files); files2["assets/000.png"]=big
    m=json.loads(files2["manifest.json"]); m["assets"]["asset_000"]["bytes"]=len(big); m["assets"]["asset_000"]["sha256"]=hashlib.sha256(big).hexdigest(); files2["manifest.json"]=json.dumps(m,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
    before=e.assets.list(e.nid)
    with pytest.raises(ValueError): a.inspect_archive(s,e.nid,e.scope,"local-author",_pack(files2),lambda:None)
    # F4: unknown alias must fail before Asset staging.
    files3=dict(files); _refresh_page(files3,lambda d:d["panels"][0].update(asset_id="asset_999"))
    with pytest.raises(ValueError): a.inspect_archive(s,e.nid,e.scope,"local-author",_pack(files3),lambda:None)
    # F2: a receipt with no assets is not a supported profile; reject before staging.
    files4=dict(files); files4.pop("assets/000.png")
    m=json.loads(files4["manifest.json"]); m["assets"]={}; files4["manifest.json"]=json.dumps(m,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
    _refresh_page(files4,lambda d:(d["panels"][0].pop("asset_id",None),d["panels"][0].pop("expected_asset_version",None)))
    with pytest.raises(ValueError): a.inspect_archive(s,e.nid,e.scope,"local-author",_pack(files4),lambda:None)
    assert e.assets.list(e.nid)==before

def _file_snapshot(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}

def _forged_restore_body(e,s,raw):
    sha=hashlib.sha256(raw).hexdigest(); incarnation=s._independent_identity(e.nid)
    token=digest({"contract":a.CONTRACT,"archive_sha256":sha,"scope":e.scope,"actor":"local-author","incarnation":incarnation})
    return a.RestoreIn(archive_base64=base64.b64encode(raw).decode(),archive_sha256=sha,
        inspection_digest=token,request_key=uuid.uuid4().hex,acknowledge_restore_drafts=True)

def test_three_old_ready_tokens_direct_restore_reject_with_zero_file_changes(mounted):
    e=mounted; s,page,book,asset=source(e); raw=_raw(e,s,book); files=_unpack(raw)
    over=dict(files); over["assets/000.png"]=b"\x89PNG\r\n\x1a\n"+b"x"*(a.MAX_ASSET_BYTES+1)
    m=json.loads(over["manifest.json"]); m["assets"]["asset_000"]["bytes"]=len(over["assets/000.png"]); m["assets"]["asset_000"]["sha256"]=hashlib.sha256(over["assets/000.png"]).hexdigest(); over["manifest.json"]=json.dumps(m,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
    missing=dict(files); _refresh_page(missing,lambda d:d["panels"][0].update(asset_id="asset_999"))
    empty=dict(files); empty.pop("assets/000.png"); m=json.loads(empty["manifest.json"]); m["assets"]={}; empty["manifest.json"]=json.dumps(m,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode(); _refresh_page(empty,lambda d:(d["panels"][0].pop("asset_id",None),d["panels"][0].pop("expected_asset_version",None)))
    for mutated in (over,missing,empty):
        raw2=_pack(mutated); before=_file_snapshot(e.root)
        with pytest.raises(ValueError): a.restore_archive(s,e.nid,e.scope,"local-author",raw2,_forged_restore_body(e,s,raw2),lambda:None)
        assert _file_snapshot(e.root)==before

def test_exact_8mb_valid_png_roundtrip(mounted):
    e=mounted; s,page,book,asset=source(e); raw=_raw(e,s,book); files=_unpack(raw)
    png=synthetic_png(); big=png+b"\0"*(a.MAX_ASSET_BYTES-len(png)); assert len(big)==a.MAX_ASSET_BYTES
    files["assets/000.png"]=big; m=json.loads(files["manifest.json"]); m["assets"]["asset_000"]["bytes"]=len(big); m["assets"]["asset_000"]["sha256"]=hashlib.sha256(big).hexdigest(); files["manifest.json"]=json.dumps(m,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
    raw2=_pack(files); report=a.inspect_archive(s,e.nid,e.scope,"local-author",raw2,lambda:None)
    body={"archive_base64":base64.b64encode(raw2).decode(),"archive_sha256":hashlib.sha256(raw2).hexdigest(),
          "inspection_digest":report["inspection_digest"],"request_key":uuid.uuid4().hex,"acknowledge_restore_drafts":True}
    restored=a.restore_archive(s,e.nid,e.scope,"local-author",raw2,a.RestoreIn.model_validate(body),lambda:None)
    new_asset=restored["pages"][0]["document"]["panels"][0]["asset_id"]
    with s._studio_asset_scope(e.nid,e.scope):
        assert e.assets.content(new_asset)==big
    exported=_raw(e,s,restored["book"])
    with zipfile.ZipFile(io.BytesIO(exported)) as z: assert z.read("assets/000.png")==big
    assert a.inspect_archive(s,e.nid,e.scope,"local-author",exported,lambda:None)["page_count"]==1

def test_media_export_inspect_restore_reopen_and_explicit_import(mounted):
    e=mounted; s,page,book,asset=source(e)
    preview=a.export_preview(s,e.nid,e.scope,"local-author",book["id"],a.ExportPreviewIn(expected_version=1),lambda:None)
    assert preview["asset_count"]==1 and preview["coverage"]=="INDEPENDENT_PAGE_WITH_PNG_PANEL_ASSETS"
    raw=a.export_archive(s,e.nid,e.scope,"local-author",book["id"],a.ExportIn(expected_version=1,export_digest=preview["export_digest"],acknowledge_author_content=True),lambda:None)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names=z.namelist(); assert "manifest.json" in names and any(n.startswith("assets/") for n in names)
        assert not any(n.startswith("../") for n in names)
    report=a.inspect_archive(s,e.nid,e.scope,"local-author",raw,lambda:None)
    assert report["page_count"]==1 and report["asset_count"]==1
    report=a.inspect_archive(s,e.nid,e.scope,"local-author",raw,lambda:None)
    body={"archive_base64":base64.b64encode(raw).decode(),"archive_sha256":hashlib.sha256(raw).hexdigest(),
          "inspection_digest":report["inspection_digest"],"request_key":uuid.uuid4().hex,"acknowledge_restore_drafts":True}
    restored=a.restore_archive(s,e.nid,e.scope,"local-author",raw,a.RestoreIn.model_validate(body),lambda:None)
    target=restored["pages"][0]; target_book=restored["book"]
    assert target["status"]=="DRAFT" and target_book["status"]=="DRAFT"
    assert target["document"]["panels"][0]["asset_id"]!=asset["id"]
    assets=e.assets.list(e.nid); assert all(x["approved_at"] is None for x in assets if x["id"] not in {asset["id"]})
    doc=copy.deepcopy(target["document"]); doc["panels"][0]["bubbles"][0]["text"]="Edited after reopen"
    updated=s.save(e.nid,e.scope,"local-author",doc,rid=target["id"],expected_version=1)
    assert updated["document"]["panels"][0]["bubbles"][0]["text"]=="Edited after reopen"
    replay=a.restore_archive(s,e.nid,e.scope,"local-author",raw,a.RestoreIn.model_validate(body),lambda:None)
    assert replay["replayed"] and replay["pages"][0]["id"]==target["id"]
    fresh=ExperimentalStore(e.root,e.backend,e.url)
    reopened=ComicLayoutsService(fresh,e.novels,e.chapters,e.screenplays,e.assets,independent_store=CreativeProjectStore(fresh))
    reopened_view=reopened._view(e.nid,e.scope,"local-author",reopened._row(e.nid,e.scope,"local-author",target["id"]))
    assert reopened_view["document"]["panels"][0]["bubbles"][0]["text"]=="Edited after reopen"

def test_media_archive_rejects_traversal_and_duplicate_and_corrupt_png(mounted):
    e=mounted; s,page,book,asset=source(e)
    preview=a.export_preview(s,e.nid,e.scope,"local-author",book["id"],a.ExportPreviewIn(expected_version=1),lambda:None)
    raw=a.export_archive(s,e.nid,e.scope,"local-author",book["id"],a.ExportIn(expected_version=1,export_digest=preview["export_digest"],acknowledge_author_content=True),lambda:None)
    with zipfile.ZipFile(io.BytesIO(raw)) as z: files={n:z.read(n) for n in z.namelist()}
    def pack(files):
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,"w",compression=zipfile.ZIP_STORED) as z:
            for n,d in files.items(): z.writestr(zipfile.ZipInfo(n),d)
        return stream.getvalue()
    for mutated in [pack({**files,"../x":b"x"}), pack({**files,"manifest.json":b"{}"}), pack({**files,"assets/000.png":b"not png"})]:
        with pytest.raises(ValueError): a.decode(mutated)
    before=s.store.read(e.nid,e.scope)
    with pytest.raises(ValueError): a.inspect_archive(s,e.nid,e.scope,"local-author",pack({**files,"assets/000.png":b"not png"}),lambda:None)
    assert s.store.read(e.nid,e.scope)==before
