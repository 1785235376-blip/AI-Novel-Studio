"""Real codec bytes and original File/PostgreSQL authority owner scenarios."""
import copy
import hashlib
import io
import json
import zipfile
import pytest
from PIL import Image
import test_comic_publication as cbz
from test_comic_publication import setup_book, publication_scope
from test_comic_independent import original_independent_owner
from test_r3_mounted_contracts import mounted, prefix, checked
from app.experimental import comic_page_archive_codec as codec
from app.experimental.comic_publication import export_page_archive, _render_page


def request(e, book, path, image_format='WEBP', loss_mode='LOSSLESS', quality=None):
    body = {'expected_version': book['version'], 'reading_direction': 'RTL',
            'image_format': image_format, 'loss_mode': loss_mode, 'quality': quality}
    report = checked(e.client.post(path + '/page-archive-preflight', json=body))
    return {**body, 'pages': report['pages'], 'publication_digest': report['publication_digest']}, report


@pytest.mark.parametrize('fmt,mode,quality', [('JPEG','LOSSY',100), ('WEBP','LOSSY',80), ('WEBP','LOSSLESS',None)])
def test_actual_ordered_codec_bytes_and_no_mutation(mounted, fmt, mode, quality):
    e = mounted; service, pages, book, path = setup_book(e, 3)
    before = e.store.read(e.nid, e.scope)
    body, report = request(e, book, path, fmt, mode, quality)
    response = e.client.post(path + '/export-page-archive', json=body)
    assert response.status_code == 200, response.text
    assert response.headers['content-type'] == 'application/zip'
    assert response.headers['content-disposition'].endswith('comic-pages.zip"')
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-content-sha256'] == hashlib.sha256(response.content).hexdigest()
    assert response.headers['x-comic-publication-digest'] == report['publication_digest']
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        ext = 'jpg' if fmt == 'JPEG' else 'webp'
        assert archive.namelist() == [f'{i:04}.{ext}' for i in range(1,4)] + ['manifest.json']
        assert manifest['image_format'] == fmt and manifest['loss_mode'] == mode and manifest['quality'] == quality
        assert manifest['reading_direction'] == 'RTL' and manifest['page_order'] == 'SAVED_CHAPTER_THEN_PAGE_ORDER'
        assert 'NO_COLOR_PROFILE_OR_PRINT_FIDELITY' in manifest['losses']
        assert ('PIXEL_EXACT_FLATTENED_RGB_ONLY' if mode == 'LOSSLESS' else 'LOSSY_PIXELS_INCLUDING_QUALITY_100') in manifest['losses']
        assert not any(s in json.dumps(manifest) for s in ['local-author','asset_sources','source_evidence','project_incarnation'])
        for i, page in enumerate(manifest['pages']):
            data = archive.read(page['filename'])
            assert hashlib.sha256(data).hexdigest() == page['sha256']
            with Image.open(io.BytesIO(data)) as image:
                image.load()
                assert image.format == fmt and image.size == (320,640)
                assert not set(image.info).intersection({'exif','icc_profile','xmp','comment'})
                assert max(image.getpixel((24+i,24))) < 40
                if mode == 'LOSSLESS':
                    row = service._row(e.nid,e.scope,'local-author',pages[i]['id'])
                    with Image.open(io.BytesIO(_render_page(service,e.nid,e.scope,'local-author',row))) as original:
                        assert image.tobytes() == original.tobytes()
    assert before == e.store.read(e.nid,e.scope)
    assert e.client.post(path + '/export-page-archive',json=body).content == response.content


@pytest.mark.parametrize('patch', [{'image_format':'PNG'}, {'image_format':'JPEG'}, {'quality':80}, {'loss_mode':'LOSSY'}, {'quality':False}, {'quality':80.0}, {'quality':'80'}, {'method':6}])
def test_invalid_explicit_codec_contract(mounted, patch):
    e=mounted; _,_,book,path=setup_book(e,1)
    body={'expected_version':book['version'],'reading_direction':'LTR','image_format':'WEBP','loss_mode':'LOSSLESS','quality':None,**patch}
    assert e.client.post(path+'/page-archive-preflight',json=body).status_code == 422


