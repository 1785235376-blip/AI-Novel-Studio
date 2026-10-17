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
      { node_id: 'unused', node_version: 4, title: '同名', dialogue: '要移除的作者内容🙂', ending: '', character_id: 'alice', background_asset_id: 'image', music_asset_id: 'music', choices: [{ id: 'outgoing', label: '去结局', target: 'end', condition: '', assignments: {} }] },
    ] }, analysis: { issues: [], warnings: [{ code: 'UNREACHABLE', node_id: 'unused' }], endings: [{ node_id: 'end', ending: '回家', choices: ['home'] }], states_checked: 2, analysis_complete: true, state_limit_reached: false, step_limit_reached: false, max_steps: 32, can_review: true } };
}
function catalog(): StoryCatalog {
  return { graphs: [{ id: 'graph', version: 3, title: '原规划', truncated: false, nodes: [...story().spec!.nodes, { node_id: 'other', node_version: 1, title: '同名' }] }], characters: [{ id: 'alice', name: 'Alice' }], graph_records: [{ id: 'evidence', title: '事实', version: 2 }], assets: [{ id: 'image', label: '图', kind: 'image', version: 1 }, { id: 'music', label: '音', kind: 'audio', version: 1 }], target_runtime: 'NOT_RUN' };
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
const preview = () => screen.getByRole('button', { name: '预览移除当前节点' }) as HTMLButtonElement;
const confirm = () => screen.getByRole('button', { name: '确认移除所选节点' }) as HTMLButtonElement;
const current = () => screen.getByLabelText('当前编辑节点') as HTMLSelectElement;
const select = (index: number) => fireEvent.change(current(), { target: { value: String(index) } });
function retained(element: HTMLElement, handler = 'onClick') { const key = Object.keys(element).find(key => key.startsWith('__reactProps$'))!; return (element as any)[key][handler] as (event?: any) => void; }
const writes = (fetch: ReturnType<typeof backend>) => fetch.mock.calls.filter(([, init]) => init.method !== 'GET');

it('previews exact ID and version, explicitly removes only that node, preserves dirty Unicode and saves through the original contract', async () => {
  const fetch = backend(); vi.stubGlobal('fetch', fetch); render(<InteractiveStoryPanel client={client()} />); await open();
  fireEvent.change(screen.getByLabelText('对白或叙述'), { target: { value: '保留未保存🙂é\n第二行' } }); select(2); fireEvent.click(preview());
  expect(screen.getByText('待移除：同名 · unused · v4')).toBeTruthy(); expect(current().options).toHaveLength(3); expect(writes(fetch)).toHaveLength(0);
  fireEvent.click(confirm()); expect(current().options).toHaveLength(2); expect(current().value).toBe('1'); expect(writes(fetch)).toHaveLength(0);
  select(0); expect((screen.getByLabelText('对白或叙述') as HTMLTextAreaElement).value).toBe('保留未保存🙂é\n第二行');
  fireEvent.click(screen.getByRole('button', { name: '保存互动草稿' })); await screen.findByText('互动草稿已保存，需要重新审核。');
  const expected = story().spec!; expected.nodes.pop(); expected.nodes[0].dialogue = '保留未保存🙂é\n第二行';
  expect(JSON.parse(String(writes(fetch)[0][1].body))).toEqual({ expected_version: 1, spec: expected }); expect(writes(fetch)).toHaveLength(1);
  expect(writes(fetch)[0][1].headers).toMatchObject({ 'X-Branch-Id': 'branch', 'X-Session-Token': 'session' });
});

it('explains entry and incoming blockers with exact IDs and uses original controls to resolve them', async () => {
  const fetch = backend(); vi.stubGlobal('fetch', fetch); render(<InteractiveStoryPanel client={client()} />); await open();
  fireEvent.click(preview()); expect(confirm().disabled).toBe(true); expect(screen.getByText(/这是故事入口/)).toBeTruthy();
  select(1); fireEvent.click(preview()); expect(confirm().disabled).toBe(true);
  expect(screen.getByText('入站引用：节点 gate · 选择 home')).toBeTruthy(); expect(screen.getByText('入站引用：节点 unused · 选择 outgoing')).toBeTruthy();
  select(0); fireEvent.change(screen.getByLabelText('故事入口节点'), { target: { value: 'end' } }); fireEvent.click(preview()); expect(confirm().disabled).toBe(false);
  fireEvent.click(confirm()); expect(current().options).toHaveLength(2); expect((screen.getByLabelText('故事入口节点') as HTMLSelectElement).value).toBe('end');
  expect(writes(fetch)).toHaveLength(0);
});

it('does not cascade incoming choices, including false-condition and self-loop references', async () => {
  const row = story(); row.spec!.nodes[2].choices[0].target = 'unused'; row.spec!.nodes[2].choices[0].condition = 'False';
  const fetch = backend(row); vi.stubGlobal('fetch', fetch); render(<InteractiveStoryPanel client={client()} />); await open(); select(2); fireEvent.click(preview());
  expect(confirm().disabled).toBe(true); expect(screen.getByText('入站引用：节点 unused · 选择 outgoing')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '移除选择 1' })); expect(screen.queryByRole('region', { name: '互动节点移除预览' })).toBeNull();
  fireEvent.click(preview()); fireEvent.click(confirm()); expect(current().options).toHaveLength(2); expect(writes(fetch)).toHaveLength(0);
});

