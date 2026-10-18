import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { Chapter } from '../api';
import { Badge, Button, EmptyState, StatusMessage } from '../ui/primitives';
import { segment, type ExperimentalClient, type Row } from './api';
import { Details, ErrorMessage, Field, ResourceState, useResource } from './shared';
import { useReviewAction } from './styleReviewClient';

type ModelRoute = { route_id: string; provider_id: string; model_id: string; display_name: string; synthetic: boolean; available: boolean; reasons: string[] };
type ModelCatalog = { routes: ModelRoute[]; profile: string; max_cost_microusd: number };
type ModelPreview = { preview_digest: string; request: unknown; broker: { chosen?: ModelRoute | null }; budget: unknown; sources: unknown; source_ranges?: unknown; truncation?: string; source_strategy: string; execution_available: boolean; max_output_bytes: number; timeout_seconds: number; quality_verification: string };
type Evidence = { chapter_id: string; chapter_version: number; content_sha256: string; start: number; end: number; quote: string };
type Candidate = { id: string; title: string; fields: unknown; rationale: string; evidence: Evidence[]; analysis_source: string };
type ModelRequest = { id: string; version: number; node_id: string; graph_id: string; target_version: number; title: string; created_at?: string; stale: boolean; instruction?: string; template_id?: string; candidate_count?: number; model_preview?: ModelPreview | null; model_execution?: { job_id: string; status: string; receipt_state: string; usage_state: string; model_called?: boolean; failure_code?: string; accounting?: unknown } | null; model_candidates: Candidate[]; candidates_digest?: string | null; saved_proposals: Record<string, string> };
type Props = { client: ExperimentalClient; node?: Row; chapter?: Chapter; sourceReady: boolean; instruction: string; templateId: string; requestedJobId?: string; onOpenProposal: (id: string) => void };
const base = '/planning/model/requests';
let scopeSequence = 0;
export function PlanningModelPanel(props: Props) {
  const identity = useMemo(() => ++scopeSequence, [props.client]);
  const [opened, setOpened] = useState(false);
  if (!opened && !props.requestedJobId) return <section className="experimental-section" aria-label="分层规划模型请求"><h3>可选的本地模型规划</h3><p>需要原模型中心与准确请求检查功能已启用，并关联 1–3 个已保存章节。手动编辑与 Mock 双方案可继续独立使用。</p><Button onClick={() => setOpened(true)}>打开本地模型规划</Button></section>;
  return <PlanningModelBody key={identity} {...props} />;
}
function PlanningModelBody({ client, node, chapter, sourceReady, instruction, templateId, requestedJobId, onOpenProposal }: Props) {
  const [catalog, setCatalog] = useState<ModelCatalog>(), [routeId, setRouteId] = useState('');
  const [candidateCount, setCandidateCount] = useState(2), [selectedId, setSelectedId] = useState(''), [dismissedJob, setDismissedJob] = useState<string>();
  const [reviewed, setReviewed] = useState(false), [reviewedCandidates, setReviewedCandidates] = useState<string[]>([]);
  const [suspended, setSuspended] = useState(false), [unconfirmed, setUnconfirmed] = useState(false), [notice, setNotice] = useState('');
  useLayoutEffect(() => { setDismissedJob(undefined); }, [requestedJobId]);
  const targetJob = requestedJobId && requestedJobId !== dismissedJob ? requestedJobId : undefined;
  const requests = useResource(async signal => {
    const value = await client.get<{ items: ModelRequest[] }>(base, signal);
    return { items: Array.isArray(value.items) ? value.items : [], targetJob };
  }, [client, targetJob]);
  const listReady = !requests.loading && !requests.error && requests.data?.targetJob === targetJob;
  const matches = listReady ? requests.data!.items.filter(row => targetJob ? row.model_execution?.job_id === targetJob : row.id === selectedId) : [];
  const selected = matches.length === 1 ? matches[0] : undefined;
  const runId = selected?.id || '';
  const detailKey = JSON.stringify([targetJob, runId, selected?.version]);
  const detail = useResource(async signal => {
    if (!runId) return undefined;
    const row = await client.get<ModelRequest>(`${base}/${segment(runId)}`, signal);
    if (row.id !== runId || row.node_id !== selected?.node_id || row.graph_id !== selected?.graph_id || targetJob && row.model_execution?.job_id !== targetJob) throw new Error('PLANNING_MODEL_REQUEST_ID_MISMATCH');
    return { row, key: detailKey };
  }, [client, detailKey]);
  const run = listReady && !detail.loading && !detail.error && detail.data?.key === detailKey && detail.data.row.version === selected?.version ? detail.data.row : undefined;
  const inputKey = JSON.stringify([node?.id, node?.version, node?.links, chapter?.id, chapter?.version, instruction, templateId, candidateCount]);
  const key = JSON.stringify([inputKey, detailKey, routeId, run?.version]);
  const live = useRef({ key, epoch: 0 });
  if (live.current.key !== key) live.current = { key, epoch: live.current.epoch + 1 };
  const epoch = live.current.epoch;
  const current = () => live.current.epoch === epoch;
  const previousInput = useRef(inputKey);
  useLayoutEffect(() => {
    if (previousInput.current !== inputKey) { setSuspended(true); setReviewed(false); setReviewedCandidates([]); previousInput.current = inputKey; }
  }, [inputKey]);
  useLayoutEffect(() => { setReviewed(false); setReviewedCandidates([]); }, [detailKey, run?.version, run?.model_preview?.preview_digest, run?.candidates_digest]);
  useLayoutEffect(() => { setRouteId(run?.model_preview?.broker.chosen?.route_id || ''); }, [run?.id]);
  const action = useReviewAction();
  const linkedChapters: string[] = Array.isArray(node?.links?.chapter_ids) ? node.links.chapter_ids : [];
  const instructionLength = Array.from(instruction).length;
  const canCreate = listReady && instructionLength <= 4000 && sourceReady && !!node && node.status !== 'ARCHIVED' && linkedChapters.length >= 1 && linkedChapters.length <= 3 && !!templateId;
  const execution = run?.model_execution;
  const fresh = !!run && !run.stale && !suspended && !unconfirmed;
  const preview = fresh ? run.model_preview : undefined;
  const candidatesReady = fresh && execution?.status === 'COMPLETED' && execution.receipt_state === 'RECORDED' && !!run.candidates_digest;
  const localRoute = catalog?.profile === 'LOCAL_ONLY' && catalog.max_cost_microusd === 0 && catalog.routes.some(row => row.route_id === routeId && row.available);
  const canPreview = !!run && !run.stale && !execution && !unconfirmed && !!localRoute;
  const canDispatch = !!preview?.execution_available && !!preview.preview_digest && !execution && reviewed && preview.broker.chosen?.route_id === routeId;
  const busy = action.busy;
  const reload = () => { live.current.epoch++; setReviewed(false); setReviewedCandidates([]); setNotice(''); if (!runId) setUnconfirmed(false); requests.reload(); detail.reload(); };
  const readOriginal = () => action.run(async isCurrent => {
    if (!runId || !selected) { reload(); return; }
    setSuspended(true); setReviewed(false); setReviewedCandidates([]);
    const value = await client.get<ModelRequest>(`${base}/${segment(runId)}`);
    if (!isCurrent() || !current()) return;
    if (value.id !== runId || value.node_id !== selected.node_id || value.graph_id !== selected.graph_id || targetJob && value.model_execution?.job_id !== targetJob) throw new Error('PLANNING_MODEL_REQUEST_ID_MISMATCH');
    setUnconfirmed(false); setSuspended(false); requests.reload(); detail.reload();
  });
  const create = () => action.run(async isCurrent => {
    if (!current() || !canCreate || targetJob) return;
    setUnconfirmed(true); setReviewed(false); setReviewedCandidates([]); setNotice('');
    const value = await client.post<ModelRequest>(base, { node_id: node!.id, expected_node_version: node!.version, template_id: templateId, instruction, candidate_count: candidateCount });
    if (!isCurrent() || !current()) return;
    if (!value.id || value.node_id !== node!.id || value.target_version !== node!.version) throw new Error('PLANNING_MODEL_REQUEST_ID_MISMATCH');
    setSelectedId(value.id); setRouteId(''); setSuspended(false); setUnconfirmed(false); requests.reload(); detail.reload(); setNotice('规划请求已保存。尚未调用模型，请选择本地路线并核对准确预览。');
  });
  const loadCatalog = () => action.run(async isCurrent => {
    const value = await client.get<ModelCatalog>('/planning/model/catalog');
    if (isCurrent() && current()) setCatalog(value);
  });
  const mutate = (operation: 'preview' | 'dispatch' | 'refresh' | 'cancel') => action.run(async isCurrent => {
    if (!current() || !run || operation === 'preview' && !canPreview || operation === 'dispatch' && !canDispatch || ['refresh', 'cancel'].includes(operation) && !execution) return;
    setReviewed(false); setReviewedCandidates([]); setUnconfirmed(true); setNotice('');
    const value = await client.post<ModelRequest>(`${base}/${segment(run.id)}/${operation}`, { expected_version: run.version, ...(operation === 'preview' ? { route_id: routeId } : operation === 'dispatch' ? { reviewed_preview_digest: preview!.preview_digest } : {}) });
    if (!isCurrent() || !current()) return;
    if (value.id !== run.id || value.node_id !== run.node_id || value.graph_id !== run.graph_id || value.target_version !== run.target_version || operation === 'preview' && value.model_preview?.broker.chosen?.route_id !== routeId) throw new Error('PLANNING_MODEL_REQUEST_ID_MISMATCH');
    setUnconfirmed(false); setSuspended(false); requests.reload(); detail.reload();
  });
  const save = (candidate: Candidate) => action.run(async isCurrent => {
    if (!current() || !candidatesReady || !run?.candidates_digest || !reviewedCandidates.includes(candidate.id) || run.saved_proposals?.[candidate.id]) return;
    setReviewedCandidates([]); setUnconfirmed(true); setNotice('');
    const value = await client.post<{ run: ModelRequest; proposal_id: string; graph_id: string; node_id: string; replayed: boolean }>(`${base}/${segment(run.id)}/candidates/${segment(candidate.id)}/save`, { expected_version: run.version, reviewed_candidates_digest: run.candidates_digest });
    if (!isCurrent() || !current()) return;
    if (value.run.id !== run.id || value.run.node_id !== run.node_id || value.run.graph_id !== run.graph_id || value.node_id !== run.node_id || value.graph_id !== run.graph_id || !value.proposal_id) throw new Error('PLANNING_MODEL_REQUEST_ID_MISMATCH');
    setUnconfirmed(false); setSuspended(false); requests.reload(); detail.reload(); setNotice('已保存为原节点的 REVIEW 待审方案。还需明确批准规划；正文与 Canon 未改动。'); onOpenProposal(value.proposal_id);
  });
  return <section className="experimental-section" aria-label="分层规划模型请求">
    <h3>可选的本地模型规划</h3>
    <p>输入仅为原节点已保存的规划、其关联的 1–3 个已保存章节与方案指令。节点表单中未保存的标题、结构字段和关联不会发送。只支持本地已知零费用路线，不安装模型、不回退云端、不读取其他分支。</p>
    <p>先保存请求并查看准确内容，再单独同意发送。模型候选仅是建议，真实文学质量未验证；保存候选只进入原规划审核。</p>
    {targetJob && <section aria-label="任务中心原规划模型任务"><p>正在定位原模型任务 {targetJob}；只读取原请求，不重建或重发任务。</p>
      {listReady && !selected && <StatusMessage tone="warning">原模型任务在当前授权记录中不可用或身份不唯一；不会选择其他请求。</StatusMessage>}
      <Button disabled={busy} onClick={() => { live.current.epoch++; setDismissedJob(targetJob); setSelectedId(''); setReviewed(false); setReviewedCandidates([]); }}>退出原规划任务定位</Button>
    </section>}
    {!targetJob && <section aria-label="准备原节点模型请求">
      <p>当前已保存节点：{node ? `${node.title} · ${node.level} · v${node.version}` : '尚未选择'}。关联章节：{linkedChapters.join('、') || '无'}。</p>
      {instructionLength > 4000 && <StatusMessage tone="warning">模型方案指令上限为 4000 个字符，当前 {instructionLength} 个。原指令已保留，请自行精简后再保存模型请求；不会自动截断。</StatusMessage>}
      {(!sourceReady || !node || linkedChapters.length < 1 || linkedChapters.length > 3 || node.status === 'ARCHIVED') && <StatusMessage tone="warning">请先保存可用节点，并在“关联真实记录”中保存 1–3 个章节 ID，再刷新原规划。未关联章节的项目规划不能使用本模型入口。</StatusMessage>}
      <Field label="模型规划候选数量"><select value={candidateCount} disabled={busy} onChange={event => setCandidateCount(Number(event.target.value))}>{[1, 2, 3].map(count => <option key={count} value={count}>{count} 个候选</option>)}</select></Field>
      <Button disabled={busy || !canCreate || unconfirmed} onClick={() => void create()}>保存新的模型规划请求（不发送）</Button>
    </section>}
    <div className="experimental-actions"><Button disabled={busy || requests.loading} onClick={reload}>刷新规划模型记录（保留输入）</Button><Button disabled={busy || !runId} onClick={() => void readOriginal()}>重新读取原规划请求</Button></div>
    <ResourceState loading={requests.loading || !!runId && detail.loading} error={requests.error || detail.error} />
    {(!!requests.error || !!detail.error) && <StatusMessage tone="warning">原记录不可用，旧证据已隐藏。核对权限、来源与功能开关后重新读取；不会自动重发。</StatusMessage>}
    {listReady && !requests.data!.items.length && <EmptyState title="还没有模型规划请求" detail="手动编辑与 Mock 双方案仍可使用。打开此页不会调用模型。" />}
    <Field label="查看原规划模型请求"><select value={runId} disabled={busy || !listReady || !!targetJob} onChange={event => { live.current.epoch++; setSelectedId(event.target.value); setReviewed(false); setReviewedCandidates([]); setSuspended(false); setUnconfirmed(false); setNotice(''); }}><option value="">请选择已保存请求</option>{listReady && requests.data!.items.map(row => <option key={row.id} value={row.id}>{row.title || row.id} · v{row.version}{row.stale ? ' · 来源已变化' : ''}</option>)}</select></Field>
    {run && <section aria-label={`原规划模型请求 ${run.id}`}>
      <p>请求 {run.id} · v{run.version} · 原规划图 {run.graph_id} · 原节点 {run.node_id} · 目标基线 v{run.target_version}</p>
      <p>原请求的指令与模板以准确预览中的已保存内容为准。上方方案指令变化只用于新建请求。</p>
      {run.stale && <StatusMessage tone="warning">来源已变化，旧预览与候选已隐藏。请核对并保存最新原节点，明确创建新的请求。</StatusMessage>}
      {suspended && <StatusMessage tone="warning">当前来源或表单已变化，旧预览与候选已隐藏。重新读取仅核对原请求；新的方案指令与模板需要保存为新请求。</StatusMessage>}
      {!execution && <><Button disabled={busy || run.stale || unconfirmed} onClick={() => void loadCatalog()}>查看本地规划模型路线</Button>
        {catalog && <><Field label="本地规划模型"><select value={routeId} disabled={busy} onChange={event => { live.current.epoch++; setRouteId(event.target.value); setReviewed(false); setReviewedCandidates([]); setSuspended(true); }}><option value="">请选择本地模型</option>{catalog.routes.map(row => <option key={row.route_id} value={row.route_id} disabled={!row.available}>{row.display_name} · {row.provider_id}/{row.model_id}{row.synthetic ? ' · 合成协议测试' : ''}{!row.available ? ' · 不可用' : ''}</option>)}</select></Field>
          {!catalog.routes.length && <EmptyState title="没有已注册的本地规划模型" detail="请在原模型中心配置后刷新。本页不会安装模型或改用云端。" />}
          {catalog.routes.filter(row => !row.available).map(row => <StatusMessage tone="warning" key={row.route_id}>{row.display_name}：{row.reasons.join('；')}</StatusMessage>)}
          <Button disabled={busy || !canPreview} onClick={() => void mutate('preview')}>准备准确规划模型预览</Button>
        </>}
      </>}
      {preview && <section aria-label="准确规划模型预览">
        <Badge>{preview.quality_verification === 'SYNTHETIC_PROTOCOL_ONLY' ? '合成协议测试；真实质量未验证' : '模型建议；真实文学质量未验证'}</Badge>
        <Field label="准确规划模型请求"><textarea readOnly rows={10} value={JSON.stringify(preview.request, null, 2)} /></Field>
        <Details open label="原节点来源、模型与费用预占" value={{ node_id: run.node_id, target_version: run.target_version, sources: preview.sources, source_ranges: preview.source_ranges, truncation: preview.truncation, source_strategy: preview.source_strategy, broker: preview.broker, budget: preview.budget }} />
        <p>每个关联章节仅使用前 16000 个 Unicode 字符；准确范围与摘要如上。组合规划输入上限 18000 个字符，超过上限需选择更小的已保存来源，不能静默删减。</p>
        <p>输出上限 {preview.max_output_bytes} 字节；时限 {preview.timeout_seconds} 秒；Token 数未知。没有概率或文学总分，不自动重试。</p>
        {!preview.execution_available && <StatusMessage tone="warning">当前路线、价格或预算不满足本地已知零费用条件，不能发送。</StatusMessage>}
        {!execution && <><label className="experimental-check"><input type="checkbox" checked={reviewed} disabled={busy || !preview.execution_available} onChange={event => setReviewed(event.target.checked)} />已核对原节点、关联章节、准确请求、模型与零费用预占</label><Button disabled={busy || !canDispatch} onClick={() => void mutate('dispatch')}>明确发送此次规划模型请求</Button></>}
      </section>}
      {execution && <section aria-label="原规划模型 Job"><p>原任务 {execution.job_id} · {execution.status} · {execution.receipt_state}</p><p>用量状态：{execution.usage_state}。{execution.model_called ? '已发生适配器调度，已发送的数据无法撤回。' : '尚未确认适配器调度。'}</p>
        <Details label="原任务费用与核对凭据" value={execution.accounting} />
        {execution.failure_code && <StatusMessage tone="warning">{execution.failure_code}。无效候选不会保存为规划。</StatusMessage>}
        {execution.receipt_state === 'UNKNOWN_NO_AUTOMATIC_REPLAY' && <StatusMessage tone="warning">原任务状态未知。仅核对原 Job，不重放、不重建任务，也不释放未知费用预占。</StatusMessage>}
        <Button disabled={busy} onClick={() => void mutate('refresh')}>查询原任务并核对规划候选</Button><Button disabled={busy || ['COMPLETED', 'FAILED', 'CANCELLED'].includes(execution.status)} onClick={() => void mutate('cancel')}>取消原规划模型任务</Button>
      </section>}
      {fresh && execution?.status === 'COMPLETED' && !run.model_candidates?.length && <StatusMessage>模型没有可保存的有效候选。这不代表原规划或文学质量已通过。</StatusMessage>}
      {candidatesReady && run.model_candidates?.map(candidate => <article className="experimental-record" key={candidate.id} aria-label={`规划模型候选 ${candidate.title}`}>
        <h4>{candidate.title}</h4><Badge>{candidate.analysis_source === 'SYNTHETIC_PROTOCOL_ONLY' ? '合成协议测试' : 'AI_SUGGESTION · 模型建议'} · 真实质量未验证</Badge><p>{candidate.rationale}</p>
        <Details open label="候选规划字段" value={candidate.fields} />
        {candidate.evidence.map((proof, index) => <section key={index}><p>原章节 {proof.chapter_id} v{proof.chapter_version} · 原始 Markdown Unicode 范围 {proof.start}–{proof.end}（不含结束位置）</p><p>内容摘要 {proof.content_sha256}</p><Field label={`规划候选 ${candidate.id} 引文 ${index + 1}`}><textarea readOnly value={proof.quote} /></Field></section>)}
        {run.saved_proposals?.[candidate.id] ? <StatusMessage>已保存为原规划待审方案 {run.saved_proposals[candidate.id]}。</StatusMessage> : <><label className="experimental-check"><input type="checkbox" checked={reviewedCandidates.includes(candidate.id)} disabled={busy || !run.candidates_digest} onChange={event => setReviewedCandidates(values => event.target.checked ? [...values, candidate.id] : values.filter(id => id !== candidate.id))} />已核对候选 {candidate.title} 的字段与原文证据</label><Button disabled={busy || !run.candidates_digest || !reviewedCandidates.includes(candidate.id)} onClick={() => void save(candidate)}>将候选 {candidate.title} 保存为原规划待审方案</Button></>}
      </article>)}
      {!!Object.keys(run.saved_proposals || {}).length && <section aria-label="已保存原规划方案"><h4>已保存的原规划方案</h4><p>即使原请求来源已变化，仍可重新读取这些原方案。这里不复用旧候选证据，也不自动批准。</p>{Object.entries(run.saved_proposals).map(([candidateId, proposalId]) => <div className="experimental-record" key={candidateId}><p>候选 {candidateId} → 原方案 {proposalId}</p><Button disabled={busy} onClick={() => { if (current()) onOpenProposal(proposalId); }}>打开原规划待审方案</Button></div>)}</section>}
    </section>}
    {unconfirmed && <StatusMessage tone="warning">本次操作尚未核实，输入保留。请重新读取原请求或刷新记录核对已保存状态；不会自动再次发送。</StatusMessage>}
    {!!action.error && <ErrorMessage error={action.error} />}{notice && <StatusMessage tone="success">{notice}</StatusMessage>}
  </section>;
}
