import { useEffect, useRef, useState } from 'react';
import { apiErrorView, type Asset } from '../api';
import { Badge, Button, StatusMessage } from '../ui/primitives';
import type { StudioAsset, StudioClient, StudioReference, StudioReferenceKind, StudioRelationshipType, StudioRelationshipGraph } from './studioClient';

const types: [StudioRelationshipType, string][] = [
  ['REFERENCES', '参考'], ['USED_IN', '用于'], ['ALTERNATE_VERSION', '备选版本'],
  ['LINKED_CONTEXT', '关联上下文'], ['APPROVED_FOR', '审核适用'],
  ['SOURCE_OF', '作为来源'], ['DERIVED_FROM', '派生自'],
];
const labels = Object.fromEntries(types);
const kinds: [StudioReferenceKind, string][] = [['ASSET', '资产'], ['CHAPTER', '章节（只读引用）'], ['SCREENPLAY', '剧本（只读引用）']];
const referenceKey = (value: StudioReference) => JSON.stringify([value.kind, value.id, value.version, value.digest]);
const states: Record<string, string> = { CURRENT: '当前', STALE: '目标已更新', DELETED: '目标已删除', UNAVAILABLE: '不可用或无权访问' };
type Props = {
  asset: Asset;
  client: Pick<StudioClient, 'references' | 'relationships' | 'addRelationship' | 'removeRelationship'>;
  canMutate: boolean;
  canReview: boolean;
  blocked: boolean;
  busy: boolean;
  isCurrent: () => boolean;
  read: <T>(operation: () => Promise<T>) => Promise<T>;
  mutate: (operation: () => Promise<StudioAsset>) => Promise<StudioAsset>;
  onDirtyChange: (dirty: boolean) => void;
};

