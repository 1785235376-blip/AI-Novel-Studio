// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { webcrypto } from 'node:crypto';
import { Blob as NodeBlob } from 'node:buffer';
import { ApiError } from '../api';
import { useLocalHostSession } from '../localHostSession';
import { captionCommand, rulerTicks, timebaseOf, validateTimebase } from '../nle/timelineOps';
import { StudioTimelineEditor } from './StudioTimelineEditor';
import { StudioTimelinePlaybackPanel } from './StudioTimelinePlaybackPanel';
import { StudioMediaExecutionPanel } from './StudioMediaExecutionPanel';
import { useStudioTimelineEditor, type StudioTimelineEditorProps } from './useStudioTimelineEditor';
import { useStudioTimelinePlayback } from './useStudioTimelinePlayback';
import { checkedTimeline, checkedTimelineRow, cloneTimeline, newTimelineDraft, type StudioTimelineDraft } from './studioTimelineTypes';
import { checkedTimelineExportPreview, checkedTimelineExportProfile } from './studioTimelineExportTypes';
import { checkedTimelinePlayback } from './studioTimelinePlaybackTypes';
import { studioProductionClient, type StudioProductionClient } from './studioProductionClient';
import { audioTimelineAssets, audioTimelineBytes, audioTimelineExport, audioTimelineJob, audioTimelinePlayback, audioTimelineProject, audioTimelineRow } from './studioAudioTimeline.testFixtures';

const response = (value: unknown) => ({ ok: true, status: 200, json: async () => value });
const propsFor = (client: StudioProductionClient): StudioTimelineEditorProps => ({ client, mediaKind: 'AUDIO', projectId: audioTimelineProject, assets: audioTimelineAssets(),
  canMutate: true, busy: false, isCurrent: () => true, read: async work => work(), mutate: async work => work(), onDirtyChange: vi.fn(), onJob: vi.fn(), onUnavailable: vi.fn() });
beforeEach(() => {
  vi.stubGlobal('crypto', webcrypto); useLocalHostSession.setState({ token: 'synthetic-audio-timeline', actorId: '' });
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:audio-timeline') });
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() });
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {});
  vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('closed independent audio timeline contract', () => {
  it('preserves pure schema3 and does not inject a video canvas, FPS or captions', () => {
    const timeline = checkedTimeline(audioTimelineRow().timeline);
    expect(Object.keys(timeline)).toEqual(['schema_version', 'media_kind', 'duration_ms', 'tracks']);
    expect(timeline.tracks[0].clips[0]).toMatchObject({ gain_db: -3, fade_in_ms: 100, fade_out_ms: 200, speed_num: 1, speed_den: 1 });
    expect(newTimelineDraft('AUDIO').timeline).toEqual({ schema_version: 3, media_kind: 'AUDIO', duration_ms: 5000, tracks: [] });
    expect(newTimelineDraft().timeline).not.toHaveProperty('schema_version');
  });
  it.each(['width', 'height', 'fps', 'captions', 'unknown'])('rejects forbidden audio field %s', key => {
    expect(() => checkedTimeline({ ...audioTimelineRow().timeline, [key]: key === 'captions' ? [] : 24 })).toThrow();
  });
  it.each(['missing discriminator', 'video track', 'video source', 'visual clip', 'too many tracks', 'too long', 'fades'])('fails closed on %s', fault => {
    const value: any = cloneTimeline(audioTimelineRow().timeline);
    if (fault === 'missing discriminator') delete value.media_kind;
    if (fault === 'video track') value.tracks[0].kind = 'VIDEO';
    if (fault === 'video source') value.tracks[0].clips[0].source_snapshot.asset_kind = 'video';
    if (fault === 'visual clip') value.tracks[0].clips[0].width = 64;
    if (fault === 'too many tracks') value.tracks = Array.from({ length: 5 }, (_, i) => ({ ...cloneTimeline(value.tracks[0]), id: `track${i}`, order: i, clips: [{ ...cloneTimeline(value.tracks[0].clips[0]), id: `clip${i}` }] }));
    if (fault === 'too long') value.duration_ms = 600001;
    if (fault === 'fades') value.tracks[0].clips[0].fade_out_ms = 1000;
    expect(() => checkedTimeline(value)).toThrow();
  });
  it('keeps WAV profile closed and binds it to the audio source', () => {
    const row = audioTimelineRow(), preview = audioTimelineExport(row);
    expect(checkedTimelineExportProfile({ preset: 'AUDIO_WAV_PCM16' })).toEqual({ preset: 'AUDIO_WAV_PCM16' });
    expect(() => checkedTimelineExportProfile({ preset: 'AUDIO_WAV_PCM16', audio_bitrate_kbps: 96 })).toThrow();
    expect(checkedTimelineExportPreview(preview, row, { preset: 'AUDIO_WAV_PCM16' })).toEqual(preview);
    expect(() => checkedTimelineExportPreview({ ...preview, export_profile: { preset: 'REVIEW_MP4' } }, row, { preset: 'REVIEW_MP4' })).toThrow();
    expect(checkedTimelinePlayback(audioTimelinePlayback(), row, value => value as ReturnType<typeof audioTimelineJob>, { novelId: audioTimelineProject, branchId: null }).export_preview.export_profile.preset).toBe('AUDIO_WAV_PCM16');
  });
  it('uses a genuine millisecond audio ruler without frame labels or subtitle actions', () => {
    const timeline = audioTimelineRow().timeline, timebase = timebaseOf(timeline);
    expect(timebase).toEqual({ durationMs: 1000, mediaKind: 'AUDIO' }); expect(validateTimebase(timebase).ok).toBe(true);
    expect(validateTimebase({ ...timebase, fps: 24 }).ok).toBe(false);
    expect(rulerTicks({ startMs: 0, scale: 1 }, timebase, 960).ticks.every(tick => !Object.hasOwn(tick, 'frame'))).toBe(true);
    expect(captionCommand('caption-insert', { timeline, caption: { start_ms: 0, end_ms: 100, text: 'no' } }).ok).toBe(false);
  });
});

