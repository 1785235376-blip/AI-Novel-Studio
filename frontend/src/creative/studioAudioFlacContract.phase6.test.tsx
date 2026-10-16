// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { webcrypto } from 'node:crypto';
import { useLocalHostSession } from '../localHostSession';
import { studioProductionClient, type MediaCommand } from './studioProductionClient';
import { StudioMediaExecutionPanel } from './StudioMediaExecutionPanel';
import type { StudioAsset } from './studioClient';
import capture from './fixtures/phase6.capture.editing-pipeline.json';
import { audioPreview } from './studioAudioWav.testFixtures';
const copy = <T,>(value: T): T => structuredClone(value);
let fetcher: ReturnType<typeof vi.fn>;
const project = capture.audio_receipts.approved.novel_id;
const command = () => copy(capture.audio_receipts.command) as MediaCommand;
const response = (value: unknown) => ({ ok: true, status: 200, json: async () => value });
const client = () => studioProductionClient(project, { sessionToken: '' });
beforeEach(() => { vi.stubGlobal('crypto', webcrypto); useLocalHostSession.setState({ token: 'synthetic-flac-contract-unit', actorId: '' }); fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('Phase 6 actual standalone FLAC receipts retain original media ownership', () => {
  it('reads exact mounted native preview, queue, measured candidate and explicit approval', async () => {
    const api = client(); fetcher.mockResolvedValue(response(capture.audio_receipts.preview)); expect(await api.preview(command())).toEqual(capture.audio_receipts.preview);
    fetcher.mockResolvedValue(response(capture.audio_receipts.queued)); expect(await api.create(command(), capture.audio_receipts.preview.preview_digest)).toEqual(capture.audio_receipts.queued);
    for (const raw of [capture.audio_receipts.queued, capture.audio_receipts.executed, capture.audio_receipts.approved]) { fetcher.mockResolvedValue(response(raw)); expect(await api.get('audio', raw.id)).toEqual(raw); }
    expect(capture.audio_receipts.executed.media_measurement).toMatchObject({ total_samples: 17640, decoded_pcm_bytes: 35280, container: 'flac', profile_validation: 'FLAC_STREAMINFO_PCM_VERIFIED' });
  });
  it.each([
    ['missing sample proof', (v: Record<string, unknown>) => { delete v.total_samples; }],
    ['decoded byte count', (v: Record<string, unknown>) => { v.decoded_pcm_bytes = 1; }],
    ['unmeasured MD5', (v: Record<string, unknown>) => { v.streaminfo_md5 = '0'.repeat(32); }],
    ['invalid PCM SHA', (v: Record<string, unknown>) => { v.decoded_pcm_sha256 = 'bad'; }],
    ['wrong container', (v: Record<string, unknown>) => { v.container = 'wav'; }],
    ['wrong codec', (v: Record<string, unknown>) => { v.audio_codec = 'mp3'; }],
    ['WAV proof substituted', (v: Record<string, unknown>) => { v.profile_validation = 'PCM_DECODED'; }],
    ['wrong measured samples', (v: Record<string, unknown>) => { v.total_samples = 17600; v.decoded_pcm_bytes = 35200; v.duration_ms = 798; }],
  ])('rejects %s before exposing a reviewed receipt', async (_name, mutate) => {
    const raw = copy(capture.audio_receipts.approved); mutate(raw.media_measurement as Record<string, unknown>); fetcher.mockResolvedValue(response(raw)); await expect(client().get('audio', raw.id)).rejects.toBeTruthy();
  });
  it.each(['WAV', 'mp3', 'flac', false, null])('rejects non-opt-in format %s without network', async format => {
    const input = command(); input.parameters.output_format = format as string; await expect(client().preview(input)).rejects.toBeTruthy(); expect(fetcher).not.toHaveBeenCalled();
  });
  it.each(['m8.audio.speech', 'm8.audio.music', 'm7.video.t2v'] as const)('does not admit FLAC controls for %s', async operation_id => {
    await expect(client().preview({ ...command(), operation_id })).rejects.toBeTruthy(); expect(fetcher).not.toHaveBeenCalled();
  });
});

describe('Phase 6 replaceable Audio Inspector retains default WAV serialization', () => {
  it('selects FLAC explicitly and clears only that control when returning to the old default', async () => {
    const source = command().source_snapshots[0], asset = { id: source.id, version: source.version, sha256: source.digest, kind: 'audio', novel_id: project, filename: 'synthetic-source.wav', branch_id: null, media_type: 'audio/wav', size: 100, created_at: '', updated_at: '' } as StudioAsset;
    fetcher.mockImplementation(async (url: string, init?: RequestInit) => {
      if (url.endsWith('/providers')) return response({ items: [], health_probed: false, credentials_read: false });
      if (url.endsWith('/jobs')) return response({ items: [] });
      if (url.endsWith('/preview')) { const input = JSON.parse(init!.body as string) as MediaCommand; return response(input.parameters.output_format === 'FLAC' ? { ...copy(capture.audio_receipts.preview), request_id: input.request_id, command: { ...copy(capture.audio_receipts.preview.command), request_id: input.request_id } } : { ...audioPreview(input), novel_id: project }); }
      throw new Error('Unexpected controlled UI request');
    });
    render(<StudioMediaExecutionPanel client={client()} assets={[asset]} canMutate canReview busy={false} isCurrent={() => true} read={async work => work()} mutate={async work => work()} onDirtyChange={vi.fn()} onUnavailable={vi.fn()} />);
    await waitFor(() => expect((screen.getByLabelText('操作') as HTMLSelectElement).disabled).toBe(false)); fireEvent.change(screen.getByLabelText('操作'), { target: { value: 'm8.audio.trim' } });
    expect((screen.getByLabelText('独立音频交付格式（可选）') as HTMLSelectElement).value).toBe(''); fireEvent.click(screen.getByLabelText('synthetic-source.wav · v1'));
    for (const [label, value] of [['来源起点（毫秒）', '100'], ['来源终点（毫秒）', '900'], ['输出采样率（8000–96000 Hz，可选）', '22050'], ['输出声道（可选）', '1'], ['独立音频交付格式（可选）', 'FLAC']]) fireEvent.change(screen.getByLabelText(label), { target: { value } });
    fireEvent.click(screen.getByRole('button', { name: '读取制作预览' })); await screen.findByRole('region', { name: '制作预览确认' });
    const posts = () => fetcher.mock.calls.filter(([url]) => url.endsWith('/preview')); expect(JSON.parse(posts()[0][1].body as string).parameters.output_format).toBe('FLAC');
    fireEvent.change(screen.getByLabelText('独立音频交付格式（可选）'), { target: { value: '' } }); expect(screen.queryByRole('region', { name: '制作预览确认' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '读取制作预览' })); await screen.findByRole('region', { name: '制作预览确认' });
    expect(Object.hasOwn(JSON.parse(posts()[1][1].body as string).parameters, 'output_format')).toBe(false);
    expect(fetcher.mock.calls.filter(([url, init]) => url.endsWith('/jobs') && init?.method === 'POST')).toHaveLength(0); expect(fetcher.mock.calls.filter(([url]) => url.endsWith('/execute') || url.endsWith('/review'))).toHaveLength(0);
  });
});
