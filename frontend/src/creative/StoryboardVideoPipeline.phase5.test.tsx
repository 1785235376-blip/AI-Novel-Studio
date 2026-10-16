// @vitest-environment jsdom
import { useState } from 'react';
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { webcrypto } from 'node:crypto';
import { ApiError } from '../api';
import { CreativeCanvas } from './CreativeCanvas';
import { StoryboardProductionPanel } from './StoryboardProductionPanel';
import { useStoryboardProductionController, type StoryboardProductionProps } from './useStoryboardProductionController';
import { checkedStoryboardReceipt, checkedStoryboardVideoRequest, type StoryboardReceipt } from './studioStoryboardContract';
import { checkedStoryboardTimelineCreation, checkedStoryboardVideoAdoption } from './studioStoryboardPipelineContract';
import { mediaProviderKey } from './useStudioMediaExecution';
import { documentInput, type CreativeDocument } from './types';
import type { CreativeClient } from './client';
import type { StudioClient, StudioAsset } from './studioClient';
import type { StudioProductionClient, ProductionProvider, ProductionJob } from './studioProductionClient';
import boundFixture from './fixtures/phase5.capture.storyboard-video-bound.json';
import boardFixture from './fixtures/phase5.capture.storyboard-video-approved.json';
import requestedFixture from './fixtures/phase5.capture.video-request.json';
import createdFixture from './fixtures/phase5.capture.timeline-created.json';
import recoveredFixture from './fixtures/phase5.capture.timeline-recovered.json';
import adoptedFixture from './fixtures/phase5.capture.video-adopted.json';
import jobFixture from './fixtures/phase5.capture.video-approved.json';

// Controlled view/client units reuse actual synthetic mounted API receipts.
// The mocks exercise controller decisions, not provider inference or acceptance.
const copy = <T,>(value: T): T => structuredClone(value);
const deferred = <T,>() => { let resolve!: (value: T) => void; const promise = new Promise<T>(yes => { resolve = yes; }); return { promise, resolve }; };
const board = () => checkedStoryboardReceipt(copy(boardFixture));
const original = () => checkedStoryboardReceipt({ ...copy(boundFixture), document_snapshot: copy(requestedFixture.shot_pin.document_snapshot), approved: true,
  shots: boundFixture.shots.map(shot => { const value = copy(shot) as Record<string, unknown>; delete value.video_result; return value; }) });
const documentFor = (receipt: StoryboardReceipt): CreativeDocument => ({ id: receipt.document_snapshot.id, version: receipt.document_snapshot.version, mode: 'STORYBOARD', title: 'Synthetic pipeline',
  status: 'DRAFT', created_at: '', updated_at: '', actor_id: 'synthetic-author', source_evidence: {}, source_chapter_ids: [], source_independent: true, scenes: [], director_notes: [], shots: receipt.shots.map(row => copy(row.shot)), video_plan: null });
const created = () => checkedStoryboardTimelineCreation(copy(createdFixture), createdFixture.timeline.novel_id, null, createdFixture.creation_receipt.document_id, copy(createdFixture.creation_receipt.request));
const recovered = () => checkedStoryboardTimelineCreation(copy(recoveredFixture), createdFixture.timeline.novel_id, null, createdFixture.creation_receipt.document_id, copy(createdFixture.creation_receipt.request));
const adopted = () => { const value = board(), shot = value.shots[0]; return checkedStoryboardVideoAdoption(copy(adoptedFixture), createdFixture.timeline.novel_id, null,
  { document_snapshot: value.document_snapshot, shot_id: shot.shot_id, shot_version: shot.shot_version, shot_digest: shot.shot_digest }, shot.video_result!); };
const job = () => copy(jobFixture) as unknown as ProductionJob;
const provider = { operation_id: 'm7.video.i2v', provider_id: requestedFixture.command.provider_id, model_id: requestedFixture.command.model_id,
  local: true, model_class: 'VIDEO', route_state: 'CONFIGURED_NOT_VERIFIED', estimated_vram_mb: null, operation_supported: true } as unknown as ProductionProvider;
const videoAsset = (): StudioAsset => ({ id: jobFixture.output_candidate.id, novel_id: createdFixture.timeline.novel_id, branch_id: null,
  version: jobFixture.approved_asset_version, sha256: jobFixture.output_candidate.digest, filename: 'synthetic-reviewed.webm', kind: 'video', media_type: 'video/webm', size: 100, created_at: '', updated_at: '' });
