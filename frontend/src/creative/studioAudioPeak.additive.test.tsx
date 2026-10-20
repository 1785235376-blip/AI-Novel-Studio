// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { createHash, webcrypto } from 'node:crypto';
import { Blob as NodeBlob } from 'node:buffer';
import { useLocalHostSession } from '../localHostSession';
import { StudioMediaExecutionPanel } from './StudioMediaExecutionPanel';
import { studioProductionClient, type MediaCommand, type ProductionJob } from './studioProductionClient';
import { audioAssets, audioBytes, audioCommand, audioJob, audioPreview, audioProject } from './studioAudioWav.testFixtures';

// Structural mounted fixtures only. Real native PCM/lifecycle proof is in the CPU suite.
const label = '增益前目标采样峰值（-24 至 -1 dBFS，可选）';
const reply = (value: unknown, status = 200) => ({ ok: status < 400, status, json: async () => value });
const api = () => studioProductionClient(audioProject, { sessionToken: '' });
const hash = (value: Uint8Array) => createHash('sha256').update(value).digest('hex');
function bytes(command: MediaCommand) {
  const result = Buffer.from(audioBytes(command));
  if (command.parameters.target_peak_dbfs !== undefined) {
    const peak = Math.round(32768 * 10 ** ((Number(command.parameters.target_peak_dbfs) + Number(command.parameters.gain_db ?? 0)) / 20));
    for (let offset = 44; offset < result.length; offset += 2) result.writeInt16LE(peak, offset);
  }
  return result;
}
function peakJob(status: ProductionJob['status'], version: number, command: MediaCommand) {
  const result = audioJob(status, version, command);
  if (result.media_measurement && command.parameters.target_peak_dbfs !== undefined) {
    const output = bytes(command), pcm = output.subarray(44), target = Number(command.parameters.target_peak_dbfs);
    result.media_measurement.output_sha256 = hash(output); result.output_candidate!.digest = hash(output);
    result.media_measurement.peak_normalization = { contract: 'studio-audio-sample-peak/1', source_sha256: command.source_snapshots[0].digest,
      selected_pcm_sha256: 'c'.repeat(64), selected_frames: pcm.length / 2 / Number(result.media_measurement.channels), source_peak_s16: 8000,
      target_peak_dbfs: target, normalization_gain_db: target - 20 * Math.log10(8000 / 32768), manual_gain_db: Number(command.parameters.gain_db ?? 0),
      output_peak_s16: Math.abs(pcm.readInt16LE(0)), output_frames: pcm.length / 2 / Number(result.media_measurement.channels), output_pcm_sha256: hash(pcm) };
  }
  return result;
}
let fetcher: ReturnType<typeof vi.fn>, job: ProductionJob | undefined;
const button = (name: string) => screen.getByRole('button', { name }) as HTMLButtonElement;
const change = (name: string, value: string) => fireEvent.change(screen.getByLabelText(name), { target: { value } });
const calls = (suffix: string) => fetcher.mock.calls.filter(([url]) => url.endsWith(suffix));
beforeEach(() => {
  vi.stubGlobal('crypto', webcrypto); useLocalHostSession.setState({ token: 'synthetic-peak-unit', actorId: '' }); job = undefined;
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:peak-unit') });
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() });
  fetcher = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/providers')) return reply({ items: [], health_probed: false, credentials_read: false });
    if (url.endsWith('/preview')) return reply(audioPreview(JSON.parse(init!.body as string)));
    if (url.endsWith('/jobs')) {
      if (init?.method === 'POST') { job = peakJob('QUEUED', 1, JSON.parse(init.body as string).command); return reply(job); }
      return reply({ items: job ? [job] : [] });
    }
    if (url.endsWith('/execute')) { job = peakJob('AWAITING_REVIEW', 3, job!.command as MediaCommand); return reply(job); }
    if (url.endsWith('/candidate')) return { ...reply({}), blob: async () => new NodeBlob([bytes(job!.command as MediaCommand)], { type: 'audio/wav' }) };
    if (url.endsWith('/review')) { job = peakJob('APPROVED', 4, job!.command as MediaCommand); return reply(job); }
    throw new Error('Unexpected peak fixture request');
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
  change('来源起点（毫秒）', '100'); change('来源终点（毫秒）', '600');
}
async function preview() { fireEvent.click(button('读取制作预览')); await screen.findByRole('region', { name: '制作预览确认' }); }
it('keeps absent target exactly omitted and binds an explicit fractional target', async () => {
  mount(); await choose(); await preview(); const first = JSON.parse(calls('/preview')[0][1].body);
  expect(first).toEqual(audioCommand(first.request_id)); change(label, '-6.5'); await preview();
  expect(JSON.parse(calls('/preview')[1][1].body).parameters).toEqual({ in_ms: 100, out_ms: 600, target_peak_dbfs: -6.5 });
  expect(calls('/execute')).toHaveLength(0);
});
it('invalidates target preview and consent on edit-away-and-back', async () => {
  const view = mount(); await choose(); change(label, '-6'); await preview(); fireEvent.click(screen.getByLabelText('已核对本次输入、来源和处理边界'));
  change(label, '-7'); change(label, '-6'); expect(screen.queryByRole('region', { name: '制作预览确认' })).toBeNull();
  expect(view.props.onDirtyChange).toHaveBeenCalledWith(true); expect(calls('/jobs')).toHaveLength(0);
});
it.each(['0', '-25', '-0.5'])('rejects invalid target %s without transport', async value => {
  mount(); await choose(); change(label, value); expect(button('读取制作预览').disabled).toBe(true); expect(calls('/preview')).toHaveLength(0);
});
it('rejects normalized compressed output and excessive manual gain without rewriting inputs', async () => {
  mount(); await choose(); change(label, '-6'); change('增益（-60–12 dB，可选）', '6');
  expect(button('读取制作预览').disabled).toBe(true); change('增益（-60–12 dB，可选）', '0'); change('独立音频交付格式（可选）', 'FLAC');
  expect(button('读取制作预览').disabled).toBe(true); expect((screen.getByLabelText(label) as HTMLInputElement).value).toBe('-6');
});
it('retains separate queue execution candidate and review actions with measured proof', async () => {
  mount(); await choose(); change(label, '-6'); await preview(); fireEvent.click(screen.getByLabelText('已核对本次输入、来源和处理边界'));
  fireEvent.click(button('仅创建任务并入队')); await screen.findByText('任务已保存入队。执行仍需单独点击。'); expect(calls('/execute')).toHaveLength(0);
  fireEvent.click(button('明确执行当前入队任务')); fireEvent.click(button('明确执行当前入队任务'));
  await screen.findByRole('region', { name: '采样峰值实际证明' }); expect(calls('/execute')).toHaveLength(1);
  expect(button('明确审核并入素材库').disabled).toBe(true); fireEvent.click(button('读取并核对候选媒体')); await screen.findByLabelText('本任务的音频候选');
  fireEvent.click(screen.getByLabelText('已查看本次候选，确认采用当前任务版本与输出摘要')); fireEvent.click(button('明确审核并入素材库'));
  await screen.findByText('原任务已审核入库。产品里程碑验收状态仍为 LOCAL_REQUIRED。'); expect(calls('/review')).toHaveLength(1);
});
it.each([null, true, '-6', 0, -25, NaN, Infinity])('rejects malformed target %s before transport', async value => {
  const command = audioCommand(); (command.parameters as Record<string, unknown>).target_peak_dbfs = value;
  await expect(api().preview(command)).rejects.toBeTruthy(); expect(fetcher).not.toHaveBeenCalled();
});
it.each(['missing', 'source', 'frames', 'peak', 'gain', 'null'] as const)('rejects %s normalized output proof on stored get', async mutation => {
  const result = peakJob('AWAITING_REVIEW', 3, audioCommand('peak', { target_peak_dbfs: -6 }));
  const proof = result.media_measurement!.peak_normalization!;
  if (mutation === 'missing') delete result.media_measurement!.peak_normalization;
  else if (mutation === 'source') proof.source_sha256 = 'b'.repeat(64);
  else if (mutation === 'frames') proof.output_frames++;
  else if (mutation === 'peak') proof.output_peak_s16 = 32767;
  else if (mutation === 'gain') proof.normalization_gain_db = 0;
  else (proof as unknown as Record<string, unknown>).target_peak_dbfs = null;
  fetcher.mockResolvedValue(reply(result)); await expect(api().get('audio', result.id)).rejects.toBeTruthy();
});
it('does not adopt a late preview after owner changes away and back', async () => {
  const view = mount(); await choose(); change(label, '-6'); let resolve!: (value: unknown) => void;
  fetcher.mockImplementationOnce(() => new Promise(done => { resolve = done; })); fireEvent.click(button('读取制作预览'));
  await waitFor(() => expect(calls('/preview')).toHaveLength(1)); const input = JSON.parse(calls('/preview')[0][1].body);
  view.rerender(<StudioMediaExecutionPanel {...view.props} client={api()} />); view.rerender(<StudioMediaExecutionPanel {...view.props} />);
  await act(async () => resolve(reply(audioPreview(input)))); expect(screen.queryByRole('region', { name: '制作预览确认' })).toBeNull();
});
it('revokes preview consent after source or author permissions change', async () => {
  const view = mount(); await choose(); change(label, '-6'); await preview(); fireEvent.click(screen.getByLabelText('已核对本次输入、来源和处理边界'));
  view.rerender(<StudioMediaExecutionPanel {...view.props} canMutate={false} />); view.rerender(<StudioMediaExecutionPanel {...view.props} assets={audioAssets().map(row => ({ ...row, version: 3 }))} />);
  expect(screen.queryByRole('region', { name: '制作预览确认' })).toBeNull(); expect(calls('/jobs')).toHaveLength(0);
});
it('keeps UNKNOWN normalization disabled and never automatically executes', async () => {
  const view = mount(); view.rerender(<StudioMediaExecutionPanel {...view.props} externalJob={peakJob('UNKNOWN', 2, audioCommand('peak', { target_peak_dbfs: -6 }))} />);
  await screen.findByText('无法确认先前分派结果，禁止再次执行。同一原任务只能继续读取核对或丢弃本地结果。');
  expect(button('明确执行当前入队任务').disabled).toBe(true); expect(calls('/execute')).toHaveLength(0);
});
