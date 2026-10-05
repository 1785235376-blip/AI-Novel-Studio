import { useState } from 'react';
import type { Chapter } from '../api';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import { type ExperimentalClient, type Row, type Rows, segment } from './api';
import { Field, Form, RecordStatus, Refresh, ResourceState, useAction, useResource } from './shared';
import type { WorkspaceNavigation } from './uxClient';

type Node = { kind: string; id: string; label?: string };
type Evidence = { record_id: string; record_version: number; chapter_id: string; source_versions: Record<string, { version: number; digest: string }> };
type Edge = { id: string; subject: Node; object: Node; relation: string; layer: string; statement: string; world_time: number | null; valid_from: number | null; valid_to: number | null; calendar: string; evidence: Evidence };
type Graph = { perspective: string; nodes: Node[]; edges: Edge[]; visible_count: number };
type MindItem = { text: string; epistemic_status: string; evidence_status: string; evidence: Evidence };
type Mind = { [key: string]: unknown };
type Props = { client: ExperimentalClient; chapter?: Chapter; mindEnabled?: boolean; onNavigate?: (target: WorkspaceNavigation) => void };
const kinds = { STORY_RELATION: '关系', STORY_CONCEPT: '物品 / 秘密 / 伏笔', KNOWLEDGE_EVENT: '知识与心智事件' };
const layers: Record<string, string> = { WORLD_FACT: '世界事实', CHARACTER_BELIEF: '人物信念', RESEARCH: '研究资料', SPECULATION: '推测' };
const categories: Record<string, string> = { KNOWN_FACT: '已知事实', BELIEF: '信念', FALSE_BELIEF: '错误信念', SECRET: '获知秘密', GOAL: '目标', FEAR: '恐惧', VALUE: '价值观', EMOTION: '情绪', INTENT: '意图' };
const mindSections: Record<string, string> = { known_facts: '已知事实', beliefs: '信念', false_beliefs: '错误信念', secrets: '获知秘密', goals: '目标', fears: '恐惧', values: '价值观', emotion: '情绪', intent: '意图' };
const operations: Record<string, string> = { LEARN: '获知', HEARSAY: '转述', FORGET: '遗忘', MISUNDERSTAND: '误解', CORRECT: '纠正', GOAL_CHANGE: '目标改变', SET_STATE: '状态改变' };
const numberOrNull = (value: string) => value === '' ? null : Number(value);
const nodeKey = (node: Node) => `${node.kind}:${node.id}`;

function EvidenceJump({ evidence, onNavigate }: { evidence: Evidence; onNavigate?: Props['onNavigate'] }) {
  const version = evidence.source_versions[evidence.chapter_id]?.version;
  return <div className="experimental-actions"><span>来源章节 {evidence.chapter_id} · v{version ?? '?'} · 记录 v{evidence.record_version}</span>{onNavigate && <Button onClick={() => onNavigate({ kind: 'chapter', id: evidence.chapter_id, version })}>返回来源章节</Button>}</div>;
}