const unknown = () => new ApiError({ status: 503, code: 'SYNTHETIC_UNKNOWN', message: 'Synthetic receipt unavailable' });

function setup(options: { initial?: StoryboardReceipt; current?: () => boolean; panel?: boolean } = {}) {
  const initial = options.initial ?? original(), onDenied = vi.fn(), onDirtyChange = vi.fn(), onDocument = vi.fn();
  const creative = { storyboardGet: vi.fn().mockResolvedValue(initial), storyboardApprove: vi.fn(), storyboardBindImage: vi.fn(), storyboardImageRequest: vi.fn(),
    storyboardVideoRequest: vi.fn(), storyboardBindVideo: vi.fn(), storyboardTimelineCreate: vi.fn(), storyboardTimelineCreation: vi.fn(), storyboardAdoptVideo: vi.fn(), get: vi.fn() };
  const studio = { assets: vi.fn().mockResolvedValue({ items: [] }), asset: vi.fn().mockResolvedValue(videoAsset()), download: vi.fn() };
  const production = { providers: vi.fn().mockResolvedValue([provider]), list: vi.fn().mockResolvedValue([job()]), get: vi.fn().mockResolvedValue(job()),
    preview: vi.fn(), create: vi.fn(), execute: vi.fn(), refresh: vi.fn(), review: vi.fn(), candidate: vi.fn(), timelineList: vi.fn() };
  const props: Omit<StoryboardProductionProps, 'document' | 'onDocument'> = { client: creative as unknown as CreativeClient, studio: studio as unknown as StudioClient,
    production: production as unknown as StudioProductionClient, active: true, editable: true, busy: false, isBusy: () => false, isCurrent: options.current ?? (() => true),
    perform: async <T,>(work: () => Promise<T>): Promise<T> => work(), onDenied, onDirtyChange };
  let change!: (value: CreativeDocument) => void;
  function useHarness() { const [document, setDocument] = useState(documentFor(initial)); change = setDocument;
    return useStoryboardProductionController({ ...props, document, onDocument: value => { onDocument(value); setDocument(value); } }); }
  function Harness() { const [document, setDocument] = useState(documentFor(initial)); change = setDocument;
    return <StoryboardProductionPanel {...props} document={document} onDocument={value => { onDocument(value); setDocument(value); }} />; }
  const hook = options.panel ? undefined : renderHook(useHarness), view = options.panel ? render(<Harness />) : undefined;
  return { initial, creative, studio, production, onDenied, onDirtyChange, onDocument, hook, view, change: (value: StoryboardReceipt) => change(documentFor(value)) };
}
async function read(state: ReturnType<typeof setup>) { act(() => state.hook!.result.current.read()); await waitFor(() => expect(state.hook!.result.current.receipt).toBeTruthy()); }
async function createTimeline(state: ReturnType<typeof setup>) { state.creative.storyboardTimelineCreate.mockResolvedValue(await created()); await read(state);
  act(() => { state.hook!.result.current.confirm(true); state.hook!.result.current.chooseTimelineShot('shot-1', true); });
  act(() => state.hook!.result.current.makeTimeline()); await waitFor(() => expect(state.hook!.result.current.creation).toBeTruthy()); }
async function adoptionReady(state: ReturnType<typeof setup>) { await createTimeline(state); state.creative.storyboardGet.mockResolvedValue(board()); act(() => state.change(board())); await read(state);
  act(() => state.hook!.result.current.chooseClip(createdFixture.storyboard_origin.shots[0].clip_id)); act(() => state.hook!.result.current.changeRange('out', '500')); act(() => state.hook!.result.current.confirmAdoption(true)); }
