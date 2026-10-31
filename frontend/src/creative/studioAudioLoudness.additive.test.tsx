// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { webcrypto } from 'node:crypto';
import { useLocalHostSession } from '../localHostSession';
import { StudioMediaExecutionPanel } from './StudioMediaExecutionPanel';
import { studioProductionClient, type ProductionJob } from './studioProductionClient';
import { audioAssets, audioCommand, audioJob, audioPreview, audioProject } from './studioAudioWav.testFixtures';
import actual from './fixtures/studioAudioLoudness.actual.json';

// UI transport mocks check structure/lifetime only. This response fixture was
// produced by test_v2_audio_loudness_api with real CPU FFmpeg, not a mock meter.
const label = '目标综合响度（-30 至 -14 LUFS，可选）';
const reply = (value: unknown) => ({ ok: true, status: 200, json: async () => value });
const api = () => studioProductionClient(audioProject, { sessionToken: '' });
const actualApi = () => studioProductionClient(actual.executed.novel_id, { sessionToken: '' });
let fetcher: ReturnType<typeof vi.fn>;
const button = (name: string) => screen.getByRole('button', { name }) as HTMLButtonElement;
const change = (name: string, value: string) => fireEvent.change(screen.getByLabelText(name), { target: { value } });
const calls = (suffix: string) => fetcher.mock.calls.filter(([url]) => url.endsWith(suffix));
beforeEach(() => {
  vi.stubGlobal('crypto', webcrypto); useLocalHostSession.setState({ token: 'synthetic-loudness-unit', actorId: '' });
  fetcher = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/providers')) return reply({ items: [], health_probed: false, credentials_read: false });
    if (url.endsWith('/preview')) return reply(audioPreview(JSON.parse(init!.body as string)));
    if (url.endsWith('/jobs') && init?.method === 'POST') return reply(audioJob('QUEUED', 1, JSON.parse(init.body as string).command));
    if (url.endsWith('/jobs')) return reply({ items: [] });
    throw new Error('Unexpected loudness UI request');
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
it('omits an absent target and queues an explicitly reviewed fractional LUFS target without dispatch', async () => {
  mount(); await choose(); await preview(); expect(JSON.parse(calls('/preview')[0][1].body).parameters).toEqual({ in_ms: 500, out_ms: 4500 });
  change(label, '-23.5'); await preview(); expect(JSON.parse(calls('/preview')[1][1].body).parameters.target_lufs).toBe(-23.5);
  fireEvent.click(screen.getByLabelText('已核对本次输入、来源和处理边界')); fireEvent.click(button('仅创建任务并入队'));
  await waitFor(() => expect(calls('/jobs')).toHaveLength(1)); expect(calls('/execute')).toHaveLength(0);
});
it.each(['-30.1', '-13.9', '0'])('rejects out of bounds %s before transport', async value => {
  mount(); await choose(); change(label, value); expect(button('读取制作预览').disabled).toBe(true); expect(calls('/preview')).toHaveLength(0);
});
it('rejects short intervals and conflicting processing without rewriting inputs', async () => {
  mount(); await choose(); change(label, '-23.5'); change('来源终点（毫秒）', '3499'); expect(button('读取制作预览').disabled).toBe(true);
  change('来源终点（毫秒）', '4500'); change('增益（-60–12 dB，可选）', '1'); expect(button('读取制作预览').disabled).toBe(true);
  change('增益（-60–12 dB，可选）', '0'); change('淡入时长（毫秒，可选）', '1'); expect(button('读取制作预览').disabled).toBe(true);
  change('淡入时长（毫秒，可选）', '0'); change('增益前目标采样峰值（-24 至 -1 dBFS，可选）', '-6'); expect(button('读取制作预览').disabled).toBe(true);
  change('增益前目标采样峰值（-24 至 -1 dBFS，可选）', ''); change('独立音频交付格式（可选）', 'FLAC'); expect(button('读取制作预览').disabled).toBe(true);
  expect((screen.getByLabelText(label) as HTMLInputElement).value).toBe('-23.5'); expect(calls('/preview')).toHaveLength(0);
});
it('invalidates reviewed preview when target changes away and back', async () => {
  const view = mount(); await choose(); change(label, '-23.5'); await preview(); fireEvent.click(screen.getByLabelText('已核对本次输入、来源和处理边界'));
  change(label, '-24'); change(label, '-23.5'); expect(screen.queryByRole('region', { name: '制作预览确认' })).toBeNull(); expect(view.props.onDirtyChange).toHaveBeenCalledWith(true);
});
it('does not adopt a late preview after source version changes', async () => {
  const view = mount(); await choose(); change(label, '-23.5'); let resolve!: (value: unknown) => void;
  fetcher.mockImplementationOnce(() => new Promise(done => { resolve = done; })); fireEvent.click(button('读取制作预览'));
  await waitFor(() => expect(calls('/preview')).toHaveLength(1)); const command = JSON.parse(calls('/preview')[0][1].body);
  view.rerender(<StudioMediaExecutionPanel {...view.props} assets={audioAssets().map(asset => ({ ...asset, version: 3 }))} />);
  await act(async () => resolve(reply(audioPreview(command)))); expect(screen.queryByRole('region', { name: '制作预览确认' })).toBeNull(); expect(calls('/jobs')).toHaveLength(0);
});
it.each([null, true, '-23', NaN, Infinity, -31, -13])('rejects malformed target %s before transport', async target => {
  const command = audioCommand('loudness', { in_ms: 500, out_ms: 4500 }); (command.parameters as Record<string, unknown>).target_lufs = target;
  await expect(api().preview(command)).rejects.toBeTruthy(); expect(fetcher).not.toHaveBeenCalled();
});
it('decodes actual CPU queued executed approved and list responses', async () => {
  for (const result of [actual.queued, actual.executed, actual.approved]) {
    fetcher.mockResolvedValue(reply(result)); expect(await actualApi().get('audio', result.id)).toEqual(result);
  }
  fetcher.mockResolvedValue(reply({ items: [actual.executed] })); expect((await actualApi().list())[0]).toEqual(actual.executed);
});
it.each(['missing', 'version', 'source', 'interval', 'outputHash', 'frames', 'gain', 'peak', 'target', 'nonfinite', 'extra'] as const)('rejects %s actual measured proof corruption', async mutation => {
  const result = structuredClone(actual.executed) as unknown as ProductionJob;
  const proof = result.media_measurement!.loudness_matching!;
  if (mutation === 'missing') delete result.media_measurement!.loudness_matching;
  else if (mutation === 'version') proof.source_version++;
  else if (mutation === 'source') proof.source_sha256 = 'b'.repeat(64);
  else if (mutation === 'interval') proof.in_ms++;
  else if (mutation === 'outputHash') proof.output_sha256 = 'b'.repeat(64);
  else if (mutation === 'frames') proof.output_frames++;
  else if (mutation === 'gain') proof.applied_gain_db = 0;
  else if (mutation === 'peak') proof.output_true_peak_dbtp = 0;
  else if (mutation === 'target') proof.output_lufs++;
  else if (mutation === 'nonfinite') proof.output_lufs = Infinity;
  else (proof as unknown as Record<string, unknown>).extra = true;
  fetcher.mockResolvedValue(reply(result)); await expect(actualApi().get('audio', result.id)).rejects.toBeTruthy();
});
it('shows actual measured input/output proof while retaining private review controls', async () => {
  const view = mount(); view.rerender(<StudioMediaExecutionPanel {...view.props} externalJob={actual.executed as unknown as ProductionJob} />);
  const region = await screen.findByRole('region', { name: '综合响度实测证据' }); expect(region.textContent).toContain('-23.5 LUFS');
  expect(region.textContent).toContain(actual.executed.media_measurement.loudness_matching.output_pcm_sha256);
  expect(button('明确审核并入素材库').disabled).toBe(true); expect(calls('/execute')).toHaveLength(0);
});
it('keeps UNKNOWN loudness jobs disabled and never automatically reruns', async () => {
  const view = mount(); const job = structuredClone(actual.queued) as unknown as ProductionJob; job.status = 'UNKNOWN';
  view.rerender(<StudioMediaExecutionPanel {...view.props} externalJob={job} />);
  await screen.findByText('无法确认先前分派结果，禁止再次执行。同一原任务只能继续读取核对或丢弃本地结果。');
  expect(button('明确执行当前入队任务').disabled).toBe(true); expect(calls('/execute')).toHaveLength(0);
});
