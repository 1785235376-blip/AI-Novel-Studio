// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { webcrypto } from 'node:crypto';
import { Blob as NodeBlob } from 'node:buffer';
import { useStudio } from '../store';
import { bindLocalHostSession, useLocalHostSession } from '../localHostSession';
import { IndependentStudioWorkspace } from './IndependentStudioWorkspace';
import type { StudioAsset, StudioOverview } from './studioClient';
import type { CollaborationContext } from '../api';
import type { MediaCommand, ProductionJob } from './studioProductionClient';
import { audioAssets, audioBytes, audioCommand, audioJob, audioPreview, audioProject } from './studioAudioWav.testFixtures';
const base = `/api/projects/${audioProject}/studio`, production = `${base}/production`;
const deferred = <T,>() => { let resolve!: (value: T) => void; const promise = new Promise<T>(yes => { resolve = yes; }); return { promise, resolve }; };
const reply = (value: unknown, status = 200) => ({ ok: status < 400, status, json: async () => value, blob: async () => media });
let media: Blob, rows: StudioAsset[], currentJob: ProductionJob | undefined, fetcher: ReturnType<typeof vi.fn>, context: CollaborationContext;
let executeResponse: ReturnType<typeof deferred<ReturnType<typeof reply>>> | undefined;
let candidateResponse: ReturnType<typeof deferred<ReturnType<typeof reply>>> | undefined;
let createResponse: ReturnType<typeof deferred<ReturnType<typeof reply>>> | undefined;
const overview = (): StudioOverview => ({ project: { id: audioProject, title: 'WAV controls fixture', entry_kind: 'NEUTRAL_STUDIO' },
  preferences: { version: 1, intents: [], preset: 'IMAGE', custom_intent: '' }, capabilities: { can_mutate: true, can_review: true,
    manual_import: true, manual_export: true, chapter_required: false, model_required: false, media_validator_configured: true,
    asset_kinds: ['image', 'video', 'audio'], intent_is_permission: false } });
beforeEach(() => {
  localStorage.clear(); vi.stubGlobal('crypto', webcrypto);
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:private-wav') });
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() });
  media = new NodeBlob([audioBytes()], { type: 'audio/wav' }) as unknown as Blob;
  rows = audioAssets(); currentJob = undefined; executeResponse = undefined; createResponse = undefined; candidateResponse = undefined;
  context = { sessionToken: '' }; useStudio.setState({ novelId: audioProject, sessionToken: '', actor: undefined, scope: undefined });
  useLocalHostSession.setState({ token: 'audio-host', actorId: '' });
  fetcher = vi.fn(async (url: string, init?: RequestInit) => {
    if (url === base) return reply(overview());
    if (url.includes('/assets?')) return reply({ items: rows });
    if (url === `${base}/production-contracts`) return reply({ code: 'FIXTURE_CATALOG_UNAVAILABLE' }, 400);
    if (url === `${production}/providers`) return reply({ items: [], health_probed: false, credentials_read: false });
    if (url === `${production}/timelines`) return reply({ items: [] });
    if (url === `${production}/preview`) return reply(audioPreview(JSON.parse(init!.body as string)));
    if (url === `${production}/jobs`) {
      if (init?.method === 'POST') { const command = JSON.parse(init.body as string).command as MediaCommand; currentJob = audioJob('QUEUED', 1, command); return createResponse?.promise ?? reply(currentJob); }
      return reply({ items: currentJob ? [currentJob] : [] });
    }
    if (url === `${production}/jobs/audio/audio-job`) return reply(currentJob);
    if (url.endsWith('/audio-job/execute')) {
      if (executeResponse) return executeResponse.promise;
      currentJob = audioJob('AWAITING_REVIEW', 3, currentJob!.command as MediaCommand);
      media = new NodeBlob([audioBytes(currentJob.command as MediaCommand)], { type: 'audio/wav' }) as unknown as Blob; return reply(currentJob);
    }
    if (url.endsWith('/audio-job/cancel')) { currentJob = { ...currentJob!, status: 'CANCELLED', version: currentJob!.version + 1, cancellation_mode: 'LOCAL_RESULT_DISCARD' }; return reply(currentJob); }
    if (url.endsWith('/audio-job/reconcile')) { currentJob = audioJob('AWAITING_REVIEW', currentJob!.version + 1, currentJob!.command as MediaCommand); return reply(currentJob); }
    if (url.endsWith('/audio-job/candidate')) return candidateResponse?.promise ?? reply({});
    if (url.endsWith('/audio-job/review')) { currentJob = audioJob('APPROVED', currentJob!.version + 1, currentJob!.command as MediaCommand); return reply(currentJob); }
    throw new Error(`Unexpected fixture request: ${url}`);
  }); vi.stubGlobal('fetch', fetcher);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
