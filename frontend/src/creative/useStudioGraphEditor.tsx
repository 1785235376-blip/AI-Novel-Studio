import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, apiErrorView } from '../api';
import { AssetInspector } from '../novel/AssetInspector';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import type { StudioAsset, StudioClient } from './studioClient';
import type { StudioGraphCatalog, StudioGraphDefinition, StudioGraphDefinitionId, StudioGraphRecord } from './studioGraphTypes';
import { GraphCanvas } from './GraphCanvas';
import { GraphRunPanel } from './GraphRunPanel';
import { blankGraph, connectionIssue, graphId, retainsSavedAssetBindings } from './graphDraft';
import { GRAPH_NODE_LABELS } from './studioGraphLabels';
import './studioGraph.css';

type Props = { active: boolean; denied: boolean; identity: string; client: StudioClient; canMutate: boolean; canReview: boolean; busy: boolean; externalDirty: boolean;
  isCurrent: () => boolean; read: <T>(work: () => Promise<T>) => Promise<T>; mutate: <T>(work: () => Promise<T>) => Promise<T> };
const same = (left: unknown, right: unknown) => JSON.stringify(left) === JSON.stringify(right);
const portKey = (node: string, port: string) => JSON.stringify([node, port]);

/** An editor of scoped graph definitions, never a second project, asset or job owner. */
export function useStudioGraphEditor({ active, denied, identity, client, canMutate, canReview, busy, externalDirty, isCurrent, read, mutate }: Props) {
  const [catalog, setCatalog] = useState<StudioGraphCatalog>(), [records, setRecords] = useState<StudioGraphRecord[]>([]), [base, setBase] = useState<StudioGraphRecord>();
  const [draft, setDraft] = useState<StudioGraphDefinition>(blankGraph), [selected, setSelected] = useState<string[]>([]);
  const [past, setPast] = useState<StudioGraphDefinition[]>([]), [future, setFuture] = useState<StudioGraphDefinition[]>([]);
  const [loading, setLoading] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState(''), [blocked, setBlocked] = useState(false);
  const [candidate, setCandidate] = useState<StudioGraphRecord>(), [replaceConfirmed, setReplaceConfirmed] = useState(false);
  const [pendingNavigation, setPendingNavigation] = useState<() => void>(), [discardConfirmed, setDiscardConfirmed] = useState(false);
  const [kind, setKind] = useState<StudioGraphDefinitionId>('text_input'), [sourcePort, setSourcePort] = useState(''), [targetPort, setTargetPort] = useState('');
  const [assets, setAssets] = useState<StudioAsset[]>([]), [assetChoice, setAssetChoice] = useState(''), [assetLoading, setAssetLoading] = useState(false), [preview, setPreview] = useState<StudioAsset>();
  const alive = useRef(true), selectedEpoch = useRef(0), catalogEpoch = useRef(0), assetEpoch = useRef(0), saving = useRef(false);
  const draftRef = useRef(draft); draftRef.current = draft;
  const baseRef = useRef(base); baseRef.current = base;
  const createRequest = useRef(graphId('graph'));
  const current = useCallback(() => alive.current && isCurrent(), [isCurrent]);
  const dirty = !same(draft, base?.definition || blankGraph());
  const editable = !!catalog && canMutate && !denied && !busy && !externalDirty && !blocked && base?.can_edit !== false;
  const protectedNodes = base?.definition.nodes.filter(node => node.definition_id === 'asset_reference').map(node => node.id) || [];

  const accept = useCallback((record: StudioGraphRecord) => {
    selectedEpoch.current++; setBase(record); setDraft(structuredClone(record.definition)); setPast([]); setFuture([]); setSelected([]); setCandidate(undefined); setBlocked(false); setSourcePort(''); setTargetPort('');
    setRecords(rows => [...rows.filter(row => row.id !== record.id), record]); createRequest.current = graphId('graph');
  }, []);
  const discard = useCallback(() => { selectedEpoch.current++; setDraft(structuredClone(baseRef.current?.definition || blankGraph())); setPast([]); setFuture([]); setBlocked(false); setCandidate(undefined); setPendingNavigation(undefined); setSourcePort(''); setTargetPort(''); createRequest.current = graphId('graph'); }, []);
  useEffect(() => { alive.current = true; return () => { alive.current = false; selectedEpoch.current++; catalogEpoch.current++; assetEpoch.current++; }; }, []);
  useEffect(() => {
    if (denied) { selectedEpoch.current++; catalogEpoch.current++; assetEpoch.current++; setCatalog(undefined); setRecords([]); setBase(undefined); setDraft(blankGraph()); setPast([]); setFuture([]); setSelected([]); setAssets([]); setPreview(undefined); setCandidate(undefined); setPendingNavigation(undefined); setError(''); setNotice(''); }
  }, [denied]);

  const load = useCallback(async () => {
    if (!current()) return;
    const epoch = ++catalogEpoch.current; setLoading(true); setError('');
    try {
      const [schema, values] = await read(() => Promise.all([client.graphs.catalog(), client.graphs.list()]));
      if (current() && epoch === catalogEpoch.current) { setCatalog(schema); setRecords(values.items); }
    } catch (value) { if (current() && epoch === catalogEpoch.current) setError(apiErrorView(value, '创作图目录读取失败。').message); }
    finally { if (current() && epoch === catalogEpoch.current) setLoading(false); }
  }, [client, current, read]);
  useEffect(() => { if (active && !denied && !catalog) void load(); }, [active, denied, catalog, load]);

  const change = useCallback((next: StudioGraphDefinition, record = true) => {
    if (!editable || !current() || saving.current) return;
    if (!retainsSavedAssetBindings(baseRef.current?.definition.nodes || [], next.nodes)) { setError('已保存资产引用暂不能移除或重新绑定；可移动或禁用节点。原资产不会被删除。'); return; }
    if (same(draftRef.current, next)) return;
    if (record) { setPast(rows => [...rows.slice(-49), structuredClone(draftRef.current)]); setFuture([]); }
    draftRef.current = next; setDraft(next); setError(''); setNotice(''); setCandidate(undefined);
  }, [editable, current]);
  function navigate(work: () => void) {
    if (busy || saving.current || externalDirty) return;
    if (dirty || blocked) { setDiscardConfirmed(false); setPendingNavigation(() => work); return; }
    work();
  }
  async function open(id: string) {
    const epoch = ++selectedEpoch.current; setError('');
    try { const value = await mutate(() => client.graphs.get(id)); if (current() && epoch === selectedEpoch.current) accept(value); }
    catch (value) { if (current() && epoch === selectedEpoch.current) setError(apiErrorView(value, '创作图读取失败，当前草稿未替换。').message); }
  }
  function newGraph() { selectedEpoch.current++; setBase(undefined); setDraft(blankGraph()); setSelected([]); setPast([]); setFuture([]); setBlocked(false); setCandidate(undefined); setSourcePort(''); setTargetPort(''); createRequest.current = graphId('graph'); }
  async function save(retry = false) {
    if ((!editable && !(retry && blocked && !base && canMutate && !busy && !externalDirty)) || saving.current || !current() || !draft.title.trim()) return;
    saving.current = true; setError(''); const epoch = selectedEpoch.current, value = structuredClone(draftRef.current), original = base;
    try {
      const saved = await mutate(() => original ? client.graphs.save(original.id, { expected_version: original.version, definition: value }) : client.graphs.create({ request_id: createRequest.current, expected_version: 0, definition: value }));
      if (current() && epoch === selectedEpoch.current) { accept(saved); setNotice(`创作图已保存 · v${saved.version}。没有自动创建运行。`); }
    } catch (value) {
      if (current() && epoch === selectedEpoch.current) { setError(apiErrorView(value, '创作图未保存，输入已保留。').message); if (!(value instanceof ApiError) || value.status === 0 || value.status === 409 || value.status >= 500) setBlocked(true); }
    } finally { saving.current = false; }
  }
  async function checkServer() {
    if (busy || !current()) return;
    const source = base, epoch = selectedEpoch.current; setError(''); setReplaceConfirmed(false);
    try {
      if (!source) { await load(); if (current()) setNotice('已读取保存目录。创建回执不确定时，可明确使用同一请求重试，不按标题猜测或自动重复创建。'); }
      else { const value = await read(() => client.graphs.get(source.id)); if (current() && epoch === selectedEpoch.current) setCandidate(value); }
    } catch (value) { if (current() && epoch === selectedEpoch.current) setError(apiErrorView(value, '服务端版本核对失败。').message); }
  }
  async function loadAssets() {
    if (assetLoading || !current()) return;
    const epoch = ++assetEpoch.current; setAssetLoading(true); setError('');
    try { const result = await read(() => client.assets()); if (current() && epoch === assetEpoch.current) { setAssets(result.items.filter(row => ['image', 'video', 'audio'].includes(row.kind) && !row.deleted_at)); setAssetChoice(''); } }
    catch (value) { if (current() && epoch === assetEpoch.current) setError(apiErrorView(value, '原资产目录读取失败。').message); }
    finally { if (current() && epoch === assetEpoch.current) setAssetLoading(false); }
  }
  function addNode() {
    const spec = catalog?.definitions.find(row => row.id === kind), asset = assets.find(row => row.id === assetChoice);
    if (!editable || !spec || draft.nodes.length >= catalog!.limits.nodes || kind === 'asset_reference' && !asset) return;
    const node = { id: graphId(), definition_id: kind, definition_version: 1 as const, enabled: true, position: { x: 24 + draft.nodes.length % 4 * 280, y: 24 + Math.floor(draft.nodes.length / 4) * 180 },
      parameters: kind === 'asset_reference' ? { asset_id: asset!.id, version: asset!.version, digest: asset!.sha256, kind: asset!.kind as 'image' | 'video' | 'audio' } : structuredClone(spec.default_parameters || {}) };
    change({ ...draft, nodes: [...draft.nodes, node] }); setSelected([node.id]);
  }
  function connect() {
    if (!editable || !sourcePort || !targetPort || draft.edges.length >= catalog!.limits.edges) return;
    const [source_node_id, source_port] = JSON.parse(sourcePort), [target_node_id, target_port] = JSON.parse(targetPort);
    const edge = { id: graphId('edge'), source_node_id, source_port, target_node_id, target_port }, problem = connectionIssue(draft, catalog!.definitions, edge);
    if (problem) { setError(problem); return; }
    change({ ...draft, edges: [...draft.edges, edge] }); setSourcePort(''); setTargetPort('');
  }
  function travel(redo: boolean) {
    if (!editable) return;
    const from = redo ? future : past, value = redo ? from[0] : from.at(-1); if (!value) return;
    if (!retainsSavedAssetBindings(base?.definition.nodes || [], value.nodes)) { setError('撤销不能移除已经保存的资产绑定。'); return; }
    if (redo) { setPast(rows => [...rows.slice(-49), structuredClone(draft)]); setFuture(rows => rows.slice(1)); }
    else { setFuture(rows => [structuredClone(draft), ...rows].slice(0, 50)); setPast(rows => rows.slice(0, -1)); }
    draftRef.current = structuredClone(value); setDraft(draftRef.current); setSourcePort(''); setTargetPort('');
  }
  const node = draft.nodes.find(row => row.id === selected[0]);
  useEffect(() => {
    let valid = true; setPreview(undefined);
    if (!active || !node || node.definition_id !== 'asset_reference' || !node.parameters.asset_id || denied) return;
    void read(() => client.asset(node.parameters.asset_id!)).then(value => { if (valid && current()) setPreview(value); }).catch(value => { if (valid && current()) setNotice(apiErrorView(value, '引用资产当前不可预览。').message); });
    return () => { valid = false; };
  }, [active, denied, node?.id, node?.parameters.asset_id, client, read, current]);

  const content = <section className="studio-graph-editor" aria-label="独立创作图编辑器">
    <Panel title="创作图 · 手工编排"><p>空图和不相连的组件都可以保存。导演备注可选，可随时移除；连接类型由服务端定义。</p><p>本阶段只支持本地文本和手工结果的原工作流运行。资产节点仅引用原文件，模型、媒体处理和存储迁移未接入。</p>
      <div className="studio-graph-actions"><Button disabled={busy || externalDirty} onClick={() => navigate(newGraph)}>新建空图</Button><Button disabled={loading || busy} onClick={() => void load()}>刷新创作图目录</Button></div>
      <label>已保存创作图<select aria-label="已保存创作图" disabled={busy || externalDirty} value={base?.id || ''} onChange={event => { const id = event.target.value; if (id) navigate(() => void open(id)); }}><option value="">未选择已保存图</option>{records.map(row => <option key={row.id} value={row.id}>{row.definition.title} · v{row.version}</option>)}</select></label>
      <label>创作图标题<input maxLength={160} value={draft.title} disabled={!editable} onChange={event => change({ ...draft, title: event.target.value })} /></label>
      <Badge tone={dirty || blocked ? 'warning' : 'neutral'}>{base ? `v${base.version}` : '尚未保存'} · {dirty ? '未保存修改' : '无未保存修改'}</Badge>
      <div className="studio-graph-actions"><Button variant="primary" disabled={!editable || !draft.title.trim() || !!base && !dirty} onClick={() => void save()}>保存创作图</Button><Button disabled={!editable || !past.length} onClick={() => travel(false)}>撤销图编辑</Button><Button disabled={!editable || !future.length} onClick={() => travel(true)}>重做图编辑</Button><Button disabled={busy || !base} onClick={() => navigate(() => void open(base!.id))}>重新读取创作图</Button></div>
    </Panel>
    {loading && <StatusMessage>正在读取当前范围的节点目录…</StatusMessage>}{error && <StatusMessage tone="error">{error}</StatusMessage>}{notice && <StatusMessage>{notice}</StatusMessage>}
    {externalDirty && <StatusMessage tone="warning">请先保存或放弃资产/偏好输入，再修改创作图。</StatusMessage>}
    {base?.can_edit === false && <StatusMessage tone="warning">图中包含不可见的资产引用，当前仅可查看。原绑定不会被省略、删除或重新保存；需恢复访问后重新读取。</StatusMessage>}
    {blocked && <section className="studio-graph-conflict" role="alert"><p>保存版本或回执不确定。草稿已保留，不会自动覆盖或重试。</p><Button disabled={busy} onClick={() => void checkServer()}>核对图服务端版本</Button>{!base && <Button disabled={busy || !canMutate} onClick={() => void save(true)}>使用同一请求重试保存</Button>}</section>}
    {candidate && <section className="studio-graph-conflict" aria-label="图服务端版本"><p>服务端 v{candidate.version} · {candidate.definition.title} · {candidate.definition.nodes.length} 节点 / {candidate.definition.edges.length} 连接</p><label><input type="checkbox" checked={replaceConfirmed} onChange={event => setReplaceConfirmed(event.target.checked)} />确认放弃当前图草稿，采用已核对服务端版本</label><Button disabled={!replaceConfirmed || busy} onClick={() => accept(candidate)}>采用图服务端版本</Button><Button onClick={() => setCandidate(undefined)}>保留图草稿</Button></section>}
    {pendingNavigation && <section role="alert" className="studio-graph-conflict"><p>当前图有未保存输入，切换会放弃本页草稿。</p><label><input type="checkbox" checked={discardConfirmed} onChange={event => setDiscardConfirmed(event.target.checked)} />确认放弃图草稿</label><Button disabled={!discardConfirmed || busy} onClick={() => { const work = pendingNavigation; setPendingNavigation(undefined); work(); }}>确认切换创作图</Button><Button onClick={() => setPendingNavigation(undefined)}>继续编辑创作图</Button></section>}
    {catalog && <><section className="studio-graph-controls" aria-label="添加与连接节点"><label>节点类型<select aria-label="节点类型" value={kind} disabled={!editable} onChange={event => { const value = event.target.value as StudioGraphDefinitionId; setKind(value); if (value === 'asset_reference') void loadAssets(); }}>{catalog.definitions.map(row => <option value={row.id} key={row.id}>{GRAPH_NODE_LABELS[row.id]}</option>)}</select></label>
      {kind === 'asset_reference' && <><label>原资产<select aria-label="原资产" disabled={!editable || assetLoading} value={assetChoice} onChange={event => setAssetChoice(event.target.value)}><option value="">选择已保存原资产</option>{assets.map(row => <option value={row.id} key={row.id}>{row.filename} · {row.kind} · v{row.version}</option>)}</select></label><Button disabled={assetLoading || busy} onClick={() => void loadAssets()}>刷新图引用资产</Button><p>只保存原资产 ID、版本和摘要；不复制文件。保存后的引用暂不能移除或重绑，可禁用节点。</p></>}
      <Button disabled={!editable || draft.nodes.length >= catalog.limits.nodes || kind === 'asset_reference' && !assetChoice} onClick={addNode}>添加节点</Button>
      <label>起始输出端口<select aria-label="起始输出端口" disabled={!editable} value={sourcePort} onChange={event => setSourcePort(event.target.value)}><option value="">选择输出端口</option>{draft.nodes.flatMap(row => (catalog.definitions.find(item => item.id === row.definition_id)?.outputs || []).map(port => <option key={portKey(row.id, port.id)} value={portKey(row.id, port.id)}>{GRAPH_NODE_LABELS[row.definition_id]} · {row.id} · {port.id} ({port.type})</option>))}</select></label>
      <label>目标输入端口<select aria-label="目标输入端口" disabled={!editable} value={targetPort} onChange={event => setTargetPort(event.target.value)}><option value="">选择输入端口</option>{draft.nodes.flatMap(row => (catalog.definitions.find(item => item.id === row.definition_id)?.inputs || []).map(port => <option key={portKey(row.id, port.id)} value={portKey(row.id, port.id)}>{GRAPH_NODE_LABELS[row.definition_id]} · {row.id} · {port.id} ({port.type})</option>))}</select></label>
      <Button disabled={!editable || !sourcePort || !targetPort || draft.edges.length >= catalog.limits.edges} onClick={connect}>连接所选端口</Button></section>
      <GraphCanvas definition={draft} nodeDefinitions={catalog.definitions} selectedNodeIds={selected} onSelectionChange={setSelected} onDefinitionChange={change} readonly={!editable} busy={busy} protectedNodeIds={protectedNodes} interactionKey={`${identity}:${base?.id || 'new'}`} onPortSelect={port => { if (port.direction === 'output') setSourcePort(portKey(port.nodeId, port.portId)); else setTargetPort(portKey(port.nodeId, port.portId)); }} />
      <section aria-label="图连接列表"><h3>已保存到草稿的连接</h3>{!draft.edges.length && <p>暂无连接；不相连节点可以独立保存。</p>}<ul>{draft.edges.map(edge => <li key={edge.id}>{edge.source_node_id}.{edge.source_port} → {edge.target_node_id}.{edge.target_port}<Button disabled={!editable} onClick={() => change({ ...draft, edges: draft.edges.filter(row => row.id !== edge.id) })}>移除连接 {edge.id}</Button></li>)}</ul></section>
      <GraphRunPanel client={client.graphs} graph={base} targetNodeIds={selected} dirty={dirty || blocked} busy={busy} canMutate={canMutate && !externalDirty} canReview={canReview && !externalDirty} isCurrent={current} read={read} mutate={mutate} />
    </>}
  </section>;
  const referenceState = base?.reference_states.find(row => row.node_id === node?.id)?.state;
  const inspector = <section className="studio-graph-inspector" aria-label="创作图节点检查器">{node ? <><h2>{GRAPH_NODE_LABELS[node.definition_id]}</h2><p>{node.id} · 定义 v{node.definition_version}</p><label><input type="checkbox" checked={node.enabled} disabled={!editable} onChange={event => change({ ...draft, nodes: draft.nodes.map(row => row.id === node.id ? { ...row, enabled: event.target.checked } : row) })} />启用当前节点</label>
    {(['text_input', 'manual_transform', 'director_note'] as const).includes(node.definition_id as 'text_input') && <label>{node.definition_id === 'text_input' ? '作者输入文本' : node.definition_id === 'manual_transform' ? '手工处理结果' : '可选导演备注'}<textarea maxLength={node.definition_id === 'director_note' ? 4000 : 8000} disabled={!editable} value={String(node.parameters[node.definition_id === 'text_input' ? 'text' : node.definition_id === 'manual_transform' ? 'result' : 'note'] || '')} onChange={event => { const key = node.definition_id === 'text_input' ? 'text' : node.definition_id === 'manual_transform' ? 'result' : 'note'; change({ ...draft, nodes: draft.nodes.map(row => row.id === node.id ? { ...row, parameters: { [key]: event.target.value } } : row) }); }} /></label>}
    <div className="studio-graph-position">{(['x', 'y'] as const).map(axis => <label key={axis}>节点 {axis.toUpperCase()}<input type="number" min={-100000} max={100000} value={node.position[axis]} disabled={!editable} onChange={event => { const value = Number(event.target.value); if (Number.isFinite(value) && value >= -100000 && value <= 100000) change({ ...draft, nodes: draft.nodes.map(row => row.id === node.id ? { ...row, position: { ...row.position, [axis]: value } } : row) }); }} /></label>)}</div>
    {node.definition_id === 'asset_reference' && <><p>引用状态：{referenceState || '待保存核对'} · 执行适配尚未接入</p>{node.parameters.asset_id ? <p>原资产 {node.parameters.asset_id} · v{node.parameters.version}</p> : <p>引用不可用或无权访问，原详情已隐藏。</p>}{preview && <AssetInspector asset={preview} downloadAsset={asset => read(() => client.download(asset.id))} isCurrent={current} showReferences={false} />}</>}
    <Button variant="danger" disabled={!editable || protectedNodes.includes(node.id)} onClick={() => { change({ ...draft, nodes: draft.nodes.filter(row => row.id !== node.id), edges: draft.edges.filter(edge => edge.source_node_id !== node.id && edge.target_node_id !== node.id) }); setSelected([]); }}>移除当前节点</Button><p>移除节点只修改本图，不删除任何原资产、章节或运行记录。</p>
    </> : <EmptyState title="未选择图节点" detail="在画布或键盘节点列表中选择一个节点，编辑其参数和位置。" />}</section>;
  return { content, inspector, dirty: dirty || blocked, discard };
}
