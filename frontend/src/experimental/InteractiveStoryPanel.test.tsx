// @vitest-environment jsdom
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

it('authors Unicode choices and typed variables then saves exact original IDs and scope', async () => {
  const fetch = backend(); vi.stubGlobal('fetch', fetch); render(<InteractiveStoryPanel client={client()} />); await select();
  const dialogue = screen.getByLabelText('对白或叙述'); fireEvent.compositionStart(dialogue); fireEvent.change(dialogue, { target: { value: '新对白🙂é' } }); fireEvent.compositionEnd(dialogue);
  expect((screen.getByRole('button', { name: '核对当前互动版本' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText('选择 1 条件'), { target: { value: 'not trusted' } });
  fireEvent.click(screen.getByLabelText('选择后设置 trusted')); fireEvent.change(screen.getByLabelText('选择 1 设置 trusted'), { target: { value: 'false' } });
  fireEvent.click(screen.getByRole('button', { name: '保存互动草稿' })); await screen.findByText('互动草稿已保存，需要重新审核。');
  const request = fetch.mock.calls.find(([, init]) => init.method === 'PUT')!; const body = JSON.parse(String(request[1].body));
  expect(body.expected_version).toBe(1); expect(body.spec.nodes[0].node_id).toBe('gate'); expect(body.spec.nodes[0].dialogue).toBe('新对白🙂é');
  expect(body.spec.nodes[0].choices[0].assignments.trusted).toBe(false); expect(new Headers(request[1].headers).get('X-Branch-Id')).toBe('branch');
  expect(fetch.mock.calls.some(([url]) => /generate|chapters\//.test(url))).toBe(false);
});

it('actually plays server-returned choices to an ending, and resets bounded state', async () => {
  const fetch = backend(); vi.stubGlobal('fetch', fetch); render(<InteractiveStoryPanel client={client()} />); await select();
  fireEvent.click(screen.getByRole('button', { name: '从开头试玩' }));
  fireEvent.click(await screen.findByRole('button', { name: /^回家$/ })); await screen.findByText('结局：回家');
  expect(screen.getByText('1 / 4 步 · ENDING')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '从开头试玩' })); await screen.findByRole('button', { name: /^回家$/ });
  const requests = fetch.mock.calls.filter(([url]) => url.endsWith('/preview'));
  expect(requests.map(([, init]) => JSON.parse(String(init.body)).choices)).toEqual([[], ['home'], []]);
});

it('preserves unsaved draft and beforeunload protection after a CAS conflict', async () => {
  vi.stubGlobal('fetch', backend(makeStory(), (_url, init) => init.method === 'PUT' ? reply({ detail: { code: 'EXPERIMENTAL_VERSION_CONFLICT' } }, 409) : undefined));
  const view = render(<InteractiveStoryPanel client={client()} />); await select();
  fireEvent.change(screen.getByLabelText('对白或叙述'), { target: { value: '必须保留🙂' } });
  const guard = new Event('beforeunload', { cancelable: true }); window.dispatchEvent(guard); expect(guard.defaultPrevented).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '保存互动草稿' })); await screen.findByText(/EXPERIMENTAL_VERSION_CONFLICT/);
  expect((screen.getByLabelText('对白或叙述') as HTMLTextAreaElement).value).toBe('必须保留🙂');
  fireEvent.click(screen.getByRole('button', { name: '还原未保存输入' })); expect((screen.getByLabelText('对白或叙述') as HTMLTextAreaElement).value).toBe('原对白🙂é');
  view.unmount(); const after = new Event('beforeunload', { cancelable: true }); window.dispatchEvent(after); expect(after.defaultPrevented).toBe(false);
});

