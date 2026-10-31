// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { createElement } from 'react';
import { StudioProductionLeaveContext } from './studioProductionLeaveRisk';
import { ApiError } from '../api';
import { useStudioMediaExecution, mediaProviderKey, type StudioMediaExecutionProps } from './useStudioMediaExecution';
import { useStudioTimelineEditor, type StudioTimelineEditorProps } from './useStudioTimelineEditor';
import { useStudioTimelinePlayback } from './useStudioTimelinePlayback';
import { useStudioTimelineTransfer } from './useStudioTimelineTransfer';
import { useStudioTimelineSourceEdit } from './useStudioTimelineSourceEdit';
import type { StudioProductionClient, MediaOperation, MediaCommand, ProductionPreview, ProductionProvider } from './studioProductionClient';
import type { StudioProductionLeaveGuard, StudioProductionLeaveRisk } from './studioProductionLeaveRisk';
import { checkedTimelineRow } from './studioTimelineTypes';
import type { TimelineTransferPreview } from './studioTimelineTransferTypes';
import { audioTimelineAssets, audioTimelineRow, audioTimelinePlayback } from './studioAudioTimeline.testFixtures';
import capture from './fixtures/phase6.capture.editing-pipeline.json';

// Original controllers with bounded transport fixtures; no inference/native-render claim.
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
const lost = () => new ApiError({ status: 503, code: 'UNAVAILABLE', message: 'Lost response' });
function guard() {
  const readers = new Set<() => StudioProductionLeaveRisk>(), snapshots: StudioProductionLeaveRisk[][] = [];
  const collect = () => [...readers].map(read => read());
  const value: StudioProductionLeaveGuard = { register: read => { readers.add(read); return () => { value.capture(); readers.delete(read); }; }, capture: () => { snapshots.push(collect()); } };
  return { value, collect, snapshots };
}
const asset = capture.video_source;
const source = () => checkedTimelineRow(structuredClone(capture.created));
function timelineProps(client: unknown, leaveGuard: StudioProductionLeaveGuard): StudioTimelineEditorProps {
  return { client: client as StudioProductionClient, assets: [asset], projectId: capture.created.novel_id,
    canMutate: true, busy: false, isCurrent: () => true, read: work => work(), mutate: work => work(),
    onDirtyChange: vi.fn(), onUnavailable: vi.fn(), onJob: vi.fn(), leaveGuard };
}
it.each(['m5.image.t2i', 'm7.video.t2v'] as MediaOperation[])('captures original %s create UNKNOWN and fences retained callbacks after retirement', async operation => {
  const g = guard(); let current = true;
  const provider: ProductionProvider = { operation_id: operation, provider_id: 'fixture-local', model_id: 'configured-only', local: true,
    route_digest: 'a'.repeat(64), readiness: 'CONFIGURED_NOT_VERIFIED', capability: 'FIXTURE', supported_parameters: [] };
  const preview = vi.fn(async (command: MediaCommand) => ({ command, operation_id: operation, request_digest: 'b'.repeat(64), preview_digest: 'c'.repeat(64), provider } as unknown as ProductionPreview));
  const create = vi.fn(async () => { throw lost(); });
  const props: StudioMediaExecutionProps = { client: { providers: vi.fn(async () => [provider]), preview, create } as unknown as StudioProductionClient,
    assets: [], canMutate: true, canReview: true, busy: false, isCurrent: () => current, read: work => work(), mutate: work => work(), onDirtyChange: vi.fn(), onUnavailable: vi.fn() };
  const hook = renderHook(() => useStudioMediaExecution(props), { wrapper: ({ children }) => createElement(StudioProductionLeaveContext.Provider, { value: g.value }, children) });
  await waitFor(() => expect(hook.result.current.providerLoading).toBe(false));
  act(() => hook.result.current.changeOperation(operation));
  act(() => hook.result.current.changeField('providerKey', mediaProviderKey(provider)));
  act(() => hook.result.current.changeField('prompt', 'Explicit local fixture'));
  await act(async () => hook.result.current.inspect());
  act(() => hook.result.current.confirmPreview(true)); await act(async () => hook.result.current.create());
  expect(create).toHaveBeenCalledTimes(1); expect(hook.result.current.creationUncertain).toBe(true);
  const requestId = preview.mock.calls[0][0].request_id;
  expect(g.collect()).toEqual([{ unknown: true, requests: [{ requestId, owner: operation.startsWith('m5') ? 'image' : 'video', operationId: operation }] }]);
  const retained = hook.result.current.create; current = false; g.value.capture(); hook.rerender();
  await act(async () => retained()); expect(create).toHaveBeenCalledTimes(1);
  expect(g.snapshots.flat().flatMap(row => row.requests).some(row => row.requestId === requestId)).toBe(true);
});
it.each(['SAVE', 'TRACK_LOCK'] as const)('captures original Timeline %s UNKNOWN without inventing a missing protocol ID', async operation => {
  const row = source(), g = guard(); let requestId = '';
  const save = vi.fn(async () => { throw lost(); });
  const lock = vi.fn(async (_source: unknown, _track: string, _locked: boolean, id: string) => { requestId = id; throw lost(); });
  const props = timelineProps({ timelineList: async () => ({ items: [row] }), timelineGet: async () => row, timelineSave: save, timelineTrackLock: lock }, g.value);
  const hook = renderHook(() => useStudioTimelineEditor(props)); await waitFor(() => expect(hook.result.current.rows).toHaveLength(1));
  await act(async () => hook.result.current.checkServer(row.id)); act(() => hook.result.current.setAdoptConfirmed(true)); act(() => hook.result.current.adoptCandidate(false));
  if (operation === 'SAVE') { act(() => hook.result.current.change(draft => { draft.title = 'Explicit changed draft'; })); await act(async () => hook.result.current.save()); }
  else await act(async () => hook.result.current.setTrackLocked(row.timeline.tracks[0].id, true));
  expect(hook.result.current.failure).toBe('UNKNOWN');
  expect(g.collect().some(value => value.unknown)).toBe(true);
  const ids = g.collect().flatMap(value => value.requests).map(value => value.requestId);
  expect(ids).toEqual(operation === 'SAVE' ? [] : [requestId]);
  await act(async () => operation === 'SAVE' ? hook.result.current.save() : hook.result.current.setTrackLocked(row.timeline.tracks[0].id, true));
  expect(operation === 'SAVE' ? save : lock).toHaveBeenCalledTimes(1);
});
it('captures original playback build UNKNOWN before a subsequent 401 clears its controller', async () => {
  const g = guard(), missing = audioTimelinePlayback();
  const client = { timelinePlaybackPreview: vi.fn(async () => missing), timelinePlaybackBuild: vi.fn(async () => { throw lost(); }), timelinePlaybackAttestation: vi.fn(), get: vi.fn(async () => { throw new ApiError({status:401,code:'SESSION_REQUIRED',message:'Retired'}); }) };
  const props = { ...timelineProps(client, g.value), assets: audioTimelineAssets() };
  const hook = renderHook(() => useStudioTimelinePlayback({ props, source: audioTimelineRow(), isReady: () => true, onGateChange: vi.fn(), onAuthorityLost: vi.fn() }));
  await act(async () => hook.result.current.previewPlayback()); act(() => hook.result.current.setConfirmed(true)); await act(async () => hook.result.current.buildPlayback());
  expect(g.collect()[0].requests[0].requestId).toBe(missing.request_id);
  await act(async () => hook.result.current.readOriginal());
  expect(g.snapshots.flat().flatMap(row => row.requests).some(row => row.requestId === missing.request_id)).toBe(true);
  expect(client.timelinePlaybackBuild).toHaveBeenCalledTimes(1);
});
it('captures original exchange import UNKNOWN from the transfer owner', async () => {
  const g = guard(), row = source(); let id = '';
  const preview = { direction: 'IMPORT', format: 'OTIO', timeline: row.timeline, timeline_digest: row.timeline_digest, preview_digest: 'a'.repeat(64), requires_loss_acknowledgment: false } as TimelineTransferPreview;
  const client = { timelineTransferPreview: async () => preview, timelineTransferAttachment: vi.fn(), timelineTransferImport: vi.fn(async (_r: unknown, _i: unknown, _p: unknown, requestId: string) => { id = requestId; throw lost(); }) };
  const hook = renderHook(() => useStudioTimelineTransfer({ props: timelineProps(client, g.value), source: row, canOperate: true, isReady: () => true, onAdopt: vi.fn(), onAuthorityLost: vi.fn(), onGateChange: vi.fn() }));
  act(() => hook.result.current.change({ direction: 'IMPORT', content: '{"OTIO_SCHEMA":"Timeline.1","tracks":{"OTIO_SCHEMA":"Stack.1","children":[]}}' }));
  await act(async () => hook.result.current.previewTransfer()); act(() => hook.result.current.setConfirmed(true)); await act(async () => hook.result.current.importTransfer());
  expect(id).not.toBe(''); expect(g.collect()[0].requests[0].requestId).toBe(id);
  await act(async () => hook.result.current.importTransfer()); expect(client.timelineTransferImport).toHaveBeenCalledTimes(1);
});
it('captures original source-edit UNKNOWN with its immutable request ID', async () => {
  const g = guard(), row = source(); let id = '';
  const client = { timelineEdit: vi.fn(async (_r: unknown, body: {request_id: string}) => { id = body.request_id; throw lost(); }) };
  const hook = renderHook(() => useStudioTimelineSourceEdit({ props: timelineProps(client, g.value), source: row, canOperate: true, isReady: () => true, onAdopt: vi.fn(), onAuthorityLost: vi.fn(), onGateChange: vi.fn() }));
  act(() => hook.result.current.change({ asset_id: asset.id })); act(() => hook.result.current.prepare());
  act(() => hook.result.current.confirm(true)); await act(async () => hook.result.current.execute());
  expect(id).not.toBe(''); expect(g.collect()[0].requests[0].requestId).toBe(id);
  await act(async () => hook.result.current.execute()); expect(client.timelineEdit).toHaveBeenCalledTimes(1);
});
