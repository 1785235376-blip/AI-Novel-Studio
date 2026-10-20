// @vitest-environment jsdom
import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { WritingFocusPanel, WritingReferenceRail, defaultWritingPreferences } from './WritingFocusPanel';
import { experimentalClient } from './api';
import type { Chapter } from '../api';
const chapter: Chapter = { id: 'chapter', novel_id: 'novel', title: '海港', number: 1, content: '真实合成正文', document: {}, version: 2, word_count: 6, status: 'DRAFT' };
const preferences = { version: 1, preferences: defaultWritingPreferences, pins: [], recovery_required: false };
const card = { kind: 'character', id: 'qing', revision: 'a'.repeat(64), title: '阿青', text: '身份：船长', read_only: true, truncated: false, privacy_level: 'LOCAL_ONLY' };
const note = { id: 'note', capture_id: 'saved-capture', version: 1, title: '旧信', text: '让旧信指向失踪的船。', status: 'DRAFT', chapter_id: null, chapter_version: null, source_state: 'NONE', included_in_ai_context: false, canon: false, copies: [] };
const flags = { experimental: true, default_enabled: false as const, features: { 'experimental.advanced_planning_v2': true } };
const response = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
function backend(extra?: (url: string, init?: RequestInit) => Promise<Response> | Response | undefined) {
  return vi.fn(async (url: string, init?: RequestInit) => extra?.(url, init) || response(url.endsWith('/preferences') ? preferences : url.includes('/references?') ? { items: [card], branch_sources_available: true, truncated: false } : url.includes('/notes?') ? { items: [note], truncated: false } : url.endsWith('/planning-targets') ? { items: [{ id: 'node', title: '海港规划', level: 'PROJECT', version: 3 }] } : { items: [] }));
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const client = () => experimentalClient('novel', { sessionToken: 'synthetic-session' });

describe('U04 actual writing focus controls', () => {
  it('loads under StrictMode, applies prose preferences and persists versioned personal settings', async () => {
    const change = vi.fn(), fetch = backend((url, init) => url.endsWith('/preferences') && init?.method === 'PUT' ? response({ ...preferences, version: 2, ...JSON.parse(String(init.body)) }) : undefined);
    vi.stubGlobal('fetch', fetch);
    render(<StrictMode><WritingFocusPanel client={client()} chapter={chapter} onPreferencesChange={change} /></StrictMode>);
    await waitFor(() => expect(change).toHaveBeenCalledWith(defaultWritingPreferences));
    fireEvent.change(screen.getByLabelText('正文字号'), { target: { value: '24' } });
    expect(change).toHaveBeenLastCalledWith({ ...defaultWritingPreferences, font_size: 24 });
    fireEvent.click(screen.getByLabelText('段落聚焦（突出光标所在段落）'));
    fireEvent.click(screen.getByRole('button', { name: '保存阅读偏好' }));
    await screen.findByText('阅读偏好已保存。正文和选区未改变。');
    const save = fetch.mock.calls.find(([, init]) => init?.method === 'PUT')!;
    expect(JSON.parse(String(save[1]?.body))).toMatchObject({ expected_version: 1, preferences: { font_size: 24, paragraph_focus: true }, pins: [] });
    expect(save[1]?.body).not.toContain('synthetic-session'); expect(save[1]?.body).not.toContain(chapter.content);
    expect(fetch.mock.calls.every(([url]) => !url.includes('generate'))).toBe(true);
  });
  it('toggles the host existing editor without submitting or writing manuscript', async () => {
    const focus = vi.fn(), fetch = backend(); vi.stubGlobal('fetch', fetch);
    const context = client();
    const ui = render(<WritingFocusPanel client={context} focusActive={false} onFocusChange={focus} />);
    fireEvent.click(screen.getByRole('button', { name: '进入专注' }));
    expect(focus).toHaveBeenCalledWith(true);
    ui.rerender(<WritingFocusPanel client={context} focusActive onFocusChange={focus} />);
    fireEvent.click(screen.getByRole('button', { name: '退出专注' }));
    expect(focus).toHaveBeenLastCalledWith(false);
    expect(fetch.mock.calls.every(([, init]) => init?.method === 'GET')).toBe(true);
  });
  it('preserves preference changes before initial loading and after conflict refresh', async () => {
    let finish: (value: Response) => void = () => {};
    let reads = 0;
    const fetch = backend((url, init) => {
      if (url.endsWith('/preferences') && init?.method === 'PUT') return response({ detail: { code: 'EXPERIMENTAL_VERSION_CONFLICT' } }, 409);
      if (url.endsWith('/preferences')) return ++reads === 1 ? new Promise(resolve => { finish = resolve; }) : response({ ...preferences, version: 3 });
    }); vi.stubGlobal('fetch', fetch);
    render(<WritingFocusPanel client={client()} />);
    fireEvent.change(screen.getByLabelText('阅读列宽'), { target: { value: 'narrow' } });
    await act(async () => finish(response(preferences)));
    expect((screen.getByLabelText('阅读列宽') as HTMLSelectElement).value).toBe('narrow');
    fireEvent.click(screen.getByRole('button', { name: '保存阅读偏好' }));
    await screen.findByText(/EXPERIMENTAL_VERSION_CONFLICT/);
    fireEvent.click(screen.getByRole('button', { name: '核对服务器偏好' }));
    await waitFor(() => expect(reads).toBe(2));
    expect((screen.getByLabelText('阅读列宽') as HTMLSelectElement).value).toBe('narrow');
  });
  it('pins only source identity and revision, preserving unrelated unsaved typography', async () => {
    const changed = vi.fn(), fetch = backend((url, init) => url.endsWith('/preferences') && init?.method === 'PUT' ? response({ ...JSON.parse(String(init.body)), version: 2 }) : undefined);
    vi.stubGlobal('fetch', fetch);
    render(<WritingFocusPanel client={client()} onReferencesChange={changed} />);
    const pin = await screen.findByRole('button', { name: '固定 阿青' });
    await waitFor(() => expect((pin as HTMLButtonElement).disabled).toBe(false));
    fireEvent.change(screen.getByLabelText('正文字号'), { target: { value: '24' } });
    fireEvent.click(pin);
    await waitFor(() => expect(changed).toHaveBeenCalled());
    const body = JSON.parse(String(fetch.mock.calls.find(([, init]) => init?.method === 'PUT')![1]?.body));
    expect(body.pins).toEqual([{ kind: 'character', id: 'qing', revision: card.revision }]);
    expect(body.preferences.font_size).toBe(18);
    expect((screen.getByLabelText('正文字号') as HTMLSelectElement).value).toBe('24');
  });
  it('keeps inspiration input on save failure and only saves on explicit action', async () => {
    const fetch = backend((url, init) => url.endsWith('/notes') && init?.method === 'POST' ? response({ detail: { code: 'FORBIDDEN' } }, 403) : undefined);
    vi.stubGlobal('fetch', fetch);
    render(<WritingFocusPanel client={client()} chapter={chapter} />);
    fireEvent.change(screen.getByLabelText('灵感内容'), { target: { value: '新灵感仍然需要保留' } });
    fireEvent.click(screen.getByLabelText('关联当前已保存章节「海港」v2'));
    expect(fetch.mock.calls.every(([, init]) => init?.method === 'GET')).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: '保存灵感草稿' }));
    await screen.findByText(/FORBIDDEN/);
    expect((screen.getByLabelText('灵感内容') as HTMLTextAreaElement).value).toBe('新灵感仍然需要保留');
    const save = JSON.parse(String(fetch.mock.calls.find(([, init]) => init?.method === 'POST')![1]?.body));
    expect(save).toMatchObject({ text: '新灵感仍然需要保留', chapter_id: 'chapter', chapter_version: 2 });
    expect(save).not.toHaveProperty('canon'); expect(save).not.toHaveProperty('actor');
  });
  it('does not submit Ctrl+Enter while IME is composing; duplicate clicks are fenced', async () => {
    let finish: (value: Response) => void = () => {};
    const fetch = backend((url, init) => url.endsWith('/notes') && init?.method === 'POST' ? new Promise(resolve => { finish = resolve; }) : undefined); vi.stubGlobal('fetch', fetch);
    render(<WritingFocusPanel client={client()} />);
    const content = screen.getByLabelText('灵感内容');
    fireEvent.change(content, { target: { value: '正在输入中文' } });
    fireEvent.keyDown(content, { key: 'Enter', ctrlKey: true, isComposing: true });
    expect(fetch.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(0);
    fireEvent.keyDown(content, { key: 'Enter', ctrlKey: true });
    fireEvent.keyDown(content, { key: 'Enter', ctrlKey: true });
    expect(fetch.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1);
    fireEvent.change(content, { target: { value: '请求期间又输入了内容' } });
    await act(async () => finish(response(note, 201)));
    expect((content as HTMLTextAreaElement).value).toBe('请求期间又输入了内容');
  });
  it('requires selected target, reviewed preview and explicit copy; never approves the proposal', async () => {
    const fetch = backend((url, init) => url.endsWith('/planning/preview') ? response({ preview_digest: 'b'.repeat(64), field: 'goal', before: '寻找船长', after: '寻找船长\n旧信指向失踪的船', target_title: '海港规划', note_version: 1, target_version: 3, status_after_copy: 'REVIEW' }) : url.endsWith('/planning/copy') ? response({ proposal_id: 'proposal', status: 'REVIEW', note }) : undefined); vi.stubGlobal('fetch', fetch);
    render(<WritingFocusPanel client={client()} flags={flags} />);
    fireEvent.click(await screen.findByRole('button', { name: '核对并复制到规划 旧信' }));
    await screen.findByRole('option', { name: '海港规划 · PROJECT · v3' });
    fireEvent.change(screen.getByLabelText('目标规划节点'), { target: { value: 'node' } });
    fireEvent.click(screen.getByRole('button', { name: '预览规划草稿' }));
    const copyButton = await screen.findByRole('button', { name: '确认复制为待审规划' });
    expect((copyButton as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByLabelText('已核对「海港规划」v3 和上述内容'));
    fireEvent.click(copyButton);
    await waitFor(() => expect(screen.queryByRole('region', { name: '灵感复制审核' })).toBeNull());
    const request = fetch.mock.calls.find(([url]) => url.endsWith('/planning/copy'))!;
    expect(JSON.parse(String(request[1]?.body))).toEqual({ expected_version: 1, node_id: 'node', expected_node_version: 3, field: 'goal', preview_digest: 'b'.repeat(64) });
    expect(fetch.mock.calls.every(([url]) => !url.includes('/approve') && !url.includes('/generate'))).toBe(true);
  });
  it('invalidates copy preview when field changes and on stale response', async () => {
    const fetch = backend(url => url.endsWith('/planning/preview') ? response({ preview_digest: 'b'.repeat(64), before: '', after: '新计划', target_title: '海港规划', target_version: 3 }) : url.endsWith('/planning/copy') ? response({ detail: { code: 'EXPERIMENTAL_SOURCE_STALE' } }, 409) : undefined); vi.stubGlobal('fetch', fetch);
    render(<WritingFocusPanel client={client()} flags={flags} />);
    fireEvent.click(await screen.findByRole('button', { name: '核对并复制到规划 旧信' }));
    await screen.findByRole('option', { name: /海港规划/ });
    fireEvent.change(screen.getByLabelText('目标规划节点'), { target: { value: 'node' } });
    fireEvent.click(screen.getByRole('button', { name: '预览规划草稿' }));
    await screen.findByRole('button', { name: '确认复制为待审规划' });
    fireEvent.change(screen.getByLabelText('追加到规划字段'), { target: { value: 'conflict' } });
    expect(screen.queryByRole('button', { name: '确认复制为待审规划' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '预览规划草稿' }));
    fireEvent.click(await screen.findByLabelText('已核对「海港规划」v3 和上述内容'));
    fireEvent.click(screen.getByRole('button', { name: '确认复制为待审规划' }));
    await screen.findByText(/EXPERIMENTAL_SOURCE_STALE/);
    expect(screen.queryByRole('button', { name: '确认复制为待审规划' })).toBeNull();
    expect(screen.getByText(note.text)).toBeTruthy();
  });
  it('rejects old A → B → A preference callbacks and private reference responses', async () => {
    const finishes: ((value: Response) => void)[] = [];
    const fetch = backend(url => url.endsWith('/preferences') ? new Promise(resolve => finishes.push(resolve)) : undefined); vi.stubGlobal('fetch', fetch);
    const change = vi.fn(), a = client(), b = experimentalClient('other', { sessionToken: 'b' });
    const ui = render(<WritingFocusPanel client={a} onPreferencesChange={change} />);
    ui.rerender(<WritingFocusPanel client={b} onPreferencesChange={change} />);
    ui.rerender(<WritingFocusPanel client={a} onPreferencesChange={change} />);
    await act(async () => { finishes[0](response({ ...preferences, preferences: { ...defaultWritingPreferences, font_size: 24 } })); finishes[1](response(preferences)); });
    expect(change).not.toHaveBeenCalled();
    await act(async () => finishes[2](response(preferences)));
    expect(change).toHaveBeenCalledTimes(1);
  });
  it('reference rail is readonly, removes stale cards and shows recoverable permission errors', async () => {
    let reads = 0;
    vi.stubGlobal('fetch', backend(url => url.endsWith('/pins') ? ++reads === 1 ? response({ items: [{ ...card, state: 'READY', card }] }) : reads === 2 ? response({ items: [{ ...card, state: 'STALE', card: null }] }) : response({ detail: { code: 'FORBIDDEN' } }, 403) : undefined));
    render(<StrictMode><WritingReferenceRail client={client()} /></StrictMode>);
    // StrictMode cancels its first read; the second read is the current evidence.
    await screen.findByText('来源已变化，请到“专注写作”重新核对并固定。');
    expect(screen.queryByText('身份：船长')).toBeNull();
    expect(screen.queryByRole('textbox')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '刷新参考' }));
    await screen.findByText(/FORBIDDEN/);
    expect(screen.queryByText('阿青')).toBeNull();
  });
});

