import capturedApi from './fixtures/storyboard-speech.file-api.json';
import capturedApiV1 from './fixtures/storyboard-speech.file-api-v1.json';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { checkedStoryboardAudioRequest, checkedStoryboardSpeechCommand, checkedStoryboardSpeechFields, checkedStoryboardSpeechPin, sameStoryboardSpeech } from './studioStoryboardSpeechContract';
import { createStoryboardClient } from './studioStoryboardClient';
import { studioProductionClient } from './studioProductionClient';
import { speechBoard, speechJob, speechPin, speechPreview, speechRequest } from './storyboardSpeech.testFixtures';
const transport = vi.hoisted(() => ({ json: vi.fn(), blob: vi.fn() }));
vi.mock('./studioClient', async original => ({ ...await original<typeof import('./studioClient')>(), studioTransport: () => transport }));
const record = (value: unknown) => value as Record<string, unknown>;
beforeEach(() => { transport.json.mockReset(); transport.blob.mockReset(); });
describe('Storyboard speech contract stays closed and version-bound', () => {
  it('normalizes nullable legacy fields while retaining only the speech provenance', () => {
    const value = speechRequest(); record(value.command.parameters).width = null; record(value.command.source_snapshots[0]).asset_kind = null;
    const next = checkedStoryboardAudioRequest(value, speechPin()); expect(next.command.parameters).toEqual({ voice_id: 'narrator', speech_rate: 1.2 });
    expect(next.command.storyboard_speech).toEqual(speechPin()); expect(next.command).not.toHaveProperty('storyboard_shot'); expect(next.model_called).toBe(false);
  });
  it.each([
    ['automatic dispatch', (r: Record<string, unknown>) => { r.automatic_dispatch = true; }],
    ['claimed acceptance', (r: Record<string, unknown>) => { r.product_acceptance = 'PASS'; }],
    ['model called', (r: Record<string, unknown>) => { r.model_called = true; }],
    ['pin mismatch', (r: Record<string, unknown>) => { record(r.shot_pin).dialogue_index = 0; }],
    ['cloud', (r: Record<string, unknown>) => { record(r.command).allow_cloud = true; }],
    ['video operation', (r: Record<string, unknown>) => { record(r.command).operation_id = 'm7.video.t2v'; }],
    ['video provenance', (r: Record<string, unknown>) => { record(r.command).storyboard_shot = speechPin(); }],
    ['source role', (r: Record<string, unknown>) => { record((record(r.command).source_snapshots as unknown[])[0]).reference_only = false; }],
    ['source version', (r: Record<string, unknown>) => { record((record(r.command).source_snapshots as unknown[])[0]).version = 99; }],
    ['missing voice', (r: Record<string, unknown>) => { delete record(record(r.command).parameters).voice_id; }],
    ['invalid rate', (r: Record<string, unknown>) => { record(record(r.command).parameters).speech_rate = '1.2'; }],
    ['unrelated parameter', (r: Record<string, unknown>) => { record(record(r.command).parameters).duration_seconds = 2; }],
  ])('rejects %s', (_name, mutate) => { const value = record(speechRequest()); mutate(value); expect(() => checkedStoryboardAudioRequest(value, speechPin())).toThrow(); });
  it.each([-1, 200, true, '1', null, 1.5])('rejects non-exact dialogue index %s', dialogue_index => expect(() => checkedStoryboardSpeechPin({ ...speechPin(), dialogue_index })).toThrow());
  it('leaves ordinary speech commands unchanged and refuses an injected or missing pin', () => {
    const legacy = structuredClone(speechRequest().command); delete legacy.storyboard_speech;
    expect(() => checkedStoryboardSpeechFields(legacy)).not.toThrow(); expect(sameStoryboardSpeech(legacy, legacy)).toBe(true);
    expect(sameStoryboardSpeech(legacy, speechRequest().command)).toBe(false); expect(sameStoryboardSpeech(speechRequest().command, legacy)).toBe(false);
    expect(() => checkedStoryboardSpeechCommand({ ...speechRequest().command, storyboard_speech: null })).toThrow();
  });
});
describe('Original Creative audio preparation remains explicit and read-only', () => {
  it('posts exact document, shot and dialogue pins with explicit choices', async () => {
    const request = vi.fn().mockResolvedValue(speechRequest()), board = speechBoard(), client = createStoryboardClient('project', '/creative', null, request);
    await client.storyboardAudioRequest(board, board.shots[0], 1, 'local-speech', 'speech-fixture', 'speech-request', 'narrator', 1.2);
    expect(request).toHaveBeenCalledTimes(1); expect(request).toHaveBeenCalledWith(`/creative/documents/${board.document_snapshot.id}/shots/${board.shots[0].shot_id}/audio-request`, 'POST', {
      expected_version: board.document_snapshot.version, document_digest: board.document_snapshot.digest, shot_version: board.shots[0].shot_version, shot_digest: board.shots[0].shot_digest,
      dialogue_index: 1, request_id: 'speech-request', provider: { operation_id: 'm8.audio.speech', provider_id: 'local-speech', model_id: 'speech-fixture' }, voice_id: 'narrator', speech_rate: 1.2,
    });
  });
  it('blocks unapproved, missing dialogue and invalid explicit choices before transport', () => {
    const request = vi.fn(), client = createStoryboardClient('project', '/creative', null, request), board = speechBoard();
    for (const [receipt, index, voice, rate] of [[{ ...board, approved: false }, 1, 'voice', 1], [board, 199, 'voice', 1], [board, 1, '', 1], [board, 1, 'voice', 0.4]] as const)
      expect(() => client.storyboardAudioRequest(receipt, board.shots[0], index, 'local-speech', 'speech-fixture', 'speech-request', voice, rate)).toThrow();
    expect(request).not.toHaveBeenCalled();
  });
  it.each(['prompt', 'voice', 'rate', 'provider', 'request'])('rejects changed %s after preparation', async field => {
    const value = speechRequest(); if (field === 'prompt') value.command.prompt = 'changed'; if (field === 'voice') value.command.parameters.voice_id = 'other'; if (field === 'rate') value.command.parameters.speech_rate = 0.5; if (field === 'provider') value.command.provider_id = 'other'; if (field === 'request') value.command.request_id = 'other';
    const request = vi.fn().mockResolvedValue(value), board = speechBoard(); await expect(createStoryboardClient('project', '/creative', null, request).storyboardAudioRequest(board, board.shots[0], 1, 'local-speech', 'speech-fixture', 'speech-request', 'narrator', 1.2)).rejects.toBeTruthy();
  });
});
describe('Original media receipts preserve speech provenance through review', () => {
  it('accepts preview, creation and review with the exact speech input', async () => {
    const preview = speechPreview(), job = speechJob(), client = studioProductionClient(job.novel_id, { sessionToken: 'inert-fixture' });
    transport.json.mockResolvedValueOnce(preview); expect((await client.preview(speechRequest().command)).command.storyboard_speech).toEqual(speechPin());
    transport.json.mockResolvedValueOnce(job); expect((await client.create(speechRequest().command, preview.preview_digest)).owner).toBe('audio');
    transport.json.mockResolvedValueOnce(job); expect((await client.review(job)).approved_asset_version).toBe(job.approved_asset_version);
  });
  it.each(['pin', 'prompt', 'voice', 'rate', 'missing'])('rejects a changed %s during original review', async field => {
    const job = speechJob(), changed = structuredClone(job); if (field === 'pin') changed.command!.storyboard_speech!.dialogue_index = 0; if (field === 'prompt') changed.command!.prompt = 'other'; if (field === 'voice') changed.command!.parameters.voice_id = 'other'; if (field === 'rate') changed.command!.parameters.speech_rate = 1; if (field === 'missing') delete changed.command!.storyboard_speech;
    transport.json.mockResolvedValue(changed); await expect(studioProductionClient(job.novel_id, { sessionToken: 'inert-fixture' }).review(job)).rejects.toBeTruthy();
  });
});

// Captured by the synthetic mounted backend test; no real inference or paid route was used.
describe.each([['api', capturedApi], ['api-v1', capturedApiV1]] as const)('Mounted %s speech wire interoperability', (_route, fixture) => {
  it('decodes exact preparation, queued, private-ready and reviewed original Audio receipts', async () => {
    const prepared = checkedStoryboardAudioRequest(fixture.prepared, checkedStoryboardSpeechPin(fixture.prepared.shot_pin));
    expect(prepared.command.storyboard_speech).toEqual(fixture.prepared.shot_pin);
    const client = studioProductionClient(fixture.approved.novel_id, { sessionToken: 'inert-capture-decoder' });
    for (const wire of [fixture.queued, fixture.ready, fixture.approved]) {
      transport.json.mockResolvedValueOnce(wire); const job = await client.get('audio', wire.id);
      expect(sameStoryboardSpeech(prepared.command, job.command)).toBe(true); expect(job.status).toBe(wire.status); expect(job.needs_reconciliation).toBeNull(); expect(job.execution_state).toBeNull();
    }
    expect(fixture.approved.approved_asset_version).toBeGreaterThan(0);
  });
});
