// @vitest-environment jsdom
// Extracted additions and migrated variants; protected baseline suite stays byte-identical.
// Migrated variants preserve newer assertions and are not counted as unique new capabilities.
import { StrictMode } from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { experimentalClient } from './api';
import { InteractiveStoryPanel } from './InteractiveStoryPanel';
import type { InteractiveStory, StoryCatalog, StoryPlay } from './interactiveStoryClient';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
const client = (id = 'n') => experimentalClient(id, { sessionToken: 'session', scope: { branchId: 'branch' } as any });
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
const analysis = { issues: [], warnings: [], endings: [{ node_id: 'end', ending: '回家', choices: ['home'] }], states_checked: 2, analysis_complete: true, state_limit_reached: false, step_limit_reached: false, max_steps: 4, can_review: true };
function makeStory(status: InteractiveStory['status'] = 'DRAFT'): InteractiveStory {
  return { id: 'story', version: 1, status, stale: false, content_withheld: false, analysis, spec: { title: '合成互动故事', graph_id: 'graph', graph_version: 1, entry_node_id: 'gate', max_steps: 4, variables: [{ name: 'trusted', type: 'bool', initial: true, minimum: 0, maximum: 100 }], graph_record_ids: [], nodes: [
    { node_id: 'gate', node_version: 1, title: '城门', dialogue: '原对白🙂é', character_id: 'alice', background_asset_id: null, music_asset_id: null, ending: '', choices: [{ id: 'home', label: '回家', target: 'end', condition: 'trusted', assignments: {} }] },
    { node_id: 'end', node_version: 1, title: '终章', dialogue: '抵达', character_id: null, background_asset_id: null, music_asset_id: null, ending: '回家', choices: [] },
  ] } };
}
const catalog: StoryCatalog = { graphs: [{ id: 'graph', version: 1, title: '原规划图', truncated: false, nodes: makeStory().spec!.nodes }], characters: [{ id: 'alice', name: 'Alice' }], assets: [], graph_records: [], target_runtime: 'NOT_RUN' };
function backend(row = makeStory(), handler?: (url: string, init: RequestInit) => Response | Promise<Response> | undefined) {
  return vi.fn(async (url: string, init: RequestInit) => {
    const special = await handler?.(url, init); if (special) return special;
    if (url.endsWith('/catalog')) return reply(catalog);
    if (init.method === 'GET') return reply(url.endsWith('/story') ? row : { items: [row], truncated: false });
    const body = JSON.parse(String(init.body));
    if (init.method === 'PUT') { row = { ...row, version: row.version + 1, spec: body.spec, status: 'DRAFT' }; return reply(row); }
    if (url.endsWith('/review-preview')) return reply({ preview_digest: 'a'.repeat(64), can_approve: true, analysis });
    if (url.endsWith('/review')) { row = { ...row, version: row.version + 1, status: body.action === 'submit' ? 'REVIEW' : body.action === 'approve' ? 'APPROVED' : 'DRAFT' }; return reply(row); }
    if (url.endsWith('/preview')) {
      const node = row.spec!.nodes[body.choices.length ? 1 : 0]; const play: StoryPlay = { node, choices: body.choices.length ? [] : [{ id: 'home', label: '回家', enabled: true }], variables: { trusted: true }, steps: body.choices.length, max_steps: 4, path: body.choices, status: body.choices.length ? 'ENDING' : 'PLAYING' }; return reply(play);
    }
    return reply(row);
  });
}
async function select() { fireEvent.click(await screen.findByRole('button', { name: /合成互动故事 · v/ })); }

