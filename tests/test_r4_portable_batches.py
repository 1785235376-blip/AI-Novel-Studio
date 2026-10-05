"""U14/U16 real File and opt-in actual PostgreSQL domain-authority contracts."""
import base64
from copy import deepcopy
import io
import json
import stat
import threading
import zipfile
import pytest
from fastapi import HTTPException
from app.experimental.portable_projects import PortableProjectsService, read_archive, LIMITS, MAX_MEMBER, MAX_MEMBERS, safe_document
from app.experimental.safe_batches import SafeBatchesService
from app.experimental.media import MediaService, batch_media_context
from app.experimental.reader_preflight import ReaderPreflightService
from app.experimental.writing_focus import WritingFocusService
from app.experimental.ux import ReadContext
from app.experimental.common import StaleSourceError
from app.services.v1_capability_service import CapabilityVersionConflict
from test_r3_media_support import rig, wav_bytes

FLAGS = 'portable_projects_v2,safe_batches_v2,reader_preflight_v2,cover_storyboard_generation,media_adapter_registry'

@pytest.fixture
def work(rig, monkeypatch):
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', FLAGS); monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'false')
    r = rig; r.ctx = ReadContext(r.nid, r.scope, r.actor)
    r.sources = WritingFocusService(r.store, r.novels, r.chapters)
    r.reader = ReaderPreflightService(r.store, r.novels, r.chapters, sources=r.sources, assets=r.assets)
    r.media = MediaService(r.store, r.novels, r.chapters, assets=r.assets, screenplays=r.screenplays)
    r.portable = PortableProjectsService(r.store, r.novels, r.chapters, sources=r.sources, assets=r.assets)
    r.batches = SafeBatchesService(r.store, r.novels, r.chapters, sources=r.sources, reader=r.reader, media=r.media)
    return r


def confirm(row): return {'expected_version': row['version'], 'snapshot_digest': row['snapshot_digest'], 'confirmed': True}
def version(row): return {'expected_version': row['version']}
def upload(data, name='portable.zip'): return {'filename': name, 'content_base64': base64.b64encode(data).decode()}
def add_media(r, missing=False):
    data = wav_bytes(); asset = r.assets.create(r.nid, 'synthetic.wav', base64.b64encode(data).decode(), 'audio/wav', 'audio')
    chapter = r.chapters.get(r.chapter['id']); doc = chapter['document']; doc['content'].append({'type': 'audio', 'attrs': {'asset_id': asset['id'], 'title': 'Synthetic audio'}})
    r.chapters.save(chapter['id'], {'version': chapter['version'], 'document': doc})
    if missing: (r.assets.root / (asset['id'] + '.bin')).unlink()
    return asset, data


def test_portable_real_round_trip_new_ids_missing_media_and_original_history(work):
    r=work; asset,_=add_media(r); history=deepcopy(r.chapters.history(r.chapter['id'])); original=deepcopy(r.chapters.get(r.chapter['id']))
    exported=r.portable.export(r.ctx, {'chapter_ids':[r.chapter['id']]})
    raw=r.portable.download(r.ctx,exported['id'],exported['version']); manifest,payloads=read_archive(raw)
    assert manifest['media'][0]['state']=='AVAILABLE' and list(payloads)==['a0001']
    assert str(r.root).encode() not in raw and asset['id'].encode() not in raw and r.nid.encode() not in raw
    preview=r.portable.preflight_import(r.ctx,upload(raw)); assert len(r.novels.list())==1
    restored=r.portable.restore(r.ctx,preview['id'],confirm(preview)); target=restored['target_id']
    assert target!=r.nid and restored['status']=='RESTORED'
    cid=restored['id_map']['chapters']['c0001']; aid=restored['id_map']['media']['a0001']
    assert cid!=r.chapter['id'] and aid!=asset['id']
    assert r.chapters.get(cid)['document']['content'][-1]['attrs']['asset_id']==aid
    assert r.assets.content(aid,actor_id=r.actor)==payloads['a0001']
    assert r.chapters.get(r.chapter['id'])==original and r.chapters.history(r.chapter['id'])==history
    with pytest.raises((ValueError,CapabilityVersionConflict)): r.portable.restore(r.ctx,preview['id'],confirm(preview))
    r.novels.delete(target)


