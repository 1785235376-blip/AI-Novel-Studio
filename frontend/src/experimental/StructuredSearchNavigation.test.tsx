// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, expect, it, vi } from 'vitest';
import { api } from '../api';
import { useStudio } from '../store';
import { WorldRulesPanel } from '../novel/StoryDatabase';
import { AssetLibraryPanel } from '../novel/AssetLibraryPanel';
import { WorkflowPanel } from '../novel/WorkflowPanel';
import { WorldPanel } from './WorldPanel';
import { StoryGraphPanel } from './StoryGraphPanel';
import { experimentalClient } from './api';
import { WorkspaceToolsPanel } from './WorkspaceToolsPanel';

const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const original = { id: 'original-2', title: '原来源二', kind: 'CIVILIZATION', version: 1, status: 'REVIEW', data: { name: '组织' }, sources: {}, event_order: 0 };
const clients: QueryClient[] = [];
function queryView(element: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  clients.push(client);
  return render(<QueryClientProvider client={client}>{element}</QueryClientProvider>);
}
afterEach(() => { cleanup(); clients.splice(0).forEach(client => client.clear()); vi.restoreAllMocks(); vi.unstubAllGlobals(); useStudio.getState().setCollaboration(''); });

it.each([['organization', '组织 / 文明', 'world_record', 'world_character_engines_v2'], ['rule', '世界规则 / 能力', 'world_rule', 'story'], ['story_graph', '故事图谱', 'graph_record', 'temporal_story_graph_v2'], ['asset', '资产', 'asset_record', 'assets'], ['workflow', '工作流定义', 'workflow_definition', 'workflow']])('resolves %s with its exact original owner and original ID', async (kind, label, authority, feature) => {
  const indexedId = authority === 'world_rule' ? 'legacy:original-2' : 'original-2';
  const fetch = vi.fn(async (url: string, init?: RequestInit) => reply(url.endsWith('/resume') ? { item: null, availability: 'EMPTY' } : url.endsWith('/search/resolve') ? { kind: 'feature', id: original.id, novel_id: 'novel', task_authority: authority, feature } : url.includes('/search?') ? { items: [{ kind, id: indexedId, novel_id: 'novel', branch_id: null, title: original.title, revision: 'a'.repeat(64), feature, offset: 0, aliases: [], snippet: '' }], branch_sources_available: true } : {}));
  vi.stubGlobal('fetch', fetch); const navigate = vi.fn();
  render(<WorkspaceToolsPanel client={experimentalClient('novel', { sessionToken: '' })} initialSection="search" onNavigate={navigate} />);
  fireEvent.change(screen.getByLabelText('内容类型'), { target: { value: kind } });
  await screen.findByText(original.title, { selector: 'h3' });
  expect(screen.getByRole('option', { name: label })).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '打开资料库来源' }));
  await waitFor(() => expect(navigate).toHaveBeenCalledWith(expect.objectContaining({ task_authority: authority, id: original.id, feature })));
  const sent = JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/search/resolve'))![1]?.body));
  expect(sent).toMatchObject({ kind, id: indexedId, revision: 'a'.repeat(64) });
  expect(fetch.mock.calls.every(([url, init]) => !init?.method || init.method === 'GET' || url.endsWith('/search/resolve') || url.endsWith('/search/cancel'))).toBe(true);
});

it('focuses the exact original world record, preserves create draft, and clears records on denied refresh', async () => {
  let denied = false;
  const fetch = vi.fn(async (url: string) => denied ? reply({ detail: { code: 'FORBIDDEN' } }, 403) : reply({ items: url.endsWith('/world/records') ? [{ ...original, id: 'unrelated', title: '其他来源' }, original] : [] }));
  vi.stubGlobal('fetch', fetch);
  render(<WorldPanel client={experimentalClient('novel', { sessionToken: '' })} requestedRecordId={original.id} />);
  const record = await screen.findByRole('article', { name: '世界记录 原来源二' });
  await waitFor(() => expect(document.activeElement).toBe(record));
  expect(record.getAttribute('aria-current')).toBe('true');
  expect((screen.getByLabelText('世界记录标题') as HTMLInputElement).value).toBe('');
  denied = true; fireEvent.click(screen.getByRole('button', { name: '刷新实验记录' }));
  await screen.findByRole('alert');
  expect(screen.queryByRole('article', { name: '世界记录 原来源二' })).toBeNull();
});

