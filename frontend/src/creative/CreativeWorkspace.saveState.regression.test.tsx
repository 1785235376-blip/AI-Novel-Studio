// @vitest-environment jsdom
// Real CreativeWorkspace / Canvas / AppShell interactions. API timing is
// controlled; these mounted regressions are not real File/PG acceptance.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CreativeWorkspace, type CreativeWorkspaceProps } from './CreativeWorkspace';
import { newDocument, newScene, newShot, type CreativeCapabilities, type CreativeDocument } from './types';

const caps: CreativeCapabilities = { enabled: true, can_mutate: true,
  modes: ['SCREENPLAY', 'DIRECTOR', 'STORYBOARD', 'PRODUCTION'] };
function row(mode: 'SCREENPLAY' | 'STORYBOARD' = 'STORYBOARD', patch: Partial<CreativeDocument> = {}): CreativeDocument {
  return { ...newDocument(mode), id: mode === 'STORYBOARD' ? 'board' : 'script', title: mode === 'STORYBOARD' ? 'Saved board' : 'Saved screenplay',
    version: 1, status: 'DRAFT', actor_id: 'author', created_at: '2026-10-17', updated_at: '2026-10-17', source_evidence: {},
    scenes: [{ ...newScene(1), id: 'scene', heading: 'Original scene', action: 'Original action' }],
    shots: mode === 'STORYBOARD' ? [{ ...newShot(1, 'scene'), id: 'shot', frame_prompt: 'Exact original frame\n  ' }] : [], ...patch };
}
function props(patch: Partial<CreativeWorkspaceProps> = {}): CreativeWorkspaceProps {
  return { enabled: true, novelId: 'project', context: { sessionToken: 'trusted-session',
    actor: { id: 'author', displayName: 'Author', workspaceId: 'workspace' },
    scope: { workspaceId: 'workspace', projectId: 'project', storylineId: 'story', branchId: 'branch' } },
    scope: { workspace: 'Workspace', project: 'Project', storyline: 'Story', branch: 'Branch' }, actor: 'Author',
    chapterCount: 0, manuscriptReady: false, novelMain: <div>Original novel canvas</div>, novelSidebar: <div>Original novel sidebar</div>,
    novelInspector: <div>Original novel inspector</div>, novelStatus: <span>正文：正在打开章节…</span>,
    onExit: vi.fn(), onModuleChange: vi.fn(), ...patch };
}
function response(value: unknown, status = 200) { return new Response(JSON.stringify(value), {
  status, headers: { 'Content-Type': 'application/json' },
}); }
function deferred<T>() {
  let resolve!: (value: T) => void, reject!: (reason: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject };
}
type Override = (url: string, init: RequestInit) => Response | Promise<Response> | undefined;
let fetcher: ReturnType<typeof vi.fn>;
function server(documents = [row()], override?: Override) {
  fetcher = vi.fn(async (target: string, init: RequestInit = {}) => {
    const url = String(target), custom = override?.(url, init); if (custom !== undefined) return custom;
    if (url.endsWith('/capabilities')) return response(caps);
    if (url.endsWith('/documents') && init.method === 'GET') return response({ items: documents });
    if (url.endsWith('/creation-reference-data')) return response({ characters: [], locations: [], story_routes: [] });
    if (url.endsWith('/assets')) return response([]);
    if (url.endsWith('/director-proposals') || url.endsWith('/model-routes')) return response({ items: [] });
    return response({ code: 'NOT_CONFIGURED', message: 'Outside save-state regression' }, 404);
  }); vi.stubGlobal('fetch', fetcher);
}
const mutations = () => fetcher.mock.calls.filter(([, init]) => init.method && init.method !== 'GET');
const stage = (name: RegExp) => within(screen.getByRole('tablist', { name: '创作模式' })).getByRole('tab', { name });
const canvas = () => screen.getByRole('region', { name: '创作画布' });
const footer = () => document.querySelector('.status-bar')!;
const title = () => screen.getByLabelText('文档标题') as HTMLInputElement;
const frame = () => screen.getByLabelText('画面描述') as HTMLTextAreaElement;
const save = () => screen.getByRole('button', { name: '保存草稿' }) as HTMLButtonElement;
async function open(name: RegExp = /Storyboard/) {
  await waitFor(() => expect(screen.queryByText('正在核对创作文档与权限…')).toBeNull());
  fireEvent.click(stage(name)); await screen.findByLabelText('文档标题');
}
beforeEach(() => { server(); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('Creative current document save-state ownership', () => {
  it('hydrates a fresh saved document without inventing dirty content or a write', async () => {
    render(<CreativeWorkspace {...props()} />); await open();
    expect(within(canvas()).getByText('已保存 · v1')).toBeTruthy();
    expect(save().disabled).toBe(true); expect(frame().value).toBe('Exact original frame\n  ');
    expect(mutations()).toHaveLength(0);
  });
  it('projects the current saved Creative version instead of an unrelated novel loading status', async () => {
    render(<CreativeWorkspace {...props()} />);
    expect(footer().textContent).toContain('正文：正在打开章节…'); await open();
    expect(footer().textContent).not.toContain('正文：正在打开章节…');
    expect(footer().textContent).toContain('当前分镜：已保存 · v1');
    expect(screen.getByRole('status', { name: '当前创作文档保存状态' }).textContent).toContain('已保存 · v1');
  });
  it('retains the original common connection and Tutor content while isolating the manuscript status', async () => {
    render(<CreativeWorkspace {...props({ commonStatus: <span>连接：协作服务 · Original Tutor</span> })} />); await open();
    expect(footer().textContent).toContain('连接：协作服务 · Original Tutor');
    expect(footer().textContent).not.toContain('正文：正在打开章节…');
    fireEvent.click(stage(/Novel/)); expect(footer().textContent).toContain('正文：正在打开章节…');
    expect(screen.queryByRole('status', { name: '当前创作文档保存状态' })).toBeNull();
  });
  it('does not announce a saved version while the original scoped list is still pending', async () => {
    const pending = deferred<Response>();
    server([], (url, init) => url.endsWith('/documents') && init.method === 'GET' ? pending.promise : undefined);
    render(<CreativeWorkspace {...props()} />); fireEvent.click(stage(/Storyboard/));
    expect(screen.getByRole('status', { name: '当前创作文档保存状态' }).textContent).toContain('正在核对创作文档与权限');
    expect(screen.queryByLabelText('文档标题')).toBeNull();
    await act(async () => pending.resolve(response({ items: [row()] })));
    await screen.findByLabelText('文档标题'); expect(footer().textContent).toContain('当前分镜：已保存 · v1');
  });
  it('returns to clean only after a real title edit is restored exactly to the saved payload', async () => {
    render(<CreativeWorkspace {...props()} />); await open();
    fireEvent.change(title(), { target: { value: 'Actual unsaved title' } });
    expect(within(canvas()).getByText('未保存')).toBeTruthy(); expect(save().disabled).toBe(false);
    fireEvent.change(title(), { target: { value: 'Saved board' } });
    expect(within(canvas()).getByText('已保存 · v1')).toBeTruthy(); expect(save().disabled).toBe(true);
    expect(frame().value).toBe('Exact original frame\n  '); expect(mutations()).toHaveLength(0);
  });
  it('does not invent a content change for equivalent numeric editing', async () => {
    render(<CreativeWorkspace {...props()} />); await open();
    fireEvent.change(screen.getByLabelText('镜头时长（秒）'), { target: { value: '5.0' } });
    expect(within(canvas()).getByText('已保存 · v1')).toBeTruthy(); expect(save().disabled).toBe(true);
    expect(mutations()).toHaveLength(0);
  });
  it('keeps real frame whitespace changes dirty and preserves every entered character', async () => {
    render(<CreativeWorkspace {...props()} />); await open();
    const changed = '\n Exact original frame\n   ';
    fireEvent.change(frame(), { target: { value: changed } });
    expect(frame().value).toBe(changed); expect(within(canvas()).getByText('未保存')).toBeTruthy();
    expect(save().disabled).toBe(false); expect(mutations()).toHaveLength(0);
  });
  it('uses the original optional-field projection when an added visual target is explicitly removed', async () => {
    server([row('STORYBOARD', { visual_target: null })]);
    render(<CreativeWorkspace {...props()} />); await open();
    fireEvent.change(screen.getByLabelText('视觉风格'), { target: { value: 'A real style' } });
    expect(within(canvas()).getByText('未保存')).toBeTruthy();
    fireEvent.click(within(canvas()).getByRole('button', { name: '移除此文档视觉目标' }));
    expect(within(canvas()).getByText('已保存 · v1')).toBeTruthy(); expect(save().disabled).toBe(true);
  });
  it('treats identical nested objects as clean when their server key order differs from the editor order', async () => {
    server([row('STORYBOARD', { visual_target: { rhythm: '', color: '', reference_works: [], atmosphere: '', style: '' } })]);
    render(<CreativeWorkspace {...props()} />); await open();
    fireEvent.click(within(canvas()).getByRole('button', { name: '移除此文档视觉目标' }));
    fireEvent.change(within(canvas()).getByLabelText('视觉风格'), { target: { value: 'Actual style' } });
    fireEvent.change(within(canvas()).getByLabelText('视觉风格'), { target: { value: '' } });
    expect(within(canvas()).getByText('已保存 · v1')).toBeTruthy(); expect(save().disabled).toBe(true);
    expect(mutations()).toHaveLength(0);
  });
  it('preserves ordered character arrays and becomes clean only after their exact order is restored', async () => {
    const original = row(); original.shots[0].characters = ['character-A', 'character-B']; server([original]);
    render(<CreativeWorkspace {...props()} />); await open();
    fireEvent.change(screen.getByLabelText('镜头角色（用、分隔）'), { target: { value: 'character-B、character-A' } });
    expect(within(canvas()).getByText('未保存')).toBeTruthy(); expect(save().disabled).toBe(false);
    fireEvent.change(screen.getByLabelText('镜头角色（用、分隔）'), { target: { value: 'character-A、character-B' } });
    expect(within(canvas()).getByText('已保存 · v1')).toBeTruthy(); expect(mutations()).toHaveLength(0);
  });
  it('does not let an exact title undo hide a different unsaved nested scene change', async () => {
    render(<CreativeWorkspace {...props()} />); await open();
    fireEvent.change(screen.getByLabelText('动作与叙事'), { target: { value: 'Original action\n ' } });
    fireEvent.change(title(), { target: { value: 'Changed title' } });
    fireEvent.change(title(), { target: { value: 'Saved board' } });
    expect(within(canvas()).getByText('未保存')).toBeTruthy(); expect(save().disabled).toBe(false);
    expect((screen.getByLabelText('动作与叙事') as HTMLTextAreaElement).value).toBe('Original action\n ');
    expect(footer().textContent).toContain('当前分镜：未保存更改 · 基于 v1');
  });
  it('does not clear an edited new document merely because its title is later emptied', async () => {
    server([]); render(<CreativeWorkspace {...props()} />); await open();
    expect(within(canvas()).getByText('新草稿')).toBeTruthy();
    fireEvent.change(title(), { target: { value: 'Unsaved new work' } });
    fireEvent.change(title(), { target: { value: '' } });
    expect(within(canvas()).getByText('未保存')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '返回经典工作区' }));
    expect(screen.getByLabelText('确认放弃未保存草稿并离开')).toBeTruthy();
  });
  it('names other-stage real dirty drafts while preserving the saved current document and the original exit guard', async () => {
    server([row(), row('SCREENPLAY')]); const original = props();
    render(<CreativeWorkspace {...original} />); await open(/Screenplay/);
    fireEvent.change(title(), { target: { value: 'Unsaved screenplay kept in memory' } });
    fireEvent.click(stage(/Storyboard/)); await screen.findByLabelText('画面描述');
    expect(within(canvas()).getByText('已保存 · v1')).toBeTruthy();
    fireEvent.click(stage(/Screenplay/)); expect(title().value).toBe('Unsaved screenplay kept in memory');
    fireEvent.click(stage(/Storyboard/));
    expect(footer().textContent).toContain('当前分镜：已保存 · v1');
    expect(screen.getByLabelText('其他创作草稿状态').textContent).toContain('剧本');
    fireEvent.click(screen.getByRole('button', { name: '返回经典工作区' }));
    expect(screen.getByLabelText('确认放弃未保存草稿并离开')).toBeTruthy();
    expect(original.onExit).not.toHaveBeenCalled(); expect(mutations()).toHaveLength(0);
  });
  it('adopts the actual normalized server response as both input and CAS base after saving', async () => {
    server([row()], (url, init) => {
      if (url.endsWith('/documents/board') && init.method === 'PUT') {
        const { expected_version, ...input } = JSON.parse(init.body as string);
        return response({ ...row(), ...input, title: input.title.trim(), version: expected_version + 1 });
      }
    });
    render(<CreativeWorkspace {...props()} />); await open();
    fireEvent.change(title(), { target: { value: '  Server normalized title  ' } }); fireEvent.click(save());
    await screen.findByText('已保存“Server normalized title” · v2');
    expect(title().value).toBe('Server normalized title'); expect(within(canvas()).getByText('已保存 · v2')).toBeTruthy();
    expect(save().disabled).toBe(true); expect(frame().value).toBe('Exact original frame\n  ');
    fireEvent.change(frame(), { target: { value: 'Next exact frame\n ' } }); fireEvent.click(save());
    await screen.findByText('已保存“Server normalized title” · v3');
    expect(mutations().map(([, init]) => JSON.parse(init.body as string).expected_version)).toEqual([1, 2]);
    expect(footer().textContent).toContain('当前分镜：已保存 · v3');
  });
  it('identifies a real pending save and fences repeated clicks until its original response arrives', async () => {
    const pending = deferred<Response>();
    server([row()], (url, init) => url.endsWith('/documents/board') && init.method === 'PUT' ? pending.promise : undefined);
    render(<CreativeWorkspace {...props()} />); await open(); fireEvent.change(title(), { target: { value: 'Saved once' } });
    fireEvent.click(save()); const pendingSave = screen.getByRole('button', { name: '保存中…' }); fireEvent.click(pendingSave);
    expect(mutations()).toHaveLength(1); expect(title().disabled).toBe(false);
    expect(title().closest('fieldset')?.disabled).toBe(true);
    expect(screen.getByRole('status', { name: '当前创作文档保存状态' }).textContent).toContain('保存中');
    await act(async () => pending.resolve(response(row('STORYBOARD', { title: 'Saved once', version: 2 }))));
    expect(within(canvas()).getByText('已保存 · v2')).toBeTruthy(); expect(footer().textContent).toContain('当前分镜：已保存 · v2');
  });
  it('reports an actual save ahead of an older pending list and preserves its server-normalized draft', async () => {
    const pendingList = deferred<Response>(), pendingSave = deferred<Response>();
    server([], (url, init) => {
      if (url.endsWith('/capabilities')) return response({ ...caps, modes: [...caps.modes, 'SCRIPT'] });
      if (url.endsWith('/documents') && init.method === 'GET') return pendingList.promise;
      if (url.endsWith('/documents') && init.method === 'POST') return pendingSave.promise;
    });
    render(<CreativeWorkspace {...props()} />); fireEvent.click(stage(/Screenplay/));
    fireEvent.click(await screen.findByRole('button', { name: '新建独立通用脚本' }));
    fireEvent.change(title(), { target: { value: 'Actual new script' } });
    fireEvent.change(screen.getByLabelText('通用脚本内容'), { target: { value: 'Exact script body\n ' } }); fireEvent.click(save());
    expect(screen.getByRole('status', { name: '当前创作文档保存状态' }).textContent).toBe('当前剧本：保存中…');
    const actual = row('SCREENPLAY', { mode: 'SCRIPT', id: 'created-script', title: 'Actual normalized script', script: { purpose: 'CUSTOM', body: 'Exact script body\n ' } });
    await act(async () => { pendingSave.resolve(response(actual)); pendingList.resolve(response({ items: [] })); });
    expect(title().value).toBe('Actual normalized script');
    expect((screen.getByLabelText('通用脚本内容') as HTMLTextAreaElement).value).toBe('Exact script body\n ');
    expect(footer().textContent).toContain('当前剧本：已保存 · v1'); expect(mutations()).toHaveLength(1);
  });
  it('keeps a saved document read-only without claiming that edit permission is available', async () => {
    server([row()], url => url.endsWith('/capabilities') ? response({ ...caps, can_mutate: false }) : undefined);
    render(<CreativeWorkspace {...props()} />); await open();
    expect(footer().textContent).toContain('当前分镜：已保存 · v1'); expect(footer().textContent).toContain('只读');
    expect(title().closest('fieldset')?.disabled).toBe(true); expect(save().disabled).toBe(true);
    expect(mutations()).toHaveLength(0);
  });
  it('ignores the old scope save receipt and its saved status after a new branch is mounted', async () => {
    const pending = deferred<Response>(), original = props();
    server([row()], (url, init) => {
      if (url.endsWith('/documents/board') && init.method === 'PUT') return pending.promise;
      if (url.endsWith('/documents') && init.method === 'GET' && (init.headers as Record<string, string>)['X-Branch-Id'] === 'branch-new') return response({ items: [row('STORYBOARD', { id: 'new-board', title: 'New branch board', version: 4 })] });
    });
    const view = render(<CreativeWorkspace {...original} />); await open();
    fireEvent.change(title(), { target: { value: 'Old branch unsaved' } }); fireEvent.click(save());
    view.rerender(<CreativeWorkspace {...original} context={{ ...original.context, scope: { ...original.context.scope!, branchId: 'branch-new' } }} />);
    await open(); fireEvent.change(frame(), { target: { value: 'New branch unsaved frame' } });
    await act(async () => pending.resolve(response(row('STORYBOARD', { title: 'Old branch unsaved', version: 2 }))));
    expect(title().value).toBe('New branch board'); expect(frame().value).toBe('New branch unsaved frame');
    expect(footer().textContent).toContain('当前分镜：未保存更改 · 基于 v4');
    expect(screen.queryByText('已保存“Old branch unsaved” · v2')).toBeNull(); expect(mutations()).toHaveLength(1);
  });
  it('does not let a previous document history response change the new document status or draft', async () => {
    const pending = deferred<Response>(), second = row('STORYBOARD', { id: 'board-B', title: 'Saved board B', version: 5 });
    server([row(), second], url => url.endsWith('/documents/board/history') ? pending.promise : undefined);
    render(<CreativeWorkspace {...props()} />); await open(); fireEvent.click(screen.getByRole('button', { name: '历史' }));
    fireEvent.click(within(screen.getByRole('region', { name: '创作文档' })).getByRole('button', { name: /Saved board B/ }));
    fireEvent.change(title(), { target: { value: 'Unsaved B stays mine' } });
    await act(async () => pending.resolve(response({ document_id: 'board', current_version: 1, items: [row()] })));
    expect(screen.queryByText('版本历史 · 当前 v1')).toBeNull(); expect(title().value).toBe('Unsaved B stays mine');
    expect(footer().textContent).toContain('当前分镜：未保存更改 · 基于 v5'); expect(mutations()).toHaveLength(0);
  });
  it('does not attach a late verification candidate to a different clean document after an uncertain derive', async () => {
    const pending = deferred<Response>(), second = row('SCREENPLAY', { id: 'script-B', title: 'Saved screenplay B', version: 5 });
    server([row('SCREENPLAY'), second], (url, init) => {
      if (url.endsWith('/derive')) return response({ code: 'EXPERIMENTAL_VERSION_CONFLICT', message: 'Uncertain derive' }, 409);
      if (url.endsWith('/documents/script') && init.method === 'GET') return pending.promise;
    });
    render(<CreativeWorkspace {...props()} />); await open(/Screenplay/);
    fireEvent.click(screen.getByRole('button', { name: '建立分镜草稿' })); await screen.findByText('需要核对版本 · 本地草稿仍保留');
    fireEvent.click(screen.getByRole('button', { name: '核对服务端版本' }));
    fireEvent.click(within(screen.getByRole('region', { name: '创作文档' })).getByRole('button', { name: /Saved screenplay B/ }));
    expect(title().value).toBe('Saved screenplay B');
    await act(async () => pending.resolve(response(row('SCREENPLAY', { title: 'Late old candidate', version: 8 }))));
    expect(screen.queryByRole('region', { name: '服务端版本核对' })).toBeNull();
    expect(screen.queryByText('服务端 v8 · Late old candidate')).toBeNull();
    expect(title().value).toBe('Saved screenplay B'); expect(footer().textContent).toContain('当前剧本：已保存 · v5');
  });
  it('distinguishes a pending original derive operation from saving the current document', async () => {
    const pending = deferred<Response>(); server([row('SCREENPLAY')], url => url.endsWith('/derive') ? pending.promise : undefined);
    render(<CreativeWorkspace {...props()} />); await open(/Screenplay/);
    fireEvent.click(screen.getByRole('button', { name: '建立分镜草稿' }));
    const status = screen.getByRole('status', { name: '当前创作文档保存状态' });
    expect(status.textContent).toBe('当前剧本：建立派生文档中… · 基于 v1'); expect(status.textContent).not.toContain('保存中');
    expect(save().disabled).toBe(true); expect(screen.queryByRole('button', { name: '保存中…' })).toBeNull();
    fireEvent.click(stage(/Storyboard/)); expect(stage(/Screenplay/).getAttribute('aria-selected')).toBe('true');
    await act(async () => pending.resolve(response(row('STORYBOARD', { title: 'Actual derived board' }))));
    expect(footer().textContent).toContain('当前分镜：已保存 · v1'); expect(mutations()).toHaveLength(1);
  });
  it('distinguishes a pending reviewed history restore and adopts only its original versioned response', async () => {
    const pending = deferred<Response>(); server([row('STORYBOARD', { version: 2 })], url => {
      if (url.endsWith('/history')) return response({ document_id: 'board', current_version: 2, items: [row(), row('STORYBOARD', { version: 2 })] });
      if (url.endsWith('/restore')) return pending.promise;
    });
    render(<CreativeWorkspace {...props()} />); await open(); fireEvent.click(screen.getByRole('button', { name: '历史' }));
    await screen.findByText('版本历史 · 当前 v2'); fireEvent.click(screen.getByLabelText('已核对 v1 的完整内容；恢复会新建当前版本'));
    fireEvent.click(screen.getByRole('button', { name: '恢复 v1 为新版本' }));
    expect(screen.getByRole('status', { name: '当前创作文档保存状态' }).textContent).toBe('当前分镜：恢复历史版本中… · 基于 v2');
    expect(save().disabled).toBe(true); expect(screen.queryByRole('button', { name: '保存中…' })).toBeNull();
    await act(async () => pending.resolve(response(row('STORYBOARD', { title: 'Restored original history', version: 3 }))));
    expect(footer().textContent).toContain('当前分镜：已保存 · v3');
    expect(JSON.parse(mutations()[0][1].body as string)).toEqual({ expected_version: 2, restore_version: 1 });
  });
  it('does not call a pending Director proposal a document save', async () => {
    const pending = deferred<Response>(); server([row(), row('SCREENPLAY')], (url, init) => url.endsWith('/director-proposals') && init.method === 'POST' ? pending.promise : undefined);
    render(<CreativeWorkspace {...props()} />); await open();
    fireEvent.click(screen.getByRole('button', { name: '准备待审导演建议' }));
    await screen.findByRole('button', { name: '处理中…' });
    expect(save().disabled).toBe(true); expect(screen.queryByRole('button', { name: '保存中…' })).toBeNull();
    expect(footer().textContent).toContain('创作操作进行中…');
    await act(async () => pending.resolve(response({ code: 'UNAVAILABLE', message: 'No proposal in this bounded regression' }, 422)));
    expect(footer().textContent).toContain('当前分镜：已保存 · v1'); expect(mutations()).toHaveLength(1);
  });
  it('does not label explicit server verification as saving or silently replace the blocked draft', async () => {
    const pending = deferred<Response>(); server([row()], (url, init) => {
      if (url.endsWith('/documents/board') && init.method === 'PUT') return response({ code: 'EXPERIMENTAL_VERSION_CONFLICT', message: 'Current changed' }, 409);
      if (url.endsWith('/documents/board') && init.method === 'GET') return pending.promise;
    });
    render(<CreativeWorkspace {...props()} />); await open(); fireEvent.change(title(), { target: { value: 'Mine stays blocked' } }); fireEvent.click(save());
    await screen.findByText('需要核对版本 · 本地草稿仍保留'); fireEvent.click(screen.getByRole('button', { name: '核对服务端版本' }));
    expect(screen.getByRole('status', { name: '当前创作文档保存状态' }).textContent).toBe('当前分镜：核对服务端版本中… · 基于 v1');
    expect(save().disabled).toBe(true); expect(screen.queryByRole('button', { name: '保存中…' })).toBeNull();
    await act(async () => pending.resolve(response(row('STORYBOARD', { version: 2 }))));
    expect(title().value).toBe('Mine stays blocked'); expect(footer().textContent).toContain('需核对保存结果');
  });
  it.each(['network', 'conflict'] as const)('keeps the exact draft blocked after %s failure until explicit original-server adoption', async kind => {
    server([row()], (url, init) => {
      if (url.endsWith('/documents/board') && init.method === 'PUT') {
        if (kind === 'network') return Promise.reject(new TypeError('Real controlled transport failure'));
        return response({ detail: { code: 'EXPERIMENTAL_VERSION_CONFLICT', message: 'CAS changed' } }, 409);
      }
      if (url.endsWith('/documents/board') && init.method === 'GET') return response(row('STORYBOARD', { title: 'Actual server v3', version: 3 }));
    });
    render(<CreativeWorkspace {...props()} />); await open(); fireEvent.change(title(), { target: { value: 'My exact unsaved title' } }); fireEvent.click(save());
    await screen.findByText('需要核对版本 · 本地草稿仍保留');
    expect(title().value).toBe('My exact unsaved title'); expect(mutations()).toHaveLength(1); expect(save().disabled).toBe(true);
    expect(screen.getByRole('status', { name: '当前创作文档保存状态' }).textContent).toContain('需核对保存结果');
    fireEvent.click(screen.getByRole('button', { name: '核对服务端版本' })); await screen.findByText('服务端 v3 · Actual server v3');
    expect(title().value).toBe('My exact unsaved title');
    fireEvent.click(screen.getByLabelText('已核对并确认用服务端版本替换当前本地草稿'));
    fireEvent.click(screen.getByRole('button', { name: '使用核对后的服务端版本' }));
    expect(title().value).toBe('Actual server v3'); expect(within(canvas()).getByText('已保存 · v3')).toBeTruthy();
    expect(footer().textContent).toContain('当前分镜：已保存 · v3'); expect(mutations()).toHaveLength(1);
  });
});
