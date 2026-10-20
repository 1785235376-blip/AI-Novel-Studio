import { useId, useMemo, useState } from 'react';
import { WorldVisualFields, emptyVisualData, isVisualKind, validVisualData, visualTextLength, type VisualData } from './WorldVisualFields';
import { useRequestedRecord } from './useRequestedRecord';
import type { Chapter } from '../api';
import { Button, Panel, StatusMessage } from '../ui/primitives';
import { type ExperimentalClient, type Row, type Rows, segment } from './api';
import { Details, Field, Form, ObjectInput, RecordStatus, Refresh, ResourceState, objectValue, useAction, useResource } from './shared';
const examples: Record<string, object> = {
  HISTORY: { time: 1, relations: [] }, GEOGRAPHY: { location_id: '', region_id: null, owner_id: null, explanation: '' }, CIVILIZATION: { name: '', organization_type: 'ORGANIZATION' }, ABILITY: { name: '', limits: {}, costs: {}, forbidden_actions: [] },
  CHARACTER_EVENT: { character_id: '', event: 'DEATH', explanation: '' }, PSYCHOLOGY: { character_id: '', state: '', arc_id: '', arc_stage: 1, from_state: '' }, RELATIONSHIP: { source_character_id: '', target_character_id: '', state: '', from_state: '' }, ABILITY_USE: { character_id: '', rule_id: '', metrics: {}, actions: [], cost_paid: {} },
};
type WorldPanelProps = { client: ExperimentalClient; chapter?: Chapter; requestedRecordId?: string };
let worldScopeSequence = 0;
export function WorldPanel(props: WorldPanelProps) {
  const observer = useMemo(() => ++worldScopeSequence, [props.client]);
  return <WorldBody key={observer} {...props} />;
}
function WorldBody({ client, chapter, requestedRecordId }: WorldPanelProps) {
  const resource = useResource(async signal => { const [records, canon, schema] = await Promise.all([client.get<Rows>('/world/records', signal), client.get<Rows>('/world/canon', signal), client.get('/world/schema', signal)]); return { records: records.items, canon: canon.items, schema }; }, [client]);
  const action = useAction(resource.reload), [kind, setKind] = useState('HISTORY'), [title, setTitle] = useState(''), [chapterId, setChapterId] = useState(chapter?.id || ''), [eventOrder, setEventOrder] = useState(0), [data, setData] = useState(JSON.stringify(examples.HISTORY, null, 2));
  const [visualData, setVisualData] = useState<VisualData>(emptyVisualData('CHARACTER_VISUAL'));
  const titleHint = useId();
  const visual = isVisualKind(kind);
  const validVisual = !visual || (title.length > 0 && visualTextLength(title) <= 240 && Number.isSafeInteger(eventOrder) && eventOrder >= 0 && validVisualData(kind, visualData));
  const [editing, setEditing] = useState<Row>(), [findings, setFindings] = useState<any>(), [history, setHistory] = useState<any>();
  const latestEditing = editing && resource.data?.records.find(row => row.id === editing.id);
  const visualImmutable = visual && (editing?.status === 'APPROVED' || latestEditing?.status === 'APPROVED');
  const [characterId, setCharacterId] = useState(''), [stateChapter, setStateChapter] = useState(chapter?.id || ''), [state, setState] = useState<any>();
  const save = () => { if (!validVisual || visualImmutable) return; return action.run(async () => { const body = { kind, title, chapter_id: chapterId || null, event_order: eventOrder, data: visual ? visualData : objectValue(data) }; if (editing) await client.put(`/world/records/${segment(editing.id)}`, { ...body, expected_version: editing.version }); else await client.post('/world/records', body); setEditing(undefined); setTitle(''); }, '世界记录已进入审核'); };
  const review = (row: Row, operation: string) => action.run(async () => {
    await client.post(`/world/records/${segment(row.id)}/${operation}`, { expected_version: row.version });
    // Preserve unsaved fields and the edit's original version; a successful approval
    // makes this visible draft read-only even if the following reload fails.
    if (isVisualKind(row.kind) && operation === 'approve') setEditing(current => current?.id === row.id ? { ...current, status: 'APPROVED' } : current);
  }, '世界审核已更新');
  const busy = action.busy || resource.loading;
  const visualLocked = visual && (busy || visualImmutable);
  const requested = useRequestedRecord(requestedRecordId, resource.data?.records, !resource.loading && !resource.error, client);
  return <Panel title="世界与人物语义记录 V2" actions={<Refresh reload={resource.reload} busy={busy} />}>
    <StatusMessage>候选须经审核才进入实验 Canon。连续性检查为确定性规则，不代表完整语义推理。</StatusMessage>{action.feedback}<ResourceState loading={resource.loading} error={resource.error} /><Details label="类型字段与校验 schema" value={resource.data?.schema} />
    <Form onSubmit={save}>
      <h3>{editing ? '编辑世界候选' : '创建世界候选'}</h3>
      <Field label="世界记录类型"><select disabled={!!editing || (visual && busy)} value={kind} onChange={event => {
        const next = event.target.value; setKind(next);
        if (isVisualKind(next)) setVisualData(emptyVisualData(next));
        else setData(JSON.stringify(examples[next], null, 2));
      }}>{[...Object.keys(examples), 'CHARACTER_VISUAL', 'SCENE_VISUAL'].map(key => <option key={key}>{key}</option>)}</select></Field>
      <Field label="世界记录标题"><input required aria-describedby={visual ? titleHint : undefined} aria-invalid={visual && visualTextLength(title) > 240 || undefined} disabled={visualLocked} value={title} onChange={event => setTitle(event.target.value)} /></Field>
      {visual && <p id={titleHint}>{visualTextLength(title)} / 240 字符{visualTextLength(title) > 240 ? '，超出上限，请缩短后保存。' : ''}</p>}
      <Field label="世界记录来源章节 ID"><input disabled={visualLocked} value={chapterId} onChange={event => setChapterId(event.target.value)} /></Field>
      <Field label="事件顺序"><input type="number" min={0} step={1} disabled={visualLocked} value={eventOrder} onChange={event => setEventOrder(Number(event.target.value))} /></Field>
      {visual ? <WorldVisualFields kind={kind} data={visualData} onChange={setVisualData} disabled={busy || visualImmutable} /> : <ObjectInput label="类型数据（JSON；真实人物 / 地点 / 规则 ID）" value={data} onChange={setData} />}
      {visualImmutable && <StatusMessage tone="warning">此视觉记录现已批准，当前输入已保留但不能保存或修改。可取消编辑后查看记录与历史。</StatusMessage>}
      <div className="experimental-actions"><Button type="submit" disabled={busy || visualImmutable || !title.trim() || !validVisual}>{editing ? '保存世界候选' : '创建世界候选'}</Button>{editing && <Button type="button" disabled={visual && busy} onClick={() => setEditing(undefined)}>取消编辑世界记录</Button>}</div>
    </Form>
    {requested.missing && <StatusMessage tone="warning">请求的原世界记录当前不可读或已移除，请刷新搜索。</StatusMessage>}
    <div className="experimental-list">{!resource.loading && !resource.error && resource.data?.records.map(row => <article className="experimental-record" key={row.id} aria-label={`世界记录 ${row.title}`} aria-current={row.id === requestedRecordId ? "true" : undefined} tabIndex={row.id === requestedRecordId ? -1 : undefined} ref={row.id === requestedRecordId ? requested.ref : undefined}><h3>{row.kind} · {row.title}</h3><RecordStatus row={row} /><Details value={{ data: row.data, chapter_id: row.chapter_id, event_order: row.event_order, sources: row.sources, created_by: row.created_by }} /><div className="experimental-actions">{row.status === 'REVIEW' && <><Button disabled={busy || row.stale} onClick={() => review(row, 'approve')}>批准世界候选</Button><Button disabled={busy} onClick={() => review(row, 'reject')}>驳回世界候选</Button></>}{['REJECTED', 'ARCHIVED'].includes(row.status || '') && <Button disabled={busy} onClick={() => review(row, 'reopen')}>重开世界审核</Button>}{row.status !== 'ARCHIVED' && <Button disabled={busy} onClick={() => review(row, 'archive')}>归档世界记录</Button>}<Button disabled={busy || (isVisualKind(row.kind) && row.status === 'APPROVED')} title={isVisualKind(row.kind) && row.status === 'APPROVED' ? '已批准的视觉记录不可编辑' : undefined} onClick={() => { setEditing(row); setKind(row.kind); setTitle(row.title); setChapterId(row.chapter_id || ''); setEventOrder(row.event_order); setData(JSON.stringify(row.data, null, 2)); if (isVisualKind(row.kind)) setVisualData({ ...emptyVisualData(row.kind), ...row.data }); }}>编辑世界记录</Button><Button disabled={busy} onClick={() => action.run(async () => setHistory(await client.get(`/world/records/${segment(row.id)}/history`)), '世界历史已读取')}>世界记录历史</Button></div></article>)}</div>
    {history && <Details label="世界历史版本" value={history} />}<Details label={`实验 Canon（${resource.data?.canon.length || 0}）`} value={resource.data?.canon} />
    <section className="experimental-section"><h3>连续性检查</h3><Button disabled={busy} onClick={() => action.run(async () => setFindings(await client.get('/world/continuity?include_candidates=true')), '确定性检查已完成')}>检查世界连续性</Button>{findings && <section aria-label="世界连续性结果"><p>{findings.verification} · {findings.items?.length || 0} 项发现</p><Details value={findings.items} label="死亡出现 / 归属 / 能力限制 / 时序检查结果" /></section>}</section>
    <Form onSubmit={() => action.run(async () => setState(await client.get(`/world/character-state?character_id=${segment(characterId)}&chapter_id=${segment(stateChapter)}`)), '人物时点状态已读取')}><h3>人物在章节时点的状态</h3><Field label="状态查询人物 ID"><input required value={characterId} onChange={event => setCharacterId(event.target.value)} /></Field><Field label="状态查询章节 ID"><input required value={stateChapter} onChange={event => setStateChapter(event.target.value)} /></Field><Button type="submit" disabled={busy || !characterId || !stateChapter}>查询人物章节状态</Button></Form>{state && <Details value={state} label="已批准人物章节状态" />}
  </Panel>;
}
