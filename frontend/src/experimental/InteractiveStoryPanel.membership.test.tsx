// @vitest-environment jsdom
import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { experimentalClient } from './api';
import { InteractiveStoryPanel } from './InteractiveStoryPanel';
import type { InteractiveStory, StoryCatalog } from './interactiveStoryClient';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
const client = (id = 'novel', branchId = 'branch') => experimentalClient(id, { sessionToken: 'session', scope: { branchId } as any });
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
function story(): InteractiveStory {
  return { id: 'story', version: 1, status: 'DRAFT', stale: false, content_withheld: false,
    spec: { title: '原有改编', graph_id: 'graph', graph_version: 3, entry_node_id: 'gate', max_steps: 32, variables: [{ name: 'trusted', type: 'bool', initial: true, minimum: 0, maximum: 100 }], graph_record_ids: ['evidence'], nodes: [
      { node_id: 'gate', node_version: 2, title: '同名', dialogue: '原稿🙂é', ending: '', character_id: 'alice', background_asset_id: 'image', music_asset_id: 'music', choices: [{ id: 'home', label: '回家', target: 'end', condition: 'trusted', assignments: { trusted: false } }] },
      { node_id: 'end', node_version: 1, title: '同名', dialogue: '终章', ending: '回家', character_id: null, background_asset_id: null, music_asset_id: null, choices: [] },
    ] } };
}
function catalog(): StoryCatalog {
  return { graphs: [{ id: 'graph', version: 3, title: '原规划', truncated: false, nodes: [...story().spec!.nodes, { node_id: 'unused', node_version: 4, title: '同名' }, { node_id: 'other-unused', node_version: 1, title: '同名' }] }], characters: [{ id: 'alice', name: 'Alice' }], graph_records: [{ id: 'evidence', title: '已审核事实', version: 2 }], assets: [{ id: 'image', label: '图', kind: 'image', version: 1 }, { id: 'music', label: '音', kind: 'audio', version: 1 }], target_runtime: 'NOT_RUN' };
}
function backend(initial = story(), sources = catalog(), override?: (url: string, init: RequestInit) => Response | Promise<Response> | undefined) {
  let row = initial;
  return vi.fn(async (url: string, init: RequestInit) => {
    const special = await override?.(url, init); if (special) return special;
    if (url.endsWith('/catalog')) return reply(sources);
    if (init.method === 'GET') return reply(url.endsWith('/story') ? row : { items: [row] });
    if (init.method === 'PUT') { row = { ...row, version: row.version + 1, status: 'DRAFT', spec: JSON.parse(String(init.body)).spec }; return reply(row); }
    return reply(row);
  });
}
async function open() { fireEvent.click(await screen.findByRole('button', { name: '原有改编 · v1' })); }
const picker = () => screen.getByLabelText('待添加原规划节点') as HTMLSelectElement;
const add = () => screen.getByRole('button', { name: '添加所选原节点' }) as HTMLButtonElement;
function choose(id = 'unused') { fireEvent.change(picker(), { target: { value: id } }); }
function retained(element: HTMLElement, handler: string) {
  const key = Object.keys(element).find(key => key.startsWith('__reactProps$'))!;
  return (element as any)[key][handler] as (event?: any) => void;
}
const writes = (fetch: ReturnType<typeof backend>) => fetch.mock.calls.filter(([, init]) => init.method !== 'GET');

it('adds the exact unused ID/version with blank author fields, preserves dirty Unicode and saves only explicitly', async () => {
  const sources = catalog(); Object.assign(sources.graphs[0].nodes[2], { dialogue: 'MUST NOT COPY', choices: [{ target: 'gate' }], character_id: 'foreign' });
  const fetch = backend(story(), sources); vi.stubGlobal('fetch', fetch); render(<InteractiveStoryPanel client={client()} />); await open();
  expect(screen.getByRole('option', { name: '同名 · unused · v4' })).toBeTruthy();
  expect(screen.getByRole('option', { name: '同名 · other-unused · v1' })).toBeTruthy();
  fireEvent.change(screen.getByLabelText('对白或叙述'), { target: { value: '未保存🙂é\n第二行' } });
  choose(); fireEvent.click(add());
  expect((screen.getByLabelText('当前编辑节点') as HTMLSelectElement).value).toBe('2');
  expect(screen.getByText('原节点 ID：unused · v4')).toBeTruthy();
  expect((screen.getByLabelText('对白或叙述') as HTMLTextAreaElement).value).toBe('');
  expect(picker().value).toBe(''); expect(writes(fetch)).toHaveLength(0);
  expect([...picker().options].some(option => option.value === 'unused')).toBe(false);
  fireEvent.click(screen.getByRole('button', { name: '保存互动草稿' })); await screen.findByText('互动草稿已保存，需要重新审核。');
  const body = JSON.parse(String(writes(fetch)[0][1].body)); const expected = story().spec!; expected.nodes[0].dialogue = '未保存🙂é\n第二行';
  expect(body.expected_version).toBe(1); expect(body.spec).toEqual({ ...expected, nodes: [...expected.nodes, { node_id: 'unused', node_version: 4, title: '同名', dialogue: '', ending: '', character_id: null, background_asset_id: null, music_asset_id: null, choices: [] }] });
  expect(writes(fetch)).toHaveLength(1);
  expect(writes(fetch)[0][1].headers).toMatchObject({ 'X-Branch-Id': 'branch', 'X-Session-Token': 'session' });
});

