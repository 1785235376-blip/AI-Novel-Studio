// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { webcrypto } from 'node:crypto';
import { Blob as NodeBlob } from 'node:buffer';
import { useLocalHostSession } from '../localHostSession';
import { StudioMediaExecutionPanel } from './StudioMediaExecutionPanel';
import { studioProductionClient, type MediaCommand, type ProductionJob } from './studioProductionClient';
import { audioAssets, audioBytes, audioCommand, audioJob, audioPreview, audioProject } from './studioAudioWav.testFixtures';

// Structural fixtures exercise UI/receipt boundaries, not acoustic quality.
let fetcher: ReturnType<typeof vi.fn>, job: ProductionJob | undefined;
const reply = (value: unknown, status = 200) => ({ ok: status < 400, status, json: async () => value });
const api = () => studioProductionClient(audioProject, { sessionToken: '' });
const fades = { fade_in_ms: 200, fade_out_ms: 300 };
const labels = ['淡入时长（毫秒，可选）', '淡出时长（毫秒，可选）'];
const button = (name: string) => screen.getByRole('button', { name }) as HTMLButtonElement;
const change = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });
const calls = (suffix: string) => fetcher.mock.calls.filter(([url]) => url.endsWith(suffix));
beforeEach(() => {
  vi.stubGlobal('crypto', webcrypto); useLocalHostSession.setState({ token: 'synthetic-fade-unit', actorId: '' }); job = undefined;
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:fade-unit') });
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() });
  fetcher = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/providers')) return reply({ items: [], health_probed: false, credentials_read: false });
    if (url.endsWith('/preview')) return reply(audioPreview(JSON.parse(init!.body as string)));
    if (url.endsWith('/jobs')) {
      if (init?.method === 'POST') { job = audioJob('QUEUED', 1, JSON.parse(init.body as string).command); return reply(job); }
      return reply({ items: job ? [job] : [] });
    }
    if (url.endsWith('/execute')) { job = audioJob('AWAITING_REVIEW', 3, job!.command as MediaCommand); return reply(job); }
    if (url.endsWith('/candidate')) return { ...reply({}), blob: async () => new NodeBlob([audioBytes(job!.command as MediaCommand)], { type: 'audio/wav' }) };
    if (url.endsWith('/review')) { job = audioJob('APPROVED', 4, job!.command as MediaCommand); return reply(job); }
    throw new Error('Unexpected fade fixture request');
  }); vi.stubGlobal('fetch', fetcher);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
