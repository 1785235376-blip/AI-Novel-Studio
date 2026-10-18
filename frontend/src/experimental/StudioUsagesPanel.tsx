import { useEffect, useRef, useState } from 'react';
import { Badge, Button, EmptyState, StatusMessage } from '../ui/primitives';
import type { ExperimentalClient } from './api';
import { segment } from './api';

type Owner = 'CREATIVE_GRAPH' | 'STUDIO_TIMELINE';
type AssetPin = { kind: 'ASSET'; id: string; version: number; digest: string; asset_kind: 'image' | 'video' | 'audio' };
type StudioUsage = {
  owner: Owner; id: string; version: number; digest: string;
  node_id?: string; definition_id?: string; track_id?: string; clip_id?: string;
  source: AssetPin; current_source: AssetPin; state: 'CURRENT' | 'STALE';
};
type UsageResponse = {
  owner: Owner; source: AssetPin; items: StudioUsage[]; coverage: 'EXACT_SAVED_DIRECT_ASSET_REFERENCES';
  truncated: boolean; limit: 200; read_only: true; automatic_regeneration: false; other_dependencies: 'UNKNOWN';
};
type ReadState = { status: 'idle' | 'loading' | 'unavailable' } | { status: 'ready'; value: UsageResponse };
type Props = { client: ExperimentalClient; assetId: string; sourceIdentity: string };
const owners = [
  { owner: 'CREATIVE_GRAPH', label: 'Studio 图定义', path: 'studio-graph-usages' },
  { owner: 'STUDIO_TIMELINE', label: 'Studio 时间线', path: 'studio-timeline-usages' },
] as const;
const initialState = (): Record<Owner, ReadState> => ({ CREATIVE_GRAPH: { status: 'idle' }, STUDIO_TIMELINE: { status: 'idle' } });
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const identityText = (value: unknown): value is string => typeof value === 'string' && value.length > 0 && value.length <= 240;
const digest = (value: unknown): value is string => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
const version = (value: unknown): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value > 0;
function isPin(value: unknown, assetId: string): value is AssetPin {
  return record(value) && value.kind === 'ASSET' && identityText(value.id) && value.id === assetId && version(value.version)
    && digest(value.digest) && typeof value.asset_kind === 'string' && ['image', 'video', 'audio'].includes(value.asset_kind);
}
const samePin = (left: AssetPin, right: AssetPin) => left.id === right.id && left.version === right.version && left.digest === right.digest && left.asset_kind === right.asset_kind;
function readResponse(value: unknown, owner: Owner, assetId: string): UsageResponse {
  // An unavailable or incompatible response is never an authorized empty list.
  if (!record(value) || value.owner !== owner || value.coverage !== 'EXACT_SAVED_DIRECT_ASSET_REFERENCES'
    || value.limit !== 200 || typeof value.truncated !== 'boolean' || value.read_only !== true
    || value.automatic_regeneration !== false || value.other_dependencies !== 'UNKNOWN'
    || !isPin(value.source, assetId) || !Array.isArray(value.items) || value.items.length > 200) throw new Error('Unavailable Studio usage coverage');
  const identities = new Set<string>();
  for (const item of value.items) {
    if (!record(item) || item.owner !== owner || !identityText(item.id) || !version(item.version) || !digest(item.digest)
      || !isPin(item.source, assetId) || !isPin(item.current_source, assetId)
      || !samePin(item.current_source, value.source)
      || ['definition_id', 'node_id', 'track_id', 'clip_id'].some(key => item[key] !== undefined && !identityText(item[key]))
      || (owner === 'CREATIVE_GRAPH' ? !identityText(item.node_id) : !identityText(item.track_id) || !identityText(item.clip_id))) throw new Error('Unavailable Studio usage evidence');
    const current = samePin(item.source, item.current_source);
    if (item.state !== (current ? 'CURRENT' : 'STALE')) throw new Error('Inconsistent Studio usage evidence');
    const identity = JSON.stringify([item.id, item.node_id, item.track_id, item.clip_id]);
    if (identities.has(identity)) throw new Error('Duplicate Studio usage evidence');
    identities.add(identity);
  }
  return value as UsageResponse;
}

function UsageEvidence({ item }: { item: StudioUsage }) {
  return <article className="experimental-record" aria-label={`${item.owner} ${item.id} ${item.node_id || item.clip_id}`}>
    <div className="experimental-actions"><Badge>{item.owner}</Badge><Badge tone={item.state === 'STALE' ? 'warning' : 'neutral'}>{item.state === 'STALE' ? 'STALE · 来源版本已变化' : 'CURRENT · 已保存引用与当前来源一致'}</Badge></div>
    <dl className="experimental-meta">
      <div><dt>使用方 ID</dt><dd>{item.id}</dd></div>
      <div><dt>使用方版本</dt><dd>v{item.version}</dd></div>
      <div><dt>使用方摘要</dt><dd>{item.digest}</dd></div>
      {item.definition_id && <div><dt>定义 ID</dt><dd>{item.definition_id}</dd></div>}
      {item.node_id && <div><dt>节点 ID</dt><dd>{item.node_id}</dd></div>}
      {item.track_id && <div><dt>轨道 ID</dt><dd>{item.track_id}</dd></div>}
      {item.clip_id && <div><dt>片段 ID</dt><dd>{item.clip_id}</dd></div>}
    </dl>
    <details className="experimental-details"><summary>已保存引用与当前资产证据</summary>
      <dl className="experimental-meta">
        <div><dt>已保存引用</dt><dd>ASSET · {item.source.id} · {item.source.asset_kind} · v{item.source.version} · {item.source.digest}</dd></div>
        <div><dt>当前资产</dt><dd>ASSET · {item.current_source.id} · {item.current_source.asset_kind} · v{item.current_source.version} · {item.current_source.digest}</dd></div>
      </dl>
    </details>
  </article>;
}