it('requires exact review preview and drops receipt when edited', async () => {
  const fetch = backend(makeStory('REVIEW')); vi.stubGlobal('fetch', fetch); render(<InteractiveStoryPanel client={client()} />); await select();
  fireEvent.click(screen.getByRole('button', { name: '预览互动审核' })); await screen.findByRole('button', { name: '批准此互动版本' });
  fireEvent.change(screen.getByLabelText('对白或叙述'), { target: { value: 'new' } });
  await waitFor(() => expect(screen.queryByRole('button', { name: '批准此互动版本' })).toBeNull());
  fireEvent.click(screen.getByRole('button', { name: '还原未保存输入' })); fireEvent.click(screen.getByRole('button', { name: '预览互动审核' }));
  fireEvent.click(await screen.findByRole('button', { name: '批准此互动版本' })); await screen.findByText('此版本互动改编已批准。');
  const request = fetch.mock.calls.find(([url]) => url.endsWith('/review'))!; expect(JSON.parse(String(request[1].body)).preview_digest).toBe('a'.repeat(64));
});

it('does not leak late private playback or mutations after a client scope change in StrictMode', async () => {
  let finish: (r: Response) => void = () => {};
  const fetch = backend(makeStory(), (url, init) => url.includes('/other/') ? reply(url.endsWith('/catalog') ? catalog : { items: [] }) : init.method === 'PUT' ? new Promise<Response>(resolve => { finish = resolve; }) : undefined);
  vi.stubGlobal('fetch', fetch); const view = render(<StrictMode><InteractiveStoryPanel client={client()} /></StrictMode>); await select();
  fireEvent.change(screen.getByLabelText('对白或叙述'), { target: { value: 'private old' } }); fireEvent.click(screen.getByRole('button', { name: '保存互动草稿' }));
  await waitFor(() => expect(fetch.mock.calls.some(([, init]) => init.method === 'PUT')).toBe(true));
  view.rerender(<StrictMode><InteractiveStoryPanel client={client('other')} /></StrictMode>); finish(reply(makeStory()));
  await waitFor(() => expect(screen.queryByLabelText('对白或叙述')).toBeNull()); expect(screen.queryByDisplayValue('private old')).toBeNull();
});

it('withholds stale content and identifies recovery rather than permitting preview', async () => {
  const row = { ...makeStory(), stale: true, content_withheld: true, spec: undefined, analysis: undefined };
  vi.stubGlobal('fetch', backend(row)); render(<InteractiveStoryPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: /来源变化的互动改编 · v/ }));
  expect(screen.queryByLabelText('对白或叙述')).toBeNull(); expect(screen.queryByRole('button', { name: '从开头试玩' })).toBeNull();
  expect(screen.getByText(/旧内容已停止展示和导出/)).toBeTruthy();
});

it('requires explicit loss acknowledgment before ZIP generation and revokes object URL', async () => {
  const createObjectURL = vi.fn(() => 'blob:story'), revokeObjectURL = vi.fn();
  vi.stubGlobal('URL', class extends URL { static createObjectURL = createObjectURL; static revokeObjectURL = revokeObjectURL; });
  const fetch = backend(makeStory('APPROVED'), url => url.endsWith('/export-preview') ? reply({ preview_digest: 'b'.repeat(64), can_export: true, losses: ['MEDIA_REFERENCES_NOT_EMBEDDED_OR_PLAYED'], media_manifest: [], target_runtime: 'NOT_RUN', analysis }) : url.endsWith('/export') ? reply({ filename: 'interactive-story.zip', mime: 'application/zip', content_base64: btoa('synthetic zip response') }) : undefined);
  vi.stubGlobal('fetch', fetch); const view = render(<InteractiveStoryPanel client={client()} />); await select();
  fireEvent.click(screen.getByRole('button', { name: '预检互动导出' }));
  const generate = await screen.findByRole('button', { name: '生成互动故事包' }); expect((generate as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('已核对缺失项与兼容性损失，确认生成独立下载')); fireEvent.click(generate);
  expect((await screen.findByRole('link', { name: '下载 interactive-story.zip' })).getAttribute('href')).toBe('blob:story');
  expect(JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/export'))![1].body)).preview_digest).toBe('b'.repeat(64));
  view.unmount(); expect(revokeObjectURL).toHaveBeenCalledWith('blob:story');
});

it('empty and permission error states do not start a model or allow creation', async () => {
  const fetch = vi.fn(async (url: string) => reply(url.endsWith('/catalog') ? { detail: { code: 'FORBIDDEN' } } : { items: [] }, url.endsWith('/catalog') ? 403 : 200));
  vi.stubGlobal('fetch', fetch); render(<InteractiveStoryPanel client={client()} />); await screen.findByText(/FORBIDDEN/); await screen.findByText('暂无记录');
  expect((screen.getByRole('button', { name: '创建互动改编' }) as HTMLButtonElement).disabled).toBe(true);
});

it('explicit source rebind requires a current preview, then restores text only as draft', async () => {
  const stale = { ...makeStory(), stale: true, content_withheld: true, spec: undefined, analysis: undefined };
  const fetch = backend(stale, url => url.endsWith('/refresh-preview') ? reply({ preview_digest: 'c'.repeat(64), retained_nodes: 2, changed_source_count: 1 }) : url.endsWith('/refresh') ? reply(makeStory()) : undefined);
  vi.stubGlobal('fetch', fetch); render(<InteractiveStoryPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: /来源变化的互动改编 · v/ }));
  expect(screen.queryByRole('button', { name: '确认重绑定并重新审核' })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '预览互动来源重绑定' }));
  fireEvent.click(await screen.findByRole('button', { name: '确认重绑定并重新审核' }));
  await screen.findByLabelText('对白或叙述'); expect((screen.getByRole('button', { name: '预检互动导出' }) as HTMLButtonElement).disabled).toBe(true);
  expect(JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/refresh'))![1].body)).preview_digest).toBe('c'.repeat(64));
});

