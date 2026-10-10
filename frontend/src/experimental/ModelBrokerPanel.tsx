import { useEffect, useMemo, useRef, useState } from 'react';
import type { Chapter, CollaborationContext } from '../api';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import { AuthorRequestPreviewPanel } from '../novel/AuthorRequestPreviewPanel';
import { defaultAuthorRequestScope, type AuthorRequestScope, type AuthorPreviewReceipt, type AuthorRequestBody } from '../novel/authorContextClient';
import { AuthorRequestControls } from '../novel/AuthorRequestControls';
import type { ExperimentalClient, Row } from './api';
import { Details, Field, ResourceState, useAction, useResource } from './shared';
import { modelBrokerClient, type BrokerApi, type BrokerJob, type BrokerPreview, type BrokerStatus } from './modelBrokerClient';
import { ModelBenchmarkPanel } from './ModelBenchmarkPanel';

let scopeSequence = 0;
const freshId = () => globalThis.crypto?.randomUUID?.() || `broker-${Date.now()}-${Math.random()}`;
const cost = (value: number | null | undefined) => value == null ? '未知' : `${value} µUSD`;
export function ModelBrokerPanel(props: { client: ExperimentalClient; novelId: string; context: CollaborationContext; chapter?: Chapter; benchmarkEnabled?: boolean; onOpenGeneration?: (jobId: string, chapterId: string) => Promise<void> }) {
  const identity = useMemo(() => ++scopeSequence, [props.client, props.chapter?.id, props.chapter?.version]);
  return <BrokerBody key={identity} {...props} />;
}
function BrokerBody({ client, novelId, context, chapter, benchmarkEnabled = false, onOpenGeneration }: { client: ExperimentalClient; novelId: string; context: CollaborationContext; chapter?: Chapter; benchmarkEnabled?: boolean; onOpenGeneration?: (jobId: string, chapterId: string) => Promise<void> }) {
  const api = useMemo(() => modelBrokerClient(client), [client]);
  const status = useResource(signal => api.status(signal), [api]);
  const history = useResource(signal => api.history(signal), [api]);
  const [capability, setCapability] = useState('TEXT');
  const [policy, setPolicy] = useState('LOCAL_FIRST'), [profile, setProfile] = useState('LOCAL_ONLY'), [route, setRoute] = useState('');
  const [contextTokens, setContextTokens] = useState('0'), [limit, setLimit] = useState(''), [latency, setLatency] = useState('');
  const [ram, setRam] = useState(''), [vram, setVram] = useState('');
  const [fallback, setFallback] = useState(false), [license, setLicense] = useState(false);
  const [synthetic, setSynthetic] = useState(false), [excluded, setExcluded] = useState<string[]>([]);
  const [quote, setQuote] = useState<BrokerPreview>(), [operation, setOperation] = useState('continue'), [instruction, setInstruction] = useState('');
  const [requestScope, setRequestScope] = useState<AuthorRequestScope>(defaultAuthorRequestScope);
  const [receipt, setReceipt] = useState<AuthorPreviewReceipt>(), [reviewed, setReviewed] = useState(false), [reservation, setReservation] = useState('');
  const epoch = useRef(0), alive = useRef(true), requestId = useRef(freshId());
  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; }; }, []);
  const action = useAction(() => { history.reload(); status.reload(); });
  const invalidate = () => { epoch.current++; setQuote(undefined); setReceipt(undefined); setReviewed(false); requestId.current = freshId(); };
  const authorChanged = () => { setReceipt(undefined); setReviewed(false); requestId.current = freshId(); };
  const author: AuthorRequestBody | null = quote?.chosen?.capability === 'TEXT' && chapter ? { novel_id: novelId, chapter_id: chapter.id, chapter_version: chapter.version,
    operation, instruction, style: '', profile, request_scope: requestScope, provider_id: quote.chosen.provider_id, model_id: quote.chosen.model_id, source: '', selected_text: '' } : null;
  const currentRoutes = status.data?.candidates.filter(r => r.capability === capability) || [];
  const providers = [...new Set(currentRoutes.map(r => r.provider_id))];
  return <div className="experimental-section">
    <Panel title="可解释模型调度">
      <p>候选来自当前已注册模型与 Adapter。发现不代表启用，路由预览不代表执行授权；不自动改走云端。</p>
      <ResourceState loading={status.loading} error={status.error} />
      {!status.loading && !status.error && !currentRoutes.length && <EmptyState title="没有此类型的注册路线" detail="先在已有 Model Center 配置、验证并明确启用本地模型；没有真实模型时可明确选择合成协议测试。" />}
      <Field label="模型能力类型"><select value={capability} onChange={e => { invalidate(); setCapability(e.target.value); setRoute(''); setContextTokens('0'); }}><option value="TEXT">TEXT · 作者草稿</option><option value="IMAGE">IMAGE · 批次媒体预检</option><option value="AUDIO">AUDIO · 已审核语音段预检</option></select></Field>
      {capability !== 'TEXT' && <p>这里只创建原路线预检；请在安全批处理中选择同一来源、明确本地与 0 USD 上限，再单独确认和执行。费用未知不能当作免费。</p>}
      <div className="experimental-grid">
        <Field label="调度策略"><select value={policy} onChange={e => { invalidate(); setPolicy(e.target.value); }}><option value="LOCAL_FIRST">本地优先</option><option value="COST">成本优先</option><option value="QUALITY">质量优先（无证据不排名）</option><option value="SPEED">速度优先（仅当前执行证据）</option><option value="PRIVACY_FIRST">隐私优先（只允许本地）</option><option value="BALANCED">平衡（当前成本 / 延迟）</option><option value="CUSTOM">自定义指定路线</option></select></Field>
        <Field label="创作隐私模式"><select value={profile} onChange={e => { invalidate(); setProfile(e.target.value); }}><option value="LOCAL_ONLY">仅本地</option><option value="HYBRID">允许已授权云端候选</option><option value="QUALITY">质量模式（仍检查来源授权）</option></select></Field>
        <Field label="偏好模型路线"><select value={route} onChange={e => { invalidate(); setRoute(e.target.value); }}><option value="">无偏好</option>{currentRoutes.map(r => <option key={r.route_id} value={r.route_id}>{r.display_name} · {r.provider_id}{r.available ? '' : ' · 不可用'}{r.synthetic ? ' · 合成测试' : ''}</option>)}</select></Field>
        <Field label="最低上下文容量（Token；0 表示未设）"><input type="number" min="0" max="10000000" value={contextTokens} onChange={e => { invalidate(); setContextTokens(e.target.value); }} /></Field>
        <Field label="单任务预占上限（µUSD；留空不另设）"><input type="number" min="0" value={limit} onChange={e => { invalidate(); setLimit(e.target.value); }} /></Field>
        <Field label="最大已测延迟（毫秒；留空不另设）"><input type="number" min="1" value={latency} onChange={e => { invalidate(); setLatency(e.target.value); }} /></Field>
        <Field label="最低主机总内存（MiB；留空不另设）"><input type="number" min="1" value={ram} onChange={e => { invalidate(); setRam(e.target.value); }} /></Field>
        <Field label="最低主机总显存（MiB；留空不另设）"><input type="number" min="1" value={vram} onChange={e => { invalidate(); setVram(e.target.value); }} /></Field>
      </div>
      <p>主机容量只在明确设限时读取；不是当前空闲内存，也不保证推理适配。没有真实硬件证据时不满足资源硬限制。</p>
      <label className="experimental-check"><input type="checkbox" checked={synthetic} onChange={e => { invalidate(); setSynthetic(e.target.checked); }} />明确允许内置合成协议测试（不代表真实模型质量）</label>
      <label className="experimental-check"><input type="checkbox" checked={fallback} onChange={e => { invalidate(); setFallback(e.target.checked); }} />提前允许本地优先策略提出云端候选（仍需来源授权和单次生成确认）</label>
      <label className="experimental-check"><input type="checkbox" checked={license} onChange={e => { invalidate(); setLicense(e.target.checked); }} />只接受已有 License 确认证据的路线</label>
      <details><summary>排除 Provider</summary>{providers.map(id => <label className="experimental-check" key={id}><input type="checkbox" checked={excluded.includes(id)} onChange={e => { invalidate(); setExcluded(old => e.target.checked ? [...old, id] : old.filter(v => v !== id)); }} />排除 {id}</label>)}</details>
      <p>当前来源：{chapter ? `「${chapter.title}」已保存版本 v${chapter.version}` : '尚未选择章节'}。只使用已保存章节；未保存的编辑请先返回编辑器保存。</p>
      <div className="experimental-actions"><Button disabled={!chapter || action.busy || status.loading || !!status.error || (policy === 'CUSTOM' && !route)} onClick={() => void action.run(async () => {
        const ticket = ++epoch.current; setQuote(undefined); setReceipt(undefined); setReviewed(false);
        const result = await api.preview({ capability, chapter_ids: [chapter!.id], policy, profile, preferred_route: route || null, excluded_providers: excluded,
          context_tokens: Number(contextTokens || 0), max_latency_ms: latency ? Number(latency) : null, max_cost_microusd: limit ? Number(limit) : null, allow_synthetic: synthetic, allow_cloud_fallback: fallback, require_confirmed_license: license, min_host_ram_mib: ram ? Number(ram) : null, min_host_vram_mib: vram ? Number(vram) : null });
        if (alive.current && ticket === epoch.current) setQuote(result);
      }, '路线检查已完成；尚未调用模型。')}>预览合法模型路线</Button><Button disabled={action.busy} onClick={() => { invalidate(); status.reload(); history.reload(); }}>重新读取当前注册状态</Button></div>
      {action.feedback}
      {quote && <section className="experimental-section" aria-label="模型路线预览">
        {quote.chosen ? <StatusMessage tone="success">建议：{quote.chosen.display_name} · {quote.chosen.cloud ? '云端' : '本地'} · 预占 {cost(quote.chosen.price?.reserve_microusd)} · {quote.chosen.cost_state}</StatusMessage> : <StatusMessage tone="warning">没有合法候选。请核对下方排除原因，不会自动选择替代云模型。</StatusMessage>}
        {!!quote.warnings.length && <StatusMessage tone="warning">文学质量证据不足，未进行质量排名。</StatusMessage>}
        {quote.candidates.map(r => <article className="experimental-record" key={r.route_id}><div className="experimental-actions"><strong>{r.display_name}</strong><Badge tone={r.eligible ? 'success' : 'warning'}>{r.eligible ? '合法候选' : '已排除'}</Badge><span>{r.provider_id} / {r.model_id}</span></div><p>{r.reasons.length ? r.reasons.join(' · ') : '通过当前能力、模型状态、来源隐私与预算检查'}</p><p>费用：{r.cost_state === 'UNKNOWN' ? '未知，不能当作免费' : cost(r.price?.reserve_microusd)} · {r.verification}</p></article>)}
        <Details value={quote.policy_explanation} label="策略排序与未知证据" /><Details value={quote.will_send} label="核对来源、版本与外发范围" />
      </section>}
    </Panel>
    {quote?.chosen && author && <Panel title="按已核对路线生成单份草稿">
      <Field label="创作任务"><select value={operation} disabled={action.busy} onChange={e => { authorChanged(); setOperation(e.target.value); }}><option value="continue">续写</option><option value="polish">润色</option><option value="brainstorm">构思</option><option value="review">审稿</option></select></Field>
      <Field label="本次创作要求"><textarea maxLength={20000} value={instruction} onChange={e => { authorChanged(); setInstruction(e.target.value); }} /></Field>
      <AuthorRequestControls value={requestScope} onChange={value => { setRequestScope(value); authorChanged(); }} source={author.source} operation={operation} disabled={action.busy} />
      <AuthorRequestPreviewPanel body={author} context={context} saved={true} disabled={action.busy} onScopeChange={value => { setRequestScope(value); authorChanged(); }} onReceipt={value => { setReceipt(value); setReviewed(false); }} />
      <label className="experimental-check"><input type="checkbox" disabled={!receipt} checked={reviewed} onChange={e => setReviewed(e.target.checked)} />已核对准确请求、来源与模型，并授权生成这一次草稿</label>
      <StatusMessage>预算限制预占金额；上游实际费用可能超出估计。取消后已发出的内容不能收回，费用不确定时仍保留预占。</StatusMessage>
      {!status.data?.author_execution_available && <StatusMessage tone="warning">当前服务器尚未接入原有作者任务协调器，不能执行。</StatusMessage>}
      <Button disabled={!receipt || !reviewed || action.busy || !status.data?.author_execution_available} onClick={() => void action.run(async () => {
        const ticket = epoch.current;
        const result = await api.generate(quote, { ...receipt!.requestBody, preview_digest: receipt!.previewDigest }, requestId.current);
        if (alive.current && ticket === epoch.current) { setReservation(result.reservation_id); setReviewed(false); }
      }, '已交给原有作者任务执行器。结果仍是草稿，不自动写入正文。')}>按预览路线预占并生成</Button>
    </Panel>}
    {reservation && <BrokerJobStatus api={api} reservation={reservation} onOpenGeneration={onOpenGeneration} onSettled={() => { history.reload(); status.reload(); }} />}
    {status.data && <BudgetSettings api={api} status={status.data} stale={status.loading || !!status.error} onSaved={() => { invalidate(); status.reload(); }} />}
    <Panel title="决策与费用历史"><Button disabled={history.loading} onClick={history.reload}>刷新决策与账本</Button><ResourceState loading={history.loading} error={history.error} empty={!history.data?.ledger.length && !history.data?.decisions.length} />
      {!history.loading && !history.error && history.data?.ledger.map(row => <article key={row.id} className="experimental-record"><strong>{row.provider_id} / {row.model_id}</strong><p>{row.status} · 预占 {cost(row.reserve_microusd)} · 实际 {cost(row.actual_microusd)} · {row.cost_state}</p><Button onClick={() => setReservation(row.id)}>查看原任务 {row.job_id}</Button>{(row.status === 'UNKNOWN_UPSTREAM' || (row.status === 'SETTLED' && row.overrun)) && <ReconcileLedger api={api} row={row} onSaved={() => { invalidate(); history.reload(); status.reload(); }} />}</article>)}
      {!history.loading && !history.error && history.data?.decisions.map(row => <details key={row.id}><summary>{row.created_at} · {row.chosen?.display_name || '无合法候选'} · {row.status}</summary><p>历史预览不用于直接重试；请重新核对当前来源和模型。</p><Details value={row.candidates.map(r => ({ provider: r.provider_id, model: r.model_id, reasons: r.reasons }))} /></details>)}
    </Panel>
    {benchmarkEnabled && <ModelBenchmarkPanel api={api} routes={status.data?.candidates || []} />}
  </div>;
}
function BrokerJobStatus({ api, reservation, onSettled, onOpenGeneration }: { api: BrokerApi; reservation: string; onSettled: () => void; onOpenGeneration?: (jobId: string, chapterId: string) => Promise<void> }) {
  const [data, setData] = useState<BrokerJob>(), [error, setError] = useState<unknown>();
  const [revision, setRevision] = useState(0), callback = useRef(onSettled); callback.current = onSettled;
  useEffect(() => {
    const controller = new AbortController(); let timer: ReturnType<typeof setTimeout>; let terminal = false;
    setData(undefined); setError(undefined);
    const read = async () => { try { const value = await api.job(reservation, controller.signal); if (controller.signal.aborted) return; setData(value);
      const pending = value.job && !value.recovery && (value.job.status === 'SETTLING' || ['RESERVED', 'DISPATCHED'].includes(value.ledger.status || ''));
      if (pending) timer = setTimeout(() => void read(), 1000); else if (!terminal) { terminal = true; callback.current(); }
    } catch (failure) { if (!controller.signal.aborted) setError(failure); } };
    void read(); return () => { controller.abort(); clearTimeout(timer); };
  }, [api, reservation, revision]);
  const action = useAction(() => setRevision(v => v + 1));
  return <Panel title="原有作者任务进度"><ResourceState loading={!data && !error} error={error} />{data && <><p>{data.job?.status || '执行器会话不可恢复'} · 账本 {data.ledger.status}</p>{data.recovery && <StatusMessage tone="warning">执行器重启后不会自动重发。保留账本记录；请先核对上游状态，费用未知的预占不会自动释放。</StatusMessage>}{data.orphan_reconciliation_available && <ReconcileLedger api={api} row={data.ledger} orphan onSaved={() => setRevision(v => v + 1)} />}{data.job?.output && <Field label="生成草稿（只读）"><textarea readOnly value={data.job.output} /></Field>}{data.job?.error && <StatusMessage tone="error">{data.job.error}</StatusMessage>}<p>实际费用：{cost(data.ledger.actual_microusd)}。审核与采用仍使用原有作者草稿流程。</p>{data.job && <Button disabled={action.busy || !onOpenGeneration || !data.job.chapter_id} onClick={() => void action.run(() => onOpenGeneration!(data.job!.id, data.job!.chapter_id), '已核对当前权限并打开原有草稿审核；尚未采用。')}>在原有草稿审核中打开</Button>}{data.job && !['COMPLETED', 'FAILED', 'CANCELLED', 'ACCEPTED', 'REJECTED'].includes(data.job.status) && <Button disabled={action.busy} onClick={() => void action.run(() => api.cancel(reservation, data.ledger.version), '已请求取消；上游消耗仍可能产生。')}>取消本次生成</Button>}</>}<Button onClick={() => setRevision(v => v + 1)}>重新核对任务状态</Button>{action.feedback}</Panel>;
}
function BudgetSettings({ api, status, stale, onSaved }: { api: BrokerApi; status: BrokerStatus; stale: boolean; onSaved: () => void }) {
  const [expectedVersion, setExpectedVersion] = useState(status.budget.version);
  const [limit, setLimit] = useState(status.budget.limit_microusd == null ? '' : String(status.budget.limit_microusd)), [concurrency, setConcurrency] = useState(status.budget.max_inflight);
  const [known, setKnown] = useState(status.budget.require_known_estimate);
  const [routeId, setRouteId] = useState(''), [estimate, setEstimate] = useState(''), [source, setSource] = useState(''), [expiry, setExpiry] = useState('');
  const [priceVersion, setPriceVersion] = useState(0);
  const [inputRate, setInputRate] = useState(''), [outputRate, setOutputRate] = useState('');
  const action = useAction(onSaved), route = status.candidates.find(r => r.route_id === routeId);
  return <Panel title="项目预算与价格来源"><p>所有作者共享当前项目分支的费用上限；已占用 {cost(status.budget.committed_microusd)}，进行中 {status.budget.inflight}，上游未知 {status.budget.unknown_count}。金额单位 µUSD（1 USD = 1,000,000 µUSD）。</p>
    <div className="experimental-grid"><Field label="累计预占上限（µUSD；留空不设金额上限）"><input type="number" min="0" value={limit} onChange={e => setLimit(e.target.value)} /></Field><Field label="最多并发任务"><input type="number" min="1" max="8" value={concurrency} onChange={e => setConcurrency(Number(e.target.value))} /></Field></div>
    <label className="experimental-check"><input type="checkbox" checked={known} onChange={e => setKnown(e.target.checked)} />要求已配置费用估计；严格金额上限始终要求估计</label>
    <div className="experimental-actions"><Button disabled={action.busy || stale} onClick={() => void action.run(async () => { const result = await api.budget({ expected_version: expectedVersion, limit_microusd: limit ? Number(limit) : null, max_inflight: concurrency, require_known_estimate: known }); setExpectedVersion(result.version); }, '项目预算已保存，旧路线预览失效。')}>保存版本化项目预算</Button>{expectedVersion !== status.budget.version && <Button disabled={action.busy || stale} onClick={() => setExpectedVersion(status.budget.version)}>已核对最新预算 v{status.budget.version}，保留输入继续编辑</Button>}</div>
    <details><summary>配置明确路线的费用估计</summary><div className="experimental-form"><Field label="价格适用路线"><select value={routeId} onChange={e => { setRouteId(e.target.value); setPriceVersion(status.prices.find(p => p.route_id === e.target.value)?.version || 0); }}><option value="">请选择</option>{status.candidates.filter(r => !r.synthetic).map(r => <option key={r.route_id} value={r.route_id}>{r.display_name} · {r.provider_id}</option>)}</select></Field><Field label="每请求保守预占（µUSD）"><input type="number" min="0" value={estimate} onChange={e => setEstimate(e.target.value)} /></Field><Field label="价格依据（来源或报价说明）"><input maxLength={240} value={source} onChange={e => setSource(e.target.value)} /></Field><Field label="价格有效至"><input type="datetime-local" value={expiry} onChange={e => setExpiry(e.target.value)} /></Field><Field label="输入费率（每百万 Token 的 µUSD；可空）"><input type="number" min="0" value={inputRate} onChange={e => setInputRate(e.target.value)} /></Field><Field label="输出费率（每百万 Token 的 µUSD；可空）"><input type="number" min="0" value={outputRate} onChange={e => setOutputRate(e.target.value)} /></Field><p>估计绑定当前模型、Runtime 和 Adapter 指纹。没有使用量费率时，实际费用保持未知；此配置不冒充免费或供应商硬上限。</p><Button disabled={action.busy || stale || !route || !source.trim() || !expiry || estimate === ''} onClick={() => void action.run(async () => { const result = await api.price({ route_id: route!.route_id, route_fingerprint: route!.fingerprint, expected_version: priceVersion, currency: 'USD', reserve_microusd: Number(estimate), source, as_of: new Date().toISOString(), expires_at: new Date(expiry).toISOString(), applicability: 'per_request', input_per_million_microusd: inputRate ? Number(inputRate) : null, output_per_million_microusd: outputRate ? Number(outputRate) : null }); setPriceVersion(result.version); }, '当前路线的费用估计已保存。')}>保存路线价格依据</Button></div></details>{action.feedback}
  </Panel>;
}