it('locates exact saved issues in the original dirty editor without writing or discarding Unicode input', async () => {
  const row = makeStory(); row.spec!.nodes[1].title = row.spec!.nodes[0].title;
  row.analysis = { ...analysis, issues: [{ code: 'CONDITION_TYPE_MISMATCH', node_id: 'gate', choice_id: 'home' }, { code: 'NO_EXIT', node_id: 'end' }], warnings: [{ code: 'CYCLE_STEP_CAP_REQUIRED', node_id: 'gate' }], can_review: false };
  const fetch = backend(row); vi.stubGlobal('fetch', fetch); render(<InteractiveStoryPanel client={client()} />); await select();
  fireEvent.change(screen.getByLabelText('对白或叙述'), { target: { value: '保留新稿🙂é' } });
  fireEvent.click(screen.getByRole('button', { name: '定位 NO_EXIT 节点 end' }));
  expect((screen.getByLabelText('当前编辑节点') as HTMLSelectElement).value).toBe('1');
  expect(document.activeElement).toBe(screen.getByLabelText('互动节点标题'));
  fireEvent.click(screen.getByRole('button', { name: '定位 CONDITION_TYPE_MISMATCH 节点 gate 选择 home' }));
  expect(document.activeElement).toBe(screen.getByLabelText('选择 1 条件'));
  expect((screen.getByLabelText('对白或叙述') as HTMLTextAreaElement).value).toBe('保留新稿🙂é');
  expect(screen.getByText(/以下是已保存版本的检查结果/)).toBeTruthy();
  expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
  fireEvent.change(screen.getByLabelText('选择 1 条件'), { target: { value: 'not trusted' } });
  fireEvent.click(screen.getByRole('button', { name: '保存互动草稿' })); await screen.findByText('互动草稿已保存，需要重新审核。');
  const body = JSON.parse(String(fetch.mock.calls.find(([, init]) => init.method === 'PUT')![1].body));
  expect(body.expected_version).toBe(1); expect(body.spec.nodes[0].dialogue).toBe('保留新稿🙂é');
  expect(body.spec.nodes[0].choices[0].condition).toBe('not trusted'); expect(body.spec.graph_version).toBe(1);
});

it('keeps missing, removed-choice and node-less issues non-navigable with no guessed target', async () => {
  const row = makeStory(); row.analysis = { ...analysis, issues: [{ code: 'UNDEFINED_VARIABLE', node_id: 'gate', choice_id: 'home' }, { code: 'NO_EXIT', node_id: 'missing' }, { code: 'NO_REACHABLE_ENDING_WITHIN_CAP' }], warnings: [] };
  const fetch = backend(row); vi.stubGlobal('fetch', fetch); render(<InteractiveStoryPanel client={client()} />); await select();
  expect((screen.getByRole('button', { name: '定位 NO_EXIT 节点 missing' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '移除选择 1' }));
  expect((screen.getByRole('button', { name: '定位 UNDEFINED_VARIABLE 节点 gate 选择 home' }) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.queryByRole('button', { name: /定位 NO_REACHABLE_ENDING/ })).toBeNull();
  expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
});

it('bounds issue navigation to twenty rows and keeps archived drafts read-only', async () => {
  const row = makeStory('ARCHIVED'); row.analysis = { ...analysis, issues: Array.from({ length: 41 }, (_, i) => ({ code: `ISSUE_${i}`, node_id: 'gate' })), warnings: [] };
  vi.stubGlobal('fetch', backend(row)); render(<InteractiveStoryPanel client={client()} />); await select();
  expect(screen.getAllByRole('button', { name: /^定位 ISSUE_/ })).toHaveLength(20);
  expect(screen.getAllByRole('button', { name: /^定位 ISSUE_/ }).every(b => (b as HTMLButtonElement).disabled)).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '下一页路径问题' })); expect(screen.getByText('路径问题第 2 / 3 页')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '下一页路径问题' })); expect(screen.getAllByRole('button', { name: /^定位 ISSUE_/ })).toHaveLength(1);
});

it('rejects ambiguous node IDs and isolates issue navigation after switching the client', async () => {
  const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
  const row = makeStory(); row.spec!.nodes[1].node_id = 'gate'; row.analysis = { ...analysis, issues: [{ code: 'NO_EXIT', node_id: 'gate' }] };
  vi.stubGlobal('fetch', backend(row, url => url.includes('/other/') ? reply(url.endsWith('/catalog') ? catalog : { items: [] }) : undefined));
  const view = render(<StrictMode><InteractiveStoryPanel client={client()} /></StrictMode>); await select();
  expect((screen.getByRole('button', { name: '定位 NO_EXIT 节点 gate' }) as HTMLButtonElement).disabled).toBe(true);
  view.rerender(<StrictMode><InteractiveStoryPanel client={client('other')} /></StrictMode>);
  expect(screen.queryByRole('button', { name: '定位 NO_EXIT 节点 gate' })).toBeNull();
  expect(consoleError.mock.calls.every(([message]) => String(message).includes('same key'))).toBe(true);
});

