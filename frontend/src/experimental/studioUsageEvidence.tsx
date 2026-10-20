import { Badge } from '../ui/primitives';

export type Owner = 'CREATIVE_GRAPH' | 'STUDIO_TIMELINE';
export type AssetPin = { kind: 'ASSET'; id: string; version: number; digest: string; asset_kind: 'image' | 'video' | 'audio' };
export type StudioUsage = {
  owner: Owner; id: string; version: number; digest: string;
  node_id?: string; definition_id?: string; track_id?: string; clip_id?: string;
  source: AssetPin; current_source: AssetPin; state: 'CURRENT' | 'STALE';
};
export type UsageResponse = {
  owner: Owner; source: AssetPin; items: StudioUsage[]; coverage: 'EXACT_SAVED_DIRECT_ASSET_REFERENCES';
  truncated: boolean; limit: 200; read_only: true; automatic_regeneration: false; other_dependencies: 'UNKNOWN';
};
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const identityText = (value: unknown): value is string => typeof value === 'string' && value.length > 0 && value.length <= 240;
const digest = (value: unknown): value is string => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
const version = (value: unknown): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value > 0;
function isPin(value: unknown, assetId: string): value is AssetPin {
  return record(value) && value.kind === 'ASSET' && identityText(value.id) && value.id === assetId && version(value.version)
    && digest(value.digest) && typeof value.asset_kind === 'string' && ['image', 'video', 'audio'].includes(value.asset_kind);
}
export const samePin = (left: AssetPin, right: AssetPin) => left.id === right.id && left.version === right.version && left.digest === right.digest && left.asset_kind === right.asset_kind;
export function readResponse(value: unknown, owner: Owner, assetId: string): UsageResponse {
  // An unavailable or incompatible response is never an authorized empty list.
  if (!record(value) || value.owner !== owner || value.coverage !== 'EXACT_SAVED_DIRECT_ASSET_REFERENCES'
    || value.limit !== 200 || typeof value.truncated !== 'boolean' || value.read_only !== true
    || value.automatic_regeneration !== false || value.other_dependencies !== 'UNKNOWN'
    || !isPin(value.source, assetId) || !Array.isArray(value.items) || value.items.length > 200) throw new Error('Unavailable Studio usage coverage');
  const identities = new Set<string>();
  const documents = new Map<string, string>();
  for (const item of value.items) {
    if (!record(item) || item.owner !== owner || !identityText(item.id) || !version(item.version) || !digest(item.digest)
      || !isPin(item.source, assetId) || !isPin(item.current_source, assetId)
      || !samePin(item.current_source, value.source)
      || ['definition_id', 'node_id', 'track_id', 'clip_id'].some(key => item[key] !== undefined && !identityText(item[key]))
      || (owner === 'CREATIVE_GRAPH'
        ? !identityText(item.node_id) || item.definition_id !== 'asset_reference' || item.track_id !== undefined || item.clip_id !== undefined
        : !identityText(item.track_id) || !identityText(item.clip_id) || item.node_id !== undefined || item.definition_id !== undefined)) throw new Error('Unavailable Studio usage evidence');
    const documentPin = JSON.stringify([item.version, item.digest]);
    if (documents.has(item.id) && documents.get(item.id) !== documentPin) throw new Error('Inconsistent owner document snapshot');
    documents.set(item.id, documentPin);
    if (documents.size > 25) throw new Error('Studio owner document limit exceeded');
    const current = samePin(item.source, item.current_source);
    if (item.state !== (current ? 'CURRENT' : 'STALE')) throw new Error('Inconsistent Studio usage evidence');
    const identity = JSON.stringify([item.id, item.node_id, item.track_id, item.clip_id]);
    if (identities.has(identity)) throw new Error('Duplicate Studio usage evidence');
    identities.add(identity);
  }
  return value as UsageResponse;
}

export function UsageEvidence({ item }: { item: StudioUsage }) {
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
