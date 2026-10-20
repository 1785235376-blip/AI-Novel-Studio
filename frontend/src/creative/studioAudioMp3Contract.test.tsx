// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { webcrypto } from 'node:crypto';
import { useLocalHostSession } from '../localHostSession';
import { AUDIO_MP3_PROFILE, studioProductionClient, type MediaCommand } from './studioProductionClient';
import { StudioMediaExecutionPanel } from './StudioMediaExecutionPanel';
import type { StudioAsset } from './studioClient';
import { audioPreview } from './studioAudioWav.testFixtures';

let fetcher: ReturnType<typeof vi.fn>;
const project = 'mp3-project';
const response = (value: unknown) => ({ ok: true, status: 200, json: async () => value });
const client = () => studioProductionClient(project, { sessionToken: '' });
beforeEach(() => { vi.stubGlobal('crypto', webcrypto); useLocalHostSession.setState({ token: 'synthetic-mp3-unit', actorId: '' }); fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it('sends selected MP3 explicitly, preserves unsupported rate input, and never automatically creates or executes', async () => {
  const asset = { id: 'source-a', version: 1, sha256: 'b'.repeat(64), kind: 'audio', novel_id: project, filename: 'owned-tone.wav', branch_id: null, media_type: 'audio/wav', size: 100, created_at: '', updated_at: '' } as StudioAsset;
  fetcher.mockImplementation(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/providers')) return response({ items: [], health_probed: false, credentials_read: false });
    if (url.endsWith('/jobs')) return response({ items: [] });
    if (url.endsWith('/preview')) {
      const input = JSON.parse(init!.body as string) as MediaCommand, preview = audioPreview(input);
      if (input.parameters.output_format === 'MP3') {
        preview.execution_recipe.output_profile = 'MP3_LIBMP3LAME_22050_MONO_CBR64';
        preview.execution_recipe.audio_profile = input.audio_profile;
      }
      return response({ ...preview, novel_id: project });
    }
    throw new Error('Unexpected controlled UI request');
  });
  render(<StudioMediaExecutionPanel client={client()} assets={[asset]} canMutate canReview busy={false} isCurrent={() => true} read={async work => work()} mutate={async work => work()} onDirtyChange={vi.fn()} onUnavailable={vi.fn()} />);
  await waitFor(() => expect((screen.getByLabelText('操作') as HTMLSelectElement).disabled).toBe(false));
  fireEvent.change(screen.getByLabelText('操作'), { target: { value: 'm8.audio.trim' } });
  fireEvent.click(screen.getByLabelText('owned-tone.wav · v1'));
  for (const [label, value] of [['来源起点（毫秒）', '100'], ['来源终点（毫秒）', '800'], ['输出采样率（8000–96000 Hz，可选）', '96000'], ['输出声道（可选）', '1'], ['独立音频交付格式（可选）', 'MP3']]) fireEvent.change(screen.getByLabelText(label), { target: { value } });
  expect((screen.getByLabelText('独立音频交付格式（可选）') as HTMLSelectElement).value).toBe('MP3');
  expect(screen.getByText(/MP3 采样率仅支持/)).toBeTruthy();
  expect((screen.getByLabelText('输出采样率（8000–96000 Hz，可选）') as HTMLInputElement).value).toBe('96000');
  expect((screen.getByRole('button', { name: '读取制作预览' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText('输出采样率（8000–96000 Hz，可选）'), { target: { value: '22050' } });
  fireEvent.click(screen.getByRole('button', { name: '读取制作预览' })); await screen.findByRole('region', { name: '制作预览确认' });
  const posts = () => fetcher.mock.calls.filter(([url]) => url.endsWith('/preview'));
  expect(JSON.parse(posts()[0][1].body as string).audio_profile).toBe(AUDIO_MP3_PROFILE);
  expect(JSON.parse(posts()[0][1].body as string).parameters).toEqual({ in_ms: 100, out_ms: 800, sample_rate: 22050, channels: 1, output_format: 'MP3' });
  fireEvent.change(screen.getByLabelText('独立音频交付格式（可选）'), { target: { value: '' } });
  expect(screen.queryByRole('region', { name: '制作预览确认' })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '读取制作预览' })); await screen.findByRole('region', { name: '制作预览确认' });
  expect(Object.hasOwn(JSON.parse(posts()[1][1].body as string).parameters, 'output_format')).toBe(false);
  expect(Object.hasOwn(JSON.parse(posts()[1][1].body as string), 'audio_profile')).toBe(false);
  expect(fetcher.mock.calls.filter(([url, init]) => url.endsWith('/jobs') && init?.method === 'POST')).toHaveLength(0);
  expect(fetcher.mock.calls.filter(([url]) => url.endsWith('/execute') || url.endsWith('/review'))).toHaveLength(0);
});

// Original File-owner service DTOs from a real synthetic CPU encode/probe/decode.
import capture from './fixtures/audio-mp3-versioned.capture.json';
import historical from './fixtures/audio-mp3.capture.json';
const capturedClient = () => studioProductionClient(capture.executed.novel_id, { sessionToken: '' });
it('accepts original real MP3 preview, queued, measured and approved receipts', async () => {
  const api = capturedClient();
  fetcher.mockResolvedValue(response(capture.preview)); expect(await api.preview(capture.command as MediaCommand)).toEqual(capture.preview);
  fetcher.mockResolvedValue(response(capture.queued)); expect(await api.create(capture.command as MediaCommand, capture.preview.preview_digest)).toEqual(capture.queued);
  for (const row of [capture.queued, capture.executed, capture.approved]) {
    fetcher.mockResolvedValue(response(row)); expect(await api.get('audio', row.id)).toEqual(row);
  }
  expect(capture.executed.media_measurement).toMatchObject({ audio_codec: 'mp3', container: 'mp3', sample_rate: 22050, channels: 1, bit_rate: 64000, duration_ms: 700, total_samples: 15435, decoded_pcm_bytes: 30870 });
});
it.each([
  ['missing samples', (v: Record<string, unknown>) => { delete v.total_samples; }],
  ['wrong rate', (v: Record<string, unknown>) => { v.sample_rate = 48000; }],
  ['wrong channels', (v: Record<string, unknown>) => { v.channels = 2; }],
  ['wrong bitrate', (v: Record<string, unknown>) => { v.bit_rate = 128000; }],
  ['missing bitrate', (v: Record<string, unknown>) => { delete v.bit_rate; }],
  ['padding outside frame budget', (v: Record<string, unknown>) => { v.container_duration_ms = 5000; }],
  ['short container', (v: Record<string, unknown>) => { v.container_duration_ms = 600; }],
  ['wrong decoded size', (v: Record<string, unknown>) => { v.decoded_pcm_bytes = 30868; }],
  ['invalid decoded digest', (v: Record<string, unknown>) => { v.decoded_pcm_sha256 = 'bad'; }],
  ['lossless claim', (v: Record<string, unknown>) => { v.profile_validation = 'FLAC_STREAMINFO_PCM_VERIFIED'; }],
  ['unknown checksum', (v: Record<string, unknown>) => { v.streaminfo_md5 = 'a'.repeat(32); }],
  ['different output', (v: Record<string, unknown>) => { v.output_sha256 = 'a'.repeat(64); }],
])('rejects MP3 %s', async (_name, mutate) => {
  const row = structuredClone(capture.executed); mutate(row.media_measurement); fetcher.mockResolvedValue(response(row));
  await expect(capturedClient().get('audio', row.id)).rejects.toBeTruthy();
});
it.each([8001, 44101, 64000, 96000])('rejects unsupported MP3 rate %s before network', async sample_rate => {
  const command = structuredClone(capture.command); command.parameters.sample_rate = sample_rate;
  await expect(capturedClient().preview(command as MediaCommand)).rejects.toBeTruthy(); expect(fetcher).not.toHaveBeenCalled();
});
it.each([1, 5, 9])('rejects MP3 interval %s ms before network instead of rounding output', async milliseconds => {
  const command = structuredClone(capture.command); command.parameters.out_ms = command.parameters.in_ms + milliseconds;
  await expect(capturedClient().preview(command as MediaCommand)).rejects.toBeTruthy(); expect(fetcher).not.toHaveBeenCalled();
});

import { Blob as NodeBlob } from 'node:buffer';
it.each(['audio/mpeg', 'audio/wav'])('shows measured lossy receipt and checks candidate MIME %s before explicit review', async mime => {
  const api = capturedClient(); fetcher.mockResolvedValueOnce(response(capture.executed));
  const job = await api.get('audio', capture.executed.id);
  const source = capture.command.source_snapshots[0], asset = { id: source.id, version: source.version, sha256: source.digest, kind: 'audio', novel_id: capture.executed.novel_id, filename: 'owned-tone.wav', branch_id: null, media_type: 'audio/wav', size: 96044, created_at: '', updated_at: '' } as StudioAsset;
  const media = new NodeBlob([Buffer.from(capture.candidate_base64, 'base64')], { type: mime });
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:synthetic-mp3') });
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() });
  fetcher.mockImplementation(async (url: string) => {
    if (url.endsWith('/providers')) return response({ items: [], health_probed: false, credentials_read: false });
    if (url.endsWith('/candidate')) return { ...response({}), blob: async () => media };
    throw new Error('Unexpected controlled candidate request');
  });
  render(<StudioMediaExecutionPanel client={api} externalJob={job} assets={[asset]} canMutate canReview busy={false} isCurrent={() => true} read={async work => work()} mutate={async work => work()} onDirtyChange={vi.fn()} onUnavailable={vi.fn()} />);
  await screen.findByRole('region', { name: '音频实际输出测量' });
  expect(screen.getByText(/MP3 为有损格式/)).toBeTruthy(); expect(screen.getByText(/MP3 · 64 kb\/s/)).toBeTruthy();
  const review = () => screen.getByRole('button', { name: '明确审核并入素材库' }) as HTMLButtonElement;
  expect(review().disabled).toBe(true);
  await waitFor(() => expect((screen.getByRole('button', { name: '读取并核对候选媒体' }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole('button', { name: '读取并核对候选媒体' }));
  if (mime === 'audio/mpeg') {
    await screen.findByLabelText('本任务的音频候选'); expect(review().disabled).toBe(true);
    fireEvent.click(screen.getByLabelText('已查看本次候选，确认采用当前任务版本与输出摘要'));
    expect(review().disabled).toBe(false);
  } else {
    await screen.findByText('本地 MP3 候选与实际输出测量不一致，不可审核。');
    expect(screen.queryByLabelText('本任务的音频候选')).toBeNull(); expect(review().disabled).toBe(true);
  }
  expect(fetcher.mock.calls.some(([url]) => url.endsWith('/execute') || url.endsWith('/review'))).toBe(false);
});


it('keeps real historical unmarked receipts readable but rejects resubmission before transport', async () => {
  const api = studioProductionClient(historical.executed.novel_id, { sessionToken: '' });
  for (const row of [historical.queued, historical.executed, historical.approved]) {
    fetcher.mockResolvedValue(response(row));
    expect(await api.get('audio', row.id)).toEqual(row);
    fetcher.mockResolvedValue(response({ items: [row] }));
    expect(await api.list()).toEqual([row]);
  }
  fetcher.mockClear();
  await expect(api.preview(historical.command as MediaCommand)).rejects.toBeTruthy();
  await expect(api.create(historical.command as MediaCommand, historical.preview.preview_digest)).rejects.toBeTruthy();
  expect(fetcher).not.toHaveBeenCalled();
});

it.each([undefined, null, '', false, 'studio-audio-mp3/2'])('rejects invalid new MP3 marker %s before transport', async marker => {
  const command = structuredClone(capture.command) as Record<string, unknown>;
  if (marker === undefined) delete command.audio_profile; else command.audio_profile = marker;
  await expect(capturedClient().preview(command as unknown as MediaCommand)).rejects.toBeTruthy();
  await expect(capturedClient().create(command as unknown as MediaCommand, capture.preview.preview_digest)).rejects.toBeTruthy();
  expect(fetcher).not.toHaveBeenCalled();
});

it.each(['command', 'execution_recipe'])('rejects missing or mismatched preview marker in %s', async field => {
  const preview = structuredClone(capture.preview);
  delete (preview[field as 'command' | 'execution_recipe'] as Record<string, unknown>).audio_profile;
  fetcher.mockResolvedValue(response(preview));
  await expect(capturedClient().preview(capture.command as MediaCommand)).rejects.toBeTruthy();
});

it('keeps historical explicit action payload limited to original job/version/digest', async () => {
  const api = studioProductionClient(historical.executed.novel_id, { sessionToken: '' });
  fetcher.mockResolvedValue(response(historical.executed));
  expect(await api.execute(historical.queued as never)).toEqual(historical.executed);
  const [url, init] = fetcher.mock.calls[0];
  expect(url).toContain('/jobs/audio/' + historical.queued.id + '/execute');
  expect(JSON.parse(init.body)).toEqual({ expected_version: historical.queued.version, expected_request_digest: historical.queued.request_digest });
  expect(fetcher).toHaveBeenCalledTimes(1);
});
