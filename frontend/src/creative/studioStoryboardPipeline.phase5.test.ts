import { describe, expect, it, vi } from 'vitest';
import boundFixture from './fixtures/phase5.capture.storyboard-video-bound.json';
import boardFixture from './fixtures/phase5.capture.storyboard-video-approved.json';
import requestedFixture from './fixtures/phase5.capture.video-request.json';
import createdFixture from './fixtures/phase5.capture.timeline-created.json';
import recoveredFixture from './fixtures/phase5.capture.timeline-recovered.json';
import adoptedFixture from './fixtures/phase5.capture.video-adopted.json';
import { checkedStoryboardReceipt, checkedStoryboardVideoRequest, type StoryboardVideoResult, type ShotPin } from './studioStoryboardContract';
import { checkedStoryboardCreateInput, checkedStoryboardTimelineCreation, checkedStoryboardVideoAdoption } from './studioStoryboardPipelineContract';
import { createStoryboardClient } from './studioStoryboardClient';

// Exact public JSON from the File-mounted synthetic API/real tiny CPU-video run.
// These contract fixtures do not establish real-model or Windows acceptance.
const copy = <T,>(value: T): T => structuredClone(value);
const row = (value: unknown) => value as Record<string, unknown>;
const project = createdFixture.timeline.novel_id;
const document = createdFixture.creation_receipt.document_id;
const input = () => checkedStoryboardCreateInput(copy(createdFixture.creation_receipt.request));
const pin = (): ShotPin => copy(requestedFixture.shot_pin);
const video = (): StoryboardVideoResult => checkedStoryboardReceipt(copy(boundFixture)).shots[0].video_result!;
const sourceBoard = () => checkedStoryboardReceipt({ ...copy(boundFixture), document_snapshot: pin().document_snapshot,
  approved: true, shots: boundFixture.shots.map(shot => { const value = row(copy(shot)); delete value.video_result; return value; }) });
const adoptedBoard = () => checkedStoryboardReceipt(copy(boardFixture));
const expectedAdoptionPin = (): ShotPin => ({ document_snapshot: adoptedBoard().document_snapshot,
  shot_id: adoptedBoard().shots[0].shot_id, shot_version: adoptedBoard().shots[0].shot_version, shot_digest: adoptedBoard().shots[0].shot_digest });
const decodeCreate = (value: unknown, expected = input()) => checkedStoryboardTimelineCreation(value, project, null, document, expected);
const decodeAdopt = (value: unknown) => checkedStoryboardVideoAdoption(value, project, null, expectedAdoptionPin(), video());