def test_missing_media_retains_manuscript_and_explicit_digest_relink(work):
    r=work; asset,raw=add_media(r,True)
    exported=r.portable.export(r.ctx,{'chapter_ids':[r.chapter['id']]}); body=r.portable.download(r.ctx,exported['id'],1)
    manifest,_=read_archive(body); assert manifest['media'][0]['state']=='MISSING'; assert manifest['chapters'][0]['document']
    catalog=r.portable.catalog(r.ctx); assert catalog['missing'][0]['expected_sha256']==asset['sha256']
    history=r.chapters.history(r.chapter['id'])
    relink=r.portable.preflight_relink(r.ctx,{**upload(raw,'same-name.wav'),'missing_id':asset['id'],'chapter_ids':[r.chapter['id']],'kind':'audio'})
    assert relink['digest_matches']; result=r.portable.relink(r.ctx,relink['id'],confirm(relink))
    assert result['status']=='RELINKED'; new=result['id_map']['media'][asset['id']]
    assert new!=asset['id'] and r.assets.content(new,actor_id=r.actor)==raw
    assert len(r.chapters.history(r.chapter['id']))>len(history)
    assert r.assets.get(asset['id'])['sha256']==asset['sha256']


def test_relink_same_name_mismatch_requires_explicit_replace_and_stale_denied(work):
    r=work; asset,_=add_media(r,True)
    args={**upload(wav_bytes(sample=101),'synthetic.wav'),'missing_id':asset['id'],'chapter_ids':[r.chapter['id']],'kind':'audio'}
    row=r.portable.preflight_relink(r.ctx,args); assert not row['digest_matches']
    with pytest.raises(ValueError,match='EXPLICIT_REPLACEMENT'):r.portable.relink(r.ctx,row['id'],confirm(row))
    old=r.chapters.get(r.chapter['id']);r.chapters.save(old['id'],{'version':old['version'],'document':{'type':'doc','content':[{'type':'paragraph','content':[{'type':'text','text':'changed'}]}]}})
    with pytest.raises(StaleSourceError):r.portable.relink(r.ctx,row['id'],{**confirm(row),'accept_different_digest':True})


def test_cache_preview_cleanup_preserves_assets_history_trash_and_regenerates(work):
    r=work; asset,_=add_media(r); row=r.portable.export(r.ctx,{'chapter_ids':[r.chapter['id']]}); raw=r.portable.download(r.ctx,row['id'],1)
    before=r.chapters.history(r.chapter['id']); preview=r.portable.storage(r.ctx)
    assert {c['kind'] for c in preview['categories']}=={'MANUSCRIPT','ACCEPTED_ASSETS','HISTORY','TRASH','REPRODUCIBLE_CACHE','TEMPORARY_FAILED_FILES'}
    with pytest.raises(ValueError):r.portable.cleanup(r.ctx,{'record_ids':[asset['id']],'preview_digest':preview['preview_digest'],'confirmed':True})
    result=r.portable.cleanup(r.ctx,{'record_ids':[row['id']],'preview_digest':preview['preview_digest'],'confirmed':True})
    assert result['removed_cache_count']==1 and r.chapters.history(r.chapter['id'])==before
    assert r.assets.content(asset['id'])
    assert r.portable.download(r.ctx,row['id'],1)==raw


def archive(entries):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        for name,raw in entries: z.writestr(name,raw)
    return out.getvalue()

@pytest.mark.parametrize('name',['../escape','/absolute','media/../escape','media\\a0001.wav','https://host/a','config.json','media/a0001.svg','media/a0001.html','media/a0001.xml','media/a0001.gguf'])
def test_untrusted_members_cannot_escape_or_execute(name):
    with pytest.raises(ValueError): read_archive(archive([(name,b'evil')]))