it('keeps at least one node and cancels preview without changing the draft', async () => {
  const row = story(); row.spec!.nodes = [row.spec!.nodes[0]]; row.spec!.nodes[0].choices = [];
  const fetch = backend(row); vi.stubGlobal('fetch', fetch); render(<InteractiveStoryPanel client={client()} />); await open(); fireEvent.click(preview());
  expect(confirm().disabled).toBe(true); expect(screen.getByText('必须保留至少一个互动节点。')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '取消移除节点' })); expect(screen.queryByRole('button', { name: '确认移除所选节点' })).toBeNull();
  expect((screen.getByRole('button', { name: '保存互动草稿' }) as HTMLButtonElement).disabled).toBe(true); expect(writes(fetch)).toHaveLength(0);
});

it('re-adds only blank source content and prevents saved analysis or retained navigation from targeting a replacement', async () => {
  const fetch = backend(); vi.stubGlobal('fetch', fetch); render(<InteractiveStoryPanel client={client()} />); await open();
  const locate = screen.getByRole('button', { name: '定位 UNREACHABLE 节点 unused' }), oldLocate = retained(locate);
  select(2); fireEvent.click(preview()); const oldConfirm = retained(confirm()); act(() => { oldConfirm(); oldConfirm(); });
  expect(current().options).toHaveLength(2); expect((locate as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText('待添加原规划节点'), { target: { value: 'unused' } }); fireEvent.click(screen.getByRole('button', { name: '添加所选原节点' }));
  expect(current().options).toHaveLength(3); expect((screen.getByLabelText('对白或叙述') as HTMLTextAreaElement).value).toBe(''); expect(screen.queryByLabelText('选择 1 文案')).toBeNull();
  expect((screen.getByLabelText('对白角色') as HTMLSelectElement).value).toBe(''); expect((locate as HTMLButtonElement).disabled).toBe(true);
  select(0); act(() => { oldConfirm(); oldLocate(); }); expect(current().value).toBe('0'); expect(current().options).toHaveLength(3);
  fireEvent.click(screen.getByRole('button', { name: '还原未保存输入' })); expect((locate as HTMLButtonElement).disabled).toBe(false); select(2);
  expect((screen.getByLabelText('对白或叙述') as HTMLTextAreaElement).value).toBe('要移除的作者内容🙂'); expect(writes(fetch)).toHaveLength(0);
});

it.each(['edit', 'navigation', 'entry', 'add-selection', 'cancel', 'save', 'revert'] as const)('invalidates retained removal confirmation in the same batch as %s', async kind => {
  const fetch = backend(); vi.stubGlobal('fetch', fetch); render(<InteractiveStoryPanel client={client()} />); await open();
  fireEvent.change(screen.getByLabelText('对白或叙述'), { target: { value: '未保存🙂' } }); select(2); fireEvent.click(preview()); const oldConfirm = retained(confirm());
  const target = kind === 'edit' ? screen.getByLabelText('对白或叙述') : kind === 'navigation' ? current() : kind === 'entry' ? screen.getByLabelText('故事入口节点') : kind === 'add-selection' ? screen.getByLabelText('待添加原规划节点') : screen.getByRole('button', { name: kind === 'cancel' ? '取消移除节点' : kind === 'save' ? '保存互动草稿' : '还原未保存输入' });
  const action = retained(target, ['edit', 'navigation', 'entry', 'add-selection'].includes(kind) ? 'onChange' : 'onClick');
  act(() => { action({ target: { value: kind === 'edit' ? '刚写入🙂é' : kind === 'navigation' ? '0' : kind === 'entry' ? 'end' : 'other' } }); oldConfirm(); });
  if (kind === 'save') await screen.findByText('互动草稿已保存，需要重新审核。');
  expect(current().options).toHaveLength(3); expect(screen.queryByRole('button', { name: '确认移除所选节点' })).toBeNull();
  if (kind === 'edit') expect((screen.getByLabelText('对白或叙述') as HTMLTextAreaElement).value).toBe('刚写入🙂é');
  expect(writes(fetch)).toHaveLength(kind === 'save' ? 1 : 0);
});

it('rejects both retained preview and confirmation during and after IME composition', async () => {
  const fetch = backend(); vi.stubGlobal('fetch', fetch); render(<InteractiveStoryPanel client={client()} />); await open(); select(2);
  const oldPreview = retained(preview()); fireEvent.click(preview()); const oldConfirm = retained(confirm()); const input = screen.getByLabelText('对白或叙述');
  fireEvent.compositionStart(input); fireEvent.change(input, { target: { value: '输入法🙂é' } }); act(() => { oldPreview(); oldConfirm(); }); expect(preview().disabled).toBe(true);
  fireEvent.compositionEnd(input); act(() => { oldPreview(); oldConfirm(); }); expect(current().options).toHaveLength(3); expect(screen.queryByRole('button', { name: '确认移除所选节点' })).toBeNull();
  expect((input as HTMLTextAreaElement).value).toBe('输入法🙂é'); expect(writes(fetch)).toHaveLength(0);
});

it('retains removed membership and surviving Unicode after save conflict and blocks during the request', async () => {
  let finish!: (response: Response) => void;
  const fetch = backend(story(), catalog(), (_url, init) => init.method === 'PUT' ? new Promise(resolve => { finish = resolve; }) : undefined);
  vi.stubGlobal('fetch', fetch); render(<InteractiveStoryPanel client={client()} />); await open();
  fireEvent.change(screen.getByLabelText('对白或叙述'), { target: { value: '冲突保留🙂é' } }); select(2); fireEvent.click(preview()); const oldConfirm = retained(confirm()); fireEvent.click(confirm());
  const oldPreview = retained(preview()); fireEvent.click(screen.getByRole('button', { name: '保存互动草稿' })); await waitFor(() => expect(writes(fetch)).toHaveLength(1));
  expect(preview().disabled).toBe(true); act(() => { oldConfirm(); oldPreview(); }); finish(reply({ detail: { code: 'EXPERIMENTAL_VERSION_CONFLICT' } }, 409)); await screen.findByText(/EXPERIMENTAL_VERSION_CONFLICT/);
  expect(current().options).toHaveLength(2); select(0); expect((screen.getByLabelText('对白或叙述') as HTMLTextAreaElement).value).toBe('冲突保留🙂é'); expect(writes(fetch)).toHaveLength(1);
});

it.each(['archive', 'stale', 'withheld', 'graph-version', 'member-version', 'duplicate-source', 'duplicate-member'] as const)('fails closed for %s without editing or repinning', async kind => {
  const row = story(), sources = catalog();
  if (kind === 'archive') row.status = 'ARCHIVED'; if (kind === 'stale') row.stale = true; if (kind === 'withheld') row.content_withheld = true;
  if (kind === 'graph-version') sources.graphs[0].version++; if (kind === 'member-version') sources.graphs[0].nodes[2].node_version++;
  if (kind === 'duplicate-source') sources.graphs[0].nodes.push({ ...sources.graphs[0].nodes[2] }); if (kind === 'duplicate-member') row.spec!.nodes.push({ ...row.spec!.nodes[2] });
  vi.spyOn(console, 'error').mockImplementation(() => {});
  const fetch = backend(row, sources); vi.stubGlobal('fetch', fetch); render(<InteractiveStoryPanel client={client()} />); await open();
  if (kind === 'stale' || kind === 'withheld') expect(screen.queryByRole('button', { name: '预览移除当前节点' })).toBeNull();
  else { expect(preview().disabled).toBe(true); act(() => retained(preview())()); expect(screen.queryByRole('button', { name: '确认移除所选节点' })).toBeNull(); }
  expect(writes(fetch)).toHaveLength(0);
});

it('invalidates preview and callbacks across catalog loading, error and A to B to A', async () => {
  let response: Response | Promise<Response> = reply(catalog()), finish!: (response: Response) => void;
  const fetch = backend(story(), catalog(), url => url.endsWith('/catalog') ? response : undefined);
  vi.stubGlobal('fetch', fetch); render(<InteractiveStoryPanel client={client()} />); await open(); select(2); const oldPreview = retained(preview()); fireEvent.click(preview()); const oldConfirm = retained(confirm());
  response = new Promise(resolve => { finish = resolve; }); fireEvent.click(screen.getByRole('button', { name: '刷新可用规划与资产' })); await waitFor(() => expect(preview().disabled).toBe(true));
  act(() => { oldConfirm(); oldPreview(); }); finish(reply({ detail: { code: 'FORBIDDEN' } }, 403)); await screen.findByText(/当前身份没有此操作权限/);
  const changed = catalog(); changed.graphs[0].version++; response = reply(changed); fireEvent.click(screen.getByRole('button', { name: '刷新可用规划与资产' })); await screen.findByText(/原规划版本或节点来源无法精确匹配/);
  response = reply(catalog()); fireEvent.click(screen.getByRole('button', { name: '刷新可用规划与资产' })); await waitFor(() => expect(preview().disabled).toBe(false));
  act(() => { oldConfirm(); oldPreview(); }); expect(current().options).toHaveLength(3); expect(screen.queryByRole('button', { name: '确认移除所选节点' })).toBeNull();
  fireEvent.click(preview()); fireEvent.click(confirm()); expect(current().options).toHaveLength(2); expect(writes(fetch)).toHaveLength(0);
});

it.each(['client', 'scope'] as const)('rejects retained callbacks after %s A to B to A in StrictMode', async kind => {
  const fetch = backend(); vi.stubGlobal('fetch', fetch); const a = client(), b = kind === 'client' ? client('other') : client('novel', 'other-branch');
  const view = render(<StrictMode><InteractiveStoryPanel client={a} /></StrictMode>); await open(); select(2); const oldPreview = retained(preview()); fireEvent.click(preview()); const oldConfirm = retained(confirm());
  view.rerender(<StrictMode><InteractiveStoryPanel client={b} /></StrictMode>); await open(); view.rerender(<StrictMode><InteractiveStoryPanel client={a} /></StrictMode>); await open();
  act(() => { oldConfirm(); oldPreview(); }); expect(current().options).toHaveLength(3); expect(current().value).toBe('0'); expect(screen.queryByRole('button', { name: '确认移除所选节点' })).toBeNull(); expect(writes(fetch)).toHaveLength(0);
});

it.each(['dialogue', 'entry', 'choice', 'save', 'revert', 'navigation'] as const)('rejects retained %s after confirmation in the same batch and after rerender', async kind => {
  const fetch = backend(); vi.stubGlobal('fetch', fetch); render(<InteractiveStoryPanel client={client()} />); await open();
  fireEvent.change(screen.getByLabelText('对白或叙述'), { target: { value: '保留新稿🙂é' } }); select(2); fireEvent.click(preview());
  const oldConfirm = retained(confirm());
  const target = kind === 'dialogue' ? screen.getByLabelText('对白或叙述') : kind === 'entry' ? screen.getByLabelText('故事入口节点') : kind === 'choice' ? screen.getByLabelText('选择 1 文案') : kind === 'navigation' ? current() : screen.getByRole('button', { name: kind === 'save' ? '保存互动草稿' : '还原未保存输入' });
  const oldAction = retained(target, kind === 'save' || kind === 'revert' ? 'onClick' : 'onChange');
  const event = { target: { value: kind === 'navigation' ? '2' : kind === 'entry' ? 'unused' : '过期输入🙂' } };
  act(() => { oldConfirm(); oldAction(event); });
  expect(current().options).toHaveLength(2); expect(current().value).toBe('1'); expect(writes(fetch)).toHaveLength(0);
  act(() => oldAction(event)); expect(current().options).toHaveLength(2); expect(current().value).toBe('1'); expect(writes(fetch)).toHaveLength(0);
  select(0); expect((screen.getByLabelText('对白或叙述') as HTMLTextAreaElement).value).toBe('保留新稿🙂é');
  expect((screen.getByLabelText('故事入口节点') as HTMLSelectElement).value).toBe('gate');
  fireEvent.click(screen.getByRole('button', { name: '保存互动草稿' })); await screen.findByText('互动草稿已保存，需要重新审核。');
  expect(JSON.parse(String(writes(fetch)[0][1].body)).spec.nodes.map((node: { node_id: string }) => node.node_id)).toEqual(['gate', 'end']);
  expect(writes(fetch)).toHaveLength(1);
});

it.each(['start', 'end'] as const)('preserves final Unicode onChange in the same batch as composition %s while rejecting stale removal', async boundary => {
  const fetch = backend(); vi.stubGlobal('fetch', fetch); render(<InteractiveStoryPanel client={client()} />); await open(); select(2);
  fireEvent.click(preview()); const oldConfirm = retained(confirm()), oldPreview = retained(preview());
  const input = screen.getByLabelText('对白或叙述');
  if (boundary === 'end') fireEvent.compositionStart(input);
  const composition = retained(input.closest('fieldset')!, boundary === 'start' ? 'onCompositionStartCapture' : 'onCompositionEndCapture');
  const finalChange = retained(input, 'onChange');
  act(() => { composition(); finalChange({ target: { value: '最终组合文本🙂é汉字' } }); oldConfirm(); oldPreview(); });
  expect((input as HTMLTextAreaElement).value).toBe('最终组合文本🙂é汉字'); expect(current().options).toHaveLength(3);
  expect(screen.queryByRole('button', { name: '确认移除所选节点' })).toBeNull(); expect(writes(fetch)).toHaveLength(0);
  if (boundary === 'start') fireEvent.compositionEnd(input);
  fireEvent.click(screen.getByRole('button', { name: '保存互动草稿' })); await screen.findByText('互动草稿已保存，需要重新审核。');
  expect(JSON.parse(String(writes(fetch)[0][1].body)).spec.nodes[2].dialogue).toBe('最终组合文本🙂é汉字');
});