def test_format_quality_mode_digest_drift(mounted):
    e=mounted; _,_,book,path=setup_book(e,1)
    first,_=request(e,book,path,'JPEG','LOSSY',80)
    for patch in ({'image_format':'WEBP'}, {'quality':100}, {'image_format':'WEBP','loss_mode':'LOSSLESS','quality':None}):
        assert e.client.post(path+'/export-page-archive',json={**first,**patch}).status_code==409
    assert e.client.post(path+'/export-cbz',json=first).status_code==422
    old=cbz.request(e,book,path)
    assert e.client.post(path+'/export-page-archive',json={**first,'publication_digest':old['publication_digest']}).status_code==409


@pytest.mark.parametrize('kind',['pixels','pages','side','work','output','unavailable','decode','render','encoded'])
def test_entire_request_limits_before_codec(mounted,monkeypatch,kind):
    from app.experimental import comic_publication_budget as budget
    e=mounted; _,_,book,path=setup_book(e,2); body,_=request(e,book,path)
    def forbidden(*args,**kwargs): raise AssertionError('codec allocation before admission')
    monkeypatch.setattr(codec,'encode',forbidden)
    names={'pixels':'MAX_CODEC_PIXELS','pages':'MAX_CODEC_PAGES','side':'MAX_CODEC_SIDE','work':'MAX_CODEC_WORK_BYTES'}
    if kind in names: monkeypatch.setattr(codec,names[kind],1)
    elif kind=='output': monkeypatch.setattr(budget,'MAX_ARCHIVE_BYTES',1)
    elif kind=='unavailable': monkeypatch.setattr(codec.features,'check',lambda _:False)
    else: monkeypatch.setattr(budget,{'decode':'MAX_DECODE_PIXELS','render':'MAX_RENDER_PIXELS','encoded':'MAX_BUFFER_WRITE_BYTES'}[kind],1)
    response=e.client.post(path+'/export-page-archive',json=body)
    assert response.status_code==422,response.text
    assert not response.content.startswith(b'PK')


def test_admission_supports_one_1024_square_and_rejects_cumulative(monkeypatch):
    from app.experimental.comic_publication import PageArchiveIn
    request=PageArchiveIn(expected_version=1,reading_direction='LTR',image_format='WEBP',loss_mode='LOSSLESS',quality=None)
    assert codec.admit([(1024,1024)],request)['total_page_pixels']==1048576
    with pytest.raises(ValueError,match='PIXEL_LIMIT'): codec.admit([(1024,1024),(320,640)],request)


def archive_routes(e,monkeypatch):
    post=e.client.post
    def archive_post(url,**kwargs):
        if url.endswith(('/publication-preflight','/export-cbz')):
            url=url.removesuffix('/publication-preflight')+'/page-archive-preflight' if url.endswith('/publication-preflight') else url.removesuffix('/export-cbz')+'/export-page-archive'
            kwargs['json']={**kwargs['json'],'image_format':'WEBP','loss_mode':'LOSSLESS','quality':None}
        response=post(url,**kwargs)
        if response.status_code!=200: assert not response.content.startswith(b'PK')
        return response
    monkeypatch.setattr(e.client,'post',archive_post)


@pytest.mark.parametrize('change',['page_pin','digest','missing','extra','order','book_version','direction'])
def test_exact_archive_pins(mounted,monkeypatch,change):
    archive_routes(mounted,monkeypatch); cbz.test_exact_export_pins(mounted,change)


@pytest.mark.parametrize('change',['page','book','approval'])
def test_archive_final_recheck(mounted,monkeypatch,change):
    archive_routes(mounted,monkeypatch); cbz.test_global_final_recheck_first_page_after_render(mounted,monkeypatch,change)


@pytest.mark.parametrize('change',['asset','privacy','decode','source'])
def test_archive_current_sources(mounted,monkeypatch,change):
    archive_routes(mounted,monkeypatch); cbz.test_actual_source_pins_and_decode_budget(mounted,monkeypatch,change)


@pytest.mark.parametrize('change',['draft','webtoon','owner','actor','scope'])
def test_archive_current_owner(mounted,monkeypatch,change):
    archive_routes(mounted,monkeypatch); cbz.test_unapproved_or_foreign_page_fail_closed(mounted,change)


def test_archive_real_scope_and_revocation(publication_scope,monkeypatch):
    archive_routes(publication_scope,monkeypatch); cbz.test_real_session_scope_and_mid_render_revocation(publication_scope,monkeypatch)


