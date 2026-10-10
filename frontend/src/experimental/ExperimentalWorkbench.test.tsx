// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ExperimentalWorkbench, EXPERIMENTAL_GROUPS, EXPERIMENTAL_TABS } from './ExperimentalWorkbench';
import { FeatureLauncher, FEATURE_GROUP_DEFAULTS } from '../ui/FeatureLauncher';
import type { Chapter } from '../api';
import type { ExperimentalFlags } from './api';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const flags = (...keys: string[]): ExperimentalFlags => ({ experimental: true, default_enabled: false, features: Object.fromEntries(keys.map(key => [`experimental.${key}`, true])) });
describe('default-off Experimental UI', () => {
  it('does not mount any domain requests or tabs without server opt-in', () => {
    const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
    render(<ExperimentalWorkbench novelId="novel" context={{ sessionToken: '' }} />);
    expect(screen.getByText('Experimental 未启用')).toBeTruthy(); expect(screen.queryByRole('navigation', { name: '实验功能' })).toBeNull(); expect(fetch).not.toHaveBeenCalled();
    expect(screen.queryByRole('searchbox', { name: '查找已启用工具' })).toBeNull();
  });
  it('keeps the inherited launcher unchanged without opt-in', () => {
    render(<FeatureLauncher selectedId="history" expandedGroups={FEATURE_GROUP_DEFAULTS} onSelect={() => {}} onToggleGroup={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: '打开功能导航' }));
    expect(screen.queryByText('实验工作台')).toBeNull(); expect(screen.getByText('版本历史')).toBeTruthy();
  });
  it('adds only an optional consumer group', () => {
    render(<FeatureLauncher selectedId="experimental" expandedGroups={{ ...FEATURE_GROUP_DEFAULTS, experimental: true }} extraGroups={EXPERIMENTAL_GROUPS} onSelect={() => {}} onToggleGroup={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: '打开功能导航' }));
    expect(screen.getByRole('button', { name: '实验工作台' }).getAttribute('aria-current')).toBe('page');
  });
  it('shows NOT_CONFIGURED honestly and cannot issue an embedding query', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(url.endsWith('/status') ? { status: 'NOT_CONFIGURED', capability: null, lexical_fallback: false } : { items: [] }), { status: 200 })));
    render(<ExperimentalWorkbench novelId="novel" context={{ sessionToken: '' }} flags={flags('visual_embeddings')} />);
    await screen.findByText('NOT_CONFIGURED');
    expect((screen.getByRole('button', { name: '查询向量' }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByRole('button', { name: '分层规划' })).toBeNull();
  });
  it('uses the domain batch allowlist and reports partial results without retrying', async () => {
    const row = { id: 'review-1', domain: 'world', version: 2, status: 'REVIEW', preview: '待核对世界记录', allowed_actions: ['approve', 'reject'], batch_safe: true, batch_actions: ['reject'], stale: false };
    const fetch = vi.fn(async (_url: string, request: RequestInit) => new Response(JSON.stringify(request.method === 'POST' ? { status: 'PARTIAL', results: [{ id: 'review-1', status: 'FAILED', code: 'VERSION_CONFLICT' }], remaining: 1 } : { items: [row] }), { status: 200 }));
    vi.stubGlobal('fetch', fetch);
    render(<ExperimentalWorkbench novelId="novel" context={{ sessionToken: '' }} flags={flags('unified_review_inbox')} />);
    fireEvent.click(await screen.findByRole('checkbox', { name: '加入安全批量审核' }));
    expect((screen.getByRole('button', { name: '批量批准已选审核项' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: '批量驳回已选审核项' }));
    await screen.findByText('PARTIAL · 未处理 1');
    const writes = fetch.mock.calls.filter(([, request]) => request.method === 'POST');
    expect(writes).toHaveLength(1); expect(writes[0][0]).toBe('/api/novels/novel/experimental/review-inbox/batch');
    expect(JSON.parse(writes[0][1].body as string)).toEqual({ items: [{ domain: 'world', id: 'review-1', action: 'reject', expected_version: 2 }] });
  });
  it('keeps failed forms and conflict messages visible for explicit retry', async () => {
    vi.stubGlobal('fetch', vi.fn(async (_url: string, request: RequestInit) => request.method === 'POST' ? new Response(JSON.stringify({ detail: { code: 'STALE_SOURCE' } }), { status: 409 }) : new Response(JSON.stringify({ items: [] }), { status: 200 })));
    render(<ExperimentalWorkbench novelId="novel" context={{ sessionToken: '' }} flags={flags('advanced_planning_v2')} />);
    await waitFor(() => expect((screen.getByRole('button', { name: '创建项目规划' }) as HTMLButtonElement).disabled).toBe(true));
    fireEvent.change(screen.getByLabelText('规划名称'), { target: { value: '保留我的规划' } }); await waitFor(() => expect((screen.getByRole('button', { name: '创建项目规划' }) as HTMLButtonElement).disabled).toBe(false)); fireEvent.click(screen.getByRole('button', { name: '创建项目规划' }));
    await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('STALE_SOURCE'));
    expect((screen.getByLabelText('规划名称') as HTMLInputElement).value).toBe('保留我的规划');
  });
});

