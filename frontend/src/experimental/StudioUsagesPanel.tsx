import { useEffect, useRef, useState } from 'react';
import { Button, EmptyState, StatusMessage } from '../ui/primitives';
import type { ExperimentalClient } from './api';
import { segment } from './api';
import { readResponse, samePin, UsageEvidence, type Owner, type UsageResponse } from './studioUsageEvidence';
const identityText = (value: unknown): value is string => typeof value === 'string' && value.length > 0 && value.length <= 240;

type ReadState = { status: 'idle' | 'loading' | 'unavailable' } | { status: 'ready'; value: UsageResponse };
type Props = { client: ExperimentalClient; assetId: string; sourceIdentity: string };
const owners = [
  { owner: 'CREATIVE_GRAPH', label: 'Studio 图定义', path: 'studio-graph-usages' },
  { owner: 'STUDIO_TIMELINE', label: 'Studio 时间线', path: 'studio-timeline-usages' },
] as const;
const initialState = (): Record<Owner, ReadState> => ({ CREATIVE_GRAPH: { status: 'idle' }, STUDIO_TIMELINE: { status: 'idle' } });
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
