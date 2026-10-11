import { useEffect, useRef, useState } from 'react';
import { ApiError, apiErrorView } from '../api';
import type { StudioAsset } from './studioClient';
import type { StudioProductionClient } from './studioProductionClient';
import { checkedTimelineDraft, checkedTimelineList, checkedTimelineRow, cloneTimeline, newTimelineDraft, timelineBinding,
  timelineFailure, timelineInputKey, timelineSources, timelineSourcesCurrent, type StudioTimelineDraft, type StudioTimelineRow, type StudioTimelineSource } from './studioTimelineTypes';

export type StudioTimelineJob = Awaited<ReturnType<StudioProductionClient['timelineRender']>>;
export type StudioTimelineEditorProps = {
  client: StudioProductionClient; assets: StudioAsset[]; canMutate: boolean; busy: boolean; isBusy?: () => boolean;
  isCurrent: () => boolean; read: <T>(work: () => Promise<T>) => Promise<T>; mutate: <T>(work: () => Promise<T>) => Promise<T>;
  onDirtyChange: (dirty: boolean) => void; onJob: (job: StudioTimelineJob) => void; onUnavailable: () => void;
};
type Operation = 'LIST' | 'GET' | 'SAVE' | 'RENDER' | 'JOB';
type Attempt = { binding: string; requestId: string; state: 'UNKNOWN' | 'RETURNED'; requestDigest?: string;
  snapshot: { id: string; version: number; digest: string }; sources: StudioTimelineSource[] };

