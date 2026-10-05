import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Badge, Button, Panel, StatusMessage } from '../ui/primitives';
import type { ExperimentalClient } from './api';
import { Details, Field, ResourceState, useAction, useResource } from './shared';
import { declarativeAgentsClient, type AgentDefinition, type AgentPreflight, type AgentRun, type AuthoredWorkflow, type SchemaField } from './declarativeAgentsClient';
let sequence = 0;
const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value));
export function DeclarativeAgentsPanel(props: { client: ExperimentalClient }) {
  const key = useMemo(() => ++sequence, [props.client]); return <AgentsBody key={key} {...props} />;
}
function SchemaEditor({ label, fields, update }: { label: string; fields: SchemaField[]; update: (fields: SchemaField[]) => void }) {
  return <fieldset><legend>{label}（有限标量对象）</legend>
    {fields.map((field, index) => <div className="experimental-record" key={index}>
      <div className="experimental-grid"><Field label={`${label}字段 ${index + 1} 名称`}><input value={field.name} maxLength={40} onChange={e => update(fields.map((f, i) => i === index ? { ...f, name: e.target.value } : f))} /></Field><Field label={`${label}字段 ${index + 1} 类型`}><select value={field.type} onChange={e => update(fields.map((f, i) => i === index ? { ...f, type: e.target.value as SchemaField['type'] } : f))}><option value="string">文字</option><option value="number">数字</option><option value="boolean">布尔值</option></select></Field><Field label={`${label}字段 ${index + 1} 字数上限`}><input type="number" min={1} max={8000} value={field.max_length} onChange={e => update(fields.map((f, i) => i === index ? { ...f, max_length: Number(e.target.value) } : f))} /></Field></div>
      <label><input type="checkbox" checked={field.required} onChange={e => update(fields.map((f, i) => i === index ? { ...f, required: e.target.checked } : f))} />{label}字段 {index + 1} 必填</label><Button disabled={fields.length === 1} onClick={() => update(fields.filter((_, i) => i !== index))}>移除{label}字段 {index + 1}</Button>
    </div>)}
    <Button disabled={fields.length >= 12} onClick={() => update([...fields, { name: label === '输出' ? 'summary' : 'notes', type: 'string', required: false, max_length: 8000 }])}>添加{label}字段</Button>
  </fieldset>;
}
function AgentsBody({ client }: { client: ExperimentalClient }) {
  const api = useMemo(() => declarativeAgentsClient(client), [client]);
  const catalog = useResource(signal => api.catalog(signal), [api]);
  const definitions = useResource(signal => api.definitions(signal), [api]);
  const runs = useResource(signal => api.runs(signal), [api]);
  const [definition, setDefinition] = useState<AuthoredWorkflow>(), [saved, setSaved] = useState<AgentDefinition>();
  const [preflight, setPreflight] = useState<AgentPreflight>(), [reviewGraph, setReviewGraph] = useState(false);
  const [input, setInput] = useState<Record<string, string>>({ source_text: '林舟等潮落。\n同伴举起合成地图。' }), [chapterId, setChapterId] = useState('');
  const [run, setRun] = useState<AgentRun>(), [reviewNote, setReviewNote] = useState(''), [reviewOutput, setReviewOutput] = useState(false);
  const [edgeSource, setEdgeSource] = useState(''), [edgeTarget, setEdgeTarget] = useState('');
  const alive = useRef(true), formEpoch = useRef(0), runEpoch = useRef(0), initialized = useRef(false), nextNode = useRef(1);
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; formEpoch.current++; runEpoch.current++; }; }, []);
  useEffect(() => { if (catalog.data && !initialized.current) { initialized.current = true; setDefinition(clone(catalog.data.default_definition)); } }, [catalog.data]);
  const action = useAction();
  const edit = (next: AuthoredWorkflow) => { formEpoch.current++; setDefinition(next); setPreflight(undefined); setReviewGraph(false); };
  const agentEdit = (value: Partial<AuthoredWorkflow['agent']>) => definition && edit({ ...definition, agent: { ...definition.agent, ...value } });
  const choose = (row?: AgentDefinition) => { formEpoch.current++; setSaved(row); setDefinition(clone(row?.definition || catalog.data!.default_definition)); setPreflight(undefined); setReviewGraph(false); };
  const dirty = !!definition && JSON.stringify(definition) !== JSON.stringify(saved?.definition);
  const runAction = (name: string) => action.run(async () => { if (!run) return; const ticket = runEpoch.current; const result = await api.transition(run, name, reviewNote); if (alive.current && ticket === runEpoch.current) { setRun(result); setReviewOutput(false); runs.reload(); } }, name === 'approve' ? '审核已记录，结果仍为草稿材料。正文与 Canon 未写入。' : '工作流状态已更新。');
  const usable = !!run && !run.stale;
  return <section className="experimental-section" aria-label="Agent 与 Workflow">
    <div className="experimental-actions"><h3>Agent 与 Workflow</h3><Badge>声明式 · 本地规则</Badge><Button disabled={action.busy} onClick={() => { catalog.reload(); definitions.reload(); runs.reload(); setPreflight(undefined); }}>刷新授权目录与记录</Button></div>
    <p>复用原 Workflow DAG 与人工审核节点。此版本支持一条相连的流程链，最多 16 步。Python、JavaScript、shell、动态 import 与任意第三方插件均为 DENY_ALL。</p>
    <ResourceState loading={catalog.loading} error={catalog.error} />
    {catalog.data && !catalog.error && <>
      <Panel title="Agent 表单与已保存定义">
        <ResourceState loading={definitions.loading} error={definitions.error} />
        <Field label="已保存的 Agent 定义"><select value={saved?.id || ''} disabled={action.busy || definitions.loading || !!definitions.error} onChange={e => choose(definitions.data?.items.find(d => d.id === e.target.value))}><option value="">新建独立定义</option>{definitions.data?.items.map(d => <option key={d.id} value={d.id}>{d.definition.agent.title} · v{d.version}</option>)}</select></Field>
        {definition && <>
          <Field label="Agent 名称"><input maxLength={160} value={definition.agent.title} onChange={e => agentEdit({ title: e.target.value })} /></Field>
          <Field label="Agent 用途"><textarea maxLength={2000} value={definition.agent.purpose} onChange={e => agentEdit({ purpose: e.target.value })} /></Field>
          <Field label="角色提示词"><textarea rows={4} maxLength={8000} value={definition.agent.role_prompt} onChange={e => agentEdit({ role_prompt: e.target.value })} /></Field>
          <p>提示词仅保存为声明，不能授予权限。本地规则节点不解释提示词，也不冒充模型写作。模型生成还需要绑定原授权执行器，目前此自定义 Agent 路径不可用。</p>
          <Field label="已注册模型路线"><select value={definition.agent.model_route || ''} onChange={e => agentEdit({ model_route: e.target.value || null })}><option value="">无模型：确定性本地规则</option>{catalog.data.model_routes.map(route => <option key={route.id} value={route.id}>{route.provider_id} / {route.model_id} · 缺少绑定执行器</option>)}</select></Field>
          {definition.agent.model_route && <StatusMessage tone="warning">CUSTOM_AGENT_BOUND_EXECUTOR_REQUIRED：可以保存配置，不能从这个入口执行模型、启用云兜底或支出预算。</StatusMessage>}
          <fieldset><legend>服务端注册的允许工具</legend>{catalog.data.tools.map(tool => <label key={tool}><input type="checkbox" checked={definition.agent.allowed_tools.includes(tool)} onChange={e => agentEdit({ allowed_tools: e.target.checked ? [...definition.agent.allowed_tools, tool] : definition.agent.allowed_tools.filter(t => t !== tool) })} />{tool}</label>)}</fieldset>
          <SchemaEditor label="输入" fields={definition.agent.input_schema.fields} update={fields => agentEdit({ input_schema: { fields } })} />
          <SchemaEditor label="输出" fields={definition.agent.output_schema.fields} update={fields => agentEdit({ output_schema: { fields } })} />
          <p>本地适配器要求 source_text 输入；输出支持 draft 与 summary 文字字段。Schema 不执行表达式、正则或外部引用。</p>
          <div className="experimental-grid"><Field label="Agent 最大步骤"><input type="number" min={3} max={16} value={definition.agent.max_steps} onChange={e => agentEdit({ max_steps: Number(e.target.value) })} /></Field><Field label="运行时限（秒）"><input type="number" min={1} max={300} value={definition.agent.timeout_seconds} onChange={e => agentEdit({ timeout_seconds: Number(e.target.value) })} /></Field><Field label="每节点输出上限（字节）"><input type="number" min={256} max={128000} value={definition.agent.max_output_bytes} onChange={e => agentEdit({ max_output_bytes: Number(e.target.value) })} /></Field><Field label="成本上限（微美元）"><input type="number" value={0} readOnly /></Field></div>
          <label><input type="checkbox" checked readOnly />必须经过显式人工审核，结果只产草稿</label>
        </>}
      </Panel>
      {definition && <Panel title="Workflow 节点与连接编辑">
        <p>每个节点来自服务器注册表。最后必须是人工审核 → 保存审核材料；新增准备节点后，可在下方修改连接并运行真实 DAG 预检。</p>
        <ol>{definition.nodes.map((node, index) => <li key={node.id} className="experimental-record">
          <p>节点 ID：{node.id}</p><div className="experimental-grid"><Field label={`节点 ${index + 1} 名称`}><input value={node.name} maxLength={160} onChange={e => edit({ ...definition, nodes: definition.nodes.map((n, i) => i === index ? { ...n, name: e.target.value } : n) })} /></Field><Field label={`节点 ${index + 1} 类型`}><select value={node.type} onChange={e => edit({ ...definition, nodes: definition.nodes.map((n, i) => i === index ? { ...n, type: e.target.value } : n) })}>{catalog.data!.node_types.map(t => <option key={t} value={t}>{t}</option>)}</select></Field></div>
          <Button disabled={definition.nodes.length <= 3} onClick={() => edit({ ...definition, nodes: definition.nodes.filter(n => n.id !== node.id), edges: definition.edges.filter(e => e.source !== node.id && e.target !== node.id) })}>移除节点 {index + 1}</Button>
        </li>)}</ol>
        <Button disabled={definition.nodes.length >= 16} onClick={() => { let id: string; do { id = 'local' + nextNode.current++; } while (definition.nodes.some(n => n.id === id)); edit({ ...definition, nodes: [...definition.nodes, { id, type: 'checkpoint', name: '本地检查点' }] }); }}>添加注册节点</Button>
        <ul aria-label="Workflow 连接">{definition.edges.map((edge, index) => <li key={index}>{edge.source} → {edge.target} <Button onClick={() => edit({ ...definition, edges: definition.edges.filter((_, i) => i !== index) })}>移除连接 {index + 1}</Button></li>)}</ul>
        <div className="experimental-grid"><Field label="连接起点"><select value={edgeSource} onChange={e => setEdgeSource(e.target.value)}><option value="">选择起点</option>{definition.nodes.map(n => <option key={n.id} value={n.id}>{n.id} · {n.name}</option>)}</select></Field><Field label="连接终点"><select value={edgeTarget} onChange={e => setEdgeTarget(e.target.value)}><option value="">选择终点</option>{definition.nodes.map(n => <option key={n.id} value={n.id}>{n.id} · {n.name}</option>)}</select></Field></div>
        <Button disabled={!edgeSource || !edgeTarget || definition.edges.length >= 40} onClick={() => edit({ ...definition, edges: [...definition.edges, { source: edgeSource, target: edgeTarget }] })}>添加连接</Button>
        <div className="experimental-actions"><Button disabled={action.busy} onClick={() => action.run(async () => { const ticket = formEpoch.current; const result = await api.preflight(definition); if (alive.current && ticket === formEpoch.current) setPreflight(result); }, '服务端已验证 DAG、工具注册表、Schema 与边界。未执行节点。')}>验证 Workflow 图与权限</Button><Button disabled={action.busy || !definition.agent.title.trim()} onClick={() => action.run(async () => { const ticket = formEpoch.current; const row = await api.save(definition, saved); if (alive.current && ticket === formEpoch.current) { setSaved(row); setDefinition(clone(row.definition)); setPreflight(undefined); setReviewGraph(false); definitions.reload(); } }, '定义已保存。修改旧定义会使此前运行的来源检查失效。')}>{saved ? '保存 Agent 新版本' : '保存 Agent 定义'}</Button></div>
        {saved && <p>已保存定义 {saved.id} · v{saved.version}{dirty ? ' · 当前表单有未保存修改' : ''}</p>}
        {preflight && <><p>拓扑顺序：{preflight.topological_order.join(' → ')}</p>{preflight.blockers.map(b => <StatusMessage key={b} tone="warning">{b}</StatusMessage>)}<p>{preflight.execution_available ? '确定性本地执行可用。' : '执行依赖尚未满足。'}</p></>}
      </Panel>}
      {definition && <Panel title="测试输入与明确启动">
        <p>新运行先保存为排队状态，不会因保存定义或打开页面而执行。人工审核的等待时间计入已启动运行的总时限；超时后需明确重试。</p>
        <Field label="测试输入来源"><select value={chapterId} onChange={e => { setChapterId(e.target.value); setReviewGraph(false); }}><option value="">手工输入合成文字或明确选定的摘录</option>{catalog.data.chapters.map(c => <option key={c.id} value={c.id}>{c.title} · v{c.version}</option>)}</select></Field>
        {definition.agent.input_schema.fields.filter(f => !(chapterId && f.name === 'source_text')).map(f => <Field key={f.name} label={`测试输入 ${f.name}`}><textarea maxLength={f.max_length} value={input[f.name] || ''} onChange={e => { setInput({ ...input, [f.name]: e.target.value }); setReviewGraph(false); }} /></Field>)}
        <label><input type="checkbox" checked={reviewGraph} onChange={e => setReviewGraph(e.target.checked)} />已核对已保存图版本、输入来源、工具范围和限额</label>
        <Button disabled={action.busy || !saved || dirty || !preflight?.execution_available || !reviewGraph} onClick={() => action.run(async () => {
          const value: Record<string, unknown> = {}; for (const f of definition.agent.input_schema.fields) { if (chapterId && f.name === 'source_text') continue; const raw = input[f.name] || ''; if (!f.required && !raw) continue; value[f.name] = f.type === 'number' ? Number(raw) : f.type === 'boolean' ? raw === 'true' : raw; }
          const ticket = runEpoch.current; const row = await api.createRun(saved!, value, chapterId, globalThis.crypto.randomUUID(), catalog.data!.chapters.find(c => c.id === chapterId)?.version ?? null);
          if (alive.current && ticket === runEpoch.current) { setRun(row); setReviewOutput(false); runs.reload(); }
        }, '测试运行已保存为排队状态，请明确执行。')}>创建已核对的测试运行</Button>
      </Panel>}
      <Panel title="持久化逐节点结果与执行轨迹">
        <ResourceState loading={runs.loading} error={runs.error} empty={!runs.data?.items.length} />
        <Field label="查看 Workflow 运行"><select value={run?.id || ''} disabled={action.busy || runs.loading || !!runs.error} onChange={e => { runEpoch.current++; setRun(runs.data?.items.find(r => r.id === e.target.value)); setReviewOutput(false); }}><option value="">请选择运行</option>{runs.data?.items.map(r => <option key={r.id} value={r.id}>{r.id} · {r.status} · 尝试 {r.attempt}</option>)}</select></Field>
        {run && <>
          <p>状态 {run.status} · v{run.version} · 来源定义 v{run.definition_version}</p>
          <Button disabled={action.busy} onClick={() => action.run(async () => { const ticket = runEpoch.current; const current = await api.run(run.id); if (alive.current && ticket === runEpoch.current) setRun(current); }, '已重新核对来源与权限。')}>核对当前运行</Button>
          {run.stale && <StatusMessage tone="warning">定义或来源已变化。历史输出已隐藏，不能继续执行或批准；可取消并从当前来源创建新运行。</StatusMessage>}
          {run.error && <StatusMessage tone="error">{run.error.code}</StatusMessage>}
          <div className="experimental-actions"><Button disabled={action.busy || !usable || run.status !== 'QUEUED'} onClick={() => runAction('execute')}>执行本地节点到审核点</Button><Button disabled={action.busy || !usable || !['QUEUED', 'RUNNING', 'WAITING_APPROVAL'].includes(run.status)} onClick={() => runAction('pause')}>暂停运行</Button><Button disabled={action.busy || !usable || run.status !== 'PAUSED'} onClick={() => runAction('resume')}>继续运行</Button><Button disabled={action.busy || ['SUCCEEDED', 'FAILED', 'CANCELLED', 'REJECTED'].includes(run.status)} onClick={() => runAction('cancel')}>取消运行</Button><Button disabled={action.busy || !usable || !['FAILED', 'CANCELLED'].includes(run.status)} onClick={() => runAction('retry')}>明确重试原快照</Button></div>
          {usable && <>
            <Field label="人工审核备注"><input maxLength={1000} value={reviewNote} onChange={e => setReviewNote(e.target.value)} /></Field>
            {Object.entries(run.node_states).map(([id, state]) => <article key={id} className="experimental-record" aria-label={`节点结果 ${id}`}><p>{id} · {state.status}</p><Details label={`输出 ${id}`} value={state.output} open={state.status === 'SUCCEEDED'} />{state.error != null && <Details label={`错误 ${id}`} value={state.error} />}</article>)}
            {run.status === 'WAITING_APPROVAL' && <><label><input type="checkbox" checked={reviewOutput} onChange={e => setReviewOutput(e.target.checked)} />已查看逐节点结果，仅批准草稿材料，不写入正文或 Canon</label><div className="experimental-actions"><Button disabled={action.busy || !reviewOutput} onClick={() => runAction('approve')}>批准当前审核节点</Button><Button disabled={action.busy} onClick={() => runAction('reject')}>拒绝当前审核节点</Button></div></>}
            {run.agent_output != null && <Details label="已审核草稿输出" value={run.agent_output} open />}
          </>}
          <Details label="原 Workflow 持久化转换轨迹" value={run.trace} /><Details label="逐节点最终派发检查" value={run.dispatch_trace} />
          <p>本地真实确定性转换；模型调用 0；外发 0；正式应用 false。Adapter SDK 是可信宿主契约，不是第三方代码安装入口。</p>
        </>}
      </Panel>
    </>}
    {action.feedback}
  </section>;
}