def test_archive_symlink_duplicate_compression_bomb_size_member_limit_and_xml_html():
    symlink=zipfile.ZipInfo('manifest.json');symlink.create_system=3;symlink.external_attr=(stat.S_IFLNK|0o777)<<16
    with pytest.raises(ValueError):read_archive(archive([(symlink,b'/etc/passwd')]))
    with pytest.raises(ValueError):read_archive(archive([('manifest.json',b'{}'),('manifest.json',b'{}')]))
    with pytest.raises(ValueError):read_archive(archive([('manifest.json',b'{}')]+[(f'media/a{i:04d}.wav',b'x') for i in range(MAX_MEMBERS)]))
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED) as z:z.writestr('manifest.json',b' '*100000)
    with pytest.raises(ValueError,match='COMPRESSION'):read_archive(out.getvalue())
    with pytest.raises(ValueError):read_archive(archive([('media/a0001.wav',b'x'*(MAX_MEMBER+1))]))
    for text in (b'<!DOCTYPE x [<!ENTITY x SYSTEM "file:///etc/passwd">]><x>&x;</x>',b'<script>fetch("https://host")</script>'):
        with pytest.raises(ValueError):read_archive(archive([('manifest.json',text)]))
    for node in ({'type':'html','text':'<script>x</script>'},{'type':'image','attrs':{'src':'file:///private/path'}},{'type':'paragraph','attrs':{'onclick':'run()'}}):
        with pytest.raises(ValueError):safe_document({'type':'doc','content':[node]})


def test_digest_member_tamper_credentials_and_extra_fields_rejected(work):
    r=work;add_media(r);row=r.portable.export(r.ctx,{'chapter_ids':[r.chapter['id']]});raw=r.portable.download(r.ctx,row['id'],1)
    with zipfile.ZipFile(io.BytesIO(raw)) as z: entries=[(i.filename,z.read(i)) for i in z.infolist()]
    with pytest.raises(ValueError,match='DIGEST'):read_archive(archive([(n,b'tamper' if n.startswith('media/') else d) for n,d in entries]))
    manifest=json.loads(entries[0][1]);manifest['api_key']='fake-test-secret'
    with pytest.raises(ValueError,match='CREDENTIAL'):read_archive(archive([('manifest.json',json.dumps(manifest).encode())]))


def test_portable_actor_hidden_source_final_permission_and_new_project_no_overwrite(work):
    r=work;row=r.portable.export(r.ctx,{'chapter_ids':[r.chapter['id']]});other=ReadContext(r.nid,r.scope,'other')
    assert r.portable.records(other)['items']==[]
    with pytest.raises(FileNotFoundError):r.portable.download(other,row['id'],1)
    def denied():raise HTTPException(403,'revoked')
    with pytest.raises(HTTPException):r.portable.export(r.ctx,{'chapter_ids':[r.chapter['id']]},denied)
    source=r.chapters.get(r.chapter['id']);r.sources.chapter_reader=lambda ctx:[{**source,'hidden':True}]
    assert r.portable.records(r.ctx)['items']==[] and r.portable.catalog(r.ctx)['chapters']==[]


def batch(r,items):return r.batches.preflight(r.ctx,{'items':items})
def ready(r,row):return r.batches.confirm(r.ctx,row['id'],{**confirm(row),'budget_microusd':0})
def dispatch(r,row):return r.batches.dispatch(r.ctx,row['id'],version(row))


def test_batch_preflight_never_starts_confirm_not_dispatch_selected_exports_proof_and_skip(work):
    r=work;second=r.chapters.create(r.nid,{'title':'Do not include','content':'UNSELECTED_PRIVATE_TEXT'})
    row=batch(r,[{'kind':'EXPORT','chapter_ids':[r.chapter['id']],'format':'txt'},{'kind':'PROOF','chapter_ids':[r.chapter['id']]}])
    assert row['status']=='PREFLIGHT' and all(i['status']=='PENDING' for i in row['items'])
    with pytest.raises(ValueError):dispatch(r,row)
    row=ready(r,row);assert row['status']=='READY' and all(i['attempts']==0 for i in row['items'])
    row=dispatch(r,row);assert row['items'][0]['status']=='COMPLETED' and row['items'][1]['status']=='PENDING'
    raw,fmt,_=r.batches.download(r.ctx,row['id'],0);assert b'UNSELECTED_PRIVATE_TEXT' not in raw and fmt=='txt'
    row=dispatch(r,row);assert row['status']=='COMPLETED'
    skipped=batch(r,[{'kind':'EXPORT','chapter_ids':[r.chapter['id']],'format':'txt'}]);assert skipped['items'][0]['status']=='SKIPPED'
    assert ready(r,skipped)['status']=='COMPLETED'