beforeEach(() => { vi.stubGlobal('crypto', { subtle: webcrypto.subtle, getRandomValues: webcrypto.getRandomValues.bind(webcrypto), randomUUID: vi.fn(() => createdFixture.creation_receipt.request_id) });
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Unexpected view network'))); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('Phase 5 explicit original Video production view', () => {
  it('prepares a pinned I2V command for the original media panel without dispatch', async () => {
    const state = setup({ panel: true }); expect(state.creative.storyboardGet).not.toHaveBeenCalled(); expect(state.production.list).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '明确读取已保存创作回执' })); await screen.findByRole('region', { name: '分镜生产预览' });
    fireEvent.click(screen.getByRole('button', { name: '明确读取已有图片与模型配置' })); await waitFor(() => expect(state.production.providers).toHaveBeenCalledOnce());
    fireEvent.change(screen.getByLabelText('镜头视频操作'), { target: { value: 'm7.video.i2v' } }); await screen.findByRole('option', { name: `${provider.provider_id} · ${provider.model_id}` }); fireEvent.change(screen.getByLabelText('已有视频模型'), { target: { value: mediaProviderKey(provider) } });
    state.creative.storyboardVideoRequest.mockResolvedValue(checkedStoryboardVideoRequest(copy(requestedFixture), copy(requestedFixture.shot_pin)));
    fireEvent.click(screen.getByRole('button', { name: '准备版本绑定视频请求' })); await screen.findByRole('heading', { name: '原分镜视频请求' });
    expect(state.creative.storyboardVideoRequest).toHaveBeenCalledWith(state.initial, state.initial.shots[0], 'm7.video.i2v', provider.provider_id, provider.model_id, expect.any(String), {});
    expect(screen.getByRole('button', { name: '读取制作预览' })).toBeTruthy(); expect(screen.queryByLabelText('本次提示词')).toBeNull();
    expect(state.production.preview).not.toHaveBeenCalled(); expect(state.production.create).not.toHaveBeenCalled(); expect(state.production.execute).not.toHaveBeenCalled(); expect(state.production.review).not.toHaveBeenCalled();
  });
  it('rechecks the exact APPROVED Job and formal Asset before binding its historical Shot pin', async () => {
    const state = setup(); await read(state); act(() => state.hook!.result.current.loadVideoJobs()); await waitFor(() => expect(state.hook!.result.current.videoJobs).toHaveLength(1));
    state.creative.storyboardBindVideo.mockResolvedValue(checkedStoryboardReceipt(boundFixture)); state.creative.get.mockResolvedValue(documentFor(checkedStoryboardReceipt(boundFixture)));
    act(() => state.hook!.result.current.chooseVideoJob(jobFixture.id)); act(() => state.hook!.result.current.bindVideo()); await waitFor(() => expect(state.onDocument).toHaveBeenCalledOnce());
    expect(state.production.get).toHaveBeenCalledWith('video', jobFixture.id); expect(state.studio.asset).toHaveBeenCalledWith(jobFixture.output_candidate.id);
    expect(state.creative.storyboardBindVideo).toHaveBeenCalledWith(state.initial, state.initial.shots[0], { asset_id: jobFixture.output_candidate.id, version: 2, digest: jobFixture.output_candidate.digest, kind: 'video' },
      { id: jobFixture.id, version: 8, request_digest: jobFixture.request_digest, receipt_digest: jobFixture.receipt_digest }, requestedFixture.shot_pin);
    expect(state.hook!.result.current.receipt?.approved).toBe(false); expect(state.hook!.result.current.receipt?.shots[0].video_result?.source_shot.document_snapshot.version).toBe(3);
  });
  it('does not chain Asset or binding requests after a late Job read loses identity', async () => {
    let current = true; const state = setup({ current: () => current }), pending = deferred<ProductionJob>(); await read(state); act(() => state.hook!.result.current.loadVideoJobs());
    await waitFor(() => expect(state.hook!.result.current.videoJobs).toHaveLength(1)); state.production.get.mockReturnValueOnce(pending.promise);
    act(() => state.hook!.result.current.chooseVideoJob(jobFixture.id)); act(() => state.hook!.result.current.bindVideo()); current = false;
    await act(async () => { pending.resolve(job()); await pending.promise; }); expect(state.studio.asset).not.toHaveBeenCalled(); expect(state.creative.storyboardBindVideo).not.toHaveBeenCalled(); expect(state.onDocument).not.toHaveBeenCalled();
  });
  it('does not bind changed formal Asset versions even with an APPROVED Job', async () => {
    const state = setup(); await read(state); act(() => state.hook!.result.current.loadVideoJobs()); await waitFor(() => expect(state.hook!.result.current.videoJobs).toHaveLength(1));
    state.studio.asset.mockResolvedValue({ ...videoAsset(), version: 3 }); act(() => state.hook!.result.current.chooseVideoJob(jobFixture.id)); act(() => state.hook!.result.current.bindVideo());
    await waitFor(() => expect(state.hook!.result.current.uncertain).toBe(true)); expect(state.creative.storyboardBindVideo).not.toHaveBeenCalled();
  });
});

