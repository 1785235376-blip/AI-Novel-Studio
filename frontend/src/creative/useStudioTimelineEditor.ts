import { applySelectionSplit, selectionSplitPreview, type SelectionSplitIds } from '../nle/timelineSelectionSplit';
import { changedRangeBeyondMeasurement, measuredBoundFromWaveform, measuredBoundKey, type TimelineMeasuredBound } from './timelineMeasuredBounds';
import type { TimelineWaveform } from './studioTimelineWaveformTypes';
import { selectionDuplicateOperations, type SelectionDuplicateIds } from '../nle/timelineSelectionDuplicate';
import { selectionMoveOperations } from '../nle/timelineSelectionMove';
import type { TimelineAssetHandoff } from './StudioTimelineAssetHandoff';
import { useEffect, useRef, useState } from 'react';
import { ApiError, apiErrorView } from '../api';
import type { StudioAsset } from './studioClient';
import type { StudioProductionClient } from './studioProductionClient';
import { checkedTimeline, checkedTimelineDraft, checkedTimelineList, checkedTimelineRow, cloneTimeline, newTimelineDraft, timelineBinding,
  timelineClipDuration, timelineFailure, timelineInputKey, timelineSources, timelineSourcesCurrent, type StudioTimeline, type StudioTimelineDraft, type StudioTimelineRow, type StudioTimelineSource } from './studioTimelineTypes';
import { AUDIO_TIMELINE_MAX_WAV_DURATION_MS, checkedTimelineExportPreview, checkedTimelineExportProfile, timelineExportKey, type TimelineExportProfile, type TimelineExportPreview } from './studioTimelineExportTypes';
import { useStudioTimelineTransfer } from './useStudioTimelineTransfer';
import { useStudioTimelinePlayback } from './useStudioTimelinePlayback';
import { useStudioTimelineSourceEdit } from './useStudioTimelineSourceEdit';

export type StudioTimelineJob = Awaited<ReturnType<StudioProductionClient['timelineRender']>>;
export type StudioTimelineEditorProps = {
  client: StudioProductionClient; assets: StudioAsset[]; canMutate: boolean; busy: boolean; isBusy?: () => boolean;
  isCurrent: () => boolean; read: <T>(work: () => Promise<T>) => Promise<T>; mutate: <T>(work: () => Promise<T>) => Promise<T>;
  onDirtyChange: (dirty: boolean) => void; onJob: (job: StudioTimelineJob) => void; onUnavailable: () => void;
  /** UX-PRODUCT batch 3 (UX-06): display-only project identity for the editing rail. */
  projectId?: string;
  mediaKind?: 'VIDEO' | 'AUDIO';
  assetHandoff?: TimelineAssetHandoff;
};
type Operation = 'LIST' | 'GET' | 'SAVE' | 'RENDER' | 'JOB' | 'EXPORT_PREVIEW' | 'EXPORT' | 'TRACK_LOCK';
type Attempt = { binding: string; requestId: string; state: 'UNKNOWN' | 'RETURNED'; requestDigest?: string;
  snapshot: { id: string; version: number; digest: string }; sources: StudioTimelineSource[]; timeline: StudioTimeline;
  exportProfile?: TimelineExportProfile; recipeDigest?: string; measurement?: StudioTimelineJob['media_measurement'] };

