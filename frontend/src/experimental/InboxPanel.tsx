import { useEffect, useRef, useState } from 'react';
import { Badge, Button, Panel, StatusMessage } from '../ui/primitives';
import { type ExperimentalClient, type Row, type Rows, segment } from './api';
import { Details, Field, Form, RecordStatus, Refresh, ResourceState, useAction, useResource } from './shared';
import { hasPromotionIntent, needsPromotionRecovery, PromotionRecovery } from './PromotionRecovery';
const actionLabels: Record<string, string> = { approve: '批准', reject: '驳回', reopen: '重开审核' };
export function InboxPanel({ client, requestedItemId, requestedDomain }: { client: ExperimentalClient; requestedItemId?: string; requestedDomain?: string }) {
  const [domain, setDomain] = useState(''), [status, setStatus] = useState(''), [search, setSearch] = useState(''), [stale, setStale] = useState(''), [filter, setFilter] = useState('');
  const targetFocused = useRef('');
  useEffect(() => { if (requestedItemId && requestedDomain) { setDomain(requestedDomain); setFilter('?' + new URLSearchParams({ domain: requestedDomain })); targetFocused.current = ''; } }, [requestedItemId, requestedDomain, client]);
  const resource = useResource(signal => client.get<Rows & { partial?: boolean; unavailable?: unknown[] }>('/review-inbox' + filter, signal), [client, filter]);
  const action = useAction(resource.reload), [selected, setSelected] = useState<string[]>([]), [batchResult, setBatchResult] = useState<any>();
  const rows = resource.data?.items || [], key = (row: Row) => `${row.domain}:${row.id}`;
  const selectedRows = rows.filter(row => selected.includes(key(row)));
  const batchAllowed = (operation: string) => selectedRows.length > 0 && selectedRows.every(row => !hasPromotionIntent(row) && row.batch_safe === true && row.batch_actions?.includes(operation) && (operation !== 'approve' || !row.stale));
  const execute = (row: Row, operation: string) => action.run(async () => {
    try { return await client.post(`/review-inbox/${segment(row.domain)}/${segment(row.id)}/${operation}`, { expected_version: row.version }); }
    catch (error) { if (operation === 'approve') resource.reload(); throw error; }
  }, '领域审核已完成');
  const busy = action.busy || resource.loading;
  return <Panel title="Unified Review Inbox · 统一审核" actions={<Refresh reload={resource.reload} busy={busy} />}>
    <StatusMessage>所有动作转交原领域审核服务。不可批量审核的领域不会显示批量选择，过期记录不能批准。</StatusMessage>{action.feedback}
    <Form onSubmit={() => { const params = new URLSearchParams(); Object.entries({ domain, status, search, stale }).forEach(([key, value]) => { if (value) params.set(key, value); }); setFilter(`?${params}`); setSelected([]); }}>
      <div className="experimental-grid"><Field label="审核领域"><select value={domain} onChange={event => setDomain(event.target.value)}><option value="">全部领域</option>{['import', 'world', 'planning', 'agent_team', 'media', 'audiobook', 'legacy_import', 'legacy_planning', 'legacy_canon', 'legacy_world_rule', 'legacy_agent', 'legacy_workflow', 'legacy_media', 'export_release_gate'].map(value => <option key={value}>{value}</option>)}</select></Field><Field label="审核状态筛选"><input value={status} placeholder="例如 REVIEW" onChange={event => setStatus(event.target.value)} /></Field><Field label="来源过期筛选"><select value={stale} onChange={event => setStale(event.target.value)}><option value="">全部来源状态</option><option value="true">已过期</option><option value="false">未过期</option></select></Field></div><Field label="搜索审核项"><input value={search} onChange={event => setSearch(event.target.value)} /></Field><Button type="submit" disabled={busy}>筛选审核项</Button>
    </Form>
    {requestedItemId && !resource.loading && !resource.error && !rows.some(row => row.id === requestedItemId && row.domain === requestedDomain) && <StatusMessage tone="warning">请求的原审核项当前不可读或已移除；未自动选择其他记录。</StatusMessage>}
    <ResourceState loading={resource.loading} error={resource.error} empty={!rows.length} />
    {resource.data?.partial && <StatusMessage tone="warning">部分领域暂不可读；这里不是完整队列。</StatusMessage>}
    {!!resource.data?.unavailable?.length && <Details label="不可用领域" value={resource.data.unavailable} />}
    <div className="experimental-actions">{['approve', 'reject'].map(operation => <Button key={operation} disabled={busy || !batchAllowed(operation)} onClick={() => action.run(async () => { setBatchResult(await client.post('/review-inbox/batch', { items: selectedRows.map(row => ({ domain: row.domain, id: row.id, action: operation, expected_version: row.version })) })); setSelected([]); }, '批量处理结果已返回，请逐项核对')}>批量{actionLabels[operation]}已选审核项</Button>)}</div>
    {batchResult && <section aria-label="批量审核结果"><StatusMessage tone={batchResult.status === 'COMPLETED' ? 'success' : 'warning'}>{batchResult.status} · 未处理 {batchResult.remaining}</StatusMessage><Details label="逐项 checkpoint（成功项不会自动重试）" value={batchResult.results} /></section>}
    <div className="experimental-list">{rows.map(row => <article className="experimental-record" key={key(row)} aria-current={row.id === requestedItemId && row.domain === requestedDomain ? "true" : undefined} tabIndex={row.id === requestedItemId && row.domain === requestedDomain ? 0 : undefined} ref={element => { if (element && row.id === requestedItemId && row.domain === requestedDomain && targetFocused.current !== key(row)) { targetFocused.current = key(row); element.focus(); element.scrollIntoView?.({ block: "nearest" }); } }} aria-label={`审核项 ${row.domain} ${typeof row.preview === 'string' ? row.preview : row.id}`}>
      <div className="experimental-actions"><Badge tone="info">{row.domain}</Badge><strong>{typeof row.preview === 'string' ? row.preview : row.preview?.title || row.id}</strong></div><RecordStatus row={row} />
      <dl className="experimental-meta">{Object.entries({ source: row.source, project: row.project, workspace: row.workspace, branch: row.branch, created_by: row.created_by, risk: row.risk, privacy_state: row.privacy_state, source_hash: row.source_hash }).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{typeof value === 'object' ? JSON.stringify(value) : String(value ?? '—')}</dd></div>)}</dl>
      <Details label="来源版本、预览与目标" value={{ source_versions: row.source_versions, preview: row.preview, target: row.target }} />
      <PromotionRecovery row={row} busy={busy} sourceUnavailable={!!resource.error} onResume={row.allowed_actions?.includes('approve') ? () => execute(row, 'approve') : undefined} />
      {row.batch_safe === true && !hasPromotionIntent(row) && <label className="experimental-check"><input type="checkbox" checked={selected.includes(key(row))} onChange={event => setSelected(current => event.target.checked ? [...current, key(row)] : current.filter(id => id !== key(row)))} />加入安全批量审核</label>}
      <div className="experimental-actions">{(row.allowed_actions || []).filter((operation: string) => operation in actionLabels && !needsPromotionRecovery(row) && (!hasPromotionIntent(row) || operation === 'approve')).map((operation: string) => <Button key={operation} disabled={busy || (operation === 'approve' && row.stale)} onClick={() => execute(row, operation)}>{actionLabels[operation]}此审核项</Button>)}{!row.allowed_actions?.length && <span>此领域当前状态仅供查看。</span>}</div>
    </article>)}</div>
  </Panel>;
}