it('reverts appended membership without a dangling editor index and rejects repeated retained add callbacks', async () => {
  const fetch = backend(); vi.stubGlobal('fetch', fetch); render(<InteractiveStoryPanel client={client()} />); await open(); choose();
  const callback = retained(add(), 'onClick'); act(() => { callback(); callback(); });
  expect((screen.getByLabelText('当前编辑节点') as HTMLSelectElement).options).toHaveLength(3);
  fireEvent.click(screen.getByRole('button', { name: '还原未保存输入' })); act(() => callback());
  expect((screen.getByLabelText('当前编辑节点') as HTMLSelectElement).value).toBe('0');
  expect((screen.getByLabelText('当前编辑节点') as HTMLSelectElement).options).toHaveLength(2);
  expect((screen.getByLabelText('对白或叙述') as HTMLTextAreaElement).value).toBe('原稿🙂é');
  expect(picker().value).toBe(''); expect(writes(fetch)).toHaveLength(0);
});

it.each(['dialogue', 'candidate', 'save'] as const)('rejects an old add callback in the same batch as %s changes', async kind => {
  const fetch = backend(); vi.stubGlobal('fetch', fetch); render(<InteractiveStoryPanel client={client()} />); await open();
  fireEvent.change(screen.getByLabelText('对白或叙述'), { target: { value: '脏稿🙂é' } }); choose();
  const oldAdd = retained(add(), 'onClick');
  const change = retained(kind === 'dialogue' ? screen.getByLabelText('对白或叙述') : kind === 'candidate' ? picker() : screen.getByRole('button', { name: '保存互动草稿' }), kind === 'save' ? 'onClick' : 'onChange');
  act(() => { change({ target: { value: kind === 'dialogue' ? '同批新稿🙂é' : 'other-unused' } }); oldAdd(); });
  if (kind === 'save') await screen.findByText('互动草稿已保存，需要重新审核。');
  expect((screen.getByLabelText('当前编辑节点') as HTMLSelectElement).options).toHaveLength(2);
  expect((screen.getByLabelText('对白或叙述') as HTMLTextAreaElement).value).toBe(kind === 'dialogue' ? '同批新稿🙂é' : '脏稿🙂é');
  if (kind === 'candidate') expect(picker().value).toBe('other-unused');
  expect(writes(fetch)).toHaveLength(kind === 'save' ? 1 : 0);
});

it('preserves composing input, requires a fresh callback after IME, and never appends mid-composition', async () => {
  const fetch = backend(); vi.stubGlobal('fetch', fetch); render(<InteractiveStoryPanel client={client()} />); await open(); choose();
  const callback = retained(add(), 'onClick'), dialogue = screen.getByLabelText('对白或叙述');
  fireEvent.compositionStart(dialogue); fireEvent.change(dialogue, { target: { value: '正在写🙂é' } }); act(() => callback());
  expect(add().disabled).toBe(true); expect((screen.getByLabelText('当前编辑节点') as HTMLSelectElement).options).toHaveLength(2);
  fireEvent.compositionEnd(dialogue); act(() => callback()); expect((screen.getByLabelText('当前编辑节点') as HTMLSelectElement).options).toHaveLength(2);
  fireEvent.click(add()); fireEvent.change(screen.getByLabelText('当前编辑节点'), { target: { value: '0' } });
  expect((screen.getByLabelText('对白或叙述') as HTMLTextAreaElement).value).toBe('正在写🙂é'); expect(writes(fetch)).toHaveLength(0);
});