def test_final_guard_after_codec(mounted,monkeypatch):
    e=mounted; service,_,book,path=setup_book(e,1); body,_=request(e,book,path)
    original=codec.encode; revoked=False
    def encode(*args,**kwargs):
        nonlocal revoked
        data=original(*args,**kwargs); revoked=True; return data
    monkeypatch.setattr(codec,'encode',encode)
    def guard():
        if revoked: raise PermissionError('revoked')
    with pytest.raises(PermissionError): export_page_archive(service,e.nid,e.scope,'local-author',book['id'],body,guard)


@pytest.mark.parametrize('fmt,mode,quality',[('JPEG','LOSSY',100),('WEBP','LOSSY',100),('WEBP','LOSSLESS',None)])
def test_maximum_admitted_entropy_roundtrip(fmt,mode,quality):
    import random
    from app.experimental.comic_publication import PageArchiveIn
    from app.experimental.comic_publication_budget import publication_budget
    request=PageArchiveIn(expected_version=1,reading_direction='LTR',image_format=fmt,loss_mode=mode,quality=quality)
    limits=codec.admit([(1024,1024)],request)
    raw=random.Random(27).randbytes(1024*1024*3)
    with Image.frombytes('RGB',(1024,1024),raw) as source:
        png=io.BytesIO(); source.save(png,format='PNG')
    with publication_budget(): data=codec.encode(png.getvalue(),1024,1024,request)
    assert len(data)<limits['reserved_output_bytes']
    with Image.open(io.BytesIO(data)) as decoded:
        assert decoded.size==(1024,1024)
        if mode=='LOSSLESS': assert decoded.tobytes()==raw
        else: assert decoded.tobytes()!=raw  # quality100 still cannot promise losslessness


@pytest.mark.parametrize('change',['asset','privacy'])
def test_current_sources_rechecked_after_last_codec(mounted,monkeypatch,change):
    e=mounted; _,pages,book,path=setup_book(e,2,with_image=True)
    body,_=request(e,book,path); original=codec.encode; calls=0
    def mutate(*args,**kwargs):
        nonlocal calls
        data=original(*args,**kwargs); calls+=1
        if calls==2:
            if change=='asset':
                e.assets.update_metadata(pages[0]['document']['panels'][0]['asset_id'], {'parameters':{'private_marker':'never echo'}})
            else:
                from app.source_privacy import review_source_privacy,content_digest
                review_source_privacy(e.chapter,None,'local-author','CLOUD_ALLOWED',e.chapter['version'],content_digest(e.chapter),e.root)
        return data
    monkeypatch.setattr(codec,'encode',mutate)
    response=e.client.post(path+'/export-page-archive',json=body)
    assert response.status_code in (409,422),response.text
    assert not response.content.startswith(b'PK') and 'never echo' not in response.text


def test_lossless_claim_requires_real_pixel_identity(monkeypatch):
    from app.experimental.comic_publication import PageArchiveIn
    source=Image.new('RGB',(320,640),(235,17,82)); png=io.BytesIO(); source.save(png,format='PNG')
    request=PageArchiveIn(expected_version=1,reading_direction='LTR',image_format='WEBP',loss_mode='LOSSLESS',quality=None)
    # Corrupt only the decoded verification image, never the source comparison.
    original_open=Image.open
    def corrupt_open(fp,*args,**kwargs):
        image=original_open(fp,*args,**kwargs)
        if image.format=='WEBP': image.load(); image.putpixel((0,0),(0,0,0))
        return image
    monkeypatch.setattr(Image,'open',corrupt_open)
    with pytest.raises(ValueError,match='LOSSLESS_MISMATCH'):
        codec.encode(png.getvalue(),320,640,request)
    source.close()



def test_codec_verification_rejects_geometry_before_decode(monkeypatch):
    from app.experimental.comic_publication import PageArchiveIn
    with Image.new('RGB',(320,640),'white') as source:
        png=io.BytesIO(); source.save(png,format='PNG')
    request=PageArchiveIn(expected_version=1,reading_direction='LTR',image_format='WEBP',loss_mode='LOSSLESS',quality=None)
    original_open=Image.open
    def wrong_geometry(fp,*args,**kwargs):
        image=original_open(fp,*args,**kwargs)
        if image.format=='WEBP':
            image._size=(100000,100000)
            def forbidden(*args,**kwargs): raise AssertionError('decode before geometry admission')
            image.load=forbidden
        return image
    monkeypatch.setattr(Image,'open',wrong_geometry)
    with pytest.raises(ValueError,match='CODEC_INVALID'):
        codec.encode(png.getvalue(),320,640,request)
