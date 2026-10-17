import { exactHandoffAsset, type TimelineAssetHandoff } from './StudioTimelineAssetHandoff';
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { ApiError, apiErrorView, type Asset } from '../api';
import type { CreativeClient } from './client';
import { documentInput, type CreativeDocument } from './types';
import type { StudioClient, StudioAsset } from './studioClient';
import type { ProductionProvider, ProductionJob } from './studioProductionClient';
import type { StudioProductionClient } from './studioProductionClient';
import { mediaProviderKey } from './useStudioMediaExecution';
import { maskSha256 } from './studioManualMaskContract';
import type { StudioTimelineRow } from './studioTimelineTypes';
import { storyboardInvalid, type StoryboardReceipt, type DirectorAdvice, type StoryboardImageRequest, type StoryboardVideoRequest, type StoryboardTimelineDraft } from './studioStoryboardContract';
import { sameStoryboardValue, type StoryboardTimelineCreation, type StoryboardTimelineCreateInput, type StoryboardAdoptionRequest } from './studioStoryboardPipelineContract';

export type StoryboardProductionProps = { document: CreativeDocument; client: CreativeClient; studio: StudioClient; production: StudioProductionClient;
  exactImage?: TimelineAssetHandoff; ownsOperation?: () => boolean; active: boolean; editable: boolean; busy: boolean; isBusy: () => boolean; isCurrent: () => boolean; perform: <T>(work: () => Promise<T>) => Promise<T>;
  onDocument: (document: CreativeDocument) => void; onReceipt?: (receipt: StoryboardReceipt | undefined) => void; onDenied: () => void; onDirtyChange: (dirty: boolean) => void };
