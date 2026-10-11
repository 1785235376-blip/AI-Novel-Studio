import { useEffect, useRef, useState } from 'react';
import { ApiError, apiErrorView } from '../api';
import type { StudioAsset } from './studioClient';
import type { StudioProductionClient } from './studioProductionClient';
import { checkedTimeline, checkedTimelineDraft, checkedTimelineList, checkedTimelineRow, cloneTimeline, newTimelineDraft, timelineBinding,
  timelineClipDuration, timelineFailure, timelineInputKey, timelineSources, timelineSourcesCurrent, type StudioTimeline, type StudioTimelineDraft, type StudioTimelineRow, type StudioTimelineSource } from './studioTimelineTypes';
import { checkedTimelineExportPreview, checkedTimelineExportProfile, timelineExportKey, type TimelineExportProfile, type TimelineExportPreview } from './studioTimelineExportTypes';

export type StudioTimelineJob = Awaited<ReturnType<StudioProductionClient['timelineRender']>>;
export type StudioTimelineEditorProps = {
  client: StudioProductionClient; assets: StudioAsset[]; canMutate: boolean; busy: boolean; isBusy?: () => boolean;
  isCurrent: () => boolean; read: <T>(work: () => Promise<T>) => Promise<T>; mutate: <T>(work: () => Promise<T>) => Promise<T>;
  onDirtyChange: (dirty: boolean) => void; onJob: (job: StudioTimelineJob) => void; onUnavailable: () => void;
};
type Operation = 'LIST' | 'GET' | 'SAVE' | 'RENDER' | 'JOB' | 'EXPORT_PREVIEW' | 'EXPORT';
type Attempt = { binding: string; requestId: string; state: 'UNKNOWN' | 'RETURNED'; requestDigest?: string;
  snapshot: { id: string; version: number; digest: string }; sources: StudioTimelineSource[]; timeline: StudioTimeline;
  exportProfile?: TimelineExportProfile; recipeDigest?: string; measurement?: StudioTimelineJob['media_measurement'] };