it('blocks issue navigation during an original save, then preserves the exact draft after conflict', async () => {
  let finish: (response: Response) => void = () => {};
  const row = makeStory(); row.analysis = { ...analysis, issues: [{ code: 'NO_EXIT', node_id: 'end' }] };
  const fetch = backend(row, (_url, init) => init.method === 'PUT' ? new Promise<Response>(resolve => { finish = resolve; }) : undefined);
  vi.stubGlobal('fetch', fetch); render(<InteractiveStoryPanel client={client()} />); await select();
  fireEvent.change(screen.getByLabelText('对白或叙述'), { target: { value: '冲突也保留🙂' } });
  fireEvent.click(screen.getByRole('button', { name: '保存互动草稿' }));
  await waitFor(() => expect(fetch.mock.calls.some(([, init]) => init.method === 'PUT')).toBe(true));
  const button = screen.getByRole('button', { name: '定位 NO_EXIT 节点 end' });
  expect((button as HTMLButtonElement).disabled).toBe(true); fireEvent.click(button);
  expect((screen.getByLabelText('当前编辑节点') as HTMLSelectElement).value).toBe('0');
  finish(reply({ detail: { code: 'EXPERIMENTAL_VERSION_CONFLICT' } }, 409)); await screen.findByText(/EXPERIMENTAL_VERSION_CONFLICT/);
  fireEvent.click(screen.getByRole('button', { name: '定位 NO_EXIT 节点 end' }));
  expect((screen.getByLabelText('当前编辑节点') as HTMLSelectElement).value).toBe('1');
  fireEvent.change(screen.getByLabelText('当前编辑节点'), { target: { value: '0' } });
  expect((screen.getByLabelText('对白或叙述') as HTMLTextAreaElement).value).toBe('冲突也保留🙂');
  expect(fetch.mock.calls.filter(([, init]) => init.method !== 'GET')).toHaveLength(1);
});

it('keeps the composing source node and Unicode draft until IME composition finishes', async () => {
  const row = makeStory(); row.analysis = { ...analysis, issues: [{ code: 'NO_EXIT', node_id: 'end' }] };
  const fetch = backend(row); vi.stubGlobal('fetch', fetch); render(<InteractiveStoryPanel client={client()} />); await select();
  const dialogue = screen.getByLabelText('对白或叙述');
  fireEvent.compositionStart(dialogue); fireEvent.change(dialogue, { target: { value: '正在输入🙂é' } });
  const locate = screen.getByRole('button', { name: '定位 NO_EXIT 节点 end' });
  expect((locate as HTMLButtonElement).disabled).toBe(true); fireEvent.click(locate);
  expect((screen.getByLabelText('当前编辑节点') as HTMLSelectElement).value).toBe('0');
  fireEvent.compositionEnd(dialogue); fireEvent.click(locate);
  expect((screen.getByLabelText('当前编辑节点') as HTMLSelectElement).value).toBe('1');
  fireEvent.change(screen.getByLabelText('当前编辑节点'), { target: { value: '0' } });
  expect((screen.getByLabelText('对白或叙述') as HTMLTextAreaElement).value).toBe('正在输入🙂é');
  expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
});

it('rejects malformed supplied choice references and never resolves a choice in another node', async () => {
  const row = makeStory(); row.analysis = { ...analysis, issues: [
    { code: 'EMPTY_CHOICE', node_id: 'gate', choice_id: '' },
    { code: 'NULL_CHOICE', node_id: 'gate', choice_id: null as any },
    { code: 'NUMBER_CHOICE', node_id: 'gate', choice_id: 0 as any },
    { code: 'WRONG_PARENT', node_id: 'end', choice_id: 'home' },
  ] };
  const fetch = backend(row); vi.stubGlobal('fetch', fetch); render(<InteractiveStoryPanel client={client()} />); await select();
  expect(screen.getAllByRole('button', { name: /^定位 / }).every(button => (button as HTMLButtonElement).disabled)).toBe(true);
  expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
});

it('rejects duplicate choice IDs instead of focusing an arbitrary control', async () => {
  const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
  const row = makeStory(); row.spec!.nodes[0].choices.push({ ...row.spec!.nodes[0].choices[0] });
  row.analysis = { ...analysis, issues: [{ code: 'DUPLICATE_CHOICE', node_id: 'gate', choice_id: 'home' }] };
  vi.stubGlobal('fetch', backend(row)); render(<InteractiveStoryPanel client={client()} />); await select();
  expect((screen.getByRole('button', { name: '定位 DUPLICATE_CHOICE 节点 gate 选择 home' }) as HTMLButtonElement).disabled).toBe(true);
  expect(consoleError.mock.calls.every(([message]) => String(message).includes('same key'))).toBe(true);
});