it('blocks during Save and keeps appended membership and dirty text on conflict', async () => {
  let finish!: (value: Response) => void;
  const fetch = backend(story(), catalog(), (_url, init) => init.method === 'PUT' ? new Promise(resolve => { finish = resolve; }) : undefined);
  vi.stubGlobal('fetch', fetch); render(<InteractiveStoryPanel client={client()} />); await open(); choose(); fireEvent.click(add());
  fireEvent.change(screen.getByLabelText('对白或叙述'), { target: { value: '新分支🙂' } }); choose('other-unused'); const callback = retained(add(), 'onClick');
  fireEvent.click(screen.getByRole('button', { name: '保存互动草稿' })); await waitFor(() => expect(writes(fetch)).toHaveLength(1));
  expect(add().disabled).toBe(true); act(() => callback());
  finish(reply({ detail: { code: 'EXPERIMENTAL_VERSION_CONFLICT' } }, 409)); await screen.findByText(/EXPERIMENTAL_VERSION_CONFLICT/);
  expect((screen.getByLabelText('当前编辑节点') as HTMLSelectElement).options).toHaveLength(3);
  expect((screen.getByLabelText('对白或叙述') as HTMLTextAreaElement).value).toBe('新分支🙂'); expect(writes(fetch)).toHaveLength(1);
});

it.each(['archive', 'stale', 'withheld'] as const)('does not add for %s records', async kind => {
  const row = story(); if (kind === 'archive') row.status = 'ARCHIVED'; if (kind === 'stale') row.stale = true; if (kind === 'withheld') row.content_withheld = true;
  const fetch = backend(row); vi.stubGlobal('fetch', fetch); render(<InteractiveStoryPanel client={client()} />); await open();
  if (kind === 'archive') { expect(add().disabled).toBe(true); const callback = retained(picker(), 'onChange'); act(() => callback({ target: { value: 'unused' } })); expect(picker().value).toBe(''); }
  else expect(screen.queryByLabelText('待添加原规划节点')).toBeNull();
  expect(writes(fetch)).toHaveLength(0);
});

it.each(['graph-version', 'graph-id', 'duplicate-graph', 'duplicate-source-id', 'duplicate-member-id', 'member-pin', 'candidate-version', 'title-control', 'title-surrogate', 'title-limit'] as const)('fails closed for %s without repinning', async kind => {
  const row = story(), sources = catalog(), graph = sources.graphs[0];
  if (kind === 'graph-version') graph.version++;
  if (kind === 'graph-id') graph.id = 'other';
  if (kind === 'duplicate-graph') sources.graphs.push(structuredClone(graph));
  if (kind === 'duplicate-source-id') graph.nodes.push({ ...graph.nodes[2] });
  if (kind === 'duplicate-member-id') row.spec!.nodes[1].node_id = 'gate';
  if (kind === 'member-pin') graph.nodes[0].node_version++;
  if (kind === 'candidate-version') graph.nodes[2].node_version = 0;
  if (kind === 'title-control') graph.nodes[2].title = '坏\u0000字';
  if (kind === 'title-surrogate') graph.nodes[2].title = '\ud800';
  if (kind === 'title-limit') graph.nodes[2].title = '🙂'.repeat(241);
  vi.spyOn(console, 'error').mockImplementation(() => {});
  const fetch = backend(row, sources); vi.stubGlobal('fetch', fetch); render(<InteractiveStoryPanel client={client()} />); await open();
  expect(picker().disabled).toBe(true); expect(add().disabled).toBe(true); expect(screen.getByText(/原规划版本或节点来源无法精确匹配/)).toBeTruthy(); expect(writes(fetch)).toHaveLength(0);
});

it('accepts bounded astral Unicode titles and enforces the 100-node membership cap', async () => {
  const row = story(), sources = catalog(); sources.graphs[0].nodes[2].title = '🙂'.repeat(240);
  sources.graphs[0].nodes.pop();
  for (let i = 2; i < 99; i++) row.spec!.nodes.push({ ...row.spec!.nodes[1], node_id: `member-${i}` });
  sources.graphs[0].nodes.push(...row.spec!.nodes.slice(2)); sources.graphs[0].truncated = true;
  const fetch = backend(row, sources); vi.stubGlobal('fetch', fetch); render(<InteractiveStoryPanel client={client()} />); await open(); choose(); fireEvent.click(add());
  expect((screen.getByLabelText('当前编辑节点') as HTMLSelectElement).options).toHaveLength(100);
  expect((screen.getByLabelText('互动节点标题') as HTMLInputElement).value).toBe('🙂'.repeat(240));
  expect(add().disabled).toBe(true); expect(picker().disabled).toBe(true); expect(screen.getByText('互动改编最多包含 100 个节点。')).toBeTruthy(); expect(writes(fetch)).toHaveLength(0);
});

