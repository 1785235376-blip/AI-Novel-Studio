// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ExperimentalWorkbench, EXPERIMENTAL_GROUPS } from './ExperimentalWorkbench';
import { FeatureLauncher, FEATURE_GROUP_DEFAULTS } from '../ui/FeatureLauncher';
import type { ExperimentalFlags } from './api';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const flags = (key: string): ExperimentalFlags => ({ experimental: true, default_enabled: false, features: { [`experimental.${key}`]: true } });
describe('default-off Experimental UI', () => {
  it('does not mount any domain requests or tabs without server opt-in', () => {
    const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
    render(<ExperimentalWorkbench novelId="novel" context={{ sessionToken: '' }} />);
    expect(screen.getByText('Experimental 未启用')).toBeTruthy(); expect(screen.queryByRole('navigation', { name: '实验功能' })).toBeNull(); expect(fetch).not.toHaveBeenCalled();
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