function mount() {
  const leave = vi.fn(), query = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const node = () => <QueryClientProvider client={query}><IndependentStudioWorkspace projectId={audioProject} context={context}
    scope={{ workspace: '本机', project: 'WAV controls fixture', storyline: '默认', branch: '主线' }} actor="作者" module="IMAGE"
    onModuleChange={leave} onProjectChoice={leave} /></QueryClientProvider>;
  return { ...render(node()), leave, node };
}
function button(name: string) { return screen.getByRole('button', { name }) as HTMLButtonElement; }
function calls(suffix: string) { return fetcher.mock.calls.filter(([url]) => url.endsWith(suffix)); }
const labels = { gain_db: '增益（-60–12 dB，可选）', sample_rate: '输出采样率（8000–96000 Hz，可选）', channels: '输出声道（可选）' };
function change(name: string, value: string) { fireEvent.change(screen.getByLabelText(name), { target: { value } }); }
async function choose(controls: Record<string, number> = {}) {
  fireEvent.click(await screen.findByRole('button', { name: '制作操作' }));
  await waitFor(() => expect((screen.getByLabelText('操作') as HTMLSelectElement).disabled).toBe(false));
  change('操作', 'm8.audio.trim'); fireEvent.click(await screen.findByLabelText('source.wav · v2'));
  change('来源起点（毫秒）', '100'); change('来源终点（毫秒）', '600');
  for (const [name, value] of Object.entries(controls)) change(labels[name as keyof typeof labels], String(value));
}
async function preview(controls: Record<string, number> = {}) { await choose(controls); fireEvent.click(button('读取制作预览')); await screen.findByRole('region', { name: '制作预览确认' }); }
async function queue(controls: Record<string, number> = {}) { await preview(controls); fireEvent.click(screen.getByLabelText('已核对本次输入、来源和处理边界')); fireEvent.click(button('仅创建任务并入队')); await screen.findByText('任务已保存入队。执行仍需单独点击。'); }
async function execute(controls: Record<string, number> = {}) { await queue(controls); fireEvent.click(button('明确执行当前入队任务')); await waitFor(() => expect(button('读取并核对候选媒体').disabled).toBe(false)); }
async function candidate() { await execute({ gain_db: -6, sample_rate: 22050, channels: 1 }); fireEvent.click(button('读取并核对候选媒体')); await screen.findByLabelText('本任务的音频候选'); }
describe('WAV controls through the original mounted production workspace', () => {
  it('fills exact timecode positions only on explicit apply and uses the original preview command', async () => {
    mount(); await choose({ gain_db: -6 });
    change('裁剪起点时间码', '0:00.125'); change('裁剪终点时间码', '00:00:00.625');
    expect((screen.getByLabelText('来源起点（毫秒）') as HTMLInputElement).value).toBe('100');
    expect((screen.getByLabelText('来源终点（毫秒）') as HTMLInputElement).value).toBe('600');
    expect(calls('/preview')).toHaveLength(0); expect(calls('/jobs')).toHaveLength(0);
    fireEvent.click(button('填入起止毫秒'));
    expect((screen.getByLabelText('来源起点（毫秒）') as HTMLInputElement).value).toBe('125');
    expect((screen.getByLabelText('来源终点（毫秒）') as HTMLInputElement).value).toBe('625');
    fireEvent.click(button('读取制作预览')); await screen.findByRole('region', { name: '制作预览确认' });
    const command = JSON.parse(calls('/preview')[0][1]!.body as string);
    expect(command).toEqual({ ...audioCommand(command.request_id, { gain_db: -6 }), parameters: { in_ms: 125, out_ms: 625, gain_db: -6 } });
    expect(calls('/jobs')).toHaveLength(0); expect(calls('/execute')).toHaveLength(0);
  });
  it('keeps malformed or reversed timecodes from replacing the current millisecond range', async () => {
    mount(); await choose();
    for (const [start, end] of [['0:60', '1:01'], ['0:00', '10:00.001'], ['0:01', '0:00.500'], ['0:01', '0:01']]) {
      change('裁剪起点时间码', start); change('裁剪终点时间码', end);
      expect(button('填入起止毫秒').disabled).toBe(true); fireEvent.click(button('填入起止毫秒'));
      expect((screen.getByLabelText('来源起点（毫秒）') as HTMLInputElement).value).toBe('100');
      expect((screen.getByLabelText('来源终点（毫秒）') as HTMLInputElement).value).toBe('600');
    }
    expect(calls('/preview')).toHaveLength(0);
  });
  it('retires preview consent when applying timecodes and preserves the original duration validation', async () => {
    mount(); await preview(); fireEvent.click(screen.getByLabelText('已核对本次输入、来源和处理边界'));
    change('裁剪起点时间码', '0:00'); change('裁剪终点时间码', '3:00'); fireEvent.click(button('填入起止毫秒'));
    expect(screen.queryByRole('region', { name: '制作预览确认' })).toBeNull();
    expect(button('读取制作预览').disabled).toBe(true); expect(calls('/preview')).toHaveLength(1);
    expect(calls('/jobs')).toHaveLength(0);
    change('裁剪起点时间码', '0:00.100'); change('裁剪终点时间码', '0:00.600'); fireEvent.click(button('填入起止毫秒'));
    expect(button('读取制作预览').disabled).toBe(false);
    expect(screen.queryByRole('button', { name: '仅创建任务并入队' })).toBeNull();
  });
  it('discards unapplied helper input after manual range edits or operation changes', async () => {
    mount(); await choose(); change('裁剪起点时间码', '0:00.222');
    change('来源起点（毫秒）', '200');
    expect((screen.getByLabelText('裁剪起点时间码') as HTMLInputElement).value).toBe('0:00.200');
    change('裁剪起点时间码', '0:00.333'); change('操作', 'm8.audio.speech');
    expect(screen.queryByLabelText('裁剪起点时间码')).toBeNull(); change('操作', 'm8.audio.trim');
    expect((screen.getByLabelText('裁剪起点时间码') as HTMLInputElement).value).toBe('');
    expect(calls('/preview')).toHaveLength(0);
  });
  it('keeps blank controls absent, original defaults explicit, and preview/queue/execute separate', async () => {
    mount(); await preview(); const command = JSON.parse(calls('/preview')[0][1]!.body as string);
    expect(command).toEqual(audioCommand(command.request_id)); expect(calls('/jobs')).toHaveLength(0); expect(calls('/execute')).toHaveLength(0);
    for (const label of Object.values(labels)) expect((screen.getByLabelText(label) as HTMLInputElement).value).toBe('');
    expect(screen.getByText(/不加增益、48000 Hz、双声道/)).toBeTruthy(); expect(button('仅创建任务并入队').disabled).toBe(true);
    expect(screen.queryByLabelText('服务商与模型')).toBeNull(); expect(screen.queryByLabelText('本次提示词')).toBeNull();
    expect(screen.queryByRole('region', { name: '音频实际输出测量' })).toBeNull();
  });
  it('executes explicit controls, shows only measured WAV output, byte-checks privately and requires explicit review', async () => {
    mount(); const controls = { gain_db: -6.25, sample_rate: 22050, channels: 1 }; await queue(controls);
    const command = JSON.parse(calls('/preview')[0][1]!.body as string); expect(command).toEqual(audioCommand(command.request_id, controls));
    expect(calls('/execute')).toHaveLength(0); expect(screen.queryByRole('region', { name: '音频实际输出测量' })).toBeNull();
    fireEvent.click(button('明确执行当前入队任务')); const measured = await screen.findByRole('region', { name: '音频实际输出测量' });
    expect(within(measured).getByText('22050 Hz · 1 声道 · 16 位 PCM WAV')).toBeTruthy(); expect(within(measured).getByText('500 毫秒')).toBeTruthy();
    expect(within(measured).queryByText('-6.25')).toBeNull(); expect(URL.createObjectURL).not.toHaveBeenCalled();
    fireEvent.click(button('读取并核对候选媒体')); await screen.findByLabelText('本任务的音频候选'); expect(button('明确审核并入素材库').disabled).toBe(true);
    fireEvent.click(screen.getByLabelText('已查看本次候选，确认采用当前任务版本与输出摘要')); fireEvent.click(button('明确审核并入素材库'));
    await screen.findByText('原任务已审核入库。产品里程碑验收状态仍为 LOCAL_REQUIRED。'); expect(calls('/execute')).toHaveLength(1); expect(calls('/review')).toHaveLength(1);
    expect(JSON.parse(calls('/review')[0][1]!.body as string)).toEqual({ expected_version: 3, expected_request_digest: 'f'.repeat(64), reviewed_output_digest: currentJob!.output_candidate!.digest });
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:private-wav');
  });
  it.each([['gain_db', '-60.1'], ['gain_db', '12.1'], ['sample_rate', '7999'], ['sample_rate', '96001'], ['sample_rate', '22050.5']] as const)('rejects %s %s without preview dispatch', async (name, value) => {
    mount(); await choose(); change(labels[name], value); expect(button('读取制作预览').disabled).toBe(true); fireEvent.click(button('读取制作预览')); expect(calls('/preview')).toHaveLength(0);
  });
  it('enforces the combined byte budget without rewriting the chosen controls', async () => {
    mount(); await choose({ sample_rate: 96000, channels: 2 }); change('来源终点（毫秒）', '120100');
    expect(screen.getByText(/超过 25 MiB 输出上限/)).toBeTruthy(); expect(button('读取制作预览').disabled).toBe(true);
    expect((screen.getByLabelText(labels.sample_rate) as HTMLInputElement).value).toBe('96000'); expect(calls('/preview')).toHaveLength(0);
  });
  it.each(Object.keys(labels) as Array<keyof typeof labels>)('invalidates consent when %s is edited, including ABA back to blank', async name => {
    mount(); await preview(); fireEvent.click(screen.getByLabelText('已核对本次输入、来源和处理边界'));
    change(labels[name], name === 'gain_db' ? '0' : name === 'sample_rate' ? '22050' : '1');
    expect(screen.queryByRole('region', { name: '制作预览确认' })).toBeNull(); change(labels[name], '');
    expect(screen.queryByRole('button', { name: '仅创建任务并入队' })).toBeNull(); expect(calls('/jobs')).toHaveLength(0);
  });
  it('clears controls when leaving trim and does not expose them to generated audio', async () => {
    mount(); await choose({ gain_db: 0, sample_rate: 22050, channels: 1 }); change('操作', 'm8.audio.speech');
    for (const label of Object.values(labels)) expect(screen.queryByLabelText(label)).toBeNull();
    change('操作', 'm8.audio.trim'); for (const label of Object.values(labels)) expect((screen.getByLabelText(label) as HTMLInputElement).value).toBe('');
  });
  it('revokes source-bound preview when source version changes', async () => {
    mount(); await preview({ gain_db: -6 }); fireEvent.click(screen.getByLabelText('已核对本次输入、来源和处理边界'));
    rows = rows.map(row => ({ ...row, version: row.version + 1 })); fireEvent.click(button('读取当前素材版本'));
    await waitFor(() => expect(screen.queryByRole('region', { name: '制作预览确认' })).toBeNull()); expect(button('读取制作预览').disabled).toBe(true); expect(calls('/jobs')).toHaveLength(0);
  });
  it('recovers a lost create using the original controls/request without replay', async () => {
    mount(); await preview({ gain_db: -6 }); createResponse = deferred(); fireEvent.click(screen.getByLabelText('已核对本次输入、来源和处理边界')); fireEvent.click(button('仅创建任务并入队'));
    await waitFor(() => expect(calls('/jobs')).toHaveLength(1)); await act(async () => createResponse!.resolve(reply({ code: 'UNKNOWN' }, 503)));
    expect(screen.getByText(/操作结果尚未确认/)).toBeTruthy(); fireEvent.click(button('读取任务列表')); await screen.findByText('已找到原请求的保存记录；不会重新创建或执行。');
    expect(calls('/jobs').filter(([, init]) => init?.method === 'POST')).toHaveLength(1); expect(calls('/execute')).toHaveLength(0);
  });
  it('keeps the shared workspace locked while executing and never submits a duplicate execution', async () => {
    const view = mount(); await queue({ gain_db: -6 }); executeResponse = deferred(); fireEvent.click(button('明确执行当前入队任务')); fireEvent.click(button('明确执行当前入队任务'));
    await waitFor(() => expect(calls('/execute')).toHaveLength(1)); expect(button('读取当前素材版本').disabled).toBe(true);
    expect((screen.getByLabelText(labels.gain_db) as HTMLInputElement).disabled).toBe(true);
    expect(button('填入起止毫秒').disabled).toBe(true);
    expect((screen.getByLabelText('裁剪起点时间码') as HTMLInputElement).disabled).toBe(true);
    fireEvent.click(within(screen.getByRole('tablist', { name: '创作模块' })).getByRole('tab', { name: '视频' })); expect(view.leave).not.toHaveBeenCalled();
    await act(async () => executeResponse!.resolve(reply(audioJob('AWAITING_REVIEW', 3, currentJob!.command as MediaCommand))));
    await waitFor(() => expect(button('读取当前素材版本').disabled).toBe(false)); expect(calls('/execute')).toHaveLength(1);
  });
  it('cancels the queued task with exact CAS while preserving its selected controls', async () => {
    mount(); await queue({ gain_db: -6, channels: 1 }); fireEvent.click(button('丢弃未采用的本地结果')); await screen.findByText('已丢弃本地结果');
    expect(JSON.parse(calls('/cancel')[0][1]!.body as string)).toEqual({ expected_version: 1, expected_request_digest: 'f'.repeat(64) });
    expect(currentJob!.command!.parameters).toMatchObject({ gain_db: -6, channels: 1 }); expect(calls('/execute')).toHaveLength(0);
  });
  it.each(['RUNNING', 'UNKNOWN', 'REVIEWING'] as const)('recovers the original %s WAV reservation without reexecution or automatic review', async status => {
    mount(); await choose(); const completed = audioJob('AWAITING_REVIEW', 3, audioCommand('audio-request', { gain_db: -6, sample_rate: 22050, channels: 1 }));
    currentJob = { ...completed, status, output_candidate: status === 'REVIEWING' ? completed.output_candidate : null };
    fireEvent.click(button('读取任务列表')); await screen.findByLabelText('已保存任务'); change('已保存任务', 'audio:audio-job'); await screen.findByText('任务 audio-job · v3');
    fireEvent.click(button('核对中断状态，不重新发送')); await screen.findByText('任务 audio-job · v4');
    expect(calls('/reconcile')).toHaveLength(1); expect(calls('/execute')).toHaveLength(0); expect(calls('/review')).toHaveLength(0);
    expect(button('明确审核并入素材库').disabled).toBe(true); expect(URL.createObjectURL).not.toHaveBeenCalled();
    expect(JSON.parse(calls('/reconcile')[0][1]!.body as string)).toEqual({ expected_version: 3, expected_request_digest: 'f'.repeat(64) });
  });
  it('does not manufacture actual measurements for a legacy completed receipt', async () => {
    mount(); await choose(); currentJob = { ...audioJob('AWAITING_REVIEW', 3), media_measurement: null };
    fireEvent.click(button('读取任务列表')); await screen.findByLabelText('已保存任务'); change('已保存任务', 'audio:audio-job'); await screen.findByText('任务 audio-job · v3');
    expect(screen.queryByRole('region', { name: '音频实际输出测量' })).toBeNull(); expect(screen.getByText(/尚未读取到已核对的 WAV 输出测量/)).toBeTruthy();
  });
  it('rejects private candidate size outside the verified output measurement', async () => {
    mount(); await execute(); media = new NodeBlob([audioBytes().slice(0, -1)], { type: 'audio/wav' }) as unknown as Blob;
    fireEvent.click(button('读取并核对候选媒体')); await screen.findByText('本地 WAV 候选与实际输出测量不一致，不可审核。');
    expect(URL.createObjectURL).not.toHaveBeenCalled(); expect(button('明确审核并入素材库').disabled).toBe(true); expect(calls('/review')).toHaveLength(0);
  });
  it.each(['host', 'host-rebind', 'project', 'actor', 'branch', 'session'])('redacts private candidate and latches %s ABA', async kind => {
    if (['actor', 'branch', 'session'].includes(kind)) {
      context = { sessionToken: 'fixture-author', actor: { id: 'author', displayName: '作者', workspaceId: 'w' }, scope: { workspaceId: 'w', projectId: audioProject, storylineId: 's', branchId: 'b' } };
      rows = rows.map(row => ({ ...row, branch_id: 'b' })); const original = fetcher.getMockImplementation()!;
      fetcher.mockImplementation(async (url, init) => { const response = await original(url, init); const json = response.json;
        return { ...response, json: async () => { const value = await json(); return value && typeof value === 'object' && 'novel_id' in value ? { ...value, branch_id: 'b' } : value; } }; });
      useStudio.setState({ sessionToken: context.sessionToken, actor: context.actor, scope: context.scope });
    }
    mount(); await candidate(); act(() => {
      if (kind === 'host') { useLocalHostSession.setState({ token: 'different' }); useLocalHostSession.setState({ token: 'audio-host' }); }
      else if (kind === 'host-rebind') bindLocalHostSession('audio-host', { session_mode: 'LOCAL_HOST', actor_id: 'new-author' });
      else if (kind === 'project') { useStudio.setState({ novelId: 'other' }); useStudio.setState({ novelId: audioProject }); }
      else if (kind === 'actor') { useStudio.setState({ actor: { ...context.actor!, id: 'other' } }); useStudio.setState({ actor: context.actor }); }
      else if (kind === 'branch') { useStudio.setState({ scope: { ...context.scope!, branchId: 'other' } }); useStudio.setState({ scope: context.scope }); }
      else { useStudio.setState({ sessionToken: 'other' }); useStudio.setState({ sessionToken: context.sessionToken }); }
    });
    expect(screen.queryByLabelText('本任务的音频候选')).toBeNull(); expect(screen.queryByRole('region', { name: '音频实际输出测量' })).toBeNull();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:private-wav'); expect(calls('/review')).toHaveLength(0);
  });
  it('ignores a candidate response arriving after project identity ABA', async () => {
    const view = mount(); await execute(); candidateResponse = deferred(); fireEvent.click(button('读取并核对候选媒体'));
    await waitFor(() => expect(calls('/candidate')).toHaveLength(1)); act(() => { useStudio.setState({ novelId: 'other' }); useStudio.setState({ novelId: audioProject }); });
    await act(async () => candidateResponse!.resolve(reply({}))); view.rerender(view.node()); expect(URL.createObjectURL).not.toHaveBeenCalled(); expect(calls('/review')).toHaveLength(0);
  });
});
