import { useEffect, useRef, useState } from 'react';
import { ApiError, apiErrorView } from '../api';
import { Badge, Button, StatusMessage } from '../ui/primitives';
import type { StudioGraphClient } from './studioGraphClient';
import type { StudioGraphModelCapabilities, StudioGraphRun } from './studioGraphTypes';

export type GraphModelAction = 'preview' | 'dispatch' | 'refresh';
export type GraphModelActionEvidence = { route_id?: string; allow_synthetic?: boolean; reviewed_preview_digest?: string };
type Props = {
  client: StudioGraphClient; run?: StudioGraphRun; locked: boolean; canMutate: boolean; uncertain: boolean;
  isCurrent: () => boolean; read: <T>(work: () => Promise<T>) => Promise<T>;
  perform: (action: GraphModelAction, evidence?: GraphModelActionEvidence) => Promise<boolean>;
  onUnavailable: () => void;
};

/** Explicit actions only: mounting, selecting a route and reading capabilities never dispatch. */
export function GraphModelExecutionPanel({ client, run, locked, canMutate, uncertain, isCurrent, read, perform, onUnavailable }: Props) {
  const [capabilities, setCapabilities] = useState<StudioGraphModelCapabilities>(), [routeId, setRouteId] = useState('');
  const [allowSynthetic, setAllowSynthetic] = useState(false), [reviewed, setReviewed] = useState(false), [loading, setLoading] = useState(false), [error, setError] = useState('');
  const alive = useRef(true), pending = useRef(false), epoch = useRef(0);
  const model = run?.model_runtime, preview = !run?.stale ? model?.preview : null, execution = model?.execution;
  const route = capabilities?.routes.find(item => item.route_id === routeId);
  const terminal = !!run && ['SUCCEEDED', 'FAILED', 'CANCELLED', 'REJECTED'].includes(run.status);
  const disabled = locked || loading || !canMutate || !!run?.stale || run?.status === 'PAUSED' || terminal;
  const previewReady = !!model && ['AWAITING_PREVIEW', 'PREVIEWED'].includes(model.status) && !execution;
  const exactRoute = !!preview?.route && !!route && preview.route.route_id === route.route_id
    && preview.route.provider_id === route.provider_id && preview.route.model_id === route.model_id && preview.route.synthetic === route.synthetic;
  const canDispatch = model?.status === 'PREVIEWED' && !!preview?.execution_available && exactRoute && !!route?.available
    && (!route.synthetic || allowSynthetic) && reviewed && !disabled && !uncertain;
  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; }; }, []);
  useEffect(() => { setReviewed(false); }, [run?.id, run?.version, preview?.preview_digest, routeId, allowSynthetic, locked, canMutate, uncertain]);
  const current = () => alive.current && isCurrent();

  async function load() {
    if (pending.current || locked || !current()) return;
    pending.current = true; const request = ++epoch.current; setLoading(true); setError(''); setReviewed(false); setCapabilities(undefined); setRouteId(''); setAllowSynthetic(false);
    try { const value = await read(() => client.modelCapabilities()); if (current() && request === epoch.current) setCapabilities(value); }
    catch (value) { if (current() && request === epoch.current) { setError(apiErrorView(value, '模型能力读取失败。请核对当前项目权限。').message); if (value instanceof ApiError && [401, 403, 404].includes(value.status)) onUnavailable(); } }
    finally { pending.current = false; if (current() && request === epoch.current) setLoading(false); }
  }
  async function action(kind: GraphModelAction) {
    if (!run || pending.current || !current() || disabled) return;
    if (kind === 'preview' && (uncertain || !previewReady || !route?.available || route.synthetic && !allowSynthetic)) return;
    if (kind === 'dispatch' && !canDispatch) return;
    if (kind === 'refresh' && !execution) return;
    pending.current = true; setLoading(true); setReviewed(false);
    try { await perform(kind, kind === 'preview' ? { route_id: route!.route_id, allow_synthetic: allowSynthetic }
      : kind === 'dispatch' ? { reviewed_preview_digest: preview!.preview_digest } : undefined); }
    finally { pending.current = false; if (current()) setLoading(false); }
  }

  return <section className="studio-graph-model" aria-label="可选本地文字模型执行">
    <h3>可选本地文字模型执行</h3><p>先读取能力并选择本地路由，再核对完整输入并明确调用一次。不会自动安装、启动模型、调用、重试或转云端。结果仍需人工审核，不写入正文。</p>
    <p>云端 API：预留，当前不可执行。实际推理质量验收：未运行。</p>
    <Button disabled={locked || loading} onClick={() => void load()}>读取本地模型能力</Button>
    {loading && <StatusMessage>正在核对模型执行信息…</StatusMessage>}{error && <StatusMessage tone="error">{error}</StatusMessage>}
    {capabilities && <><p>适配器：{capabilities.adapter_owner} · 路由：{capabilities.router_owner} · 调度：{capabilities.scheduler_owner}</p><p>每次运行最多 {capabilities.limits.model_nodes} 个模型节点，最长 {capabilities.limits.timeout_seconds} 秒，最多 {capabilities.limits.max_output_tokens} 输出 token。</p>
      {!capabilities.routes.length && <StatusMessage tone="warning">没有可用的已配置本地模型路由。手工节点仍可使用。</StatusMessage>}
      <label>本地文字模型路由<select aria-label="本地文字模型路由" value={routeId} disabled={disabled || !!execution || uncertain} onChange={event => { setRouteId(event.target.value); setAllowSynthetic(false); setReviewed(false); }}><option value="">明确选择本地路由</option>{capabilities.routes.map(item => <option key={item.route_id} value={item.route_id} disabled={!item.available}>{item.display_name} · {item.provider_id} / {item.model_id}{item.synthetic ? ' · 测试适配器' : ''}{item.available ? '' : ' · 不可用'}</option>)}</select></label>
      {route && <><p>验证状态：{route.verification} · 上下文窗口：{route.context_window ?? '未知'}</p>{route.reasons.map(reason => <StatusMessage key={reason} tone="warning">{reason}</StatusMessage>)}{route.synthetic && <label><input type="checkbox" checked={allowSynthetic} disabled={disabled || !!execution || uncertain} onChange={event => setAllowSynthetic(event.target.checked)} />明确使用测试适配器；不代表真实本地模型推理</label>}</>}
    </>}
    {!run && <p>先保存图并创建运行；保存和创建都不会调用模型。</p>}
    {run && !model && <p>当前运行没有模型节点，保持原本地处理边界。</p>}
    {model && <><Badge>{model.status}</Badge>{model.status === 'PENDING' && <p>先明确执行前置本地节点，到达模型边界后再预览。</p>}
      {previewReady && <Button disabled={disabled || uncertain || !route?.available || route.synthetic && !allowSynthetic} onClick={() => void action('preview')}>预览图节点模型输入</Button>}
      {preview && !terminal && <section aria-label="图节点模型输入预览"><Badge tone="info">预览尚未调用模型</Badge><p>节点：{preview.node_id} · 路由：{preview.route?.provider_id || '未选定'} / {preview.route?.model_id || '未选定'}</p><p>最多 {preview.limits.max_output_tokens} 输出 token · 最长 {preview.limits.timeout_seconds} 秒 · 最高费用 0 USD</p><details><summary>核对完整模型输入</summary><pre>{preview.prompt}</pre></details>{preview.reasons.map(reason => <StatusMessage key={reason} tone="warning">{reason}</StatusMessage>)}
        {!execution && <><label><input type="checkbox" checked={reviewed} disabled={disabled || uncertain || !preview.execution_available || !exactRoute || !route?.available || route.synthetic && !allowSynthetic} onChange={event => setReviewed(event.target.checked)} />已核对当前节点、完整输入和本地路由，允许调用一次</label><Button variant="primary" disabled={!canDispatch} onClick={() => void action('dispatch')}>确认调用图节点本地模型</Button></>}
      </section>}
      {execution && <section aria-label="图节点模型执行回执"><p>任务：{execution.job_id} · {execution.status}</p><p>模型调用：{execution.model_called ? '已调用' : '调用记录尚待核对'} · {execution.synthetic ? '测试适配器任务' : '本地模型任务'}</p><p>回执：{execution.receipt_state} · 用量：{execution.usage_state}</p>{execution.failure_code && <StatusMessage tone="warning">{execution.failure_code}</StatusMessage>}{!terminal && <Button disabled={disabled} onClick={() => void action('refresh')}>核对图节点模型结果</Button>}<p>等待中的模型任务只能核对或取消，不能暂停后重复调度。</p></section>}
      {(uncertain || model.status === 'UNKNOWN') && <StatusMessage tone="warning">调用回执不确定。请重新读取当前运行或核对结果；不会自动重放。</StatusMessage>}
      {model.status === 'RESULT_REVIEW' && <p>模型输出尚未应用。请在节点输出审核中阅读并决定是否批准。</p>}
    </>}
  </section>;
}
