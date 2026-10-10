// @vitest-environment jsdom
import { useEffect, useState } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CreativeWorkspace, type CreativeWorkspaceProps } from './CreativeWorkspace';
import { newDocument, newScene, newShot, type CreativeDocument, type CreativeCapabilities } from './types';

const caps: CreativeCapabilities = { enabled: true, can_mutate: true, modes: ['SCREENPLAY', 'DIRECTOR', 'STORYBOARD', 'PRODUCTION'] };
function saved(patch: Partial<CreativeDocument> = {}): CreativeDocument {
  return { ...newDocument('SCREENPLAY', 'chapter-1'), id: 'doc-original', title: 'Saved screenplay', version: 7, status: 'DRAFT', actor_id: 'actor-1', created_at: '2026-10-09T00:00:00Z', updated_at: '2026-10-09T00:00:00Z', source_evidence: {}, scenes: [{ ...newScene(1, 'chapter-1'), id: 'scene-1', heading: 'Harbor', action: 'Original scene action' }], ...patch };
}
function props(patch: Partial<CreativeWorkspaceProps> = {}): CreativeWorkspaceProps {
  return { enabled: true, novelId: 'novel-1', context: { sessionToken: 'session-original', actor: { id: 'actor-1', displayName: 'Author', workspaceId: 'w' }, scope: { workspaceId: 'w', projectId: 'p', storylineId: 's', branchId: 'branch-original' } }, scope: { workspace: 'Workspace', project: 'Novel', storyline: 'Story', branch: 'Main' }, actor: 'Author', chapter: { id: 'chapter-1', novel_id: 'novel-1', title: 'Original chapter', content: 'Manuscript', document: {}, number: 1, version: 3, word_count: 1, status: 'DRAFT' }, chapterCount: 1, manuscriptReady: true, novelMain: <div>Original manuscript editor</div>, novelSidebar: <div>Original chapter tree</div>, novelInspector: <div>Original manuscript inspector</div>, novelStatus: <span>Manuscript saved</span>, onExit: vi.fn(), onModuleChange: vi.fn(), ...patch };
}
function response(body: unknown, status = 200) { return { ok: status >= 200 && status < 300, status, json: async () => body }; }
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(done => { resolve = done; }); return { promise, resolve }; }
type Handler = (url: string, init: RequestInit) => unknown | Promise<unknown>;
let fetchMock: ReturnType<typeof vi.fn>;
function server(options: { documents?: CreativeDocument[]; capabilities?: CreativeCapabilities; override?: Handler } = {}) {
  fetchMock = vi.fn(async (url: string, init: RequestInit = {}) => {
    const result = options.override?.(url, init); if (result !== undefined) return await result;
    if (url.endsWith('/capabilities')) return response(options.capabilities || caps);
    if (url.endsWith('/documents') && init.method === 'GET') return response({ items: options.documents || [] });
    if (url.endsWith('/creation-reference-data')) return response({ characters: [], locations: [], story_routes: [] });
    if (url.endsWith('/assets')) return response([]);
    if (url.endsWith('/director-proposals') || url.endsWith('/model-routes')) return response({ items: [] });
    if (url.endsWith('/local-ai/environment')) return response({ code: 'UNAVAILABLE' }, 404);
    throw new Error(`Unexpected request ${init.method} ${url}`);
  });
  vi.stubGlobal('fetch', fetchMock); return fetchMock;
}
const mutations = () => fetchMock.mock.calls.filter(([, init]) => init.method && init.method !== 'GET');
const tab = (name: RegExp) => within(screen.getByRole('tablist', { name: '创作模式' })).getByRole('tab', { name });
async function ready() { await waitFor(() => expect(screen.queryByText('正在核对创作文档与权限…')).toBeNull()); }
async function screenplay() { await ready(); fireEvent.click(tab(/Screenplay/)); await screen.findByLabelText('文档标题'); }
beforeEach(() => { server(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('creative workspace protected manuscript and request boundaries', () => {
  it('performs no reads or writes while the client feature is disabled', () => {
    render(<CreativeWorkspace {...props({ enabled: false })} />);
    expect(screen.getByText('V2 创作工作台未启用')).toBeTruthy(); expect(fetchMock).not.toHaveBeenCalled();
  });
  it('stops at capability discovery when the server feature is disabled', async () => {
    server({ capabilities: { ...caps, enabled: false, modes: [] } }); render(<CreativeWorkspace {...props()} />); await ready();
    expect(screen.getByText('服务端尚未启用创作 V2')).toBeTruthy(); expect(fetchMock).toHaveBeenCalledTimes(1); expect(mutations()).toHaveLength(0);
  });
  it.each([
    ['SCREENPLAY', /Screenplay/], ['PRODUCTION', /Production/], ['VIDEO_PLANNING', /Production/],
  ] as const)('recovers saved %s when its stage is selected before the initial reads finish', async (mode, stage) => {
    const permission = deferred<ReturnType<typeof response>>(), listing = deferred<ReturnType<typeof response>>();
    const document = saved({ ...newDocument(mode, 'chapter-1'), title: `Recovered ${mode}`, version: 3 });
    if (document.video_plan) document.video_plan.notes = 'Saved production plan, not an empty replacement';
    server({ override: (url, init) => {
      if (url.endsWith('/capabilities')) return permission.promise;
      if (url.endsWith('/documents') && init.method === 'GET') return listing.promise;
      if (init.method === 'PUT') return response({ ...document, ...JSON.parse(String(init.body)), version: 4 });
    } });
    render(<CreativeWorkspace {...props()} />);
    const allowed = { ...caps, modes: [...caps.modes, 'VIDEO_PLANNING'] };
    if (mode === 'PRODUCTION') await act(async () => permission.resolve(response(allowed)));
    fireEvent.click(tab(stage));
    expect(tab(stage).getAttribute('aria-selected')).toBe('true');
    expect(screen.queryByLabelText('文档标题')).toBeNull();
    if (mode !== 'PRODUCTION') await act(async () => permission.resolve(response(allowed)));
    expect(screen.queryByLabelText('文档标题')).toBeNull();
    await act(async () => listing.resolve(response({ items: [document] })));
    expect((screen.getByLabelText('文档标题') as HTMLInputElement).value).toBe(document.title);
    expect(screen.getByText('已保存 · v3')).toBeTruthy();
    if (document.video_plan) expect((screen.getByLabelText('制作备注') as HTMLTextAreaElement).value).toBe(document.video_plan.notes);
    expect(mutations()).toHaveLength(0);
    fireEvent.change(screen.getByLabelText('文档标题'), { target: { value: 'Edit recovered document' } });
    fireEvent.click(screen.getByRole('button', { name: '保存草稿' }));
    await screen.findByText('已保存“Edit recovered document” · v4');
    expect(mutations()).toHaveLength(1);
    expect(mutations()[0][0]).toContain(`/documents/${document.id}`);
    expect(mutations()[0][1].method).toBe('PUT');
    expect(JSON.parse(mutations()[0][1].body)).toMatchObject({ mode, expected_version: 3 });
  });
  it('initializes only the latest selected stage after a delayed successful empty list', async () => {
    const listing = deferred<ReturnType<typeof response>>();
    server({ override: (url, init) => url.endsWith('/documents') && init.method === 'GET' ? listing.promise : undefined });
    render(<CreativeWorkspace {...props()} />);
    fireEvent.click(tab(/Screenplay/)); fireEvent.click(tab(/Production/)); fireEvent.click(tab(/Director/));
    expect(screen.queryByLabelText('文档标题')).toBeNull();
    await act(async () => listing.resolve(response({ items: [] })));
    expect(tab(/Director/).getAttribute('aria-selected')).toBe('true');
    expect((screen.getByLabelText('文档标题') as HTMLInputElement).value).toBe('');
    expect(screen.getByText('新草稿')).toBeTruthy();
    fireEvent.change(screen.getByLabelText('文档标题'), { target: { value: 'Manual director draft' } });
    fireEvent.click(tab(/Screenplay/)); fireEvent.click(tab(/Director/));
    expect((screen.getByLabelText('文档标题') as HTMLInputElement).value).toBe('Manual director draft');
    expect(mutations()).toHaveLength(0);
  });
  it('keeps an explicit new document, including an untouched draft, across stage and source changes', async () => {
    server({ documents: [saved()] });
    const original = props(), view = render(<CreativeWorkspace {...original} />); await screenplay();
    fireEvent.click(screen.getByRole('button', { name: '新建文档' }));
    fireEvent.click(tab(/Production/)); fireEvent.click(tab(/Screenplay/));
    view.rerender(<CreativeWorkspace {...original} chapter={{ ...original.chapter!, id: 'chapter-2' }} />);
    expect((screen.getByLabelText('文档标题') as HTMLInputElement).value).toBe('');
    expect(screen.getByText('新草稿')).toBeTruthy();
    fireEvent.change(screen.getByLabelText('文档标题'), { target: { value: 'Intentional new draft' } });
    fireEvent.click(tab(/Novel/)); fireEvent.click(tab(/Screenplay/));
    expect((screen.getByLabelText('文档标题') as HTMLInputElement).value).toBe('Intentional new draft');
    expect(mutations()).toHaveLength(0);
  });
  it('does not treat a failed list read as an empty project and recovers on explicit retry', async () => {
    let reads = 0;
    server({ override: (url, init) => url.endsWith('/documents') && init.method === 'GET' ? ++reads === 1 ? response({ code: 'SERVER_ERROR' }, 500) : response({ items: [saved()] }) : undefined });
    render(<CreativeWorkspace {...props()} />); fireEvent.click(tab(/Screenplay/)); await ready();
    expect(screen.queryByLabelText('文档标题')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '重试读取工作台' }));
    await screen.findByLabelText('文档标题');
    expect((screen.getByLabelText('文档标题') as HTMLInputElement).value).toBe('Saved screenplay');
    expect(reads).toBe(2); expect(mutations()).toHaveLength(0);
  });
  it('reloads saved content after confirmed discard and immediate workbench reopen', async () => {
    const listing = deferred<ReturnType<typeof response>>(); let reads = 0;
    server({ documents: [saved()], override: (url, init) => url.endsWith('/documents') && init.method === 'GET' && ++reads > 1 ? listing.promise : undefined });
    function Route() {
      const [open, setOpen] = useState(true);
      return open ? <CreativeWorkspace {...props({ onExit: () => setOpen(false) })} /> : <button onClick={() => setOpen(true)}>Reopen workspace</button>;
    }
    render(<Route />); await screenplay();
    fireEvent.change(screen.getByLabelText('文档标题'), { target: { value: 'Discard this edit only' } });
    fireEvent.click(screen.getByRole('button', { name: '返回经典工作区' }));
    fireEvent.click(screen.getByRole('button', { name: '继续编辑' }));
    expect((screen.getByLabelText('文档标题') as HTMLInputElement).value).toBe('Discard this edit only');
    fireEvent.click(screen.getByRole('button', { name: '返回经典工作区' }));
    fireEvent.click(screen.getByLabelText('确认放弃未保存草稿并离开'));
    fireEvent.click(screen.getByRole('button', { name: '确认离开' }));
    fireEvent.click(screen.getByRole('button', { name: 'Reopen workspace' })); fireEvent.click(tab(/Screenplay/));
    expect(screen.queryByLabelText('文档标题')).toBeNull();
    await act(async () => listing.resolve(response({ items: [saved()] })));
    expect((screen.getByLabelText('文档标题') as HTMLInputElement).value).toBe('Saved screenplay');
    expect((screen.getByLabelText('动作与叙事') as HTMLTextAreaElement).value).toBe('Original scene action');
    expect(screen.getByText('已保存 · v7')).toBeTruthy(); expect(mutations()).toHaveLength(0);
  });
  it('does not replace a blocked dirty draft when a recovery reread discovers its uncertain creation', async () => {
    let reads = 0;
    server({ override: (url, init) => {
      if (url.endsWith('/documents') && init.method === 'GET') return response({ items: ++reads > 1 ? [saved({ title: 'Server accepted title', version: 1 })] : [] });
      if (init.method === 'POST') return response({ code: 'SERVER_ERROR' }, 500);
    } });
    render(<CreativeWorkspace {...props()} />); await screenplay();
    fireEvent.change(screen.getByLabelText('文档标题'), { target: { value: 'Keep uncertain local draft' } });
    fireEvent.click(screen.getByRole('button', { name: '保存草稿' })); await screen.findByText('需要核对版本 · 本地草稿仍保留');
    fireEvent.click(screen.getByRole('button', { name: '核对服务端版本' })); await ready();
    expect(screen.getByRole('button', { name: /Server accepted title/ })).toBeTruthy();
    fireEvent.click(tab(/Production/)); fireEvent.click(tab(/Screenplay/));
    expect((screen.getByLabelText('文档标题') as HTMLInputElement).value).toBe('Keep uncertain local draft');
    expect(screen.getByLabelText('文档标题').closest('fieldset')!.disabled).toBe(true);
    expect(screen.getByText('需要核对版本 · 本地草稿仍保留')).toBeTruthy(); expect(mutations()).toHaveLength(1);
  });
  it('initializes the new scope only when its list succeeds and ignores the old pending list', async () => {
    const oldList = deferred<ReturnType<typeof response>>(), newList = deferred<ReturnType<typeof response>>();
    server({ override: (url, init) => url.endsWith('/documents') && init.method === 'GET' ? (init.headers as Record<string, string>)['X-Branch-Id'] === 'branch-original' ? oldList.promise : newList.promise : undefined });
    const original = props(), view = render(<CreativeWorkspace {...original} />); fireEvent.click(tab(/Screenplay/));
    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => url.endsWith('/documents'))).toBe(true));
    view.rerender(<CreativeWorkspace {...original} context={{ ...original.context, scope: { ...original.context.scope!, branchId: 'branch-new' } }} />);
    fireEvent.click(tab(/Screenplay/));
    await act(async () => oldList.resolve(response({ items: [saved({ title: 'Old branch secret' })] })));
    expect(screen.queryByLabelText('文档标题')).toBeNull(); expect(screen.queryByText('Old branch secret')).toBeNull();
    await act(async () => newList.resolve(response({ items: [saved({ id: 'new-scope-doc', title: 'Current branch document', version: 2 })] })));
    expect((screen.getByLabelText('文档标题') as HTMLInputElement).value).toBe('Current branch document');
    expect(screen.getByText('已保存 · v2')).toBeTruthy(); expect(mutations()).toHaveLength(0);
  });
  it('does not initialize a delayed list after access is revoked during bootstrap', async () => {
    const listing = deferred<ReturnType<typeof response>>(), proposals = deferred<ReturnType<typeof response>>();
    server({ override: (url, init) => {
      if (url.endsWith('/documents') && init.method === 'GET') return listing.promise;
      if (url.endsWith('/director-proposals')) return proposals.promise;
    } });
    render(<CreativeWorkspace {...props()} />); fireEvent.click(tab(/Screenplay/));
    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => url.endsWith('/director-proposals'))).toBe(true));
    await act(async () => proposals.resolve(response({ code: 'FORBIDDEN' }, 403))); await screen.findByText('访问已锁定');
    await act(async () => listing.resolve(response({ items: [saved({ title: 'Revoked document' })] })));
    expect(screen.queryByLabelText('文档标题')).toBeNull(); expect(screen.queryByText('Revoked document')).toBeNull();
    expect(screen.queryByRole('button', { name: '重试读取工作台' })).toBeNull(); expect(mutations()).toHaveLength(0);
  });
  it('exposes all five keyboard-accessible modes while the manuscript stays mounted', async () => {
    const mounted = vi.fn(), unmounted = vi.fn();
    function Manuscript() { const [value, setValue] = useState('Existing unsaved manuscript'); useEffect(() => { mounted(); return unmounted; }, []); return <textarea aria-label="Original manuscript" value={value} onChange={event => setValue(event.target.value)} />; }
    render(<CreativeWorkspace {...props({ novelMain: <Manuscript /> })} />); await ready();
    const manuscript = screen.getByLabelText('Original manuscript'); fireEvent.change(manuscript, { target: { value: 'Keep my unsaved prose' } });
    expect(within(screen.getByRole('tablist', { name: '创作模式' })).getAllByRole('tab')).toHaveLength(5);
    for (const name of [/Screenplay/, /Director/, /Storyboard/, /Production/, /Novel/]) {
      fireEvent.click(tab(name)); expect(tab(name).getAttribute('aria-selected')).toBe('true');
      expect(screen.getByLabelText('Original manuscript')).toBe(manuscript); expect((manuscript as HTMLTextAreaElement).value).toBe('Keep my unsaved prose');
    }
    fireEvent.keyDown(tab(/Novel/), { key: 'End' }); expect(tab(/Production/).getAttribute('aria-selected')).toBe('true'); expect(document.activeElement).toBe(tab(/Production/));
    fireEvent.keyDown(tab(/Production/), { key: 'ArrowRight' }); expect(tab(/Novel/).getAttribute('aria-selected')).toBe('true');
    expect(mounted).toHaveBeenCalledTimes(1); expect(unmounted).not.toHaveBeenCalled(); expect(mutations()).toHaveLength(0);
  });
  it('creates once, saves again with the returned version, and preserves captured identity', async () => {
    server({ override: (url, init) => {
      if (url.endsWith('/documents') && init.method === 'POST') return response(saved({ ...JSON.parse(String(init.body)), version: 1 }));
      if (url.endsWith('/documents/doc-original') && init.method === 'PUT') return response(saved({ ...JSON.parse(String(init.body)), version: 2 }));
    } });
    render(<CreativeWorkspace {...props()} />); await screenplay();
    fireEvent.change(screen.getByLabelText('文档标题'), { target: { value: 'New adaptation' } }); fireEvent.click(screen.getByRole('button', { name: '添加场景' }));
    fireEvent.change(screen.getByLabelText('动作与叙事'), { target: { value: 'A quiet opening.' } }); fireEvent.click(screen.getByRole('button', { name: '保存草稿' }));
    await screen.findByText('已保存“New adaptation” · v1'); fireEvent.change(screen.getByLabelText('文档标题'), { target: { value: 'Revised adaptation' } }); fireEvent.click(screen.getByRole('button', { name: '保存草稿' }));
    await screen.findByText('已保存“Revised adaptation” · v2'); expect(mutations()).toHaveLength(2); const [created, updated] = mutations();
    expect(JSON.parse(created[1].body)).toMatchObject({ mode: 'SCREENPLAY', source_chapter_ids: ['chapter-1'], title: 'New adaptation', scenes: [{ action: 'A quiet opening.' }] });
    expect(JSON.parse(created[1].body)).not.toHaveProperty('expected_version'); expect(JSON.parse(updated[1].body)).toMatchObject({ expected_version: 1, title: 'Revised adaptation' });
    for (const [, init] of mutations()) expect(init.headers).toMatchObject({ 'X-Session-Token': 'session-original', 'X-Branch-Id': 'branch-original' });
    expect(fetchMock.mock.calls.some(([url]) => /chapters.*(save|revision)|generation/.test(url))).toBe(false);
  });
  it('coalesces repeated save clicks while a mutation is pending', async () => {
    const pending = deferred<ReturnType<typeof response>>(); server({ documents: [saved()], override: (_url, init) => init.method === 'PUT' ? pending.promise : undefined });
    render(<CreativeWorkspace {...props()} />); await screenplay(); fireEvent.change(screen.getByLabelText('文档标题'), { target: { value: 'One save only' } });
    const button = screen.getByRole('button', { name: '保存草稿' }); act(() => { button.dispatchEvent(new MouseEvent('click', { bubbles: true })); button.dispatchEvent(new MouseEvent('click', { bubbles: true })); });
    expect(mutations()).toHaveLength(1); expect(screen.getByRole('button', { name: '保存中…' })).toBeTruthy();
    await act(async () => pending.resolve(response(saved({ title: 'One save only', version: 8 })))); await screen.findByText('已保存“One save only” · v8'); expect(mutations()).toHaveLength(1);
  });
  it.each([409, 500])('preserves and locks the local draft after uncertain status %i', async status => {
    server({ documents: [saved()], override: (_url, init) => init.method === 'PUT' ? response({ code: status === 409 ? 'CREATIVE_VERSION_CONFLICT' : 'SERVER_ERROR' }, status) : undefined });
    render(<CreativeWorkspace {...props()} />); await screenplay(); fireEvent.change(screen.getByLabelText('动作与叙事'), { target: { value: 'Do not discard my revised scene.' } }); fireEvent.click(screen.getByRole('button', { name: '保存草稿' }));
    await screen.findByText('需要核对版本 · 本地草稿仍保留'); expect((screen.getByLabelText('动作与叙事') as HTMLTextAreaElement).value).toBe('Do not discard my revised scene.');
    expect(screen.getByLabelText('动作与叙事').closest('fieldset')!.disabled).toBe(true); expect((screen.getByRole('button', { name: '保存草稿' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: '保存草稿' })); expect(mutations()).toHaveLength(1); expect(JSON.parse(mutations()[0][1].body).expected_version).toBe(7);
  });
  it('locks the workspace and removes creative contents after authorization is denied', async () => {
    server({ documents: [saved()], override: (_url, init) => init.method === 'PUT' ? response({ code: 'FORBIDDEN' }, 403) : undefined });
    render(<CreativeWorkspace {...props()} />); await screenplay(); fireEvent.change(screen.getByLabelText('文档标题'), { target: { value: 'Private draft' } }); fireEvent.click(screen.getByRole('button', { name: '保存草稿' }));
    await screen.findByText('访问已锁定'); expect(screen.queryByLabelText('文档标题')).toBeNull(); expect(screen.queryByText('Saved screenplay')).toBeNull(); expect(screen.queryByRole('button', { name: '准备待审导演建议' })).toBeNull();
    fireEvent.click(tab(/Storyboard/)); expect(tab(/Screenplay/).getAttribute('aria-selected')).toBe('true'); expect(mutations()).toHaveLength(1);
  });
  it('keeps read-only document fields disabled and never writes', async () => {
    server({ documents: [saved()], capabilities: { ...caps, can_mutate: false } }); render(<CreativeWorkspace {...props()} />); await screenplay();
    expect(screen.getByLabelText('文档标题').closest('fieldset')!.disabled).toBe(true); expect((screen.getByRole('button', { name: '保存草稿' }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole('button', { name: '准备待审导演建议' }) as HTMLButtonElement).disabled).toBe(true); expect(mutations()).toHaveLength(0);
  });
  it('cancels navigation without losing edits and requires explicit discard before exiting', async () => {
    const onExit = vi.fn(); render(<CreativeWorkspace {...props({ onExit })} />); await screenplay(); fireEvent.change(screen.getByLabelText('文档标题'), { target: { value: 'Unsaved adaptation' } });
    fireEvent.click(screen.getByRole('button', { name: '返回经典工作区' })); expect(onExit).not.toHaveBeenCalled(); expect((screen.getByRole('button', { name: '确认离开' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: '继续编辑' })); expect(screen.queryByRole('button', { name: '确认离开' })).toBeNull(); expect((screen.getByLabelText('文档标题') as HTMLInputElement).value).toBe('Unsaved adaptation');
    fireEvent.click(screen.getByRole('button', { name: '返回经典工作区' })); fireEvent.click(screen.getByLabelText('确认放弃未保存草稿并离开')); fireEvent.click(screen.getByRole('button', { name: '确认离开' })); expect(onExit).toHaveBeenCalledTimes(1); expect(mutations()).toHaveLength(0);
  });
  it('ignores a late mutation receipt from the previous scope and captures the new branch', async () => {
    const pending = deferred<ReturnType<typeof response>>(); server({ override: (_url, init) => init.method === 'POST' ? pending.promise : undefined });
    const original = props(), view = render(<CreativeWorkspace {...original} />); await screenplay(); fireEvent.change(screen.getByLabelText('文档标题'), { target: { value: 'Old branch draft' } }); fireEvent.click(screen.getByRole('button', { name: '保存草稿' })); expect(mutations()).toHaveLength(1);
    view.rerender(<CreativeWorkspace {...original} context={{ ...original.context, sessionToken: 'session-new', scope: { ...original.context.scope!, branchId: 'branch-new' } }} />);
    await ready(); await act(async () => pending.resolve(response(saved({ title: 'Old branch draft', version: 1 })))); await screenplay();
    expect((screen.getByLabelText('文档标题') as HTMLInputElement).value).toBe(''); expect(screen.queryByText(/已保存“Old branch draft”/)).toBeNull(); expect(screen.queryByRole('button', { name: /Old branch draft/ })).toBeNull();
    expect(mutations()[0][1].headers).toMatchObject({ 'X-Session-Token': 'session-original', 'X-Branch-Id': 'branch-original' });
    const newReads = fetchMock.mock.calls.filter(([, init]) => init.headers['X-Session-Token'] === 'session-new'); expect(newReads.length).toBeGreaterThan(0); for (const [, init] of newReads) expect(init.headers['X-Branch-Id']).toBe('branch-new');
  });
  it('does not expose late history from a document after switching modes', async () => {
    const pending = deferred<ReturnType<typeof response>>(); server({ documents: [saved()], override: url => url.endsWith('/history') ? pending.promise : undefined });
    render(<CreativeWorkspace {...props()} />); await screenplay(); fireEvent.click(screen.getByRole('button', { name: '历史' })); fireEvent.click(tab(/Storyboard/));
    await act(async () => pending.resolve(response({ document_id: 'doc-original', current_version: 7, items: [saved()] })));
    expect(screen.queryByRole('region', { name: '创作文档历史' })).toBeNull(); expect(screen.queryByText('版本历史 · 当前 v7')).toBeNull();
  });
  it('does not leak a late document list from a prior scope', async () => {
    const pending = deferred<ReturnType<typeof response>>();
    server({ override: (url, init) => url.endsWith('/documents') && init.method === 'GET' && (init.headers as Record<string, string>)['X-Session-Token'] === 'session-original' ? pending.promise : undefined });
    const original = props(), view = render(<CreativeWorkspace {...original} />);
    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => url.endsWith('/documents'))).toBe(true));
    view.rerender(<CreativeWorkspace {...original} context={{ ...original.context, sessionToken: 'session-new', scope: { ...original.context.scope!, branchId: 'branch-new' } }} />);
    await ready(); await act(async () => pending.resolve(response({ items: [saved({ title: 'Other branch secret' })] })));
    await screenplay(); expect(screen.queryByText('Other branch secret')).toBeNull(); expect((screen.getByLabelText('文档标题') as HTMLInputElement).value).toBe('');
  });

  it('requires explicit server-version adoption and preserves the draft when adoption is cancelled', async () => {
    let writes = 0;
    server({ documents: [saved()], override: (url, init) => {
      if (init.method === 'PUT') { writes++; return writes === 1 ? response({ code: 'CONFLICT' }, 409) : response(saved({ ...JSON.parse(String(init.body)), version: 10 })); }
      if (url.endsWith('/documents/doc-original') && init.method === 'GET') return response(saved({ title: 'Server candidate', version: 9 }));
    } });
    render(<CreativeWorkspace {...props()} />); await screenplay(); fireEvent.change(screen.getByLabelText('文档标题'), { target: { value: 'Local preserved title' } }); fireEvent.click(screen.getByRole('button', { name: '保存草稿' }));
    await screen.findByText('需要核对版本 · 本地草稿仍保留'); fireEvent.click(screen.getByRole('button', { name: '核对服务端版本' })); await screen.findByText('服务端 v9 · Server candidate');
    expect((screen.getByRole('button', { name: '使用核对后的服务端版本' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: '保留本地草稿' })); expect((screen.getByLabelText('文档标题') as HTMLInputElement).value).toBe('Local preserved title');
    fireEvent.click(screen.getByRole('button', { name: '核对服务端版本' })); await screen.findByText('服务端 v9 · Server candidate');
    fireEvent.click(screen.getByLabelText('已核对并确认用服务端版本替换当前本地草稿')); fireEvent.click(screen.getByRole('button', { name: '使用核对后的服务端版本' }));
    expect((screen.getByLabelText('文档标题') as HTMLInputElement).value).toBe('Server candidate'); expect(screen.queryByText('需要核对版本 · 本地草稿仍保留')).toBeNull();
    fireEvent.change(screen.getByLabelText('文档标题'), { target: { value: 'Edit after adoption' } }); fireEvent.click(screen.getByRole('button', { name: '保存草稿' })); await screen.findByText('已保存“Edit after adoption” · v10');
    expect(JSON.parse(mutations()[1][1].body).expected_version).toBe(9);
  });

  it('does not repopulate denied content from a pending successful mutation', async () => {
    const readPending = deferred<ReturnType<typeof response>>(), writePending = deferred<ReturnType<typeof response>>();
    server({ documents: [saved()], override: (url, init) => {
      if (url.endsWith('/director-proposals')) return readPending.promise;
      if (init.method === 'PUT') return writePending.promise;
    } });
    render(<CreativeWorkspace {...props()} />); await screenplay(); fireEvent.change(screen.getByLabelText('文档标题'), { target: { value: 'Late revoked content' } }); fireEvent.click(screen.getByRole('button', { name: '保存草稿' }));
    expect(mutations()).toHaveLength(1); await act(async () => readPending.resolve(response({ code: 'FORBIDDEN' }, 403))); await screen.findByText('访问已锁定');
    await act(async () => writePending.resolve(response(saved({ title: 'Late revoked content', version: 8 }))));
    expect(screen.queryByRole('button', { name: /Late revoked content/ })).toBeNull(); expect(screen.queryByText('已保存“Late revoked content” · v8')).toBeNull();
  });

  it('copies only saved chapter content into a local screenplay scaffold without writing the manuscript', async () => {
    render(<CreativeWorkspace {...props()} />); await screenplay(); fireEvent.click(screen.getByRole('button', { name: '从当前已保存章节建立场景底稿' }));
    expect((screen.getByLabelText('动作与叙事') as HTMLTextAreaElement).value).toBe('Manuscript'); expect((screen.getByLabelText('场景标题') as HTMLInputElement).value).toBe('Original chapter');
    expect(screen.getByText(/尚未进行剧本改编或调用模型/)).toBeTruthy(); expect(mutations()).toHaveLength(0);
  });

  it('derives a storyboard from the saved version and never overwrites the screenplay', async () => {
    server({ documents: [saved()], override: url => url.endsWith('/derive') ? response(saved({ id: 'storyboard-1', mode: 'STORYBOARD', version: 1, title: 'Derived storyboard' })) : undefined });
    render(<CreativeWorkspace {...props()} />); await screenplay(); fireEvent.click(screen.getByRole('button', { name: '建立分镜草稿' }));
    await screen.findByText(/已从当前已保存版本建立“Derived storyboard”/); expect(tab(/Storyboard/).getAttribute('aria-selected')).toBe('true'); expect(mutations()).toHaveLength(1);
    expect(JSON.parse(mutations()[0][1].body)).toEqual({ expected_version: 7, mode: 'STORYBOARD' }); fireEvent.click(tab(/Screenplay/)); expect((screen.getByLabelText('文档标题') as HTMLInputElement).value).toBe('Saved screenplay');
  });

  it('restores history only after explicit review and creates a new current version', async () => {
    server({ documents: [saved()], override: url => {
      if (url.endsWith('/history')) return response({ document_id: 'doc-original', current_version: 7, items: [saved({ version: 3, title: 'Historic screenplay' }), saved()] });
      if (url.endsWith('/restore')) return response(saved({ title: 'Historic screenplay', version: 8 }));
    } });
    render(<CreativeWorkspace {...props()} />); await screenplay(); fireEvent.click(screen.getByRole('button', { name: '历史' })); await screen.findByText('版本历史 · 当前 v7');
    fireEvent.click(screen.getByText('v3 · Historic screenplay')); const restore = screen.getByRole('button', { name: '恢复 v3 为新版本' }) as HTMLButtonElement;
    expect(restore.disabled).toBe(true); fireEvent.click(screen.getByLabelText('已核对 v3 的完整内容；恢复会新建当前版本')); fireEvent.click(restore);
    await screen.findByText('已将所选历史内容恢复为新版本 v8，其他历史版本仍保留。'); expect(mutations()).toHaveLength(1); expect(JSON.parse(mutations()[0][1].body)).toEqual({ expected_version: 7, restore_version: 3 });
    expect((screen.getByLabelText('文档标题') as HTMLInputElement).value).toBe('Historic screenplay');
  });

  it('reorders storyboard shots without replacing their identities and saves their new sequence', async () => {
    const shots = [{ ...newShot(1, 'scene-1'), id: 'shot-first', frame_prompt: 'First frame' }, { ...newShot(2, 'scene-1'), id: 'shot-second', frame_prompt: 'Second frame' }];
    server({ documents: [saved({ mode: 'STORYBOARD', shots })], override: (_url, init) => init.method === 'PUT' ? response(saved({ ...JSON.parse(String(init.body)), version: 8 })) : undefined });
    render(<CreativeWorkspace {...props()} />); await ready(); fireEvent.click(tab(/Storyboard/));
    expect((screen.getByRole('button', { name: '前移镜头 1' }) as HTMLButtonElement).disabled).toBe(true); expect((screen.getByRole('button', { name: '后移镜头 2' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: '后移镜头 1' })); fireEvent.click(screen.getByRole('button', { name: '保存草稿' })); await screen.findByText('已保存“Saved screenplay” · v8');
    expect(JSON.parse(mutations()[0][1].body).shots).toEqual([{ ...shots[1], number: 1 }, { ...shots[0], number: 2 }]); expect(JSON.parse(mutations()[0][1].body).expected_version).toBe(7);
  });

});
