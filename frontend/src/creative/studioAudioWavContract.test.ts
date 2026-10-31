// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import mountedFixture from './fixtures/audioWav.mounted.json';
import { useLocalHostSession } from '../localHostSession';
import { studioProductionClient, type MediaCommand } from './studioProductionClient';
import { graphMediaParameterNames } from './useStudioGraphEditorController';
import { createStudioGraphClient } from './studioGraphClient';
import { audioCommand, audioJob, audioPreview, audioProject } from './studioAudioWav.testFixtures';
let fetcher: ReturnType<typeof vi.fn>;
beforeEach(() => { useLocalHostSession.setState({ token: 'fixture-host', actorId: '' }); fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher); });
afterEach(() => vi.unstubAllGlobals());
const respond = (value: unknown) => fetcher.mockResolvedValue({ ok: true, status: 200, json: async () => value });
const client = () => studioProductionClient(audioProject, { sessionToken: '' });
describe('standalone WAV controls on original production DTO', () => {
  it('decodes the actual mounted API native FFmpeg preview, queue, measured output and approval unchanged', async () => {
    const api = studioProductionClient(mountedFixture.source.novel_id, { sessionToken: '' });
    respond(mountedFixture.preview); expect(await api.preview(mountedFixture.command as MediaCommand)).toEqual(mountedFixture.preview);
    respond(mountedFixture.queued); expect(await api.create(mountedFixture.command as MediaCommand, mountedFixture.preview.preview_digest)).toEqual(mountedFixture.queued);
    for (const row of [mountedFixture.queued, mountedFixture.executed, mountedFixture.approved]) {
      respond(row); expect(await api.get('audio', row.id)).toEqual(row);
    }
    expect(mountedFixture.executed.media_measurement).toMatchObject({ duration_ms: 700, sample_rate: 22050, channels: 1, profile_validation: 'PCM_DECODED' });
  });
  it('preserves byte-exact legacy request serialization with optional controls absent', async () => {
    const command = audioCommand(), preview = audioPreview(command); respond(preview);
    expect(await client().preview(command)).toEqual(preview);
    expect(fetcher.mock.calls[0][1].body).toBe(JSON.stringify(command));
    expect(Object.keys(JSON.parse(fetcher.mock.calls[0][1].body).parameters)).toEqual(['in_ms', 'out_ms']);
    const queued = audioJob(); respond(queued); await client().create(command, preview.preview_digest);
    expect(fetcher.mock.calls[1][1].body).toBe(JSON.stringify({ command, reviewed_preview_digest: preview.preview_digest }));
  });
  it.each([{ gain_db: -60 }, { gain_db: 12 }, { gain_db: -3.125 }, { gain_db: 0 }, { sample_rate: 8000 }, { sample_rate: 96000 }, { channels: 1 }, { channels: 2 }, { gain_db: -6, sample_rate: 22050, channels: 1 }])('accepts bounded explicit controls %j', async controls => {
    const command = audioCommand('audio-request', controls as Record<string, number>); respond(audioPreview(command)); expect(await client().preview(command)).toEqual(audioPreview(command));
    for (const row of [audioJob('QUEUED', 1, command), audioJob('AWAITING_REVIEW', 3, command), audioJob('APPROVED', 5, command)]) {
      respond(row); expect(await client().get('audio', row.id)).toEqual(row);
    }
  });
  it('accepts original known null preview defaults without adding them to the request', async () => {
    const command = audioCommand(), preview = audioPreview(command);
    const projected = { ...preview, command: { ...command, parameters: { ...command.parameters, width: null, height: null, steps: null, speech_rate: null },
      source_snapshots: command.source_snapshots.map(row => ({ ...row, reference_only: true })) } };
    respond(projected); expect(await client().preview(command)).toEqual(projected);
  });
  it.each([null, undefined])('keeps old stored trim receipts readable without measurement: %s', async media_measurement => {
    const row = { ...audioJob('AWAITING_REVIEW', 3), media_measurement }; respond(row); expect(await client().get('audio', row.id)).toEqual(row);
  });
  it.each(['RUNNING', 'UNKNOWN'] as const)('allows verified output reservation without a published candidate in %s', async status => {
    const row = { ...audioJob('AWAITING_REVIEW', 3, audioCommand('audio-request', { gain_db: -6 })), status, output_candidate: null };
    respond(row); expect(await client().get('audio', row.id)).toEqual(row);
  });
  it.each(['QUEUED', 'AWAITING_REVIEW', 'SUCCEEDED', 'REVIEWING', 'APPROVED'] as const)('rejects a measured %s response missing its finalized candidate', async status => {
    const row = { ...audioJob('AWAITING_REVIEW', 3, audioCommand('audio-request', { gain_db: -6 })), status, output_candidate: null };
    respond(row); await expect(client().get('audio', row.id)).rejects.toThrow();
  });
  it.each([null, undefined])('requires measured proof for a successful explicitly controlled output: %s', async media_measurement => {
    const row = { ...audioJob('AWAITING_REVIEW', 3, audioCommand('audio-request', { gain_db: 0 })), media_measurement };
    respond(row); await expect(client().get('audio', row.id)).rejects.toThrow();
  });
  it.each([
    { gain_db: -60.1 }, { gain_db: 12.1 }, { gain_db: NaN }, { gain_db: Infinity }, { gain_db: '3' }, { gain_db: true },
    { sample_rate: 7999 }, { sample_rate: 96001 }, { sample_rate: 48000.5 }, { sample_rate: '48000' }, { channels: 0 }, { channels: 3 }, { channels: 1.5 }, { channels: true },
    { speed: 2 }, { normalize: true }, { codec: 'mp3' }, { gain_db: null }, { in_ms: -1 }, { out_ms: 100 },
  ])('rejects invalid controls without network %j', async controls => {
    const command = { ...audioCommand(), parameters: { ...audioCommand().parameters, ...controls } } as unknown as MediaCommand;
    await expect(client().preview(command)).rejects.toMatchObject({ problem: { code: 'STUDIO_RESPONSE_INVALID' } }); expect(fetcher).not.toHaveBeenCalled();
  });
  it.each(['m8.audio.speech', 'm8.audio.music', 'm8.audio.effects', 'm5.image.t2i', 'm7.video.t2v'] as const)('does not expand %s parameter admission', async operation_id => {
    await expect(client().preview({ ...audioCommand(), operation_id, parameters: { gain_db: 0 } })).rejects.toThrow(); expect(fetcher).not.toHaveBeenCalled();
  });
  it.each([
    { duration_ms: 497 }, { duration_ms: 503 }, { duration_ms: 0 }, { duration_ms: 500.5 }, { byte_count: 0 }, { byte_count: 25 * 1024 * 1024 + 1 },
    { sample_rate: 48000 }, { channels: 2 }, { sample_width: 3 }, { audio_codec: 'aac' }, { container: 'mp3' }, { profile_validation: 'REQUESTED' },
    { output_sha256: 'b'.repeat(64) }, { raw_path: '/private' }, { gain_db: -6 },
  ])('rejects altered or unverified measured WAV receipt %j', async patch => {
    const row = audioJob('AWAITING_REVIEW', 3, audioCommand('audio-request', { gain_db: -6, sample_rate: 22050, channels: 1 }));
    respond({ ...row, media_measurement: { ...row.media_measurement, ...patch } }); await expect(client().get('audio', row.id)).rejects.toThrow();
  });
  it.each(['duration_ms', 'byte_count', 'sample_rate', 'channels', 'sample_width', 'container', 'audio_codec', 'profile_validation', 'output_sha256'])('requires measured field %s', async key => {
    const row = audioJob('AWAITING_REVIEW', 3), measurement = { ...row.media_measurement } as Record<string, unknown>; delete measurement[key];
    respond({ ...row, media_measurement: measurement }); await expect(client().get('audio', row.id)).rejects.toThrow();
  });
  it.each(['parameters', 'output_profile', 'adapter', 'unknown'])('rejects changed preview recipe %s', async key => {
    const value = audioPreview(audioCommand('audio-request', { gain_db: -6, sample_rate: 22050, channels: 1 }));
    value.execution_recipe[key] = key === 'parameters' ? { in_ms: 100, out_ms: 600, gain_db: 0, sample_rate: 22050, channels: 1 } : 'substitution';
    respond(value); await expect(client().preview(value.command)).rejects.toThrow();
  });
  it('rejects a preview inventing an explicit optional parameter for a legacy request', async () => {
    respond(audioPreview(audioCommand('audio-request', { gain_db: 0 }))); await expect(client().preview(audioCommand())).rejects.toThrow();
  });
  it.each(['gain', 'recipe', 'source', 'version'])('rejects action substitution of original %s binding', async kind => {
    const expected = audioJob(), result = audioJob('AWAITING_REVIEW', 3);
    if (kind === 'gain') { result.command!.parameters.gain_db = 0; (result.execution_recipe.parameters as Record<string, number>).gain_db = 0; }
    if (kind === 'recipe') result.execution_recipe.recipe_digest = 'a'.repeat(64);
    if (kind === 'source') { result.sources[0].id = 'other'; result.command!.source_snapshots[0].id = 'other'; }
    if (kind === 'version') { expected.version = 4; result.version = 3; }
    respond(result); await expect(client().execute(expected)).rejects.toThrow();
  });
  it('rejects a queued command changing controls despite echoed request identifiers', async () => {
    respond(audioJob('QUEUED', 1, audioCommand('audio-request', { gain_db: 0 }))); await expect(client().create(audioCommand(), 'e'.repeat(64))).rejects.toThrow();
  });
  it.each(['gain_db', 'sample_rate', 'channels'])('keeps Graph trim closed to %s', key => {
    expect(graphMediaParameterNames('m8.audio.trim')).toEqual(['in_ms', 'out_ms']);
    const json = vi.fn(), graph = createStudioGraphClient(audioProject, {}, { json });
    expect(() => graph.create({ request_id: 'graph_request', expected_version: 0, definition: { title: 'Original Graph trim boundary', schema_version: 3,
      nodes: [{ id: 'generate', definition_id: 'media_generate', definition_version: 1, enabled: true, position: { x: 0, y: 0 },
        parameters: { operation_id: 'm8.audio.trim', parameters: { in_ms: 100, out_ms: 600, [key]: key === 'sample_rate' ? 22050 : 1 } } }],
      edges: [], viewport: { x: 0, y: 0, zoom: 1 } } } as never)).toThrow();
    expect(json).not.toHaveBeenCalled();
  });
  it('keeps WAV measurement unavailable to a timeline or generated audio receipt', async () => {
    for (const operation_id of ['m8.audio.speech', 'm9.timeline.multitrack']) {
      const row = audioJob('AWAITING_REVIEW', 3); respond({ ...row, operation_id }); await expect(client().get('audio', row.id)).rejects.toThrow();
    }
  });
});