function mount() {
  const client = api(), onDirtyChange = vi.fn(), onUnavailable = vi.fn();
  const props = { client, assets: audioAssets(), canMutate: true, canReview: true, busy: false, isCurrent: () => true,
    read: async <T,>(work: () => Promise<T>) => work(), mutate: async <T,>(work: () => Promise<T>) => work(), onDirtyChange, onUnavailable };
  return { ...render(<StudioMediaExecutionPanel {...props} />), props, onDirtyChange, onUnavailable };
}
async function choose() {
  await waitFor(() => expect((screen.getByLabelText('操作') as HTMLSelectElement).disabled).toBe(false));
  change('操作', 'm8.audio.trim'); fireEvent.click(screen.getByLabelText('source.wav · v2'));
  change('来源起点（毫秒）', '100'); change('来源终点（毫秒）', '600');
}
async function preview() { fireEvent.click(button('读取制作预览')); await screen.findByRole('region', { name: '制作预览确认' }); }
async function queue() { await preview(); fireEvent.click(screen.getByLabelText('已核对本次输入、来源和处理边界')); fireEvent.click(button('仅创建任务并入队')); await screen.findByText('任务已保存入队。执行仍需单独点击。'); }
it('keeps omitted fades byte-shape compatible and explicit zero present', async () => {
  mount(); await choose(); await preview();
  const first = JSON.parse(calls('/preview')[0][1].body); expect(first).toEqual(audioCommand(first.request_id));
  change(labels[0], '0'); change(labels[1], '0'); await preview();
  expect(JSON.parse(calls('/preview')[1][1].body).parameters).toEqual({ in_ms: 100, out_ms: 600, fade_in_ms: 0, fade_out_ms: 0 });
  expect(calls('/execute')).toHaveLength(0); expect(calls('/review')).toHaveLength(0);
});
it.each(labels)('invalidates preview and consent on %s ABA edits', async label => {
  const view = mount(); await choose(); await preview(); fireEvent.click(screen.getByLabelText('已核对本次输入、来源和处理边界'));
  change(label, '100'); change(label, '');
  expect(screen.queryByRole('region', { name: '制作预览确认' })).toBeNull(); expect(screen.queryByRole('button', { name: '仅创建任务并入队' })).toBeNull();
  expect(view.onDirtyChange).toHaveBeenCalledWith(true); expect(calls('/jobs').filter(([, init]) => init?.method === 'POST')).toHaveLength(0);
});
it.each(['-1', '1.5', '120001'])('rejects invalid fade %s without dispatch', async value => {
  mount(); await choose(); change(labels[0], value); expect(button('读取制作预览').disabled).toBe(true); expect(calls('/preview')).toHaveLength(0);
});
it('rejects overlap without rewriting controls and clears fades when switching operations', async () => {
  mount(); await choose(); change(labels[0], '300'); change(labels[1], '201');
  expect(screen.getByText('淡入与淡出时长之和不能超过截取片段时长。')).toBeTruthy(); expect(button('读取制作预览').disabled).toBe(true);
  expect((screen.getByLabelText(labels[1]) as HTMLInputElement).value).toBe('201'); change('操作', 'm8.audio.speech');
  expect(screen.queryByLabelText(labels[0])).toBeNull(); change('操作', 'm8.audio.trim'); expect((screen.getByLabelText(labels[0]) as HTMLInputElement).value).toBe('');
});
it('requires separate queue, execute, candidate and approve actions with fades', async () => {
  mount(); await choose(); change(labels[0], '200'); change(labels[1], '300'); await queue(); expect(calls('/execute')).toHaveLength(0);
  fireEvent.click(button('明确执行当前入队任务')); fireEvent.click(button('明确执行当前入队任务'));
  await screen.findByRole('region', { name: '音频实际输出测量' }); expect(calls('/execute')).toHaveLength(1);
  expect(button('明确审核并入素材库').disabled).toBe(true); fireEvent.click(button('读取并核对候选媒体')); await screen.findByLabelText('本任务的音频候选');
  expect(button('明确审核并入素材库').disabled).toBe(true); fireEvent.click(screen.getByLabelText('已查看本次候选，确认采用当前任务版本与输出摘要'));
  fireEvent.click(button('明确审核并入素材库')); await screen.findByText('原任务已审核入库。产品里程碑验收状态仍为 LOCAL_REQUIRED。'); expect(calls('/review')).toHaveLength(1);
});
it('invalidates faded preview after a source version change', async () => {
  const view = mount(); await choose(); change(labels[0], '100'); await preview();
  view.rerender(<StudioMediaExecutionPanel {...view.props} assets={audioAssets().map(row => ({ ...row, version: row.version + 1 }))} />);
  await waitFor(() => expect(screen.queryByRole('region', { name: '制作预览确认' })).toBeNull()); expect(button('读取制作预览').disabled).toBe(true);
});
it('does not adopt a late preview after owner changes away and back', async () => {
  const view = mount(); await choose(); change(labels[0], '100');
  let resolve!: (value: unknown) => void; fetcher.mockImplementationOnce(() => new Promise(done => { resolve = done; }));
  fireEvent.click(button('读取制作预览')); await waitFor(() => expect(calls('/preview')).toHaveLength(1));
  const input = JSON.parse(calls('/preview')[0][1].body);
  view.rerender(<StudioMediaExecutionPanel {...view.props} client={api()} />); view.rerender(<StudioMediaExecutionPanel {...view.props} />);
  await act(async () => resolve(reply(audioPreview(input)))); expect(screen.queryByRole('region', { name: '制作预览确认' })).toBeNull();
});
it('fails closed on denied faded preview', async () => {
  const view = mount(); await choose(); change(labels[0], '100'); fetcher.mockResolvedValueOnce(reply({ code: 'DENIED' }, 403));
  fireEvent.click(button('读取制作预览')); await waitFor(() => expect(view.onUnavailable).toHaveBeenCalled()); expect(screen.queryByRole('region', { name: '制作预览确认' })).toBeNull();
});
it('preserves uncertain create without retrying or executing', async () => {
  mount(); await choose(); change(labels[0], '100'); await preview(); fetcher.mockResolvedValueOnce(reply({ code: 'UNKNOWN' }, 503));
  fireEvent.click(screen.getByLabelText('已核对本次输入、来源和处理边界')); fireEvent.click(button('仅创建任务并入队'));
  await screen.findByText(/操作结果尚未确认/); expect((screen.getByLabelText(labels[0]) as HTMLInputElement).disabled).toBe(true);
  expect(calls('/jobs').filter(([, init]) => init?.method === 'POST')).toHaveLength(1); expect(calls('/execute')).toHaveLength(0);
});
it.each([null, false, '1', -1, 1.5, 120001, Infinity])('rejects malformed fade %s before transport', async value => {
  const command = audioCommand(); (command.parameters as Record<string, unknown>).fade_in_ms = value;
  await expect(api().preview(command)).rejects.toBeTruthy(); expect(fetcher).not.toHaveBeenCalled();
});
it.each(['command', 'execution_recipe'] as const)('rejects fade null in preview %s', async field => {
  const command = audioCommand('fade', fades), result = audioPreview(command);
  result.command = structuredClone(result.command); result.execution_recipe = structuredClone(result.execution_recipe);
  (result[field].parameters as Record<string, unknown>).fade_in_ms = null;
  fetcher.mockResolvedValue(reply(result)); await expect(api().preview(command)).rejects.toBeTruthy();
});
it.each(['omitted', 'zero', 'different', 'missing-measurement'] as const)('rejects incomplete or mismatched faded receipt %s', async mode => {
  const result = audioJob('AWAITING_REVIEW', 3, audioCommand('fade', fades));
  if (mode === 'missing-measurement') result.media_measurement = null;
  else if (mode === 'omitted') delete (result.execution_recipe.parameters as Record<string, unknown>).fade_in_ms;
  else (result.execution_recipe.parameters as Record<string, unknown>).fade_in_ms = mode === 'zero' ? 0 : 199;
  fetcher.mockResolvedValue(reply(result)); await expect(api().get('audio', result.id)).rejects.toBeTruthy();
});
it('keeps UNKNOWN faded jobs readable without making them executable', async () => {
  const result = audioJob('UNKNOWN', 2, audioCommand('fade', fades)); fetcher.mockResolvedValue(reply(result));
  expect(await api().get('audio', result.id)).toEqual(result);
});
it('rejects fade controls on generated audio before transport', async () => {
  const command = { ...audioCommand('fade', fades), operation_id: 'm8.audio.music' as const };
  await expect(api().preview(command)).rejects.toBeTruthy(); expect(fetcher).not.toHaveBeenCalled();
});

it('revokes faded preview consent when author permission changes away and back', async () => {
  const view = mount(); await choose(); change(labels[0], '100'); await preview();
  fireEvent.click(screen.getByLabelText('已核对本次输入、来源和处理边界'));
  view.rerender(<StudioMediaExecutionPanel {...view.props} canMutate={false} />);
  view.rerender(<StudioMediaExecutionPanel {...view.props} />);
  expect(screen.queryByRole('region', { name: '制作预览确认' })).toBeNull();
  expect(calls('/jobs').filter(([, init]) => init?.method === 'POST')).toHaveLength(0);
});
it('keeps UNKNOWN faded receipt execution disabled in the panel', async () => {
  const view = mount();
  view.rerender(<StudioMediaExecutionPanel {...view.props} externalJob={audioJob('UNKNOWN', 2, audioCommand('fade', fades))} />);
  await screen.findByText('无法确认先前分派结果，禁止再次执行。同一原任务只能继续读取核对或丢弃本地结果。');
  expect(button('明确执行当前入队任务').disabled).toBe(true); expect(calls('/execute')).toHaveLength(0);
});
