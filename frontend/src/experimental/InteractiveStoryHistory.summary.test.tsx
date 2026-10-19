// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { experimentalClient } from './api';
import { InteractiveStoryHistory } from './InteractiveStoryHistory';
import { interactiveStoryClient, type InteractiveStory } from './interactiveStoryClient';
import { summarizeHistorySpec } from './interactiveStoryHistorySummary';

const response = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
const digest = 'a'.repeat(64);
const choice = (id: string, target: string) => ({ id, label: id, target, condition: '', assignments: {} });
const node = (nodeId: string, title: string, choices: ReturnType<typeof choice>[] = [], ending = '') => ({ node_id: nodeId, node_version: 1, title, dialogue: '', character_id: null, background_asset_id: null, music_asset_id: null, ending, choices });
const variable = (name: string) => ({ name, type: 'bool' as const, initial: true, minimum: 0, maximum: 100 });
const spec = (over: Record<string, any>) => ({ title: '历史标题', graph_id: 'graph', graph_version: 1, entry_node_id: 'gate', nodes: [node('gate', '城门', [choice('go', 'end')]), node('end', '终章', [], '回家')], variables: [variable('trusted')], graph_record_ids: [], max_steps: 8, ...over });
const revision = (version: number, specValue: unknown, over: Record<string, any> = {}) => ({ version, status: 'DRAFT', spec: specValue, preview_digest: digest, ...over });
const api = () => interactiveStoryClient(experimentalClient('n1', { sessionToken: '' }));
const summaryOf = (version: number) => within(screen.getByRole('region', { name: '历史版本摘要 v' + version }));
function backend(items: unknown[], restore?: (init?: RequestInit) => Response | Promise<Response> | undefined) {
  const fetch = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/restore-revision')) { const special = await restore?.(init); if (special) return special; }
    if (url.endsWith('/history')) return response({ items, truncated: false });
    if (url.endsWith('/restore-revision')) return response({ id: 'story', version: 4, status: 'DRAFT' });
    return response({ items: [] });
  });
  return fetch;
}
async function load(items: unknown[], options: { story?: Record<string, any>; blocked?: boolean; restore?: (init?: RequestInit) => Response | Promise<Response> | undefined } = {}) {
  const fetch = backend(items, options.restore);
  vi.stubGlobal('fetch', fetch);
  const perform = vi.fn(async (fn: () => Promise<unknown>) => { await fn(); });
  const story = { id: 'story', version: 2, status: 'DRAFT', ...(options.story || {}) } as unknown as InteractiveStory;
  const view = render(<InteractiveStoryHistory api={api()} story={story} blocked={options.blocked || false} perform={perform} />);
  fireEvent.click(screen.getByRole('button', { name: '读取互动改编历史' }));
  await screen.findByRole('region', { name: '历史版本摘要 v' + (items[0] as any).version });
  return { fetch, perform, view, story };
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it('shows the six readable summary fields from that history revision spec', async () => {
  await load([revision(1, spec({ title: '历史甲', variables: [variable('trusted'), variable('mood')] }))]);
  const summary = summaryOf(1);
  expect(summary.getByText('历史甲')).toBeTruthy();
  expect(summary.getByText('入口节点：城门')).toBeTruthy();
  expect(summary.getByText('节点数：2')).toBeTruthy();
  expect(summary.getByText('选择项总数：1')).toBeTruthy();
  expect(summary.getByText('声明结局：1')).toBeTruthy();
  expect(summary.getByText('变量数：2')).toBeTruthy();
});

it('computes zero values for empty node, choice and variable arrays', async () => {
  await load([revision(1, spec({ nodes: [], variables: [] }))]);
  const summary = summaryOf(1);
  expect(summary.getByText('节点数：0')).toBeTruthy();
  expect(summary.getByText('选择项总数：0')).toBeTruthy();
  expect(summary.getByText('声明结局：0')).toBeTruthy();
  expect(summary.getByText('变量数：0')).toBeTruthy();
  expect(summary.getByText(/入口节点：入口不可解析（原始入口 ID：gate）/)).toBeTruthy();
});

it('counts zero choices when every declared choice array is empty', async () => {
  await load([revision(2, spec({ nodes: [node('gate', '城门', []), node('end', '终章', [], '回家')], variables: [] }))]);
  expect(summaryOf(2).getByText('选择项总数：0')).toBeTruthy();
  expect(summaryOf(2).getByText('声明结局：1')).toBeTruthy();
});

it('reports an unresolvable entry when entry_node_id is missing without inventing one', async () => {
  await load([revision(1, spec({ entry_node_id: undefined }))]);
  expect(summaryOf(1).getByText('入口节点：入口不可解析')).toBeTruthy();
  expect(summaryOf(1).queryByText(/原始入口 ID/)).toBeNull();
});

it('reports an unresolvable entry for an unknown entry ID while keeping the raw ID', async () => {
  await load([revision(2, spec({ entry_node_id: 'ghost' }))]);
  expect(summaryOf(2).getByText(/入口节点：入口不可解析（原始入口 ID：ghost）/)).toBeTruthy();
});

it('reports an unresolvable entry when the entry node title is missing', async () => {
  await load([revision(3, spec({ nodes: [node('gate', ''), node('end', '终章')] }))]);
  expect(summaryOf(3).getByText(/入口节点：入口不可解析（原始入口 ID：gate）/)).toBeTruthy();
});

it('keeps distinct titles and entries for different history revisions', async () => {
  await load([
    revision(1, spec({ title: '历史甲', variables: [variable('a')] })),
    revision(2, spec({ title: '历史乙', entry_node_id: 'shore', nodes: [node('shore', '岸边'), node('other', '别处')], variables: [] }))
  ]);
  expect(summaryOf(1).getByText('历史甲')).toBeTruthy();
  expect(summaryOf(1).getByText('入口节点：城门')).toBeTruthy();
  expect(summaryOf(1).getByText('节点数：2')).toBeTruthy();
  expect(summaryOf(2).getByText('历史乙')).toBeTruthy();
  expect(summaryOf(2).getByText('入口节点：岸边')).toBeTruthy();
  expect(summaryOf(2).getByText('变量数：0')).toBeTruthy();
});

it('does not re-read or reuse the current story version when it changes', async () => {
  const items = [revision(1, spec({ title: '历史甲' }))];
  const { view, fetch, story } = await load(items);
  const calls = fetch.mock.calls.length;
  view.rerender(<InteractiveStoryHistory api={api()} story={{ ...story, version: 9 } as InteractiveStory} blocked={false} perform={async () => undefined} />);
  expect(summaryOf(1).getByText('历史甲')).toBeTruthy();
  expect(summaryOf(1).getByText('节点数：2')).toBeTruthy();
  expect(fetch.mock.calls.length).toBe(calls);
});

it('counts every declared choice even when different nodes reuse the same choice ID', async () => {
  await load([revision(1, spec({ nodes: [node('gate', '城门', [choice('dup', 'a'), choice('dup', 'b')]), node('end', '终章', [], '回家')] }))]);
  expect(summaryOf(1).getByText('选择项总数：2')).toBeTruthy();
});

it('counts declared endings without reachability or condition analysis', async () => {
  await load([revision(1, spec({ nodes: [node('gate', '城门', [choice('go', 'end')]), node('end', '终章', [], '回家'), node('孤岛', '未到达的结局', [], '秘密')] }))]);
  expect(summaryOf(1).getByText('声明结局：2')).toBeTruthy();
  expect(summaryOf(1).getByText('节点数：3')).toBeTruthy();
});

it('survives a missing or malformed spec without crashing the whole history list', async () => {
  await load([revision(1, null), revision(2, spec({ title: '正常历史' }))]);
  expect(summaryOf(1).getByText('标题未记录')).toBeTruthy();
  expect(summaryOf(1).getByText('节点数：不可用')).toBeTruthy();
  expect(summaryOf(1).getByText('选择项总数：不可用')).toBeTruthy();
  expect(summaryOf(1).getByText('声明结局：不可用')).toBeTruthy();
  expect(summaryOf(1).getByText('变量数：不可用')).toBeTruthy();
  expect(summaryOf(2).getByText('正常历史')).toBeTruthy();
});

it('keeps the original detail fold and its raw spec content', async () => {
  await load([revision(1, spec({ title: '历史甲' }))]);
  fireEvent.click(screen.getByText('互动历史 v1'));
  expect(screen.getByText(/"title": "历史甲"/)).toBeTruthy();
});

it('keeps the restore button and its exact expected_version / restore_version / preview_digest payload', async () => {
  const { fetch, perform } = await load([revision(1, spec({ title: '历史甲' }))]);
  fireEvent.click(screen.getByRole('button', { name: '恢复互动 v1 为待审草稿' }));
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => String(url).endsWith('/restore-revision'))).toBe(true));
  const request = fetch.mock.calls.find(([url]) => String(url).endsWith('/restore-revision'))!;
  expect(JSON.parse(String(request[1]!.body))).toEqual({ expected_version: 2, restore_version: 1, preview_digest: digest });
  expect(perform).toHaveBeenCalledTimes(1);
});

