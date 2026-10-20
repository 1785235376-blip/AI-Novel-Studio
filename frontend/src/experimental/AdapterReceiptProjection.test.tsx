// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { experimentalClient } from './api';
import { InboxPanel } from './InboxPanel';
import { WorkspaceToolsPanel } from './WorkspaceToolsPanel';
import { defaultLayout, formalAdapterNotice } from './uxClient';

const response = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
const domains = ['research_analysis', 'visual_identity'] as const;
const receipt = (domain: string) => ({ id: domain + '-receipt', authority: domain, label: domain === 'research_analysis' ? 'Research 原分析回执' : '视觉身份原比较回执', feature: domain === 'research_analysis' ? 'research_library_v2' : 'visual_embeddings', status: 'NOT_CONFIGURED', stage_label: '未配置', version: 1, progress: null, stale: false, history: [], lifecycle: '不会自动运行、恢复或批准。', revision: 'a'.repeat(64), actions: ['cancel'], navigation_contract: 'FORMAL_SOURCE_ONLY', source_domain: domain });
const saved = (items: unknown[]) => ({ availability: 'READY', item: { id: 'resume', version: 1, chapter_id: null, chapter_version: null, anchor: { offset: 0, scroll: 0 }, layout: defaultLayout, stopping_note: '', pinned_chapter_ids: [], recent_commands: [], guide_dismissed: false, updated_at: '2026-10-07', pending_tasks: items } });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('formal-only adapter receipt surfaces', () => {
  it.each(domains)('does not manufacture an exact source-open action for %s or its aggregate review task', async domain => {
    const task = receipt(domain), aggregate = { ...task, id: 'aggregate-' + task.id, authority: 'review_inbox', actions: [] };
    const legacy = { ...receipt('legacy'), id: 'legacy-real', authority: 'media', label: '既有媒体任务', navigation_contract: undefined, source_domain: undefined, actions: ['open_source'], source: { kind: 'feature', feature: 'assets', id: 'legacy-real' } };
    const fetch = vi.fn(async (url: string) => response(url.includes('/tasks?') ? { items: [task, aggregate, legacy], unavailable: [], truncated: false } : { item: null, availability: 'EMPTY' }));
    vi.stubGlobal('fetch', fetch); const navigate = vi.fn();
    render(<WorkspaceToolsPanel client={experimentalClient('novel', { sessionToken: '' })} initialSection="tasks" onNavigate={navigate} />);
    await screen.findByText('既有媒体任务');
    expect(screen.getAllByText(formalAdapterNotice(domain))).toHaveLength(2);
    expect(screen.getAllByRole('button', { name: '打开来源工具' })).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: '打开来源工具' }));
    expect(navigate).toHaveBeenCalledTimes(1); expect(navigate).toHaveBeenCalledWith(legacy.source);
    expect(fetch.mock.calls.every(([url]) => !url.includes('/run') && !url.includes('/review') && !url.includes('/recover'))).toBe(true);
  });

  it.each(domains)('keeps resume pending %s receipts formal-only', async domain => {
    vi.stubGlobal('fetch', vi.fn(async () => response(saved([receipt(domain)])))); const navigate = vi.fn();
    render(<WorkspaceToolsPanel client={experimentalClient('novel', { sessionToken: '' })} onNavigate={navigate} />);
    await screen.findByText(formalAdapterNotice(domain));
    const pending = screen.getByRole('region', { name: '上次未决任务' });
    expect(within(pending).queryByRole('button', { name: /查看原任务工具|恢复原生成草稿/ })).toBeNull();
    expect(navigate).not.toHaveBeenCalled();
  });

  it.each(domains)('shows original-domain review requirements for %s without generic approval', async domain => {
    const row = { ...receipt(domain), domain, preview: '', source_versions: { receipt_version: 1 }, allowed_actions: [], batch_safe: false, batch_actions: [], target: { id: domain + '-receipt', domain, navigation_contract: 'FORMAL_SOURCE_ONLY' } };
    const fetch = vi.fn(async () => response({ items: [row], unavailable: [] })); vi.stubGlobal('fetch', fetch);
    render(<InboxPanel client={experimentalClient('novel', { sessionToken: '' })} />);
    await screen.findByText(formalAdapterNotice(domain));
    expect(screen.queryByRole('button', { name: '批准此审核项' })).toBeNull();
    expect(screen.queryByRole('checkbox', { name: '加入安全批量审核' })).toBeNull();
    expect((screen.getByRole('button', { name: '批量批准已选审核项' }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByRole('button', { name: /打开来源/ })).toBeNull();
    expect(screen.getByRole('option', { name: domain })).toBeTruthy();
    expect(fetch.mock.calls).toHaveLength(1);
  });

  it('dispatches an explicit original cancellation with the captured revision, then refreshes', async () => {
    const item = receipt('research_analysis'); let cancelled = false;
    const fetch = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith('/cancel')) { cancelled = true; return response({ cancellation_requested: true, item: { ...item, status: 'CANCELLED', actions: [] } }); }
      if (url.includes('/tasks?')) return response({ items: [{ ...item, ...(cancelled ? { status: 'CANCELLED', stage_label: '已取消', actions: [] } : {}) }], unavailable: [], truncated: false });
      return response({ item: null, availability: 'EMPTY' });
    });
    vi.stubGlobal('fetch', fetch);
    render(<WorkspaceToolsPanel client={experimentalClient('novel', { sessionToken: '' })} initialSection="tasks" onNavigate={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: '取消原任务' }));
    fireEvent.click(screen.getByRole('button', { name: '确认请求取消' }));
    await screen.findByText('已取消');
    expect(fetch.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1);
    expect(JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/cancel'))![1]?.body))).toEqual({ expected_revision: item.revision });
    expect(screen.queryByRole('button', { name: '打开来源工具' })).toBeNull();
  });

  it('clears formal receipt rows on a denied refresh and discards late prior-scope reads', async () => {
    let denied = false, finish: (value: Response) => void = () => {};
    const first = experimentalClient('one', { sessionToken: 'a' }), second = experimentalClient('two', { sessionToken: 'b' });
    const fetch = vi.fn(async (url: string) => {
      if (!url.includes('/tasks?')) return response({ item: null, availability: 'EMPTY' });
      if (url.includes('/novels/two/')) return new Promise<Response>(resolve => { finish = resolve; });
      return denied ? response({ detail: { code: 'PERMISSION_DENIED' } }, 403) : response({ items: [receipt('visual_identity')], unavailable: [], truncated: false });
    });
    vi.stubGlobal('fetch', fetch);
    const rendered = render(<WorkspaceToolsPanel client={first} initialSection="tasks" onNavigate={vi.fn()} />);
    await screen.findByText(formalAdapterNotice('visual_identity'));
    denied = true; fireEvent.click(screen.getByRole('button', { name: '刷新任务' }));
    await waitFor(() => expect(screen.queryByText('任务 ID：visual_identity-receipt')).toBeNull());
    rendered.rerender(<WorkspaceToolsPanel client={second} initialSection="tasks" onNavigate={vi.fn()} />);
    rendered.rerender(<WorkspaceToolsPanel client={first} initialSection="tasks" onNavigate={vi.fn()} />);
    await act(async () => finish(response({ items: [receipt('research_analysis')], unavailable: [] })));
    expect(screen.queryByText('任务 ID：research_analysis-receipt')).toBeNull();
  });
});
