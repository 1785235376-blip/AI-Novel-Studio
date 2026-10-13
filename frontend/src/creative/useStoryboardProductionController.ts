import { useCallback, useLayoutEffect, useRef, useState } from 'react';
import { ApiError, apiErrorView, type Asset } from '../api';
import type { CreativeClient } from './client';
import type { CreativeDocument } from './types';
import type { StudioClient, StudioAsset } from './studioClient';
import type { ProductionProvider } from './studioProductionClient';
import type { StudioProductionClient } from './studioProductionClient';
import { mediaProviderKey } from './useStudioMediaExecution';
import { maskSha256 } from './studioManualMaskContract';
import type { StudioTimelineRow } from './studioTimelineTypes';
import { storyboardInvalid, type StoryboardReceipt, type DirectorAdvice, type StoryboardImageRequest, type StoryboardTimelineDraft } from './studioStoryboardContract';

export type StoryboardProductionProps = { document: CreativeDocument; client: CreativeClient; studio: StudioClient; production: StudioProductionClient;
  active: boolean; editable: boolean; busy: boolean; isBusy: () => boolean; isCurrent: () => boolean; perform: <T>(work: () => Promise<T>) => Promise<T>;
  onDocument: (document: CreativeDocument) => void; onDenied: () => void; onDirtyChange: (dirty: boolean) => void };