function editorFixture() {
  let saved = audioTimelineRow();
  const client = { timelineList: vi.fn(async () => ({ items: [cloneTimeline(saved)] })), timelineGet: vi.fn(async () => cloneTimeline(saved)),
    timelineSave: vi.fn(async (_id: string | undefined, body: StudioTimelineDraft & { expected_version: number }) => {
      saved = checkedTimelineRow({ ...saved, ...body, version: body.expected_version + 1, timeline_digest: '4'.repeat(64) }); return cloneTimeline(saved);
    }), timelineRender: vi.fn(), timelineExportPreview: vi.fn(async () => audioTimelineExport(saved)), timelineExport: vi.fn(), list: vi.fn(async () => []), timelineEdit: vi.fn() };
  const props = propsFor(client as unknown as StudioProductionClient);
  const hook = renderHook((next: StudioTimelineEditorProps) => useStudioTimelineEditor(next), { initialProps: props }); return { client, props, hook };
}
async function adopt(state: ReturnType<typeof editorFixture>) {
  await waitFor(() => expect(state.hook.result.current.rows).toHaveLength(1));
  await act(async () => state.hook.result.current.checkServer('audio-timeline'));
  act(() => state.hook.result.current.setAdoptConfirmed(true)); act(() => state.hook.result.current.adoptCandidate(false));
}
it('edits trim, gain and fades, explicitly saves CAS and reopens the original audio owner', async () => {
  const state = editorFixture(); await adopt(state);
  act(() => state.hook.result.current.trimClip('dialogue', 'voice', 100, 900, false));
  act(() => state.hook.result.current.change(input => { input.timeline.tracks[0].gain_db = -6; Object.assign(input.timeline.tracks[0].clips[0], { gain_db: 2, fade_in_ms: 50, fade_out_ms: 80 }); }));
  expect(state.client.timelineSave).not.toHaveBeenCalled(); const intended = cloneTimeline(state.hook.result.current.draft!);
  await act(async () => state.hook.result.current.save()); expect(state.client.timelineSave).toHaveBeenCalledWith('audio-timeline', { ...intended, expected_version: 1 });
  expect(state.hook.result.current.base?.version).toBe(2); expect(state.hook.result.current.exportProfile).toEqual({ preset: 'AUDIO_WAV_PCM16' });
  expect(state.client.timelineRender).not.toHaveBeenCalled(); expect(state.client.timelineExport).not.toHaveBeenCalled();
  state.hook.unmount(); const reopened = renderHook(() => useStudioTimelineEditor(state.props));
  await waitFor(() => expect(reopened.result.current.rows).toHaveLength(1)); await act(async () => reopened.result.current.checkServer('audio-timeline'));
  act(() => reopened.result.current.setAdoptConfirmed(true)); act(() => reopened.result.current.adoptCandidate(false));
  expect(reopened.result.current.draft).toEqual(intended); expect(reopened.result.current.draft?.timeline).not.toHaveProperty('width');
});
it('keeps audio save uncertainty fenced without repeated saves', async () => {
  const state = editorFixture(); await adopt(state); state.client.timelineSave.mockRejectedValue(new ApiError({ status: 503, code: 'UNKNOWN', message: 'unknown' }));
  act(() => state.hook.result.current.change(value => { value.title = 'retained'; })); await act(async () => state.hook.result.current.save());
  await act(async () => state.hook.result.current.save()); expect(state.client.timelineSave).toHaveBeenCalledTimes(1);
  expect(state.hook.result.current.failure).toBe('UNKNOWN'); expect(state.hook.result.current.draft?.title).toBe('retained');
});
it('shows the original editor with audio controls and no visual canvas, captions or MP4 options', async () => {
  const state = editorFixture(); state.hook.unmount(); render(<StudioTimelineEditor {...state.props} />);
  await waitFor(() => expect(screen.getByRole('option', { name: 'Audio only · v1' })).toBeTruthy());
  expect(screen.queryByLabelText('画面宽度')).toBeNull(); expect(screen.queryByLabelText('帧率')).toBeNull();
  expect(screen.queryByRole('button', { name: '添加视频轨道' })).toBeNull(); expect(screen.queryByRole('button', { name: '添加字幕' })).toBeNull();
  expect(screen.getByRole('button', { name: '添加音频轨道' })).toBeTruthy(); expect(state.client.timelineRender).not.toHaveBeenCalled();
});

