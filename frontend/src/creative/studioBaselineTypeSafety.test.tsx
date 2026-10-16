// @vitest-environment jsdom
import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { checkedGraphTimelineEdits, checkedGraphTimelineParameters, checkedGraphTimelineSnapshot } from './studioGraphTimelineContract';
import { checkedTimelineExportPreview, type TimelineExportPreview } from './studioTimelineExportTypes';
import type { StudioTimelineRow } from './studioTimelineTypes';
import type { ProductionJob, StudioProductionClient } from './studioProductionClient';
import type { TimelinePlayback } from './studioTimelinePlaybackTypes';
import type { StudioGraphClient } from './studioGraphClient';
import { modelGraph, modelRun } from './studioGraphModel.testFixtures';
import { useStudioGraphMediaExecution, type StudioGraphMediaExecutionProps } from './useStudioGraphMediaExecution';
import { useStudioTimelinePlayback } from './useStudioTimelinePlayback';
import type { StudioTimelineEditorProps } from './useStudioTimelineEditor';

const digest = 'a'.repeat(64), snapshot = { id: 'timeline', version: 1, digest };
const source: StudioTimelineRow = { id: snapshot.id, version: snapshot.version, timeline_digest: digest,
  title: 'Type safety fixture', created_at: '', updated_at: '', timeline: {
    duration_ms: 1000, width: 32, height: 32, fps: 24, captions: [], tracks: [{ id: 'track', kind: 'VIDEO', order: 0,
      muted: false, gain_db: 0, clips: [{ id: 'clip', start_ms: 0, in_ms: 0, out_ms: 1000, x: 0, y: 0, width: 32, height: 32,
        source_snapshot: { id: 'asset', kind: 'ASSET', asset_kind: 'video', version: 1, digest } }] }] } };
