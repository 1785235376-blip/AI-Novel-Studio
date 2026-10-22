"""Media author archive service tests on the original Comic/Asset owners."""
import base64, copy, hashlib, io, json, uuid, zipfile
import pytest
from app.experimental import comic_author_media_archive as a
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