describe('Phase 5 separate original Timeline ownership and UNKNOWN recovery', () => {
  it.each([503, 200])('retains a lost/invalid creation reply (%s) and recovers only by original request GET', async status => {
    const state = setup(); await read(state); state.creative.storyboardTimelineCreate.mockRejectedValue(status === 503 ? unknown() : new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: 'Synthetic invalid receipt' }));
    act(() => { state.hook!.result.current.confirm(true); state.hook!.result.current.chooseTimelineShot('shot-1', true); }); act(() => state.hook!.result.current.makeTimeline());
    await waitFor(() => expect(state.hook!.result.current.timelineUnknown).toBe(true)); const savedBody = state.creative.storyboardTimelineCreate.mock.calls[0][1];
    await read(state); act(() => state.hook!.result.current.confirm(true)); act(() => state.hook!.result.current.makeTimeline()); expect(state.creative.storyboardTimelineCreate).toHaveBeenCalledOnce();
    state.creative.storyboardTimelineCreation.mockResolvedValue(await recovered()); act(() => state.hook!.result.current.inspectTimelineRecovery()); await waitFor(() => expect(state.hook!.result.current.timelineUnknown).toBe(false));
    expect(state.creative.storyboardTimelineCreation).toHaveBeenCalledWith(state.initial, savedBody); expect(state.hook!.result.current.creation?.creation_receipt.creation_snapshot.version).toBe(1);
    expect(state.hook!.result.current.creation?.timeline.version).toBe(2); expect(state.creative.storyboardTimelineCreate).toHaveBeenCalledOnce(); expect(state.production.timelineList).not.toHaveBeenCalled();
  });
  it('adopts only a reviewed video into the mapped original clip and keeps initial creation evidence', async () => {
    const state = setup(); await adoptionReady(state); state.creative.storyboardAdoptVideo.mockResolvedValue(await adopted()); act(() => state.hook!.result.current.adoptVideo());
    await waitFor(() => expect(state.hook!.result.current.creation?.timeline.version).toBe(2)); const args = state.creative.storyboardAdoptVideo.mock.calls[0];
    expect(args[0]).toEqual(board()); expect(args[1].video_result.source_shot.document_snapshot.version).toBe(3); expect(args[3]).toMatchObject({ expected_timeline_version: 1, reviewed_timeline_digest: createdFixture.timeline.timeline_digest,
      clip_id: createdFixture.storyboard_origin.shots[0].clip_id, in_ms: 0, out_ms: 500, include_audio: false });
    expect(state.hook!.result.current.creation?.creation_receipt.creation_snapshot.version).toBe(1); expect(state.hook!.result.current.creation?.storyboard_origin).toEqual(createdFixture.storyboard_origin);
  });
  it('does not replay unknown adoption after a saved Storyboard read or a current Timeline lacking the effect proof', async () => {
    const state = setup(); await adoptionReady(state); state.creative.storyboardAdoptVideo.mockRejectedValue(unknown()); act(() => state.hook!.result.current.adoptVideo());
    await waitFor(() => expect(state.hook!.result.current.adoptionUnknown).toBe(true)); await read(state); expect(state.hook!.result.current.adoptionUnknown).toBe(true);
    state.creative.storyboardTimelineCreation.mockResolvedValue(await created()); act(() => state.hook!.result.current.inspectTimelineRecovery()); await waitFor(() => expect(state.hook!.result.current.loading).toBe(''));
    expect(state.hook!.result.current.adoptionUnknown).toBe(true); act(() => state.hook!.result.current.confirmAdoption(true)); act(() => state.hook!.result.current.adoptVideo());
    expect(state.creative.storyboardAdoptVideo).toHaveBeenCalledOnce(); expect(state.onDirtyChange).toHaveBeenLastCalledWith(true);
  });
  it('clears unknown adoption only for the exact current full request receipt, without another write', async () => {
    const state = setup(); await adoptionReady(state); vi.mocked(crypto.randomUUID).mockReturnValue(adoptedFixture.adoption_receipt.request.request_id as `${string}-${string}-${string}-${string}-${string}`);
    state.creative.storyboardAdoptVideo.mockRejectedValue(unknown()); act(() => state.hook!.result.current.adoptVideo()); await waitFor(() => expect(state.hook!.result.current.adoptionUnknown).toBe(true));
    state.creative.storyboardTimelineCreation.mockResolvedValue(await recovered()); act(() => state.hook!.result.current.inspectTimelineRecovery()); await waitFor(() => expect(state.hook!.result.current.adoptionUnknown).toBe(false));
    expect(state.hook!.result.current.creation?.timeline.version).toBe(2); expect(state.creative.storyboardAdoptVideo).toHaveBeenCalledOnce(); expect(state.onDirtyChange).toHaveBeenLastCalledWith(false);
  });
  it('blocks locked tracks and invalid source ranges before calling the original adoption endpoint', async () => {
    const state = setup(); await adoptionReady(state); act(() => state.hook!.result.current.changeRange('out', '0')); act(() => state.hook!.result.current.confirmAdoption(true)); act(() => state.hook!.result.current.adoptVideo());
    expect(state.creative.storyboardAdoptVideo).not.toHaveBeenCalled(); const locked = await created(); locked.timeline.timeline.tracks[0].locked = true;
    state.creative.storyboardTimelineCreation.mockResolvedValue(locked); act(() => state.hook!.result.current.inspectTimelineRecovery()); await waitFor(() => expect(state.hook!.result.current.eligibleClips[0]?.locked).toBe(true));
    act(() => state.hook!.result.current.changeRange('out', '500')); act(() => state.hook!.result.current.confirmAdoption(true)); act(() => state.hook!.result.current.adoptVideo()); expect(state.creative.storyboardAdoptVideo).not.toHaveBeenCalled();
  });
  it('permits a fresh explicit range confirmation after a definite pre-execution 422 without automatic retry', async () => {
    const state = setup(); await adoptionReady(state); state.creative.storyboardAdoptVideo.mockRejectedValue(new ApiError({ status: 422, code: 'SYNTHETIC_RANGE', message: 'Synthetic source range rejected' }));
    act(() => state.hook!.result.current.adoptVideo()); await waitFor(() => expect(state.hook!.result.current.error).toBeTruthy()); expect(state.hook!.result.current.adoptionUnknown).toBe(false);
    expect(state.creative.storyboardAdoptVideo).toHaveBeenCalledOnce(); act(() => state.hook!.result.current.changeRange('out', '400')); act(() => state.hook!.result.current.confirmAdoption(true)); act(() => state.hook!.result.current.adoptVideo());
    await waitFor(() => expect(state.creative.storyboardAdoptVideo).toHaveBeenCalledTimes(2));
  });
});