def test_batch_failure_keeps_success_retry_only_failed_and_unknown_no_replay(work,monkeypatch):
    r=work;row=ready(r,batch(r,[{'kind':'EXPORT','chapter_ids':[r.chapter['id']]},{'kind':'PROOF','chapter_ids':[r.chapter['id']]}]));row=dispatch(r,row)
    original=r.reader.proof
    def fail(ctx):raise ValueError('synthetic failure')
    monkeypatch.setattr(r.reader,'proof',fail)
    with pytest.raises(ValueError):dispatch(r,row)
    row=r.batches.list_batches(r.ctx)['items'][0];assert row['status']=='PARTIAL' and row['items'][0]['attempts']==1
    retry=r.batches.retry_failed(r.ctx,row['id'],version(row));assert retry['status']=='PREFLIGHT' and retry['items'][0]['status']=='COMPLETED'
    monkeypatch.setattr(r.reader,'proof',original);done=dispatch(r,ready(r,retry));assert done['status']=='COMPLETED' and done['items'][0]['attempts']==1
    with r.store.transaction(r.nid,r.scope) as state:
        raw=state['collections'][r.batches.BATCHES][done['id']];raw['status']='RUNNING';raw['items'][1].update(status='RUNNING',claim='orphan')
    unknown=r.batches.list_batches(r.ctx)['items'][0];assert unknown['status']=='UNKNOWN'
    with pytest.raises(ValueError,match='UNKNOWN'):r.batches.retry_failed(r.ctx,unknown['id'],version(unknown))


def test_batch_source_permission_configuration_revocation_and_hidden_data(work):
    r=work;row=batch(r,[{'kind':'PROOF','chapter_ids':[r.chapter['id']]}]);r.reader.save_settings(r.ctx,{'expected_version':0,'rules':{'punctuation':False}})
    with pytest.raises(StaleSourceError):ready(r,row)
    row=batch(r,[{'kind':'EXPORT','chapter_ids':[r.chapter['id']]}]);row=ready(r,row)
    def denied():raise HTTPException(403,'revoked')
    with pytest.raises(HTTPException):r.batches.dispatch(r.ctx,row['id'],version(row),denied)
    other=ReadContext(r.nid,r.scope,'other');assert r.batches.list_batches(other)['items']==[]
    source=r.chapters.get(r.chapter['id']);r.sources.chapter_reader=lambda ctx:[{**source,'hidden':True}]
    assert r.batches.list_batches(r.ctx)['items']==[]
    with pytest.raises(FileNotFoundError):dispatch(r,row)


def test_batch_stop_during_stage_drops_late_result_and_blocks_next(work,monkeypatch):
    r=work;row=ready(r,batch(r,[{'kind':'EXPORT','chapter_ids':[r.chapter['id']]},{'kind':'PROOF','chapter_ids':[r.chapter['id']]}]));original=r.novels.export_snapshot_result
    def stopped(snapshot,format,**kw):
        current=r.batches._owned(r.ctx,row['id']);r.batches.stop(r.ctx,row['id'],version(current));return original(snapshot,format)
    monkeypatch.setattr(r.novels,'export_snapshot_result',stopped)
    with pytest.raises(ValueError,match='STOPPED'):dispatch(r,row)
    stopped=r.batches.list_batches(r.ctx)['items'][0];assert stopped['status']=='CANCELLED' and all(i['status']=='CANCELLED' for i in stopped['items'])
    with pytest.raises(ValueError):r.batches.download(r.ctx,row['id'],0)