/** Owns the CAS/draft boundary; the presentation can be replaced independently. */
export function useStudioTimelineEditor(props: StudioTimelineEditorProps) {
  const [draft, setDraft] = useState<StudioTimelineDraft>(newTimelineDraft), [base, setBase] = useState<StudioTimelineRow>();
  const [rows, setRows] = useState<StudioTimelineRow[]>([]), [candidate, setCandidate] = useState<StudioTimelineRow>();
  const [pending, setPending] = useState<Operation>(), [failure, setFailure] = useState<'CONFLICT' | 'UNKNOWN'>();
  const [error, setError] = useState(''), [notice, setNotice] = useState(''), [denied, setDenied] = useState(false);
  const [confirmed, setConfirmed] = useState(''), [adoptConfirmed, setAdoptConfirmed] = useState(false), [discardConfirmed, setDiscardConfirmed] = useState(false);
  const [attempt, setAttempt] = useState<Attempt>();
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
  const dirty = owns && (inputDirty || !!failure || uncertainRender || pending === 'SAVE' || pending === 'RENDER');
  const canEdit = owns && props.canMutate && !props.busy && !pending && !failure;
  const sourcesCurrent = timelineSourcesCurrent(draft.timeline, props.assets);
  const savedBinding = base ? timelineBinding(base) : '';
  const renderedThisSnapshot = !!attempt && attempt.binding === savedBinding;
  const canRender = canEdit && !!base && !inputDirty && confirmed === savedBinding && sourcesCurrent && !renderedThisSnapshot && !uncertainRender;

  useEffect(() => { alive.current = true; return () => {
    alive.current = false; epoch.current++; reading.current?.abort();
    if (slot.current?.operation === 'LIST') { slot.current = undefined; started.current = false; }
  }; }, []);
  useEffect(() => {
    owner.current = props.client; deniedRef.current = false; epoch.current++; reading.current?.abort(); reading.current = undefined; slot.current = undefined; started.current = false;
    const input = newTimelineDraft(); draftRef.current = input; baseRef.current = undefined; candidateRef.current = undefined; failureRef.current = undefined; attemptRef.current = undefined;
    baseline.current = timelineInputKey(input); setDraft(input); setBase(undefined); setRows([]); setCandidate(undefined); setFailure(undefined); setAttempt(undefined); setPending(undefined);
    consent.current = { render: '', adopt: '', discard: '' };
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
    setPending(operation); setError(''); setNotice(''); setConfirmed(''); setAdoptConfirmed(false); setDiscardConfirmed(false);
    if (operation === 'SAVE' || operation === 'RENDER') latest.current.onDirtyChange(true);
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
    if (!row || consent.current.adopt !== timelineBinding(row) || blocked() || keepDraft && !latest.current.canMutate) return;
    adopt(row, keepDraft);
    setNotice(keepDraft ? '输入保留，基于读取的版本继续编辑；需要你明确再次保存。' : '已采用读取的服务端时间线；没有再次保存或渲染。');
  }
  function change(work: (input: StudioTimelineDraft) => void) {
    if (blocked() || !latest.current.canMutate || failureRef.current) return;
    const input = cloneTimeline(draftRef.current); work(input); draftRef.current = input; setDraft(input);
    consent.current = { render: '', adopt: '', discard: '' };
    candidateRef.current = undefined; setCandidate(undefined); setConfirmed(''); setAdoptConfirmed(false); setDiscardConfirmed(false); setError(''); setNotice('');
    latest.current.onDirtyChange(true);
  }
  function createNew() {
    const unsaved = timelineInputKey(draftRef.current) !== baseline.current;
    if (blocked() || !latest.current.canMutate || failureRef.current || attemptRef.current?.state === 'UNKNOWN' || unsaved && consent.current.discard !== timelineInputKey(draftRef.current)) return;
    const input = newTimelineDraft(); draftRef.current = input; baseRef.current = undefined; baseline.current = timelineInputKey(input); candidateRef.current = undefined;
    consent.current = { render: '', adopt: '', discard: '' };
    setDraft(input); setBase(undefined); setCandidate(undefined); setConfirmed(''); setAdoptConfirmed(false); setDiscardConfirmed(false); setError(''); setNotice('新时间线尚未保存。请添加素材与片段。');
  }
  function discardDraft() {
    if (blocked() || consent.current.discard !== timelineInputKey(draftRef.current) || timelineInputKey(draftRef.current) === baseline.current || failureRef.current) return;
    const source = baseRef.current;
    const input = source ? { title: source.title, timeline: cloneTimeline(source.timeline) } : newTimelineDraft();
    draftRef.current = input; setDraft(input); baseline.current = timelineInputKey(input); setConfirmed(''); setAdoptConfirmed(false); setDiscardConfirmed(false); candidateRef.current = undefined; setCandidate(undefined);
    consent.current = { render: '', adopt: '', discard: '' };
    setNotice('仅已放弃本地编辑，没有请求删除或更改服务端时间线。');
  }
  async function save() {
    if (!latest.current.canMutate || failureRef.current || timelineInputKey(draftRef.current) === baseline.current && baseRef.current || blocked()) return;
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
    if (attemptRef.current?.binding === binding || attemptRef.current?.state === 'UNKNOWN') return;
    const requestId = crypto.randomUUID(), request = begin('RENDER'); if (!request) return;
    const reserved: Attempt = { binding, requestId, state: 'UNKNOWN', snapshot: { id: source.id, version: source.version, digest: source.timeline_digest }, sources: timelineSources(source.timeline) };
    attemptRef.current = reserved; setAttempt(reserved); setConfirmed('');
    try {
      const job = await latest.current.mutate(() => request.client.timelineRender(source.id, { expected_version: source.version, reviewed_timeline_digest: source.timeline_digest, request_id: requestId }));
      if (active(request)) {
        checkedAttemptJob(job, reserved);
        const status = job.status;
        const result: Attempt = { ...reserved, requestDigest: job.request_digest, state: ['APPROVED', 'AWAITING_REVIEW', 'SUCCEEDED', 'FAILED', 'CANCELLED'].includes(status) ? 'RETURNED' : 'UNKNOWN' };
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
  function checkedAttemptJob(job: StudioTimelineJob, source: Attempt) {
    const value = job as unknown as { timeline_snapshot?: unknown; sources?: unknown };
    const snapshot = value.timeline_snapshot as { id?: unknown; version?: unknown; digest?: unknown } | undefined;
    const sources = value.sources;
    if (job.owner !== 'timeline' || job.operation_id !== 'm9.timeline.multitrack' || job.request_id !== source.requestId
      || source.requestDigest && job.request_digest !== source.requestDigest
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
      const result: Attempt = { ...source, requestDigest: job.request_digest, state: ['APPROVED', 'AWAITING_REVIEW', 'SUCCEEDED', 'FAILED', 'CANCELLED'].includes(job.status) ? 'RETURNED' : 'UNKNOWN' };
      attemptRef.current = result; setAttempt(result); latest.current.onJob(job);
      setNotice(result.state === 'RETURNED' ? '已读取并绑定原请求的终态或候选回执。请在制作任务继续预览和审核；相同快照仍不会再次渲染。' : '已读取原任务，状态仍待核对；没有重新渲染或改变原任务。');
    } catch (reason) { if (active(request)) handleError(reason, '原渲染任务读取失败，未知状态与请求标识仍保留。'); }
    finally { if (reading.current === abort) reading.current = undefined; finish(request); }
  }
  return { draft: owns ? draft : undefined, base: owns ? base : undefined, rows: owns ? rows : [], candidate: owns ? candidate : undefined,
    failure: owns ? failure : undefined, attempt: owns ? attempt : undefined, error: owns ? error : '', notice: owns ? notice : '',
    denied: denied || !owns, pending, inputDirty, dirty, sourcesCurrent, canEdit, canRender, confirmed: confirmed === savedBinding,
    adoptConfirmed, discardConfirmed, change, reload, checkServer, adoptCandidate, createNew, discardDraft, save, render, checkRenderJob,
    setConfirmed: (value: boolean) => { if (!blocked() && baseRef.current && timelineInputKey(draftRef.current) === baseline.current) {
      consent.current.render = value ? timelineBinding(baseRef.current) : ''; setConfirmed(consent.current.render);
    } },
    setAdoptConfirmed: (value: boolean) => { if (!blocked() && candidateRef.current) { consent.current.adopt = value ? timelineBinding(candidateRef.current) : ''; setAdoptConfirmed(value); } },
    setDiscardConfirmed: (value: boolean) => { if (!blocked()) { consent.current.discard = value ? timelineInputKey(draftRef.current) : ''; setDiscardConfirmed(value); } } };
}
export type StudioTimelineEditorController = ReturnType<typeof useStudioTimelineEditor>;