it('keeps the archived-story restore restriction', async () => {
  await load([revision(1, spec({ title: '历史甲' }))], { story: { status: 'ARCHIVED' } });
  expect((screen.getByRole('button', { name: '恢复互动 v1 为待审草稿' }) as HTMLButtonElement).disabled).toBe(true);
});

it('keeps the blocked-state history and restore restrictions without any request', () => {
  const fetch = backend([]); vi.stubGlobal('fetch', fetch);
  const story = { id: 'story', version: 2, status: 'DRAFT' } as unknown as InteractiveStory;
  render(<InteractiveStoryHistory api={api()} story={story} blocked={true} perform={vi.fn()} />);
  expect((screen.getByRole('button', { name: '读取互动改编历史' }) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.queryByRole('button', { name: /恢复互动/ })).toBeNull();
  expect(fetch).not.toHaveBeenCalled();
});

it('keeps the original version-conflict rejection on restore without pretending success', async () => {
  const fetch = backend([revision(1, spec({ title: '历史甲' }))], () => response({ detail: { code: 'EXPERIMENTAL_VERSION_CONFLICT' } }, 409));
  vi.stubGlobal('fetch', fetch);
  const outcomes: unknown[] = [];
  const perform = vi.fn(async (fn: () => Promise<unknown>) => { try { await fn(); outcomes.push('resolved'); } catch (error) { outcomes.push(error); } });
  render(<InteractiveStoryHistory api={api()} story={{ id: 'story', version: 2, status: 'DRAFT' } as unknown as InteractiveStory} blocked={false} perform={perform} />);
  fireEvent.click(screen.getByRole('button', { name: '读取互动改编历史' }));
  await screen.findByRole('region', { name: '历史版本摘要 v1' });
  fireEvent.click(screen.getByRole('button', { name: '恢复互动 v1 为待审草稿' }));
  await waitFor(() => expect(outcomes).toHaveLength(1));
  const outcome = outcomes[0] as { problem?: { code?: string } };
  expect(outcome?.problem?.code ?? String(outcome)).toContain('EXPERIMENTAL_VERSION_CONFLICT');
  expect(screen.queryByText('已创建历史内容的新待审版本。需要重新检查路径并批准。')).toBeNull();
  expect(screen.getByText('历史甲')).toBeTruthy();
});

it('adds no history or restore request when rendering summaries and toggling details', async () => {
  const items = [revision(1, spec({ title: '历史甲' })), revision(2, spec({ title: '历史乙' }))];
  const before = JSON.stringify(items);
  const { fetch } = await load(items);
  const calls = fetch.mock.calls.length;
  fireEvent.click(screen.getByText('互动历史 v1'));
  fireEvent.click(screen.getByText('互动历史 v2'));
  expect(fetch.mock.calls.length).toBe(calls);
  expect(JSON.stringify(items)).toBe(before);
});

it('derives the same pure summary from the same frozen spec on every call', () => {
  const value = Object.freeze(spec({ title: '冻结历史' }));
  const first = summarizeHistorySpec(value);
  const second = summarizeHistorySpec(value);
  expect(second).toEqual(first);
  expect(first).toEqual({ title: '冻结历史', titleMissing: false, entryId: 'gate', entryTitle: '城门', entryResolved: true, nodeCount: 2, choiceCount: 1, declaredEndingCount: 1, variableCount: 1 });
  expect(summarizeHistorySpec(undefined).nodeCount).toBeNull();
});