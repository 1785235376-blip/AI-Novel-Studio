import { useEffect, useState } from 'react';
import { Badge, Button, Panel, StatusMessage } from '../ui/primitives';
import type { Chapter } from '../api';
import { type ExperimentalClient, type Row, type Rows, segment } from './api';
import { Details, Field, Form, ObjectInput, RecordStatus, Refresh, ResourceState, ids, objectValue, useAction, useResource } from './shared';

const emptyFields = { goal: '', conflict: '', turning_point: '', climax: '', ending_intent: '' };
const fieldLabels: Record<keyof typeof emptyFields, string> = { goal: '目标', conflict: '冲突', turning_point: '转折点', climax: '高潮', ending_intent: '结局意图' };
export function PlanningPanel({ client, chapter }: { client: ExperimentalClient; chapter?: Chapter }) {
  const [graphId, setGraphId] = useState(''), [nodeId, setNodeId] = useState('');
  const overview = useResource(async signal => {
    const [graphs, proposals, templates] = await Promise.all([client.get<Rows>('/planning/graphs', signal), client.get<Rows>('/planning/proposals', signal), client.get<Rows>('/planning/templates', signal)]);
    return { graphs: graphs.items, proposals: proposals.items, templates: templates.items };
  }, [client]);
  const graph = useResource(signal => graphId ? client.get<Row>(`/planning/graphs/${segment(graphId)}`, signal) : Promise.resolve(undefined), [client, graphId]);
  const reload = () => { overview.reload(); graph.reload(); };
  const action = useAction(reload);
  const [graphTitle, setGraphTitle] = useState(''), [title, setTitle] = useState(''), [editingVersion, setEditingVersion] = useState(1);
  const [fields, setFields] = useState(emptyFields), [objectives, setObjectives] = useState('{}'), [beats, setBeats] = useState('{}');
  const [links, setLinks] = useState({ chapter_ids: '', character_ids: '', location_ids: '', world_rule_ids: '', story_route_ids: '' });
  const [instruction, setInstruction] = useState(''), [template, setTemplate] = useState('three-act');
  const [selected, setSelected] = useState<string[]>([]), [comparison, setComparison] = useState<any>();
  const [history, setHistory] = useState<{ proposal: Row; items: Row[] }>();
  const node: Row | undefined = graph.data?.nodes?.find((item: Row) => item.id === nodeId);
  useEffect(() => { if (!graphId && overview.data?.graphs[0]) setGraphId(overview.data.graphs[0].id); }, [overview.data, graphId]);
  useEffect(() => { if (graph.data && !graph.data.nodes?.some((item: Row) => item.id === nodeId)) setNodeId(graph.data.root_node_id); }, [graph.data]);
  useEffect(() => {
    if (!node) return;
    setTitle(node.title); setEditingVersion(node.version);
    setFields(Object.fromEntries(Object.keys(emptyFields).map(key => [key, node.fields?.[key] || ''])) as typeof emptyFields);
    setObjectives(JSON.stringify(node.fields?.character_objectives || {})); setBeats(JSON.stringify(node.fields?.beats || {}));
    setLinks(Object.fromEntries(Object.keys(links).map(key => [key, (node.links?.[key] || []).join(', ')])) as typeof links);
    setSelected([]); setComparison(undefined);
  }, [node?.id]);
  const payload = () => ({ title, fields: { ...fields, character_objectives: objectValue(objectives), beats: objectValue(beats) }, links: Object.fromEntries(Object.entries(links).map(([key, value]) => [key, ids(value)])) });
  const nextLevel = node && ({ PROJECT: 'VOLUME', VOLUME: 'CHAPTER', CHAPTER: 'SCENE' } as Record<string, string>)[node.level];
  const proposals = (overview.data?.proposals || []).filter(row => !nodeId || row.node_id === nodeId);
  const review = (row: Row, operation: string) => action.run(() => client.post(`/planning/proposals/${segment(row.id)}/${operation}`, { expected_version: row.version }), '审核状态已更新');
  const busy = action.busy || overview.loading || graph.loading;
  const requiresRebase = !!node && node.version > editingVersion;
  return <Panel title="分层创作规划 V2" actions={<Refresh reload={reload} busy={busy} />}>
    <StatusMessage>Project → Volume → Chapter → Scene。生成使用 MOCK_ONLY；批准只更新规划，正文与 Canon 保持人工审核流程。</StatusMessage>
    {action.feedback}<ResourceState loading={overview.loading || graph.loading} error={overview.error || graph.error} />
    <Form onSubmit={() => action.run(async () => { const value = await client.post<Row>('/planning/graphs', { title: graphTitle }); setGraphId(value.id); setNodeId(value.root_node_id); setGraphTitle(''); }, '已创建项目规划')}>
      <Field label="规划名称"><input required value={graphTitle} onChange={event => setGraphTitle(event.target.value)} /></Field>
      <Button type="submit" disabled={busy || !graphTitle.trim()}>创建项目规划</Button>
    </Form>
    {!!overview.data?.graphs.length && <Field label="规划图"><select value={graphId} onChange={event => { setGraphId(event.target.value); setNodeId(''); }}><option value="">选择规划</option>{overview.data.graphs.map(row => <option key={row.id} value={row.id}>{row.title}</option>)}</select></Field>}
    {graph.data && <div className="experimental-list" aria-label="规划层级">{graph.data.nodes?.map((row: Row) => <div className={`experimental-record ${nodeId === row.id ? 'is-selected' : ''}`} key={row.id}><Button type="button" aria-pressed={nodeId === row.id} onClick={() => setNodeId(row.id)}>{row.level} · {row.title}</Button><RecordStatus row={row} /><small>父节点：{row.parent_id || '项目根节点'}</small></div>)}</div>}
    {graph.data && <div className="experimental-actions"><Button disabled={busy} onClick={() => action.run(() => client.post(`/planning/graphs/${segment(graph.data!.id)}/${graph.data!.status === 'ARCHIVED' ? 'restore' : 'archive'}`, { expected_version: graph.data!.version }), '规划图归档状态已更新')}>{graph.data.status === 'ARCHIVED' ? '恢复规划图' : '归档规划图'}</Button><Badge>{graph.data.status}</Badge></div>}
    {node && <section className="experimental-section" aria-label="规划节点编辑">
      <h3>编辑 {node.level}</h3>
      {requiresRebase && <section className="experimental-record" aria-label="规划节点版本恢复">
        <StatusMessage tone="warning">当前节点已更新为 v{node.version}，草稿仍以 v{editingVersion} 为基线。你的编辑已保留。请对照当前记录核对草稿，再明确更新保存基线。</StatusMessage>
        <div className="experimental-grid">
          <Details open label={`当前服务器节点 · v${node.version}`} value={{ title: node.title, fields: node.fields, links: node.links }} />
          <Details open label={`保留的编辑草稿 · 基线 v${editingVersion}`} value={{ title, fields, character_objectives_json: objectives, beats_json: beats, links }} />
        </div>
        <p>更新基线只保留当前表单并改变下一次保存的预期版本，不会自动提交，也不会丢弃你的编辑。请先把需要保留的服务器变更合入表单。</p>
        <Button disabled={busy} onClick={() => action.run(async () => { setEditingVersion(node.version); }, '草稿已保留并更新保存基线，尚未提交')}>保留草稿并更新保存基线</Button>
      </section>}
      <Field label="节点标题"><input value={title} onChange={event => setTitle(event.target.value)} /></Field>
      <div className="experimental-grid">{Object.entries(fieldLabels).map(([key, label]) => <Field key={key} label={label}><textarea value={fields[key as keyof typeof fields]} onChange={event => setFields(current => ({ ...current, [key]: event.target.value }))} /></Field>)}</div>
      <ObjectInput label="人物目标（JSON：人物 ID → 目标）" value={objectives} onChange={setObjectives} /><ObjectInput label="自定义节拍（JSON）" value={beats} onChange={setBeats} />
      <details><summary>关联真实记录</summary><div className="experimental-grid">{Object.entries({ chapter_ids: '章节 ID', character_ids: '人物 ID', location_ids: '地点 ID', world_rule_ids: '已批准世界规则 ID', story_route_ids: '剧情路线 ID' }).map(([key, label]) => <Field key={key} label={`${label}（逗号分隔）`}><input value={links[key as keyof typeof links]} onChange={event => setLinks(current => ({ ...current, [key]: event.target.value }))} /></Field>)}</div></details>
      <div className="experimental-actions">
        <Button disabled={busy || requiresRebase || !title.trim() || node.status === 'ARCHIVED' || graph.data?.status === 'ARCHIVED'} onClick={() => action.run(async () => { const value = await client.put<Row>(`/planning/nodes/${segment(node.id)}`, { ...payload(), expected_version: editingVersion, position: node.position }); setEditingVersion(value.version); }, '节点已保存')}>保存节点</Button>
        <Button disabled={busy || requiresRebase || !title.trim()} onClick={() => action.run(() => client.post('/planning/proposals', { ...payload(), node_id: node.id, expected_node_version: editingVersion, rationale: instruction }), '方案已进入审核')}>保存为待审方案</Button>
        {node.level !== 'PROJECT' && <Button disabled={busy || graph.data?.status === 'ARCHIVED' || (node.status !== 'ARCHIVED' && graph.data?.nodes?.some((row: Row) => row.parent_id === node.id && row.status !== 'ARCHIVED'))} onClick={() => action.run(() => client.post(`/planning/nodes/${segment(node.id)}/${node.status === 'ARCHIVED' ? 'restore' : 'archive'}`, { expected_version: node.version }), '规划节点归档状态已更新')}>{node.status === 'ARCHIVED' ? '恢复规划节点' : '归档规划节点'}</Button>}
        {nextLevel && <Button disabled={busy || !title.trim() || ((nextLevel === 'CHAPTER' || nextLevel === 'SCENE') && !chapter && !node.links?.chapter_ids?.length)} onClick={() => action.run(async () => { const value = await client.post<Row>('/planning/nodes', { ...payload(), title: `${nextLevel} ${title}`, graph_id: graphId, parent_id: node.id, level: nextLevel, links: { ...payload().links, chapter_ids: nextLevel === 'SCENE' ? node.links.chapter_ids : nextLevel === 'CHAPTER' ? [chapter?.id] : [] } }); setNodeId(value.id); }, '已创建下级规划')}>添加 {nextLevel} 子节点</Button>}
      </div>
      <Field label="规划模板"><select value={template} onChange={event => setTemplate(event.target.value)}>{overview.data?.templates.map(row => <option key={row.id} value={row.id}>{row.title}</option>)}</select></Field>
      <Field label="方案指令"><textarea value={instruction} onChange={event => setInstruction(event.target.value)} /></Field>
      <Button disabled={busy} onClick={() => action.run(() => client.post('/planning/generate', { node_id: node.id, expected_node_version: node.version, adapter_id: 'mock-structured-planner', template_id: template, instruction, candidate_count: 2 }), '已生成 2 个 MOCK_ONLY 待审方案')}>生成 Mock 双方案</Button>
    </section>}
    <h3>方案审核与比较</h3>
    <Button disabled={busy || selected.length < 2} onClick={() => action.run(async () => setComparison(await client.post('/planning/proposals/compare', { proposal_ids: selected })), '比较已更新')}>比较已选方案</Button>
    {comparison && <section aria-label="规划方案比较" className="experimental-record"><h3>方案差异</h3>{Object.entries(comparison.differences || {}).map(([key, value]) => <Details key={key} label={fieldLabels[key as keyof typeof fieldLabels] || key} value={value} />)}{!Object.keys(comparison.differences || {}).length && <p>结构字段一致；方案仍需人工选择。</p>}</section>}
    <div className="experimental-list">{proposals.map(row => <article key={row.id} className="experimental-record" aria-label={`方案 ${row.title}`}>
      <label className="experimental-check"><input type="checkbox" checked={selected.includes(row.id)} onChange={event => setSelected(current => event.target.checked ? [...current, row.id] : current.filter(id => id !== row.id))} />{row.title}</label>
      <RecordStatus row={row} /><p>{row.fields?.goal}</p><Details value={{ fields: row.fields, links: row.links, sources: row.sources, rationale: row.rationale, created_by: row.created_by }} />
      <div className="experimental-actions">{row.status === 'REVIEW' && <><Button disabled={busy || row.stale} onClick={() => review(row, 'approve')}>批准规划</Button><Button disabled={busy} onClick={() => review(row, 'reject')}>驳回规划</Button></>}{['REVIEW', 'REJECTED', 'APPROVED'].includes(row.status || '') && <Button disabled={busy} onClick={() => review(row, 'archive')}>归档方案</Button>}{['REJECTED', 'ARCHIVED'].includes(row.status || '') && <Button disabled={busy} onClick={() => review(row, 'reopen')}>重新审核</Button>}<Button disabled={busy} onClick={() => action.run(async () => { const value = await client.get<Rows>(`/planning/proposals/${segment(row.id)}/history`); setHistory({ proposal: row, items: value.items }); }, '历史已读取')}>方案历史</Button></div>
    </article>)}</div>
    {history && <section className="experimental-section" aria-label="规划方案历史"><h3>{history.proposal.title} · 历史</h3><p>恢复会创建新的待审版本；原始来源与目标版本仍需通过校验。</p>{history.items.length === 0 && <p>暂无历史版本。</p>}{history.items.map((row, index) => <div className="experimental-record" key={row.version || index}><Badge>历史 v{row.version} · {row.status}</Badge><Details value={row.fields} /><Button disabled={busy} onClick={() => action.run(async () => { const latest = overview.data?.proposals.find(item => item.id === history.proposal.id) || history.proposal; await client.post(`/planning/proposals/${segment(latest.id)}/restore`, { expected_version: latest.version, historical_version: row.version }); setHistory(undefined); }, '历史已恢复为待审版本')}>恢复历史 v{row.version}</Button></div>)}</section>}
  </Panel>;
}
