import { useEffect, useRef, useState } from 'react';
import { ApiError, apiErrorView } from '../api';
import { Badge, Button, StatusMessage } from '../ui/primitives';
import type { StudioGraphClient } from './studioGraphClient';
import type { StudioGraphAction, StudioGraphPreflight, StudioGraphRecord, StudioGraphRun } from './studioGraphTypes';
import { graphId } from './graphDraft';
import { GRAPH_STATUS_LABELS } from './studioGraphLabels';

type Props = { client: StudioGraphClient; graph?: StudioGraphRecord; targetNodeIds: string[]; dirty: boolean; busy: boolean; canMutate: boolean; canReview: boolean;
  isCurrent: () => boolean; read: <T>(work: () => Promise<T>) => Promise<T>; mutate: <T>(work: () => Promise<T>) => Promise<T> };

export function GraphRunPanel(props: Props) {
  return <ScopedGraphRunPanel key={`${props.graph?.id || 'new'}:${props.graph?.version || 0}`} {...props} />;
}
function ScopedGraphRunPanel({ client, graph, targetNodeIds, dirty, busy, canMutate, canReview, isCurrent, read, mutate }: Props) {
  const [preflight, setPreflight] = useState<StudioGraphPreflight>(), [reviewed, setReviewed] = useState(false), [outputReviewed, setOutputReviewed] = useState(false);
  const [runs, setRuns] = useState<StudioGraphRun[]>([]), [selected, setSelected] = useState<StudioGraphRun>();
  const [error, setError] = useState(''), [notice, setNotice] = useState(''), [loading, setLoading] = useState(false), [uncertain, setUncertain] = useState(false), [note, setNote] = useState('');
  const alive = useRef(true), pending = useRef(false), selectionEpoch = useRef(0), listEpoch = useRef(0);
  const creation = useRef<{ identity: string; request: string }>();
  const targetsKey = JSON.stringify([...targetNodeIds].sort());
  const targetIdentity = useRef(targetsKey); targetIdentity.current = targetsKey;
  const current = () => alive.current && isCurrent();
  const locked = busy || dirty;
  useEffect(() => { alive.current = true; return () => { alive.current = false; selectionEpoch.current++; listEpoch.current++; }; }, []);
  useEffect(() => { setPreflight(undefined); setReviewed(false); creation.current = undefined; }, [targetsKey, dirty]);
  const failure = (value: unknown) => { if (current()) setError(apiErrorView(value, '运行操作未完成，请核对当前记录。').message); };

  async function inspect() {
    if (!graph || locked || pending.current || !current()) return;
    const identity = targetsKey; pending.current = true; setLoading(true); setError(''); setReviewed(false);
    try {
      const value = await read(() => client.preflight(graph.id, { expected_version: graph.version, target_node_ids: [...targetNodeIds] }));
      if (current() && targetIdentity.current === identity) setPreflight(value);
    } catch (value) { failure(value); }
    finally { pending.current = false; if (current()) setLoading(false); }
  }
  async function listRuns() {
    if (!graph || !current()) return;
    const epoch = ++listEpoch.current; setLoading(true); setError('');
    try { const value = await read(() => client.runs(graph.id)); if (current() && epoch === listEpoch.current) setRuns(value.items); }
    catch (value) { if (epoch === listEpoch.current) failure(value); }
    finally { if (current() && epoch === listEpoch.current) setLoading(false); }
  }
  async function openRun(id: string) {
    if (pending.current || !current()) return;
    const epoch = ++selectionEpoch.current; setSelected(undefined); setOutputReviewed(false); setUncertain(false); setError('');
    try { const value = await read(() => client.getRun(id)); if (current() && epoch === selectionEpoch.current && value.graph_id === graph?.id) setSelected(value); }
    catch (value) { if (epoch === selectionEpoch.current) failure(value); }
  }
  async function createRun() {
    if (!graph || !preflight?.executable || !reviewed || locked || !canMutate || pending.current || !current()) return;
    const identity = JSON.stringify([graph.id, graph.version, preflight.preflight_digest, preflight.target_node_ids]);
    if (creation.current?.identity !== identity) creation.current = { identity, request: graphId('run') };
    pending.current = true; setError('');
    const epoch = ++selectionEpoch.current;
    try {
      const value = await mutate(() => client.createRun(graph.id, { expected_graph_version: graph.version, reviewed_preflight_digest: preflight.preflight_digest, target_node_ids: [...preflight.target_node_ids], request_id: creation.current!.request }));
      if (current() && epoch === selectionEpoch.current) { listEpoch.current++; setLoading(false); setSelected(value); setRuns(rows => [...rows.filter(row => row.id !== value.id), value]); setUncertain(false); setReviewed(false); setNotice('运行记录已建立。尚未自动执行节点。'); creation.current = undefined; }
    } catch (value) { if (current()) { failure(value); setUncertain(true); setNotice('创建回执需要核对。可以读取运行记录；再次创建会明确复用同一请求标识，不会自动重试。'); } }
    finally { pending.current = false; }
  }
  async function action(action: StudioGraphAction) {
    if (!selected || locked || pending.current || !current()) return;
    const reviewing = action === 'approve' || action === 'reject';
    if (reviewing ? !canReview || !selected.review || !outputReviewed : !canMutate) return;
    if (uncertain && action !== 'cancel') return;
    pending.current = true; setError(''); const epoch = selectionEpoch.current, source = selected;
    try {
      const value = await mutate(() => client.action(source.id, action, { expected_version: source.version, ...(reviewing ? { node_id: source.review!.node_id, reviewed_output_digest: source.review!.output_digest } : {}), note }));
      if (current() && epoch === selectionEpoch.current) { listEpoch.current++; setLoading(false); setSelected(value); setRuns(rows => [...rows.filter(row => row.id !== value.id), value]); setOutputReviewed(false); setUncertain(false); setNotice('原工作流运行记录已更新；正文和资产未被写入。'); }
    } catch (value) { if (current() && epoch === selectionEpoch.current) { failure(value); if (!(value instanceof ApiError) || value.status === 0 || value.status >= 500 || value.status === 409) setUncertain(true); } }
    finally { pending.current = false; }
  }
  const terminal = selected && ['SUCCEEDED', 'FAILED', 'CANCELLED', 'REJECTED'].includes(selected.status);
  return <section className="studio-graph-run" aria-label="创作图运行与审核">
    <h3>本地节点运行</h3><p>仅通过原工作流处理作者输入、手工结果和本地规则。无模型调用；资产引用节点尚无执行适配。审核不会改写正文或原文件。</p>
    {!graph && <p>先保存创作图，再核对选中节点的运行范围。</p>}{dirty && <StatusMessage tone="warning">创作图有未保存修改，请先保存后运行。</StatusMessage>}
    {error && <StatusMessage tone="error">{error}</StatusMessage>}{notice && <StatusMessage>{notice}</StatusMessage>}
    <Button disabled={!graph || locked || loading} onClick={() => void inspect()}>核对运行范围</Button><Button disabled={!graph || loading || busy} onClick={() => void listRuns()}>读取运行记录</Button>
    {loading && <StatusMessage>正在读取原工作流信息…</StatusMessage>}
    {preflight && <section aria-label="运行预检"><p>选中范围 {preflight.selected_closure.length} 个节点；顺序：{preflight.execution_order.join(' → ') || '无可执行节点'}</p><p>未选择目标时核对整个图；不相连的组件不会被自动连线。</p>{preflight.issues.map((issue, index) => <StatusMessage key={`${issue.code}:${issue.node_id}:${index}`} tone="warning">{issue.code}{issue.node_id ? ` · ${issue.node_id}` : ''}</StatusMessage>)}<label><input type="checkbox" checked={reviewed} disabled={locked || !preflight.executable || !canMutate} onChange={event => setReviewed(event.target.checked)} />已核对当前图版本、节点范围与本地处理边界</label><Button disabled={locked || !reviewed || !preflight.executable || !canMutate} onClick={() => void createRun()}>{uncertain && !selected ? '使用同一请求重试创建运行' : '创建本地运行'}</Button></section>}
    {!!runs.length && <label>已保存运行<select aria-label="已保存运行" disabled={busy} value={selected?.id || ''} onChange={event => { if (event.target.value) void openRun(event.target.value); }}><option value="">选择运行记录</option>{runs.map(row => <option key={row.id} value={row.id}>{row.id} · {GRAPH_STATUS_LABELS[row.status] || row.status} · v{row.version}</option>)}</select></label>}
    {selected && <section aria-label="当前创作图运行"><p>运行 {selected.id} · v{selected.version} · 图 v{selected.graph_version}</p><Badge>{GRAPH_STATUS_LABELS[selected.status] || selected.status}</Badge><p>缓存命中 {selected.cache.hits} / 未命中 {selected.cache.misses}；仅同图版本的已审核本地结果。</p><p>模型调用：无 · 外部调用：0 · 应用到正文：否</p><p>运行时限 {selected.timeout_seconds} 秒 · 截止 {selected.deadline_at}。暂停、恢复与审核不会重新计时。</p>
      {selected.stale && <StatusMessage tone="warning">来源图已经变化，运行输出不可继续采用，请重新核对当前图。</StatusMessage>}
      {uncertain && <StatusMessage tone="warning">版本或回执不确定。请先重新读取运行，不会自动重复动作。</StatusMessage>}
      <Button disabled={busy} onClick={() => void openRun(selected.id)}>重新读取当前运行</Button>
      <ul>{Object.entries(selected.node_states).map(([id, state]) => <li key={id}>{id} · {GRAPH_STATUS_LABELS[state.status] || state.status}{state.error && <span> · {state.error.code}</span>}</li>)}</ul>
      <label>运行备注<input maxLength={1000} disabled={locked} value={note} onChange={event => setNote(event.target.value)} /></label>
      {!terminal && <div className="studio-graph-actions"><Button disabled={locked || !canMutate || uncertain || selected.stale || selected.status !== 'QUEUED'} onClick={() => void action('execute')}>执行本地节点</Button><Button disabled={locked || !canMutate || uncertain || selected.stale || !['QUEUED', 'RUNNING', 'WAITING_APPROVAL'].includes(selected.status)} onClick={() => void action('pause')}>暂停运行</Button><Button disabled={locked || !canMutate || uncertain || selected.stale || selected.status !== 'PAUSED'} onClick={() => void action('resume')}>恢复运行</Button><Button variant="danger" disabled={locked || !canMutate} onClick={() => void action('cancel')}>取消运行</Button></div>}
      {selected.review && !selected.stale && <section aria-label="节点输出审核"><h4>待审核输出 · {selected.review.node_id}</h4><p>来源：{selected.review.draft.origin === 'MANUAL' ? '手工填写' : '作者输入'}</p><pre>{selected.review.draft.text}</pre>{selected.review.draft.direction && <p>导演备注：{selected.review.draft.direction.note}</p>}{selected.review.draft.plan && <ol>{selected.review.draft.plan.map(row => <li key={row.sequence}>{row.beat}</li>)}</ol>}<label><input type="checkbox" checked={outputReviewed} disabled={locked || !canReview || uncertain} onChange={event => setOutputReviewed(event.target.checked)} />已阅读本次输出并核对当前审核摘要</label><Button disabled={locked || !canReview || !outputReviewed || uncertain} onClick={() => void action('approve')}>批准节点输出</Button><Button disabled={locked || !canReview || !outputReviewed || uncertain} onClick={() => void action('reject')}>驳回节点输出</Button></section>}
    </section>}
  </section>;
}