it('duplicate preview clicks dispatch once and late playback cannot cross records', async () => {
  let finish: (response: Response) => void = () => {};
  const fetch = backend(makeStory(), (url, init) => url.endsWith('/preview') && init.method === 'POST' ? new Promise<Response>(resolve => { finish = resolve; }) : url.includes('/other/') ? reply(url.endsWith('/catalog') ? catalog : { items: [] }) : undefined);
  vi.stubGlobal('fetch', fetch); const view = render(<InteractiveStoryPanel client={client()} />); await select();
  const button = screen.getByRole('button', { name: '从开头试玩' }); fireEvent.click(button); fireEvent.click(button);
  await waitFor(() => expect(fetch.mock.calls.filter(([url]) => url.endsWith('/preview')).length).toBe(1));
  view.rerender(<InteractiveStoryPanel client={client('other')} />);
  finish(reply({ node: makeStory().spec!.nodes[0], character_name: 'Private late name', choices: [], variables: {}, steps: 0, max_steps: 4, path: [], status: 'PLAYING' }));
  await waitFor(() => expect(screen.queryByLabelText('互动故事播放')).toBeNull()); expect(screen.queryByText('Private late name')).toBeNull();
});

it('creates using selected planning IDs in selection order rather than storage object order', async () => {
  const reversed = { ...catalog, graphs: [{ ...catalog.graphs[0], nodes: [...catalog.graphs[0].nodes].reverse() }] };
  const fetch = backend(makeStory(), url => url.endsWith('/catalog') ? reply(reversed) : undefined);
  vi.stubGlobal('fetch', fetch); render(<InteractiveStoryPanel client={client()} />);
  await screen.findByRole('button', { name: /合成互动故事 · v/ });
  fireEvent.change(screen.getByLabelText('互动故事名称'), { target: { value: 'New' } });
  fireEvent.change(screen.getByLabelText('原规划图'), { target: { value: 'graph' } });
  fireEvent.click(screen.getByLabelText('城门')); fireEvent.click(screen.getByLabelText('终章'));
  fireEvent.click(screen.getByRole('button', { name: '创建互动改编' }));
  await waitFor(() => expect(fetch.mock.calls.some(([url, init]) => url.endsWith('/interactive-stories') && init.method === 'POST')).toBe(true));
  const request = fetch.mock.calls.find(([url, init]) => url.endsWith('/interactive-stories') && init.method === 'POST')!;
  const spec = JSON.parse(String(request[1].body)).spec; expect(spec.entry_node_id).toBe('gate'); expect(spec.nodes.map((n: any) => n.node_id)).toEqual(['gate', 'end']);
});