it('opens an exact graph source in author mode without running a query or creating a candidate', async () => {
  const fetch = vi.fn(async (url: string) => reply({ items: url.endsWith('/story-graph/records') ? [{ ...original, kind: 'STORY_CONCEPT', data: { description: '原记录说明' } }] : [] }));
  vi.stubGlobal('fetch', fetch); const client = experimentalClient('novel', { sessionToken: '' });
  const view = render(<StoryGraphPanel client={client} mindEnabled />);
  await screen.findByRole('article', { name: '图谱记录 原来源二' });
  fireEvent.click(screen.getByRole('button', { name: '人物可知视图' }));
  expect(screen.queryByRole('article', { name: '图谱记录 原来源二' })).toBeNull();
  view.rerender(<StoryGraphPanel client={client} mindEnabled requestedRecordId={original.id} />);
  const record = await screen.findByRole('article', { name: '图谱记录 原来源二' });
  await waitFor(() => expect(document.activeElement).toBe(record));
  expect(fetch.mock.calls.some(([url]) => url.includes('/query?'))).toBe(false);
});

it('focuses the original legacy rule and reports a removed rule', async () => {
  vi.spyOn(api, 'worldRules').mockResolvedValue({ items: [{ id: original.id, payload: { statement: '原规则陈述' }, status: 'PENDING' }], storage: 'file' });
  const view = queryView(<WorldRulesPanel novelId="novel" requestedRuleId={original.id} />);
  const record = await screen.findByRole('article', { name: '世界规则 原规则陈述' });
  await waitFor(() => expect(document.activeElement).toBe(record));
  view.unmount();
  queryView(<WorldRulesPanel novelId="novel" requestedRuleId="removed" />);
  await screen.findByText('请求的原世界规则当前不可读或已移除，请刷新搜索。');
});

it('focuses the original asset only after its owner refresh and does not upload or delete', async () => {
  const assets = vi.spyOn(api, 'assets').mockResolvedValue([{ id: original.id, novel_id: 'novel', filename: '原素材.txt', kind: 'file', size: 10, media_type: 'text/plain', sha256: 'a'.repeat(64) } as any]);
  const upload = vi.spyOn(api, 'uploadAsset'), remove = vi.spyOn(api, 'deleteAsset');
  queryView(<AssetLibraryPanel novelId="novel" requestedAssetId={original.id} />);
  const record = await screen.findByRole('article', { name: '资产 原素材.txt' });
  await waitFor(() => expect(document.activeElement).toBe(record));
  expect(assets).toHaveBeenCalled(); expect(upload).not.toHaveBeenCalled(); expect(remove).not.toHaveBeenCalled();
});

it('selects the exact workflow definition and reads its runs without executing it', async () => {
  vi.spyOn(api, 'workflows').mockResolvedValue({ items: [{ id: original.id, title: original.title }], total: 1 } as any);
  const runs = vi.spyOn(api, 'workflowRuns').mockResolvedValue({ items: [], total: 0 } as any);
  const execute = vi.spyOn(api, 'createWorkflowRun');
  render(<WorkflowPanel novelId="novel" requestedWorkflowId={original.id} />);
  await waitFor(() => expect(runs).toHaveBeenCalledWith(original.id));
  expect(document.activeElement?.getAttribute('aria-label')).toBe('工作流定义 原来源二');
  expect(screen.getByRole('region', { name: '工作流运行记录' }).textContent).toContain(original.title);
  expect(execute).not.toHaveBeenCalled();
});

it('drops a late world source after the original client authority changes', async () => {
  let complete!: (response: Response) => void;
  const delayed = new Promise<Response>(resolve => { complete = resolve; });
  let old = true;
  vi.stubGlobal('fetch', vi.fn(async (url: string) => url.endsWith('/world/records') && old ? delayed : reply({ items: [] })));
  const view = render(<WorldPanel client={experimentalClient('novel', { sessionToken: 'old' })} requestedRecordId={original.id} />);
  old = false;
  view.rerender(<WorldPanel client={experimentalClient('novel', { sessionToken: 'new' })} requestedRecordId={original.id} />);
  await screen.findByText('请求的原世界记录当前不可读或已移除，请刷新搜索。');
  await act(async () => complete(reply({ items: [{ ...original, title: 'PRIVATE_LATE_WORLD' }] })));
  expect(screen.queryByText(/PRIVATE_LATE_WORLD/)).toBeNull();
});

it('never reuses an old asset authority in-flight result for a requested source', async () => {
  let complete!: (assets: any[]) => void;
  const delayed = new Promise<any[]>(resolve => { complete = resolve; });
  const assets = vi.spyOn(api, 'assets').mockReturnValueOnce(delayed).mockResolvedValue([]);
  queryView(<AssetLibraryPanel novelId="novel" requestedAssetId={original.id} />);
  await waitFor(() => expect(assets).toHaveBeenCalledTimes(1));
  act(() => useStudio.getState().setCollaboration('new-source-authority'));
  await waitFor(() => expect(assets).toHaveBeenCalledTimes(2));
  await screen.findByText('请求的原资产当前不可读或已移除，请刷新搜索。');
  await act(async () => complete([{ id: original.id, novel_id: 'novel', filename: 'PRIVATE_LATE_ASSET.txt', media_type: 'text/plain', size: 10, sha256: 'a'.repeat(64) }]));
  expect(screen.queryByRole('article', { name: /PRIVATE_LATE_ASSET/ })).toBeNull();
});