it.each(['valid', 'wrong channels', 'extra visual', 'wrong count', 'wrong bytes', 'wrong candidate', 'missing proof'])('checks audio timeline original job receipt: %s', async fault => {
  const job = audioTimelineJob(), raw: any = cloneTimeline(job);
  if (fault === 'wrong channels') raw.media_measurement.channels = 1;
  if (fault === 'extra visual') raw.media_measurement.width = 640;
  if (fault === 'wrong count') raw.media_measurement.sample_count--;
  if (fault === 'wrong bytes') raw.media_measurement.byte_count--;
  if (fault === 'wrong candidate') raw.output_candidate.kind = 'video';
  if (fault === 'missing proof') raw.media_measurement = null;
  vi.stubGlobal('fetch', vi.fn(async () => response(raw))); const client = studioProductionClient(audioTimelineProject, { sessionToken: '' });
  if (fault === 'valid') expect(await client.get('timeline', job.id)).toEqual(job);
  else await expect(client.get('timeline', job.id)).rejects.toBeTruthy();
});

it('builds, verifies and loads actual WAV bytes only after explicit actions, then revokes stale audio', async () => {
  const source = audioTimelineRow(), job = audioTimelineJob(), missing = audioTimelinePlayback(), present = audioTimelinePlayback(job);
  const client = { timelinePlaybackPreview: vi.fn(async () => missing), timelinePlaybackBuild: vi.fn(async () => present),
    timelinePlaybackAttestation: vi.fn(async () => ({ sha256: job.output_candidate!.digest, byte_count: 192044, asset_version: 1 })),
    get: vi.fn(async () => job), candidate: vi.fn(async () => new NodeBlob([audioTimelineBytes()], { type: 'audio/wav' })) };
  const props = propsFor(client as unknown as StudioProductionClient), options = { props, source, isReady: () => true, onGateChange: vi.fn(), onAuthorityLost: vi.fn() };
  const hook = renderHook(next => useStudioTimelinePlayback(next), { initialProps: options });
  expect(client.timelinePlaybackPreview).not.toHaveBeenCalled(); await act(async () => hook.result.current.previewPlayback());
  expect(client.timelinePlaybackBuild).not.toHaveBeenCalled(); act(() => hook.result.current.setConfirmed(true)); await act(async () => hook.result.current.buildPlayback());
  expect(client.candidate).not.toHaveBeenCalled(); act(() => hook.result.current.setConfirmed(true)); await act(async () => hook.result.current.loadPlayback());
  expect(hook.result.current.visible?.mediaType).toBe('audio/wav'); expect(client.timelinePlaybackBuild).toHaveBeenCalledTimes(1);
  const view = render(<StudioTimelinePlaybackPanel controller={hook.result.current} />);
  const audio = screen.getByLabelText('已核验的时间线缓存音频'); expect(audio).toBeInstanceOf(HTMLAudioElement); expect(view.container.querySelector('video')).toBeNull();
  expect(HTMLMediaElement.prototype.play).not.toHaveBeenCalled(); expect(audio.hasAttribute('autoplay')).toBe(false);
  fireEvent.change(screen.getByLabelText('预览播放速度'), { target: { value: '1.5' } }); expect((audio as HTMLAudioElement).playbackRate).toBe(1.5);
  await act(async () => hook.result.current.loadPlayback()); expect(client.candidate).toHaveBeenCalledTimes(1); expect(client.timelinePlaybackAttestation).toHaveBeenCalledTimes(2);
  hook.rerender({ ...options, props: { ...props, assets: audioTimelineAssets().map(asset => ({ ...asset, version: 2 })) } });
  await waitFor(() => expect(hook.result.current.visible).toBeUndefined()); expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:audio-timeline');
});
it('preserves audio playback UNKNOWN and recovers only the original job without a second build', async () => {
  const source = audioTimelineRow(), job = audioTimelineJob(), missing = audioTimelinePlayback();
  const client = { timelinePlaybackPreview: vi.fn(async () => missing), timelinePlaybackBuild: vi.fn(async () => { throw new Error('lost response'); }),
    timelinePlaybackAttestation: vi.fn(), get: vi.fn(async () => job) };
  const hook = renderHook(() => useStudioTimelinePlayback({ props: propsFor(client as unknown as StudioProductionClient), source, isReady: () => true, onGateChange: vi.fn(), onAuthorityLost: vi.fn() }));
  await act(async () => hook.result.current.previewPlayback()); act(() => hook.result.current.setConfirmed(true)); await act(async () => hook.result.current.buildPlayback());
  expect(hook.result.current.unknown?.preview.request_id).toBe(missing.request_id); await act(async () => hook.result.current.buildPlayback());
  expect(client.timelinePlaybackBuild).toHaveBeenCalledTimes(1); await act(async () => hook.result.current.readOriginal()); expect(hook.result.current.unknown).toBeUndefined();
  expect(hook.result.current.preview?.job?.id).toBe(job.id); expect(client.get).toHaveBeenCalledWith('timeline', missing.job_id);
});

