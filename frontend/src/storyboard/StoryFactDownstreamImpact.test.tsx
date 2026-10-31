// @vitest-environment jsdom
import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import { readResponse, samePin } from '../experimental/studioUsageEvidence';
import { StoryFactDownstreamImpact } from './StoryFactDownstreamImpact';
import { StoryFactUsagePanel } from './StoryFactUsagePanel';
import { checkedImpact, type FactTarget, type FactUse } from './storyFactClient';
import { factAssetPin, factPathKey, revalidateFactPath } from './storyFactDownstream';
// [HERMIA-FE-20261023 M1-flaky] Root cause: these long jsdom integration flows take 3-5s unloaded and exceed vitest's default 5000ms testTimeout under full-suite CPU load. Budget raised per file; no assertion, step or mock changed.
vi.setConfig({ testTimeout: 30000 });
afterEach(cleanup);
const digest = (letter: string) => letter.repeat(64);
const fact = { id: 'fact', version: 2, digest: digest('a'), title: 'Fact' };
const target: FactTarget = { document_id: 'doc', document_version: 2, document_digest: digest('b'), scene_id: 'scene', shot_id: 'shot', shot_version: 3, shot_digest: digest('c') };
const asset: FactUse['assets'][number] = { asset_id: 'asset/1', version: 4, digest: digest('d'), kind: 'image' };
const row: FactUse = { id: 'use', version: 1, fact, current_fact: { ...fact, status: 'APPROVED' }, target, state: 'CURRENT', blockers: [], purpose: 'CAUSAL_CONTEXT', rationale: 'Author reason', assets: [asset] };
const pin = factAssetPin(asset);
const graphItem = { owner: 'CREATIVE_GRAPH', id: 'saved-graph', version: 3, digest: digest('e'), node_id: 'node', definition_id: 'asset_reference', source: pin, current_source: pin, state: 'CURRENT' };
const timelineItem = { owner: 'STUDIO_TIMELINE', id: 'saved-timeline', version: 3, digest: digest('f'), track_id: 'track', clip_id: 'clip', source: pin, current_source: pin, state: 'CURRENT' };
const response = (owner: string, items: unknown[] = []) => ({ owner, source: pin, items, coverage: 'EXACT_SAVED_DIRECT_ASSET_REFERENCES', truncated: false, limit: 200, read_only: true, automatic_regeneration: false, other_dependencies: 'UNKNOWN' });
const impact = (rows: unknown[] = [row]) => ({ contract: 'creative-fact-impact/1', coverage: 'EXPLICIT_CONFIRMED_FACT_USES_AND_CURRENT_SHOT_ASSET_BINDINGS', unrecorded_dependencies: 'UNKNOWN', automatic_regeneration: false, model_called: false, items: rows });
function setup() {
  const json = vi.fn(async (url: string): Promise<unknown> => {
    if (url.endsWith('/studio-graph-usages')) return response('CREATIVE_GRAPH', [graphItem]);
    if (url.endsWith('/studio-timeline-usages')) return response('STUDIO_TIMELINE', [timelineItem]);
    if (url.endsWith('/story-facts')) return { contract: 'creative-story-facts/1', coverage: 'APPROVED_WORLD_FACT_RELATIONS_ONLY', items: [fact] };
    return impact();
  });
  const gate = async <T,>(work: () => Promise<T>): Promise<T> => work();
  const readMock = vi.fn(gate);
  const read = readMock as typeof gate & typeof readMock;
  return { projectId: 'p', identity: 'branch/session-A', target, uses: [row], transport: { json } as StudioGraphTransport,
    enabled: true, busy: false, isCurrent: () => true, read, json };
}
function select() { fireEvent.change(screen.getByLabelText('检查的事实镜头素材'), { target: { value: factPathKey(row, asset) } }); }
function inspect() { fireEvent.click(screen.getByRole('button', { name: '检查下游使用（只读）' })); }
function pending() { let resolve!: (value: unknown) => void; const promise = new Promise<unknown>(yes => { resolve = yes; }); return { resolve, promise }; }
describe('exact bounded fact downstream evidence', () => {
  it('compares every exact asset pin field and rejects changed fact paths and duplicates', () => {
    expect(samePin(pin, { ...pin })).toBe(true);
    for (const change of [{ id: 'other' }, { version: 5 }, { digest: digest('e') }, { asset_kind: 'video' as const }]) expect(samePin(pin, { ...pin, ...change })).toBe(false);
    expect(revalidateFactPath([row], row, asset, target)).toEqual(row);
    for (const rows of [[], [row, row], [{ ...row, version: 2 }], [{ ...row, assets: [asset, asset] }], [{ ...row, target: { ...target, shot_version: 8 } }], [{ ...row, current_fact: { ...row.current_fact, version: 8 } }]]) expect(() => revalidateFactPath(rows, row, asset, target)).toThrow();
    expect(() => checkedImpact(impact([row, row]), 'doc')).toThrow();
    expect(() => checkedImpact(impact(Array.from({ length: 201 }, (_, i) => ({ ...row, id: `use-${i}` }))), 'doc')).toThrow();
  });
  it('rejects malformed, wrong-owner, duplicate, over-bound and inconsistent consumer documents', () => {
    const valid = response('CREATIVE_GRAPH', [graphItem]);
    expect(readResponse(valid, 'CREATIVE_GRAPH', asset.asset_id)).toEqual(valid);
    for (const invalid of [{ ...valid, owner: 'STUDIO_TIMELINE' }, { ...valid, source: { ...pin, digest: 'bad' } }, { ...valid, limit: 201 }, { ...valid, items: [graphItem, graphItem] }, { ...valid, items: [{ ...graphItem, track_id: 'wrong-owner' }] }, { ...valid, items: [{ ...graphItem, definition_id: 'image_generate' }] }, { ...valid, items: [graphItem, { ...graphItem, node_id: 'second', version: 4 }] }, { ...valid, items: Array.from({ length: 26 }, (_, i) => ({ ...graphItem, id: `graph-${i}` })) }, { ...valid, items: Array.from({ length: 201 }, (_, i) => ({ ...graphItem, node_id: `node-${i}` })) }]) expect(() => readResponse(invalid, 'CREATIVE_GRAPH', asset.asset_id)).toThrow();
    expect(readResponse({ ...valid, items: Array.from({ length: 200 }, (_, i) => ({ ...graphItem, node_id: `node-${i}` })), truncated: true }, 'CREATIVE_GRAPH', asset.asset_id).items).toHaveLength(200);
  });
});
describe('mounted read-only fact downstream inspection', () => {
  it('is lazy, reads fact before and after both original owners and shows complete exact paths', async () => {
    const props = setup(); render(<StrictMode><StoryFactDownstreamImpact {...props} /></StrictMode>);
    expect(props.json).not.toHaveBeenCalled(); select(); expect(props.json).not.toHaveBeenCalled(); inspect();
    await screen.findByText('saved-graph'); expect(screen.getByText('saved-timeline')).toBeTruthy();
    expect(props.json.mock.calls.map(([url]) => url)).toEqual([
      '/api/novels/p/experimental/creative/documents/doc/fact-uses',
      '/api/novels/p/experimental/production/assets/asset%2F1/studio-graph-usages',
      '/api/novels/p/experimental/production/assets/asset%2F1/studio-timeline-usages',
      '/api/novels/p/experimental/creative/documents/doc/fact-uses',
    ]);
    expect(props.read).toHaveBeenCalledTimes(4);
    expect(screen.getAllByText(/精确路径/)).toHaveLength(2);
    expect(screen.getByText(/事实 fact v2.*镜头 shot v3.*素材 asset\/1 v4/)).toBeTruthy();
    expect(screen.getByText(/不是原子快照或语义因果证明/)).toBeTruthy();
    expect(screen.getByText(/Export、成本和未记录依赖仍为 UNKNOWN/)).toBeTruthy();
    expect(props.json.mock.calls.every(call => (call as unknown[])[1] === 'GET')).toBe(true);
    expect(screen.getAllByRole('button')).toHaveLength(1);
  });
  it('labels same-ID different snapshots separately without an exact-path claim', async () => {
    const props = setup(); const original = props.json.getMockImplementation()!;
    props.json.mockImplementation(async url => url.endsWith('/studio-graph-usages') ? response('CREATIVE_GRAPH', [{ ...graphItem, source: { ...pin, version: 1 }, state: 'STALE' }]) : original(url));
    render(<StoryFactDownstreamImpact {...props} />); select(); inspect(); await screen.findByText('saved-graph');
    expect(screen.getAllByText(/精确路径/)).toHaveLength(1); expect(screen.getByText(/另一素材快照/)).toBeTruthy();
  });
  it.each(['before', 'after', 'graph-pin', 'timeline-denial', 'malformed'])('clears the whole observation for %s failure, including a successful sibling', async failure => {
    const props = setup(); render(<StoryFactDownstreamImpact {...props} />); select(); inspect(); await screen.findByText('saved-graph');
    const original = props.json.getMockImplementation()!; let facts = 0;
    props.json.mockImplementation(async url => {
      if (url.endsWith('/fact-uses')) { facts++; if (failure === 'before' || failure === 'after' && facts === 2) return impact([{ ...row, current_fact: { ...row.current_fact, version: 10 } }]); }
      if (url.endsWith('/studio-graph-usages') && failure === 'graph-pin') return { ...response('CREATIVE_GRAPH'), source: { ...pin, version: 5 } };
      if (url.endsWith('/studio-timeline-usages') && failure === 'timeline-denial') throw new Error('403');
      if (url.endsWith('/studio-timeline-usages') && failure === 'malformed') return {};
      return original(url);
    });
    inspect(); expect(screen.queryByText('saved-graph')).toBeNull(); await screen.findByText(/下游覆盖不可用/);
    expect(screen.queryByText('saved-graph')).toBeNull(); expect(screen.queryByText('saved-timeline')).toBeNull();
    if (failure === 'before') expect(facts).toBe(1);
    props.json.mockImplementation(original); inspect(); await screen.findByText('saved-graph');
  });
  it.each(['identity', 'transport', 'project', 'target', 'enabled', 'admission', 'selection'])('fences delayed A→B→A %s transitions without automatic reinspection', async change => {
    const props = setup(), late = pending(); const original = props.json.getMockImplementation()!;
    props.json.mockImplementationOnce(() => late.promise);
    const { rerender } = render(<StoryFactDownstreamImpact {...props} />); select(); inspect();
    if (change === 'selection') { fireEvent.change(screen.getByLabelText('检查的事实镜头素材'), { target: { value: '' } }); select(); }
    else {
      const changed = change === 'identity' ? { identity: 'B' } : change === 'transport' ? { transport: { json: props.json } as StudioGraphTransport } : change === 'project' ? { projectId: 'B' } : change === 'target' ? { target: { ...target, shot_version: 9 } } : change === 'enabled' ? { enabled: false } : { isCurrent: () => false };
      rerender(<StoryFactDownstreamImpact {...props} {...changed} />); rerender(<StoryFactDownstreamImpact {...props} />);
    }
    await act(async () => { late.resolve(impact()); await late.promise; });
    expect(screen.queryByText('saved-graph')).toBeNull(); expect(props.json).toHaveBeenCalledTimes(1);
    props.json.mockImplementation(original); select(); inspect(); await screen.findByText('saved-graph');
  });
  it('does not revive a late successful sibling after denial and a new successful inspection', async () => {
    const props = setup(), late = pending(); const original = props.json.getMockImplementation()!;
    props.json.mockImplementation(async url => {
      if (url.endsWith('/studio-graph-usages')) return late.promise;
      if (url.endsWith('/studio-timeline-usages')) throw new Error('403');
      return original(url);
    });
    render(<StoryFactDownstreamImpact {...props} />); select(); inspect(); await screen.findByText(/下游覆盖不可用/);
    props.json.mockImplementation(original); inspect(); await screen.findByText('saved-graph');
    await act(async () => { late.resolve(response('CREATIVE_GRAPH', [{ ...graphItem, id: 'retired-graph' }])); await late.promise; });
    expect(screen.queryByText('retired-graph')).toBeNull(); expect(screen.getByText('saved-graph')).toBeTruthy();
  });
  it.each(['deselected', 'deselected-ABA', 'asset-B', 'asset-B-ABA'])('rejects a retained selected-A click after selection %s', async transition => {
    const props = setup();
    const otherAsset = { ...asset, asset_id: 'asset/2', kind: 'video' as const };
    props.uses = [{ ...row, assets: [asset, otherAsset] }];
    render(<StoryFactDownstreamImpact {...props} />); select();
    const button = screen.getByRole('button', { name: '检查下游使用（只读）' });
    const reactKey = Object.keys(button).find(key => key.startsWith('__reactProps'))!;
    const retained = (button as unknown as Record<string, { onClick: () => void }>)[reactKey].onClick;
    const next = transition.startsWith('asset-B') ? factPathKey(row, otherAsset) : '';
    fireEvent.change(screen.getByLabelText('检查的事实镜头素材'), { target: { value: next } });
    if (transition.endsWith('ABA')) select();
    await act(async () => { retained(); });
    expect(props.read).not.toHaveBeenCalled();
    expect(props.json).not.toHaveBeenCalled();
    expect(screen.queryByText('saved-graph')).toBeNull();
    select(); inspect(); await screen.findByText('saved-graph');
  });
  it.each([1, 2, 4])('does not dispatch obsolete reads when host gate %s resumes after selection ABA', async gateNumber => {
    const props = setup(), held = pending(); let gates = 0;
    props.read.mockImplementation(async work => {
      gates++;
      if (gates === gateNumber) await held.promise;
      return work();
    });
    render(<StoryFactDownstreamImpact {...props} />); select(); inspect();
    await waitFor(() => expect(gates).toBeGreaterThanOrEqual(gateNumber));
    const dispatched = props.json.mock.calls.length;
    fireEvent.change(screen.getByLabelText('检查的事实镜头素材'), { target: { value: '' } }); select();
    await act(async () => { held.resolve(undefined); await held.promise; });
    expect(props.json).toHaveBeenCalledTimes(dispatched);
    expect(screen.queryByText('saved-graph')).toBeNull();
    expect(screen.queryByText('saved-timeline')).toBeNull();
  });
  it('discards late callbacks after unmount', async () => {
    const props = setup(), late = pending(); props.json.mockImplementationOnce(() => late.promise);
    const { unmount } = render(<StoryFactDownstreamImpact {...props} />); select(); inspect(); unmount();
    await act(async () => { late.resolve(impact()); await late.promise; }); expect(props.json).toHaveBeenCalledTimes(1);
  });
  it('distinguishes empty and truncated coverage and requires explicit reinspection', async () => {
    const props = setup(); const original = props.json.getMockImplementation()!;
    props.json.mockImplementation(async url => url.endsWith('/studio-graph-usages') ? { ...response('CREATIVE_GRAPH', [graphItem]), truncated: true } : url.endsWith('/studio-timeline-usages') ? response('STUDIO_TIMELINE') : original(url));
    render(<StoryFactDownstreamImpact {...props} />); select(); inspect(); await screen.findByText('saved-graph');
    expect(screen.getByText(/结果已截断/)).toBeTruthy(); expect(screen.getByText(/本次授权范围没有已记录直接引用/)).toBeTruthy();
    expect(props.json).toHaveBeenCalledTimes(4); inspect(); await waitFor(() => expect(props.json).toHaveBeenCalledTimes(8));
  });
  it('mounts in the original fact panel and allows read-only inspection with zero mutations', async () => {
    const props = setup();
    const gate = async <T,>(work: () => Promise<T>) => work();
    const mutateMock = vi.fn(gate), mutate = mutateMock as typeof gate & typeof mutateMock;
    render(<StoryFactUsagePanel {...props} writable={false} mutate={mutate} />);
    fireEvent.click(screen.getByRole('button', { name: '读取事实依赖' })); await screen.findByLabelText('检查的事实镜头素材');
    select(); inspect(); await screen.findByText('saved-graph');
    expect(mutate).not.toHaveBeenCalled(); expect(props.json.mock.calls.every(call => (call as unknown[])[1] === 'GET')).toBe(true);
    expect((screen.getByRole('button', { name: '确认事实使用' }) as HTMLButtonElement).disabled).toBe(true);
  });
});