describe('Phase 5 exact reviewed VideoResult and original historical Shot input', () => {
  it('reads actual binding and reapproval without replacing the historical source version', () => {
    const bound = checkedStoryboardReceipt(boundFixture), reviewed = adoptedBoard();
    expect(bound.approved).toBe(false); expect(reviewed.approved).toBe(true);
    expect(reviewed.shots[0].video_result?.source_shot).toEqual(pin());
    expect(reviewed.document_snapshot.version).toBeGreaterThan(pin().document_snapshot.version);
    expect(reviewed.shots[0].shot_version).toBe(pin().shot_version);
    expect(reviewed.shots[0].shot_digest).toBe(pin().shot_digest);
  });
  it.each([
    ['wrong source shot', (v: Record<string, unknown>) => { row(row(row((v.shots as unknown[])[0]).video_result).source_shot).shot_id = 'another'; }],
    ['wrong source shot revision', (v: Record<string, unknown>) => { row(row(row((v.shots as unknown[])[0]).video_result).source_shot).shot_version = 2; }],
    ['future document version', (v: Record<string, unknown>) => { row(row(row(row((v.shots as unknown[])[0]).video_result).source_shot).document_snapshot).version = 999; }],
    ['private candidate version zero', (v: Record<string, unknown>) => { row(row(row((v.shots as unknown[])[0]).video_result).asset).version = 0; }],
    ['wrong output kind', (v: Record<string, unknown>) => { row(row(row((v.shots as unknown[])[0]).video_result).asset).kind = 'image'; }],
    ['unknown job authority', (v: Record<string, unknown>) => { row(row(row((v.shots as unknown[])[0]).video_result).job).approved = true; }],
    ['job identity controls rejected by original owner', (v: Record<string, unknown>) => { row(row(row((v.shots as unknown[])[0]).video_result).job).id = 'job\n'; }],
  ])('rejects malformed %s', (_name, mutate) => { const value = row(copy(boundFixture)); mutate(value); expect(() => checkedStoryboardReceipt(value)).toThrow(); });
  it('accepts actual prepared I2V and rejects source/command divergence before consumption', () => {
    expect(checkedStoryboardVideoRequest(requestedFixture, pin()).command.storyboard_shot).toEqual(pin());
    const changed = copy(requestedFixture); changed.command.storyboard_shot.shot_digest = 'a'.repeat(64);
    expect(() => checkedStoryboardVideoRequest(changed, pin())).toThrow();
  });
  it('checks binding postconditions against requested Asset, Job and original pin', async () => {
    const request = vi.fn().mockResolvedValue(copy(boundFixture));
    const client = createStoryboardClient(project, '/api/synthetic-creative', null, request);
    const before = sourceBoard();
    expect(await client.storyboardBindVideo(before, before.shots[0], video().asset, video().job, pin())).toEqual(checkedStoryboardReceipt(boundFixture));
    expect(request).toHaveBeenCalledWith(`/api/synthetic-creative/documents/${document}/shots/shot-1/video-binding`, 'POST',
      { expected_version: before.document_snapshot.version, shot_version: before.shots[0].shot_version, shot_digest: before.shots[0].shot_digest, asset: video().asset, video_job: video().job });
    const wrong = copy(boundFixture); row(row(row(wrong.shots[0]).video_result).job).receipt_digest = '0'.repeat(64); request.mockResolvedValue(wrong);
    await expect(client.storyboardBindVideo(before, before.shots[0], video().asset, video().job, pin())).rejects.toBeTruthy();
  });
});

describe('Phase 5 persistent Timeline CREATE identity and read-only UNKNOWN recovery', () => {
  it('verifies actual creation hashes and a later current Timeline without rewriting creation v1', async () => {
    const created = await decodeCreate(createdFixture), recovered = await decodeCreate(recoveredFixture);
    expect(created.creation_receipt).toEqual(recovered.creation_receipt);
    expect(created.creation_receipt.creation_snapshot.version).toBe(1);
    expect(recovered.timeline.version).toBe(2); expect(recovered.replayed).toBe(true);
    expect(created.automatic_dispatch).toBe(false); expect(created.rendered).toBe(false);
  });
  it.each([
    ['request id', (v: Record<string, unknown>) => { row(v.creation_receipt).request_id = 'other'; }],
    ['original full request', (v: Record<string, unknown>) => { row(row(v.creation_receipt).request).title = 'different'; }],
    ['request digest', (v: Record<string, unknown>) => { row(v.creation_receipt).request_digest = '0'.repeat(64); }],
    ['origin digest', (v: Record<string, unknown>) => { row(v.creation_receipt).origin_digest = '0'.repeat(64); }],
    ['wrong current project', (v: Record<string, unknown>) => { row(v.timeline).novel_id = 'foreign'; }],
    ['wrong current branch', (v: Record<string, unknown>) => { row(v.timeline).branch_id = 'foreign'; }],
    ['forged successful model call', (v: Record<string, unknown>) => { v.model_called = true; }],
    ['missing nested owner receipt', (v: Record<string, unknown>) => { delete row(v.timeline).creation_receipt; }],
    ['missing origin mirror', (v: Record<string, unknown>) => { delete row(v.timeline).storyboard_origin; }],
  ])('rejects %s rather than clearing an unknown operation', async (_name, mutate) => {
    const value = row(copy(recoveredFixture)); mutate(value); await expect(decodeCreate(value)).rejects.toBeTruthy();
  });
  it('does not turn another full request into a matching creation reply', async () => {
    await expect(decodeCreate(createdFixture, { ...input(), request_id: 'new-attempt' })).rejects.toBeTruthy();
    await expect(decodeCreate(createdFixture, { ...input(), shot_ids: ['shot-2'] })).rejects.toBeTruthy();
  });
  it('issues only a GET for original creation recovery and keeps the retained request', async () => {
    const request = vi.fn().mockResolvedValue(copy(recoveredFixture)), client = createStoryboardClient(project, '/api/synthetic-creative', null, request);
    const signal = new AbortController().signal;
    const recovered = await client.storyboardTimelineCreation(sourceBoard(), input(), signal);
    expect(recovered.timeline.version).toBe(2);
    expect(request).toHaveBeenCalledTimes(1);
    expect(request).toHaveBeenCalledWith(`/api/synthetic-creative/documents/${document}/storyboard/timeline-creations/${input().request_id}`, 'GET', undefined, signal);
  });
});

