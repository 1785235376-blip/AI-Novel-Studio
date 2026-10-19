import { useEffect, useRef, useState } from 'react';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import { readResponse, samePin, UsageEvidence, type UsageResponse } from '../experimental/studioUsageEvidence';
import { Button, StatusMessage } from '../ui/primitives';
import { createStoryFactClient, type FactTarget, type FactUse } from './storyFactClient';
import { factAssetPin, factPathKey, revalidateFactPath, sameTarget, type FactAsset } from './storyFactDownstream';

type Props = { projectId: string; identity: string; target: FactTarget; uses: FactUse[]; transport: StudioGraphTransport;
  enabled: boolean; busy: boolean; isCurrent: () => boolean; read: <T>(work: () => Promise<T>) => Promise<T> };
const owners = [
  { owner: 'CREATIVE_GRAPH', label: 'Studio 图定义', path: 'studio-graph-usages' },
  { owner: 'STUDIO_TIMELINE', label: 'Studio 时间线', path: 'studio-timeline-usages' },
] as const;
type Observation = { row: FactUse; asset: FactAsset; responses: UsageResponse[] };
export function StoryFactDownstreamImpact(props: Props) {
  const key = JSON.stringify([props.identity, props.projectId, props.target, props.uses, props.enabled, props.isCurrent()]);
  const lifetime = useRef({ key, transport: props.transport, generation: 0 });
  if (lifetime.current.key !== key || lifetime.current.transport !== props.transport) {
    lifetime.current = { key, transport: props.transport, generation: lifetime.current.generation + 1 };
  }
  const generation = lifetime.current.generation;
  return <Inspection key={generation} {...props} isCurrent={() => lifetime.current.generation === generation && props.isCurrent()} />;
}
function Inspection(props: Props) {
  const [selection, setSelection] = useState(''), [loading, setLoading] = useState(false);
  const [observation, setObservation] = useState<Observation | null>(null), [unavailable, setUnavailable] = useState(false);
  const active = useRef<AbortController>(), mounted = useRef(false), latest = useRef(props); latest.current = props;
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; active.current?.abort(); }; }, []);
  const options = props.uses.filter(row => sameTarget(row.target, props.target)).flatMap(row => row.assets.map(asset => ({ row, asset, key: factPathKey(row, asset) })));
  const selected = options.find(option => option.key === selection);
  const clear = () => { active.current?.abort(); active.current = undefined; setObservation(null); setUnavailable(false); setLoading(false); };
  const inspect = async () => {
    if (!selected || active.current || !props.enabled || props.busy || !props.isCurrent()) return;
    const controller = new AbortController(); active.current = controller;
    setObservation(null); setUnavailable(false); setLoading(true);
    const current = () => mounted.current && active.current === controller && !controller.signal.aborted && latest.current.enabled && latest.current.isCurrent();
    const requireCurrent = () => { if (!current()) throw new Error('上下文已变化'); };
    const { row, asset } = selected;
    const client = createStoryFactClient(props.projectId, props.transport);
    try {
      const before = await props.read(() => client.impact(props.target.document_id));
      requireCurrent(); revalidateFactPath(before, row, asset, props.target);
      const responses = await Promise.all(owners.map(async ({ owner, path }) => {
        requireCurrent();
        const value = await props.read(() => props.transport.json<unknown>(
          `/api/novels/${encodeURIComponent(props.projectId)}/experimental/production/assets/${encodeURIComponent(asset.asset_id)}/${path}`,
          'GET', undefined, controller.signal));
        requireCurrent();
        const result = readResponse(value, owner, asset.asset_id);
        if (!samePin(result.source, factAssetPin(asset))) throw new Error('素材固定版本已变化');
        return result;
      }));
      requireCurrent();
      const after = await props.read(() => client.impact(props.target.document_id));
      requireCurrent();
      const verified = revalidateFactPath(after, row, asset, props.target);
      setObservation({ row: verified, asset, responses });
    } catch {
      // A denied or malformed sibling invalidates the entire assembled path.
      if (mounted.current && active.current === controller) { setObservation(null); setUnavailable(true); }
      controller.abort();
    } finally {
      if (mounted.current && active.current === controller) { active.current = undefined; setLoading(false); }
    }
  };
  const visible = props.enabled && props.isCurrent() ? observation : null;
  return <section aria-label="事实下游使用检查（只读）">
    <h3>事实 → 镜头 → 正式素材 → 已保存使用方</h3>
    <p>明确选择一个当前镜头素材后检查。每类原使用方最多 25 个文档、200 条引用；超过文档上限时覆盖不可用。只读，不自动重生成。</p>
    <p>这是跨原所有者的有界读取观察，不是原子快照或语义因果证明。Export、成本和未记录依赖仍为 UNKNOWN。</p>
    <label>检查的事实镜头素材<select value={selection} disabled={!props.enabled || props.busy} onChange={e => { clear(); setSelection(e.target.value); }}>
      <option value="">选择一个已核实素材</option>
      {options.map(option => <option key={option.key} value={option.key}>{option.row.fact.id} → {option.row.target.shot_id} → {option.asset.asset_id} v{option.asset.version} ({option.asset.kind})</option>)}
    </select></label>
    <Button disabled={!selected || !props.enabled || !props.isCurrent() || props.busy || loading} onClick={() => void inspect()}>{loading ? '正在检查下游使用…' : '检查下游使用（只读）'}</Button>
    {unavailable && <StatusMessage tone="error">下游覆盖不可用：权限、上下文、固定版本或回执证据已变化。整条观察已清除；请重新读取事实依赖并明确检查，不能据此认定没有影响。</StatusMessage>}
    {!visible && !unavailable && !loading && <p>尚未检查，Graph / Timeline 下游覆盖未知。</p>}
    {visible && <>
      <p>事实 {visible.row.fact.id} v{visible.row.fact.version} · {visible.row.fact.digest} → 文档 {visible.row.target.document_id} v{visible.row.target.document_version} · {visible.row.target.document_digest} → 场景 {visible.row.target.scene_id} → 镜头 {visible.row.target.shot_id} v{visible.row.target.shot_version} · {visible.row.target.shot_digest} → {visible.asset.kind} 素材 {visible.asset.asset_id} v{visible.asset.version} · {visible.asset.digest}</p>
      <p>理由：显式确认记录 {visible.row.id} v{visible.row.version} · {visible.row.purpose}：{visible.row.rationale}；原镜头绑定经回读核实。事实使用状态 {visible.row.state}；当前事实 {visible.row.current_fact.id} v{visible.row.current_fact.version} · {visible.row.current_fact.digest} · {visible.row.current_fact.status}</p>
      {visible.row.blockers.length > 0 && <StatusMessage tone="warning">事实使用阻塞：{visible.row.blockers.join('、')}。下游引用不代表事实已重新批准。</StatusMessage>}
      {visible.responses.map(response => <section key={response.owner} aria-label={`${response.owner} 下游证据`}>
        <h4>{owners.find(owner => owner.owner === response.owner)!.label}</h4>
        <p>本次返回 {response.items.length} 条引用，非全部依赖总数。</p>
        {response.truncated && <StatusMessage tone="warning">结果已截断，覆盖不完整。</StatusMessage>}
        {response.items.length === 0 && !response.truncated && <p>本次授权范围没有已记录直接引用；未记录依赖未知，不能据此认定不受影响。</p>}
        {response.items.map(item => <div key={JSON.stringify([item.id, item.node_id, item.track_id, item.clip_id])}>
          <p>{samePin(item.source, factAssetPin(visible.asset)) ? '精确路径：使用方保存的素材 ID、版本、摘要和类型均匹配所选镜头素材。' : '另一素材快照：仅素材 ID 相同，版本、摘要或类型不同；不是所选事实素材的精确匹配。'}</p>
          <UsageEvidence item={item} />
        </div>)}
      </section>)}
    </>}
  </section>;
}