def test_synthetic_media_original_executor_and_legacy_bypass_denied(work):
    r=work;brief=r.media.create_cover(r.nid,r.scope,r.actor,{'title':'Synthetic cover','chapter_ids':[r.chapter['id']]})
    row=ready(r,batch(r,[{'kind':'SYNTHETIC_MEDIA','brief_id':brief['id'],'expected_brief_version':brief['version']}]))
    done=dispatch(r,row);assert done['status']=='COMPLETED';proposal=done['items'][0]['proposals'][0]
    assert proposal['verification']=='MOCK_ONLY' and proposal['media']['width']==16
    internal=r.batches._owned(r.ctx,done['id']);task_id=internal['items'][0]['task_id']
    assert r.media.tasks(r.nid,r.scope)==[] and r.media.proposals(r.nid,r.scope)==[]
    for action in ('execute','retry','approve'):
        with pytest.raises(FileNotFoundError):
            if action=='execute':r.media.execute(r.nid,r.scope,r.actor,task_id,1)
            elif action=='retry':r.media.transition(r.nid,r.scope,r.actor,task_id,'retry',1)
            else:r.media.review(r.nid,r.scope,r.actor,proposal['id'],'approve',1)
    raw,mime=r.batches.preview_media(r.ctx,done['id'],proposal['id']);assert raw.startswith(b'\x89PNG') and mime=='image/png'
    approved=r.batches.approve_media(r.ctx,done['id'],{**confirm(done),'proposal_id':proposal['id'],'proposal_version':proposal['version']})
    assert approved['items'][0]['proposals'][0]['status']=='APPROVED'
    assert len(r.assets.list(r.nid))==1  # explicit original review publishes the accepted asset
    assert len(r.assets.list(r.nid,actor_id=r.actor))==1


def test_batch_off_v1_no_callbacks_or_child_content(work,monkeypatch):
    r=work;row=ready(r,batch(r,[{'kind':'PROOF','chapter_ids':[r.chapter['id']]}]))
    monkeypatch.setenv('V1_ACCEPTANCE_MODE','true')
    with pytest.raises(HTTPException):dispatch(r,row)
    assert r.batches._owned(r.ctx,row['id'])['items'][0]['attempts']==0


def test_portable_missing_restoration_readable_and_asset_escape_fails(work):
    r=work;asset,_=add_media(r,True);exported=r.portable.export(r.ctx,{'chapter_ids':[r.chapter['id']]})
    imported=r.portable.preflight_import(r.ctx,upload(r.portable.download(r.ctx,exported['id'],1)));restored=r.portable.restore(r.ctx,imported['id'],confirm(imported))
    cid=restored['id_map']['chapters']['c0001'];chapter=r.chapters.get(cid)
    assert 'Alice' in chapter['content'];missing_id=chapter['document']['content'][-1]['attrs']['asset_id'];assert missing_id.startswith('missing-')
    r.novels.delete(restored['target_id'])
    # A symlink cannot make an unrelated host file into a portable member.
    target=r.root/'never-package';target.write_bytes(b'PRIVATE_HOST_BYTES');(r.assets.root/(asset['id']+'.bin')).symlink_to(target)
    row=r.portable.export(r.ctx,{'chapter_ids':[r.chapter['id']]});raw=r.portable.download(r.ctx,row['id'],1)
    assert b'PRIVATE_HOST_BYTES' not in raw and row['media'][0]['state']=='MISSING'


def test_portable_no_cleanup_on_stale_preview_and_does_not_touch_failed_inputs(work):
    r=work;row=r.portable.export(r.ctx,{'chapter_ids':[r.chapter['id']]});preview=r.portable.storage(r.ctx)
    imported=r.portable.preflight_import(r.ctx,upload(r.portable.download(r.ctx,row['id'],1)))
    assert imported['id'] not in {i['id'] for i in r.portable.storage(r.ctx)['eligible']}
    r.portable.export(r.ctx,{'chapter_ids':[r.chapter['id']]})
    with pytest.raises(StaleSourceError):r.portable.cleanup(r.ctx,{'record_ids':[row['id']],'preview_digest':preview['preview_digest'],'confirmed':True})
    assert r.portable._file(r.ctx,imported['id']).exists() and r.portable._file(r.ctx,row['id']).exists()


def test_batch_budget_title_and_privacy_changes_invalidate_confirmation(work):
    from app.source_privacy import review_source_privacy,content_digest
    r=work;row=batch(r,[{'kind':'EXPORT','chapter_ids':[r.chapter['id']]}]);r.novels.update(r.nid,{'title':'Changed project title'})
    with pytest.raises(StaleSourceError):ready(r,row)
    row=batch(r,[{'kind':'PROOF','chapter_ids':[r.chapter['id']]}]);source=r.chapters.get(r.chapter['id'])
    review_source_privacy(source,None,r.actor,'CLOUD_ALLOWED',source['version'],content_digest(source),r.root)
    with pytest.raises(StaleSourceError):ready(r,row)