/** Versioned, optional descriptions of existing content. Never executes a graph. */
export function AssetRelationshipsPanel({ asset, client, canMutate, canReview, blocked, busy, isCurrent, read, mutate, onDirtyChange }: Props) {
  const [open, setOpen] = useState(false), [kind, setKind] = useState<StudioReferenceKind>('ASSET');
  const [type, setType] = useState<StudioRelationshipType>('REFERENCES'), [target, setTarget] = useState<StudioReference>();
  const [reason, setReason] = useState(''), [references, setReferences] = useState<StudioReference[]>();
  const [loading, setLoading] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const [removing, setRemoving] = useState<string>(), [confirmed, setConfirmed] = useState(false);
  const [graph, setGraph] = useState<StudioRelationshipGraph>(), [graphBusy, setGraphBusy] = useState(false), [graphError, setGraphError] = useState('');
  const alive = useRef(true), pending = useRef(false), sequence = useRef(0);
  const controller = useRef<AbortController>();
  const draft = !!target || !!reason || type !== 'REFERENCES';
  const locked = busy || blocked || !!asset.deleted_at;
  const canAdd = type === 'APPROVED_FOR' ? canReview : canMutate;
  const current = () => alive.current && isCurrent();
  useEffect(() => { alive.current = true; return () => { alive.current = false; controller.current?.abort(); }; }, []);
  useEffect(() => { onDirtyChange(draft || !!removing); }, [draft, removing, onDirtyChange]);

  async function loadReferences(nextKind = kind, checkSelection = true) {
    if (!current()) return;
    controller.current?.abort();
    const request = ++sequence.current, abort = new AbortController(); controller.current = abort;
    setLoading(true); setError('');
    try {
      const result = await read(() => client.references(nextKind, abort.signal));
      if (!current() || request !== sequence.current) return;
      const items = result.items.filter(item => !item.deleted && !(item.kind === 'ASSET' && item.id === asset.id));
      setReferences(items);
      // A refresh never silently advances the version selected by the author.
      if (checkSelection && target) {
        const accessible = items.find(item => item.id === target.id && item.kind === target.kind);
        if (!accessible) {
          setTarget(undefined); setGraph(undefined);
          setNotice('所选目标已不可用或无权访问，引用详情已清除。关联理由仍保留，请选择其他目标。');
        } else if (accessible.version !== target.version || accessible.digest !== target.digest) {
          setNotice('所选目标已变化或不可用。原选择已保留；请核对后重新选择目标。');
        }
      }
    } catch (value) { if (current() && request === sequence.current && !abort.signal.aborted) setError(apiErrorView(value, '引用目录读取失败。').message); }
    finally { if (current() && request === sequence.current) setLoading(false); }
  }
  function resetDraft() { setType('REFERENCES'); setReason(''); setTarget(undefined); setRemoving(undefined); setConfirmed(false); setNotice(''); if (kind !== 'ASSET') { setKind('ASSET'); setReferences(undefined); void loadReferences('ASSET', false); } }
  async function save(operation: () => Promise<StudioAsset>) {
    if (!current() || pending.current || locked) return;
    pending.current = true; setError('');
    try { await mutate(operation); if (current()) { resetDraft(); setGraph(undefined); setNotice('关联已保存，原文件和引用内容未改变。'); } }
    catch (value) { if (current()) setError(apiErrorView(value, '关联未保存，当前输入已保留。').message); }
    finally { pending.current = false; }
  }
  const chosenCurrent = target && references?.some(item => item.id === target.id && item.kind === target.kind && item.version === target.version && item.digest === target.digest);

  return <section className="asset-relationships" aria-label="资产关联">
    <Button variant="ghost" aria-expanded={open} onClick={() => { setOpen(!open); if (!open && !references) void loadReferences(); }}>可选资产关联</Button>
    {open && <>
      <p>源资产：{asset.filename} · v{asset.version} · {asset.deleted_at ? '已删除' : '当前读取版本'}</p>
      <p>关联只记录内容关系，不复制章节或剧本，不授予版权，也不会生成内容或自动执行任务。</p>
      {!asset.relationships?.length && <p role="status">尚未添加关联。独立导入和导出无需关联。</p>}
      <ul className="asset-relationships__list">{asset.relationships?.map(link => <li key={link.id}>
        <strong>{labels[link.type] || link.type}</strong> · <Badge tone={link.state === 'CURRENT' ? 'neutral' : 'warning'}>{states[link.state]}</Badge>
        <p>{link.target.label}</p>
        {link.state !== 'UNAVAILABLE' && <><p>目标 {link.target.kind} · v{link.target.version} · {link.target.deleted ? '已删除' : '可读取'}</p><p>关联时 v{link.expected.version} · 当前 v{link.target.version}</p><p>理由：{link.reason || '未填写'}</p></>}
        <Button variant="ghost" disabled={!canMutate || locked || draft} onClick={() => { setRemoving(link.id); setConfirmed(false); }}>移除关联 {labels[link.type] || link.type}</Button>
      </li>)}</ul>
      {removing && <section role="alert" aria-label="确认移除关联"><p>只移除此关联，保留两端内容和历史记录。</p><label><input type="checkbox" checked={confirmed} disabled={locked} onChange={event => setConfirmed(event.target.checked)} />确认移除此关联</label><Button variant="danger" disabled={!confirmed || !canMutate || locked} onClick={() => { if (canMutate && confirmed && removing) void save(() => client.removeRelationship(asset.id, removing, asset.version!)); }}>确认移除</Button><Button disabled={busy} onClick={() => { setRemoving(undefined); setConfirmed(false); }}>取消移除</Button></section>}
      {blocked && <StatusMessage tone="warning">请先保存或放弃来源声明，再修改关联。</StatusMessage>}
      {!canMutate && !canReview && <p role="status">关联只读，可以查看状态和引用目录。</p>}
      <form onSubmit={event => { event.preventDefault(); if (target && chosenCurrent && canAdd && !removing) void save(() => client.addRelationship(asset.id, { expected_version: asset.version!, type, target: { kind: target.kind, id: target.id, version: target.version, digest: target.digest }, reason })); }}>
        <h3>添加关联 · 基于 v{asset.version}</h3>
        <label>关系类型<select aria-label="关系类型" disabled={locked || !!removing || !(canMutate || canReview)} value={type} onChange={event => setType(event.target.value as StudioRelationshipType)}>{types.map(([id, label]) => <option key={id} value={id} disabled={id === 'APPROVED_FOR' ? !canReview : !canMutate}>{label}</option>)}</select></label>
        {type === 'APPROVED_FOR' && <p>仅有审核权限时可保存；此声明不代表版权授权。</p>}
        {(type === 'SOURCE_OF' || type === 'DERIVED_FROM') && <p>只能描述来源声明中已经建立的父子资产关系，不能创建生成记录。</p>}
        <label>引用类型<select aria-label="引用类型" disabled={locked || !!removing} value={kind} onChange={event => { const next = event.target.value as StudioReferenceKind; setKind(next); setTarget(undefined); setReferences(undefined); setNotice(''); void loadReferences(next, false); }}>{kinds.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label>
        <Button type="button" disabled={loading || busy} onClick={() => void loadReferences()}>重新读取引用目录</Button>
        {loading && <StatusMessage>正在读取可访问的引用…</StatusMessage>}
        {!loading && references?.length === 0 && <p role="status">当前没有可选引用；可以保持独立创作。</p>}
        <label>关联目标<select aria-label="关联目标" disabled={locked || loading || !canAdd || !!removing} value={target ? referenceKey(target) : ''} onChange={event => { setTarget(references?.find(item => referenceKey(item) === event.target.value)); setNotice(''); }}><option value="">请选择（可跳过）</option>{target && !chosenCurrent && <option value={referenceKey(target)}>{target.label} · v{target.version}（已变化或不可用）</option>}{references?.map(item => <option key={`${item.kind}:${item.id}`} value={referenceKey(item)}>{item.label} · v{item.version}</option>)}</select></label>
        {target && <p>已选 {target.kind} · v{target.version} · SHA-256 {target.digest}</p>}
        <label>关联理由<textarea maxLength={1000} disabled={locked || !canAdd || !!removing} value={reason} onChange={event => setReason(event.target.value)} /></label>
        {error && <StatusMessage tone="error">{error}</StatusMessage>}{notice && <StatusMessage>{notice}</StatusMessage>}
        <Button type="submit" disabled={locked || !canAdd || !chosenCurrent || !!removing}>保存关联</Button>
        <Button type="button" disabled={busy || !draft} onClick={resetDraft}>放弃关联输入</Button>
      </form>
      <Button variant="ghost" disabled={graphBusy} onClick={() => { if (!current()) return; setGraphBusy(true); setGraphError(''); void read(() => client.relationships()).then(value => { if (current()) setGraph(value); }).catch(value => { if (current()) setGraphError(apiErrorView(value, '项目关联读取失败。').message); }).finally(() => { if (current()) setGraphBusy(false); }); }}>读取项目关联概览</Button>
      {graphBusy && <StatusMessage>正在读取关联概览…</StatusMessage>}{graphError && <StatusMessage tone="error">{graphError}</StatusMessage>}
      {graph && <section aria-label="项目关联概览"><p>{graph.nodes.length} 个资产 · {graph.edges.length} 条关联</p><p>描述性资产关系；不会执行、自动重新生成或写入知识图谱。</p><ul className="asset-relationships__list">{graph.edges.map(edge => <li key={edge.id}>{graph.nodes.find(node => node.id === edge.from)?.label || '当前可访问资产'} → {edge.target.label} · {labels[edge.type] || edge.type} · {states[edge.state]}{edge.owner === 'ASSET_LINEAGE' && ' · 原始来源关系（只读）'}</li>)}</ul></section>}
    </>}
  </section>;
}
