// @vitest-environment jsdom
import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { PlanningPanel } from './PlanningPanel';
import { experimentalClient, type Row } from './api';
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const client = () => experimentalClient('novel', { sessionToken: 'test-session' });
const proposal = (id = 'selected'): Row => ({ id, version: 3, status: 'REVIEW', stale: false, title: `Route ${id}`, node_id: 'other-node', graph_id: 'other-graph', target_version: 2, fields: { goal: 'Reach the gate', beats: { one: '[假设通过规则检查] Try the key' } }, sources: { chapter: { version: 4, digest: 'chapter-digest' } }, simulation_provenance: { run_id: 'run-one', route_id: 'route-one', input_digest: 'input-digest', result_digest: 'result-digest' } });
const node = { id: 'node', version: 1, title: 'Original editor', status: 'DRAFT', level: 'PROJECT', fields: { goal: 'Original goal' }, links: {} };
function transport(override?: (url: string, init: RequestInit) => Promise<Response | undefined>) {
  let selected = proposal();
  return vi.fn(async (url: string, init: RequestInit) => {
    const value = await override?.(url, init); if (value) return value;
    if (url.endsWith('/planning/graphs')) return reply({ items: [{ id: 'graph', title: 'Original graph' }] });
    if (url.endsWith('/planning/graphs/graph')) return reply({ id: 'graph', root_node_id: 'node', version: 1, nodes: [node] });
    if (url.endsWith('/planning/templates')) return reply({ items: [] });
    if (url.endsWith('/planning/proposals')) return reply({ items: [{ ...proposal('unrelated'), node_id: 'node' }] });
    if (url.endsWith('/planning/proposals/selected/approve')) { selected = { ...selected, status: 'APPROVED', version: 4 }; return reply(selected); }
    if (url.endsWith('/planning/proposals/selected/history')) return reply({ items: [proposal()] });
    if (url.endsWith('/planning/proposals/selected')) return reply(selected);
    return reply(proposal(url.split('/').at(-1)));
  });
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
async function click(name: string) {
  await waitFor(() => expect((screen.getByRole('button', { name }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole('button', { name }));
}
it('opens the exact original proposal outside the default node, exposes its receipts, and reviews only by explicit action', async () => {
  const fetch = transport(), navigate = vi.fn(); vi.stubGlobal('fetch', fetch);
  render(<StrictMode><PlanningPanel client={client()} requestedProposalId="selected" onNavigate={navigate} /></StrictMode>);
  const article = await screen.findByRole('article', { name: '方案 Route selected' });
  expect(screen.queryByRole('article', { name: '方案 Route unrelated' })).toBeNull();
  expect(article.textContent).toContain('chapter-digest'); expect(article.textContent).toContain('input-digest'); expect(article.textContent).toContain('result-digest');
  expect(fetch.mock.calls.every(([, options]) => options.method === 'GET')).toBe(true);
  await screen.findByDisplayValue('Original editor');
  await click('核对原推演约束与证据');
  expect(navigate).toHaveBeenCalledWith({ kind: 'feature', id: 'run-one', feature: 'story_simulator_v2', task_authority: 'simulator_run' });
  await click('批准规划');
  await screen.findByText('APPROVED · v4');
  const writes = fetch.mock.calls.filter(([, options]) => options.method !== 'GET');
  expect(writes).toHaveLength(1); expect(writes[0][0]).toMatch(/\/planning\/proposals\/selected\/approve$/);
  expect(JSON.parse(writes[0][1].body as string)).toEqual({ expected_version: 3 });
  await click('方案历史'); await screen.findByRole('region', { name: '规划方案历史' });
});
it.each(['denied', 'wrong-id', 'stale'])('does not fall back to another proposal or allow stale approval: %s', async mode => {
  const fetch = transport(async url => url.endsWith('/planning/proposals/selected') ? mode === 'denied' ? reply({}, 403) : reply({ ...proposal(mode === 'wrong-id' ? 'wrong' : 'selected'), stale: mode === 'stale' }) : undefined);
  vi.stubGlobal('fetch', fetch); render(<PlanningPanel client={client()} requestedProposalId="selected" />);
  if (mode === 'stale') { await screen.findByText('STALE · 来源已变化'); expect((screen.getByRole('button', { name: '批准规划' }) as HTMLButtonElement).disabled).toBe(true); }
  else { await screen.findByRole('alert'); expect(screen.queryByRole('button', { name: '批准规划' })).toBeNull(); }
  expect(screen.queryByRole('article', { name: '方案 Route unrelated' })).toBeNull();
  expect(fetch.mock.calls.every(([, options]) => options.method === 'GET')).toBe(true);
});
it('preserves the current node draft while targeting and dismissing a proposal', async () => {
  vi.stubGlobal('fetch', transport()); const owner = client();
  const view = render(<PlanningPanel client={owner} />);
  await screen.findByRole('heading', { name: '编辑 PROJECT' });
  fireEvent.change(screen.getByLabelText('节点标题'), { target: { value: 'Keep my local draft' } });
  view.rerender(<PlanningPanel client={owner} requestedProposalId="selected" />);
  await screen.findByRole('article', { name: '方案 Route selected' });
  expect(screen.queryByRole('textbox', { name: '节点标题' })).toBeNull();
  await click('返回规划节点与方案列表');
  expect((screen.getByRole('textbox', { name: '节点标题' }) as HTMLInputElement).value).toBe('Keep my local draft');
});
it('hides prior target evidence on failed reread and can explicitly recover', async () => {
  let denied = false;
  vi.stubGlobal('fetch', transport(async url => denied && url.endsWith('/planning/proposals/selected') ? reply({}, 403) : undefined));
  render(<PlanningPanel client={client()} requestedProposalId="selected" />);
  await screen.findByRole('article', { name: '方案 Route selected' }); denied = true;
  await click('重新读取指定方案'); await screen.findByRole('alert');
  expect(screen.queryByText(/输入摘要：input-digest/)).toBeNull();
  expect(screen.queryByRole('button', { name: '批准规划' })).toBeNull();
  denied = false; await click('重新读取指定方案'); await screen.findByRole('article', { name: '方案 Route selected' });
});
it('ignores an aborted A → B → A response and owner replacement', async () => {
  let resolveFirst!: (value: Response) => void, count = 0;
  const fetch = transport(async url => {
    if (url.endsWith('/planning/proposals/selected') && ++count === 1) return new Promise<Response>(resolve => { resolveFirst = resolve; });
    return undefined;
  });
  vi.stubGlobal('fetch', fetch); const owner = client();
  const view = render(<PlanningPanel client={owner} requestedProposalId="selected" />);
  await waitFor(() => expect(resolveFirst).toBeTypeOf('function'));
  view.rerender(<PlanningPanel client={owner} requestedProposalId="second" />);
  await screen.findByRole('article', { name: '方案 Route second' });
  view.rerender(<PlanningPanel client={owner} requestedProposalId="selected" />);
  await screen.findByRole('article', { name: '方案 Route selected' });
  await act(async () => resolveFirst(reply({ ...proposal(), title: 'Late discarded' })));
  expect(screen.queryByText('Late discarded')).toBeNull();
  view.rerender(<PlanningPanel client={client()} requestedProposalId="second" />);
  await screen.findByRole('article', { name: '方案 Route second' });
  expect(screen.queryByRole('article', { name: '方案 Route selected' })).toBeNull();
});