/** Owns the CAS/draft boundary; the presentation can be replaced independently. */
export function useStudioTimelineEditor(props: StudioTimelineEditorProps) {
  const [draft, setDraft] = useState<StudioTimelineDraft>(newTimelineDraft), [base, setBase] = useState<StudioTimelineRow>();
  const [rows, setRows] = useState<StudioTimelineRow[]>([]), [candidate, setCandidate] = useState<StudioTimelineRow>();
  const [pending, setPending] = useState<Operation>(), [failure, setFailure] = useState<'CONFLICT' | 'UNKNOWN'>();
  const [error, setError] = useState(''), [notice, setNotice] = useState(''), [denied, setDenied] = useState(false);
  const [confirmed, setConfirmed] = useState(''), [adoptConfirmed, setAdoptConfirmed] = useState(false), [discardConfirmed, setDiscardConfirmed] = useState(false);
  const [attempt, setAttempt] = useState<Attempt>();
  const [historySize, setHistorySize] = useState({ undo: 0, redo: 0 });
  const history = useRef<{ undo: StudioTimelineDraft[]; redo: StudioTimelineDraft[] }>({ undo: [], redo: [] });
  const [exportProfile, setExportProfile] = useState<TimelineExportProfile>({ preset: 'REVIEW_MP4' });
  const [exportPreview, setExportPreview] = useState<TimelineExportPreview>(), [exportConfirmed, setExportConfirmed] = useState('');
  const exportRef = useRef<{ profile: TimelineExportProfile; preview?: TimelineExportPreview; consent: string }>({ profile: exportProfile, consent: '' });
  const reservedBindings = useRef(new Set<string>());
  const latest = useRef(props); latest.current = props;
  const alive = useRef(true), epoch = useRef(0), owner = useRef(props.client), reading = useRef<AbortController>();
  const slot = useRef<{ epoch: number; operation: Operation }>(), started = useRef(false), deniedRef = useRef(false);
  const consent = useRef({ render: '', adopt: '', discard: '' });
  const draftRef = useRef(draft), baseRef = useRef(base), candidateRef = useRef(candidate), failureRef = useRef(failure), attemptRef = useRef(attempt);
  draftRef.current = draft; baseRef.current = base; candidateRef.current = candidate; failureRef.current = failure; attemptRef.current = attempt;
  const baseline = useRef(timelineInputKey(newTimelineDraft()));
  const current = () => alive.current && !deniedRef.current && owner.current === latest.current.client && latest.current.isCurrent();
  const blocked = () => !!slot.current || latest.current.busy || !!latest.current.isBusy?.() || !current();
  const owns = owner.current === props.client && props.isCurrent() && !denied;
  const inputDirty = timelineInputKey(draft) !== baseline.current;
  const uncertainRender = !!attempt && attempt.state === 'UNKNOWN';
  const dirty = owns && (inputDirty || !!failure || uncertainRender || !!exportConfirmed || pending === 'SAVE' || pending === 'RENDER' || pending === 'EXPORT' || pending === 'EXPORT_PREVIEW');
  const canEdit = owns && props.canMutate && !props.busy && !pending && !failure && !uncertainRender;
  const sourcesCurrent = timelineSourcesCurrent(draft.timeline, props.assets);
  const savedBinding = base ? timelineBinding(base) : '';
  const renderedThisSnapshot = reservedBindings.current.has(savedBinding);
  const canRender = canEdit && !!base && !inputDirty && confirmed === savedBinding && sourcesCurrent && !renderedThisSnapshot && !uncertainRender;
  let exportKey = ''; try { exportKey = timelineExportKey(exportProfile); } catch { /* The form may hold an incomplete number while editing. */ }
  const exportBinding = `${savedBinding}:export:${exportKey}`;
  const exportAvailable = !!props.client.timelineExportPreview && !!props.client.timelineExport;
  const canPreviewExport = canEdit && exportAvailable && !!base && !inputDirty && sourcesCurrent && !uncertainRender && !!exportKey;
  const canExport = canPreviewExport && !!exportPreview && exportConfirmed === exportPreview.preview_digest
    && exportPreview.timeline_snapshot.id === base?.id && exportPreview.timeline_snapshot.version === base?.version
    && exportPreview.timeline_snapshot.digest === base?.timeline_digest && !reservedBindings.current.has(exportBinding);

  useEffect(() => { alive.current = true; return () => {
    alive.current = false; epoch.current++; reading.current?.abort();
    if (slot.current?.operation === 'LIST') { slot.current = undefined; started.current = false; }
  }; }, []);
  useEffect(() => {
    owner.current = props.client; deniedRef.current = false; epoch.current++; reading.current?.abort(); reading.current = undefined; slot.current = undefined; started.current = false;
    const input = newTimelineDraft(); draftRef.current = input; baseRef.current = undefined; candidateRef.current = undefined; failureRef.current = undefined; attemptRef.current = undefined;
    baseline.current = timelineInputKey(input); setDraft(input); setBase(undefined); setRows([]); setCandidate(undefined); setFailure(undefined); setAttempt(undefined); setPending(undefined);
    consent.current = { render: '', adopt: '', discard: '' };
    clearHistory();
    reservedBindings.current.clear(); exportRef.current.profile = { preset: 'REVIEW_MP4' }; setExportProfile(exportRef.current.profile); clearExportPreview();
    setDenied(false); setError(''); setNotice(''); setConfirmed(''); setAdoptConfirmed(false); setDiscardConfirmed(false);
    return () => { epoch.current++; reading.current?.abort(); };
  }, [props.client]);
  useEffect(() => { props.onDirtyChange(dirty); }, [dirty, props.onDirtyChange]);
  useEffect(() => () => latest.current.onDirtyChange(false), []);
  useEffect(() => {
    // Automatic read only. StrictMode cleanup invalidates the first callback;
    // a replacement setup can make its own bounded list request.
    if (!started.current && !blocked()) { started.current = true; void reload(); }
  }, [props.client, props.busy]);

  function loseAuthority() {
    deniedRef.current = true; epoch.current++; reading.current?.abort(); slot.current = undefined;
    baseRef.current = undefined; candidateRef.current = undefined; failureRef.current = undefined; attemptRef.current = undefined;
    draftRef.current = newTimelineDraft(); baseline.current = timelineInputKey(draftRef.current);
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
    if (operation === 'SAVE' || operation === 'RENDER' || operation === 'EXPORT' || operation === 'EXPORT_PREVIEW') latest.current.onDirtyChange(true);
    return { ...value, client: latest.current.client };
  }
  function active(value: { epoch: number; client: StudioProductionClient }) { return current() && owner.current === value.client && slot.current?.epoch === value.epoch && epoch.current === value.epoch; }
  function finish(value: { epoch: number; client: StudioProductionClient }) {
    if (slot.current?.epoch === value.epoch) slot.current = undefined;
    if (current() && owner.current === value.client && epoch.current === value.epoch) setPending(undefined);
  }
  function adopt(row: StudioTimelineRow, keepDraft = false) {
    const input = keepDraft ? cloneTimeline(draftRef.current) : { title: row.title, timeline: cloneTimeline(row.timeline) };
    baseRef.current = row; draftRef.current = input; baseline.current = timelineInputKey({ title: row.title, timeline: row.timeline });
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
      if (active(request)) { setRows(list); setNotice('列表已读取；不会替换本地时间线。选择后读取并核对。'); }
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
  function change(work: (input: StudioTimelineDraft) => void) {
    if (blocked() || !latest.current.canMutate || failureRef.current || attemptRef.current?.state === 'UNKNOWN') return;
    const input = cloneTimeline(draftRef.current); work(input);
    if (timelineInputKey(input) === timelineInputKey(draftRef.current)) return;
    history.current.undo = [...history.current.undo.slice(-49), cloneTimeline(draftRef.current)]; history.current.redo = [];
    setHistorySize({ undo: history.current.undo.length, redo: 0 }); applyLocalInput(input);
  }
  function clearHistory() {
    history.current = { undo: [], redo: [] }; setHistorySize({ undo: 0, redo: 0 });
  }
  function clearExportPreview() {
    exportRef.current.preview = undefined; exportRef.current.consent = ''; setExportPreview(undefined); setExportConfirmed('');
  }
  function changeExportProfile(profile: TimelineExportProfile) {
    if (blocked() || !latest.current.canMutate || failureRef.current || attemptRef.current?.state === 'UNKNOWN') return;
    exportRef.current.profile = { ...profile }; setExportProfile(exportRef.current.profile); clearExportPreview(); setError(''); setNotice('');
  }
  function applyLocalInput(input: StudioTimelineDraft) {
    draftRef.current = input; setDraft(input);
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
        const offset = position - clip.start_ms, duration = timelineClipDuration(clip);
        if (offset <= 0 || offset >= duration) throw new Error('拆分位置必须位于片段的时间线范围内，保留两段有效长度。');
        const mediaOffset = offset * (clip.speed_num ?? 1) / (clip.speed_den ?? 1);
        if (!Number.isSafeInteger(mediaOffset)) throw new Error('此拆分位置不能按当前速度映射至整数毫秒的素材入点。');
        const right = { ...cloneTimeline(clip), id: crypto.randomUUID(), start_ms: position, in_ms: clip.in_ms + mediaOffset };
        if (clip.source_snapshot.asset_kind === 'image') { clip.out_ms = offset; right.in_ms = 0; right.out_ms = duration - offset; }
        else clip.out_ms = right.in_ms;
        if (input.timeline.schema_version === 2) { clip.fade_out_ms = 0; right.fade_in_ms = 0; }
        track.clips.push(right);
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
  function createNew() {
    const unsaved = timelineInputKey(draftRef.current) !== baseline.current;
    if (blocked() || !latest.current.canMutate || failureRef.current || attemptRef.current?.state === 'UNKNOWN' || unsaved && consent.current.discard !== timelineInputKey(draftRef.current)) return;
    const input = newTimelineDraft(); draftRef.current = input; baseRef.current = undefined; baseline.current = timelineInputKey(input); candidateRef.current = undefined;
    consent.current = { render: '', adopt: '', discard: '' };
    clearHistory();
    clearExportPreview();
    setDraft(input); setBase(undefined); setCandidate(undefined); setConfirmed(''); setAdoptConfirmed(false); setDiscardConfirmed(false); setError(''); setNotice('新时间线尚未保存。请添加素材与片段。');
  }
  function discardDraft() {
    if (blocked() || consent.current.discard !== timelineInputKey(draftRef.current) || timelineInputKey(draftRef.current) === baseline.current || failureRef.current || attemptRef.current?.state === 'UNKNOWN') return;
    const source = baseRef.current;
    const input = source ? { title: source.title, timeline: cloneTimeline(source.timeline) } : newTimelineDraft();
    draftRef.current = input; setDraft(input); baseline.current = timelineInputKey(input); setConfirmed(''); setAdoptConfirmed(false); setDiscardConfirmed(false); candidateRef.current = undefined; setCandidate(undefined);
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
  async function render() {
    const source = baseRef.current;
    if (!source || blocked() || !latest.current.canMutate || failureRef.current || timelineInputKey(draftRef.current) !== baseline.current || consent.current.render !== timelineBinding(source) || !timelineSourcesCurrent(source.timeline, latest.current.assets)) return;
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
    let profile: TimelineExportProfile;
    try { profile = checkedTimelineExportProfile(exportRef.current.profile); }
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
  return { draft: owns ? draft : undefined, base: owns ? base : undefined, rows: owns ? rows : [], candidate: owns ? candidate : undefined,
    failure: owns ? failure : undefined, attempt: owns ? attempt : undefined, error: owns ? error : '', notice: owns ? notice : '',
    denied: denied || !owns, pending, inputDirty, dirty, sourcesCurrent, canEdit, canRender, confirmed: confirmed === savedBinding,
    adoptConfirmed, discardConfirmed, change, reload, checkServer, adoptCandidate, createNew, discardDraft, save, render, checkRenderJob,
    canUndo: canEdit && historySize.undo > 0, canRedo: canEdit && historySize.redo > 0,
    undo: () => travelHistory('undo'), redo: () => travelHistory('redo'),
    splitClip: (trackId: string, clipId: string, position: number) => editClip(trackId, clipId, 'split', position),
    duplicateClip: (trackId: string, clipId: string, position: number) => editClip(trackId, clipId, 'duplicate', position),
    moveClip: (trackId: string, clipId: string, targetId: string, position: number) => editClip(trackId, clipId, 'move', position, targetId),
    exportAvailable, exportProfile: owns ? exportProfile : { preset: 'REVIEW_MP4' } as TimelineExportProfile, exportPreview: owns ? exportPreview : undefined,
    exportConfirmed: owns && !!exportPreview && exportConfirmed === exportPreview.preview_digest, canPreviewExport, canExport,
    changeExportProfile, previewExport, exportTimeline,
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
      if (input.timeline.schema_version === 2) return;
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