describe('enabled tool discovery', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(url.endsWith('/embeddings/status') ? { status: 'NOT_CONFIGURED', capability: null } : { items: [] }), { status: 200 })));
  });
  const navigation = () => within(screen.getByRole('navigation', { name: '实验功能' }));
  const query = () => screen.getByRole('searchbox', { name: '查找已启用工具' }) as HTMLInputElement;
  const search = (value: string) => fireEvent.change(query(), { target: { value } });
  const settled = () => waitFor(() => expect(screen.queryByText('正在读取…')).toBeNull());

  it('preserves every enabled navigation button and its order for an empty query', async () => {
    render(<ExperimentalWorkbench novelId="novel" context={{ sessionToken: '' }} flags={flags(...EXPERIMENTAL_TABS.map(([key]) => key))} />);
    await settled();
    expect(navigation().getAllByRole('button').map(button => button.textContent)).toEqual(EXPERIMENTAL_TABS.map(([, label]) => label));
    expect(navigation().getByRole('button', { name: '分层规划' }).getAttribute('aria-pressed')).toBe('true');
    expect(query().value).toBe('');
    expect((screen.getByRole('button', { name: '清除筛选' }) as HTMLButtonElement).disabled).toBe(true);
    search('   ');
    expect(navigation().getAllByRole('button')).toHaveLength(EXPERIMENTAL_TABS.length);
  });

  it('matches Chinese labels and normalized, case-insensitive feature identities locally', async () => {
    render(<ExperimentalWorkbench novelId="novel" context={{ sessionToken: '' }} flags={flags('advanced_planning_v2', 'style_dna_v2', 'visual_embeddings')} />);
    await settled();
    const reads = vi.mocked(fetch).mock.calls.length;
    for (const value of ['风格', '  STYLE  ＤＮＡ  ', 'EXPERIMENTAL.STYLE_DNA_V2']) {
      search(value);
      expect(navigation().getAllByRole('button').map(button => button.textContent)).toEqual(['风格档案']);
      expect(screen.getByText('找到 1 / 3 个已启用工具。')).toBeTruthy();
    }
    expect(fetch).toHaveBeenCalledTimes(reads);
    expect(screen.getByRole('heading', { name: '分层创作规划 V2' })).toBeTruthy();
  });

  it('keeps the mounted draft, current selection, and originating scope while filtering or clearing', async () => {
    const onNavigate = vi.fn();
    render(<ExperimentalWorkbench novelId="novel" context={{ sessionToken: 'synthetic-session', scope: { workspaceId: 'workspace', projectId: 'novel', storylineId: 'story', branchId: 'origin-branch' } }} flags={flags('advanced_planning_v2', 'visual_embeddings')} onNavigate={onNavigate} />);
    await settled();
    const draft = screen.getByLabelText('规划名称') as HTMLInputElement;
    fireEvent.change(draft, { target: { value: '尚未提交的规划草稿' } });
    const reads = vi.mocked(fetch).mock.calls.length;
    search('不存在的工具');
    expect(navigation().queryAllByRole('button')).toHaveLength(0);
    expect(screen.getByText('没有匹配的已启用工具。请更换关键词或清除筛选。')).toBeTruthy();
    expect(screen.getByText('仅筛选下方入口；当前工具：分层规划。')).toBeTruthy();
    expect(screen.getByLabelText('规划名称')).toBe(draft);
    expect(draft.value).toBe('尚未提交的规划草稿');
    expect(fetch).toHaveBeenCalledTimes(reads);
    expect(onNavigate).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '清除筛选' }));
    expect(query().value).toBe(''); expect(document.activeElement).toBe(query());
    expect(navigation().getAllByRole('button')).toHaveLength(2);
    expect(navigation().getByRole('button', { name: '分层规划' }).getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByLabelText('规划名称')).toBe(draft); expect(draft.value).toBe('尚未提交的规划草稿');
    fireEvent.click(screen.getByRole('button', { name: '刷新实验记录' })); await settled();
    for (const [url, request] of vi.mocked(fetch).mock.calls) {
      expect(url).toMatch(/^\/api\/novels\/novel\/experimental\/planning\//);
      expect(request?.method).toBe('GET');
      expect(request?.headers).toMatchObject({ 'X-Session-Token': 'synthetic-session', 'X-Branch-Id': 'origin-branch' });
    }
  });

  it('clears the filter after explicit tool selection and preserves the ordinary selected state', async () => {
    render(<ExperimentalWorkbench novelId="novel" context={{ sessionToken: '' }} flags={flags('advanced_planning_v2', 'visual_embeddings')} />);
    await settled(); search('embedding');
    const tool = navigation().getByRole('button', { name: '视觉 Embedding' });
    expect(tool.getAttribute('type')).toBe('button');
    tool.focus(); expect(document.activeElement).toBe(tool);
    fireEvent.click(tool);
    await screen.findByText('NOT_CONFIGURED');
    expect(query().value).toBe(''); expect(navigation().getAllByRole('button')).toHaveLength(2);
    expect(navigation().getByRole('button', { name: '视觉 Embedding' }).getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByText('仅筛选下方入口；当前工具：视觉 Embedding。')).toBeTruthy();
  });

  it('preserves the editor selection receipt and a pending revision candidate while typing', async () => {
    const chapter = { id: 'novel:1', novel_id: 'novel', title: '合成章节', version: 4 } as Chapter;
    const selection = { from: 1, to: 5, text: '甲🙂乙' };
    const selected = { chapter_id: chapter.id, chapter_version: 4, from_pos: selection.from, to_pos: selection.to, text: selection.text };
    const block = { anchor_id: 'a'.repeat(64), path: [0], before: selection.text, after: selection.text, from_pos: 1, to_pos: 5, status: 'PENDING', lock_state: 'UNLOCKED', diff: [], diff_method: 'EXACT_CODEPOINT_DIFF' };
    const transport = vi.fn(async (url: string, init: RequestInit) => new Response(JSON.stringify(url.endsWith('/selection') ? { selection: selected, selection_digest: 'b'.repeat(64), blocks: [block], model_called: false, coordinate_contract: 'PROSEMIRROR_UTF16_V1' } : url.includes('/catalog') ? { chapters: [chapter], blocks: [], branch_sources_available: true } : { items: [] }), { status: 200 }));
    vi.stubGlobal('fetch', transport);
    const onChapterSaved = vi.fn();
    render(<ExperimentalWorkbench novelId="novel" context={{ sessionToken: '' }} flags={flags('advanced_planning_v2', 'revision_intelligence_v2')} requestedTab="revision_intelligence_v2" chapter={chapter} currentSelection={selection} saved onChapterSaved={onChapterSaved} />);
    await settled();
    fireEvent.click(screen.getByRole('button', { name: '校验编辑器选区' }));
    const candidate = await screen.findByLabelText('区块 1 候选文字') as HTMLTextAreaElement;
    fireEvent.change(candidate, { target: { value: '仍待审核的选区候选' } });
    const calls = transport.mock.calls.length;
    search('分层'); search('没有结果');
    expect(screen.getByLabelText('区块 1 候选文字')).toBe(candidate);
    expect(candidate.value).toBe('仍待审核的选区候选');
    expect(transport).toHaveBeenCalledTimes(calls); expect(onChapterSaved).not.toHaveBeenCalled();
    const selectionWrite = transport.mock.calls.find(([url]) => url.endsWith('/selection'))!;
    expect(JSON.parse(selectionWrite[1].body as string)).toEqual(selected);
    expect(transport.mock.calls.filter(([, init]) => init.method !== 'GET')).toEqual([selectionWrite]);
  });

  it('honors external requestedTab navigation even when its entry was filtered out', async () => {
    const props = { novelId: 'novel', context: { sessionToken: '' }, flags: flags('advanced_planning_v2', 'visual_embeddings') };
    const { rerender } = render(<ExperimentalWorkbench {...props} requestedTab="advanced_planning_v2" />);
    await settled(); search('没有匹配');
    rerender(<ExperimentalWorkbench {...props} requestedTab="visual_embeddings" />);
    await screen.findByText('NOT_CONFIGURED');
    expect(query().value).toBe(''); expect(navigation().getAllByRole('button')).toHaveLength(2);
    expect(navigation().getByRole('button', { name: '视觉 Embedding' }).getAttribute('aria-pressed')).toBe('true');
  });

  it('never reveals disabled or unregistered tools and retains flag-based fallback after revocation', async () => {
    const enabledFlags = { ...flags('advanced_planning_v2', 'visual_embeddings', 'unregistered_future_tool'), features: { ...flags('advanced_planning_v2', 'visual_embeddings', 'unregistered_future_tool').features, 'experimental.audiobook_v2': false } };
    const props = { novelId: 'novel', context: { sessionToken: '' } };
    const { rerender } = render(<ExperimentalWorkbench {...props} flags={enabledFlags} requestedTab="visual_embeddings" />);
    await settled();
    for (const value of ['有声书', 'audiobook_v2', 'unregistered_future_tool']) {
      search(value); expect(navigation().queryAllByRole('button')).toHaveLength(0);
    }
    search('embedding');
    rerender(<ExperimentalWorkbench {...props} flags={flags('advanced_planning_v2')} requestedTab="visual_embeddings" />);
    await settled();
    expect(navigation().queryAllByRole('button')).toHaveLength(0);
    expect(screen.queryByRole('heading', { name: '可选视觉 Embedding' })).toBeNull();
    expect(screen.getByRole('heading', { name: '分层创作规划 V2' })).toBeTruthy();
    expect(screen.getByText('仅筛选下方入口；当前工具：分层规划。')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '清除筛选' }));
    expect(navigation().getAllByRole('button').map(button => button.textContent)).toEqual(['分层规划']);
    rerender(<ExperimentalWorkbench {...props} flags={{ experimental: false, default_enabled: false, features: {} }} requestedTab="visual_embeddings" />);
    expect(screen.getByText('Experimental 未启用')).toBeTruthy();
    expect(screen.queryByRole('searchbox')).toBeNull();
  });

  it('does not navigate, submit, or issue requests when Enter confirms an IME query', async () => {
    render(<ExperimentalWorkbench novelId="novel" context={{ sessionToken: '' }} flags={flags('advanced_planning_v2', 'visual_embeddings')} />);
    await settled();
    const draft = screen.getByLabelText('规划名称') as HTMLInputElement;
    fireEvent.change(draft, { target: { value: 'IME 草稿' } });
    const reads = vi.mocked(fetch).mock.calls.length;
    query().focus(); fireEvent.compositionStart(query()); search('视觉');
    fireEvent.keyDown(query(), { key: 'Enter', code: 'Enter', keyCode: 229, isComposing: true });
    fireEvent.compositionEnd(query(), { data: '视觉' });
    fireEvent.keyDown(query(), { key: 'Enter', code: 'Enter' });
    expect(query().value).toBe('视觉'); expect(document.activeElement).toBe(query());
    expect(screen.getByLabelText('规划名称')).toBe(draft); expect(draft.value).toBe('IME 草稿');
    expect(screen.queryByRole('heading', { name: '可选视觉 Embedding' })).toBeNull();
    expect(fetch).toHaveBeenCalledTimes(reads);
  });
});
