import { useEffect, useMemo, useRef, useState } from 'react';
import { Badge, Button, Panel, StatusMessage } from '../ui/primitives';
import { type ExperimentalClient, type Row, type Rows, segment } from './api';
import { Details, Field, Form, RecordStatus, Refresh, ResourceState, useAction, useResource } from './shared';
let sequence = 0;
export function EmbeddingPanel({ client }: { client: ExperimentalClient }) {
  const scope = useMemo(() => ++sequence, [client]);
  return <EmbeddingBody key={scope} client={client} />;
}
function EmbeddingBody({ client }: { client: ExperimentalClient }) {
  const resource = useResource(async signal => { const [status, indexes, providers, sources] = await Promise.all([client.get('/embeddings/status', signal), client.get<Rows>('/embeddings/indexes', signal), client.get<Rows>('/embeddings/providers', signal), client.get<Rows>('/embeddings/sources', signal)]); return { status, indexes: indexes.items, providers: providers.items, sources: sources.items }; }, [client]);
  const action = useAction(resource.reload), cancel = useAction(resource.reload);
  const [title, setTitle] = useState(''), [type, setType] = useState('ASSET'), [entity, setEntity] = useState(''), [screenplay, setScreenplay] = useState('');
  const [registration, setRegistration] = useState(''), [dimensions, setDimensions] = useState('768'), [editing, setEditing] = useState<Row>();
  const [indexId, setIndexId] = useState(''), [query, setQuery] = useState(''), [result, setResult] = useState<any>();
  const epoch = useRef(0), alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; }; }, []);
  const configured = resource.data?.status.status === 'CONFIGURED' && !!resource.data.status.capability;
  const selectedIndex = resource.data?.indexes.find(row => row.id === indexId);
  const available = !resource.error && !!resource.data;
  const queryReady = available && selectedIndex?.provider_status === 'CONFIGURED' && selectedIndex.status === 'ACTIVE' && !selectedIndex.stale;
  const resetResult = () => { epoch.current++; setResult(undefined); };
  const transition = (row: Row, operation: string) => {
    resetResult();
    return action.run(() => client.post(`/embeddings/indexes/${segment(row.id)}/${operation}`, { expected_version: row.version }), '索引状态已更新');
  };
  const building = resource.data?.indexes.some(row => row.status === 'BUILDING');
  useEffect(() => { if (!action.busy && !building) return; const timer = setInterval(resource.reload, 1000); return () => clearInterval(timer); }, [action.busy, building, resource.reload]);
  const busy = action.busy || cancel.busy;
  const reset = () => { setEditing(undefined); setTitle(''); setEntity(''); setScreenplay(''); };
  const choose = (row: Row) => { resetResult(); setIndexId(row.id); };
  return <Panel title="可选视觉 Embedding" actions={<Refresh reload={() => { resetResult(); resource.reload(); }} busy={resource.loading} />}>
    {action.feedback}{cancel.feedback}<ResourceState loading={resource.loading} error={resource.error} />
    {available && <><Badge tone={configured ? 'info' : 'warning'}>{resource.data!.status.status}</Badge><StatusMessage>{configured ? '请检查 provider capability、模型身份与验证级别。' : '默认 Provider 为 NOT_CONFIGURED。可选择 Model Center 中已验证、已确认 License 且已启用的本地 Embedding 注册；不会回退为词法匹配。'}</StatusMessage><Details value={resource.data!.status} label="Provider capability 与模型身份" /></>}
    <Form onSubmit={() => action.run(async () => {
      const payload = { title, entities: [{ entity_type: type, entity_id: entity, ...(type === 'SCENE' ? { screenplay_id: screenplay } : {}) }], registration_id: registration || null, dimensions: registration ? Number(dimensions) : null };
      const value = editing ? await client.put<Row>(`/embeddings/indexes/${segment(editing.id)}`, { ...payload, expected_version: editing.version }) : await client.post<Row>('/embeddings/indexes', payload);
      if (alive.current) { choose(value); reset(); }
    }, '索引定义已持久化，尚未生成向量')}>
      <Field label="向量索引标题"><input required value={title} onChange={event => setTitle(event.target.value)} /></Field>
      <Field label="索引实体类型"><select value={type} onChange={event => { setType(event.target.value); setScreenplay(''); }}>{['ASSET', 'CHARACTER', 'SCENE', 'RESEARCH'].map(value => <option key={value}>{value}</option>)}</select></Field>
      <Field label="选择当前范围中的索引来源"><select value={JSON.stringify([type, entity, screenplay])} onChange={event => { if (!event.target.value) { setEntity(''); setScreenplay(''); return; } const [kind, id, script] = JSON.parse(event.target.value); setType(kind); setEntity(id); setScreenplay(script); }}><option value="">请选择来源</option>{resource.data?.sources?.filter(row => row.entity.entity_type === type).map(row => <option key={JSON.stringify(row.entity)} value={JSON.stringify([row.entity.entity_type, row.entity.entity_id, row.entity.screenplay_id || ''])} disabled={!row.available || (!!registration && row.input_type !== 'TEXT')}>{row.title} · {row.entity.entity_id} · v{row.source_version ?? '无版本号'}{row.reason ? ` · ${row.reason}` : ''}{registration && row.input_type !== 'TEXT' ? ' · 当前本地 Adapter 不支持图片' : ''}</option>)}</select></Field>
      <details><summary>高级：手动填写精确来源标识</summary><Field label="索引实体 ID"><input required value={entity} onChange={event => setEntity(event.target.value)} /></Field>
      {type === 'SCENE' && <Field label="索引场景所属剧本 ID"><input required value={screenplay} onChange={event => setScreenplay(event.target.value)} /></Field>}</details>
      <Field label="原有 Model Center Embedding 注册"><select value={registration} onChange={event => setRegistration(event.target.value)}><option value="">使用主机已有默认 Provider</option>{resource.data?.providers?.map(row => <option key={row.id} value={row.id} disabled={!row.enabled || !row.enable_eligible || !row.license_confirmed || row.source_locality !== 'LOCAL_VERIFIED'}>{row.display_name} · {row.enabled ? '已启用' : '未启用'}</option>)}</select></Field>
      {registration && <><Field label="期望向量维度"><input required type="number" min="1" max="8192" value={dimensions} onChange={event => setDimensions(event.target.value)} /></Field><p>维度是校验约束，不是已测能力；返回维度不符时整个构建失败。当前 Ollama Adapter 只支持文字，不生成图像向量。</p></>}
      <Button type="submit" disabled={busy || !available || !title || !entity || (type === 'SCENE' && !screenplay)}>{editing ? '保存索引定义新版本' : '保存索引定义'}</Button>{editing && <Button onClick={reset}>放弃索引编辑</Button>}
    </Form>
    <p>RESEARCH 索引仅创建者可见。资料更新、撤销、删除会使派生向量失效；不会改变 Canon。重启不自动调用模型；BUILDING 遗留状态可取消后明确重建。</p>
    <div className="experimental-list">{available && resource.data!.indexes.map(row => <article className="experimental-record" key={row.id}><h3>{row.title}</h3><RecordStatus row={row} /><Details value={row} label="索引版本 / 模型 / digest / lineage" /><div className="experimental-actions">
      <Button disabled={busy || row.provider_status !== 'CONFIGURED' || ['BUILDING', 'REMOVED'].includes(row.status || '')} onClick={() => transition(row, 'rebuild')}>重建向量索引</Button>
      {row.status === 'BUILDING' && <Button disabled={cancel.busy} onClick={() => { resetResult(); void cancel.run(() => client.post(`/embeddings/indexes/${segment(row.id)}/cancel`, { expected_version: row.version }), '已取消发布；迟到结果不能写回，上游请求可能仍在结束。'); }}>取消索引构建</Button>}
      <Button disabled={busy || row.status === 'REMOVED'} onClick={() => transition(row, 'invalidate')}>标记索引失效</Button><Button disabled={busy || row.status === 'REMOVED'} onClick={() => transition(row, 'remove')}>移除索引记录</Button>
      <Button disabled={busy || ['BUILDING', 'REMOVED'].includes(row.status || '') || row.entities.length !== 1} onClick={() => { setEditing(row); setTitle(row.title); setType(row.entities[0].entity_type); setEntity(row.entities[0].entity_id); setScreenplay(row.entities[0].screenplay_id || ''); setRegistration(row.registration_id || ''); setDimensions(String(row.dimensions || 768)); }}>编辑索引定义</Button><Button onClick={() => choose(row)}>选用此索引</Button>
    </div></article>)}</div>
    <Form onSubmit={() => action.run(async () => { const ticket = epoch.current; const value = await client.post('/embeddings/query', { index_id: indexId, text: query, limit: 10 }); if (alive.current && ticket === epoch.current) setResult(value); }, '向量查询已完成')}>
      <Field label="查询向量索引"><select value={indexId} onChange={event => { resetResult(); setIndexId(event.target.value); }}><option value="">选择索引</option>{available && resource.data!.indexes.map(row => <option key={row.id} value={row.id}>{row.title}</option>)}</select></Field><Field label="视觉向量查询"><input value={query} onChange={event => { resetResult(); setQuery(event.target.value); }} /></Field><Button type="submit" disabled={busy || !queryReady || !query}>查询向量</Button>
    </Form>{available && result && <Details value={result} label="向量相似度与来源" />}
  </Panel>;
}