describe('Phase 5 original clip adoption retains exact edit effect and full request identity', () => {
  it('reads actual adoption and the same original effect in current creation recovery', async () => {
    const adopted = await decodeAdopt(adoptedFixture), recovered = await decodeCreate(recoveredFixture);
    expect(adopted.adoption_receipt).toEqual(adoptedFixture.adoption_receipt);
    expect(adopted.timeline.video_adoption_receipt).toEqual(recovered.timeline.video_adoption_receipt);
    expect(adopted.timeline.timeline.tracks[0].clips[0].source_snapshot.asset_kind).toBe('video');
  });
  it.each([
    ['full document request CAS', (v: Record<string, unknown>) => { row(row(v.adoption_receipt).request).expected_version = 999; }],
    ['full request digest', (v: Record<string, unknown>) => { row(v.adoption_receipt).request_digest = '0'.repeat(64); }],
    ['original edit digest', (v: Record<string, unknown>) => { row(row(v.adoption_receipt).edit_receipt).request_digest = '0'.repeat(64); }],
    ['original edit input revision', (v: Record<string, unknown>) => { row(row(v.adoption_receipt).edit_receipt).input_version = 999; }],
    ['different output Asset', (v: Record<string, unknown>) => { row(row(v.video_result).asset).asset_id = 'another'; }],
    ['missing nested effect receipt', (v: Record<string, unknown>) => { delete row(v.timeline).video_adoption_receipt; }],
    ['changed clip placement effect', (v: Record<string, unknown>) => { row(((row(row(v.timeline).timeline).tracks as Record<string, unknown>[])[0].clips as unknown[])[0]).out_ms = 400; }],
  ])('rejects %s and keeps adoption causality unresolved', async (_name, mutate) => {
    const value = row(copy(adoptedFixture)); mutate(value); await expect(decodeAdopt(value)).rejects.toBeTruthy();
  });
  it('checks complete replacement against original Timeline and bound reviewed result', async () => {
    const request = vi.fn().mockResolvedValue(copy(adoptedFixture));
    const client = createStoryboardClient(project, '/api/synthetic-creative', null, request), board = adoptedBoard();
    const current = await decodeCreate(createdFixture), full = adoptedFixture.adoption_receipt.request;
    const input = { expected_timeline_version: full.expected_timeline_version, reviewed_timeline_digest: full.reviewed_timeline_digest,
      request_id: full.request_id, clip_id: full.clip_id, in_ms: full.in_ms, out_ms: full.out_ms, include_audio: full.include_audio };
    expect((await client.storyboardAdoptVideo(board, board.shots[0], current, input)).timeline.version).toBe(2);
    const wrong = copy(adoptedFixture); wrong.timeline.title = 'unexpected replacement'; request.mockResolvedValue(wrong);
    await expect(client.storyboardAdoptVideo(board, board.shots[0], current, input)).rejects.toBeTruthy();
  });
});
