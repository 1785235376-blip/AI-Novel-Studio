import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import { ApiError, apiErrorView } from '../api';
import type { ComicTimelineHandoffHost } from '../experimental/ComicLayoutsPanel';
import type { ComicRecord } from '../experimental/comicLayoutsClient';
import { Field } from '../experimental/shared';
import { Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import { clearComicHandoffAttempt, readComicHandoffAttempt, saveComicHandoffAttempt } from './comicHandoffAttempt';
import { checkedHandoffRequest, handoffCanonical, type HandoffConfirm, type HandoffReceipt, type HandoffReport, type HandoffRequest, type StudioComicHandoffClient } from './studioComicHandoffClient';

type Props = ComicTimelineHandoffHost & { client: StudioComicHandoffClient; canMutate: boolean; onDenied?: () => void };
type Selection = { page: ComicRecord; duration: string };
type Form = { title: string; selected: Selection[]; width: string; height: string; fps: string };
type Preview = { generation: number; report: HandoffReport; urls: string[]; loaded: number[]; failed: boolean };
const empty = (): Form => ({ title: '漫画静态页草稿', selected: [], width: '1280', height: '720', fps: '24' });
const eligible = (page: ComicRecord) => page.status === 'APPROVED' && !page.stale && Number.isSafeInteger(page.version) && page.version > 0
  && page.document?.source_mode === 'INDEPENDENT' && page.document.preset === 'PAGE';
let nextScope = 0;
export function StudioComicTimelineHandoff(props: Props) {
  const scope = useMemo(() => ++nextScope, [props.client]);
  return <HandoffContent key={scope} {...props} />;
}
function HandoffContent(props: Props) {
  const initial = useMemo(() => {
    try { return { attempt: readComicHandoffAttempt(props.client.ownerKey), error: '' }; }
    catch (error) { return { attempt: undefined, error: apiErrorView(error, '无法读取交接恢复标识。').message }; }
  }, []);
  const [form, setForm] = useState<Form>(empty), formRef = useRef(form); formRef.current = form;
  const [attempt, setAttempt] = useState(initial.attempt), attemptRef = useRef(attempt); attemptRef.current = attempt;
  const [receipt, setReceipt] = useState<HandoffReceipt>(), receiptRef = useRef(receipt); receiptRef.current = receipt;
  const [preview, setPreview] = useState<Preview>(), previewRef = useRef(preview); previewRef.current = preview;
  const [busy, setBusy] = useState(false), [error, setError] = useState(initial.error), [denied, setDenied] = useState(false);
  const [versions, setVersions] = useState(false), [losses, setLosses] = useState(false), ack = useRef({ versions, losses }); ack.current = { versions, losses };
  const [cancelAck, setCancelAck] = useState(false), [retryAck, setRetryAck] = useState(false), [notFound, setNotFound] = useState(false);
  const [recoverId, setRecoverId] = useState(''), [unknown, setUnknown] = useState(!!attempt), [paused, setPaused] = useState(false);
  const composing = useRef(false), [isComposing, setIsComposing] = useState(false);
  const latest = useRef(props); latest.current = props;
  const alive = useRef(true), epoch = useRef(0), serial = useRef(0);
  type Operation = { id: number; epoch: number; ownerRevision: number };
  const slot = useRef<Operation>();
  const external = JSON.stringify([props.disabled, props.isCurrent(), props.getOwnerRevision(), props.canMutate,
    props.records.map(p => [p.id, p.version, p.status, p.stale, p.document])]);
  const prior = useRef(external);
  if (prior.current !== external) { prior.current = external; epoch.current++; }
  const renderEpoch = epoch.current;
  const current = () => alive.current && !denied && latest.current.isCurrent() && !latest.current.disabled;
  const admit = () => renderEpoch === epoch.current && current() && !slot.current;
  const active = (op: Operation) => slot.current === op && op.epoch === epoch.current && op.ownerRevision === latest.current.getOwnerRevision() && current();
  const dirty = !paused && (!!attempt || !!recoverId || handoffCanonical(form) !== handoffCanonical(empty()) || !!preview);
  const dropPreview = () => {
    previewRef.current?.urls.forEach(URL.revokeObjectURL); previewRef.current = undefined; setPreview(undefined);
    ack.current = { versions: false, losses: false }; setVersions(false); setLosses(false); setRetryAck(false); setCancelAck(false);
  };
  useLayoutEffect(() => { alive.current = true; return () => {
    alive.current = false; epoch.current++; slot.current = undefined;
    previewRef.current?.urls.forEach(URL.revokeObjectURL);
    props.onDirtyChange(false); props.onBusyChange(false);
  }; }, []);
  useLayoutEffect(() => { latest.current.onDirtyChange(dirty); }, [dirty]);
  useLayoutEffect(() => {
    slot.current = undefined; setBusy(false); latest.current.onBusyChange(false); dropPreview();
  }, [external]);
  function begin(advance = false): Operation | undefined {
    if (!admit() || composing.current) return;
    if (advance) { epoch.current++; dropPreview(); }
    const op = { id: ++serial.current, epoch: epoch.current, ownerRevision: latest.current.getOwnerRevision() };
    slot.current = op; setBusy(true); props.onBusyChange(true); setError(''); return op;
  }
  function finish(op: Operation) {
    if (!alive.current || slot.current !== op) return;
    slot.current = undefined; setBusy(false); latest.current.onBusyChange(false);
  }
  function failure(reason: unknown, op: Operation) {
    if (!active(op)) return;
    setError(apiErrorView(reason, '交接未完成。请保留原请求 ID，读回核对。').message);
    if (reason instanceof ApiError && [401, 403].includes(reason.status)) { setDenied(true); latest.current.onDenied?.(); }
  }
  function change(update: Partial<Form>) {
    if (!admit() || attemptRef.current) return;
    epoch.current++; dropPreview(); const next = { ...formRef.current, ...update }; formRef.current = next; setForm(next); setError('');
    latest.current.onDirtyChange(handoffCanonical(next) !== handoffCanonical(empty()));
  }
  const sourceCurrent = (item: Selection) => props.records.some(p => p.id === item.page.id && eligible(p)
    && p.version === item.page.version && handoffCanonical(p.document) === handoffCanonical(item.page.document));
  const shownPreview = preview?.generation === epoch.current && current() && !paused ? preview : undefined;
  const loaded = !!shownPreview && !shownPreview.failed && shownPreview.loaded.length === shownPreview.urls.length;
  const locked = busy || !current() || paused;
  async function prepare() {
    if (!admit() || paused || initial.error || receiptRef.current?.status === 'DRAFT_CREATED' || receiptRef.current?.status === 'CANCELLED') return;
    const op = begin(true); if (!op) return;
    try {
      const frozen = attemptRef.current;
      const selected = frozen ? frozen.request.pages.map(pin => {
        const page = latest.current.records.find(p => p.id === pin.id && p.version === pin.version && eligible(p));
        if (!page) throw new Error('原请求的已审核页面版本已变化。请读回并核对原请求，保留已写入素材。');
        return { page, duration: String(pin.duration_ms) };
      }) : formRef.current.selected;
      if (selected.length < 1 || selected.length > 4 || selected.some(item => !sourceCurrent(item))) throw new Error('请明确选择一至四个当前已审核 PAGE。');
      const reports = await Promise.all(selected.map(item => props.preflight(item.page)));
      if (!active(op)) return;
      const request = checkedHandoffRequest({ title: formRef.current.title, width: Number(formRef.current.width), height: Number(formRef.current.height), fps: Number(formRef.current.fps),
        pages: selected.map((item, i) => {
          const report = reports[i];
          if (report.can_render !== true || report.version !== item.page.version || report.status !== 'APPROVED' || !/^[a-f0-9]{64}$/.test(report.review_digest)) throw new Error('页面审核或版本未通过核对，请重新打开原记录。');
          return { id: item.page.id, version: item.page.version, review_digest: report.review_digest, duration_ms: Number(item.duration) };
        }) });
      if (frozen && handoffCanonical(request.pages) !== handoffCanonical(frozen.request.pages)) throw new Error('原请求页面审核已变化，不能重发或恢复。');
      const result = await props.client.preview(frozen ? frozen.request : request);
      if (!active(op)) return;
      if (frozen && result.report.preview_digest !== frozen.reviewed_preview_digest) throw new Error('原预览已变化，请读回原请求状态。');
      const urls: string[] = [];
      try { result.images.forEach(image => urls.push(URL.createObjectURL(image))); }
      catch (reason) { urls.forEach(URL.revokeObjectURL); throw reason; }
      const next = { generation: epoch.current, report: result.report, urls, loaded: [], failed: false };
      previewRef.current = next; setPreview(next);
    } catch (reason) { failure(reason, op); }
    finally { finish(op); }
  }
  function applyReceipt(value: HandoffReceipt) {
    epoch.current++; dropPreview(); receiptRef.current = value; setReceipt(value); setUnknown(false); setNotFound(false);
  }
  async function readBack() {
    const id = attemptRef.current?.request_id || recoverId.trim();
    if (!admit() || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$/.test(id)) return;
    const op = begin(true); if (!op) return;
    try {
      const result = await props.client.status(id, attemptRef.current);
      if (!active(op)) return;
      const frozen: HandoffConfirm = attemptRef.current || { request_id: id, request: result.preview.request,
        reviewed_preview_digest: result.preview.preview_digest, acknowledge_losses: true };
      saveComicHandoffAttempt(props.client.ownerKey, frozen); attemptRef.current = frozen; setAttempt(frozen); setPaused(false);
      applyReceipt(result);
    } catch (reason) {
      if (active(op) && reason instanceof ApiError && reason.status === 404) { setNotFound(true); setUnknown(true); }
      failure(reason, op);
    } finally { finish(op); }
  }
  async function mutate(kind: 'confirm' | 'resume' | 'cancel') {
    if (!admit() || !props.canMutate || initial.error || paused) return;
    const shown = previewRef.current;
    const verified = shown && shown.generation === epoch.current && !shown.failed && shown.loaded.length === shown.urls.length && ack.current.versions && ack.current.losses;
    const prior = attemptRef.current, observed = receiptRef.current;
    if (kind === 'cancel' ? !prior || observed?.status !== 'PLANNED' || !cancelAck
      : !verified || kind === 'resume' && (!prior || observed?.status !== 'PLANNED')
        || kind === 'confirm' && prior && (!notFound || !retryAck || observed)) return;
    const frozen: HandoffConfirm = prior || { request_id: crypto.randomUUID(), request: shown!.report.request,
      reviewed_preview_digest: shown!.report.preview_digest, acknowledge_losses: true };
    if (kind !== 'cancel' && shown!.report.preview_digest !== frozen.reviewed_preview_digest) return;
    const op = begin(); if (!op) return;
    try {
      // Persist exact immutable intent before the first POST. Every failure,
      // including invalid HTTP 200, leaves this ID available for readback.
      saveComicHandoffAttempt(props.client.ownerKey, frozen); attemptRef.current = frozen; setAttempt(frozen);
      receiptRef.current = undefined; setReceipt(undefined); setUnknown(true); setNotFound(false); setRetryAck(false); setCancelAck(false);
      const result = kind === 'confirm' ? await props.client.confirm(frozen)
        : kind === 'resume' ? await props.client.resume(frozen, observed!.version) : await props.client.cancel(frozen, observed!.version);
      if (active(op)) applyReceipt(result);
    } catch (reason) { failure(reason, op); }
    finally { finish(op); }
  }
  function close() {
    if (!alive.current || slot.current) return;
    try {
      if (attemptRef.current && receiptRef.current && receiptRef.current.status !== 'PLANNED') {
        clearComicHandoffAttempt(props.client.ownerKey, attemptRef.current.request_id); attemptRef.current = undefined; setAttempt(undefined); receiptRef.current = undefined; setReceipt(undefined); setUnknown(false);
      }
      epoch.current++; dropPreview(); formRef.current = empty(); setForm(formRef.current); setRecoverId(''); setPaused(!!attemptRef.current); setError(''); props.onDirtyChange(false);
    } catch (reason) { setError(apiErrorView(reason, '无法核对恢复标识，请保留原请求 ID。').message); }
  }
  function stopWaiting() {
    if (!alive.current || !slot.current) return;
    epoch.current++; slot.current = undefined; dropPreview(); setBusy(false); latest.current.onBusyChange(false);
    if (attemptRef.current) { setUnknown(true); setNotFound(false); }
    setError(attemptRef.current ? '已停止等待，未取消服务端写入。请保留原请求 ID 并读回核对。' : '已停止等待本次检查，预览已失效。');
  }
  function imageLoaded(index: number, element: HTMLImageElement, generation: number, failed = false) {
    const view = previewRef.current;
    if (!admit() || !view || view.generation !== generation || epoch.current !== generation) return;
    const pin = view.report.pages[index];
    const valid = !failed && element.naturalWidth === pin.width && element.naturalHeight === pin.height;
    const next = { ...view, failed: view.failed || !valid, loaded: valid ? [...new Set([...view.loaded, index])] : view.loaded };
    previewRef.current = next; setPreview(next);
    if (!valid) { ack.current = { versions: false, losses: false }; setVersions(false); setLosses(false); }
  }
  const networkLocked = locked || isComposing;
  return <Panel title="整页交接到 Timeline 草稿" data-comic-timeline-handoff
    onCompositionStartCapture={() => { if (!slot.current && alive.current) { composing.current = true; setIsComposing(true); epoch.current++; dropPreview(); } }}
    onCompositionEndCapture={() => { composing.current = false; setIsComposing(false); }}>
    <p>按顺序把一至四个已审核独立 PAGE 复制为静态 PNG 素材，并创建原 Timeline 草稿。分格、文字和图层会合并；不包含运动或音频，不继承批准，也不会渲染视频。</p>
    {(props.disabled || denied) && <StatusMessage tone="warning">请先保存或明确放弃原编辑器修改，并核对当前来源和权限。交接预览已失效。</StatusMessage>}
    {!props.canMutate && <StatusMessage>当前权限可检查或读回交接；创建、恢复和取消需要原项目写权限。</StatusMessage>}
    {busy && <><StatusMessage>正在核对交接请求，请等待当前操作完成。</StatusMessage><Button onClick={stopWaiting}>{attempt ? '停止等待并保留原请求 ID' : '停止等待当前检查'}</Button></>}
    {error && <StatusMessage tone="error">{error}</StatusMessage>}
    {paused && attempt && <><StatusMessage>已保留原请求 {attempt.request_id}。重新打开只会核对该请求。</StatusMessage><Button disabled={!current() || busy} onClick={() => { if (admit()) { epoch.current++; setPaused(false); setUnknown(true); } }}>继续核对原交接</Button></>}
    {!paused && <>
      {!attempt && <fieldset disabled={locked || !!initial.error} className="experimental-form">
        <legend>明确选择交接顺序</legend>
        {!props.records.some(eligible) && <EmptyState title="暂无可交接的已审核 PAGE" detail="请先在原漫画编辑器保存、预览并审核独立页面。" />}
        {props.records.filter(eligible).map(page => <label className="experimental-check" key={page.id}><input type="checkbox" checked={form.selected.some(p => p.page.id === page.id)} disabled={locked || form.selected.length >= 4 && !form.selected.some(p => p.page.id === page.id)} onChange={event => change({ selected: event.target.checked ? [...formRef.current.selected, { page, duration: '5000' }] : formRef.current.selected.filter(p => p.page.id !== page.id) })} />{page.document!.title} · v{page.version} · {page.id}</label>)}
        <ol>{form.selected.map((item, index) => <li key={item.page.id}>{item.page.document!.title} · v{item.page.version}{!sourceCurrent(item) && '（来源已变化）'}
          <Field label={`第 ${index + 1} 页停留时长（毫秒）`}><input type="number" min={1} max={600000} step={1} value={item.duration} onChange={event => change({ selected: formRef.current.selected.map((p, i) => i === index ? { ...p, duration: event.target.value } : p) })} /></Field>
          <Button disabled={locked || index === 0} onClick={() => { const selected = [...formRef.current.selected]; [selected[index - 1], selected[index]] = [selected[index], selected[index - 1]]; change({ selected }); }}>上移第 {index + 1} 页</Button>
          <Button disabled={locked || index === form.selected.length - 1} onClick={() => { const selected = [...formRef.current.selected]; [selected[index], selected[index + 1]] = [selected[index + 1], selected[index]]; change({ selected }); }}>下移第 {index + 1} 页</Button>
          <Button disabled={locked} onClick={() => change({ selected: formRef.current.selected.filter((_, i) => i !== index) })}>移除第 {index + 1} 页</Button>
        </li>)}</ol>
        <Field label="Timeline 草稿标题"><input value={form.title} maxLength={200} onChange={event => change({ title: event.target.value })} /></Field>
        <div className="experimental-grid">{(['width', 'height', 'fps'] as const).map((key, index) => <Field key={key} label={['输出宽度', '输出高度', '帧率'][index]}><input type="number" min={key === 'fps' ? 1 : 16} max={key === 'width' ? 1920 : key === 'height' ? 1080 : 60} step={key === 'fps' ? 1 : 2} value={form[key]} onChange={event => change({ [key]: event.target.value })} /></Field>)}</div>
      </fieldset>}
      {(!receipt || receipt.status === 'PLANNED') && <Button disabled={networkLocked || !!initial.error || !attempt && !form.selected.length} onClick={() => void prepare()}>{attempt ? '重新核对原请求整页预览' : '检查并加载整页预览'}</Button>}
      {shownPreview && <><ol>{shownPreview.report.pages.map((pin, index) => <li key={pin.source.id}>第 {index + 1} 页 · {pin.source.id} · v{pin.source.version} · {pin.duration_ms} 毫秒 · {pin.width} × {pin.height}
        <img className="comic-source-preview" src={shownPreview.urls[index]} alt={`交接整页预览 ${index + 1}`} onLoad={event => imageLoaded(index, event.currentTarget, shownPreview.generation)} onError={event => imageLoaded(index, event.currentTarget, shownPreview.generation, true)} />
      </li>)}</ol>{shownPreview.failed && <StatusMessage tone="error">整页图片未完整载入或尺寸不符，请重新检查预览。</StatusMessage>}
        <label className="experimental-check"><input type="checkbox" disabled={locked || !loaded} checked={versions} onChange={event => { if (admit() && loaded) { ack.current.versions = event.target.checked; setVersions(event.target.checked); } }} />已查看全部整页图片，核对页面版本、顺序和逐页时长</label>
        <label className="experimental-check"><input type="checkbox" disabled={locked || !loaded} checked={losses} onChange={event => { if (admit() && loaded) { ack.current.losses = event.target.checked; setLosses(event.target.checked); } }} />确认静态整页合并损失，只创建未批准的 Timeline 草稿</label>
      </>}
      {!attempt && <Button variant="primary" disabled={networkLocked || !props.canMutate || !loaded || !versions || !losses} onClick={() => void mutate('confirm')}>明确创建原 Timeline 草稿</Button>}
      {!attempt && <Field label="已有交接请求 ID"><input maxLength={80} value={recoverId} disabled={locked} onChange={event => { if (!admit()) return; epoch.current++; dropPreview(); setRecoverId(event.target.value); }} /></Field>}
      {(attempt || recoverId) && <><p>原请求 ID：{attempt?.request_id || recoverId}</p><Button disabled={networkLocked} onClick={() => void readBack()}>按原 ID 读回交接状态</Button></>}
      {attempt && unknown && <StatusMessage tone="warning">提交结果尚未核对。保持同一请求 ID；404 也不能证明请求未提交，请先读回状态。</StatusMessage>}
      {attempt && notFound && <><label className="experimental-check"><input type="checkbox" disabled={locked || !loaded} checked={retryAck} onChange={event => { if (admit()) setRetryAck(event.target.checked); }} />已核对原请求，明确按同一 ID 和相同确认内容重发</label><Button disabled={networkLocked || !props.canMutate || !loaded || !versions || !losses || !retryAck} onClick={() => void mutate('confirm')}>明确重发同一确认</Button></>}
      {receipt?.status === 'PLANNED' && <><StatusMessage>交接等待明确恢复。已完成 {receipt.steps.filter(s => s.state === 'READY').length} / {receipt.steps.length} 个素材；回执版本 v{receipt.version}。</StatusMessage>
        <Button disabled={networkLocked || !props.canMutate || !loaded || !versions || !losses} onClick={() => void mutate('resume')}>明确恢复剩余交接步骤</Button>
        <label className="experimental-check"><input type="checkbox" disabled={locked} checked={cancelAck} onChange={event => { if (admit()) setCancelAck(event.target.checked); }} />确认取消后保留已提交素材，不回滚或删除资源</label>
        <Button disabled={networkLocked || !props.canMutate || !cancelAck} onClick={() => void mutate('cancel')}>明确取消原交接</Button>
      </>}
      {receipt?.status === 'DRAFT_CREATED' && <StatusMessage tone="success">原 Timeline 草稿 ID：{receipt.timeline_snapshot!.id}。请到原 Timeline 列表选择打开。{receipt.timeline_state === 'MODIFIED_AFTER_CREATION' ? '该草稿创建后已有修改。' : ''}</StatusMessage>}
      {receipt?.status === 'CANCELLED' && <StatusMessage>原交接已取消；已提交素材继续保留。</StatusMessage>}
      {(dirty || receipt) && <Button disabled={busy || isComposing} onClick={close}>{attempt && (!receipt || receipt.status === 'PLANNED') ? '暂存恢复标识并关闭交接' : '关闭交接并保留原记录'}</Button>}
    </>}
  </Panel>;
}