function exportPreview(): TimelineExportPreview {
  return { contract: 'studio-timeline-export-preview/1', timeline_snapshot: snapshot, export_profile: { preset: 'REVIEW_MP4' },
    sources: [source.timeline.tracks[0].clips[0].source_snapshot], execution_recipe: { contract: 'studio-execution-recipe/1',
      operation_id: 'm9.timeline.multitrack', adapter: 'LOCAL_FFMPEG', output_profile: 'REVIEW_MP4', timeline: source.timeline,
      export_profile: { preset: 'REVIEW_MP4' }, automatic_fallback: false, recipe_digest: digest },
    limits: { max_output_bytes: 25 * 1024 * 1024, render_timeout_seconds: 120 }, preview_digest: digest,
    model_called: false, automatic_replay: false, product_acceptance: 'LOCAL_REQUIRED' };
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('baseline timeline validator narrowing', () => {
  it('accepts exact snapshots, array bindings and edits without changing the input', () => {
    const edits = [{ op: 'track.reorder', track_ids: ['track'] }, { op: 'track.update', track_id: 'track', changes: { locked: true, gain_db: -2.5 } }];
    const parameters = { timeline_snapshot: snapshot, export_profile: { preset: 'REVIEW_MP4' }, edit_operations: edits,
      source_bindings: [{ port: 'source_1', clip_id: 'clip' }] };
    expect(checkedGraphTimelineSnapshot(snapshot)).toEqual(snapshot);
    const checked = checkedGraphTimelineParameters(parameters);
    expect(checked).toEqual(parameters);
    expect(checked.edit_operations).not.toBe(edits);
  });
  it.each([null, [], { ...snapshot, version: '1' }, { ...snapshot, version: 0 }, { ...snapshot, digest: 'bad' },
    { ...snapshot, id: '../timeline' }, { ...snapshot, extra: true }])('rejects malformed snapshot %j', value => {
    expect(() => checkedGraphTimelineSnapshot(value)).toThrow('时间线节点的绑定或剪辑操作无效');
  });
  it.each([null, {}, [{ op: 'track.reorder', track_ids: 'track' }], [{ op: 'track.reorder', track_ids: ['track', 'track'] }],
    [{ op: 'track.update', track_id: 'track', changes: { locked: 'true' } }],
    [{ op: 'track.update', track_id: 'track', changes: { gain_db: Infinity } }],
    [{ op: 'clip.move', clip_id: 'clip', track_id: 'track', start_ms: 1.5 }],
    [{ op: 'clip.remove', clip_id: 'clip', ripple: false, replay: true }],
    Array.from({ length: 41 }, () => ({ op: 'caption.remove', index: 0 }))])('rejects malformed edit list %j', value => {
    expect(() => checkedGraphTimelineEdits(value)).toThrow('时间线节点的绑定或剪辑操作无效');
  });
  it.each([null, {}, 'source_1', [{ port: 'source_1', clip_id: 'clip' }, { port: 'source_1', clip_id: 'other' }],
    [{ port: 'source_1', clip_id: 'clip' }, { port: 'source_2', clip_id: 'clip' }]])('rejects malformed or duplicate bindings %j', source_bindings => {
    expect(() => checkedGraphTimelineParameters({ timeline_snapshot: snapshot, export_profile: { preset: 'REVIEW_MP4' }, source_bindings })).toThrow();
  });
  it('retains the exact validated export preview', () => {
    const value = exportPreview();
    expect(checkedTimelineExportPreview(value, source, { preset: 'REVIEW_MP4' })).toEqual(value);
  });
  it.each([null, undefined, [], {}, { ...exportPreview().execution_recipe, automatic_fallback: true },
    { ...exportPreview().execution_recipe, export_profile: { preset: 'DELIVERY_H264_MP4' } },
    { ...exportPreview().execution_recipe, timeline: { ...source.timeline, duration_ms: 2000 } },
    { ...exportPreview().execution_recipe, extra: true }])('fails closed on malformed or mismatched recipe %j', execution_recipe => {
    expect(() => checkedTimelineExportPreview({ ...exportPreview(), execution_recipe }, source, { preset: 'REVIEW_MP4' })).toThrow(ApiError);
  });
});

function graphProps(): StudioGraphMediaExecutionProps {
  return { client: {} as StudioGraphClient, locked: false, canMutate: true, canReview: true, uncertain: false,
    isCurrent: () => true, read: work => work(), perform: vi.fn(), onUnavailable: vi.fn() };
}
describe('graph media optional ownership', () => {
  it('does not equate two missing owners and dereference an absent graph', () => {
    const { result } = renderHook(() => useStudioGraphMediaExecution(graphProps()));
    expect(result.current.reviewNodeId).toBeUndefined();
    expect(result.current.canReview).toBe(false);
    expect(result.current.canRead).toBe(false);
  });
  it('resolves a media review only for the exact present graph and run versions', () => {
    const graph = modelGraph();
    graph.definition.nodes[2].definition_id = 'media_review';
    graph.definition.edges[1] = { ...graph.definition.edges[1], source_port: 'candidate', target_port: 'candidate' };
    const run = modelRun({ media_runtime: { schema_version: 1, contract: 'creative-graph-media/1', automatic_retry: false,
      automatic_poll: false, applied: false, product_acceptance: 'LOCAL_REQUIRED', nodes: [{ node_id: 'generate', status: 'AWAITING_PREVIEW', preview: null, execution: null }] } });
    const props: StudioGraphMediaExecutionProps = { ...graphProps(), graph, run };
    const { result, rerender } = renderHook((value: StudioGraphMediaExecutionProps) => useStudioGraphMediaExecution(value), { initialProps: props });
    expect(result.current.reviewNodeId).toBe('review');
    rerender({ ...props, graph: { ...graph, version: 2 } });
    expect(result.current.reviewNodeId).toBeUndefined();
    rerender({ ...props, graph: undefined });
    expect(result.current.reviewNodeId).toBeUndefined();
    rerender({ ...props, run: undefined });
    expect(result.current.reviewNodeId).toBeUndefined();
  });
});

function playback(): TimelinePlayback {
  return { contract: 'studio-timeline-playback/1', novel_id: 'project', branch_id: null, cache_key: digest, request_id: `playback_${digest}`,
    job_id: 'b'.repeat(64), export_preview: exportPreview(), job: null, cache_state: 'MISSING', playback_digest: 'c'.repeat(64),
    model_called: false, automatic_replay: false, product_acceptance: 'LOCAL_REQUIRED' };
}
function job(value: TimelinePlayback): ProductionJob {
  return { contract: 'studio-production-job/1', owner: 'timeline', id: value.job_id, novel_id: value.novel_id, branch_id: value.branch_id,
    version: 1, operation_id: 'm9.timeline.multitrack', request_id: value.request_id, status: 'RUNNING', request_digest: digest,
    receipt_digest: null, output_candidate: null, product_acceptance: 'LOCAL_REQUIRED', automatic_replay: false, remote_compute_may_continue: false,
    timeline_snapshot: snapshot, sources: value.export_preview.sources, command: null, provider: null,
    execution_recipe: value.export_preview.execution_recipe, approved_asset_version: null, created_at: '', updated_at: '' };
}
function playbackSetup() {
  const value = playback(), original = job(value);
  const client = { timelinePlaybackPreview: vi.fn().mockResolvedValue(value), timelinePlaybackBuild: vi.fn().mockRejectedValue(new Error('Lost response')),
    timelinePlaybackAttestation: vi.fn(), get: vi.fn().mockResolvedValue(original) };
  const props: StudioTimelineEditorProps = { client: client as unknown as StudioProductionClient, assets: [{ id: 'asset', novel_id: 'project',
    filename: 'fixture.mp4', kind: 'video', media_type: 'video/mp4', size: 1, sha256: digest, version: 1, created_at: '', updated_at: '' }],
    canMutate: true, busy: false, isCurrent: () => true, read: work => work(), mutate: work => work(), onDirtyChange: vi.fn(), onJob: vi.fn(), onUnavailable: vi.fn() };
  const options = { props, source, isReady: () => true, onGateChange: vi.fn(), onAuthorityLost: vi.fn() };
  const hook = renderHook(() => useStudioTimelinePlayback(options));
  return { ...hook, props, options, client, value, original };
}
describe('playback original-attempt recovery', () => {
  it('reads a preview without inventing an original attempt or starting a build', async () => {
    const { result, client, value } = playbackSetup();
    await act(() => result.current.readOriginal());
    expect(result.current.preview).toEqual(value);
    expect(result.current.unknown).toBeUndefined();
    expect(client.timelinePlaybackPreview).toHaveBeenCalledTimes(1);
    expect(client.timelinePlaybackBuild).not.toHaveBeenCalled();
    expect(client.get).not.toHaveBeenCalled();
  });
  it('retains UNKNOWN on a mismatched original job and recovers only the matching receipt', async () => {
    const { result, client, original, props } = playbackSetup();
    await act(() => result.current.previewPlayback());
    act(() => result.current.setConfirmed(true));
    await act(() => result.current.buildPlayback());
    expect(result.current.unknown).toBeDefined();
    client.get.mockResolvedValueOnce({ ...original, request_id: 'another_request' });
    await act(() => result.current.readOriginal());
    expect(result.current.unknown).toBeDefined();
    expect(result.current.error).toContain('读取未证明本次请求的原任务');
    expect(props.onJob).not.toHaveBeenCalled();
    await act(() => result.current.buildPlayback());
    expect(client.timelinePlaybackBuild).toHaveBeenCalledTimes(1);
    await act(() => result.current.readOriginal());
    expect(client.get).toHaveBeenCalledWith('timeline', original.id);
    expect(result.current.unknown).toBeUndefined();
    expect(result.current.preview?.job).toEqual(original);
    expect(props.onJob).toHaveBeenCalledWith(original);
    expect(client.timelinePlaybackPreview).toHaveBeenCalledTimes(1);
    expect(client.timelinePlaybackBuild).toHaveBeenCalledTimes(1);
  });
});
