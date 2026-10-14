// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import type { AssetBrowserClient } from './assetBrowserTypes';
import { relationshipGraph, sampleAssets } from './assetBrowserFixtures';
import { useAssetBrowser, type AssetBrowserControllerProps } from './useAssetBrowser';

type Fake = {
  listAssets: ReturnType<typeof vi.fn>;
  readAsset: ReturnType<typeof vi.fn>;
  readRelationships: ReturnType<typeof vi.fn>;
};
function fakeClient(patch: Partial<Fake> = {}): { client: AssetBrowserClient } & Fake {
  const client: Fake = {
    listAssets: vi.fn(async () => sampleAssets()),
    readAsset: vi.fn(async (assetId: string) => sampleAssets().find(asset => asset.id === assetId)),
    readRelationships: vi.fn(async () => relationshipGraph()),
    ...patch,
  };
  return { client: client as unknown as AssetBrowserClient, ...client };
}
const props = (client: AssetBrowserClient, patch: Partial<AssetBrowserControllerProps> = {}): AssetBrowserControllerProps => ({
  projectId: 'novel-ux03', client, identity: 'assetbrowser-test', active: true, denied: false, busy: false,
  isCurrent: () => true, read: work => work(), scopeKey: 'novel-ux03', ...patch,
});
const mount = (client: AssetBrowserClient, patch: Partial<AssetBrowserControllerProps> = {}) =>
  renderHook((props_: AssetBrowserControllerProps) => useAssetBrowser(props_), { initialProps: props(client, patch) });

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('asset browser controller', () => {
  it('reads the bounded list once and becomes READY', async () => {
    const { client, listAssets } = fakeClient();
    const { result } = mount(client);
    await waitFor(() => expect(result.current.state).toBe('READY'));
    expect(listAssets).toHaveBeenCalledTimes(1);
    expect(result.current.rows).toHaveLength(3);
    // 引用情况**没有**被顺带读取：未读就是未核实，不是 0。
    expect(result.current.referenceState).toBe('IDLE');
    expect(result.current.rows.every(row => row.reference_counts === null)).toBe(true);
  });

  it('reports a genuinely empty library as EMPTY', async () => {
    const { client } = fakeClient({ listAssets: vi.fn(async () => []) });
    const { result } = mount(client);
    await waitFor(() => expect(result.current.state).toBe('EMPTY'));
    expect(result.current.rows).toHaveLength(0);
  });

  it('never renders a denied read as an empty library', async () => {
    const onUnavailable = vi.fn();
    const { client } = fakeClient({ listAssets: vi.fn(async () => {
      throw new ApiError({ status: 403, code: 'CREATIVE_AUTHORITY_CHANGED', message: '身份或项目范围已经变化。' });
    }) });
    const { result } = mount(client, { onUnavailable });
    await waitFor(() => expect(result.current.state).toBe('DENIED'));
    expect(result.current.state).not.toBe('EMPTY');
    expect(result.current.problem?.code).toBe('CREATIVE_AUTHORITY_CHANGED');
    expect(onUnavailable).toHaveBeenCalled();
  });

  it('treats a 404 as DENIED / unavailable, never as EMPTY', async () => {
    const { client } = fakeClient({ listAssets: vi.fn(async () => {
      throw new ApiError({ status: 404, code: 'STUDIO_REQUEST_FAILED', message: '记录不可用。' });
    }) });
    const { result } = mount(client);
    await waitFor(() => expect(result.current.state).toBe('DENIED'));
    expect(result.current.rows).toHaveLength(0);
  });

  it('reports a non-authority failure as FAILED, never as EMPTY', async () => {
    const { client } = fakeClient({ listAssets: vi.fn(async () => { throw new Error('boom'); }) });
    const { result } = mount(client);
    await waitFor(() => expect(result.current.state).toBe('FAILED'));
    expect(result.current.problem?.message).toBeTruthy();
  });

  it('reads detail on demand only, and keeps the selection when the read fails', async () => {
    const failing = vi.fn(async () => { throw new ApiError({ status: 500, code: 'STUDIO_REQUEST_FAILED', message: '详情读取失败。' }); });
    const { client, readAsset } = fakeClient({ readAsset: failing });
    const { result } = mount(client);
    await waitFor(() => expect(result.current.state).toBe('READY'));
    expect(readAsset).not.toHaveBeenCalled();

    act(() => { result.current.select('asset-a'); });
    await waitFor(() => expect(result.current.detailState).toBe('FAILED'));
    // 失败的预览**不**改变当前选择，也不清空列表。
    expect(result.current.selectedId).toBe('asset-a');
    expect(result.current.rows).toHaveLength(3);
    expect(result.current.detailProblem?.code).toBe('STUDIO_REQUEST_FAILED');
    expect(readAsset).toHaveBeenCalledTimes(1);
    expect(readAsset.mock.calls[0][0]).toBe('asset-a');
  });

  it('reads exactly one detail per selection, never the whole library', async () => {
    const { client, readAsset } = fakeClient();
    const { result } = mount(client);
    await waitFor(() => expect(result.current.state).toBe('READY'));
    act(() => { result.current.select('asset-a'); });
    await waitFor(() => expect(result.current.detailState).toBe('READY'));
    act(() => { result.current.select('asset-b'); });
    await waitFor(() => expect(result.current.detail?.id).toBe('asset-b'));
    expect(readAsset).toHaveBeenCalledTimes(2);
    expect(readAsset.mock.calls.map(call => call[0])).toEqual(['asset-a', 'asset-b']);
  });

  it('keeps reference counts unverified when the relationship read fails', async () => {
    const { client } = fakeClient({ readRelationships: vi.fn(async () => {
      throw new ApiError({ status: 500, code: 'ASSET_BROWSER_RELATIONSHIPS_INVALID', message: '引用关系不可用。' });
    }) });
    const { result } = mount(client);
    await waitFor(() => expect(result.current.state).toBe('READY'));
    expect(result.current.referenceState).toBe('IDLE');
    await act(async () => { await result.current.loadReferences(); });
    expect(result.current.referenceState).toBe('FAILED');
    expect(result.current.referencesUnverified).toBe(true);
    // 引用不可读 ≠ 未被引用：计数保持 null，影响面保持 undefined。
    expect(result.current.rows.every(row => row.reference_counts === null)).toBe(true);
    expect(result.current.impact()).toBeUndefined();
    expect(result.current.deleteImpact()).toBeUndefined();
    expect(result.current.facets.reference_unverified).toBe(3);
  });

  it('stamps reference counts after a successful relationship read and exposes the impact', async () => {
    const { client } = fakeClient();
    const { result } = mount(client);
    await waitFor(() => expect(result.current.state).toBe('READY'));
    await act(async () => { await result.current.loadReferences(); });
    expect(result.current.referenceState).toBe('READY');
    const onA = result.current.rows.find(row => row.id === 'asset-a');
    expect(onA?.reference_counts?.total).toBe(2);
    act(() => { result.current.select('asset-a'); });
    await waitFor(() => expect(result.current.detailState).toBe('READY'));
    const impact = result.current.impact();
    expect(impact?.total).toBe(2);
    expect(impact?.automatic_update).toBe(false);
    const deletion = result.current.deleteImpact();
    expect(deletion?.physical_delete).toBe(false);
    expect(deletion?.content_removed).toBe(false);
  });

  it('paginates with a bounded page size and only reveals more rows', async () => {
    const rows = Array.from({ length: 30 }, (_, index) => ({ id: `asset-${index}` }));
    const base = sampleAssets()[0];
    const many = rows.map(row => ({ ...base, id: row.id, filename: `${row.id}.png` }));
    const { client } = fakeClient({ listAssets: vi.fn(async () => many) });
    const { result } = mount(client);
    await waitFor(() => expect(result.current.state).toBe('READY'));
    expect(result.current.pageRows).toHaveLength(24);
    expect(result.current.more).toBe(true);
    act(() => { result.current.loadMore(); });
    expect(result.current.pageRows).toHaveLength(30);
    expect(result.current.more).toBe(false);
    // 页大小永远有界。
    act(() => { result.current.changePageSize(1); });
    expect(result.current.pageSize).toBe(8);
    act(() => { result.current.changePageSize(10_000); });
    expect(result.current.pageSize).toBe(200);
  });

  it('filters locally without issuing another read', async () => {
    const { client, listAssets } = fakeClient();
    const { result } = mount(client);
    await waitFor(() => expect(result.current.state).toBe('READY'));
    act(() => { result.current.setQuery('theme'); });
    await waitFor(() => expect(result.current.filtered).toHaveLength(1));
    expect(result.current.filtered[0].id).toBe('asset-b');
    act(() => { result.current.setMediaKind('image'); });
    expect(result.current.filtered).toHaveLength(0);
    // 清除筛选只清"面"，搜索词按作者意图保留。
    act(() => { result.current.resetFilters(); });
    expect(result.current.filtered).toHaveLength(1);
    expect(result.current.filters.query).toBe('theme');
    act(() => { result.current.setQuery(''); });
    expect(result.current.filtered).toHaveLength(3);
    expect(listAssets).toHaveBeenCalledTimes(1);
  });

  it('does not read anything while the view is closed or denied', async () => {
    const closed = fakeClient();
    mount(closed.client, { active: false });
    await new Promise(resolve => setTimeout(resolve, 0));
    expect(closed.listAssets).not.toHaveBeenCalled();
    cleanup();

    const denied = fakeClient();
    const { result } = mount(denied.client, { denied: true });
    expect(result.current.state).toBe('DENIED');
    expect(denied.listAssets).not.toHaveBeenCalled();
  });

  it('clears every previously read value when the identity changes', async () => {
    const { client } = fakeClient();
    const { result, rerender } = mount(client);
    await waitFor(() => expect(result.current.state).toBe('READY'));
    rerender(props(client, { identity: 'another-branch' }));
    await waitFor(() => expect(result.current.rows).toHaveLength(3));
    expect(result.current.selectedId).toBeNull();
    expect(result.current.detailState).toBe('IDLE');
    expect(result.current.referenceState).toBe('IDLE');
  });

  it('computes the send-to pre-check locally without any network call', async () => {
    const { client, listAssets } = fakeClient();
    const { result } = mount(client);
    await waitFor(() => expect(result.current.state).toBe('READY'));
    act(() => { result.current.select('asset-a'); });
    const allowed = result.current.sendTo('IMAGE');
    expect(allowed?.allowed).toBe(true);
    expect(allowed?.allowed === true ? allowed.reference : null).toEqual({
      asset_id: 'asset-a', version: 3, digest: sampleAssets()[0].digest,
    });
    const audio = result.current.sendTo('IMAGE', 'asset-b');
    expect(audio?.allowed).toBe(false);
    // 预检是纯本地的：没有新的读取。
    expect(listAssets).toHaveBeenCalledTimes(1);
  });
});