function StudioUsagesRead({ client, assetId }: Props) {
  const [results, setResults] = useState(initialState);
  const active = useRef<AbortController>();
  useEffect(() => () => { active.current?.abort(); active.current = undefined; }, []);
  const loading = owners.some(({ owner }) => results[owner].status === 'loading');
  const started = owners.some(({ owner }) => results[owner].status !== 'idle');
  const read = () => {
    if (active.current) return;
    if (!identityText(assetId)) {
      setResults({ CREATIVE_GRAPH: { status: 'unavailable' }, STUDIO_TIMELINE: { status: 'unavailable' } });
      return;
    }
    const controller = new AbortController();
    active.current = controller;
    // Remove every previous count and identity before any new authority check.
    setResults({ CREATIVE_GRAPH: { status: 'loading' }, STUDIO_TIMELINE: { status: 'loading' } });
    const current = () => active.current === controller && !controller.signal.aborted;
    // Publish the two owner projections atomically: either denial may mean the
    // source authority has changed, so a successful sibling must not survive it.
    void Promise.all(owners.map(async ({ owner, path }) => readResponse(
      await client.get<unknown>(`/production/assets/${segment(assetId)}/${path}`, controller.signal), owner, assetId,
    ))).then(([graph, timeline]) => {
      if (!samePin(graph.source, timeline.source)) throw new Error('Studio source changed between reads');
      if (current()) setResults({ CREATIVE_GRAPH: { status: 'ready', value: graph }, STUDIO_TIMELINE: { status: 'ready', value: timeline } });
    }).catch(() => {
      if (current()) {
        setResults({ CREATIVE_GRAPH: { status: 'unavailable' }, STUDIO_TIMELINE: { status: 'unavailable' } });
        controller.abort();
      }
    }).finally(() => { if (active.current === controller) active.current = undefined; });
  };
  return <section className="experimental-section" aria-label="Studio 直接使用位置（只读）">
    <div className="experimental-actions"><h3>Studio 直接使用位置（只读）</h3><Button type="button" disabled={loading} onClick={read}>{started ? '重新读取 Studio 使用位置' : '读取 Studio 使用位置'}</Button></div>
    <StatusMessage>仅覆盖当前资产在已保存图定义节点和时间线片段中的直接引用；不递归包含衍生资产、未保存编辑或推断关系。其他依赖：未知。这里只读，不会自动重新生成、锁定、更新或审核产物。</StatusMessage>
    <p>有界读取：每类最多 200 条。返回条数不是所有依赖的总数。</p>
    {owners.map(({ owner, label }) => {
      const result = results[owner];
      return <section key={owner} className="experimental-section" aria-label={`${label}使用覆盖`}>
        <h4>{label}</h4>
        {result.status === 'idle' && <StatusMessage>尚未读取，使用覆盖未知。</StatusMessage>}
        {result.status === 'loading' && <StatusMessage>正在读取已授权的直接引用…</StatusMessage>}
        {result.status === 'unavailable' && <StatusMessage tone="error">覆盖不可用：功能未启用、权限不足、读取失败或响应证据不完整。不能据此判断没有使用位置；请明确重新读取。</StatusMessage>}
        {result.status === 'ready' && <>
          <p>本次返回 {result.value.items.length} 条已授权直接引用。</p>
          {result.value.truncated && <StatusMessage tone="warning">结果已截断，尚有未显示的直接引用。此列表不代表完整覆盖。</StatusMessage>}
          {result.value.items.length === 0 && !result.value.truncated && <EmptyState title="没有已记录的直接引用" detail="这是本次授权读取的空结果；未保存编辑、衍生资产和其他依赖仍未知。" />}
          {result.value.items.map(item => <UsageEvidence key={JSON.stringify([item.id, item.node_id, item.track_id, item.clip_id])} item={item} />)}
        </>}
      </section>;
    })}
  </section>;
}

export function StudioUsagesPanel(props: Props) {
  // Monotonic lifetime identity also fences A → B → A and reused clients.
  const identity = useRef({ client: props.client, assetId: props.assetId, sourceIdentity: props.sourceIdentity, generation: 0 });
  if (identity.current.client !== props.client || identity.current.assetId !== props.assetId || identity.current.sourceIdentity !== props.sourceIdentity) {
    identity.current = { client: props.client, assetId: props.assetId, sourceIdentity: props.sourceIdentity, generation: identity.current.generation + 1 };
  }
  return <StudioUsagesRead key={identity.current.generation} {...props} />;
}
