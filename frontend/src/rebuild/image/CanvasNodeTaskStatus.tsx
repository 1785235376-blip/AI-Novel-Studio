import {useEffect, useRef, useState} from 'react';
import {api, apiErrorView, getCollaborationEpoch} from '../../api';
import {useLocalHostSession} from '../../localHostSession';
import {useScopedRequestConsent} from '../../useScopedRequestConsent';
import {Badge, Button, StatusMessage} from '../../ui/primitives';
import {canvasTaskBindingKey, captureCanvasTaskOwner, imageDraftNodeExists, readCanvasTaskBinding, type CanvasTaskBinding} from './canvasTaskBinding';
import {useCanvasTaskBinding} from './useCanvasTaskBinding';
import {checkedCanvasTaskCandidate, type CanvasTaskCandidate} from './canvasTaskCandidate';
import {CanvasTaskCandidateView} from './CanvasTaskCandidateView';
import {CanvasAdoptionHistory} from './CanvasAdoptionHistory';

type Props = {novelId: string; nodeId: string; onOpen?: () => void; nodePrompt?: string; sourceRevision?: number; isSourceCurrent?: () => boolean};
const states = new Set(['QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED']);

/** Original-owner reads and an explicit browser-only asset association; no server review/write endpoint. */
export function CanvasNodeTaskStatus(props: Props) {
  const {owner, binding, sessionKey} = useCanvasTaskBinding(props.novelId, props.nodeId);
  let unreadable = false;
  if (owner && !binding) {
    try { unreadable = localStorage.getItem(canvasTaskBindingKey(owner, props.nodeId)) !== null; }
    catch { unreadable = true; }
  }
  return <section aria-label="原节点图片任务">
    {!owner ? <StatusMessage>尚未验证可持久关联的身份；核对会话后才能在此浏览器保存原节点任务关联。</StatusMessage>
      : binding ? <CanvasNodeTaskStatusSession key={JSON.stringify([sessionKey, props.nodePrompt, props.sourceRevision])} {...props} binding={binding}/>
      : unreadable ? <StatusMessage tone="warning">此节点的本机关联不可读取或格式无法核实。原记录保留，未恢复或覆盖；请保留浏览器数据后核对。</StatusMessage>
      : <p className="novel-help">此节点尚未关联已入队任务。</p>}
  </section>;
}

function CanvasNodeTaskStatusSession({novelId, nodeId, onOpen, binding, nodePrompt, isSourceCurrent}: Props & {binding: CanvasTaskBinding}) {
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [candidate, setCandidate] = useState<CanvasTaskCandidate>();
  const sequence = useRef(0), mounted = useRef(false);
  const consent = useScopedRequestConsent([]);
  const capturedScope = consent.captureScope();
  const clientEpoch = getCollaborationEpoch(), hostEpoch = useLocalHostSession.getState().epoch;
  const ownerKey = canvasTaskBindingKey(binding.owner, nodeId);
  const current = () => {
    const owner = captureCanvasTaskOwner(novelId);
    return mounted.current && (!isSourceCurrent || isSourceCurrent()) && capturedScope() && clientEpoch === getCollaborationEpoch()
      && hostEpoch === useLocalHostSession.getState().epoch && !!owner
      && canvasTaskBindingKey(owner, nodeId) === ownerKey && imageDraftNodeExists(novelId, nodeId)
      && JSON.stringify(readCanvasTaskBinding(owner, nodeId)) === JSON.stringify(binding);
  };
  async function refresh() {
    if (!current()) return;
    const request = ++sequence.current;
    setLoading(true); setStatus(''); setError(''); setCandidate(undefined);
    try {
      const result = await api.imageJobs(novelId);
      if (!current() || request !== sequence.current) return;
      const matches = (Array.isArray(result.items) ? result.items : []).filter(row => row?.id === binding.taskId);
      if (matches.length !== 1 || matches[0].novel_id !== novelId || !states.has(matches[0].status)
        || binding.owner.mode === 'collaboration' && matches[0].branch_id !== binding.owner.branchId) {
        setError('原任务当前不可读或状态无法核实；不会新建替代任务。');
      } else {
        setStatus(matches[0].status);
        setCandidate(checkedCanvasTaskCandidate(binding, matches[0]));
      }
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
  const displayedRead = sequence.current;
  const candidateCurrent = () => current() && sequence.current === displayedRead;
  return <>
    <p>原入队任务 ID：{binding.taskId}</p>
    <p className="novel-help">原任务不代表当前提示词已经入队。关联仅保存在此浏览器；状态每次从原项目队列读取，不会自动执行或采用结果。</p>
    {binding.adoption && <StatusMessage>此浏览器记录的节点资产：{binding.adoption.assetId}；读取时资产版本：{binding.adoption.assetVersion}。这是本机采用关联，尚未重新核对当前内容；没有新增服务端审核或共享画布记录。使用前请重新预览并核对。</StatusMessage>}
    <CanvasAdoptionHistory key={`history-${displayedRead}`} binding={binding} nodePrompt={nodePrompt} isCurrent={candidateCurrent}/>
    {loading && <StatusMessage>正在核实原任务状态…</StatusMessage>}
    {status && <p>服务端任务状态：<Badge>{status}</Badge></p>}
    {error && <StatusMessage tone="error">{error}</StatusMessage>}
    {candidate ? <CanvasTaskCandidateView key={displayedRead} candidate={candidate} binding={binding} nodePrompt={nodePrompt} isCurrent={candidateCurrent} onUnavailable={message => {
      if (candidateCurrent()) { setCandidate(undefined); setStatus(''); setError(message); }
    }}/>
      : status === 'SUCCEEDED' && <StatusMessage>原任务未提供完整可核实的候选来源信息，当前不能展示或预览结果；不会生成替代图片。</StatusMessage>}
    <Button variant="ghost" onClick={() => void refresh()}>刷新原任务状态</Button>
    <Button variant="ghost" disabled={!onOpen} onClick={() => { if (current()) onOpen?.(); }}>打开原图片任务</Button>
  </>;
}
