// @vitest-environment jsdom
import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { checkedTimelineRow } from './studioTimelineTypes';
import { useStudioTimelinePlayback } from './useStudioTimelinePlayback';
import type { StudioProductionClient } from './studioProductionClient';
import type { TimelinePlayback } from './studioTimelinePlaybackTypes';
import actual from './fixtures/timelinePreviewSourceSwitch.actual.json';
import original from './fixtures/timelinePreviewProxy.actual.json';

const row = checkedTimelineRow(actual.row), small = checkedTimelineRow(actual.small_row);
const half = () => structuredClone(actual.half) as unknown as TimelinePlayback;
type Options = Parameters<typeof useStudioTimelinePlayback>[0];
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(done => { resolve = done; }); return { promise, resolve }; }
function setup() {
  const client = { timelinePlaybackPreview: vi.fn(async (source: typeof row): Promise<TimelinePlayback> => {
    if (source.id === small.id) throw new ApiError({ status: 400, code: 'STUDIO_TIMELINE_PREVIEW_DIMENSIONS_UNSUPPORTED', message: 'HALF requires a 32×32 canvas.' });
    return half();
  }), timelinePlaybackBuild: vi.fn(async (): Promise<TimelinePlayback> => { throw new ApiError({ status: 0, code: 'NETWORK_ERROR', message: 'lost reply' }); }),
    timelinePlaybackAttestation: vi.fn(), get: vi.fn(), timelineSave: vi.fn(), timelineRender: vi.fn() };
  const options: Options = { source: row, props: { client: client as unknown as StudioProductionClient, assets: [actual.source], canMutate: true, busy: false,
    projectId: actual.row.novel_id, isCurrent: () => true, read: work => work(), mutate: work => work(), onDirtyChange: vi.fn(), onUnavailable: vi.fn(), onJob: vi.fn() },
    isReady: () => true, onGateChange: vi.fn(), onAuthorityLost: vi.fn() };
  const hook = renderHook((value: Options) => useStudioTimelinePlayback(value), { initialProps: options });
  act(() => hook.result.current.changeResolution('HALF'));
  return { client, options, hook };
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it('retires HALF before rendering another genuine saved 30px canvas, preserves controlled refusal and fresh positive reads', async () => {
  expect(actual.row.novel_id).toBe(actual.small_row.novel_id); expect(small.timeline.width).toBe(30);
  const { hook, client, options } = setup(); await act(async () => hook.result.current.previewPlayback());
  expect(hook.result.current.previewDimensions).toEqual([48, 32]); act(() => hook.result.current.setConfirmed(true));
  const retiredRead = hook.result.current.previewPlayback, retiredBuild = hook.result.current.buildPlayback, retiredConsent = hook.result.current.setConfirmed;
  expect(() => hook.rerender({ ...options, source: small })).not.toThrow();
  expect(hook.result.current.preview).toBeUndefined(); expect(hook.result.current.previewDimensions).toBeUndefined(); expect(hook.result.current.confirmed).toBe(false);
  hook.rerender(options);
  await act(async () => retiredRead()); act(() => retiredConsent(true)); await act(async () => retiredBuild());
  expect(client.timelinePlaybackPreview).toHaveBeenCalledTimes(1); expect(client.timelinePlaybackBuild).not.toHaveBeenCalled(); expect(hook.result.current.confirmed).toBe(false);
  hook.rerender({ ...options, source: small }); await act(async () => hook.result.current.previewPlayback());
  expect(hook.result.current.error).toContain('32×32'); expect(hook.result.current.preview).toBeUndefined(); expect(hook.result.current.pending).toBeUndefined();
  hook.rerender(options); await act(async () => hook.result.current.previewPlayback());
  expect(hook.result.current.previewDimensions).toEqual([48, 32]); expect(hook.result.current.confirmed).toBe(false);
  expect(client.timelineSave).not.toHaveBeenCalled(); expect(client.timelineRender).not.toHaveBeenCalled();
});

it('discards an in-flight genuine HALF preview after saved-source ABA and permits a new explicit read', async () => {
  const { hook, client, options } = setup(), response = deferred<TimelinePlayback>();
  client.timelinePlaybackPreview.mockImplementationOnce(() => response.promise);
  let pending!: Promise<void>; act(() => { pending = hook.result.current.previewPlayback(); }); expect(hook.result.current.pending).toBe('PREVIEW');
  hook.rerender({ ...options, source: small }); hook.rerender(options);
  await act(async () => { response.resolve(half()); await pending; });
  expect(hook.result.current.preview).toBeUndefined(); expect(hook.result.current.previewDimensions).toBeUndefined(); expect(hook.result.current.confirmed).toBe(false);
  expect(hook.result.current.pending).toBeUndefined(); expect(hook.result.current.locked).toBe(false);
  await act(async () => hook.result.current.previewPlayback()); expect(hook.result.current.previewDimensions).toEqual([48, 32]);
  expect(client.timelinePlaybackPreview).toHaveBeenCalledTimes(2); expect(client.timelinePlaybackBuild).not.toHaveBeenCalled();
});

it('retains original UNKNOWN identity without adopting an old build reply after saved-source ABA', async () => {
  const { hook, client, options } = setup(); await act(async () => hook.result.current.previewPlayback()); act(() => hook.result.current.setConfirmed(true));
  const response = deferred<TimelinePlayback>(); client.timelinePlaybackBuild.mockImplementationOnce(() => response.promise);
  let pending!: Promise<void>; act(() => { pending = hook.result.current.buildPlayback(); });
  expect(hook.result.current.unknown?.preview.request_id).toBe(actual.half.request_id);
  hook.rerender({ ...options, source: small }); hook.rerender(options);
  // Controller-only completed response: retain the captured native job shape and align the immutable request bindings.
  const value = half(); value.job = { ...structuredClone(original.half_playback_built.job), id: value.job_id, request_id: value.request_id,
    novel_id: value.novel_id, branch_id: value.branch_id, timeline_snapshot: value.export_preview.timeline_snapshot,
    sources: value.export_preview.sources, execution_recipe: value.export_preview.execution_recipe } as unknown as NonNullable<TimelinePlayback['job']>;
  value.cache_state = 'RECORDED'; await act(async () => { response.resolve(value); await pending; });
  expect(hook.result.current.preview).toBeUndefined(); expect(hook.result.current.previewDimensions).toBeUndefined(); expect(hook.result.current.pending).toBeUndefined();
  expect(hook.result.current.unknown?.preview.request_id).toBe(actual.half.request_id); expect(hook.result.current.locked).toBe(true);
  expect(options.props.onJob).not.toHaveBeenCalled();
  await act(async () => hook.result.current.buildPlayback()); expect(client.timelinePlaybackBuild).toHaveBeenCalledTimes(1);
  const read = deferred<NonNullable<TimelinePlayback['job']>>(); client.get.mockImplementationOnce(() => read.promise);
  let recovering!: Promise<void>; act(() => { recovering = hook.result.current.readOriginal(); });
  hook.rerender({ ...options, source: small }); hook.rerender(options);
  await act(async () => { read.resolve(value.job!); await recovering; });
  expect(hook.result.current.preview).toBeUndefined(); expect(hook.result.current.unknown?.preview.request_id).toBe(actual.half.request_id);
  expect(hook.result.current.auxiliary).toBeUndefined(); expect(options.props.onJob).not.toHaveBeenCalled();
  client.get.mockResolvedValueOnce(value.job); await act(async () => hook.result.current.readOriginal());
  expect(hook.result.current.unknown).toBeUndefined(); expect(hook.result.current.previewDimensions).toEqual([48, 32]);
  expect(hook.result.current.locked).toBe(false); expect(options.props.onJob).toHaveBeenCalledTimes(1);
  expect(client.timelinePlaybackBuild).toHaveBeenCalledTimes(1);
  expect(client.timelineSave).not.toHaveBeenCalled(); expect(client.timelineRender).not.toHaveBeenCalled();
});
