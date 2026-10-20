// @vitest-environment jsdom
import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import type { ExperimentalClient } from './api';
import { StudioUsagesPanel } from './StudioUsagesPanel';

const assetId = 'asset/with space';
const currentDigest = 'a'.repeat(64), recordedDigest = 'b'.repeat(64), graphDigest = 'c'.repeat(64), timelineDigest = 'd'.repeat(64);
const pin = { kind: 'ASSET', id: assetId, version: 2, digest: currentDigest, asset_kind: 'image' };
const graphItem = { owner: 'CREATIVE_GRAPH', id: 'saved-graph', version: 3, digest: graphDigest, node_id: 'reference-node', definition_id: 'asset_reference', source: { ...pin, version: 1, digest: recordedDigest }, current_source: pin, state: 'STALE' };
const timelineItem = { owner: 'STUDIO_TIMELINE', id: 'saved-timeline', version: 4, digest: timelineDigest, track_id: 'image-track', clip_id: 'exact-clip', source: pin, current_source: pin, state: 'CURRENT' };
const response = (owner: string, items: unknown[], source = pin) => ({ owner, source, items, coverage: 'EXACT_SAVED_DIRECT_ASSET_REFERENCES', truncated: false, limit: 200, read_only: true, automatic_regeneration: false, other_dependencies: 'UNKNOWN' });
const graph = () => response('CREATIVE_GRAPH', [graphItem]);
const timeline = () => response('STUDIO_TIMELINE', [timelineItem]);
function client() {
  return { get: vi.fn(async (path: string) => path.endsWith('/studio-graph-usages') ? graph() : timeline()), post: vi.fn(), put: vi.fn(), blob: vi.fn() } as unknown as ExperimentalClient;
}
function pending() {
  let resolve!: (value: unknown) => void;
  let reject!: (value: unknown) => void;
  const promise = new Promise<unknown>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
function read() { fireEvent.click(screen.getByRole('button', { name: /^(重新)?读取 Studio 使用位置$/ })); }
const graphRegion = () => screen.getByRole('region', { name: 'Studio 图定义使用覆盖' });
const timelineRegion = () => screen.getByRole('region', { name: 'Studio 时间线使用覆盖' });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('StudioUsagesPanel exact read-only bounded coverage', () => {
  it('reads lazily through the captured client and shows exact consumers and pins without actions', async () => {
    const api = client(); render(<StrictMode><StudioUsagesPanel client={api} assetId={assetId} sourceIdentity="v2" /></StrictMode>);
    expect(api.get).not.toHaveBeenCalled();
    expect(screen.getAllByText('尚未读取，使用覆盖未知。')).toHaveLength(2);
    read();
    await screen.findByText('saved-graph');
    expect(api.get).toHaveBeenCalledTimes(2);
    expect(api.get).toHaveBeenCalledWith('/production/assets/asset%2Fwith%20space/studio-graph-usages', expect.any(AbortSignal));
    expect(api.get).toHaveBeenCalledWith('/production/assets/asset%2Fwith%20space/studio-timeline-usages', expect.any(AbortSignal));
    for (const value of [graphDigest, 'reference-node', 'asset_reference', 'v3']) expect(within(graphRegion()).getByText(value)).toBeTruthy();
    for (const value of [timelineDigest, 'image-track', 'exact-clip', 'v4']) expect(within(timelineRegion()).getByText(value)).toBeTruthy();
    expect(within(graphRegion()).getByText(new RegExp(recordedDigest))).toBeTruthy();
    expect(within(graphRegion()).getByText(new RegExp(currentDigest))).toBeTruthy();
    expect(screen.getByText('STALE · 来源版本已变化')).toBeTruthy();
    expect(screen.getByText('CURRENT · 已保存引用与当前来源一致')).toBeTruthy();
    expect(screen.getByText(/不递归包含衍生资产/)).toBeTruthy();
    expect(screen.queryByRole('checkbox')).toBeNull();
    expect(screen.queryByRole('link')).toBeNull();
    expect(screen.getAllByRole('button')).toHaveLength(1);
    expect(api.post).not.toHaveBeenCalled(); expect(api.put).not.toHaveBeenCalled(); expect(api.blob).not.toHaveBeenCalled();
  });

  it('distinguishes an authorized empty projection from unavailable coverage', async () => {
    const api = client(); vi.mocked(api.get).mockImplementation(async path => response(path.endsWith('/studio-graph-usages') ? 'CREATIVE_GRAPH' : 'STUDIO_TIMELINE', []));
    render(<StudioUsagesPanel client={api} assetId={assetId} sourceIdentity="v2" />); read();
    expect(await screen.findAllByText('没有已记录的直接引用')).toHaveLength(2);
    expect(screen.getAllByText('本次返回 0 条已授权直接引用。')).toHaveLength(2);
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it.each([401, 403, 404, 409, 500])('clears all prior identities/counts immediately and treats HTTP %s as unavailable, never empty', async status => {
    const api = client(); render(<StudioUsagesPanel client={api} assetId={assetId} sourceIdentity="v2" />); read();
    await screen.findByText('saved-graph');
    const late = pending(); vi.mocked(api.get).mockImplementation(() => late.promise as Promise<any>);
    read();
    expect(screen.queryByText('saved-graph')).toBeNull(); expect(screen.queryByText('saved-timeline')).toBeNull();
    expect(screen.queryByText(/本次返回/)).toBeNull();
    await act(async () => late.reject(new ApiError({ status, code: 'PRIVATE_ERROR_ID', message: 'PRIVATE_ERROR_CONTENT' })));
    expect(screen.getAllByRole('alert')).toHaveLength(2);
    expect(screen.queryByText(/PRIVATE_ERROR/)).toBeNull();
    expect(screen.queryByText(/本次返回/)).toBeNull();
    expect(screen.queryByText('没有已记录的直接引用')).toBeNull();
  });

  it.each(['graph first', 'timeline first'])('publishes neither successful sibling while another authority is pending or denied (%s)', async order => {
    const api = client(), deferred = pending();
    vi.mocked(api.get).mockImplementation(async path => (order === 'graph first') === path.endsWith('/studio-graph-usages') ? (path.endsWith('/studio-graph-usages') ? graph() : timeline()) : deferred.promise);
    render(<StudioUsagesPanel client={api} assetId={assetId} sourceIdentity="v2" />); read();
    await act(async () => {});
    expect(screen.queryByText('saved-graph')).toBeNull(); expect(screen.queryByText('saved-timeline')).toBeNull();
    expect(screen.queryByText(/本次返回/)).toBeNull();
    await act(async () => deferred.reject(new Error('denied')));
    expect(screen.getAllByRole('alert')).toHaveLength(2);
    expect(screen.queryByText(/本次返回/)).toBeNull();
    expect(vi.mocked(api.get).mock.calls.every(([, signal]) => signal?.aborted)).toBe(true);
  });

  it.each([
    ['wrong owner', { ...graph(), owner: 'STUDIO_TIMELINE' }],
    ['wrong coverage', { ...graph(), coverage: 'INFERRED' }],
    ['not read-only', { ...graph(), read_only: false }],
    ['missing authoritative source', { ...graph(), source: undefined }],
    ['invalid authoritative digest', { ...graph(), source: { ...pin, digest: 'invalid' } }],
    ['invalid authoritative asset kind', { ...graph(), source: { ...pin, asset_kind: 'text' } }],
    ['short consumer digest', response('CREATIVE_GRAPH', [{ ...graphItem, digest: 'abc' }])],
    ['uppercase consumer digest', response('CREATIVE_GRAPH', [{ ...graphItem, digest: 'A'.repeat(64) }])],
    ['nonhex consumer digest', response('CREATIVE_GRAPH', [{ ...graphItem, digest: 'g'.repeat(64) }])],
    ['long consumer digest', response('CREATIVE_GRAPH', [{ ...graphItem, digest: 'a'.repeat(65) }])],
    ['invalid pinned digest', response('CREATIVE_GRAPH', [{ ...graphItem, source: { ...pin, digest: 'bad' } }])],
    ['invalid current digest', response('CREATIVE_GRAPH', [{ ...graphItem, current_source: { ...pin, digest: 'bad' } }])],
    ['overlong consumer identity', response('CREATIVE_GRAPH', [{ ...graphItem, id: 'x'.repeat(241) }])],
    ['overlong node identity', response('CREATIVE_GRAPH', [{ ...graphItem, node_id: 'x'.repeat(241) }])],
    ['overlong definition identity', response('CREATIVE_GRAPH', [{ ...graphItem, definition_id: 'x'.repeat(241) }])],
    ['overlong track identity', response('CREATIVE_GRAPH', [{ ...graphItem, track_id: 'x'.repeat(241) }])],
    ['overlong clip identity', response('CREATIVE_GRAPH', [{ ...graphItem, clip_id: 'x'.repeat(241) }])],
    ['unsupported pinned kind', response('CREATIVE_GRAPH', [{ ...graphItem, source: { ...pin, asset_kind: 'text' } }])],
    ['unsupported current kind', response('CREATIVE_GRAPH', [{ ...graphItem, current_source: { ...pin, asset_kind: 'document' } }])],
    ['array-valued pinned kind', response('CREATIVE_GRAPH', [{ ...graphItem, source: { ...pin, asset_kind: ['image'] } }])],
    ['wrong asset', response('CREATIVE_GRAPH', [{ ...graphItem, source: { ...pin, id: 'another-asset' } }])],
    ['non-asset pin', response('CREATIVE_GRAPH', [{ ...graphItem, source: { ...pin, kind: 'CHAPTER' } }])],
    ['missing pin version', response('CREATIVE_GRAPH', [{ ...graphItem, source: { ...pin, version: null } }])],
    ['missing node', response('CREATIVE_GRAPH', [{ ...graphItem, node_id: undefined }])],
    ['bad optional identity', response('CREATIVE_GRAPH', [{ ...graphItem, clip_id: {} }])],
    ['false current state', response('CREATIVE_GRAPH', [{ ...graphItem, state: 'CURRENT' }])],
    ['row differs from authoritative source', response('CREATIVE_GRAPH', [{ ...graphItem, current_source: { ...pin, version: 6 } }])],
    ['duplicate identity', response('CREATIVE_GRAPH', [graphItem, graphItem])],
    ['unbounded result', response('CREATIVE_GRAPH', Array.from({ length: 201 }, (_, i) => ({ ...graphItem, node_id: `node-${i}` })))],
  ])('fails closed on %s without exposing the other successful owner', async (_label, malformed) => {
    const api = client(); vi.mocked(api.get).mockImplementation(async path => path.endsWith('/studio-graph-usages') ? malformed : timeline());
    render(<StudioUsagesPanel client={api} assetId={assetId} sourceIdentity="v2" />); read();
    expect(await screen.findAllByRole('alert')).toHaveLength(2);
    expect(screen.queryByText(/本次返回/)).toBeNull(); expect(screen.queryByText('saved-timeline')).toBeNull();
  });

  it('rejects current-source versions that changed between owner reads', async () => {
    const api = client(), changed = { ...pin, version: 5 };
    vi.mocked(api.get).mockImplementation(async path => path.endsWith('/studio-graph-usages') ? graph() : response('STUDIO_TIMELINE', [{ ...timelineItem, source: changed, current_source: changed }], changed));
    render(<StudioUsagesPanel client={api} assetId={assetId} sourceIdentity="v2" />); read();
    expect(await screen.findAllByRole('alert')).toHaveLength(2);
    expect(screen.queryByText(/本次返回/)).toBeNull();
  });

  it.each([
    ['empty graph and nonempty timeline', true, false],
    ['nonempty graph and empty timeline', false, true],
    ['both empty', true, true],
  ])('rejects different authoritative sources even with %s', async (_label, graphEmpty, timelineEmpty) => {
    const api = client(), changed = { ...pin, version: 5, digest: 'e'.repeat(64) };
    vi.mocked(api.get).mockImplementation(async path => path.endsWith('/studio-graph-usages')
      ? response('CREATIVE_GRAPH', graphEmpty ? [] : [graphItem])
      : response('STUDIO_TIMELINE', timelineEmpty ? [] : [{ ...timelineItem, source: changed, current_source: changed }], changed));
    render(<StudioUsagesPanel client={api} assetId={assetId} sourceIdentity="v2" />); read();
    expect(await screen.findAllByRole('alert')).toHaveLength(2);
    expect(screen.queryByText(/本次返回/)).toBeNull();
    expect(screen.queryByText('没有已记录的直接引用')).toBeNull();
  });

  it('does not interpret an empty owner response lacking its authorized source as an empty usage list', async () => {
    const api = client(); vi.mocked(api.get).mockImplementation(async path => path.endsWith('/studio-graph-usages')
      ? { ...response('CREATIVE_GRAPH', []), source: undefined } : response('STUDIO_TIMELINE', []));
    render(<StudioUsagesPanel client={api} assetId={assetId} sourceIdentity="v2" />); read();
    expect(await screen.findAllByRole('alert')).toHaveLength(2);
    expect(screen.queryByText(/本次返回/)).toBeNull();
  });

  it.each(['', 'x'.repeat(241)])('rejects empty/overlong source identities before making a request', invalidId => {
    const api = client(); render(<StudioUsagesPanel client={api} assetId={invalidId} sourceIdentity="v2" />); read();
    expect(screen.getAllByRole('alert')).toHaveLength(2); expect(api.get).not.toHaveBeenCalled();
  });

  it.each(['image', 'video', 'audio'])('accepts canonical %s pins and boundary-length consumer identities', async assetKind => {
    const api = client(), current = { ...pin, asset_kind: assetKind }, consumerId = 'x'.repeat(240), nodeId = 'n'.repeat(240);
    vi.mocked(api.get).mockImplementation(async path => path.endsWith('/studio-graph-usages')
      ? response('CREATIVE_GRAPH', [{ ...graphItem, id: consumerId, node_id: nodeId, source: { ...graphItem.source, asset_kind: assetKind }, current_source: current }], current)
      : response('STUDIO_TIMELINE', [], current));
    render(<StudioUsagesPanel client={api} assetId={assetId} sourceIdentity="v2" />); read();
    expect(await screen.findByText(consumerId)).toBeTruthy();
    expect(screen.getByText(nodeId)).toBeTruthy(); expect(screen.queryByRole('alert')).toBeNull();
  });

  it('labels bounded truncation and never follows it with extra requests', async () => {
    const api = client(); vi.mocked(api.get).mockImplementation(async path => path.endsWith('/studio-graph-usages') ? { ...graph(), items: Array.from({ length: 200 }, (_, i) => ({ ...graphItem, node_id: `node-${i}` })), truncated: true } : response('STUDIO_TIMELINE', []));
    render(<StudioUsagesPanel client={api} assetId={assetId} sourceIdentity="v2" />); read();
    expect(await screen.findByText('本次返回 200 条已授权直接引用。')).toBeTruthy();
    expect(screen.getByText(/结果已截断/)).toBeTruthy();
    expect(within(graphRegion()).getAllByRole('article')).toHaveLength(200);
    expect(api.get).toHaveBeenCalledTimes(2);
  });

  it.each(['client', 'asset', 'source version'])('fences late %s A→B→A reads and requires a fresh explicit read in StrictMode', async change => {
    const api = client(), other = client(), oldGraph = pending(), oldTimeline = pending();
    vi.mocked(api.get).mockImplementation(path => (path.endsWith('/studio-graph-usages') ? oldGraph.promise : oldTimeline.promise) as Promise<any>);
    const original = { client: api, assetId, sourceIdentity: 'v2' };
    const renderPanel = (props: typeof original) => <StrictMode><StudioUsagesPanel {...props} /></StrictMode>;
    const view = render(renderPanel(original)); read(); read();
    expect(api.get).toHaveBeenCalledTimes(2);
    view.rerender(renderPanel({ ...original, ...(change === 'client' ? { client: other } : change === 'asset' ? { assetId: 'other-asset' } : { sourceIdentity: 'v3' }) }));
    view.rerender(renderPanel(original));
    expect(screen.getAllByText('尚未读取，使用覆盖未知。')).toHaveLength(2);
    expect(vi.mocked(api.get).mock.calls.every(([, signal]) => signal?.aborted)).toBe(true);
    await act(async () => { oldGraph.resolve(graph()); oldTimeline.resolve(timeline()); });
    expect(screen.queryByText('saved-graph')).toBeNull(); expect(screen.queryByText('saved-timeline')).toBeNull();
    expect(api.get).toHaveBeenCalledTimes(2); expect(other.get).not.toHaveBeenCalled();
    vi.mocked(api.get).mockImplementation(async path => path.endsWith('/studio-graph-usages') ? graph() : timeline());
    read(); await screen.findByText('saved-graph');
    expect(api.get).toHaveBeenCalledTimes(4);
  });

  it('clears completed evidence on a source-version change and aborts pending reads on unmount', async () => {
    const api = client(); const view = render(<StudioUsagesPanel client={api} assetId={assetId} sourceIdentity="v2" />); read();
    await screen.findByText('saved-graph');
    view.rerender(<StudioUsagesPanel client={api} assetId={assetId} sourceIdentity="v3" />);
    expect(screen.queryByText('saved-graph')).toBeNull(); expect(screen.queryByText(/本次返回/)).toBeNull();
    const late = pending(); vi.mocked(api.get).mockImplementation(() => late.promise as Promise<any>); read(); view.unmount();
    const last = vi.mocked(api.get).mock.calls.slice(-2); expect(last.every(([, signal]) => signal?.aborted)).toBe(true);
    await act(async () => late.reject(new Error('late denied')));
    expect(screen.queryByRole('alert')).toBeNull();
  });
});
