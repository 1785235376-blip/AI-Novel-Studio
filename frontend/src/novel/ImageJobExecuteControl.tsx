import {useEffect, useRef, useState} from 'react';
import {api, getCollaborationContext, getCollaborationEpoch, type AssetProviderStatus, type CollaborationContext} from '../api';
import {useLocalHostSession} from '../localHostSession';
import {captureCanvasTaskOwner, type CanvasTaskOwner} from '../rebuild/image/canvasTaskBinding';
import {Button, StatusMessage} from '../ui/primitives';
import {checkedQueuedImageJob, hasImageJobExecutionPermission, matchingExecutionProvider, sameExecutionSnapshot, type ImageJobExecutionSnapshot} from './imageJobExecution';
import {clearImageExecutionPending, markImageExecutionPending, pendingMatchesSnapshot, readImageExecutionPending} from './imageJobExecutionPending';

type Props = {novelId: string; job: unknown; ownerCurrent: () => boolean; parentRevision: string; onChanged: () => Promise<void>};
type Bundle = {snapshot: ImageJobExecutionSnapshot; provider: Readonly<AssetProviderStatus>; context: CollaborationContext};

/** The original queue and provider remain the only execution owners. */
export function ImageJobExecuteControl(props: Props) {
  const owner = captureCanvasTaskOwner(props.novelId);
  const snapshot = owner && checkedQueuedImageJob(owner, props.job);
  if (!owner || !snapshot) return <><Button disabled>执行任务</Button><StatusMessage>当前身份或原任务参数不完整；不能确认执行。</StatusMessage></>;
  return <ExecuteSession key={JSON.stringify([snapshot.fingerprint, props.parentRevision])} {...props} owner={owner} snapshot={snapshot}/>;
}

