import {useEffect, useRef, useState} from 'react';
import {api, getCollaborationContext, getCollaborationEpoch, subscribeCollaborationContext, type ScopedReadOptions} from '../../api';
import {useLocalHostSession} from '../../localHostSession';
import {Button, StatusMessage} from '../../ui/primitives';
import {canvasTaskBindingKey, captureCanvasTaskOwner, MAX_CANVAS_TASK_HISTORY, readCanvasTaskBinding,
  type CanvasTaskBinding, type CanvasTaskHistoryEntry} from './canvasTaskBinding';
import {checkedCanvasTaskCandidate, type CanvasTaskCandidate} from './canvasTaskCandidate';
import {abortableCanvasCandidateRead, canvasCandidateCryptoAvailable, canvasCandidateObservationSha256} from './canvasCandidateReview';
import {canvasAdoptionHistoryDifferences, sameCanvasAdoptionTarget} from './canvasAdoptionHistoryDisplay';
import {CanvasTaskCandidateView} from './CanvasTaskCandidateView';

type Props = {binding: CanvasTaskBinding; nodePrompt?: string; isCurrent: () => boolean; onUnavailable?: (message: string) => void};
type HistoricalRead = {candidate: CanvasTaskCandidate; displayBinding: CanvasTaskBinding;
  entry: CanvasTaskHistoryEntry; request: number; selection: number; fence: object};
const OPERATION_LABEL = {import: '首次保留的旧关联', queue: '入队关联', adopt: '本机采用', restore: '本机恢复'} as const;