describe('Phase 5 authored intent and original Canvas status', () => {
  it('keeps video intent bounded, explicitly clearable and omitted from old document input', () => {
    const initial = documentFor(board()), onChange = vi.fn(); const old = documentInput(initial); delete old.shots[0].video_generation_hint;
    const view = render(<CreativeCanvas draft={old} version={initial.version} dirty={false} canEdit busy={false} productionShots={board().shots} productionApproved selectedShotId="shot-1"
      onScene={vi.fn()} onShot={vi.fn()} onChange={onChange} onSave={vi.fn()} onNew={vi.fn()} />);
    const input = screen.getByLabelText('视频生成提示') as HTMLTextAreaElement; expect(input.maxLength).toBe(4000); expect(input.closest('details')?.open).toBe(false);
    expect(screen.getByText('正式视频 v2 · 分镜已批准')).toBeTruthy(); fireEvent.change(input, { target: { value: 'Camera follows the authored scene' } });
    expect(onChange.mock.calls[0][0].shots[0].video_generation_hint).toBe('Camera follows the authored scene');
    view.rerender(<CreativeCanvas draft={{ ...old, shots: [{ ...old.shots[0], video_generation_hint: 'old authored intent' }] }} dirty canEdit busy={false} onScene={vi.fn()} onShot={vi.fn()} onChange={onChange} onSave={vi.fn()} onNew={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('视频生成提示'), { target: { value: '' } }); expect(Object.hasOwn(onChange.mock.calls.at(-1)![0].shots[0], 'video_generation_hint')).toBe(false);
    expect(Object.hasOwn(documentInput({ ...initial, shots: [{ ...initial.shots[0], video_generation_hint: null }] }).shots[0], 'video_generation_hint')).toBe(false);
  });
});