it.each(['audio/wav', 'audio/mpeg'])('reviews the external timeline job through the original media panel only after WAV proof: %s', async mime => {
  const job = audioTimelineJob(); let current = cloneTimeline(job);
  const fetcher = vi.fn(async (url: string) => {
    if (url.endsWith('/providers')) return response({ items: [], health_probed: false, credentials_read: false });
    if (url.endsWith('/jobs')) return response({ items: [current] });
    if (url.endsWith('/candidate')) return { ...response({}), blob: async () => new NodeBlob([audioTimelineBytes()], { type: mime }) };
    if (url.endsWith('/review')) { current = { ...current, version: 4, status: 'APPROVED', approved_asset_version: 1 }; return response(current); }
    return response(current);
  }); vi.stubGlobal('fetch', fetcher);
  const client = studioProductionClient(audioTimelineProject, { sessionToken: '' });
  const checked = await client.get('timeline', job.id); const props = propsFor(client);
  render(<StudioMediaExecutionPanel {...props} canReview externalJob={checked} />);
  const load = await screen.findByRole('button', { name: '读取并核对候选媒体' });
  const review = screen.getByRole('button', { name: '明确审核并入素材库' }) as HTMLButtonElement; expect(review.disabled).toBe(true);
  fireEvent.click(load);
  if (mime !== 'audio/wav') { await screen.findByText(/音频时间线 WAV 候选与绑定/); expect(screen.queryByLabelText('本任务的音频候选')).toBeNull(); return; }
  expect(await screen.findByLabelText('本任务的音频候选')).toBeInstanceOf(HTMLAudioElement); expect(HTMLMediaElement.prototype.play).not.toHaveBeenCalled();
  expect(review.disabled).toBe(true); fireEvent.click(screen.getByLabelText('已查看本次候选，确认采用当前任务版本与输出摘要'));
  fireEvent.click(review); await screen.findByText('原任务已审核入库。产品里程碑验收状态仍为 LOCAL_REQUIRED。');
  expect(fetcher.mock.calls.filter(([url]) => url.endsWith('/review'))).toHaveLength(1);
});
it('requires explicit WAV export preview and confirmation, then reserves the original export once', async () => {
  const state = editorFixture(); await adopt(state);
  state.client.timelineExport.mockImplementation(async (_source, profile, requestId) => ({ ...audioTimelineJob(), request_id: requestId,
    execution_recipe: { ...audioTimelineExport().execution_recipe, export_profile: profile } }));
  expect(state.hook.result.current.canRender).toBe(false); expect(state.hook.result.current.canExport).toBe(false);
  await act(async () => state.hook.result.current.exportTimeline()); expect(state.client.timelineExport).not.toHaveBeenCalled();
  await act(async () => state.hook.result.current.previewExport()); expect(state.hook.result.current.exportPreview?.export_profile.preset).toBe('AUDIO_WAV_PCM16');
  act(() => state.hook.result.current.setExportConfirmed(true)); await act(async () => state.hook.result.current.exportTimeline());
  expect(state.client.timelineExport).toHaveBeenCalledTimes(1); expect(state.hook.result.current.attempt?.state).toBe('RETURNED'); expect(state.props.onJob).toHaveBeenCalledTimes(1);
  await act(async () => state.hook.result.current.exportTimeline()); expect(state.client.timelineExport).toHaveBeenCalledTimes(1);
});
it('does not resend an UNKNOWN WAV export and retains the request identity', async () => {
  const state = editorFixture(); await adopt(state); state.client.timelineExport.mockRejectedValue(new Error('lost export receipt'));
  await act(async () => state.hook.result.current.previewExport()); act(() => state.hook.result.current.setExportConfirmed(true));
  await act(async () => state.hook.result.current.exportTimeline()); const requestId = state.hook.result.current.attempt?.requestId;
  expect(requestId).toBeTruthy(); expect(state.hook.result.current.attempt?.state).toBe('UNKNOWN');
  await act(async () => state.hook.result.current.exportTimeline()); expect(state.client.timelineExport).toHaveBeenCalledTimes(1); expect(state.hook.result.current.attempt?.requestId).toBe(requestId);
});
it('filters audio from VIDEO workspace and retires audio drafts and callbacks on mode change', async () => {
  const state = editorFixture(); await adopt(state); const retained = state.hook.result.current.change;
  state.hook.rerender({ ...state.props, mediaKind: 'VIDEO' }); await waitFor(() => expect(state.hook.result.current.rows).toHaveLength(0));
  expect(state.hook.result.current.draft?.timeline.schema_version).toBeUndefined(); expect(state.hook.result.current.base).toBeUndefined();
  act(() => retained(value => { value.timeline = audioTimelineRow().timeline; })); expect(state.hook.result.current.draft?.timeline.schema_version).toBeUndefined();
  await act(async () => state.hook.result.current.checkServer('audio-timeline')); expect(state.hook.result.current.candidate).toBeUndefined();
  expect(state.hook.result.current.error).toContain('媒体类型与当前工作区不一致');
});
it('keeps ten-minute editing but refuses audio preview above the original WAV byte ceiling', async () => {
  const state = editorFixture(); await adopt(state);
  act(() => state.hook.result.current.change(input => { input.timeline.duration_ms = 600000; })); await act(async () => state.hook.result.current.save());
  expect(state.hook.result.current.base?.timeline.duration_ms).toBe(600000); expect(state.hook.result.current.canPreviewExport).toBe(false);
  await act(async () => state.hook.result.current.previewExport()); expect(state.client.timelineExportPreview).not.toHaveBeenCalled();
  expect(state.hook.result.current.error).toContain('136533');
});
it('offers original reconciliation for UNKNOWN audio timeline tasks without automatic execution', async () => {
  const job = { ...audioTimelineJob(), status: 'UNKNOWN' as const }, client = { providers: vi.fn(async () => []), list: vi.fn(async () => [job]),
    get: vi.fn(async () => job), reconcile: vi.fn(async () => ({ ...audioTimelineJob(), version: 4 })) };
  render(<StudioMediaExecutionPanel {...propsFor(client as unknown as StudioProductionClient)} canReview externalJob={job} />);
  const reconcile = await screen.findByRole('button', { name: '核对中断状态，不重新发送' });
  expect(client.reconcile).not.toHaveBeenCalled(); expect((screen.getByRole('button', { name: '明确执行当前入队任务' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(reconcile); await waitFor(() => expect(client.reconcile).toHaveBeenCalledTimes(1));
});