it('invalidates selection and callbacks across catalog loading, errors and graph A to B to A', async () => {
  let response: Response | Promise<Response> = reply(catalog()); let finish!: (value: Response) => void;
  const fetch = backend(story(), catalog(), url => url.endsWith('/catalog') ? response : undefined);
  vi.stubGlobal('fetch', fetch); render(<InteractiveStoryPanel client={client()} />); await open(); choose(); const oldAdd = retained(add(), 'onClick'), oldChoose = retained(picker(), 'onChange');
  response = new Promise(resolve => { finish = resolve; }); fireEvent.click(screen.getByRole('button', { name: '刷新可用规划与资产' }));
  await waitFor(() => expect(picker().disabled).toBe(true)); act(() => { oldAdd(); oldChoose({ target: { value: 'unused' } }); });
  finish(reply({ detail: { code: 'FORBIDDEN' } }, 403)); await screen.findByText(/当前身份没有此操作权限/); expect(picker().disabled).toBe(true);
  const changed = catalog(); changed.graphs[0].version = 4; response = reply(changed); fireEvent.click(screen.getByRole('button', { name: '刷新可用规划与资产' })); await screen.findByText(/原规划版本或节点来源无法精确匹配/);
  response = reply(catalog()); fireEvent.click(screen.getByRole('button', { name: '刷新可用规划与资产' })); await waitFor(() => expect(picker().disabled).toBe(false));
  act(() => { oldAdd(); oldChoose({ target: { value: 'unused' } }); }); expect(picker().value).toBe('');
  expect((screen.getByLabelText('当前编辑节点') as HTMLSelectElement).options).toHaveLength(2); choose(); fireEvent.click(add()); expect((screen.getByLabelText('当前编辑节点') as HTMLSelectElement).options).toHaveLength(3); expect(writes(fetch)).toHaveLength(0);
});

it.each(['client', 'scope'] as const)('rejects retained callbacks after %s A to B to A in StrictMode', async kind => {
  const fetch = backend(); vi.stubGlobal('fetch', fetch); const a = client(), b = kind === 'client' ? client('other') : client('novel', 'other-branch');
  const view = render(<StrictMode><InteractiveStoryPanel client={a} /></StrictMode>); await open(); choose(); const callback = retained(add(), 'onClick');
  view.rerender(<StrictMode><InteractiveStoryPanel client={b} /></StrictMode>); await open();
  view.rerender(<StrictMode><InteractiveStoryPanel client={a} /></StrictMode>); await open(); act(() => callback());
  expect((screen.getByLabelText('当前编辑节点') as HTMLSelectElement).options).toHaveLength(2); expect(picker().value).toBe(''); expect(writes(fetch)).toHaveLength(0);
});

it('uses the existing choice controls to connect a new ending without automatic edges', async () => {
  const fetch = backend(); vi.stubGlobal('fetch', fetch); render(<InteractiveStoryPanel client={client()} />); await open(); choose(); fireEvent.click(add());
  fireEvent.change(screen.getByLabelText('结局名称（留空表示非结局）'), { target: { value: '新的结局' } });
  fireEvent.change(screen.getByLabelText('当前编辑节点'), { target: { value: '0' } });
  expect(screen.queryByLabelText('选择 2 文案')).toBeNull(); fireEvent.click(screen.getByRole('button', { name: '添加互动选择' }));
  expect([...(screen.getByLabelText('选择 2 目标') as HTMLSelectElement).options].find(option => option.value === 'unused')?.textContent).toBe('同名 · unused · v4');
  fireEvent.change(screen.getByLabelText('选择 2 目标'), { target: { value: 'unused' } }); fireEvent.change(screen.getByLabelText('选择 2 文案'), { target: { value: '走向新结局' } });
  fireEvent.click(screen.getByRole('button', { name: '保存互动草稿' })); await screen.findByText('互动草稿已保存，需要重新审核。');
  const saved = JSON.parse(String(writes(fetch)[0][1].body)).spec;
  expect(saved.nodes[0].choices[0]).toEqual(story().spec!.nodes[0].choices[0]); expect(saved.nodes[0].choices[1].target).toBe('unused'); expect(saved.nodes[2].ending).toBe('新的结局'); expect(saved.entry_node_id).toBe('gate');
});