/** IDs and pins in this journal are unverified browser history, never server approval. */
export function CanvasAdoptionHistory({binding, nodePrompt, isCurrent, onUnavailable}: Props) {
  const [selected, setSelected] = useState<string>();
  const [read, setRead] = useState<HistoricalRead>();
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const mounted = useRef(false), running = useRef(false), sequence = useRef(0), selection = useRef(0);
  const selectedRef = useRef<string>(), controllerRef = useRef<AbortController>();
  const initialEpoch = useRef({client: getCollaborationEpoch(), host: useLocalHostSession.getState().epoch});
  const fence = useRef({binding, nodePrompt, token: {}});
  if (fence.current.binding !== binding || fence.current.nodePrompt !== nodePrompt) fence.current = {binding, nodePrompt, token: {}};
  const token = fence.current.token;
  const live = useRef(isCurrent); live.current = isCurrent;
  const history = binding.schema_version === 2 ? binding.history : [];
  const targets = history.filter(entry => !!entry.adoption);
  const capacityFull = history.length >= MAX_CANVAS_TASK_HISTORY;
  const ownerKey = canvasTaskBindingKey(binding.owner, binding.nodeId);
  const current = () => {
    const owner = captureCanvasTaskOwner(binding.owner.novelId);
    return mounted.current && fence.current.token === token && isCurrent() && live.current()
      && initialEpoch.current.client === getCollaborationEpoch() && initialEpoch.current.host === useLocalHostSession.getState().epoch
      && !!owner && canvasTaskBindingKey(owner, binding.nodeId) === ownerKey
      && JSON.stringify(readCanvasTaskBinding(owner, binding.nodeId)) === JSON.stringify(binding);
  };
  function retire() {
    sequence.current += 1; selection.current += 1; controllerRef.current?.abort(); controllerRef.current = undefined;
    running.current = false; selectedRef.current = undefined;
    setSelected(undefined); setRead(undefined); setBusy(false); setError('');
  }
  useEffect(() => {
    mounted.current = true;
    const stopClient = subscribeCollaborationContext(retire);
    const stopHost = useLocalHostSession.subscribe(state => { if (state.epoch !== initialEpoch.current.host) retire(); });
    return () => {
      mounted.current = false; sequence.current += 1; selection.current += 1; controllerRef.current?.abort(); stopClient(); stopHost();
    };
  }, []);
  useEffect(() => { retire(); }, [binding, nodePrompt]);

  function choose(entry: CanvasTaskHistoryEntry) {
    if (!current() || !entry.adoption || sameCanvasAdoptionTarget(binding.taskId, binding.adoption, entry.taskId, entry.adoption)) return;
    // Retire even A/B/A selections before React commits the next render.
    sequence.current += 1; selection.current += 1; controllerRef.current?.abort(); controllerRef.current = undefined;
    running.current = false; selectedRef.current = entry.eventId;
    setSelected(entry.eventId); setRead(undefined); setBusy(false); setError('');
  }
  async function loadSelected() {
    const entry = history.find(item => item.eventId === selectedRef.current);
    if (!current() || running.current || !entry?.adoption
      || sameCanvasAdoptionTarget(binding.taskId, binding.adoption, entry.taskId, entry.adoption)) return;
    const request = ++sequence.current, selectionRevision = selection.current;
    running.current = true; setBusy(true); setError(''); setRead(undefined);
    const controller = new AbortController(); controllerRef.current = controller;
    const timeout = setTimeout(() => controller.abort(), 15_000);
    const options: ScopedReadOptions = {signal: controller.signal, cache: 'no-store', redirect: 'error', credentials: 'omit', referrerPolicy: 'no-referrer'};
    const context = getCollaborationContext();
    const captured = {...context, scope: context.scope && {...context.scope}, actor: context.actor && {...context.actor},
      localHostToken: context.localHostToken ?? useLocalHostSession.getState().token};
    const valid = () => current() && request === sequence.current && selectionRevision === selection.current
      && selectedRef.current === entry.eventId && !controller.signal.aborted;
    try {
      const result = await abortableCanvasCandidateRead(api.imageJobs(binding.owner.novelId, captured, options), controller.signal);
      if (!valid()) return;
      const displayBinding: CanvasTaskBinding = {schema_version: 1, owner: {...binding.owner}, nodeId: binding.nodeId, taskId: entry.taskId};
      const matches = (Array.isArray(result.items) ? result.items : []).filter(row => row?.id === entry.taskId);
      const candidate = matches.length === 1 ? checkedCanvasTaskCandidate(displayBinding, matches[0]) : undefined;
      if (!candidate || candidate.approvalStatus !== 'APPROVED' || candidate.previewKind !== 'asset' || candidate.assetId !== entry.adoption.assetId) {
        throw new Error('Historical original candidate unavailable');
      }
      if (canvasCandidateCryptoAvailable()) {
        const observation = await abortableCanvasCandidateRead(canvasCandidateObservationSha256(candidate), controller.signal);
        if (!valid()) return;
        if (observation !== entry.adoption.jobObservationSha256) throw new Error('Historical original Job observation changed');
      }
      if (!valid()) return;
      setRead({candidate, displayBinding, entry, request, selection: selectionRevision, fence: token});
    } catch {
      if (current() && request === sequence.current && selectionRevision === selection.current) {
        const message = '所选历史原任务当前不可读、观察摘要已变化或读取超时。当前关联和旧记录保留，未准备恢复；不会自动重试。';
        setError(message); onUnavailable?.(message);
      }
    } finally {
      clearTimeout(timeout);
      if (controllerRef.current === controller) controllerRef.current = undefined;
      if (mounted.current && fence.current.token === token && request === sequence.current && selectionRevision === selection.current) {
        running.current = false; setBusy(false);
      }
    }
  }
  const readCurrent = (value: HistoricalRead) => current() && value.fence === token && value.request === sequence.current
    && value.selection === selection.current && selectedRef.current === value.entry.eventId;
  const visibleRead = read && readCurrent(read) ? read : undefined;
  return <section aria-label="此浏览器原节点采用历史">
    <h4>此浏览器原节点采用历史</h4>
    <p className="novel-help">以下仅比较本机保存的任务 ID、资产 ID、版本和摘要，全部尚未重新核验。选择不会读取图片或改变当前关联；恢复仍需重新加载图片、人工核对和明确确认。</p>
    <dl aria-label="当前本机关联 pin" className="image-task-inspector__facts">
      <div><dt>当前原任务 ID</dt><dd>{binding.taskId}</dd></div>
      {binding.adoption ? <>
        <div><dt>当前资产 ID</dt><dd>{binding.adoption.assetId}</dd></div>
        <div><dt>当前记录版本</dt><dd>{binding.adoption.assetVersion}</dd></div>
        <div><dt>当前内容摘要</dt><dd>{binding.adoption.assetSha256}</dd></div>
        <div><dt>当前任务观察</dt><dd>{binding.adoption.jobObservationSha256}</dd></div>
      </> : <div><dt>当前资产</dt><dd>当前记录没有采用资产</dd></div>}
    </dl>
    {binding.schema_version === 1 ? <StatusMessage>旧格式只保留当前关联，没有可读取的历史列表。不能据此断言更早的关联从未存在；首次新的有效操作才会将此旧关联保留为本机导入记录。</StatusMessage> : <>
      <p className="novel-help">本机记录 {history.length}/{MAX_CANVAS_TASK_HISTORY}，仅下列 {targets.length} 条包含资产关联；入队等其他记录仍保留，但不能作为资产恢复目标。</p>
      {capacityFull && <StatusMessage tone="warning">此浏览器原节点历史容量已满，旧记录全部保留；不能准备新的采用或恢复，不会自动删除记录。</StatusMessage>}
      {!targets.length && <StatusMessage>当前历史没有可作为资产恢复目标的记录；已有任务关联仍保留，不会生成替代历史。</StatusMessage>}
      {targets.map(entry => {
        const pin = entry.adoption!;
        const identical = sameCanvasAdoptionTarget(binding.taskId, binding.adoption, entry.taskId, pin);
        return <section key={entry.eventId} aria-label={'历史记录 ' + entry.eventId}>
          <label><input type="radio" name={'canvas-history-' + binding.nodeId} aria-label={'选择历史记录 ' + entry.eventId}
            checked={selected === entry.eventId} disabled={identical} onChange={() => choose(entry)}/>
            本机顺序 {entry.revision} · {OPERATION_LABEL[entry.operation]}</label>
          <dl className="image-task-inspector__facts">
            <div><dt>记录 ID</dt><dd title={entry.eventId}>{entry.eventId}</dd></div>
            <div><dt>原任务 ID</dt><dd title={entry.taskId}>{entry.taskId}</dd></div>
            <div><dt>资产 ID</dt><dd title={pin.assetId}>{pin.assetId}</dd></div>
            <div><dt>记录版本</dt><dd>{pin.assetVersion}</dd></div>
            <div><dt>内容摘要</dt><dd title={pin.assetSha256}>{pin.assetSha256}</dd></div>
            <div><dt>任务观察</dt><dd title={pin.jobObservationSha256}>{pin.jobObservationSha256}</dd></div>
          </dl>
          <p className="novel-help">{canvasAdoptionHistoryDifferences(binding.taskId, binding.adoption, entry.taskId, pin).join('；')}。以上为未重新核验的本机比较。</p>
          {identical && <StatusMessage>与当前记录相同，不能重复恢复。</StatusMessage>}
        </section>;
      })}
      {!!targets.length && <Button disabled={!selected || busy} loading={busy} onClick={() => void loadSelected()}>读取所选历史原任务</Button>}
    </>}
    {error && <StatusMessage tone="error">{error}</StatusMessage>}
    {visibleRead && <CanvasTaskCandidateView key={visibleRead.entry.eventId + ':' + visibleRead.request + ':' + visibleRead.selection}
      candidate={visibleRead.candidate} binding={visibleRead.displayBinding} nodePrompt={nodePrompt}
      restore={{expectedBinding: binding, entry: visibleRead.entry}} isCurrent={() => readCurrent(visibleRead)} onUnavailable={message => {
        if (readCurrent(visibleRead)) { setRead(undefined); setError(message); onUnavailable?.(message); }
      }}/>} 
  </section>;
}