def test_batch_real_adapter_declaration_not_trusted_and_no_auto_models(work):
    from app.experimental.media import AdapterDefinition
    r=work
    class Unsafe:
        definition=AdapterDefinition(adapter_id='pretend-local',family='Declared local',modality='IMAGE',operations=['cover_generation'],state='CONTRACT_VERIFIED',local=True,runnable=True)
        def generate(self,request):raise AssertionError('must never execute')
    r.media.registry.register(Unsafe());brief=r.media.create_cover(r.nid,r.scope,r.actor,{'title':'Synthetic','chapter_ids':[r.chapter['id']]})
    with pytest.raises(ValueError,match='REQUIRES_ORIGINAL_BROKER'):batch(r,[{'kind':'SYNTHETIC_MEDIA','brief_id':brief['id'],'expected_brief_version':1,'adapter_id':'pretend-local'}])
    assert r.batches.list_batches(r.ctx)['items']==[] and r.media.tasks(r.nid,r.scope)==[]


def test_batch_claim_prevents_concurrent_double_dispatch(work,monkeypatch):
    r=work;row=ready(r,batch(r,[{'kind':'PROOF','chapter_ids':[r.chapter['id']]}]));entered=threading.Event();release=threading.Event();original=r.reader.proof;results=[]
    def blocked(ctx):entered.set();assert release.wait(5);return original(ctx)
    monkeypatch.setattr(r.reader,'proof',blocked)
    def worker():results.append(dispatch(r,row))
    t=threading.Thread(target=worker);t.start();assert entered.wait(5)
    try:
        with pytest.raises(CapabilityVersionConflict):dispatch(r,row)
    finally:release.set();t.join(5)
    assert len(results)==1 and results[0]['status']=='COMPLETED' and results[0]['items'][0]['attempts']==1


def test_media_flag_revocation_hides_only_dependent_batch_and_export_cache(work,monkeypatch):
    r=work;asset,_=add_media(r);portable=r.portable.export(r.ctx,{'chapter_ids':[r.chapter['id']]})
    # A resource moving to another branch hides its dependent portable record.
    meta=r.assets.get(asset['id']);meta['branch_id']='private-other';r.assets._write_meta(meta)
    assert r.portable.records(r.ctx)['items']==[]
    with pytest.raises(FileNotFoundError):r.portable.download(r.ctx,portable['id'],1)
    # An unrelated proof batch remains available while optional media is off.
    proof=batch(r,[{'kind':'PROOF','chapter_ids':[r.chapter['id']]}])
    brief=r.media.create_cover(r.nid,r.scope,r.actor,{'title':'Hidden optional media','chapter_ids':[r.chapter['id']]})
    media=batch(r,[{'kind':'SYNTHETIC_MEDIA','brief_id':brief['id'],'expected_brief_version':1}])
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','portable_projects_v2,safe_batches_v2,reader_preflight_v2')
    rows=r.batches.list_batches(r.ctx)['items'];assert [row['id'] for row in rows]==[proof['id']]
    assert media['id'] not in json.dumps(rows)


def test_proof_selection_uses_unicode_range_and_does_not_edit(work):
    r=work;cid=r.chapter['id'];current=r.chapters.get(cid)
    r.chapters.save(cid,{'version':current['version'],'document':{'type':'doc','content':[{'type':'paragraph','content':[{'type':'text','text':'🙂 the the 甲！！'}]}]}})
    row=dispatch(r,ready(r,batch(r,[{'kind':'PROOF','chapter_ids':[cid],'start':2,'end':9}])))
    assert len(row['items'][0]['findings'])==1 and row['items'][0]['findings'][0]['quote']=='the the'
    assert row['items'][0]['source_versions'][cid]==2 and r.chapters.get(cid)['version']==2