function RecordForm({ client, chapter, nodes, records, psychology, editing, copy, onSaved, onCancel, mindEnabled }: Props & { nodes: Node[]; records: Row[]; psychology: Row[]; editing?: Row; copy?: boolean; onSaved: () => void; onCancel: () => void }) {
  const seed = editing?.data || {};
  const [kind, setKind] = useState(editing?.kind || 'STORY_RELATION');
  const [title, setTitle] = useState(editing?.title || ''), [chapterId, setChapterId] = useState(editing?.chapter_id || chapter?.id || ''), [order, setOrder] = useState(editing?.event_order || 0);
  const [statement, setStatement] = useState(seed.statement || seed.description || seed.value || '');
  const [subject, setSubject] = useState(seed.subject ? nodeKey(seed.subject) : ''), [object, setObject] = useState(seed.object ? nodeKey(seed.object) : '');
  const [relation, setRelation] = useState(seed.relation || 'ABOUT'), [layer, setLayer] = useState(seed.layer || 'WORLD_FACT'), [character, setCharacter] = useState(seed.character_id || seed.observer_id || '');
  const [concept, setConcept] = useState(seed.concept_type || 'SECRET'), [operation, setOperation] = useState(seed.operation || 'LEARN'), [category, setCategory] = useState(seed.category || 'SECRET');
  const [relationId, setRelationId] = useState(seed.relation_id || ''), [psychologyId, setPsychologyId] = useState(seed.psychology_id || ''), [stateKey, setStateKey] = useState(seed.state_key || 'current'), [certainty, setCertainty] = useState(seed.evidence_status || 'HYPOTHESIS');
  const [worldTime, setWorldTime] = useState(String(seed.world_time ?? '')), [from, setFrom] = useState(String(seed.valid_from ?? '')), [to, setTo] = useState(String(seed.valid_to ?? '')), [calendar, setCalendar] = useState(seed.calendar || 'story'), [until, setUntil] = useState(seed.until_chapter_id || '');
  const [quote, setQuote] = useState(seed.evidence?.[0]?.quote || ''), [quoteChapter, setQuoteChapter] = useState(seed.evidence?.[0]?.chapter_id || ''), [offset, setOffset] = useState(seed.evidence?.[0]?.start || 0);
  const action = useAction();
  const chapters = nodes.filter(node => node.kind === 'CHAPTER');
  const characters = nodes.filter(node => node.kind === 'CHARACTER');
  const chooseNode = (label: string, value: string, set: (value: string) => void) => <Field label={label}><select required value={value} onChange={event => set(event.target.value)}><option value="">选择现有实体</option>{nodes.map(node => <option key={nodeKey(node)} value={nodeKey(node)}>{node.kind} · {node.label || node.id}</option>)}</select></Field>;
  const chapterSelect = (label: string, value: string, set: (value: string) => void, required = false) => <Field label={label}><select required={required} value={value} onChange={event => set(event.target.value)}><option value="">{required ? '选择来源章节' : '未指定'}</option>{chapters.map(node => <option key={node.id} value={node.id}>{node.label || node.id}</option>)}</select></Field>;
  const save = () => action.run(async () => {
    const temporal = { world_time: numberOrNull(worldTime), valid_from: numberOrNull(from), valid_to: numberOrNull(to), calendar, until_chapter_id: until || null,
      evidence: [...(quote ? [{ chapter_id: quoteChapter || chapterId, quote, start: offset }] : []), ...(seed.evidence?.slice(1) || [])] };
    const find = (key: string) => { const node = nodes.find(item => nodeKey(item) === key); if (!node) throw new Error('请重新选择现有实体'); return { kind: node.kind, id: node.id }; };
    const data = kind === 'STORY_CONCEPT' ? { ...temporal, concept_type: concept, description: statement } : kind === 'STORY_RELATION' ? { ...temporal, subject: find(subject), object: find(object), relation, layer, statement, observer_id: character || null } : { ...temporal, character_id: character, operation, category, relation_id: relationId || null, psychology_id: psychologyId || null, value: statement, state_key: stateKey, evidence_status: certainty };
    const body = { kind, title, chapter_id: chapterId, event_order: order, data };
    if (editing && !copy) await client.put(`/story-graph/records/${segment(editing.id)}`, { ...body, expected_version: editing.version });
    else await client.post('/story-graph/records', body);
    onSaved();
  }, '记录已保存，等待审核');
  return <Form onSubmit={save}><h3>{editing ? copy ? '复制为新的待审记录' : '编辑待审记录' : '创建语义记录'}</h3>{action.feedback}
    <div className="experimental-grid"><Field label="记录类型"><select value={kind} disabled={!!editing} onChange={event => setKind(event.target.value)}>{Object.entries(kinds).filter(([key]) => mindEnabled || key !== 'KNOWLEDGE_EVENT').map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></Field><Field label="记录标题"><input required maxLength={240} value={title} onChange={event => setTitle(event.target.value)} /></Field>{chapterSelect('来源章节', chapterId, setChapterId, true)}<Field label="章内事件顺序"><input type="number" min={0} max={1000000} value={order} onChange={event => setOrder(Number(event.target.value))} /></Field></div>
    {kind === 'STORY_RELATION' && <div className="experimental-grid">{chooseNode('关系起点', subject, setSubject)}{chooseNode('关系终点', object, setObject)}<Field label="关系类型"><select value={relation} onChange={event => setRelation(event.target.value)}>{['ABOUT', 'LOCATED_AT', 'MEMBER_OF', 'OWNS', 'ALLIED_WITH', 'OPPOSES', 'CAUSES', 'PRECEDES', 'REVEALS', 'FORESHADOWS', 'CONTRADICTS'].map(value => <option key={value}>{value}</option>)}</select></Field><Field label="资料性质"><select value={layer} onChange={event => setLayer(event.target.value)}>{Object.entries(layers).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></Field></div>}
    {kind === 'STORY_CONCEPT' && <Field label="概念类型"><select value={concept} onChange={event => setConcept(event.target.value)}><option value="SECRET">秘密</option><option value="ITEM">物品</option><option value="FORESHADOWING">伏笔</option></select></Field>}
    {(kind === 'KNOWLEDGE_EVENT' || layer === 'CHARACTER_BELIEF' && kind === 'STORY_RELATION') && <Field label="观察人物"><select required value={character} onChange={event => setCharacter(event.target.value)}><option value="">选择现有人物</option>{characters.map(node => <option key={node.id} value={node.id}>{node.label || node.id}</option>)}</select></Field>}
    {kind === 'KNOWLEDGE_EVENT' && <><div className="experimental-grid"><Field label="知识变化"><select value={operation} onChange={event => { const value = event.target.value; setOperation(value); if (value === 'MISUNDERSTAND') setCategory('FALSE_BELIEF'); if (value === 'HEARSAY') setCategory('BELIEF'); if (value === 'GOAL_CHANGE') setCategory('GOAL'); }}>{Object.entries(operations).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></Field><Field label="心智类别"><select value={category} onChange={event => setCategory(event.target.value)}>{Object.entries(categories).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></Field><Field label="关联已审核关系"><select value={relationId} onChange={event => setRelationId(event.target.value)}><option value="">无（仅独立心智状态）</option>{records.filter(row => row.kind === 'STORY_RELATION' && row.status === 'APPROVED' && !row.stale).map(row => <option key={row.id} value={row.id}>{row.title}</option>)}</select></Field><Field label="复用心理记录"><select value={psychologyId} onChange={event => setPsychologyId(event.target.value)}><option value="">不关联</option>{psychology.filter(row => row.data.character_id === character && !row.stale).map(row => <option key={row.id} value={row.id}>{row.title}</option>)}</select></Field><Field label="状态标识"><input required value={stateKey} onChange={event => setStateKey(event.target.value)} /></Field><Field label="动机证据性质"><select value={certainty} onChange={event => setCertainty(event.target.value)}><option value="HYPOTHESIS">假设 / 无法推导</option><option value="EXPLICIT">作者明确指定</option></select></Field></div><StatusMessage>事实与秘密必须关联已批准的世界事实。转述和误解应填写人物自己的信念，不能把真实秘密作为误解内容传入。心智建模仅用于虚构人物。</StatusMessage></>}
    <Field label={kind === 'STORY_RELATION' ? '关系陈述' : kind === 'STORY_CONCEPT' ? '概念说明' : '人物信念或心智状态'}><textarea required={kind === 'STORY_RELATION'} maxLength={8000} value={statement} onChange={event => setStatement(event.target.value)} /></Field>
    <details><summary>时间与原文证据</summary><StatusMessage>世界时间可留空，保留为未知。叙事顺序按来源章节；倒叙不改写世界时间。终止时间和章节不含该端点。</StatusMessage><div className="experimental-grid"><Field label="世界时间"><input type="number" value={worldTime} onChange={event => setWorldTime(event.target.value)} /></Field><Field label="有效起始时间"><input type="number" value={from} onChange={event => setFrom(event.target.value)} /></Field><Field label="有效终止时间"><input type="number" value={to} onChange={event => setTo(event.target.value)} /></Field><Field label="历法"><input required value={calendar} onChange={event => setCalendar(event.target.value)} /></Field>{chapterSelect('叙事终止章节', until, setUntil)}{chapterSelect('证据章节（留空使用来源章节）', quoteChapter, setQuoteChapter)}<Field label="证据原文起始字符"><input type="number" min={0} value={offset} onChange={event => setOffset(Number(event.target.value))} /></Field></div><Field label="证据原文（须与起始字符完全匹配）"><textarea value={quote} onChange={event => setQuote(event.target.value)} /></Field></details>
    <div className="experimental-actions"><Button type="submit" disabled={action.busy || !title.trim() || !chapterId}>保存待审记录</Button>{editing && <Button type="button" disabled={action.busy} onClick={onCancel}>取消编辑</Button>}</div>
  </Form>;
}

function AuthorRecords(props: Props) {
  const { client, mindEnabled, onNavigate } = props;
  const resource = useResource(async signal => {
    const [records, catalog, psychology] = await Promise.all([client.get<Rows>('/story-graph/records', signal), client.get<{ items: Node[] }>('/story-graph/catalog', signal), mindEnabled ? client.get<Rows>('/world/records?kind=PSYCHOLOGY&status=APPROVED', signal) : Promise.resolve({ items: [] })]);
    return { records: records.items, nodes: catalog.items, psychology: psychology.items };
  }, [client, mindEnabled]);
  const action = useAction(resource.reload), [editing, setEditing] = useState<Row>(), [copy, setCopy] = useState(false), [revision, setRevision] = useState(0);
  const [history, setHistory] = useState<Row[]>(), [impact, setImpact] = useState<{ items: Row[]; affected_count: number }>();
  const busy = resource.loading || action.busy;
  const review = (row: Row, name: string) => action.run(() => client.post(`/story-graph/records/${segment(row.id)}/${name}`, { expected_version: row.version }), name === 'recompute' ? '仅受影响子图已重算' : '审核状态已更新');
  return <section className="experimental-section" aria-label="作者语义记录"><div className="experimental-actions"><h3>作者全知记录</h3><Refresh reload={resource.reload} busy={busy} /></div><StatusMessage>作者视图需要写作权限。批准世界事实才进入实验 Canon；信念、研究、推测和知识事件保留各自性质。</StatusMessage>{action.feedback}<ResourceState loading={resource.loading} error={resource.error} />
    {resource.data && !resource.error && <><RecordForm key={`${editing?.id || 'new'}:${copy}:${revision}`} {...props} nodes={resource.data.nodes} records={resource.data.records} psychology={resource.data.psychology} editing={editing} copy={copy} onCancel={() => setEditing(undefined)} onSaved={() => { setEditing(undefined); setRevision(value => value + 1); resource.reload(); }} />
    <ResourceState loading={false} empty={!resource.data.records.length} /><div className="experimental-list">{resource.data.records.map(row => <article key={row.id} className="experimental-record"><h3>{row.title} · {kinds[row.kind as keyof typeof kinds]}</h3><RecordStatus row={row} /><p>{row.data.statement || row.data.value || row.data.description || categories[row.data.category]}</p><p>{row.data.layer ? layers[row.data.layer] : operations[row.data.operation]} · 来源章节 {row.chapter_id} · 章内顺序 {row.event_order}</p>{onNavigate && <Button onClick={() => onNavigate({ kind: 'chapter', id: row.chapter_id, version: row.sources[row.chapter_id]?.version })}>打开来源章节</Button>}<div className="experimental-actions">{row.status === 'REVIEW' && <><Button disabled={busy || row.stale} onClick={() => review(row, 'approve')}>批准语义记录</Button><Button disabled={busy} onClick={() => review(row, 'reject')}>驳回语义记录</Button></>}{['REJECTED', 'ARCHIVED'].includes(row.status || '') && <Button disabled={busy} onClick={() => review(row, 'reopen')}>重开审核</Button>}{row.status !== 'ARCHIVED' && <Button disabled={busy} onClick={() => review(row, 'archive')}>归档语义记录</Button>}{row.status !== 'APPROVED' && <Button disabled={busy} onClick={() => { setEditing(row); setCopy(false); }}>编辑语义记录</Button>}<Button disabled={busy} onClick={() => { setEditing(row); setCopy(true); }}>复制为新候选</Button><Button disabled={busy} onClick={() => action.run(async () => setHistory((await client.get<Rows>(`/story-graph/records/${segment(row.id)}/history`)).items), '历史已读取')}>版本历史</Button><Button disabled={busy} onClick={() => action.run(async () => setImpact(await client.get(`/story-graph/records/${segment(row.id)}/impact`)), '影响已检查')}>检查变更影响</Button><Button disabled={busy || !mindEnabled} onClick={() => review(row, 'recompute')}>重算受影响子图</Button></div></article>)}</div></>}
    {history && <section aria-label="语义版本历史"><h3>版本历史</h3>{history.length ? history.map(row => <p key={row.version}>v{row.version} · {row.status} · {row.title} · {row.updated_at}</p>) : <p>还没有历史版本。</p>}</section>}
    {impact && <section aria-label="变更影响"><h3>受影响记录：{impact.affected_count}</h3>{impact.items.map(row => <p key={row.id}>{row.kind} · {row.id} · v{row.version} · {row.stale ? '来源失效' : '来源当前有效'}</p>)}</section>}
  </section>;
}

function QueryView({ client, chapter, mindEnabled, onNavigate, characterMode }: Props & { characterMode: boolean }) {
  const [chapterId, setChapterId] = useState(chapter?.id || ''), [characterId, setCharacterId] = useState(''), [time, setTime] = useState(''), [calendar, setCalendar] = useState('story');
  const [result, setResult] = useState<{ key: string; graph: Graph; mind?: Mind }>();
  const action = useAction();
  const key = JSON.stringify([chapterId, characterId, time, calendar]);
  const visible = result?.key === key ? result : undefined;
  const query = () => action.run(async () => {
    const body = { chapter_id: chapterId, character_id: characterId, world_time: numberOrNull(time), calendar };
    const params = new URLSearchParams({ chapter_id: chapterId, calendar, ...(characterMode ? { character_id: characterId } : {}), ...(time === '' ? {} : { world_time: time }) });
    const graph = await client.get<Graph>('/story-graph/query?' + params);
    const mind = characterMode ? await client.post<Mind>('/story-graph/character-context', body) : undefined;
    setResult({ key, graph, mind });
  }, '时点查询已完成');
  return <section className="experimental-section"><Form onSubmit={query}><h3>{characterMode ? '人物可知视图' : '作者时点关系'}</h3><div className="experimental-grid"><Field label="查询章节 ID"><input required value={chapterId} onChange={event => setChapterId(event.target.value)} /></Field>{characterMode && <Field label="视角人物 ID"><input required value={characterId} onChange={event => setCharacterId(event.target.value)} /></Field>}<Field label="查询世界时间（留空只按叙事顺序）"><input type="number" value={time} onChange={event => setTime(event.target.value)} /></Field><Field label="查询历法"><input required value={calendar} onChange={event => setCalendar(event.target.value)} /></Field></div><Button type="submit" disabled={action.busy || !chapterId || characterMode && (!characterId || !mindEnabled)}>查询当前视图</Button></Form>{action.feedback}
    {characterMode && <StatusMessage>只展示这个人物在此章节已获知的内容。未知秘密不会进入关系、节点、数量或上下文。源章节全文与未授权人物档案不会附带传入。</StatusMessage>}
    {visible && <><section aria-label="时间化关系图"><h3>可见关系：{visible.graph.visible_count}</h3>{!visible.graph.edges.length && <EmptyState title="此时点没有可见关系" detail="请检查审核状态、来源版本、时间范围和人物知情事件。" />}<div className="experimental-list">{visible.graph.edges.map(edge => <article className="experimental-record" key={edge.id}><div className="experimental-actions"><Badge>{layers[edge.layer]}</Badge><span>{edge.subject.kind} {edge.subject.id} → {edge.relation} → {edge.object.kind} {edge.object.id}</span></div><p>{edge.statement}</p><p>世界时间：{edge.world_time ?? '未知'} · 历法 {edge.calendar} · 有效区间 {edge.valid_from ?? '未知'} 至 {edge.valid_to ?? '未知'}</p><EvidenceJump evidence={edge.evidence} onNavigate={onNavigate} /></article>)}</div></section>
    {visible.mind && <section aria-label="人物上下文预览"><h3>实际可用的人物知识上下文</h3><StatusMessage>确定性审核事件投影。信念和假设不作为事实；此预览不调用模型。</StatusMessage>{Object.entries(mindSections).map(([name, label]) => <section key={name}><h3>{label}</h3>{(visible.mind![name] as MindItem[] || []).length ? (visible.mind![name] as MindItem[]).map((item, index) => <article className="experimental-record" key={`${name}:${index}`}><p>{item.text}</p><p>{item.evidence_status === 'HYPOTHESIS' ? '假设' : '明确指定'} · {item.epistemic_status}</p><EvidenceJump evidence={item.evidence} onNavigate={onNavigate} /></article>) : <p>未指定</p>}</section>)}</section>}</>}
  </section>;
}

export function StoryGraphPanel(props: Props) {
  const [mode, setMode] = useState<'author' | 'character'>('author');
  return <Panel title="时间化故事图谱与人物知识"><div className="experimental-actions"><Button aria-pressed={mode === 'author'} onClick={() => setMode('author')}>作者全知视图</Button><Button disabled={!props.mindEnabled} aria-pressed={mode === 'character'} onClick={() => setMode('character')}>人物可知视图</Button></div>{mode === 'author' ? <><AuthorRecords {...props} /><QueryView key="author" {...props} characterMode={false} /></> : <QueryView key="character" {...props} characterMode />}</Panel>;
}
