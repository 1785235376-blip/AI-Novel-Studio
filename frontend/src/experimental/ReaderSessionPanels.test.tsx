// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ReaderPreflightPanel } from './ReaderPreflightPanel';
import { WritingSessionPanel, NoticeCenterAddon } from './WritingSessionPanel';
import { defaultNoticePreferences, nextReminderAt, noticeSettingsChanged } from './writingSessionsClient';
import { experimentalClient } from './api';
const response = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
const settings = { version: 0, rules: { punctuation: true, repeated_words: true, literals: [] }, license_declaration: '', font_declaration: '' };
const chapter = { id: 'c', title: '港口', version: 2, revision: 'a'.repeat(64), paragraphs: [{ index: 0, offset: 0, text: '甲🙂。' }, { index: 1, offset: 4, text: '阿青！！' }] };
const reading = { chapters: [chapter], annotations: [], source_digest: 'source', branch_sources_available: true };
const findings = { items: [{ id: 'b'.repeat(64), chapter_id: 'c', revision: chapter.revision, offset: 6, quote: '！！', paragraph: 1, kind: 'punctuation', explanation: '核对连续标点', suggestion: null, ignored_reason: null }], truncated: false };
const active = { id: 'session', version: 1, status: 'ACTIVE', goal: '写结尾', tasks: [{ id: 't', text: '核对旧信', done: false }], stopping_note: '', target_characters: null, recap: null };
const overview = { items: [], truncated: false, project_goal: { current_words: 10, target_words: 1000, current_chapters: 1, target_chapters: 10 } };
const notice = { event_id: 'd'.repeat(64), kind: 'failure', priority: 'urgent', label: '导出任务', status: 'FAILED', task_id: 'job', authority: 'exports', feature: 'exports' };
function backend(extra?: (url: string, init?: RequestInit) => Promise<Response> | Response | undefined) {
  return vi.fn(async (url: string, init?: RequestInit) => extra?.(url, init) || response(url.endsWith('/reader-preflight/settings') ? settings : url.endsWith('/read') ? reading : url.endsWith('/proof') ? findings : url.endsWith('/preferences/notices') ? defaultNoticePreferences : url.includes('/notices?') ? { items: [notice], deferred_count: 0, unavailable: [] } : overview));
}
const client = (novel = 'novel') => experimentalClient(novel, { sessionToken: 'synthetic-session', scope: { workspaceId: 'w', projectId: 'novel', storylineId: 's', branchId: 'branch' } });
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('U11 real client request contracts', () => {
  it('offers contiguous reader, TOC keyboard focus and codepoint-exact server-validated jump', async () => {
    const navigate = vi.fn(), fetch = backend((url, init) => url.endsWith('/open') ? response({ kind: 'chapter', id: 'c', version: 2, anchor: { offset: JSON.parse(String(init?.body)).offset, scroll: 0 }, coordinate: 'EDITOR_TEXT_CODEPOINT' }) : undefined);
    vi.stubGlobal('fetch', fetch); render(<ReaderPreflightPanel client={client()} onNavigate={navigate} />);
    await screen.findByText('甲🙂。');
    fireEvent.click(screen.getByRole('button', { name: '港口' }));
    expect(document.activeElement?.tagName).toBe('ARTICLE');
    fireEvent.change(screen.getByLabelText('模拟阅读宽度'), { target: { value: '390' } });
    expect(document.querySelector('.reader-simulation')?.getAttribute('style')).toContain('390px');
    fireEvent.click(screen.getByRole('button', { name: '编辑器打开第 2 段' }));
    await waitFor(() => expect(navigate).toHaveBeenCalledWith(expect.objectContaining({ anchor: { offset: 4, scroll: 0 } })));
    const request = fetch.mock.calls.find(([url]) => url.endsWith('/open'))!;
    expect(JSON.parse(String(request[1]?.body))).toEqual({ chapter_id: 'c', revision: chapter.revision, offset: 4, quote: '阿青！！' });
    expect(new Headers(request[1]?.headers).get('X-Branch-Id')).toBe('branch');
  });
  it('submits bounded literal rule configuration and status-only preflight with no editor content', async () => {
    const fetch = backend((url, init) => url.endsWith('/settings') && init?.method === 'PUT' ? response({ ...settings, ...JSON.parse(String(init.body)), version: 1 }) : url.endsWith('/check') ? response({ findings: [], coverage: [{ area: 'generation_candidates', state: 'UNKNOWN' }], source_digest: 'source', checked_format: 'docx', has_integrity_blockers: false }) : undefined);
    vi.stubGlobal('fetch', fetch); render(<ReaderPreflightPanel client={client()} localDraftState={[{ chapter_id: 'c', chapter_version: 2, state: 'SAVE_FAILED' }]} />);
    await screen.findByLabelText('查找字面文字');
    fireEvent.change(screen.getByLabelText('查找字面文字'), { target: { value: '阿青' } });
    fireEvent.change(screen.getByLabelText('建议替换文字'), { target: { value: '船长' } });
    fireEvent.click(screen.getByRole('button', { name: '添加字面规则' }));
    fireEvent.click(screen.getByRole('button', { name: '保存规则与声明' }));
    await screen.findByText('规则与作者声明已保存；不会自动替换正文。');
    fireEvent.click(screen.getByRole('button', { name: '运行发布预检' }));
    await screen.findByText('generation_candidates：UNKNOWN');
    const body = JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/check'))![1]?.body));
    expect(body).toEqual({ format: 'docx', draft_status: [{ chapter_id: 'c', chapter_version: 2, state: 'SAVE_FAILED' }] });
    expect(JSON.stringify(body)).not.toContain('甲🙂');
    expect(fetch.mock.calls.every(([url]) => !/generate|execute|exports/.test(url))).toBe(true);
  });
  it('keeps annotation on permission failure and rejects stale source navigation', async () => {
    const navigate = vi.fn(), fetch = backend((url) => url.endsWith('/annotations') ? response({ detail: { code: 'FORBIDDEN' } }, 403) : url.endsWith('/open') ? response({ detail: { code: 'EXPERIMENTAL_SOURCE_STALE' } }, 409) : undefined);
    vi.stubGlobal('fetch', fetch); render(<ReaderPreflightPanel client={client()} onNavigate={navigate} />);
    fireEvent.click(await screen.findByRole('button', { name: '注释第 2 段' }));
    fireEvent.change(screen.getByLabelText('段落注释'), { target: { value: '保留我的注释' } });
    fireEvent.keyDown(screen.getByLabelText('段落注释'), { key: 'Enter', ctrlKey: true, isComposing: true });
    expect(fetch.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(0);
    fireEvent.click(screen.getByRole('button', { name: '保存注释' })); await screen.findByText(/FORBIDDEN/);
    expect((screen.getByLabelText('段落注释') as HTMLTextAreaElement).value).toBe('保留我的注释');
    fireEvent.click(screen.getByRole('button', { name: '编辑器打开第 2 段' })); await screen.findByText(/EXPERIMENTAL_SOURCE_STALE/);
    expect(navigate).not.toHaveBeenCalled();
  });
  it('scope change ignores late old read responses and clears private annotation inputs', async () => {
    let finish: (r: Response) => void = () => {}; const fetch = backend((url) => url.includes('/old/') && url.endsWith('/read') ? new Promise(resolve => { finish = resolve; }) : undefined);
    vi.stubGlobal('fetch', fetch); const ui = render(<ReaderPreflightPanel client={client('old')} />);
    ui.rerender(<ReaderPreflightPanel client={client('new')} />); await screen.findByText('甲🙂。');
    await act(async () => finish(response({ ...reading, chapters: [{ ...chapter, title: '旧作用域私密章节' }] })));
    expect(screen.queryByText('旧作用域私密章节')).toBeNull();
  });
});

describe('U15 persisted session and original task center', () => {
  it('starts an optional session and completes only through actual API writes', async () => {
    let rows: unknown[] = []; const fetch = backend((url, init) => {
      if (url.endsWith('/writing-sessions') && init?.method === 'POST') { rows = [active]; return response(active); }
      if (url.endsWith('/writing-sessions') && init?.method === 'GET') return response({ ...overview, items: rows });
      if (url.endsWith('/writing-sessions/session') && init?.method === 'PUT') { const input = JSON.parse(String(init.body)); const done = { ...active, ...input, version: 2, status: 'COMPLETED', completed_at: '2026-10-05T10:00:00Z', recap: { net_characters: 12, persisted_revision_events: 2, completed_checklist_items: 1, history_available: true } }; rows = [done]; return response(done); }
    }); vi.stubGlobal('fetch', fetch); render(<WritingSessionPanel client={client()} />);
    await screen.findByText(/原项目目标：10/);
    fireEvent.change(screen.getByLabelText('本次写作目标（可选）'), { target: { value: '写结尾' } });
    fireEvent.click(screen.getByRole('button', { name: '开始本次写作' })); await screen.findByLabelText('本次停止点笔记');
    fireEvent.click(screen.getByLabelText('核对旧信')); fireEvent.change(screen.getByLabelText('本次停止点笔记'), { target: { value: '下次修潮汐时间' } });
    fireEvent.click(screen.getByRole('button', { name: '结束本次写作并回顾' }));
    await screen.findByText(/实际保存历史事件 2 次/);
    const body = JSON.parse(String(fetch.mock.calls.find(([, init]) => init?.method === 'PUT')![1]?.body));
    expect(body).toMatchObject({ expected_version: 1, complete: true, stopping_note: '下次修潮汐时间', tasks: [{ done: true }] });
    expect(body).not.toHaveProperty('recap'); expect(body).not.toHaveProperty('model');
  });
  it('retains stopping note after CAS failure; refresh does not overwrite local edits', async () => {
    const fetch = backend((url, init) => url.endsWith('/writing-sessions') ? response({ ...overview, items: [active] }) : url.endsWith('/writing-sessions/session') && init?.method === 'PUT' ? response({ detail: { code: 'EXPERIMENTAL_VERSION_CONFLICT' } }, 409) : undefined);
    vi.stubGlobal('fetch', fetch); render(<WritingSessionPanel client={client()} />);
    const input = await screen.findByLabelText('本次停止点笔记'); fireEvent.change(input, { target: { value: '不能丢失的停止点' } });
    fireEvent.click(screen.getByRole('button', { name: '保存本次停止点' })); await screen.findByText(/EXPERIMENTAL_VERSION_CONFLICT/);
    fireEvent.click(screen.getByRole('button', { name: '核对服务器会话（保留未保存笔记）' }));
    expect((input as HTMLTextAreaElement).value).toBe('不能丢失的停止点');
  });
  it('focus asks server to defer nonurgent notices but never hides save failure', async () => {
    const fetch = backend((url) => url.includes('/notices?focus=true') ? response({ items: [notice], deferred_count: 2, unavailable: [] }) : undefined);
    vi.stubGlobal('fetch', fetch); render(<NoticeCenterAddon client={client()} focusActive saveFailure />);
    await screen.findByText(/专注模式延后 2 条/);
    expect(screen.getByText(/正文保存失败。请回到编辑器/)).toBeTruthy();
    expect(screen.getByText(/导出任务 · FAILED/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '知道了 job' }));
    await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.endsWith('/notices/acknowledge'))).toBe(true));
    const body = JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/notices/acknowledge'))![1]?.body));
    expect(body).toEqual({ expected_version: 0, event_id: notice.event_id });
  });
  it('has no default timer; an enabled reminder owns a timer which disabling or unmount clears', async () => {
    let preferences = { ...defaultNoticePreferences }; const fetch = backend((url) => url.endsWith('/preferences/notices') ? response(preferences) : undefined);
    vi.stubGlobal('fetch', fetch); vi.useFakeTimers(); vi.setSystemTime(new Date('2026-10-05T17:00:00Z'));
    const context = client(); const ui = render(<NoticeCenterAddon client={context} />);
    await act(async () => { for (let i = 0; i < 10; i++) await Promise.resolve(); });
    expect(vi.getTimerCount()).toBe(0);
    preferences = { ...defaultNoticePreferences, version: 1, reminder: { enabled: true, time: '18:00', timezone: 'UTC' } };
    await act(async () => { noticeSettingsChanged(context); for (let i = 0; i < 10; i++) await Promise.resolve(); });
    expect(vi.getTimerCount()).toBe(1);
    preferences = { ...defaultNoticePreferences, version: 2 };
    await act(async () => { noticeSettingsChanged(context); for (let i = 0; i < 10; i++) await Promise.resolve(); });
    expect(vi.getTimerCount()).toBe(0); ui.unmount(); expect(vi.getTimerCount()).toBe(0);
  });
  it('timezone calculation skips missed minutes and handles daylight-saving gap', () => {
    expect(new Date(nextReminderAt('18:00', 'Asia/Shanghai', Date.parse('2026-10-05T09:00:00Z'))!).toISOString()).toBe('2026-10-05T10:00:00.000Z');
    expect(new Date(nextReminderAt('18:00', 'UTC', Date.parse('2026-10-05T18:00:30Z'))!).toISOString()).toBe('2026-10-06T18:00:00.000Z');
    expect(new Date(nextReminderAt('02:30', 'America/New_York', Date.parse('2026-03-08T05:00:00Z'))!).toISOString()).toBe('2026-03-09T06:30:00.000Z');
  });
});