/** Owns the CAS/draft boundary; the presentation can be replaced independently. */
export function useStudioTimelineEditor(props: StudioTimelineEditorProps) {
  const [draft, setDraft] = useState<StudioTimelineDraft>(() => newTimelineDraft(props.mediaKind)), [base, setBase] = useState<StudioTimelineRow>();
  const [rows, setRows] = useState<StudioTimelineRow[]>([]), [candidate, setCandidate] = useState<StudioTimelineRow>();
  const [pending, setPending] = useState<Operation>(), [failure, setFailure] = useState<'CONFLICT' | 'UNKNOWN'>();
  const [error, setError] = useState(''), [notice, setNotice] = useState(''), [denied, setDenied] = useState(false);
  const [confirmed, setConfirmed] = useState(''), [adoptConfirmed, setAdoptConfirmed] = useState(false), [discardConfirmed, setDiscardConfirmed] = useState(false);
  const [attempt, setAttempt] = useState<Attempt>();
  const [historySize, setHistorySize] = useState({ undo: 0, redo: 0 });
  const history = useRef<{ undo: StudioTimelineDraft[]; redo: StudioTimelineDraft[] }>({ undo: [], redo: [] });
  const [exportProfile, setExportProfile] = useState<TimelineExportProfile>(() => ({ preset: props.mediaKind === 'AUDIO' ? 'AUDIO_WAV_PCM16' : 'REVIEW_MP4' }));
  const [exportPreview, setExportPreview] = useState<TimelineExportPreview>(), [exportConfirmed, setExportConfirmed] = useState('');
  const exportRef = useRef<{ profile: TimelineExportProfile; preview?: TimelineExportPreview; consent: string }>({ profile: exportProfile, consent: '' });
  const reservedBindings = useRef(new Set<string>());
  const transferGate = useRef(false);
  const playbackGate = useRef(false);
  const sourceEditGate = useRef(false);
  const mode = props.mediaKind ?? 'VIDEO', modeOwner = useRef(mode);
  const latest = useRef(props); latest.current = props;
  const measuredBounds = useRef<{source:StudioTimelineRow;client:StudioProductionClient;values:Map<string,TimelineMeasuredBound>}>();
  const [,setMeasurementRevision] = useState(0);
  // A handoff approval is bound to the original draft/target generation, not
  // merely equal JSON. Editing then undoing, or switching identical targets,
  // must still invalidate a metadata read that was already in flight.
  const handoffGeneration = useRef(0);
  const handoffEnvironment = useRef([props.client, props.busy, props.canMutate, props.projectId, props.isCurrent(), !!props.isBusy?.()]);
  const environment = [props.client, props.busy, props.canMutate, props.projectId, props.isCurrent(), !!props.isBusy?.()];
  if (environment.some((value, index) => value !== handoffEnvironment.current[index])) {
    handoffGeneration.current++; handoffEnvironment.current = environment; measuredBounds.current = undefined;
  }
  const alive = useRef(true), epoch = useRef(0), owner = useRef(props.client), reading = useRef<AbortController>();
  const slot = useRef<{ epoch: number; operation: Operation }>(), started = useRef(false), deniedRef = useRef(false);
  const consent = useRef({ render: '', adopt: '', discard: '' });
  const draftRef = useRef(draft), baseRef = useRef(base), candidateRef = useRef(candidate), failureRef = useRef(failure), attemptRef = useRef(attempt);
  draftRef.current = draft; baseRef.current = base; candidateRef.current = candidate; failureRef.current = failure; attemptRef.current = attempt;
  const baseline = useRef(timelineInputKey(newTimelineDraft(latest.current.mediaKind)));
  const current = () => alive.current && !deniedRef.current && owner.current === latest.current.client && modeOwner.current === (latest.current.mediaKind ?? 'VIDEO') && latest.current.isCurrent();
  const blocked = () => !!slot.current || transferGate.current || playbackGate.current || sourceEditGate.current || latest.current.busy || !!latest.current.isBusy?.() || !current();
  const owns = owner.current === props.client && modeOwner.current === mode && props.isCurrent() && !denied;
  const inputDirty = timelineInputKey(draft) !== baseline.current;
  const uncertainRender = !!attempt && attempt.state === 'UNKNOWN';
  const sourcesCurrent = timelineSourcesCurrent(draft.timeline, props.assets);
  const transfer = useStudioTimelineTransfer({ props: { ...props, isCurrent: current }, source: owns && mode !== 'AUDIO' ? base : undefined,
    canOperate: mode !== 'AUDIO' && owns && props.canMutate && !props.busy && !pending && !failure && !uncertainRender && !playbackGate.current && !sourceEditGate.current && !!base && !inputDirty && sourcesCurrent,
    isReady: () => (latest.current.mediaKind ?? 'VIDEO') !== 'AUDIO' && !blocked() && latest.current.canMutate && !!baseRef.current && !failureRef.current && attemptRef.current?.state !== 'UNKNOWN'
      && timelineInputKey(draftRef.current) === baseline.current && timelineSourcesCurrent(baseRef.current.timeline, latest.current.assets),
    onAdopt: row => adopt(row), onAuthorityLost: loseAuthority, onGateChange: value => { handoffGeneration.current++; transferGate.current = value; } });
  const playback = useStudioTimelinePlayback({ props: { ...props, isCurrent: current }, source: owns ? base : undefined,
    isReady: () => !blocked() && latest.current.canMutate && !!baseRef.current && !failureRef.current && attemptRef.current?.state !== 'UNKNOWN'
      && timelineInputKey(draftRef.current) === baseline.current && timelineSourcesCurrent(baseRef.current.timeline, latest.current.assets),
    onAuthorityLost: loseAuthority, onGateChange: value => { handoffGeneration.current++; playbackGate.current = value; } });
  const sourceEdit = useStudioTimelineSourceEdit({ props: { ...props, isCurrent: current }, source: owns ? base : undefined,
    canOperate: owns && props.canMutate && !props.busy && !pending && !failure && !uncertainRender && !transfer.locked && !playback.locked && !!base && !inputDirty && sourcesCurrent,
    isReady: () => !blocked() && latest.current.canMutate && !!baseRef.current && !failureRef.current && attemptRef.current?.state !== 'UNKNOWN'
      && timelineInputKey(draftRef.current) === baseline.current && timelineSourcesCurrent(baseRef.current.timeline, latest.current.assets),
    onAdopt: row => adopt(row), onAuthorityLost: loseAuthority, onGateChange: value => { handoffGeneration.current++; sourceEditGate.current = value; } });
  const dirty = owns && (inputDirty || !!failure || uncertainRender || !!transfer.dirty || !!playback.dirty || !!sourceEdit.dirty || !!exportConfirmed || pending === 'SAVE' || pending === 'RENDER' || pending === 'EXPORT' || pending === 'EXPORT_PREVIEW' || pending === 'TRACK_LOCK');
  const canEdit = owns && props.canMutate && !props.busy && !pending && !failure && !uncertainRender && !transfer.locked && !playback.locked && !sourceEdit.locked;
  const savedBinding = base ? timelineBinding(base) : '';
  const renderedThisSnapshot = reservedBindings.current.has(savedBinding);
  const canRender = mode !== 'AUDIO' && canEdit && !!base && !inputDirty && confirmed === savedBinding && sourcesCurrent && !renderedThisSnapshot && !uncertainRender;
  let exportKey = ''; try { exportKey = timelineExportKey(exportProfile); } catch { /* The form may hold an incomplete number while editing. */ }
  const exportBinding = `${savedBinding}:export:${exportKey}`;
  const exportAvailable = !!props.client.timelineExportPreview && !!props.client.timelineExport;
  const canPreviewExport = (base?.timeline.schema_version !== 3 || base.timeline.duration_ms <= AUDIO_TIMELINE_MAX_WAV_DURATION_MS) && canEdit && exportAvailable && !!base && !inputDirty && sourcesCurrent && !uncertainRender && !!exportKey;
  const canExport = canPreviewExport && !!exportPreview && exportConfirmed === exportPreview.preview_digest
    && exportPreview.timeline_snapshot.id === base?.id && exportPreview.timeline_snapshot.version === base?.version
    && exportPreview.timeline_snapshot.digest === base?.timeline_digest && !reservedBindings.current.has(exportBinding);

  useEffect(() => { alive.current = true; return () => {
    alive.current = false; epoch.current++; reading.current?.abort();
    if (slot.current?.operation === 'LIST') { slot.current = undefined; started.current = false; }
  }; }, []);
  useEffect(() => {
    owner.current = props.client; modeOwner.current = mode; deniedRef.current = false; epoch.current++; reading.current?.abort(); reading.current = undefined; slot.current = undefined; started.current = false;
    const input = newTimelineDraft(latest.current.mediaKind); handoffGeneration.current++; draftRef.current = input; baseRef.current = undefined; candidateRef.current = undefined; failureRef.current = undefined; attemptRef.current = undefined;
    baseline.current = timelineInputKey(input); setDraft(input); setBase(undefined); setRows([]); setCandidate(undefined); setFailure(undefined); setAttempt(undefined); setPending(undefined);
    consent.current = { render: '', adopt: '', discard: '' };
    clearHistory();
    reservedBindings.current.clear(); exportRef.current.profile = { preset: mode === 'AUDIO' ? 'AUDIO_WAV_PCM16' : 'REVIEW_MP4' }; setExportProfile(exportRef.current.profile); clearExportPreview();
    setDenied(false); setError(''); setNotice(''); setConfirmed(''); setAdoptConfirmed(false); setDiscardConfirmed(false);
    return () => { epoch.current++; reading.current?.abort(); };
  }, [props.client, mode]);
  useEffect(() => { props.onDirtyChange(dirty); }, [dirty, props.onDirtyChange]);
  useEffect(() => () => latest.current.onDirtyChange(false), []);
  useEffect(() => {
    // Automatic read only. StrictMode cleanup invalidates the first callback;
    // a replacement setup can make its own bounded list request.
    if (!started.current && !blocked()) { started.current = true; void reload(); }
  }, [props.client, props.busy, mode]);

  function loseAuthority() {
    deniedRef.current = true; epoch.current++; reading.current?.abort(); slot.current = undefined;
    baseRef.current = undefined; candidateRef.current = undefined; failureRef.current = undefined; attemptRef.current = undefined;
    draftRef.current = newTimelineDraft(latest.current.mediaKind); baseline.current = timelineInputKey(draftRef.current);
    consent.current = { render: '', adopt: '', discard: '' };
    clearHistory();
    reservedBindings.current.clear(); clearExportPreview();
    setDenied(true); setBase(undefined); setCandidate(undefined); setDraft(draftRef.current); setRows([]); setFailure(undefined); setAttempt(undefined); setPending(undefined); setConfirmed(''); setAdoptConfirmed(false); setDiscardConfirmed(false);
    latest.current.onDirtyChange(false); latest.current.onUnavailable();
  }
  function handleError(reason: unknown, fallback: string) {
    if (reason instanceof ApiError && [401, 403].includes(reason.status)) { loseAuthority(); return; }
    setError(apiErrorView(reason, fallback).message);
    if (reason instanceof ApiError && [404, 410, 501].includes(reason.status)) latest.current.onUnavailable();
  }
  function begin(operation: Operation) {
    if (blocked()) return undefined;
    const value = { epoch: ++epoch.current, operation }; slot.current = value;
    consent.current = { render: '', adopt: '', discard: '' };
    clearExportPreview();
    setPending(operation); setError(''); setNotice(''); setConfirmed(''); setAdoptConfirmed(false); setDiscardConfirmed(false);
    if (operation === 'SAVE' || operation === 'RENDER' || operation === 'EXPORT' || operation === 'EXPORT_PREVIEW' || operation === 'TRACK_LOCK') latest.current.onDirtyChange(true);
    return { ...value, client: latest.current.client };
  }
  function active(value: { epoch: number; client: StudioProductionClient }) { return current() && owner.current === value.client && slot.current?.epoch === value.epoch && epoch.current === value.epoch; }
  function finish(value: { epoch: number; client: StudioProductionClient }) {
    if (slot.current?.epoch === value.epoch) slot.current = undefined;
    if (current() && owner.current === value.client && epoch.current === value.epoch) setPending(undefined);
  }
  function adopt(row: StudioTimelineRow, keepDraft = false) {
    const input = keepDraft ? cloneTimeline(draftRef.current) : { title: row.title, timeline: cloneTimeline(row.timeline) };
    handoffGeneration.current++; baseRef.current = row; draftRef.current = input; baseline.current = timelineInputKey({ title: row.title, timeline: row.timeline });
    candidateRef.current = undefined; failureRef.current = undefined;
    consent.current = { render: '', adopt: '', discard: '' };
    clearHistory();
    clearExportPreview();
    setBase(row); setDraft(input); setCandidate(undefined); setFailure(undefined); setConfirmed(''); setAdoptConfirmed(false); setDiscardConfirmed(false); setError('');
    setRows(items => [row, ...items.filter(item => item.id !== row.id)]);
  }
  async function reload() {
    const request = begin('LIST'); if (!request) return;
    const abort = new AbortController(); reading.current = abort;
    try {
      const list = checkedTimelineList(await latest.current.mutate(() => latest.current.read(() => request.client.timelineList(abort.signal))));
      if (active(request)) { setRows(list.filter(row => (row.timeline.schema_version === 3) === (mode === 'AUDIO'))); setNotice('列表已读取；不会替换本地时间线。选择后读取并核对。'); }
    } catch (reason) { if (active(request)) handleError(reason, '时间线列表读取失败。'); }
    finally { if (reading.current === abort) reading.current = undefined; finish(request); }
  }
  async function checkServer(id = baseRef.current?.id) {
    if (!id) { setNotice('请先刷新列表，再选择可能已保存的时间线。列表相同不证明原请求完成。'); return; }
    const request = begin('GET'); if (!request) return;
    const abort = new AbortController(); reading.current = abort; candidateRef.current = undefined; setCandidate(undefined); setConfirmed('');
    try {
      const row = checkedTimelineRow(await latest.current.mutate(() => latest.current.read(() => request.client.timelineGet(id, abort.signal))), id);
      if (!active(request)) return;
      if ((row.timeline.schema_version === 3) !== (mode === 'AUDIO')) throw new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: '时间线媒体类型与当前工作区不一致，请从对应工作区读取。' });
      const source = baseRef.current;
      if (source?.id === row.id && (row.version < source.version || row.version === source.version && (row.timeline_digest !== source.timeline_digest || timelineInputKey({ title: row.title, timeline: row.timeline }) !== timelineInputKey({ title: source.title, timeline: source.timeline })))) throw new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: '读取的时间线版本回退或同版本内容改变，请重新核对。' });
      candidateRef.current = row; setCandidate(row); setNotice('已读取服务端时间线。核对内容后人工采用；读取本身不会覆盖草稿，也不证明先前渲染完成。');
    } catch (reason) { if (active(request)) handleError(reason, '时间线读取失败，草稿仍保留。'); }
    finally { if (reading.current === abort) reading.current = undefined; finish(request); }
  }
  function adoptCandidate(keepDraft: boolean) {
    const row = candidateRef.current;
    if (!row || consent.current.adopt !== timelineBinding(row) || blocked() || attemptRef.current?.state === 'UNKNOWN' || keepDraft && !latest.current.canMutate) return;
    adopt(row, keepDraft);
    setNotice(keepDraft ? '输入保留，基于读取的版本继续编辑；需要你明确再次保存。' : '已采用读取的服务端时间线；没有再次保存或渲染。');
  }
  function currentMeasuredBounds(): TimelineMeasuredBound[] {
    const retained=measuredBounds.current;
    if (!retained || retained.client!==latest.current.client || retained.source!==baseRef.current || !current()) return [];
    return [...retained.values.values()].filter(bound=>latest.current.assets.some(asset=>!asset.deleted_at && asset.id===bound.snapshot.id
      && asset.kind===bound.snapshot.asset_kind && asset.version===bound.snapshot.version && asset.sha256===bound.snapshot.digest));
  }
  function observeWaveformMeasurement(value:TimelineWaveform,source:StudioTimelineRow,client:StudioProductionClient):boolean {
    if (blocked() || !latest.current.canMutate || client!==latest.current.client || source!==baseRef.current
      || failureRef.current || attemptRef.current?.state==='UNKNOWN' || !timelineSourcesCurrent(source.timeline,latest.current.assets)) return false;
    try {
      const bound=measuredBoundFromWaveform(value,source);
      if (latest.current.projectId && value.novel_id!==latest.current.projectId) return false;
      const key=measuredBoundKey(bound.snapshot),existing=measuredBounds.current;
      const values=existing?.source===source&&existing.client===client?existing.values:new Map<string,TimelineMeasuredBound>();
      const old=values.get(key);
      if(old?.frames===bound.frames&&old.sampleRate===bound.sampleRate)return true;
      values.set(key,bound);measuredBounds.current={source,client,values};setMeasurementRevision(value=>value+1);return true;
    } catch { return false; }
  }
  function change(work: (input: StudioTimelineDraft) => void): boolean {
    if (blocked() || !latest.current.canMutate || failureRef.current || attemptRef.current?.state === 'UNKNOWN') return false;
    const input = cloneTimeline(draftRef.current); work(input);
    if ((input.timeline.schema_version === 3) !== ((latest.current.mediaKind ?? 'VIDEO') === 'AUDIO')) return false;
    const beyond=changedRangeBeyondMeasurement(draftRef.current,input,currentMeasuredBounds());
    if(beyond){setError(`片段 ${beyond} 的新素材终点超过已读取的实测长度，未修改草稿。请缩短范围或重新核对原素材。`);return false;}
    const source = baseRef.current, lockedTracks = source?.timeline.tracks.filter(track => track.locked) ?? [];
    if (source && lockedTracks.length && (['duration_ms', 'width', 'height', 'fps'].some(key => input.timeline[key as 'duration_ms'] !== source.timeline[key as 'duration_ms'])
      || lockedTracks.some(track => JSON.stringify(input.timeline.tracks.find(row => row.id === track.id)) !== JSON.stringify(track)))) {
      setError('锁定轨道的片段、顺序和画布受保护。请先保存其他草稿，并通过原服务明确解锁。'); return false;
    }
    if (timelineInputKey(input) === timelineInputKey(draftRef.current)) return false;
    history.current.undo = [...history.current.undo.slice(-49), cloneTimeline(draftRef.current)]; history.current.redo = [];
    setHistorySize({ undo: history.current.undo.length, redo: 0 }); applyLocalInput(input); return true;
  }
  function clearHistory() {
    history.current = { undo: [], redo: [] }; setHistorySize({ undo: 0, redo: 0 });
  }
  function clearExportPreview() {
    exportRef.current.preview = undefined; exportRef.current.consent = ''; setExportPreview(undefined); setExportConfirmed('');
  }
  function changeExportProfile(profile: TimelineExportProfile) {
    if ((draftRef.current.timeline.schema_version === 3) !== (profile.preset === 'AUDIO_WAV_PCM16')) return;
    if (blocked() || !latest.current.canMutate || failureRef.current || attemptRef.current?.state === 'UNKNOWN') return;
    exportRef.current.profile = { ...profile }; setExportProfile(exportRef.current.profile); clearExportPreview(); setError(''); setNotice('');
  }
  function applyLocalInput(input: StudioTimelineDraft) {
    handoffGeneration.current++; draftRef.current = input; setDraft(input);
    consent.current = { render: '', adopt: '', discard: '' };
    clearExportPreview();
    candidateRef.current = undefined; setCandidate(undefined); setConfirmed(''); setAdoptConfirmed(false); setDiscardConfirmed(false); setError(''); setNotice('');
    latest.current.onDirtyChange(true);
  }
  function travelHistory(direction: 'undo' | 'redo') {
    if (blocked() || !latest.current.canMutate || failureRef.current || attemptRef.current?.state === 'UNKNOWN') return;
    const source = history.current[direction], input = source.pop(); if (!input) return;
    const target = direction === 'undo' ? 'redo' : 'undo';
    history.current[target] = [...history.current[target].slice(-49), cloneTimeline(draftRef.current)];
    setHistorySize({ undo: history.current.undo.length, redo: history.current.redo.length }); applyLocalInput(input);
  }
  function editClip(trackId: string, clipId: string, action: 'split' | 'duplicate' | 'move', position: number, targetId = trackId) {
    if (blocked() || !latest.current.canMutate || failureRef.current || attemptRef.current?.state === 'UNKNOWN') return;
    try {
      const input = checkedTimelineDraft(cloneTimeline(draftRef.current)), track = input.timeline.tracks.find(row => row.id === trackId);
      const clip = track?.clips.find(row => row.id === clipId), target = input.timeline.tracks.find(row => row.id === targetId);
      if (!track || !clip || !target || target.kind !== track.kind || !Number.isSafeInteger(position)) throw new Error('请核对原片段、同类型目标轨道与整数毫秒位置。');
      if (action === 'split') {
        if (!selectionSplitPreview(input.timeline, [clipId], position).some(row => row.affected)) {
          throw new Error('拆分位置必须位于片段的时间线范围内，保留两段有效长度。');
        }
        input.timeline = applySelectionSplit(input.timeline, [clipId], position, { [clipId]: crypto.randomUUID() });
      } else if (action === 'duplicate') {
        target.clips.push({ ...cloneTimeline(clip), id: crypto.randomUUID(), start_ms: position });
      } else {
        if (target.id !== track.id && track.clips.length === 1) throw new Error('移走最后一个片段会留下空轨道；请先加入其他片段，或在保存前明确移除空轨道。');
        track.clips = track.clips.filter(row => row.id !== clip.id); target.clips.push({ ...clip, start_ms: position });
      }
      const checked = checkedTimelineDraft(input);
      change(value => { value.title = checked.title; value.timeline = checked.timeline; });
      setNotice('仅已更新本地时间线；原素材和服务端版本保留，需要明确保存。');
    } catch (reason) { setError(reason instanceof Error ? reason.message : '片段编辑无效，请核对边界与轨道重叠。'); }
  }
  function splitSelection(clipIds: readonly string[], playheadMs: number, newIds: SelectionSplitIds,
    revision: string, client: StudioProductionClient): boolean {
    if (blocked() || !latest.current.canMutate || failureRef.current || attemptRef.current?.state === 'UNKNOWN'
      || client !== latest.current.client || revision !== `${epoch.current}:${handoffGeneration.current}`) return false;
    try {
      const input = checkedTimelineDraft(cloneTimeline(draftRef.current));
      input.timeline = applySelectionSplit(input.timeline, clipIds, playheadMs, newIds);
      const checked = checkedTimelineDraft(input);
      if (!change(value => { value.title = checked.title; value.timeline = checked.timeline; })) return false;
      setNotice('已在精确播放头拆分所选片段；一次撤销可恢复，需要明确保存。');
      return true;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '所选片段拆分无效。'); return false;
    }
  }
  function duplicateSelection(clipIds: readonly string[], offsetMs: number, newIds: SelectionDuplicateIds,
    revision: string, client: StudioProductionClient): boolean {
    if (blocked() || !latest.current.canMutate || failureRef.current || attemptRef.current?.state === 'UNKNOWN'
      || client !== latest.current.client || revision !== `${epoch.current}:${handoffGeneration.current}`) return false;
    try {
      const input = checkedTimelineDraft(cloneTimeline(draftRef.current));
      const operations = selectionDuplicateOperations(input.timeline, clipIds, offsetMs, newIds);
      // Mirror original clip.duplicate (strip outgoing relationship), then only
      // restore copied internal transitions. Validate the complete result once.
      for (const operation of operations) {
        if (operation.op === 'clip.duplicate') {
          const track = input.timeline.tracks.find(row => row.id === operation.track_id)!;
          const copied = cloneTimeline(track.clips.find(clip => clip.id === operation.clip_id)!);
          delete copied.transition_out;
          copied.id = operation.new_clip_id; copied.start_ms = operation.start_ms;
          track.clips.push(copied);
        } else {
          const copied = input.timeline.tracks.flatMap(track => track.clips).find(clip => clip.id === operation.clip_id)!;
          Object.assign(copied, cloneTimeline(operation.changes));
        }
      }
      const checked = checkedTimelineDraft(input);
      if (!change(value => { value.title = checked.title; value.timeline = checked.timeline; })) return false;
      setNotice('所选片段已整体复制到原轨道的本地草稿；仅复制选择内部转场，需要明确保存。');
      return true;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '整体复制无效，请核对所选片段与原轨道约束。'); return false;
    }
  }
  function moveSelection(clipIds: readonly string[], offsetMs: number, revision: string, client: StudioProductionClient): boolean {
    if (blocked() || !latest.current.canMutate || failureRef.current || attemptRef.current?.state === 'UNKNOWN'
      || client !== latest.current.client || revision !== `${epoch.current}:${handoffGeneration.current}`) return false;
    try {
      const input = checkedTimelineDraft(cloneTimeline(draftRef.current));
      const operations = selectionMoveOperations(input.timeline, clipIds, offsetMs);
      if (offsetMs === 0) return false;
      // One detached result: intermediate overlap is allowed by the original batch owner.
      for (const operation of operations) {
        const track = input.timeline.tracks.find(row => row.id === operation.track_id)!;
        track.clips.find(clip => clip.id === operation.clip_id)!.start_ms = operation.start_ms;
      }
      const checked = checkedTimelineDraft(input);
      if (!change(value => { value.title = checked.title; value.timeline = checked.timeline; })) return false;
      setNotice('所选片段已整体移动到本地草稿，保持各自原轨道；需要明确保存。');
      return true;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '整体移动无效，请核对所选片段与原轨道约束。'); return false;
    }
  }
  function trimClip(trackId: string, clipId: string, inMs: number, outMs: number, ripple: boolean,
    revision: string, client: StudioProductionClient): boolean {
    if (blocked() || !latest.current.canMutate || failureRef.current || attemptRef.current?.state === 'UNKNOWN'
      || client !== latest.current.client || revision !== `${epoch.current}:${handoffGeneration.current}`) return false;
    try {
      const input = checkedTimelineDraft(cloneTimeline(draftRef.current));
      const track = input.timeline.tracks.find(row => row.id === trackId), clip = track?.clips.find(row => row.id === clipId);
      if (!track || !clip) throw new Error('找不到原裁剪片段，请重新选择。');
      if (track.locked) throw new Error('该轨道已锁定，请先通过原服务明确解锁。');
      if (!Number.isSafeInteger(inMs) || !Number.isSafeInteger(outMs) || typeof ripple !== 'boolean') throw new Error('裁剪需要整数毫秒入出点与明确的波纹选择。');
      if (clip.in_ms === inMs && clip.out_ms === outMs) return false;
      const previous = timelineClipDuration(clip), boundary = clip.start_ms + previous;
      clip.in_ms = inMs; clip.out_ms = outMs;
      // Same semantics as original studio_timeline_edit.py clip.trim/shift:
      // only this track, at/after the OLD end, by the rendered duration delta.
      if (ripple) {
        const delta = timelineClipDuration(clip) - previous;
        track.clips.forEach(row => { if (row.id !== clip.id && row.start_ms >= boundary) row.start_ms += delta; });
      }
      const checked = checkedTimelineDraft(input);
      if (!change(value => { value.title = checked.title; value.timeline = checked.timeline; })) return false;
      setNotice('裁剪已更新本地草稿；波纹只移动本轨道原片段终点起的后续片段，需要明确保存。');
      return true;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '裁剪无效，请核对边界、淡入淡出与轨道重叠。'); return false;
    }
  }
  function slipOrRippleRemove(trackId: string, clipId: string, action: 'slip' | 'ripple-remove', offsetMs: number,
    ripple: boolean, revision: string, client: StudioProductionClient): boolean {
    if (blocked() || !latest.current.canMutate || failureRef.current || attemptRef.current?.state === 'UNKNOWN'
      || client !== latest.current.client || revision !== `${epoch.current}:${handoffGeneration.current}`) return false;
    try {
      const input = checkedTimelineDraft(cloneTimeline(draftRef.current));
      const track = input.timeline.tracks.find(row => row.id === trackId), clip = track?.clips.find(row => row.id === clipId);
      if (!track || !clip) throw new Error('找不到原片段，请重新选择。');
      if (track.locked) throw new Error('该轨道已锁定，请先通过原服务明确解锁。');
      if (action === 'slip') {
        if (clip.source_snapshot.asset_kind === 'image') throw new Error('静态画面没有可滑移的素材时间。');
        if (!Number.isSafeInteger(offsetMs)) throw new Error('滑移需要整数毫秒增量。');
        if (offsetMs === 0) return false;
        clip.in_ms += offsetMs; clip.out_ms += offsetMs;
      } else {
        if (ripple !== true) throw new Error('波纹删除需要明确确认闭合间隙。');
        if (track.clips.length <= 1) throw new Error('删除最后一个片段会留下空轨道；请先加入其他片段。');
        const duration = timelineClipDuration(clip), boundary = clip.start_ms + duration;
        track.clips = track.clips.filter(row => row.id !== clip.id);
        track.clips.forEach(row => { if (row.start_ms >= boundary) row.start_ms -= duration; });
      }
      // Validate the complete result before publishing one history entry. Never
      // repair dangling transitions or overlaps by silently changing neighbors.
      const checked = checkedTimelineDraft(input);
      if (!change(value => { value.title = checked.title; value.timeline = checked.timeline; })) return false;
      setNotice(action === 'slip' ? '滑移已更新本地草稿；摆放与时长保持不变，需要明确保存。'
        : '波纹删除已更新本地草稿；仅移动本轨道原片段终点起的后续片段，需要明确保存。');
      return true;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '片段编辑无效，请核对素材范围、转场与轨道重叠。'); return false;
    }
  }
  function createNew() {
    const unsaved = timelineInputKey(draftRef.current) !== baseline.current;
    if (blocked() || !latest.current.canMutate || failureRef.current || attemptRef.current?.state === 'UNKNOWN' || unsaved && consent.current.discard !== timelineInputKey(draftRef.current)) return;
    const input = newTimelineDraft(latest.current.mediaKind); handoffGeneration.current++; draftRef.current = input; baseRef.current = undefined; baseline.current = timelineInputKey(input); candidateRef.current = undefined;
    consent.current = { render: '', adopt: '', discard: '' };
    clearHistory();
    clearExportPreview();
    setDraft(input); setBase(undefined); setCandidate(undefined); setConfirmed(''); setAdoptConfirmed(false); setDiscardConfirmed(false); setError(''); setNotice('新时间线尚未保存。请添加素材与片段。');
  }
  function discardDraft() {
    if (blocked() || consent.current.discard !== timelineInputKey(draftRef.current) || timelineInputKey(draftRef.current) === baseline.current || failureRef.current || attemptRef.current?.state === 'UNKNOWN') return;
    const source = baseRef.current;
    const input = source ? { title: source.title, timeline: cloneTimeline(source.timeline) } : newTimelineDraft(latest.current.mediaKind);
    handoffGeneration.current++; draftRef.current = input; setDraft(input); baseline.current = timelineInputKey(input); setConfirmed(''); setAdoptConfirmed(false); setDiscardConfirmed(false); candidateRef.current = undefined; setCandidate(undefined);
    consent.current = { render: '', adopt: '', discard: '' };
    clearHistory();
    clearExportPreview();
    setNotice('仅已放弃本地编辑，没有请求删除或更改服务端时间线。');
  }
  async function save() {
    if (!latest.current.canMutate || failureRef.current || attemptRef.current?.state === 'UNKNOWN' || timelineInputKey(draftRef.current) === baseline.current && baseRef.current || blocked()) return;
    let input: StudioTimelineDraft;
    try { input = checkedTimelineDraft(cloneTimeline(draftRef.current)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : '时间线输入无效。'); return; }
    if (!timelineSourcesCurrent(input.timeline, latest.current.assets)) { setError('有素材版本已变化或不可用，请重新选择对应素材；不会采用旧快照。'); return; }
    const source = baseRef.current, request = begin('SAVE'); if (!request) return;
    setConfirmed(''); candidateRef.current = undefined; setCandidate(undefined);
    try {
      const saved = checkedTimelineRow(await latest.current.mutate(() => request.client.timelineSave(source?.id, { ...input, expected_version: source?.version ?? 0 })), source?.id);
      if (saved.version !== (source?.version ?? 0) + 1 || timelineInputKey({ title: saved.title, timeline: saved.timeline }) !== timelineInputKey(input)) throw new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: '保存回执的版本或内容与本次提交不一致，请读取核对。' });
      if (active(request)) { adopt(saved); setNotice('时间线已保存。核对这个版本的摘要与素材后，才能明确发起本地渲染。'); }
    } catch (reason) {
      if (active(request)) { const kind = timelineFailure(reason); failureRef.current = kind; setFailure(kind); handleError(reason, '时间线未确认保存，输入已保留。'); }
    } finally { finish(request); }
  }
  async function setTrackLocked(trackId: string, locked: boolean) {
    const source = baseRef.current, method = latest.current.client.timelineTrackLock;
    if (!source || !method || blocked() || !latest.current.canMutate || failureRef.current || attemptRef.current?.state === 'UNKNOWN'
      || timelineInputKey(draftRef.current) !== baseline.current || ![2, 3].includes(source.timeline.schema_version ?? 1)
      || !timelineSourcesCurrent(source.timeline, latest.current.assets)) return;
    const track = source.timeline.tracks.find(row => row.id === trackId);
    if (!track || (track.locked ?? false) === locked) return;
    const expected = cloneTimeline(source.timeline), target = expected.tracks.find(row => row.id === trackId)!; target.locked = locked;
    const requestId = crypto.randomUUID(), request = begin('TRACK_LOCK'); if (!request) return;
    try {
      const row = checkedTimelineRow(await latest.current.mutate(() => method(source, trackId, locked, requestId)), source.id);
      if (row.version !== source.version + 1 || row.title !== source.title
        || JSON.stringify(row.timeline) !== JSON.stringify(checkedTimeline(expected))) throw new ApiError({ status: 200,
          code: 'STUDIO_RESPONSE_INVALID', message: '轨道锁回执与原版本或本次动作不一致，请读取原时间线核对。' });
      if (active(request)) { adopt(row); setNotice(`轨道已通过原编辑服务${locked ? '锁定' : '明确解锁'}并保存新版本；本地撤销与重做已清空。`); }
    } catch (reason) {
      if (active(request)) { const kind = timelineFailure(reason); failureRef.current = kind; setFailure(kind);
        handleError(reason, `轨道锁请求 ${requestId} 尚未核对，请读取服务端；没有再次发送。`); }
    } finally { finish(request); }
  }
  async function render() {
    const source = baseRef.current;
    if (!source || source.timeline.schema_version === 3 || blocked() || !latest.current.canMutate || failureRef.current || timelineInputKey(draftRef.current) !== baseline.current || consent.current.render !== timelineBinding(source) || !timelineSourcesCurrent(source.timeline, latest.current.assets)) return;
    const binding = timelineBinding(source);
    if (reservedBindings.current.has(binding) || attemptRef.current?.state === 'UNKNOWN') return;
    const requestId = crypto.randomUUID(), request = begin('RENDER'); if (!request) return;
    const reserved: Attempt = { binding, requestId, state: 'UNKNOWN', snapshot: { id: source.id, version: source.version, digest: source.timeline_digest }, sources: timelineSources(source.timeline), timeline: cloneTimeline(source.timeline) };
    reservedBindings.current.add(binding); attemptRef.current = reserved; setAttempt(reserved); setConfirmed('');
    try {
      const job = await latest.current.mutate(() => request.client.timelineRender(source.id, { expected_version: source.version, reviewed_timeline_digest: source.timeline_digest, request_id: requestId }));
      if (active(request)) {
        checkedAttemptJob(job, reserved);
        const status = job.status;
        const result: Attempt = { ...reserved, requestDigest: job.request_digest, measurement: job.media_measurement, state: ['APPROVED', 'AWAITING_REVIEW', 'SUCCEEDED', 'FAILED', 'CANCELLED'].includes(status) ? 'RETURNED' : 'UNKNOWN' };
        attemptRef.current = result; setAttempt(result); latest.current.onJob(job);
        setNotice(status === 'SUCCEEDED' || status === 'AWAITING_REVIEW' ? '已取得原渲染任务回执，产物仍是私有候选，需要在制作任务中预览和人工审核。' : '已取得原任务状态。请在制作任务中核对，不会自动重复渲染相同快照。');
      }
    } catch (reason) {
      if (active(request)) {
        // An owner or authority guard can reject after its durable marker or
        // private candidate was written. Even a 4xx is not proof that this
        // dispatched request never executed; keep its original identity.
        handleError(reason, '渲染请求结果不明，请读取制作任务核对；原请求不会自动重发。');
      }
    } finally { finish(request); }
  }
  async function previewExport() {
    const source = baseRef.current, previewMethod = latest.current.client.timelineExportPreview;
    if (!source || !previewMethod || !latest.current.client.timelineExport || blocked() || !latest.current.canMutate || failureRef.current
      || timelineInputKey(draftRef.current) !== baseline.current || attemptRef.current?.state === 'UNKNOWN' || !timelineSourcesCurrent(source.timeline, latest.current.assets)) return;
    if (source.timeline.schema_version === 3 && source.timeline.duration_ms > AUDIO_TIMELINE_MAX_WAV_DURATION_MS) { setError('当前音频时间线超出固定 WAV 的 25 MiB 上限，请缩短至 136533 毫秒以内并保存。'); return; }
    let profile: TimelineExportProfile;
    try { profile = checkedTimelineExportProfile(exportRef.current.profile);
      if ((source.timeline.schema_version === 3) !== (profile.preset === 'AUDIO_WAV_PCM16')) throw new Error('导出格式与当前时间线媒体类型不一致。'); }
    catch (reason) { setError(reason instanceof Error ? reason.message : '导出配置无效。'); return; }
    const request = begin('EXPORT_PREVIEW'); if (!request) return;
    try {
      const value = checkedTimelineExportPreview(await latest.current.mutate(() => latest.current.read(() => previewMethod(source, profile))), source, profile);
      if (active(request)) {
        exportRef.current.preview = value; setExportPreview(value);
        setNotice('已核对导出配置、保存版本与素材摘要；尚未排队、渲染或产生媒体。');
      }
    } catch (reason) { if (active(request)) handleError(reason, '导出预览失败，没有发送渲染请求。'); }
    finally { finish(request); }
  }
  async function exportTimeline() {
    const source = baseRef.current, preview = exportRef.current.preview, exportMethod = latest.current.client.timelineExport;
    if (!source || !preview || !exportMethod || !latest.current.client.timelineExportPreview || blocked() || !latest.current.canMutate || failureRef.current
      || attemptRef.current?.state === 'UNKNOWN' || timelineInputKey(draftRef.current) !== baseline.current
      || !timelineSourcesCurrent(source.timeline, latest.current.assets) || exportRef.current.consent !== preview.preview_digest) return;
    let profile: TimelineExportProfile;
    try { profile = checkedTimelineExportProfile(exportRef.current.profile); checkedTimelineExportPreview(preview, source, profile); }
    catch (reason) { handleError(reason, '导出预览已变化，请重新核对。'); return; }
    const binding = `${timelineBinding(source)}:export:${timelineExportKey(profile)}`;
    if (reservedBindings.current.has(binding)) return;
    const requestId = crypto.randomUUID(), request = begin('EXPORT'); if (!request) return;
    const reserved: Attempt = { binding, requestId, state: 'UNKNOWN', snapshot: { id: source.id, version: source.version, digest: source.timeline_digest },
      sources: timelineSources(source.timeline), timeline: cloneTimeline(source.timeline), exportProfile: profile, recipeDigest: preview.execution_recipe.recipe_digest };
    reservedBindings.current.add(binding); attemptRef.current = reserved; setAttempt(reserved);
    try {
      const job = await latest.current.mutate(() => exportMethod(source, profile, requestId, preview.preview_digest));
      if (!active(request)) return;
      checkedAttemptJob(job, reserved);
      const result: Attempt = { ...reserved, requestDigest: job.request_digest, measurement: job.media_measurement,
        state: ['APPROVED', 'AWAITING_REVIEW', 'SUCCEEDED', 'FAILED', 'CANCELLED'].includes(job.status) ? 'RETURNED' : 'UNKNOWN' };
      attemptRef.current = result; setAttempt(result); latest.current.onJob(job);
      setNotice('已取得原导出任务回执。输出仍需从制作任务中核对实际候选、内容摘要并人工审核，才能成为正式素材。');
    } catch (reason) {
      if (active(request)) handleError(reason, '导出请求结果不明，原请求标识已保留；请手动读取原任务，不会创建替代请求。');
    } finally { finish(request); }
  }
  function checkedAttemptJob(job: StudioTimelineJob, source: Attempt) {
    const value = job as unknown as { timeline_snapshot?: unknown; sources?: unknown };
    const snapshot = value.timeline_snapshot as { id?: unknown; version?: unknown; digest?: unknown } | undefined;
    const sources = value.sources;
    if (job.owner !== 'timeline' || job.operation_id !== 'm9.timeline.multitrack' || job.request_id !== source.requestId
      || source.requestDigest && job.request_digest !== source.requestDigest
      || job.execution_recipe.adapter !== 'LOCAL_FFMPEG'
      || JSON.stringify(checkedTimeline(job.execution_recipe.timeline)) !== JSON.stringify(checkedTimeline(source.timeline))
      || source.exportProfile && (job.execution_recipe.recipe_digest !== source.recipeDigest || job.execution_recipe.output_profile !== source.exportProfile.preset
        || timelineExportKey(checkedTimelineExportProfile(job.execution_recipe.export_profile)) !== timelineExportKey(source.exportProfile))
      || !source.exportProfile && (job.execution_recipe.output_profile !== 'STUDIO_MULTITRACK_LOCAL_FFMPEG' || 'export_profile' in job.execution_recipe)
      || !snapshot || snapshot.id !== source.snapshot.id || snapshot.version !== source.snapshot.version || snapshot.digest !== source.snapshot.digest
      || !Array.isArray(sources) || sources.length !== source.sources.length || sources.some((raw, index) => {
        if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return true;
        const actual = raw as Record<string, unknown>, expected = source.sources[index];
        return ['id', 'kind', 'asset_kind', 'version', 'digest'].some(key => actual[key] !== expected[key as keyof StudioTimelineSource]);
      })) throw new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: '原渲染回执与确认的请求、时间线或素材快照不一致，继续保留未知状态。' });
  }
  async function checkRenderJob() {
    const source = attemptRef.current; if (!source) return;
    const request = begin('JOB'); if (!request) return;
    const abort = new AbortController(); reading.current = abort;
    try {
      const jobs = await latest.current.mutate(() => latest.current.read(() => request.client.list(abort.signal)));
      if (!active(request)) return;
      const matching = jobs.filter(job => job.owner === 'timeline' && job.request_id === source.requestId);
      if (!matching.length) { setNotice('当前读取未找到原渲染请求；这不证明请求失败，继续保留 UNKNOWN，不会创建替代请求。'); return; }
      if (matching.length !== 1) throw new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: '原请求对应多个任务，请从原制作任务核对。' });
      const job = matching[0]; checkedAttemptJob(job, source);
      const result: Attempt = { ...source, requestDigest: job.request_digest, measurement: job.media_measurement, state: ['APPROVED', 'AWAITING_REVIEW', 'SUCCEEDED', 'FAILED', 'CANCELLED'].includes(job.status) ? 'RETURNED' : 'UNKNOWN' };
      attemptRef.current = result; setAttempt(result); latest.current.onJob(job);
      setNotice(result.state === 'RETURNED' ? '已读取并绑定原请求的终态或候选回执。请在制作任务继续预览和审核；相同快照仍不会再次渲染。' : '已读取原任务，状态仍待核对；没有重新渲染或改变原任务。');
    } catch (reason) { if (active(request)) handleError(reason, '原渲染任务读取失败，未知状态与请求标识仍保留。'); }
    finally { if (reading.current === abort) reading.current = undefined; finish(request); }
  }
  const editRevision = `${epoch.current}:${handoffGeneration.current}`;
  return { draft: owns ? draft : undefined, base: owns ? base : undefined, rows: owns ? rows : [], candidate: owns ? candidate : undefined,
    failure: owns ? failure : undefined, attempt: owns ? attempt : undefined, error: owns ? error : '', notice: owns ? notice : '',
    denied: denied || !owns, pending, inputDirty, dirty, sourcesCurrent, canEdit, canRender, confirmed: confirmed === savedBinding,
    measuredSourceCount: currentMeasuredBounds().length, observeWaveformMeasurement,
    getHandoffRevision: () => `${epoch.current}:${handoffGeneration.current}`,
    adoptConfirmed, discardConfirmed, change, reload, checkServer, adoptCandidate, createNew, discardDraft, save, render, checkRenderJob,
    canUndo: canEdit && historySize.undo > 0, canRedo: canEdit && historySize.redo > 0,
    undo: () => travelHistory('undo'), redo: () => travelHistory('redo'),
    splitClip: (trackId: string, clipId: string, position: number) => editClip(trackId, clipId, 'split', position),
    duplicateClip: (trackId: string, clipId: string, position: number) => editClip(trackId, clipId, 'duplicate', position),
    moveClip: (trackId: string, clipId: string, targetId: string, position: number) => editClip(trackId, clipId, 'move', position, targetId),
    slipClip: (trackId: string, clipId: string, offsetMs: number) => slipOrRippleRemove(trackId, clipId, 'slip', offsetMs, false, editRevision, props.client),
    rippleRemoveClip: (trackId: string, clipId: string, ripple: boolean) => slipOrRippleRemove(trackId, clipId, 'ripple-remove', 0, ripple, editRevision, props.client),
    splitSelection: (clipIds: readonly string[], playheadMs: number, newIds: SelectionSplitIds) => splitSelection(clipIds, playheadMs, newIds, editRevision, props.client),
    duplicateSelection: (clipIds: readonly string[], offsetMs: number, newIds: SelectionDuplicateIds) => duplicateSelection(clipIds, offsetMs, newIds, editRevision, props.client),
    moveSelection: (clipIds: readonly string[], offsetMs: number) => moveSelection(clipIds, offsetMs, editRevision, props.client),
    trimClip: (trackId: string, clipId: string, inMs: number, outMs: number, ripple: boolean) => trimClip(trackId, clipId, inMs, outMs, ripple, editRevision, props.client),
    exportAvailable, exportProfile: owns ? exportProfile : { preset: 'REVIEW_MP4' } as TimelineExportProfile, exportPreview: owns ? exportPreview : undefined,
    exportConfirmed: owns && !!exportPreview && exportConfirmed === exportPreview.preview_digest, canPreviewExport, canExport,
    changeExportProfile, previewExport, exportTimeline, setTrackLocked, trackLockAvailable: !!props.client.timelineTrackLock,
    transfer, playback, sourceEdit,
    setExportConfirmed: (value: boolean) => {
      const source = baseRef.current, preview = exportRef.current.preview;
      if (blocked() || !source || !preview || !latest.current.canMutate || failureRef.current || attemptRef.current?.state === 'UNKNOWN'
        || timelineInputKey(draftRef.current) !== baseline.current || !timelineSourcesCurrent(source.timeline, latest.current.assets)) return;
      try { checkedTimelineExportPreview(preview, source, exportRef.current.profile); }
      catch { return; }
      exportRef.current.consent = value ? preview.preview_digest : ''; setExportConfirmed(exportRef.current.consent);
      if (value) latest.current.onDirtyChange(true);
    },
    upgradeTimeline: () => change(input => {
      if (input.timeline.schema_version === 2 || input.timeline.schema_version === 3) return;
      input.timeline.schema_version = 2;
      input.timeline.tracks.forEach(track => {
        track.role = track.kind === 'VIDEO' ? 'PRIMARY' : 'DIALOGUE';
        track.clips.forEach(clip => Object.assign(clip, { speed_num: 1, speed_den: 1, muted: false, gain_db: 0, fade_in_ms: 0, fade_out_ms: 0,
          ...(track.kind === 'VIDEO' ? { opacity: 1, include_audio: false } : {}) }));
      });
    }),
    setConfirmed: (value: boolean) => { if (!blocked() && baseRef.current && timelineInputKey(draftRef.current) === baseline.current) {
      consent.current.render = value ? timelineBinding(baseRef.current) : ''; setConfirmed(consent.current.render);
    } },
    setAdoptConfirmed: (value: boolean) => { if (!blocked() && candidateRef.current) { consent.current.adopt = value ? timelineBinding(candidateRef.current) : ''; setAdoptConfirmed(value); } },
    setDiscardConfirmed: (value: boolean) => { if (!blocked()) { consent.current.discard = value ? timelineInputKey(draftRef.current) : ''; setDiscardConfirmed(value); } } };
}
export type StudioTimelineEditorController = ReturnType<typeof useStudioTimelineEditor>;
