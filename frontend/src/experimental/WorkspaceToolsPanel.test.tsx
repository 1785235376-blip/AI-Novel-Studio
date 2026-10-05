// @vitest-environment jsdom
import { StrictMode } from 'react';
import { cleanup, fireEvent, render, screen, waitFor, act } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { WorkspaceToolsPanel } from './WorkspaceToolsPanel';
import { experimentalClient } from './api';
import type { Chapter } from '../api';
const chapter: Chapter = { id: 'chapter-one', novel_id: 'novel', title: '风起', number: 1, content: '合成小说正文。', document: {}, version: 3, word_count: 7, status: 'DRAFT' };
const resume = { item: { id: 'resume-one', version: 1, chapter_id: chapter.id, chapter_version: 3, chapter_title: '风起', anchor: { offset: 2, scroll: 10 }, layout: { density: 'normal', section: 'resume', show_failed_only: false }, stopping_note: '明天检查旧信', recent_commands: [], pinned_chapter_ids: [], guide_dismissed: false, updated_at: '2026-10-05' }, availability: 'READY' };
const row = { kind: 'chapter', id: chapter.id, title: '风起', version: 3, revision: 'a'.repeat(64), feature: 'editor', offset: 2, snippet: '合成小说正文。', aliases: [] };
const response = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
function backend(extra?: (url: string, init?: RequestInit) => Promise<Response> | Response | undefined) {
  return vi.fn(async (url: string, init?: RequestInit) => extra?.(url, init) || response(url.endsWith('/resume') ? resume : url.includes('/search?') ? { items: [row], mode: 'LITERAL_LEXICAL', truncated: false, branch_sources_available: true } : { items: [] }));
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
describe('real workspace tools UI', () => {
  it('saves explicit chapter metadata and note with CAS, never manuscript or token', async () => {
    const fetch = backend(); vi.stubGlobal('fetch', fetch);
    render(<WorkspaceToolsPanel client={experimentalClient('novel', { sessionToken: 'private-token' })} chapter={chapter} currentAnchor={{ offset: 2, scroll: 10 }} />);
    await screen.findByText('明天检查旧信', { selector: 'textarea' });
    fireEvent.change(screen.getByLabelText('停止点与下次要做的事'), { target: { value: '继续第三章' } });
    fireEvent.click(screen.getByRole('button', { name: '保存工作现场' }));
    await screen.findByText('工作现场已保存。正文仍由编辑器保存。');
    const put = fetch.mock.calls.find(([, init]) => init?.method === 'PUT')!;
    expect(JSON.parse(String(put[1]?.body))).toMatchObject({ expected_version: 1, chapter_id: chapter.id, chapter_version: 3, anchor: { offset: 2, scroll: 10 }, stopping_note: '继续第三章' });
    expect(put[1]?.body).not.toContain('private-token'); expect(put[1]?.body).not.toContain(chapter.content);
  });
  it('restores a verified anchor under StrictMode and does not automatically run models', async () => {
    const navigate = vi.fn(), fetch = backend(url => url.endsWith('/resume/resolve') ? response({ kind: 'chapter', id: chapter.id, version: 3, anchor: { offset: 2, scroll: 10 } }) : undefined);
    vi.stubGlobal('fetch', fetch);
    render(<StrictMode><WorkspaceToolsPanel client={experimentalClient('novel', { sessionToken: '' })} chapter={chapter} onNavigate={navigate} /></StrictMode>);
    await screen.findByRole('button', { name: '恢复章节位置' });
    fireEvent.click(screen.getByRole('button', { name: '恢复章节位置' }));
    await waitFor(() => expect(navigate).toHaveBeenCalledWith({ kind: 'chapter', id: chapter.id, version: 3, anchor: { offset: 2, scroll: 10 } }));
    expect(fetch.mock.calls.every(([url]) => !url.includes('execute') && !url.includes('generate'))).toBe(true);
  });
  it('shows stale recovery choice and never jumps until explicit current-version approval', async () => {
    const navigate = vi.fn(); let resolves = 0;
    const fetch = backend((url, init) => {
      if (url.endsWith('/search/resolve')) {
        resolves++;
        return JSON.parse(String(init?.body)).open_current ? response({ kind: 'chapter', id: chapter.id, version: 4, anchor: { offset: 0, scroll: 0 } }) : response({ detail: { code: 'EXPERIMENTAL_SOURCE_STALE' } }, 409);
      }
    }); vi.stubGlobal('fetch', fetch);
    render(<WorkspaceToolsPanel client={experimentalClient('novel', { sessionToken: '' })} chapter={chapter} onNavigate={navigate} />);
    fireEvent.click(screen.getByRole('button', { name: '搜索与命令' }));
    fireEvent.click(await screen.findByRole('button', { name: '打开章节位置' }));
    await screen.findByRole('button', { name: '核对并打开当前版本' });
    expect(navigate).not.toHaveBeenCalled(); expect(resolves).toBe(1);
    fireEvent.click(screen.getByRole('button', { name: '核对并打开当前版本' }));
    await waitFor(() => expect(navigate).toHaveBeenCalledWith({ kind: 'chapter', id: chapter.id, version: 4, anchor: { offset: 0, scroll: 0 } }));
  });
  it('discards pending search and action responses after A → B → A scope changes', async () => {
    let resolveJump: (value: Response) => void = () => {};
    const fetch = backend(url => url.endsWith('/search/resolve') ? new Promise<Response>(resolve => { resolveJump = resolve; }) : undefined);
    vi.stubGlobal('fetch', fetch); const navigate = vi.fn();
    const a = experimentalClient('novel', { sessionToken: 'a', scope: { workspaceId: 'w', projectId: 'p', storylineId: 's', branchId: 'a' } });
    const b = experimentalClient('other', { sessionToken: 'b' });
    const rendered = render(<WorkspaceToolsPanel client={a} chapter={chapter} onNavigate={navigate} />);
    fireEvent.click(screen.getByRole('button', { name: '搜索与命令' }));
    fireEvent.click(await screen.findByRole('button', { name: '打开章节位置' }));
    rendered.rerender(<WorkspaceToolsPanel client={b} chapter={chapter} onNavigate={navigate} />);
    rendered.rerender(<WorkspaceToolsPanel client={a} chapter={chapter} onNavigate={navigate} />);
    await act(async () => resolveJump(response({ kind: 'chapter', id: 'old-secret-id', version: 3 })));
    expect(navigate).not.toHaveBeenCalled(); expect(screen.queryByText('old-secret-id')).toBeNull();
    expect(screen.getByRole('button', { name: '继续工作' }).getAttribute('aria-pressed')).toBe('true');
  });
  it('preserves notes typed before initial read and across same-scope refresh', async () => {
    let finish: (value: Response) => void = () => {};
    vi.stubGlobal('fetch', backend(url => url.endsWith('/resume') ? new Promise<Response>(resolve => { finish = resolve; }) : undefined));
    render(<WorkspaceToolsPanel client={experimentalClient('novel', { sessionToken: '' })} chapter={chapter} />);
    fireEvent.change(screen.getByLabelText('停止点与下次要做的事'), { target: { value: '刚刚输入，不能覆盖' } });
    await act(async () => finish(response(resume)));
    expect((screen.getByLabelText('停止点与下次要做的事') as HTMLTextAreaElement).value).toBe('刚刚输入，不能覆盖');
  });
  it('requires explicit diagnosis preview and invalidates it when selected fields change', async () => {
    const fetch = backend(url => url.endsWith('/diagnostics/preview') ? response({ schema: 'workspace-diagnostics-v1', uploaded: false, sections: { environment: { component: 'workspace_tools_v2', storage: 'file', scope_mode: 'local' }, task_states: [], error_codes: [] } }) : undefined);
    vi.stubGlobal('fetch', fetch);
    render(<WorkspaceToolsPanel client={experimentalClient('novel', { sessionToken: '' })} />);
    fireEvent.click(screen.getByRole('button', { name: '诊断包' }));
    expect(fetch.mock.calls.some(([url]) => url.includes('/diagnostics/'))).toBe(false);
    expect((screen.getByRole('button', { name: '导出已选诊断项' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: '生成诊断预览' }));
    await screen.findByRole('region', { name: '诊断预览' });
    await waitFor(() => expect((screen.getByRole('button', { name: '导出已选诊断项' }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByLabelText('任务阶段（不含标题与 ID）'));
    expect(screen.queryByRole('region', { name: '诊断预览' })).toBeNull();
    expect((screen.getByRole('button', { name: '导出已选诊断项' }) as HTMLButtonElement).disabled).toBe(true);
  });
  it('uses actual task status, unknown cost, manual source action and partial failure state', async () => {
    const fetch = backend(url => url.includes('/tasks?') ? response({ items: [{ id: 'job-real', authority: 'media', label: '图片任务', feature: 'assets', status: 'UNKNOWN', stage_label: '结果未知', progress: null, stale: false, history: [], lifecycle: '面板关闭不取消任务' }], unavailable: [{ authority: 'exports', label: '导出服务' }], truncated: false }) : undefined);
    vi.stubGlobal('fetch', fetch); const navigate = vi.fn();
    render(<WorkspaceToolsPanel client={experimentalClient('novel', { sessionToken: '' })} onNavigate={navigate} />);
    fireEvent.click(screen.getByRole('button', { name: '任务中心' }));
    await screen.findByText('结果未知'); await screen.findByText('导出服务暂时不可读，其他来源仍可使用。');
    expect(screen.getByText(/预估费用：未知 · 实际费用：未知/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '打开来源工具' }));
    expect(navigate).toHaveBeenCalledWith({ kind: 'feature', id: 'job-real', feature: 'assets' });
    expect(fetch.mock.calls.every(([, init]) => init?.method === 'GET')).toBe(true);
  });
  it('supports keyboard search results and only exposes enabled safe scenario navigation', async () => {
    const fetch = backend(); vi.stubGlobal('fetch', fetch);
    render(<WorkspaceToolsPanel client={experimentalClient('novel', { sessionToken: '' })} onNavigate={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: '搜索与命令' }));
    await screen.findByRole('button', { name: '打开章节位置' });
    fireEvent.keyDown(screen.getByLabelText('搜索中文名称、别名或正文'), { key: 'ArrowDown' });
    expect(document.activeElement).toBe(screen.getByRole('button', { name: '打开章节位置' }));
    fireEvent.click(screen.getByRole('button', { name: '使用指引' }));
    expect(screen.queryByRole('button', { name: '打开准备有声书' })).toBeNull();
    expect(screen.getByText('有声书实验入口未启用。引导不会开启服务端开关。')).toBeTruthy();
  });
  it('refreshes a conflict without overwriting the pending stopping note', async () => {
    let version = 1;
    const fetch = backend((url, init) => {
      if (url.endsWith('/resume') && init?.method === 'PUT') { version = 2; return response({ detail: { code: 'EXPERIMENTAL_VERSION_CONFLICT' } }, 409); }
      if (url.endsWith('/resume')) return response({ ...resume, item: { ...resume.item, version, stopping_note: version === 2 ? '另一端保存的笔记' : resume.item.stopping_note } });
    });
    vi.stubGlobal('fetch', fetch);
    render(<WorkspaceToolsPanel client={experimentalClient('novel', { sessionToken: '' })} chapter={chapter} />);
    await screen.findByText('现场 v1');
    fireEvent.change(screen.getByLabelText('停止点与下次要做的事'), { target: { value: '我的冲突候选' } });
    fireEvent.click(screen.getByRole('button', { name: '保存工作现场' }));
    await screen.findByRole('alert');
    expect((screen.getByLabelText('停止点与下次要做的事') as HTMLTextAreaElement).value).toBe('我的冲突候选');
    fireEvent.click(screen.getByRole('button', { name: '核对服务器现场（保留当前笔记）' }));
    await screen.findByText('现场 v2');
    expect((screen.getByLabelText('停止点与下次要做的事') as HTMLTextAreaElement).value).toBe('我的冲突候选');
  });
  it('honors explicit global search entry without overriding subsequent local section changes', async () => {
    vi.stubGlobal('fetch', backend());
    const client = experimentalClient('novel', { sessionToken: '' });
    const view = render(<WorkspaceToolsPanel client={client} initialSection="search" />);
    await screen.findByLabelText('搜索中文名称、别名或正文');
    expect(document.activeElement).toBe(screen.getByLabelText('搜索中文名称、别名或正文'));
    fireEvent.click(screen.getByRole('button', { name: '任务中心' }));
    view.rerender(<WorkspaceToolsPanel client={client} initialSection="search" />);
    expect(screen.getByRole('button', { name: '任务中心' }).getAttribute('aria-pressed')).toBe('true');
    view.rerender(<WorkspaceToolsPanel client={client} initialSection="diagnostics" />);
    expect(screen.getByRole('button', { name: '诊断包' }).getAttribute('aria-pressed')).toBe('true');
  });
  it('does not download an obsolete diagnosis export after unmount', async () => {
    let finish: (value: Response) => void = () => {};
    const createObjectURL = vi.fn(); vi.stubGlobal('URL', Object.assign(URL, { createObjectURL }));
    vi.stubGlobal('fetch', backend(url => url.endsWith('/diagnostics/preview') ? response({ schema: 'workspace-diagnostics-v1', preview_digest: 'a'.repeat(64), uploaded: false, sections: {} }) : url.endsWith('/diagnostics/export') ? new Promise<Response>(resolve => { finish = resolve; }) : undefined));
    const view = render(<WorkspaceToolsPanel client={experimentalClient('novel', { sessionToken: '' })} initialSection="diagnostics" />);
    fireEvent.click(screen.getByRole('button', { name: '生成诊断预览' }));
    await waitFor(() => expect((screen.getByRole('button', { name: '导出已选诊断项' }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole('button', { name: '导出已选诊断项' }));
    view.unmount();
    await act(async () => finish(response({ schema: 'workspace-diagnostics-v1', sections: {} })));
    expect(createObjectURL).not.toHaveBeenCalled();
  });

});

it('AUDIT ignores a search jump after the search panel is dismissed for a newer task view', async () => {
  let resolveJump: (value: Response) => void = () => {};
  vi.stubGlobal('fetch', backend(url => url.endsWith('/search/resolve') ? new Promise<Response>(resolve => { resolveJump = resolve; }) : url.includes('/tasks?') ? response({items: [], unavailable: [], truncated: false}) : undefined));
  const navigate = vi.fn();
  render(<WorkspaceToolsPanel client={experimentalClient('novel', { sessionToken: '' })} chapter={chapter} onNavigate={navigate} />);
  fireEvent.click(screen.getByRole('button', { name: '搜索与命令' }));
  fireEvent.click(await screen.findByRole('button', { name: '打开章节位置' }));
  fireEvent.click(screen.getByRole('button', { name: '任务中心' }));
  await act(async () => resolveJump(response({ kind: 'chapter', id: chapter.id, version: 3, anchor: { offset: 2, scroll: 10 } })));
  expect(navigate).not.toHaveBeenCalled();
});

it('keeps the newest safe command instead of a delayed search jump', async () => {
  let finish: (value: Response) => void = () => {};
  const fetch = backend(url => url.endsWith('/search/resolve') ? new Promise<Response>(resolve => { finish = resolve; }) : undefined);
  vi.stubGlobal('fetch', fetch); const navigate = vi.fn();
  render(<WorkspaceToolsPanel client={experimentalClient('novel', { sessionToken: '' })} initialSection="search" onNavigate={navigate} />);
  fireEvent.click(await screen.findByRole('button', { name: '打开章节位置' }));
  fireEvent.click(screen.getByRole('button', { name: '打开导出中心' }));
  expect(navigate).toHaveBeenCalledWith({ kind: 'feature', id: 'exports', feature: 'exports' });
  await act(async () => finish(response({ kind: 'chapter', id: 'old-chapter', version: 3 })));
  expect(navigate).toHaveBeenCalledTimes(1);
  expect(screen.queryByText('已请求打开来源')).toBeNull();
});

it('deduplicates repeated resolves and only honors the reopened search request', async () => {
  const pending: ((value: Response) => void)[] = [];
  const fetch = backend(url => url.endsWith('/search/resolve') ? new Promise<Response>(resolve => { pending.push(resolve); }) : url.includes('/tasks?') ? response({ items: [], unavailable: [], truncated: false }) : undefined);
  vi.stubGlobal('fetch', fetch); const navigate = vi.fn();
  render(<WorkspaceToolsPanel client={experimentalClient('novel', { sessionToken: '' })} initialSection="search" onNavigate={navigate} />);
  const open = await screen.findByRole('button', { name: '打开章节位置' });
  fireEvent.click(open); fireEvent.click(open);
  expect(pending).toHaveLength(1);
  fireEvent.click(screen.getByRole('button', { name: '任务中心' }));
  fireEvent.click(screen.getByRole('button', { name: '搜索与命令' }));
  fireEvent.click(await screen.findByRole('button', { name: '打开章节位置' }));
  expect(pending).toHaveLength(2);
  await act(async () => pending[1](response({ kind: 'chapter', id: 'new-chapter', version: 4 })));
  await act(async () => pending[0](response({ kind: 'chapter', id: 'old-chapter', version: 3 })));
  expect(navigate).toHaveBeenCalledTimes(1);
  expect(navigate).toHaveBeenCalledWith({ kind: 'chapter', id: 'new-chapter', version: 4 });
});

it('drops a delayed search jump after the query changes', async () => {
  let finish: (value: Response) => void = () => {};
  vi.stubGlobal('fetch', backend(url => url.endsWith('/search/resolve') ? new Promise<Response>(resolve => { finish = resolve; }) : undefined));
  const navigate = vi.fn();
  render(<WorkspaceToolsPanel client={experimentalClient('novel', { sessionToken: '' })} initialSection="search" onNavigate={navigate} />);
  fireEvent.click(await screen.findByRole('button', { name: '打开章节位置' }));
  fireEvent.change(screen.getByLabelText('搜索中文名称、别名或正文'), { target: { value: '新的查询' } });
  await act(async () => finish(response({ kind: 'chapter', id: 'old-chapter', version: 3 })));
  expect(navigate).not.toHaveBeenCalled();
  expect(screen.queryByText('已请求打开来源')).toBeNull();
});

it('does not restore a chapter after the resume section was dismissed and reopened', async () => {
  let finish: (value: Response) => void = () => {};
  vi.stubGlobal('fetch', backend(url => url.endsWith('/resume/resolve') ? new Promise<Response>(resolve => { finish = resolve; }) : url.includes('/tasks?') ? response({ items: [], unavailable: [], truncated: false }) : undefined));
  const navigate = vi.fn();
  render(<WorkspaceToolsPanel client={experimentalClient('novel', { sessionToken: '' })} onNavigate={navigate} />);
  fireEvent.click(await screen.findByRole('button', { name: '恢复章节位置' }));
  fireEvent.click(screen.getByRole('button', { name: '任务中心' }));
  fireEvent.click(screen.getByRole('button', { name: '继续工作' }));
  await act(async () => finish(response({ kind: 'chapter', id: 'old-chapter', version: 3 })));
  expect(navigate).not.toHaveBeenCalled();
});