function ExecuteSession({owner, snapshot, ownerCurrent, onChanged}: Props & {owner: CanvasTaskOwner; snapshot: ImageJobExecutionSnapshot}) {
  const [review, setReview] = useState<Bundle>();
  const [checked, setChecked] = useState(false), [busy, setBusy] = useState(false), [message, setMessage] = useState('');
  const [unresolved, setUnresolved] = useState(() => readImageExecutionPending(owner, snapshot.jobId).kind !== 'none');
  const mounted = useRef(false), running = useRef(false), sequence = useRef(0), approved = useRef(false);
  const apiEpoch = useRef(getCollaborationEpoch()).current, hostEpoch = useRef(useLocalHostSession.getState().epoch).current;
  const controller = useRef<AbortController>(), timer = useRef<ReturnType<typeof setTimeout>>();
  const live = useRef({ownerCurrent}); live.current = {ownerCurrent};
  const current = () => mounted.current && ownerCurrent() && live.current.ownerCurrent() && apiEpoch === getCollaborationEpoch()
    && hostEpoch === useLocalHostSession.getState().epoch;
  useEffect(() => {
    mounted.current = true;
    const storage = () => { approved.current = false; setChecked(false); setReview(undefined); setUnresolved(readImageExecutionPending(owner, snapshot.jobId).kind !== 'none'); sequence.current += 1; controller.current?.abort(); running.current = false; setBusy(false); };
    window.addEventListener('storage', storage);
    return () => { mounted.current = false; sequence.current += 1; controller.current?.abort(); clearTimeout(timer.current); window.removeEventListener('storage', storage); };
  }, []);
  const captureContext = (): CollaborationContext => {
    const value = getCollaborationContext();
    return {...value, actor: value.actor && {...value.actor}, scope: value.scope && {...value.scope},
      localHostToken: value.localHostToken ?? useLocalHostSession.getState().token};
  };
  async function readBundle(context: CollaborationContext, request: number): Promise<Bundle | undefined> {
    const [jobs, providers, permission] = await Promise.all([
      api.imageJobExecutionRead(snapshot.novelId, context), api.assetProviders(context),
      owner.mode === 'collaboration' && context.scope ? api.permissions(context.scope, context) : Promise.resolve(undefined),
    ]);
    if (!current() || sequence.current !== request) return;
    if (jobs.execution_confirmation !== 'legacy-image-confirmation/1') throw new Error('Unsupported confirmation contract');
    const matches = (Array.isArray(jobs.items) ? jobs.items : []).filter(row => row?.id === snapshot.jobId);
    const fresh = matches.length === 1 ? checkedQueuedImageJob(owner, matches[0]) : undefined;
    if (!fresh || !sameExecutionSnapshot(snapshot, fresh)) throw new Error('Task changed');
    const provider = matchingExecutionProvider(fresh, providers.items);
    if (!provider || !provider.local && !fresh.allowCloudPrompt
      || owner.mode === 'collaboration' && !hasImageJobExecutionPermission(owner, permission)) throw new Error('Execution capability unavailable');
    return {snapshot: fresh, provider, context};
  }
  function resetReview() { approved.current = false; setChecked(false); setReview(undefined); }
  async function prepare() {
    if (!current() || running.current) return;
    const request = ++sequence.current; running.current = true; setBusy(true); resetReview(); setMessage('');
    try {
      const fresh = await readBundle(captureContext(), request);
      if (!fresh || !current() || request !== sequence.current) return;
      const pending = readImageExecutionPending(owner, snapshot.jobId);
      if (pending.kind === 'unavailable' || pending.kind === 'pending' && pendingMatchesSnapshot(pending.value, fresh.snapshot)) {
        setUnresolved(true); setMessage('执行结果尚未确定，或本地恢复标记不可读取。请只读核对原任务状态；不会再次派发。'); return;
      }
      if (pending.kind === 'pending' && !clearImageExecutionPending(owner, snapshot.jobId, pending.raw)) {
        setUnresolved(true); setMessage('本地恢复标记未能核对，不能派发执行。'); return;
      }
      setUnresolved(false); setReview(fresh);
    } catch { if (current() && request === sequence.current) setMessage('原任务、服务模型或写入权限当前无法核实。请刷新原任务后重新核对；未派发执行。'); }
    finally { if (current() && request === sequence.current) { running.current = false; setBusy(false); } }
  }
  async function execute() {
    if (!current() || running.current || !review || !approved.current) return;
    const request = ++sequence.current; running.current = true; setBusy(true); setMessage('');
    try {
      const fresh = await readBundle(review.context, request);
      if (!fresh || !current() || request !== sequence.current || !approved.current) return;
      if (JSON.stringify(fresh.provider) !== JSON.stringify(review.provider) || !sameExecutionSnapshot(review.snapshot, fresh.snapshot)) {
        resetReview(); setMessage('任务或服务配置已变化，原确认已失效；未派发执行。'); return;
      }
      const pending = markImageExecutionPending(owner, fresh.snapshot);
      if (!pending) { resetReview(); setUnresolved(true); setMessage('本地恢复标记不可用或已有未决执行，未派发。请只读核对原任务。'); return; }
      setUnresolved(true); resetReview();
      const abort = new AbortController(); controller.current = abort;
      timer.current = setTimeout(() => abort.abort(), 30_000);
      try {
        await api.executeImageJob(snapshot.novelId, snapshot.jobId, {confirmed: true,
          expected_request_sha256: fresh.snapshot.requestSha256, expected_attempt: fresh.snapshot.attempt,
          expected_updated_at: fresh.snapshot.updatedAt}, fresh.context, abort.signal);
        if (current() && request === sequence.current) { setMessage('已收到原执行接口回包，请核对原任务状态；不会自动重试或接受结果。'); await onChanged(); }
      } catch {
        if (current() && request === sequence.current) setMessage('执行回执未知或请求被拒绝；超时不代表模型未运行。请只读核对原任务并使用原恢复入口，不会自动重派。');
      } finally { clearTimeout(timer.current); if (controller.current === abort) controller.current = undefined; }
    } catch { if (current() && request === sequence.current) { resetReview(); setMessage('执行前任务、服务或权限已变化，原确认已失效；未派发执行。'); } }
    finally { if (current() && request === sequence.current) { running.current = false; setBusy(false); } }
  }
  async function recoverRead() {
    if (!current() || running.current) return;
    resetReview(); setMessage('仅刷新原任务状态；相同未决快照不会重新派发。'); await onChanged();
  }
  return <>
    <Button disabled={busy || !ownerCurrent()} loading={busy} onClick={() => void prepare()}>执行任务</Button>
    {unresolved && <><StatusMessage tone="warning">存在本浏览器记录的未决执行。恢复原状态前不能重复派发。</StatusMessage><Button variant="ghost" disabled={busy} onClick={() => void recoverRead()}>只读核对原任务状态</Button></>}
    {message && <StatusMessage tone="warning">{message}</StatusMessage>}
    {review && <section aria-label="执行原图片任务确认">
      <h4>仅执行这一个已入队任务</h4>
      <p>项目：{snapshot.novelId}；原任务：{snapshot.jobId}；分支：{snapshot.branchId || '原本地范围'}。</p>
      <p>图片服务：{review.provider.display_name || snapshot.providerId}；模型：{snapshot.modelId}。</p>
      <p className="novel-help">当前配置已注册且可达，任务模型匹配配置默认模型；这不代表模型加载、推理质量或费用已经验证。{owner.mode === 'local' ? '本地模式沿用原 loopback 访问边界。' : '已读取当前写入权限，派发时原接口仍会重新授权。'}</p>
      <label>本次执行的原任务提示词<textarea aria-label="本次执行的原任务提示词" value={snapshot.prompt} readOnly rows={3}/></label>
      <dl>{Object.entries(snapshot.parameters).map(([name, value]) => <div key={name}><dt>{name}</dt><dd>{String(value)}</dd></div>)}</dl>
      <p className="novel-help">参考图片：0；角色：{snapshot.input.character_id || '未指定'}；场景：{snapshot.input.scene_id || '未指定'}。
        {snapshot.input.size && `尺寸：${snapshot.input.size}。`}{snapshot.input.quality && `质量：${snapshot.input.quality}。`}{snapshot.input.output_format && `格式：${snapshot.input.output_format}。`}</p>
      <StatusMessage tone="warning">本次最多派发这一个原任务，不会执行模板、其他节点或整个队列。费用未知，可能产生服务费用或本地算力消耗；{review.provider.local ? '本地模型也不等于无成本。' : '将向所选云服务发送此任务已授权的原提示词。'}取消或超时不能保证远端停止。</StatusMessage>
      <label><input type="checkbox" checked={checked} disabled={busy} onChange={event => { approved.current = event.target.checked; setChecked(event.target.checked); }}/>我已核对任务、参数和可能费用</label>
      <Button disabled={!checked || busy} onClick={() => void execute()}>确认执行这一个任务</Button>
      <Button variant="ghost" disabled={busy} onClick={() => { sequence.current += 1; resetReview(); }}>取消执行确认</Button>
    </section>}
  </>;
}
