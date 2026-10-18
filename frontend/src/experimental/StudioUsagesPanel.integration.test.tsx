// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { ExperimentalClient } from './api';
import { ChangeImpactPanel } from './ChangeImpactPanel';
import { ProductionLineagePanel } from './ProductionLineagePanel';

const pin = { kind: 'ASSET', id: 'asset', version: 2, digest: 'a'.repeat(64), asset_kind: 'image' };
const graphItem = { owner: 'CREATIVE_GRAPH', id: 'studio-graph', version: 3, digest: 'c'.repeat(64), node_id: 'exact-node', definition_id: 'asset_reference', source: pin, current_source: pin, state: 'CURRENT' };
const response = (owner: string, items: unknown[]) => ({ owner, source: pin, items, coverage: 'EXACT_SAVED_DIRECT_ASSET_REFERENCES', truncated: false, limit: 200, read_only: true, automatic_regeneration: false, other_dependencies: 'UNKNOWN' });
const source = { kind: 'ASSET', id: 'asset', label: 'Image asset', binding: { version: 2, digest: 'a'.repeat(64) } };
const asset = { id: 'asset', label: 'Image asset', version: 2, kind: 'image', digest: 'a'.repeat(64), deleted: false, integrity: 'VERIFIED', origin: 'ORIGINAL_INPUT', license: { label: 'Author declaration', source: '', note: '' }, operation: '', parents: [], sources: [], stale: false, impact: { assets: [], usages: [{ id: 'legacy-brief', kind: 'MEDIA_BRIEF', label: 'Original media brief', version: 1 }], other_dependencies: 'UNKNOWN' } };
const node = { key: 'MEDIA_TASK:original-task', kind: 'MEDIA_TASK', id: 'original-task', label: 'Original task', version: 3, status: 'SUCCEEDED', stale: true, locked: false, lock_version: 0, refresh_candidate: true, refresh_reason: null, evidence: [] };
function client() {
  return { get: vi.fn(async (path: string) => {
    if (path.endsWith('/studio-graph-usages')) return response('CREATIVE_GRAPH', [graphItem]);
    if (path.endsWith('/studio-timeline-usages')) return response('STUDIO_TIMELINE', []);
    if (path === '/production/assets') return { items: [asset] };
    if (path === '/production/assets/asset') return asset;
    if (path === '/change-impact/sources') return { items: [source, { ...source, kind: 'CHAPTER', id: 'chapter', label: 'Chapter source' }] };
    if (path === '/change-impact/refreshes') return { items: [] };
    throw new Error(`Unexpected path: ${path}`);
  }), post: vi.fn(async (path: string) => {
    if (path === '/change-impact/query') return { source, items: [node], coverage: 'EXACT', inferred: [], unrecorded_dependencies: 'UNKNOWN', automatic_regeneration: false };
    if (path === '/change-impact/preflights') return { id: 'preflight', version: 1, ready: false, preflight_digest: 'b'.repeat(64), maximum_candidates: 1, items: [], cost: { estimate_microusd: null, currency: 'USD' }, verification: 'UNVERIFIED' };
    throw new Error(`Unexpected write: ${path}`);
  }), put: vi.fn(async () => ({ ...node, locked: true, lock_version: 1 })), blob: vi.fn() } as unknown as ExperimentalClient;
}
const studioRegion = () => screen.getByRole('region', { name: 'Studio 直接使用位置（只读）' });
const studioCalls = (api: ExperimentalClient) => vi.mocked(api.get).mock.calls.filter(([path]) => path.endsWith('/studio-graph-usages') || path.endsWith('/studio-timeline-usages'));
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('Studio usage integration stays separate from original impact contracts', () => {
  it('adds a lazy read-only section to lineage without changing old media usages, declaration, or navigation', async () => {
    const api = client(), navigate = vi.fn(); render(<ProductionLineagePanel client={api} onNavigate={navigate} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Image asset · v2' }));
    await screen.findByRole('region', { name: 'Studio 直接使用位置（只读）' });
    expect(studioCalls(api)).toHaveLength(0);
    const legacy = screen.getByRole('region', { name: '资产替换影响' });
    expect(within(legacy).getByText(/Original media brief/)).toBeTruthy();
    fireEvent.click(within(studioRegion()).getByRole('button', { name: '读取 Studio 使用位置' }));
    await screen.findByText('studio-graph');
    expect(within(legacy).queryByText('studio-graph')).toBeNull();
    expect(within(studioRegion()).queryByRole('checkbox')).toBeNull();
    expect(within(studioRegion()).getAllByRole('button')).toHaveLength(1);
    expect(screen.getByRole('button', { name: '保存来源声明' })).toBeTruthy();
    fireEvent.click(within(legacy).getByRole('button', { name: '查看媒体任务与审核' }));
    expect(navigate).toHaveBeenCalledWith({ kind: 'feature', id: 'cover_storyboard_generation', feature: 'cover_storyboard_generation' });
    expect(api.post).not.toHaveBeenCalled(); expect(api.put).not.toHaveBeenCalled();
  });

  it('clears lineage usage evidence when current asset details are refreshed to another version', async () => {
    const api = client(), get = api.get; render(<ProductionLineagePanel client={api} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Image asset · v2' }));
    fireEvent.click(await screen.findByRole('button', { name: '读取 Studio 使用位置' }));
    await screen.findByText('studio-graph');
    api.get = vi.fn(async (path: string, signal?: AbortSignal) => path === '/production/assets/asset' ? { ...asset, version: 3, digest: 'e'.repeat(64) } : get(path, signal)) as ExperimentalClient['get'];
    fireEvent.click(screen.getByRole('button', { name: '重新读取资产详情' }));
    await screen.findByRole('heading', { name: 'Image asset · v3' });
    expect(screen.queryByText('studio-graph')).toBeNull();
    expect(within(studioRegion()).getAllByText('尚未读取，使用覆盖未知。')).toHaveLength(2);
    expect(vi.mocked(get).mock.calls.filter(([path]) => path.includes('/studio-'))).toHaveLength(2);
    expect(studioCalls(api)).toHaveLength(0);
  });

  it('clears Studio evidence even when an explicit lineage refresh returns the same asset version', async () => {
    const api = client(); render(<ProductionLineagePanel client={api} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Image asset · v2' }));
    fireEvent.click(await screen.findByRole('button', { name: '读取 Studio 使用位置' }));
    await screen.findByText('studio-graph');
    fireEvent.click(screen.getByRole('button', { name: '重新读取资产详情' }));
    await screen.findByRole('button', { name: '读取 Studio 使用位置' });
    expect(screen.queryByText('studio-graph')).toBeNull();
    expect(within(studioRegion()).getAllByText('尚未读取，使用覆盖未知。')).toHaveLength(2);
    expect(studioCalls(api)).toHaveLength(2);
  });

  it('shows Studio only for ASSET sources and keeps its consumers out of original selection/lock/preflight targets', async () => {
    const api = client(); render(<ChangeImpactPanel client={api} />);
    fireEvent.change(await screen.findByLabelText('发生修改的来源'), { target: { value: 'CHAPTER:chapter' } });
    await screen.findByRole('checkbox', { name: /Original task/ });
    expect(screen.queryByRole('region', { name: 'Studio 直接使用位置（只读）' })).toBeNull();
    fireEvent.change(screen.getByLabelText('发生修改的来源'), { target: { value: 'ASSET:asset' } });
    fireEvent.click(await screen.findByRole('button', { name: '读取 Studio 使用位置' }));
    await screen.findByText('studio-graph');
    const original = screen.getByLabelText('确切依赖');
    expect(within(original).queryByText('studio-graph')).toBeNull();
    expect(screen.getAllByRole('checkbox')).toHaveLength(1);
    expect(screen.getAllByRole('button', { name: '锁定满意成果' })).toHaveLength(1);
    expect(within(studioRegion()).queryByRole('checkbox')).toBeNull();
    fireEvent.click(screen.getByRole('checkbox', { name: /Original task/ }));
    fireEvent.click(screen.getByRole('button', { name: '预检选中的 1 项' }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/change-impact/preflights', { source: { kind: 'ASSET', id: 'asset' }, selected: [{ key: node.key, expected_version: node.version }] }));
    expect(api.put).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '锁定满意成果' }));
    await waitFor(() => expect(api.put).toHaveBeenCalledWith('/change-impact/locks', { key: node.key, expected_version: node.version, expected_lock_version: 0, locked: true }));
    await screen.findByRole('button', { name: '读取 Studio 使用位置' });
    expect(screen.queryByText('studio-graph')).toBeNull();
    expect(studioCalls(api)).toHaveLength(2);
  });

  it('uses the current queried ASSET binding and resets Studio reads when impact is refreshed', async () => {
    const api = client(); render(<ChangeImpactPanel client={api} />);
    fireEvent.change(await screen.findByLabelText('发生修改的来源'), { target: { value: 'ASSET:asset' } });
    fireEvent.click(await screen.findByRole('button', { name: '读取 Studio 使用位置' }));
    await screen.findByText('studio-graph');
    vi.mocked(api.post).mockResolvedValue({ source: { ...source, binding: { version: 3, digest: 'f'.repeat(64) } }, items: [node], inferred: [], unrecorded_dependencies: 'UNKNOWN' });
    fireEvent.click(screen.getByRole('button', { name: '重新读取影响与版本' }));
    await screen.findByRole('button', { name: '读取 Studio 使用位置' });
    expect(screen.queryByText('studio-graph')).toBeNull();
    expect(studioCalls(api)).toHaveLength(2);
    expect(screen.getByRole('button', { name: '预检选中的 0 项' })).toBeTruthy();
  });

  it('does not issue Studio reads or reveal the panel through read-only ChangeImpact access', () => {
    const api = client(); render(<ChangeImpactPanel client={api} readOnly />);
    expect(api.get).not.toHaveBeenCalled(); expect(api.post).not.toHaveBeenCalled();
    expect(screen.queryByRole('region', { name: 'Studio 直接使用位置（只读）' })).toBeNull();
  });
});
