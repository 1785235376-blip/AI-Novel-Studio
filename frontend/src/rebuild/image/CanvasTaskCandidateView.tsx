import {useEffect, useRef, useState} from 'react';
import {api, getCollaborationContext} from '../../api';
import {useLocalHostSession} from '../../localHostSession';
import {Button, StatusMessage} from '../../ui/primitives';
import type {CanvasTaskBinding} from './canvasTaskBinding';
import {checkedCanvasTaskCandidate, sameCanvasTaskCandidate, type CanvasTaskCandidate} from './canvasTaskCandidate';
import '../../novel/ImageTaskInspector.css';

type Props = {candidate: CanvasTaskCandidate; binding: CanvasTaskBinding; nodePrompt?: string; isCurrent: () => boolean; onUnavailable: (message: string) => void};
type Preview = {uri: string; request: number};

/** The original owner remains authoritative; this component only re-reads and presents its snapshot. */
export function CanvasTaskCandidateView({candidate, binding, nodePrompt, isCurrent, onUnavailable}: Props) {
  const [preview, setPreview] = useState<Preview>();
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const mounted = useRef(false), running = useRef(false), sequence = useRef(0);
  const objectUrl = useRef<string>(), download = useRef<AbortController>();
  const live = useRef({candidate, isCurrent}); live.current = {candidate, isCurrent};
  const previewRef = useRef(preview); previewRef.current = preview;
  const current = () => mounted.current && live.current.candidate === candidate && isCurrent() && live.current.isCurrent();
  function releasePreview() {
    if (objectUrl.current) { URL.revokeObjectURL(objectUrl.current); objectUrl.current = undefined; }
    setPreview(undefined);
  }
  useEffect(() => { mounted.current = true; return () => {
    mounted.current = false; sequence.current += 1; download.current?.abort();
    if (objectUrl.current) { URL.revokeObjectURL(objectUrl.current); objectUrl.current = undefined; }
  }; }, []);

  async function inspect() {
    if (!current() || running.current || !candidate.previewKind) return;
    const request = ++sequence.current;
    running.current = true; setBusy(true); setError(''); releasePreview();
    const context = getCollaborationContext();
    const captured = {...context, scope: context.scope && {...context.scope}, actor: context.actor && {...context.actor},
      localHostToken: context.localHostToken ?? useLocalHostSession.getState().token};
    const controller = new AbortController(); download.current = controller;
    const matchesCandidate = (result: {items: unknown[]}) => {
      const matches = (Array.isArray(result.items) ? result.items : []).filter(row => row && typeof row === 'object' && 'id' in row && row.id === candidate.jobId);
      const fresh = matches.length === 1 ? checkedCanvasTaskCandidate(binding, matches[0]) : undefined;
      return sameCanvasTaskCandidate(candidate, fresh);
    };
    try {
      const result = await api.imageJobs(candidate.novelId, captured);
      if (!current() || request !== sequence.current) return;
      if (!matchesCandidate(result)) {
        onUnavailable('原候选读取快照已变化或当前不可核实。请刷新原任务状态后重新确认预览。');
        return;
      }
      if (candidate.previewKind === 'asset' && candidate.assetId) {
        const blob = await api.assetDownload(candidate.assetId, candidate.novelId, captured, {
          redirect: 'error', credentials: 'omit', cache: 'no-store', referrerPolicy: 'no-referrer', signal: controller.signal, maxBytes: 36 * 1024 * 1024,
        });
        if (!current() || request !== sequence.current) return;
        if (!blob.size || !/^image\/(?:png|jpeg|jpg|webp|gif)$/i.test(blob.type.split(';')[0].trim())) {
          onUnavailable('原资产未提供本入口支持的图片内容。请核对原任务与资产，不会改用结果链接。');
          return;
        }
        const confirmed = await api.imageJobs(candidate.novelId, captured);
        if (!current() || request !== sequence.current) return;
        if (!matchesCandidate(confirmed)) {
          onUnavailable('原候选读取快照已变化或当前不可核实。请刷新原任务状态后重新确认预览。');
          return;
        }
        const uri = URL.createObjectURL(blob); objectUrl.current = uri;
        setPreview({uri, request});
      } else if (candidate.previewKind === 'inline' && candidate.previewUri) setPreview({uri: candidate.previewUri, request});
    } catch {
      if (current() && request === sequence.current) onUnavailable('原候选读取失败或权限已变化。请刷新原任务状态后核对，不会自动重试。');
    } finally {
      if (download.current === controller) download.current = undefined;
      if (current() && request === sequence.current) { running.current = false; setBusy(false); }
    }
  }
  function hide() {
    sequence.current += 1; download.current?.abort(); download.current = undefined;
    running.current = false; setBusy(false); releasePreview(); setError('');
  }
  return <section aria-label="原任务候选结果">
    <h4>原任务读取快照</h4>
    <p className="novel-help">候选只读，未自动采用。以下来自原任务记录；请求摘要不是图片文件校验，尝试次数和更新时间不是服务端正式版本。</p>
    {nodePrompt !== undefined && nodePrompt.trim() !== candidate.prompt.trim() && <StatusMessage tone="warning">当前节点提示词已不同；以下仍是历史原任务候选，不会覆盖当前草稿。</StatusMessage>}
    <dl className="image-task-inspector__facts">
      <div><dt>来源节点</dt><dd>{candidate.nodeId}</dd></div>
      <div><dt>原任务</dt><dd>{candidate.jobId}</dd></div>
      <div><dt>项目</dt><dd>{candidate.novelId}</dd></div>
      <div><dt>图片服务</dt><dd>{candidate.providerId}</dd></div>
      <div><dt>模型</dt><dd>{candidate.modelId}</dd></div>
      <div><dt>执行尝试</dt><dd>{candidate.attempt}</dd></div>
      <div><dt>任务更新时间</dt><dd>{candidate.updatedAt}</dd></div>
      <div><dt>请求摘要</dt><dd>{candidate.requestSha256}</dd></div>
      <div><dt>审核记录</dt><dd>{candidate.approvalStatus === 'APPROVED' ? '服务端标记已接受入库' : '尚未接受入库'}</dd></div>
      {candidate.assetId && <div><dt>记录资产 ID</dt><dd>{candidate.assetId}</dd></div>}
    </dl>
    <label>原任务提示词<textarea aria-label="原任务提示词" value={candidate.prompt} readOnly rows={3}/></label>
    {!candidate.previewKind && <StatusMessage>原任务尚未提供入库资产或内联图片；当前接口未提供未入库网络候选的内容读取，这里只显示来源信息。</StatusMessage>}
    <Button disabled={!candidate.previewKind || busy} loading={busy} onClick={() => void inspect()}>预览原任务候选结果</Button>
    {(preview || busy) && <Button variant="ghost" onClick={hide}>隐藏候选预览</Button>}
    {error && <StatusMessage tone="error">{error}</StatusMessage>}
    {preview && <div className="image-task-inspector__preview"><img key={preview.request} src={preview.uri} alt="原节点任务候选结果" referrerPolicy="no-referrer" onError={() => {
      if (current() && previewRef.current === preview && sequence.current === preview.request) {
        releasePreview(); setError('候选预览加载失败。来源记录保留，未执行或采用任何结果。');
      }
    }}/></div>}
    <p className="novel-help">{candidate.previewKind === 'asset' ? '已入库结果通过原资产接口读取，并在显示前再次核对原任务快照。' : '内联图片在重新核对原任务快照后显示；网络结果地址不会直接用于预览。'}不会执行或采用结果；预览不代表生成质量、图片内容审核或持续权限核验。</p>
  </section>;
}