function ReconcileLedger({ api, row, onSaved, orphan = false }: { api: BrokerApi; row: Row; onSaved: () => void; orphan?: boolean }) {
  const [amount, setAmount] = useState(''), [note, setNote] = useState(''), [confirmed, setConfirmed] = useState(false);
  const action = useAction(onSaved);
  return <details><summary>人工核对上游终态与账单</summary><div className="experimental-form"><StatusMessage tone="warning">只有确认上游已经结束后才能处理保留预占。金额会标为你提供的账单数据，本应用不会声称独立验证过账单。</StatusMessage><Field label="已核对账单金额（µUSD）"><input type="number" min="0" value={amount} onChange={e => { setConfirmed(false); setAmount(e.target.value); }} /></Field><Field label="核对依据（不要填写凭据）"><textarea maxLength={500} value={note} onChange={e => { setConfirmed(false); setNote(e.target.value); }} /></Field><label className="experimental-check"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />{orphan ? '已确认原执行器停止、上游任务终止，核对账单并确认预算影响' : '已确认上游任务终止、核对账单，并承担此记录对预算余额的影响'}</label><Button disabled={action.busy || !confirmed || amount === '' || !note.trim()} onClick={() => void action.run(() => api.reconcile(row, Number(amount), note, orphan), '已记录人工账单核对，原始预占与未知状态仍保留在版本历史。')}>记录账单并关闭未知预占</Button>{action.feedback}</div></details>;
}
