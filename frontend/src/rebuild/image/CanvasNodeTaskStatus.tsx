import {useEffect, useRef, useState} from 'react';
import {api, apiErrorView, getCollaborationEpoch} from '../../api';
import {useLocalHostSession} from '../../localHostSession';
import {useScopedRequestConsent} from '../../useScopedRequestConsent';
import {Badge, Button, StatusMessage} from '../../ui/primitives';
import {canvasTaskBindingKey, captureCanvasTaskOwner, imageDraftNodeExists, readCanvasTaskBinding, type CanvasTaskBinding} from './canvasTaskBinding';
import {useCanvasTaskBinding} from './useCanvasTaskBinding';

type Props = {novelId: string; nodeId: string; onOpen?: () => void};
const states = new Set(['QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED']);

/** Read-only view of the exact persisted job ID. No inference, adoption or write endpoint is called. */
export function CanvasNodeTaskStatus(props: Props) {
  const {owner, binding, sessionKey} = useCanvasTaskBinding(props.novelId, props.nodeId);
  return <section aria-label="原节点图片任务">
    {!owner ? <StatusMessage>尚未验证可持久关联的身份；核对会话后才能在此浏览器保存原节点任务关联。</StatusMessage>
      : binding ? <CanvasNodeTaskStatusSession key={sessionKey} {...props} binding={binding}/>
      : <p className="novel-help">此节点尚未关联已入队任务。</p>}
  </section>;
}

function CanvasNodeTaskStatusSession({novelId, nodeId, onOpen, binding}: Props & {binding: CanvasTaskBinding}) {
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const sequence = useRef(0), mounted = useRef(false);
  const consent = useScopedRequestConsent([]);
  const capturedScope = consent.captureScope();
  const clientEpoch = getCollaborationEpoch(), hostEpoch = useLocalHostSession.getState().epoch;
  const ownerKey = canvasTaskBindingKey(binding.owner, nodeId);
  const current = () => {
    const owner = captureCanvasTaskOwner(novelId);
    return mounted.current && capturedScope() && clientEpoch === getCollaborationEpoch()
      && hostEpoch === useLocalHostSession.getState().epoch && !!owner
      && canvasTaskBindingKey(owner, nodeId) === ownerKey && imageDraftNodeExists(novelId, nodeId)
      && readCanvasTaskBinding(owner, nodeId)?.taskId === binding.taskId;
  };
  async function refresh() {
    if (!current()) return;
    const request = ++sequence.current;
    setLoading(true); setStatus(''); setError('');
    try {
      const result = await api.imageJobs(novelId);
      if (!current() || request !== sequence.current) return;
      const matches = (Array.isArray(result.items) ? result.items : []).filter(row => row?.id === binding.taskId);
      if (matches.length !== 1 || matches[0].novel_id !== novelId || !states.has(matches[0].status)
        || binding.owner.mode === 'collaboration' && matches[0].branch_id !== binding.owner.branchId) {
        setError('原任务当前不可读或状态无法核实；不会新建替代任务。');
      } else setStatus(matches[0].status);
    } catch (reason) {
      if (current() && request === sequence.current) setError(apiErrorView(reason, '原任务状态无法核实').message);
    } finally {
      if (current() && request === sequence.current) setLoading(false);
    }
  }
  useEffect(() => {
    mounted.current = true; void refresh();
    return () => { mounted.current = false; sequence.current += 1; };
  }, []);
  return <>
    <p>原入队任务 ID：{binding.taskId}</p>
    <p className="novel-help">原任务不代表当前提示词已经入队。关联仅保存在此浏览器；状态每次从原项目队列读取，不会自动执行或采用结果。</p>
    {loading && <StatusMessage>正在核实原任务状态…</StatusMessage>}
    {status && <p>服务端任务状态：<Badge>{status}</Badge></p>}
    {error && <StatusMessage tone="error">{error}</StatusMessage>}
    <Button variant="ghost" onClick={() => void refresh()}>刷新原任务状态</Button>
    <Button variant="ghost" disabled={!onOpen} onClick={() => { if (current()) onOpen?.(); }}>打开原图片任务</Button>
  </>;
}