describe('U04 reuses existing chapter and scene navigation', () => {
  const overview = { items: [{ id: chapter.id, title: chapter.title, version: chapter.version, revision: 'd'.repeat(64), word_count: 6, scene_count: 1, scenes_truncated: false, scenes: [{ id: 'existing-scene', title: '码头相遇', chapter_id: chapter.id, sequence: 1, purpose: '建立信任', conflict: '隐瞒来意', outcome: '暂时合作' }] }], truncated: false, chapter_sources_available: true, scene_sources_available: true };
  it('shows existing scene IDs without new scene writes and bookmarks through existing pins', async () => {
    const navigate = vi.fn();
    const fetch = backend((url, init) => url.includes('/overview') ? response(overview) : url.endsWith('/preferences') && init?.method === 'PUT' ? response({ ...JSON.parse(String(init.body)), version: 2 }) : url.endsWith('/bookmarks/open') ? response({ kind: 'chapter', id: chapter.id, version: chapter.version, anchor: { offset: 0, scroll: 0 }, coordinate: 'EDITOR_TEXT_CODEPOINT' }) : undefined);
    vi.stubGlobal('fetch', fetch);
    render(<WritingFocusPanel client={client()} chapter={chapter} onNavigate={navigate} />);
    await screen.findByRole('region', { name: '场景概览 码头相遇' });
    expect(screen.getByText('建立信任')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '设为章节书签 海港' }));
    await screen.findByText('章节书签已保存，共用固定资料，不复制正文。');
    const body = JSON.parse(String(fetch.mock.calls.find(([, init]) => init?.method === 'PUT')![1]?.body));
    expect(body.pins).toEqual([{ kind: 'chapter', id: chapter.id, revision: 'd'.repeat(64) }]);
    fireEvent.click(screen.getByRole('button', { name: '打开概览章节 海港' }));
    await waitFor(() => expect(navigate).toHaveBeenCalledWith({ kind: 'chapter', id: chapter.id, version: chapter.version, anchor: { offset: 0, scroll: 0 }, coordinate: 'EDITOR_TEXT_CODEPOINT' }));
    expect(fetch.mock.calls.every(([url]) => !url.includes('/scenes/'))).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: '打开故事资料库' }));
    expect(navigate).toHaveBeenLastCalledWith({ kind: 'feature', id: 'story', feature: 'story' });
  });
  it('requires explicit current-version recovery for stale bookmarks', async () => {
    const navigate = vi.fn();
    const fetch = backend(url => url.endsWith('/pins') ? response({ items: [{ kind: 'chapter', id: chapter.id, revision: 'c'.repeat(64), title: '海港', state: 'STALE', card: null }] }) : url.endsWith('/bookmarks/open') ? response({ kind: 'chapter', id: chapter.id, version: 4, anchor: { offset: 0, scroll: 0 } }) : undefined);
    vi.stubGlobal('fetch', fetch);
    render(<WritingFocusPanel client={client()} chapter={chapter} onNavigate={navigate} />);
    await waitFor(() => expect(fetch.mock.calls.filter(([url]) => url.endsWith('/pins'))).toHaveLength(2));
    expect(navigate).not.toHaveBeenCalled();
    fireEvent.click(await screen.findByRole('button', { name: '核对并打开当前版本 海港' }));
    await waitFor(() => expect(navigate).toHaveBeenCalled());
    expect(JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/bookmarks/open'))![1]?.body))).toEqual({ id: chapter.id, revision: 'c'.repeat(64), open_current: true });
  });
  it('discards a pending bookmark response after chapter A → B → A', async () => {
    let finish: (value: Response) => void = () => {};
    const navigate = vi.fn(), context = client();
    vi.stubGlobal('fetch', backend(url => url.includes('/overview') ? response(overview) : url.endsWith('/bookmarks/open') ? new Promise(resolve => { finish = resolve; }) : undefined));
    const view = render(<WritingFocusPanel client={context} chapter={chapter} onNavigate={navigate} />);
    fireEvent.click(await screen.findByRole('button', { name: '打开概览章节 海港' }));
    view.rerender(<WritingFocusPanel client={context} chapter={{ ...chapter, id: 'second' }} onNavigate={navigate} />);
    view.rerender(<WritingFocusPanel client={context} chapter={chapter} onNavigate={navigate} />);
    await act(async () => finish(response({ kind: 'chapter', id: 'old-response', version: 2 })));
    expect(navigate).not.toHaveBeenCalled();
  });
});