/** Original document/asset/job ownership stays in clients. The view owns no requests or grants. */
export function useStoryboardProductionController(props: StoryboardProductionProps) {
  const [receipt, setReceipt] = useState<StoryboardReceipt>(), [advice, setAdvice] = useState<DirectorAdvice>(), [assets, setAssets] = useState<StudioAsset[]>([]), [providers, setProviders] = useState<ProductionProvider[]>([]);
  const [selectedId, setSelectedId] = useState(''), [assetId, setAssetId] = useState(''), [providerId, setProviderId] = useState('');
  const [operation, setOperation] = useState<'m5.image.t2i' | 'm5.image.i2i' | 'm5.image.reference'>('m5.image.t2i');
  const [confirmation, setConfirmation] = useState(''), [timelineShots, setTimelineShots] = useState<string[]>([]), [prepared, setPrepared] = useState<StoryboardImageRequest | StoryboardVideoRequest>(), [timeline, setTimeline] = useState<StoryboardTimelineDraft>();
  const [videoOperation, setVideoOperation] = useState<'m7.video.t2v' | 'm7.video.i2v'>('m7.video.t2v'), [videoProvider, setVideoProvider] = useState(''), [videoJobs, setVideoJobs] = useState<ProductionJob[]>([]), [videoJobId, setVideoJobId] = useState('');
  const [creation, setCreation] = useState<StoryboardTimelineCreation>(), [mediaDirty, setMediaDirty] = useState(false);
  const creationAttempt = useRef<{ receipt: StoryboardReceipt; body: StoryboardTimelineCreateInput }>();
  const [adoptionUnknown, setAdoptionUnknown] = useState(false), [clipId, setClipId] = useState(''), [rangeIn, setRangeIn] = useState('0'), [rangeOut, setRangeOut] = useState(''), [includeAudio, setIncludeAudio] = useState(false), [adoptionConsent, setAdoptionConsent] = useState('');
  const adoptionAttempt = useRef<{ document_id: string; shot_id: string; timeline_id: string; body: StoryboardAdoptionRequest }>();
  const [loading, setLoading] = useState(''), [error, setError] = useState(''), [uncertain, setUncertain] = useState(false);
  const [preview, setPreview] = useState<{ asset: StudioAsset; blob: Blob; binding: string }>();
  const [timelineUnknown, setTimelineUnknown] = useState(false), [timelineRecovery, setTimelineRecovery] = useState<StudioTimelineRow[]>([]);
  const [exactSource, setExactSource] = useState<StudioAsset>(), [exactDone, setExactDone] = useState(false);
  const exactConsumed = useRef(false);
  const exactAttempt = useRef<{ document: CreativeDocument; receipt: StoryboardReceipt; shot: import('./studioStoryboardContract').StoryboardShot; pin: import('./studioStoryboardContract').StoryboardImage }>();
  const exactEpoch = useRef(0), exactOrigin = useRef<unknown[]>([]);
  const identity = [props.client, props.studio, props.exactImage, props.exactImage?.id, props.exactImage?.reference.asset_id, props.exactImage?.reference.version, props.exactImage?.reference.digest, props.document.id, props.document.version, props.active, props.editable, props.exactImage ? props.isCurrent() : true, !!props.busy && !props.ownsOperation?.()];
  if (identity.some((item, index) => item !== exactOrigin.current[index])) { exactEpoch.current++; exactOrigin.current = identity; }
  const exactRenderGeneration = exactEpoch.current;
  const latest = useRef(props); latest.current = props; const owner = useRef(props.client), alive = useRef(true), slot = useRef(false), epoch = useRef(0), receiptRef = useRef(receipt); receiptRef.current = receipt;
  const current = () => alive.current && latest.current.active && owner.current === latest.current.client && latest.current.isCurrent();
  const stamp = () => JSON.stringify([latest.current.document.id, latest.current.document.version]);
  const fresh = !!receipt && receipt.document_snapshot.id === props.document.id && receipt.document_snapshot.version === props.document.version;
  const locked = !current() || props.busy || props.isBusy() || !!loading;
  const selected = fresh ? receipt.shots.find(shot => shot.shot_id === selectedId) : undefined;
  const previewBinding = JSON.stringify([props.document.id, props.document.version, selectedId, selected?.image_asset, selected?.video_result?.asset]);
  const previewBindingRef = useRef(previewBinding); previewBindingRef.current = previewBinding;
  const previewRef = useRef(preview); previewRef.current = preview;
  const previewCurrent = useCallback(() => alive.current && latest.current.active && owner.current === latest.current.client && latest.current.isCurrent() && previewRef.current?.binding === previewBindingRef.current, []);
  const previewDownload = useCallback(async (asset: Asset) => { const value = previewRef.current; if (!previewCurrent() || !value || asset.id !== value.asset.id || asset.sha256 !== value.asset.sha256) storyboardInvalid(); return value.blob; }, [previewCurrent]);
  const approvalKey = fresh ? JSON.stringify([receipt.document_snapshot, receipt.content_digest]) : '';
  const preparedCurrent = () => current() && latest.current.editable && !!prepared && receiptRef.current?.document_snapshot.version === latest.current.document.version && JSON.stringify(prepared.shot_pin.document_snapshot) === JSON.stringify(receiptRef.current?.document_snapshot)
    && !!receiptRef.current?.shots.some(shot => shot.shot_id === prepared.shot_pin.shot_id && shot.shot_version === prepared.shot_pin.shot_version && shot.shot_digest === prepared.shot_pin.shot_digest);
  const run = async <T,>(kind: string, work: () => Promise<T>, accept: (value: T) => void, mutation = false) => {
    if (props.exactImage && exactRenderGeneration !== exactEpoch.current || !current() || slot.current || latest.current.busy || latest.current.isBusy() || mutation && (!latest.current.editable || uncertain)) return;
    slot.current = true; const ticket = ++epoch.current, captured = stamp(), exactGeneration = exactEpoch.current; const stillOwned = () => !props.exactImage || exactGeneration === exactEpoch.current; setLoading(kind); setError('');
    try { const value = await latest.current.perform(work); if (current() && stillOwned() && epoch.current === ticket && captured === stamp()) accept(value); }
    catch (reason) { if (current() && stillOwned() && epoch.current === ticket && captured === stamp()) { setError(apiErrorView(reason, '操作未完成，请读取原版本核对。').message); setConfirmation('');
      if (kind === 'read' || ['preview', 'request'].includes(kind) && reason instanceof ApiError && (reason.status === 409 || reason.status === 200 && reason.problem.code === 'STUDIO_RESPONSE_INVALID')) { setReceipt(undefined); setAdvice(undefined); setPreview(undefined); setPrepared(undefined); setTimeline(undefined); setUncertain(true); }
      if (reason instanceof ApiError && [401, 403].includes(reason.status)) latest.current.onDenied(); else if (mutation && (!(reason instanceof ApiError) || reason.problem.code === 'STUDIO_RESPONSE_INVALID' || reason.status === 0 || reason.status >= 500 || [408, 409, 425, 429].includes(reason.status))) { setUncertain(true); if (kind === 'timeline') setTimelineUnknown(true); if (kind === 'adoption') setAdoptionUnknown(true); }
      else if (mutation && reason instanceof ApiError && reason.status >= 400 && reason.status < 500) { if (kind === 'timeline') creationAttempt.current = undefined; if (kind === 'adoption') adoptionAttempt.current = undefined; }
    } }
    finally { slot.current = false; if (alive.current && epoch.current === ticket) setLoading(''); }
  };
  async function refreshed(next: StoryboardReceipt) { if (!current() || stamp() !== JSON.stringify([props.document.id, props.document.version])) storyboardInvalid(); const document = await props.client.get(next.document_snapshot.id); if (document.version !== next.document_snapshot.version || document.id !== next.document_snapshot.id || document.mode !== 'STORYBOARD') storyboardInvalid(); return { receipt: next, document }; }
  const adopt = (value: { receipt: StoryboardReceipt; document: CreativeDocument }) => { setReceipt(value.receipt); setConfirmation(''); setPrepared(undefined); setTimeline(undefined); setUncertain(false); latest.current.onDocument(value.document); };
  const read = () => { if (prepared || props.exactImage && exactAttempt.current) return; void run<DirectorAdvice | StoryboardReceipt>('read', () => props.document.mode === 'DIRECTOR' ? props.client.directorAdvice(props.document.id) : props.client.storyboardGet(props.document.id), value => {
    if (value.document_snapshot.id !== props.document.id || value.document_snapshot.version !== props.document.version) { setReceipt(undefined); setAdvice(undefined); setUncertain(true); setError('服务端文档版本已变化，请先重新读取原创作文档。'); return; }
    setUncertain(false); setConfirmation(''); setPrepared(undefined); setTimeline(undefined); if (value.contract === 'studio-director-advice/1') setAdvice(value); else { setReceipt(value); setSelectedId(props.exactImage ? '' : value.shots[0]?.shot_id || ''); setExactSource(undefined); }
  }); };
  const loadResources = () => { const captured = stamp(); void run('resources', async () => { const assets = await props.studio.assets(); if (!current() || captured !== stamp()) storyboardInvalid(); return { assets, providers: await props.production.providers() }; }, value => { setAssets(value.assets.items.filter(asset => ['image', 'video'].includes(asset.kind) && !asset.deleted_at)); setProviders(value.providers.filter(provider => provider.local && ['m5.image.t2i', 'm5.image.i2i', 'm5.image.reference', 'm7.video.t2v', 'm7.video.i2v'].includes(provider.operation_id))); setAssetId(''); setProviderId(''); setVideoProvider(''); }); };
  const loadMediaPreview = (kind: 'image' | 'video') => { const pin = kind === 'video' ? selected?.video_result?.asset : selected?.image_asset; if (!pin || prepared) return; const binding = previewBinding; setPreview(undefined);
    void run('preview', async () => { const asset = await props.studio.asset(pin.asset_id); if (asset.id !== pin.asset_id || asset.version !== pin.version || asset.sha256 !== pin.digest || asset.kind !== kind || !asset.media_type.startsWith(`${kind}/`) || asset.deleted_at || asset.size < 1 || asset.size > 64 * 1024 * 1024) storyboardInvalid();
      if (!current() || binding !== previewBindingRef.current) storyboardInvalid(); const blob = await props.studio.download(pin.asset_id); if (blob.size !== asset.size || blob.type !== asset.media_type || await maskSha256(new Uint8Array(await blob.arrayBuffer())) !== pin.digest) storyboardInvalid(); return { asset, blob, binding };
    }, value => { if (binding === previewBindingRef.current) setPreview(value); }); };
  const loadPreview = () => loadMediaPreview('image');
  const loadVideoPreview = () => loadMediaPreview('video');
  const approve = () => { if (!receipt || !fresh || confirmation !== approvalKey) return; void run('approve', () => props.client.storyboardApprove(receipt).then(refreshed), adopt, true); };
  const bind = () => { const asset = assets.find(asset => asset.id === assetId && asset.kind === 'image'); if (!receipt || !selected || !asset || !fresh) return; void run('bind', () => props.client.storyboardBindImage(receipt, selected, { asset_id: asset.id, version: asset.version, digest: asset.sha256, kind: 'image' }).then(refreshed), adopt, true); };
  // The incoming reference is session-only. All writes stay with the original image-binding owner.
  const exactGuard = (generation: number) => current() && exactEpoch.current === generation && latest.current.editable && (!(latest.current.busy || latest.current.isBusy()) || latest.current.ownsOperation?.() === true);
  const inspectExactImage = () => {
    const intent = props.exactImage; if (!intent || exactAttempt.current || exactDone || exactRenderGeneration !== exactEpoch.current || !current() || !latest.current.editable || latest.current.busy || latest.current.isBusy() || slot.current) return;
    const generation = exactEpoch.current; setExactSource(undefined);
    void run('exact-source', async () => { const asset = await intent.readAsset();
      if (!exactGuard(generation) || !exactHandoffAsset(asset, intent.reference) || asset.kind !== 'image' || !asset.media_type.startsWith('image/') || asset.manual_mask) storyboardInvalid();
      return asset;
    }, setExactSource);
  };
  const sameTarget = (before: StoryboardReceipt, after: StoryboardReceipt) => sameStoryboardValue(before.document_snapshot, after.document_snapshot)
    && before.content_digest === after.content_digest && sameStoryboardValue(before.director_sources, after.director_sources) && sameStoryboardValue(before.shots, after.shots) && before.approved === after.approved;
  const bindingMatches = (next: StoryboardReceipt, attempt: NonNullable<typeof exactAttempt.current>) => {
    const bound = next.shots.find(row => row.shot_id === attempt.shot.shot_id);
    return next.document_snapshot.id === attempt.receipt.document_snapshot.id && next.document_snapshot.version === attempt.receipt.document_snapshot.version + 1
      && !next.approved && sameStoryboardValue(next.director_sources, attempt.receipt.director_sources) && sameStoryboardValue(next.shots, attempt.receipt.shots.map(row => row.shot_id === attempt.shot.shot_id ? { ...row, image_asset: attempt.pin } : row)) && !!bound && bound.shot_version === attempt.shot.shot_version && bound.shot_digest === attempt.shot.shot_digest
      && sameStoryboardValue(bound.shot, attempt.shot.shot) && sameStoryboardValue(bound.image_asset, attempt.pin);
  };
  const bindExactImage = () => {
    const intent = props.exactImage;
    if (exactRenderGeneration !== exactEpoch.current || !current() || !intent || !receipt || !selected || !fresh || !exactSource || !exactHandoffAsset(exactSource, intent.reference) || exactAttempt.current || exactConsumed.current || exactDone || uncertain || locked || !props.editable) return;
    const generation = exactEpoch.current, original = structuredClone(receipt), shot = structuredClone(selected), originalDocument = structuredClone(props.document);
    if (!sameStoryboardValue([...originalDocument.shots].sort((a, b) => a.number - b.number), original.shots.map(row => row.shot))) { setError('原文档与分镜回执内容不一致，请关闭后重新核对。'); setExactSource(undefined); return; }
    const pin = { asset_id: intent.reference.asset_id, version: intent.reference.version, digest: intent.reference.digest, kind: 'image' as const };
    void run('exact-bind', async () => {
      let postReturned = false;
      try {
        const source = await intent.readAsset();
        if (!exactGuard(generation)) storyboardInvalid();
        if (!exactHandoffAsset(source, pin) || source.kind !== 'image' || !source.media_type.startsWith('image/') || source.manual_mask) storyboardInvalid();
        const target = await props.client.storyboardGet(original.document_snapshot.id);
        if (!exactGuard(generation) || !sameTarget(original, target)) storyboardInvalid();
        // No await between this final authority check and the single original-owner POST.
        if (!exactGuard(generation)) storyboardInvalid();
        const attempt = { document: originalDocument, receipt: original, shot, pin }; exactAttempt.current = attempt;
        const next = await props.client.storyboardBindImage(original, shot, pin); postReturned = true;
        if (!exactGuard(generation) || !bindingMatches(next, attempt)) storyboardInvalid();
        const value = await refreshed(next);
        if (!exactGuard(generation) || !sameStoryboardValue(documentInput(value.document), documentInput(originalDocument)) || !sameStoryboardValue(value.document.source_documents, originalDocument.source_documents) || !sameStoryboardValue(value.document.source_evidence, originalDocument.source_evidence) || !sameStoryboardValue([...value.document.shots].sort((a, b) => a.number - b.number), next.shots.map(row => row.shot))) storyboardInvalid();
        return value;
      } catch (reason) {
        if (exactGuard(generation)) {
          setExactSource(undefined);
          if (exactAttempt.current && (postReturned || !(reason instanceof ApiError && reason.status >= 400 && reason.status < 500 && ![408, 425, 429].includes(reason.status)))) setUncertain(true);
          else { exactAttempt.current = undefined; setReceipt(undefined); setSelectedId(''); }
        }
        throw reason;
      }
    }, value => { exactConsumed.current = true; exactAttempt.current = undefined; setExactDone(true); setExactSource(undefined); adopt(value); });
  };
  const inspectExactAttempt = () => {
    const attempt = exactAttempt.current; if (!props.exactImage || !attempt) return;
    const generation = exactEpoch.current;
    void run('exact-reconcile', async () => {
      const next = await props.client.storyboardGet(attempt.receipt.document_snapshot.id);
      if (!exactGuard(generation)) storyboardInvalid();
      // A matching observation is not attributed to this request: the owner has no request receipt.
      if (!sameTarget(attempt.receipt, next) && !bindingMatches(next, attempt)) storyboardInvalid();
      const value = await refreshed(next);
      if (!exactGuard(generation) || !sameStoryboardValue(documentInput(value.document), documentInput(attempt.document)) || !sameStoryboardValue(value.document.source_documents, attempt.document.source_documents) || !sameStoryboardValue(value.document.source_evidence, attempt.document.source_evidence) || !sameStoryboardValue([...value.document.shots].sort((a, b) => a.number - b.number), next.shots.map(row => row.shot))) storyboardInvalid();
      return { ...value, observed: bindingMatches(next, attempt) };
    }, value => { setError(value.observed ? '已观察原文档当前版本含此绑定；无法确认是否由本次请求保存。结果仍待核对，不会重发。' : '已观察原文档仍为原版本；先前请求仍可能完成。结果仍待核对，不会重发。'); });
  };
  const prepareImage = () => { const provider = providers.find(provider => mediaProviderKey(provider) === providerId && provider.operation_id === operation); if (!receipt || !selected || !fresh || !provider) return;
    void run('request', () => props.client.storyboardImageRequest(receipt, selected, operation, provider.provider_id, provider.model_id, crypto.randomUUID(), {}), value => { setPrepared(value); setConfirmation(''); }); };
  const matchingJob = (job: ProductionJob, board = receiptRef.current) => { const pin = job.command?.storyboard_shot; return !!board && job.owner === 'video' && job.status === 'APPROVED' && !!job.receipt_digest && !!job.approved_asset_version && job.output_candidate?.kind === 'video' && !!pin && pin.document_snapshot.id === board.document_snapshot.id && pin.document_snapshot.version <= board.document_snapshot.version && board.shots.some(shot => shot.shot_id === pin.shot_id && shot.shot_version === pin.shot_version && shot.shot_digest === pin.shot_digest); };
  const loadVideoJobs = () => void run('video-jobs', () => props.production.list(), value => { setVideoJobs(value.filter(job => matchingJob(job))); setVideoJobId(''); });
  const observeJob = (job: ProductionJob) => { if (current() && matchingJob(job)) setVideoJobs(rows => [job, ...rows.filter(row => row.id !== job.id)]); };
  const prepareVideo = () => { const provider = providers.find(provider => mediaProviderKey(provider) === videoProvider && provider.operation_id === videoOperation); if (!receipt?.approved || !selected || !fresh || !provider || !props.client.storyboardVideoRequest) return;
    void run('request', () => props.client.storyboardVideoRequest(receipt, selected, videoOperation, provider.provider_id, provider.model_id, crypto.randomUUID(), {}), value => { setPrepared(value); setConfirmation(''); }); };
  const bindVideo = () => { const old = videoJobs.find(job => job.id === videoJobId && job.command?.storyboard_shot?.shot_id === selectedId); if (!receipt || !selected || !fresh || !old || !matchingJob(old) || prepared || !props.client.storyboardBindVideo) return; const captured = stamp();
    void run('video-bind', async () => { const job = await props.production.get('video', old.id); if (!current() || captured !== stamp()) storyboardInvalid(); if (!matchingJob(job) || job.version !== old.version || job.request_digest !== old.request_digest || job.receipt_digest !== old.receipt_digest || !sameStoryboardValue(job.command?.storyboard_shot, old.command?.storyboard_shot) || !job.output_candidate || !job.approved_asset_version || !job.receipt_digest || !job.command?.storyboard_shot) storyboardInvalid();
      const asset = await props.studio.asset(job.output_candidate.id); if (!current() || captured !== stamp()) storyboardInvalid(); if (asset.kind !== 'video' || asset.deleted_at || asset.id !== job.output_candidate.id || asset.version !== job.approved_asset_version || asset.sha256 !== job.output_candidate.digest) storyboardInvalid();
      return props.client.storyboardBindVideo(receipt, selected, { asset_id: asset.id, version: asset.version, digest: asset.sha256, kind: 'video' }, { id: job.id, version: job.version, request_digest: job.request_digest, receipt_digest: job.receipt_digest }, job.command.storyboard_shot).then(refreshed);
    }, adopt, true); };
  const acceptCreation = (value: StoryboardTimelineCreation) => { setCreation(value); setTimelineUnknown(false); setConfirmation(''); setAdoptionConsent('');
    if (adoptionUnknown) { const expected = adoptionAttempt.current, proof = value.timeline.video_adoption_receipt; if (expected && proof && proof.document_id === expected.document_id && proof.shot_id === expected.shot_id && proof.timeline_id === expected.timeline_id && sameStoryboardValue(proof.request, expected.body)) { setAdoptionUnknown(false); setUncertain(false); adoptionAttempt.current = undefined; } }
    else setUncertain(false);
  };
  const makeTimeline = () => { if (!current() || locked || !props.editable || uncertain || timelineUnknown || !receipt || !fresh || !receipt.approved || confirmation !== approvalKey || !timelineShots.length || timelineShots.length > 30 || creationAttempt.current) return;
    if (props.client.storyboardTimelineCreate) { const body: StoryboardTimelineCreateInput = { expected_version: receipt.document_snapshot.version, reviewed_content_digest: receipt.content_digest, title: `${props.document.title.slice(0, 220)} · 剪辑底稿`, shot_ids: [...timelineShots], width: 1280, height: 720, fps: 24, request_id: crypto.randomUUID() }; creationAttempt.current = { receipt: structuredClone(receipt), body }; void run('timeline', () => props.client.storyboardTimelineCreate(receipt, body), acceptCreation, true); }
    else void run('timeline', () => props.client.storyboardTimelineDraft(receipt, timelineShots, `${props.document.title.slice(0, 220)} · 剪辑底稿`), setTimeline, true);
  };
  const inspectTimelineRecovery = () => { const attempt = creationAttempt.current; if (attempt && props.client.storyboardTimelineCreation) { void run('timeline-recovery', () => props.client.storyboardTimelineCreation(attempt.receipt, attempt.body), acceptCreation); }
    else if (timelineUnknown) void run('timeline-recovery', () => props.production.timelineList(), value => setTimelineRecovery(value.items)); };
  const newTimelineAttempt = () => { if (!locked && !timelineUnknown && !adoptionUnknown && creation && !prepared) { creationAttempt.current = undefined; setCreation(undefined); setConfirmation(''); } };
  const adoptionKey = JSON.stringify([receipt?.document_snapshot, selected?.video_result, creation?.timeline.id, creation?.timeline.version, creation?.timeline.timeline_digest, clipId, rangeIn, rangeOut, includeAudio]);
  const eligibleClips = creation && selected ? creation.timeline.timeline.tracks.filter(track => track.kind === 'VIDEO').flatMap(track => track.clips.filter(clip => creation.storyboard_origin.shots.some(pin => pin.clip_id === clip.id && pin.shot_id === selected.shot_id && pin.shot_version === selected.shot_version && pin.shot_digest === selected.shot_digest)).map(clip => ({ ...clip, locked: track.locked === true }))) : [];
  const adoptVideo = () => { const clip = eligibleClips.find(clip => clip.id === clipId), result = selected?.video_result; if (!current() || locked || !props.editable || uncertain || adoptionUnknown || adoptionAttempt.current || !receipt?.approved || !fresh || !selected || !result || !creation || !clip || clip.locked || adoptionConsent !== adoptionKey || !props.client.storyboardAdoptVideo) return;
    const inMs = Number(rangeIn), outMs = Number(rangeOut); if (!Number.isSafeInteger(inMs) || !Number.isSafeInteger(outMs) || inMs < 0 || outMs <= inMs || outMs > 36_000_000) return;
    const input = { expected_timeline_version: creation.timeline.version, reviewed_timeline_digest: creation.timeline.timeline_digest, request_id: crypto.randomUUID(), clip_id: clipId, in_ms: inMs, out_ms: outMs, include_audio: includeAudio };
    adoptionAttempt.current = { document_id: receipt.document_snapshot.id, shot_id: selected.shot_id, timeline_id: creation.timeline.id, body: { expected_version: receipt.document_snapshot.version, shot_version: selected.shot_version, shot_digest: selected.shot_digest, ...input, video_asset: result.asset, video_job: result.job } };
    void run('adoption', () => props.client.storyboardAdoptVideo(receipt, selected, creation, input), value => { setCreation({ ...creation, timeline: { ...creation.timeline, ...value.timeline } }); adoptionAttempt.current = undefined; setAdoptionConsent(''); setUncertain(false); setAdoptionUnknown(false); }, true);
  };
  useEffect(() => { props.onDirtyChange(!!props.exactImage && !exactDone || mediaDirty || timelineUnknown && !!creationAttempt.current || adoptionUnknown); }, [mediaDirty, timelineUnknown, adoptionUnknown, props.onDirtyChange, props.exactImage, exactDone]);
  const reportedReceipt = useRef<string>(); useEffect(() => { const key = current() && fresh ? JSON.stringify(receipt) : ''; if (reportedReceipt.current !== key) { reportedReceipt.current = key; latest.current.onReceipt?.(key ? receipt : undefined); } }, [receipt, fresh, props.active, props.document.id, props.document.version]);
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; props.onDirtyChange(false); props.onReceipt?.(undefined); }; }, []);
  useLayoutEffect(() => { setPreview(undefined); }, [previewBinding]);
  useLayoutEffect(() => { if (props.exactImage && !exactAttempt.current) { setExactSource(undefined); setReceipt(undefined); setSelectedId(''); } }, [props.exactImage, props.studio, props.active, props.editable]);
  useLayoutEffect(() => { if (!receiptRef.current || receiptRef.current.document_snapshot.id !== props.document.id || receiptRef.current.document_snapshot.version !== props.document.version) { epoch.current++; setLoading(''); setReceipt(undefined); setAdvice(undefined); setPrepared(undefined); setTimeline(undefined); setConfirmation(''); setSelectedId(''); setTimelineShots([]); } }, [props.document.id, props.document.version]);
  const available = current();
  return { available, exactSource: available ? exactSource : undefined, exactDone: available && exactDone, exactPending: available && !!exactAttempt.current, inspectExactImage, bindExactImage, inspectExactAttempt, receipt: available && fresh ? receipt : undefined, advice: available ? advice : undefined, selected: available ? selected : undefined, selectedId, assets: available ? assets : [], providers: available ? providers : [], assetId, providerId, operation,
    prepared: available ? prepared : undefined, timeline: available ? timeline : undefined, creation: available ? creation : undefined, creationRequestId: available ? creationAttempt.current?.body.request_id : undefined, loading, error, uncertain, locked, fresh, reviewed: confirmation === approvalKey && !!approvalKey, timelineShots,
    preview: previewCurrent() ? preview?.asset : undefined, previewCurrent, previewDownload, loadPreview, loadVideoPreview, timelineUnknown, timelineRecovery: available ? timelineRecovery : [], inspectTimelineRecovery,
    preparedCurrent, read, loadResources, approve, bind, prepareImage, prepareVideo, videoOperation, videoProvider, videoJobs: available ? videoJobs.filter(job => job.command?.storyboard_shot?.shot_id === selectedId && matchingJob(job)) : [], videoJobId, loadVideoJobs, observeJob, bindVideo, makeTimeline, newTimelineAttempt, setMediaDirty,
    adoptionUnknown, eligibleClips: available ? eligibleClips : [], clipId, rangeIn, rangeOut, includeAudio, adoptVideo, adoptionReviewed: adoptionConsent === adoptionKey,
    chooseClip: (id: string) => { const clip = eligibleClips.find(clip => clip.id === id); if (!locked && !prepared && !adoptionUnknown && clip) { setClipId(id); setRangeIn('0'); setRangeOut(String(clip.out_ms - clip.in_ms)); setIncludeAudio(false); setAdoptionConsent(''); } },
    changeRange: (key: 'in' | 'out', value: string) => { if (!locked && !adoptionUnknown) { (key === 'in' ? setRangeIn : setRangeOut)(value); setAdoptionConsent(''); } }, chooseClipAudio: (value: boolean) => { if (!locked && !adoptionUnknown) { setIncludeAudio(value); setAdoptionConsent(''); } }, confirmAdoption: (value: boolean) => { if (!locked && !adoptionUnknown) setAdoptionConsent(value ? adoptionKey : ''); },
    select: (id: string) => { if (props.exactImage && (exactRenderGeneration !== exactEpoch.current || !current() || !latest.current.editable || latest.current.busy || latest.current.isBusy() || slot.current)) return; if (!locked && !prepared && !exactAttempt.current) { exactEpoch.current++; setSelectedId(id); setAssetId(''); } }, chooseAsset: (id: string) => { if (!locked) setAssetId(id); }, chooseProvider: (id: string) => { if (!locked) setProviderId(id); },
    chooseOperation: (value: typeof operation) => { if (!locked && ['m5.image.t2i', 'm5.image.i2i', 'm5.image.reference'].includes(value)) { setOperation(value); setProviderId(''); } },
    chooseVideoOperation: (value: typeof videoOperation) => { if (!locked && !prepared && ['m7.video.t2v', 'm7.video.i2v'].includes(value)) { setVideoOperation(value); setVideoProvider(''); } }, chooseVideoProvider: (value: string) => { if (!locked && !prepared) setVideoProvider(value); }, chooseVideoJob: (value: string) => { if (!locked && !prepared) setVideoJobId(value); },
    confirm: (value: boolean) => { if (!locked && props.editable) setConfirmation(value ? approvalKey : ''); }, chooseTimelineShot: (id: string, checked: boolean) => { if (!locked) setTimelineShots(rows => checked ? [...rows.filter(value => value !== id), id] : rows.filter(value => value !== id)); },
    closePrepared: () => { if (current()) { setPrepared(undefined); setMediaDirty(false); } },
  };
}