def test_media_original_promotion_recovery_never_duplicates_published_asset(work,monkeypatch):
    r=work;brief=r.media.create_cover(r.nid,r.scope,r.actor,{'title':'Synthetic recoverable','chapter_ids':[r.chapter['id']]})
    done=dispatch(r,ready(r,batch(r,[{'kind':'SYNTHETIC_MEDIA','brief_id':brief['id'],'expected_brief_version':1}])));proposal=done['items'][0]['proposals'][0]
    original=r.assets.promote_owned
    def interrupted(*args,**kwargs):original(*args,**kwargs);raise OSError('synthetic receipt write interruption')
    monkeypatch.setattr(r.assets,'promote_owned',interrupted)
    with pytest.raises(OSError):r.batches.approve_media(r.ctx,done['id'],{**confirm(done),'proposal_id':proposal['id'],'proposal_version':proposal['version']})
    assert len(r.assets.list(r.nid,actor_id=r.actor))==1
    recovered=r.batches.list_batches(r.ctx)['items'][0];proposal=recovered['items'][0]['proposals'][0];assert proposal['status']=='APPROVING'
    monkeypatch.setattr(r.assets,'promote_owned',original)
    final=r.batches.approve_media(r.ctx,recovered['id'],{**confirm(recovered),'proposal_id':proposal['id'],'proposal_version':proposal['version']})
    assert final['items'][0]['proposals'][0]['status']=='APPROVED' and len(r.assets.list(r.nid))==1


def test_batch_media_stop_after_local_adapter_discards_candidates(work,monkeypatch):
    r=work;brief=r.media.create_cover(r.nid,r.scope,r.actor,{'title':'Synthetic stopped','chapter_ids':[r.chapter['id']]})
    row=ready(r,batch(r,[{'kind':'SYNTHETIC_MEDIA','brief_id':brief['id'],'expected_brief_version':1}]))
    adapter=r.media.registry.resolve('mock-image-v1','cover_generation');original=adapter.generate
    def stopped(request):
        output=original(request);current=r.batches._owned(r.ctx,row['id']);r.batches.stop(r.ctx,row['id'],version(current));return output
    monkeypatch.setattr(adapter,'generate',stopped)
    with pytest.raises((ValueError,FileNotFoundError)):dispatch(r,row)
    raw=r.store.read(r.nid,r.scope);assert raw['collections'][r.batches.BATCHES][row['id']]['status']=='CANCELLED'
    assert not raw['collections'].get(r.media.PROPOSALS) and r.assets.list(r.nid)==[]


def test_xml_and_html_disguised_as_digest_valid_media_never_decode_or_execute(work):
    import hashlib
    r=work;add_media(r);row=r.portable.export(r.ctx,{'chapter_ids':[r.chapter['id']]});raw=r.portable.download(r.ctx,row['id'],1)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:manifest=json.loads(z.read('manifest.json'))
    for hostile in [b'<!DOCTYPE x [<!ENTITY x SYSTEM "file:///etc/passwd">]><x>&x;</x>',b'<html><script>fetch("https://host")</script></html>']:
        media=manifest['media'][0];media['size']=len(hostile);media['sha256']=hashlib.sha256(hostile).hexdigest()
        with pytest.raises(ValueError):read_archive(archive([('manifest.json',json.dumps(manifest).encode()),(media['path'],hostile)]))


def test_media_current_reference_bytes_are_required_at_preflight_and_dispatch(work):
    r=work;raw=wav_bytes();asset=r.assets.create(r.nid,'synthetic.wav',base64.b64encode(raw).decode(),'audio/wav','audio')
    brief=r.media.create_cover(r.nid,r.scope,r.actor,{'title':'Synthetic referenced','chapter_ids':[r.chapter['id']],'reference_asset_ids':[asset['id']]})
    body=[{'kind':'SYNTHETIC_MEDIA','brief_id':brief['id'],'expected_brief_version':1}]
    row=ready(r,batch(r,body));(r.assets.root/(asset['id']+'.bin')).unlink()
    with pytest.raises(FileNotFoundError):dispatch(r,row)
    with pytest.raises(FileNotFoundError):batch(r,body)
    state=r.store.read(r.nid,r.scope)['collections'];assert not state.get(r.media.TASKS) and state[r.batches.BATCHES][row['id']]['items'][0]['attempts']==0