/** Original document/asset/job ownership stays in clients. The view owns no requests or grants. */
export function useStoryboardProductionController(props: StoryboardProductionProps) {
  const [receipt, setReceipt] = useState<StoryboardReceipt>(), [advice, setAdvice] = useState<DirectorAdvice>(), [assets, setAssets] = useState<StudioAsset[]>([]), [providers, setProviders] = useState<ProductionProvider[]>([]);
  const [selectedId, setSelectedId] = useState(''), [assetId, setAssetId] = useState(''), [providerId, setProviderId] = useState('');
  const [operation, setOperation] = useState<'m5.image.t2i' | 'm5.image.i2i' | 'm5.image.reference'>('m5.image.t2i');
  const [confirmation, setConfirmation] = useState(''), [timelineShots, setTimelineShots] = useState<string[]>([]), [prepared, setPrepared] = useState<StoryboardImageRequest>(), [timeline, setTimeline] = useState<StoryboardTimelineDraft>();
  const [loading, setLoading] = useState(''), [error, setError] = useState(''), [uncertain, setUncertain] = useState(false);
  const [preview, setPreview] = useState<{ asset: StudioAsset; blob: Blob; binding: string }>();
  const [timelineUnknown, setTimelineUnknown] = useState(false), [timelineRecovery, setTimelineRecovery] = useState<StudioTimelineRow[]>([]);
  const latest = useRef(props); latest.current = props; const owner = useRef(props.client), alive = useRef(true), slot = useRef(false), epoch = useRef(0), receiptRef = useRef(receipt); receiptRef.current = receipt;
  const current = () => alive.current && latest.current.active && owner.current === latest.current.client && latest.current.isCurrent();
  const stamp = () => JSON.stringify([latest.current.document.id, latest.current.document.version]);
  const fresh = !!receipt && receipt.document_snapshot.id === props.document.id && receipt.document_snapshot.version === props.document.version;
  const locked = !current() || props.busy || props.isBusy() || !!loading;
  const selected = fresh ? receipt.shots.find(shot => shot.shot_id === selectedId) : undefined;
  const previewBinding = JSON.stringify([props.document.id, props.document.version, selectedId, selected?.image_asset]);
  const previewBindingRef = useRef(previewBinding); previewBindingRef.current = previewBinding;
  const previewRef = useRef(preview); previewRef.current = preview;
  const previewCurrent = useCallback(() => alive.current && latest.current.active && owner.current === latest.current.client && latest.current.isCurrent() && previewRef.current?.binding === previewBindingRef.current, []);
  const previewDownload = useCallback(async (asset: Asset) => { const value = previewRef.current; if (!previewCurrent() || !value || asset.id !== value.asset.id || asset.sha256 !== value.asset.sha256) storyboardInvalid(); return value.blob; }, [previewCurrent]);
  const approvalKey = fresh ? JSON.stringify([receipt.document_snapshot, receipt.content_digest]) : '';
  const preparedCurrent = () => current() && latest.current.editable && !!prepared && receiptRef.current?.document_snapshot.version === latest.current.document.version && JSON.stringify(prepared.shot_pin.document_snapshot) === JSON.stringify(receiptRef.current?.document_snapshot)
    && !!receiptRef.current?.shots.some(shot => shot.shot_id === prepared.shot_pin.shot_id && shot.shot_version === prepared.shot_pin.shot_version && shot.shot_digest === prepared.shot_pin.shot_digest);
  const run = async <T,>(kind: string, work: () => Promise<T>, accept: (value: T) => void, mutation = false) => {
    if (!current() || slot.current || latest.current.busy || latest.current.isBusy() || mutation && (!latest.current.editable || uncertain)) return;
    slot.current = true; const ticket = ++epoch.current, captured = stamp(); setLoading(kind); setError('');
    try { const value = await latest.current.perform(work); if (current() && epoch.current === ticket && captured === stamp()) accept(value); }
    catch (reason) { if (current() && epoch.current === ticket && captured === stamp()) { setError(apiErrorView(reason, '操作未完成，请读取原版本核对。').message); setConfirmation('');
      if (kind === 'read' || ['preview', 'request'].includes(kind) && reason instanceof ApiError && (reason.status === 409 || reason.status === 200 && reason.problem.code === 'STUDIO_RESPONSE_INVALID')) { setReceipt(undefined); setAdvice(undefined); setPreview(undefined); setPrepared(undefined); setTimeline(undefined); setUncertain(true); }
      if (reason instanceof ApiError && [401, 403].includes(reason.status)) latest.current.onDenied(); else if (mutation && (!(reason instanceof ApiError) || reason.problem.code === 'STUDIO_RESPONSE_INVALID' || reason.status === 0 || reason.status >= 500 || [408, 409, 425, 429].includes(reason.status))) { setUncertain(true); if (kind === 'timeline') setTimelineUnknown(true); } } }
    finally { slot.current = false; if (alive.current && epoch.current === ticket) setLoading(''); }
  };
  async function refreshed(next: StoryboardReceipt) { if (!current() || stamp() !== JSON.stringify([props.document.id, props.document.version])) storyboardInvalid(); const document = await props.client.get(next.document_snapshot.id); if (document.version !== next.document_snapshot.version || document.id !== next.document_snapshot.id || document.mode !== 'STORYBOARD') storyboardInvalid(); return { receipt: next, document }; }
  const adopt = (value: { receipt: StoryboardReceipt; document: CreativeDocument }) => { setReceipt(value.receipt); setConfirmation(''); setPrepared(undefined); setTimeline(undefined); setUncertain(false); latest.current.onDocument(value.document); };
  const read = () => { if (prepared) return; void run<DirectorAdvice | StoryboardReceipt>('read', () => props.document.mode === 'DIRECTOR' ? props.client.directorAdvice(props.document.id) : props.client.storyboardGet(props.document.id), value => {
    if (value.document_snapshot.version !== props.document.version) { setReceipt(undefined); setAdvice(undefined); setUncertain(true); setError('服务端文档版本已变化，请先重新读取原创作文档。'); return; }
    setUncertain(false); setConfirmation(''); setPrepared(undefined); setTimeline(undefined); if (value.contract === 'studio-director-advice/1') setAdvice(value); else { setReceipt(value); setSelectedId(value.shots[0]?.shot_id || ''); }
  }); };
  const loadResources = () => { const captured = stamp(); void run('resources', async () => { const assets = await props.studio.assets(); if (!current() || captured !== stamp()) storyboardInvalid(); return { assets, providers: await props.production.providers() }; }, value => { setAssets(value.assets.items.filter(asset => asset.kind === 'image' && !asset.deleted_at)); setProviders(value.providers.filter(provider => provider.local && ['m5.image.t2i', 'm5.image.i2i', 'm5.image.reference'].includes(provider.operation_id))); setAssetId(''); setProviderId(''); }); };
  const loadPreview = () => { const pin = selected?.image_asset; if (!pin || prepared) return; const binding = previewBinding; setPreview(undefined);
    void run('preview', async () => { const asset = await props.studio.asset(pin.asset_id); if (asset.id !== pin.asset_id || asset.version !== pin.version || asset.sha256 !== pin.digest || asset.kind !== 'image' || !asset.media_type.startsWith('image/') || asset.deleted_at || asset.size < 1 || asset.size > 64 * 1024 * 1024) storyboardInvalid();
      if (!current() || binding !== previewBindingRef.current) storyboardInvalid(); const blob = await props.studio.download(pin.asset_id); if (blob.size !== asset.size || blob.type !== asset.media_type || await maskSha256(new Uint8Array(await blob.arrayBuffer())) !== pin.digest) storyboardInvalid(); return { asset, blob, binding };
    }, value => { if (binding === previewBindingRef.current) setPreview(value); }); };
  const approve = () => { if (!receipt || !fresh || confirmation !== approvalKey) return; void run('approve', () => props.client.storyboardApprove(receipt).then(refreshed), adopt, true); };
  const bind = () => { const asset = assets.find(asset => asset.id === assetId); if (!receipt || !selected || !asset || !fresh) return; void run('bind', () => props.client.storyboardBindImage(receipt, selected, { asset_id: asset.id, version: asset.version, digest: asset.sha256, kind: 'image' }).then(refreshed), adopt, true); };
  const prepareImage = () => { const provider = providers.find(provider => mediaProviderKey(provider) === providerId && provider.operation_id === operation); if (!receipt || !selected || !fresh || !provider) return;
    void run('request', () => props.client.storyboardImageRequest(receipt, selected, operation, provider.provider_id, provider.model_id, crypto.randomUUID(), {}), value => { setPrepared(value); setConfirmation(''); }); };
  const makeTimeline = () => { if (timelineUnknown || !receipt || !fresh || !receipt.approved || confirmation !== approvalKey || !timelineShots.length || timelineShots.length > 30) return; void run('timeline', () => props.client.storyboardTimelineDraft(receipt, timelineShots, `${props.document.title.slice(0, 220)} · 剪辑底稿`), setTimeline, true); };
  const inspectTimelineRecovery = () => { if (!timelineUnknown) return; void run('timeline-recovery', () => props.production.timelineList(), value => setTimelineRecovery(value.items)); };
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; props.onDirtyChange(false); }; }, []);
  useLayoutEffect(() => { setPreview(undefined); }, [previewBinding]);
  useLayoutEffect(() => { if (!receiptRef.current || receiptRef.current.document_snapshot.id !== props.document.id || receiptRef.current.document_snapshot.version !== props.document.version) { epoch.current++; setLoading(''); setReceipt(undefined); setAdvice(undefined); setPrepared(undefined); setTimeline(undefined); setConfirmation(''); setSelectedId(''); setTimelineShots([]); } }, [props.document.id, props.document.version]);
  const available = current();
  return { receipt: available && fresh ? receipt : undefined, advice: available ? advice : undefined, selected, selectedId, assets: available ? assets : [], providers: available ? providers : [], assetId, providerId, operation,
    prepared: available ? prepared : undefined, timeline: available ? timeline : undefined, loading, error, uncertain, locked, fresh, reviewed: confirmation === approvalKey && !!approvalKey, timelineShots,
    preview: previewCurrent() ? preview?.asset : undefined, previewCurrent, previewDownload, loadPreview, timelineUnknown, timelineRecovery: available ? timelineRecovery : [], inspectTimelineRecovery,
    preparedCurrent, read, loadResources, approve, bind, prepareImage, makeTimeline,
    select: (id: string) => { if (!locked && !prepared) { setSelectedId(id); setAssetId(''); } }, chooseAsset: (id: string) => { if (!locked) setAssetId(id); }, chooseProvider: (id: string) => { if (!locked) setProviderId(id); },
    chooseOperation: (value: typeof operation) => { if (!locked && ['m5.image.t2i', 'm5.image.i2i', 'm5.image.reference'].includes(value)) { setOperation(value); setProviderId(''); } },
    confirm: (value: boolean) => { if (!locked && props.editable) setConfirmation(value ? approvalKey : ''); }, chooseTimelineShot: (id: string, checked: boolean) => { if (!locked) setTimelineShots(rows => checked ? [...rows.filter(value => value !== id), id] : rows.filter(value => value !== id)); },
    closePrepared: () => { if (current()) { setPrepared(undefined); props.onDirtyChange(false); } },
  };
}
