// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { webcrypto } from 'node:crypto';
import { useLocalHostSession } from '../localHostSession';
import { StudioMediaExecutionPanel } from './StudioMediaExecutionPanel';
import { studioProductionClient, type ProductionJob } from './studioProductionClient';
import { AUDIO_DENOISE_PROFILE } from './studioAudioDenoiseContract';
import { audioAssets, audioCommand, audioJob, audioPreview, audioProject } from './studioAudioWav.testFixtures';
import actual from './fixtures/studioAudioDenoise.actual.json';

const label = '本地平稳噪声降噪（可选）';
const reply = (value: unknown) => ({ ok: true, status: 200, json: async () => value });
let fetcher: ReturnType<typeof vi.fn>;
const button = (name: string) => screen.getByRole('button', { name }) as HTMLButtonElement;
const change = (name: string, value: string) => fireEvent.change(screen.getByLabelText(name), { target: { value } });
const calls = (suffix: string) => fetcher.mock.calls.filter(([url]) => url.endsWith(suffix));
const api = () => studioProductionClient(audioProject, { sessionToken: '' });
beforeEach(() => {
  vi.stubGlobal('crypto', webcrypto); useLocalHostSession.setState({ token: 'synthetic-denoise-unit', actorId: '' });
  fetcher = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/providers')) return reply({ items: [], health_probed: false, credentials_read: false });
    if (url.endsWith('/preview')) return reply(audioPreview(JSON.parse(init!.body as string)));
    if (url.endsWith('/jobs') && init?.method === 'POST') return reply(audioJob('QUEUED', 1, JSON.parse(init.body as string).command));
    if (url.endsWith('/jobs')) return reply({ items: [] });
    throw new Error('Unexpected denoise UI request');
  }); vi.stubGlobal('fetch', fetcher);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
function mount() {
  const props = { client: api(), assets: audioAssets(), canMutate: true, canReview: true, busy: false, isCurrent: () => true,
    read: async <T,>(work: () => Promise<T>) => work(), mutate: async <T,>(work: () => Promise<T>) => work(), onDirtyChange: vi.fn(), onUnavailable: vi.fn() };
  return { ...render(<StudioMediaExecutionPanel {...props} />), props };
}
async function choose() {
  await waitFor(() => expect((screen.getByLabelText('操作') as HTMLSelectElement).disabled).toBe(false));
  change('操作', 'm8.audio.trim'); fireEvent.click(screen.getByLabelText('source.wav · v2'));
  change('来源起点（毫秒）', '500'); change('来源终点（毫秒）', '4500');
}
async function preview() { fireEvent.click(button('读取制作预览')); await screen.findByRole('region', { name: '制作预览确认' }); }
it('defaults off, reviews a fixed profile and queues through the original owner without automatic execution', async () => {
  mount(); await choose(); await preview();
  expect(JSON.parse(calls('/preview')[0][1].body).parameters).toEqual({ in_ms: 500, out_ms: 4500 });
  change(label, AUDIO_DENOISE_PROFILE); await preview();
  expect(JSON.parse(calls('/preview')[1][1].body).parameters.denoise_profile).toBe(AUDIO_DENOISE_PROFILE);
  fireEvent.click(screen.getByLabelText('已核对本次输入、来源和处理边界')); fireEvent.click(button('仅创建任务并入队'));
  await waitFor(() => expect(calls('/jobs')).toHaveLength(1)); expect(calls('/execute')).toHaveLength(0);
});
it('invalidates reviewed preview on profile ABA and preserves conflicting inputs until explicitly corrected', async () => {
  mount(); await choose(); change(label, AUDIO_DENOISE_PROFILE); await preview();
  fireEvent.click(screen.getByLabelText('已核对本次输入、来源和处理边界'));
  change(label, ''); change(label, AUDIO_DENOISE_PROFILE);
  expect(screen.queryByRole('region', { name: '制作预览确认' })).toBeNull();
  change('增益（-60–12 dB，可选）', '1'); expect(button('读取制作预览').disabled).toBe(true);
  expect((screen.getByLabelText(label) as HTMLSelectElement).value).toBe(AUDIO_DENOISE_PROFILE);
  change('增益（-60–12 dB，可选）', '0'); change('来源终点（毫秒）', '1499'); expect(button('读取制作预览').disabled).toBe(true);
  change('来源终点（毫秒）', '1500'); expect(button('读取制作预览').disabled).toBe(false);
});
it.each([null, true, 'arbitrary-filter', 'STATIONARY_FFT_V2'])('rejects malformed profile %s before transport', async value => {
  const command = audioCommand('denoise', { in_ms: 0, out_ms: 2000 });
  (command.parameters as Record<string, unknown>).denoise_profile = value;
  await expect(api().preview(command)).rejects.toBeTruthy(); expect(fetcher).not.toHaveBeenCalled();
});
it('decodes real CPU File queued, executed, approved and history responses', async () => {
  const client = studioProductionClient(actual.executed.novel_id, { sessionToken: '' });
  for (const result of [actual.queued, actual.executed, actual.approved]) {
    fetcher.mockResolvedValue(reply(result)); expect(await client.get('audio', result.id)).toEqual(result);
  }
  fetcher.mockResolvedValue(reply({ items: [actual.executed] })); expect((await client.list())[0]).toEqual(actual.executed);
});
it.each(['missing', 'source', 'version', 'interval', 'frames', 'hash', 'rms', 'profile', 'extra'] as const)('rejects %s corruption in actual denoise proof', async mutation => {
  const result = structuredClone(actual.executed) as unknown as ProductionJob;
  const proof = result.media_measurement!.noise_reduction!;
  if (mutation === 'missing') delete result.media_measurement!.noise_reduction;
  else if (mutation === 'source') proof.source_sha256 = 'b'.repeat(64);
  else if (mutation === 'version') proof.source_version++;
  else if (mutation === 'interval') proof.in_ms++;
  else if (mutation === 'frames') proof.output_frames++;
  else if (mutation === 'hash') proof.output_sha256 = 'b'.repeat(64);
  else if (mutation === 'rms') proof.output_rms_s16 = Infinity;
  else if (mutation === 'profile') (proof as unknown as Record<string, unknown>).profile = 'wrong';
  else (proof as unknown as Record<string, unknown>).extra = true;
  fetcher.mockResolvedValue(reply(result));
  await expect(studioProductionClient(actual.executed.novel_id, { sessionToken: '' }).get('audio', result.id)).rejects.toBeTruthy();
});