it('resets issue paging on a new saved version and locates by ID after node order changes', async () => {
  const row = makeStory(); row.analysis = { ...analysis, issues: Array.from({ length: 21 }, (_, i) => ({ code: `OLD_${i}`, node_id: 'gate' })) };
  const next = makeStory(); next.version = 2; next.spec!.nodes.reverse(); next.analysis = { ...analysis, issues: [{ code: 'CURRENT', node_id: 'gate', choice_id: 'home' }] };
  vi.stubGlobal('fetch', backend(row, (url, init) => url.endsWith('/story') && init.method === 'GET' ? reply(next) : undefined));
  render(<InteractiveStoryPanel client={client()} />); await select();
  fireEvent.click(screen.getByRole('button', { name: '下一页路径问题' }));
  fireEvent.click(screen.getByRole('button', { name: '核对当前互动版本' }));
  const locate = await screen.findByRole('button', { name: '定位 CURRENT 节点 gate 选择 home' });
  expect(screen.queryByText('路径问题第 2 / 2 页')).toBeNull(); fireEvent.click(locate);
  expect((screen.getByLabelText('当前编辑节点') as HTMLSelectElement).value).toBe('1');
  expect(document.activeElement).toBe(screen.getByLabelText('选择 1 条件'));
});

it('does not restore old issue navigation after client A to B to A and a delayed version read', async () => {
  let finish: (response: Response) => void = () => {};
  const old = makeStory(); old.analysis = { ...analysis, issues: [{ code: 'OLD_PRIVATE', node_id: 'gate' }] };
  const next = makeStory(); next.version = 2; next.analysis = { ...analysis, issues: [{ code: 'CURRENT', node_id: 'end' }] };
  let listing = old;
  const fetch = backend(old, (url, init) => {
    if (url.includes('/other/')) return reply(url.endsWith('/catalog') ? catalog : { items: [] });
    if (url.endsWith('/story') && init.method === 'GET') return new Promise<Response>(resolve => { finish = resolve; });
    if (url.endsWith('/interactive-stories') && init.method === 'GET') return reply({ items: [listing] });
  });
  vi.stubGlobal('fetch', fetch); const a = client(), b = client('other');
  const view = render(<StrictMode><InteractiveStoryPanel client={a} /></StrictMode>); await select();
  fireEvent.click(screen.getByRole('button', { name: '核对当前互动版本' }));
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.endsWith('/story'))).toBe(true));
  view.rerender(<StrictMode><InteractiveStoryPanel client={b} /></StrictMode>); listing = next;
  view.rerender(<StrictMode><InteractiveStoryPanel client={a} /></StrictMode>); await select();
  finish(reply(old));
  await waitFor(() => expect(screen.queryByRole('button', { name: /定位 OLD_PRIVATE/ })).toBeNull());
  fireEvent.click(screen.getByRole('button', { name: '定位 CURRENT 节点 end' }));
  expect((screen.getByLabelText('当前编辑节点') as HTMLSelectElement).value).toBe('1');
});

it('does not retarget a saved issue to a replacement choice with a reused ID before save', async () => {
  const row = makeStory(); row.spec!.nodes[0].choices[0].id = 'choice_1';
  row.analysis = { ...analysis, issues: [{ code: 'UNDEFINED_VARIABLE', node_id: 'gate', choice_id: 'choice_1' }] };
  const fetch = backend(row); vi.stubGlobal('fetch', fetch); render(<InteractiveStoryPanel client={client()} />); await select();
  const locate = () => screen.getByRole('button', { name: '定位 UNDEFINED_VARIABLE 节点 gate 选择 choice_1' }) as HTMLButtonElement;
  expect(locate().disabled).toBe(false);
  fireEvent.click(screen.getByRole('button', { name: '移除选择 1' })); fireEvent.click(screen.getByRole('button', { name: '添加互动选择' }));
  expect((screen.getByLabelText('选择 1 文案') as HTMLInputElement).value).toBe('选择 1');
  expect(locate().disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '还原未保存输入' }));
  expect(locate().disabled).toBe(false); expect((screen.getByLabelText('选择 1 文案') as HTMLInputElement).value).toBe('回家');
  expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
});
