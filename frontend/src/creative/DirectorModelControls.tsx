import { useEffect, useState } from 'react';
import { ApiError } from '../api';
import { Badge, Button, StatusMessage } from '../ui/primitives';
import { CreativeField } from './CreativeCanvas';
import type { CreativeClient, DirectorModelRoute, DirectorProposal } from './client';
export function DirectorModelControls({ client, proposal, disabled, run, onUpdate }: { client: CreativeClient; proposal: DirectorProposal; disabled: boolean; run: (action: () => Promise<void>) => Promise<void>; onUpdate: (proposal: DirectorProposal) => void }) {
  const [routes, setRoutes] = useState<DirectorModelRoute[]>([]), [routeId, setRouteId] = useState(''), [loading, setLoading] = useState(true), [error, setError] = useState(''), [reviewed, setReviewed] = useState(false), [unauthorized, setUnauthorized] = useState(false);
  const preview = proposal.model_preview, execution = proposal.model_execution;
  useEffect(() => { const controller = new AbortController(); setLoading(true); client.modelRoutes(controller.signal).then(value => { if (!controller.signal.aborted) { setRoutes(value.items); setError(''); } }).catch(value => { if (!controller.signal.aborted) { setError('本地模型路由尚不可用。可以继续审核规则辅助建议。'); if (value instanceof ApiError && [401, 403].includes(value.status)) { setUnauthorized(true); setRoutes([]); setReviewed(false); } } }).finally(() => { if (!controller.signal.aborted) setLoading(false); }); return () => controller.abort(); }, [client]);
  useEffect(() => setReviewed(false), [proposal.version, preview?.preview_digest, routeId]);
  const execute = (operation: () => Promise<void>) => run(async () => {
    try { await operation(); } catch (value) {
      if (value instanceof ApiError && [401, 403].includes(value.status)) { setUnauthorized(true); setRoutes([]); setReviewed(false); setError('本地模型调用缺少主机授权。手动编辑和规则辅助建议仍可继续。'); return; }
      throw value;
    }
  });
  const route = routes.find(row => row.route_id === routeId) || routes.find(row => row.available && !row.synthetic);
  const terminal = ['APPROVED', 'CANCELLED'].includes(proposal.status);
  return <section className="creative-model-controls" aria-label="可选本地模型导演"><h3>可选：本地模型导演</h3><p>仅使用明确选择、价格已确认是零的本地文字模型。先预览输入，再确认调用；不自动重试或转云端。</p>{loading && <StatusMessage>读取本地模型路由…</StatusMessage>}{error && <StatusMessage tone="warning">{error}</StatusMessage>}{!loading && !error && !routes.some(row => row.available && !row.synthetic) && <StatusMessage tone="warning">尚无可用的本地模型路由。需要配置模型和路由价格，且启用模型路由、上下文预览能力。</StatusMessage>}
    {!unauthorized && !execution && !terminal && <><CreativeField label="本地导演模型"><select disabled={disabled || loading} value={route?.route_id || ''} onChange={event => setRouteId(event.target.value)}><option value="">选择本地模型</option>{routes.filter(row => !row.synthetic).map(row => <option key={row.route_id} value={row.route_id} disabled={!row.available}>{row.provider_id} / {row.model_id}{row.available ? '' : ` · 不可用 (${row.reasons.join(', ')})`}</option>)}</select></CreativeField><Button disabled={disabled || !route?.available || route.synthetic} onClick={() => route && void execute(async () => onUpdate(await client.previewModel(proposal, route.route_id)))}>预览模型输入</Button></>}
    {!unauthorized && preview && !execution && !terminal && <div className="creative-model-preview"><Badge tone="info">预览尚未调用模型</Badge><p>输入：当前已保存剧本的场景。最长 {preview.timeout_seconds}s。最高费用：0 USD。</p><p>路由：{preview.broker.chosen?.provider_id || '未选定'} / {preview.broker.chosen?.model_id || '未选定'}</p><details><summary>核对将发送的完整模型输入</summary><pre>{JSON.stringify(preview.request, null, 2)}</pre></details><label className="creative-review-check"><input disabled={disabled || !preview.execution_available} type="checkbox" checked={reviewed} onChange={e => setReviewed(e.target.checked)} />已核对输入和本地路由，允许调用一次</label><Button variant="primary" disabled={disabled || !reviewed || !preview.execution_available || route?.provider_id !== preview.broker.chosen?.provider_id || route?.model_id !== preview.broker.chosen?.model_id} onClick={() => void execute(async () => onUpdate(await client.dispatchModel(proposal)))}>确认调用本地模型</Button></div>}
    {!unauthorized && execution && <div><Badge tone={proposal.status === 'MODEL_UNAVAILABLE' ? 'warning' : 'info'}>{execution.status}</Badge><p>任务：{execution.job_id}</p><p>调用：{execution.model_called ? '已调用' : '尚未确认调用'} · 回执：{execution.receipt_state}</p>{execution.failure_code && <p>{execution.failure_code}</p>}{!terminal && <div className="creative-actions"><Button disabled={disabled} onClick={() => void execute(async () => onUpdate(await client.refreshModel(proposal)))}>核对模型结果</Button><Button disabled={disabled} onClick={() => void run(async () => onUpdate(await client.cancelProposal(proposal)))}>取消模型任务</Button></div>}</div>}
  </section>;
}
