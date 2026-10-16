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
import { cutoutAssets, cutoutBytes, cutoutCommand, cutoutJob, cutoutPreview, cutoutProject } from './studioCpuCutout.testFixtures';
const base = `/api/projects/${cutoutProject}/studio`, production = `${base}/production`;
const deferred = <T,>() => { let resolve!: (value: T) => void; const promise = new Promise<T>(yes => { resolve = yes; }); return { promise, resolve }; };
const reply = (value: unknown, status = 200) => ({ ok: status < 400, status, json: async () => value, blob: async () => media });
let media: Blob, rows: StudioAsset[], currentJob: ProductionJob | undefined, fetcher: ReturnType<typeof vi.fn>, context: CollaborationContext;
let executeResponse: ReturnType<typeof deferred<ReturnType<typeof reply>>> | undefined;
let readResponse: ReturnType<typeof deferred<ReturnType<typeof reply>>> | undefined;
let cancelResponse: ReturnType<typeof deferred<ReturnType<typeof reply>>> | undefined;
let createResponse: ReturnType<typeof deferred<ReturnType<typeof reply>>> | undefined;
const overview = (): StudioOverview => ({ project: { id: cutoutProject, title: 'CPU cutout fixture', entry_kind: 'NEUTRAL_STUDIO' },
  preferences: { version: 1, intents: [], preset: 'IMAGE', custom_intent: '' }, capabilities: { can_mutate: true, can_review: true,
    manual_import: true, manual_export: true, chapter_required: false, model_required: false, media_validator_configured: true,
    asset_kinds: ['image', 'video', 'audio'], intent_is_permission: false } });
beforeEach(() => {
  localStorage.clear(); vi.stubGlobal('crypto', webcrypto);
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:private-cutout') });
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() });
  media = new NodeBlob([cutoutBytes], { type: 'image/png' }) as unknown as Blob;
  rows = cutoutAssets(); currentJob = undefined; executeResponse = undefined; readResponse = undefined; cancelResponse = undefined; createResponse = undefined;
  context = { sessionToken: '' }; useStudio.setState({ novelId: cutoutProject, sessionToken: '', actor: undefined, scope: undefined });
  useLocalHostSession.setState({ token: 'cutout-host', actorId: '' });
  fetcher = vi.fn(async (url: string, init?: RequestInit) => {
    if (url === base) return reply(overview());
    if (url.includes('/assets?')) return reply({ items: rows });
    if (url === `${base}/production-contracts`) return reply({ code: 'FIXTURE_CATALOG_UNAVAILABLE' }, 400);
    if (url === `${production}/providers`) return reply({ items: [], health_probed: false, credentials_read: false });
    if (url === `${production}/timelines`) return reply({ items: [] });
    if (url === `${production}/preview`) return reply(cutoutPreview(JSON.parse(init!.body as string)));
    if (url === `${production}/jobs`) {
      if (init?.method === 'POST') { const command = JSON.parse(init.body as string).command as MediaCommand; currentJob = cutoutJob('QUEUED', 1, command); return createResponse?.promise ?? reply(currentJob); }
      return reply({ items: currentJob ? [currentJob] : [] });
    }
    if (url === `${production}/jobs/image/cutout-job`) return readResponse?.promise ?? reply(currentJob);
    if (url.endsWith('/cutout-job/execute')) {
      currentJob = cutoutJob('RUNNING', 2, currentJob!.command as MediaCommand);
      if (executeResponse) return executeResponse.promise;
      currentJob = cutoutJob('AWAITING_REVIEW', 3, currentJob.command as MediaCommand); return reply(currentJob);
    }
    if (url.endsWith('/cutout-job/cancel')) {
      const body = JSON.parse(init!.body as string);
      if (body.expected_version !== currentJob!.version || body.expected_request_digest !== currentJob!.request_digest) return reply({ code: 'CAS_CONFLICT' }, 409);
      currentJob = { ...currentJob!, status: 'CANCELLED', version: currentJob!.version + 1, cancellation_mode: 'COOPERATIVE_LOCAL_CANCEL' };
      return cancelResponse?.promise ?? reply(currentJob);
    }
    if (url.endsWith('/cutout-job/reconcile')) { currentJob = { ...currentJob!, version: currentJob!.version + 1, output_candidate: cutoutJob('AWAITING_REVIEW').output_candidate }; return reply(currentJob); }
    if (url.endsWith('/cutout-job/candidate')) return reply({});
    if (url.endsWith('/cutout-job/review')) { currentJob = cutoutJob('APPROVED', currentJob!.version + 1, currentJob!.command as MediaCommand); return reply(currentJob); }
    throw new Error(`Unexpected fixture request: ${url}`);
  }); vi.stubGlobal('fetch', fetcher);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
function mount() {
  const leave = vi.fn(), query = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const node = () => <QueryClientProvider client={query}><IndependentStudioWorkspace projectId={cutoutProject} context={context}
    scope={{ workspace: '本机', project: 'CPU cutout fixture', storyline: '默认', branch: '主线' }} actor="作者" module="IMAGE"
    onModuleChange={leave} onProjectChoice={leave} /></QueryClientProvider>;
  return { ...render(node()), leave, node };
}
function button(name: string) { return screen.getByRole('button', { name }) as HTMLButtonElement; }
function calls(suffix: string) { return fetcher.mock.calls.filter(([url]) => url.endsWith(suffix)); }
async function choose() {
  fireEvent.click(await screen.findByRole('button', { name: '制作操作' }));
  await waitFor(() => expect((screen.getByLabelText('操作') as HTMLSelectElement).disabled).toBe(false));
  fireEvent.change(screen.getByLabelText('操作'), { target: { value: 'm5.image.cutout' } });
  fireEvent.click(await screen.findByLabelText('source.png · v2'));
  fireEvent.change(screen.getByLabelText('绑定当前来源版本的遮罩'), { target: { value: 'mask' } });
}
async function preview() { await choose(); fireEvent.click(button('读取制作预览')); await screen.findByRole('region', { name: '制作预览确认' }); }
async function queue() { await preview(); fireEvent.click(screen.getByLabelText('已核对本次输入、来源和处理边界')); fireEvent.click(button('仅创建任务并入队')); await screen.findByText('任务已保存入队。执行仍需单独点击。'); }
async function candidate() { await queue(); fireEvent.click(button('明确执行当前入队任务')); await waitFor(() => expect(button('读取并核对候选媒体').disabled).toBe(false)); fireEvent.click(button('读取并核对候选媒体')); await screen.findByAltText('本任务经摘要核对的图片候选'); }
describe('CPU cutout through the original mounted Image workspace', () => {
  it('requires separate source/mask, preview, queue, execute, private byte check and review actions', async () => {
    mount(); await preview(); expect(calls('/jobs')).toHaveLength(0); expect(calls('/execute')).toHaveLength(0);
    expect(screen.queryByLabelText('服务商与模型')).toBeNull(); expect(screen.queryByLabelText('本次提示词')).toBeNull();
    const command = JSON.parse(calls('/preview')[0][1]!.body as string);
    expect(command).toEqual(cutoutCommand(command.request_id)); expect(button('仅创建任务并入队').disabled).toBe(true);
    fireEvent.click(screen.getByLabelText('已核对本次输入、来源和处理边界')); fireEvent.click(button('仅创建任务并入队'));
    await screen.findByText('任务已保存入队。执行仍需单独点击。'); expect(calls('/execute')).toHaveLength(0);
    fireEvent.click(button('明确执行当前入队任务')); await waitFor(() => expect(button('读取并核对候选媒体').disabled).toBe(false));
    expect(URL.createObjectURL).not.toHaveBeenCalled(); expect(calls('/review')).toHaveLength(0);
    fireEvent.click(button('读取并核对候选媒体')); await screen.findByAltText('本任务经摘要核对的图片候选');
    expect(button('明确审核并入素材库').disabled).toBe(true); fireEvent.click(screen.getByLabelText('已查看本次候选，确认采用当前任务版本与输出摘要'));
    fireEvent.click(button('明确审核并入素材库')); await screen.findByText('原任务已审核入库。产品里程碑验收状态仍为 LOCAL_REQUIRED。');
    expect(calls('/execute')).toHaveLength(1); expect(calls('/review')).toHaveLength(1);
    expect(JSON.parse(calls('/review')[0][1]!.body as string)).toMatchObject({ expected_version: 3, reviewed_output_digest: currentJob!.output_candidate!.digest });
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:private-cutout');
  });
  it('shows no eligible mask without accepting an imported lookalike', async () => {
    rows = rows.map(row => row.id === 'mask' ? { ...row, manual_mask: undefined } : row); mount(); await choose();
    expect(screen.getByText(/当前没有匹配此来源版本的可用手绘遮罩/)).toBeTruthy(); expect(button('读取制作预览').disabled).toBe(true);
    expect(calls('/preview')).toHaveLength(0);
  });
  it.each(['source', 'mask'])('revokes preview consent when %s version changes and requires explicit rebinding', async id => {
    mount(); await preview(); fireEvent.click(screen.getByLabelText('已核对本次输入、来源和处理边界'));
    rows = rows.map(row => row.id === id ? { ...row, version: row.version + 1 } : row);
    fireEvent.click(button('读取当前素材版本')); await waitFor(() => expect(screen.queryByRole('region', { name: '制作预览确认' })).toBeNull());
    expect(button('读取制作预览').disabled).toBe(true); expect(calls('/jobs')).toHaveLength(0);
  });
  it('keeps a lost create uncertain and recovers only the original saved request', async () => {
    mount(); await preview(); createResponse = deferred(); fireEvent.click(screen.getByLabelText('已核对本次输入、来源和处理边界')); fireEvent.click(button('仅创建任务并入队'));
    await waitFor(() => expect(calls('/jobs')).toHaveLength(1)); await act(async () => createResponse!.resolve(reply({ code: 'UNKNOWN' }, 503)));
    expect(screen.getByText(/操作结果尚未确认/)).toBeTruthy(); expect(screen.queryByRole('button', { name: '仅创建任务并入队' })).toBeNull();
    fireEvent.click(button('读取任务列表')); await screen.findByText('已找到原请求的保存记录；不会重新创建或执行。');
    expect(calls('/jobs').filter(([, init]) => init?.method === 'POST')).toHaveLength(1); expect(calls('/execute')).toHaveLength(0);
  });
  it('re-reads the exact running job, cancels with its current CAS and ignores a late success while keeping global exclusion', async () => {
    const view = mount(); await queue(); executeResponse = deferred(); fireEvent.click(button('明确执行当前入队任务'));
    await waitFor(() => expect(calls('/execute')).toHaveLength(1)); expect(button('读取当前素材版本').disabled).toBe(true);
    fireEvent.click(button('读取运行中的原抠图任务')); await screen.findByText('任务 cutout-job · v2');
    fireEvent.click(button('明确取消运行中的原抠图任务')); await screen.findByText('原任务已记录取消；本地处理和候选采用已被围栏阻止。不会自动重试。');
    expect(JSON.parse(calls('/cancel')[0][1]!.body as string)).toEqual({ expected_version: 2, expected_request_digest: 'f'.repeat(64) });
    fireEvent.click(within(screen.getByRole('tablist', { name: '创作模块' })).getByRole('tab', { name: '视频' })); expect(view.leave).not.toHaveBeenCalled();
    expect(button('读取当前素材版本').disabled).toBe(true);
    const late = cutoutJob('AWAITING_REVIEW', 3, currentJob!.command as MediaCommand); await act(async () => executeResponse!.resolve(reply(late)));
    await waitFor(() => expect(button('读取当前素材版本').disabled).toBe(false));
    expect(screen.getByText('已丢弃本地结果')).toBeTruthy(); expect(screen.queryByRole('region', { name: '媒体候选预览与审核' })).toBeNull();
    expect(calls('/cancel')).toHaveLength(1); expect(calls('/execute')).toHaveLength(1);
  });
  it('keeps the workspace locked if execute settles before an in-flight cancellation response', async () => {
    mount(); await queue(); executeResponse = deferred(); cancelResponse = deferred(); fireEvent.click(button('明确执行当前入队任务'));
    await waitFor(() => expect(calls('/execute')).toHaveLength(1)); fireEvent.click(button('明确取消运行中的原抠图任务'));
    await waitFor(() => expect(calls('/cancel')).toHaveLength(1)); await act(async () => executeResponse!.resolve(reply(cutoutJob('AWAITING_REVIEW', 3, currentJob!.command as MediaCommand))));
    expect(button('读取当前素材版本').disabled).toBe(true); expect(button('明确取消运行中的原抠图任务').disabled).toBe(true);
    await act(async () => cancelResponse!.resolve(reply(currentJob))); await waitFor(() => expect(button('读取当前素材版本').disabled).toBe(false));
    expect(screen.getByText('已丢弃本地结果')).toBeTruthy();
  });
  it.each(['UNKNOWN', 'REVIEWING', 'CANCELLED'] as const)('offers explicit %s recovery without replay or automatic review', async status => {
    mount(); await choose(); currentJob = { ...cutoutJob('AWAITING_REVIEW', 3), status,
      output_candidate: status === 'REVIEWING' ? cutoutJob('AWAITING_REVIEW').output_candidate : null };
    fireEvent.click(button('读取任务列表')); await screen.findByLabelText('已保存任务');
    fireEvent.change(screen.getByLabelText('已保存任务'), { target: { value: 'image:cutout-job' } }); await screen.findByText('任务 cutout-job · v3');
    fireEvent.click(button('核对中断状态，不重新发送')); await screen.findByText('任务 cutout-job · v4');
    expect(calls('/reconcile')).toHaveLength(1); expect(calls('/execute')).toHaveLength(0); expect(calls('/review')).toHaveLength(0);
    if (status === 'CANCELLED') expect(screen.queryByRole('button', { name: '明确审核并入素材库' })).toBeNull();
  });
  it('rejects candidate bytes outside the proven exact output size and clears review', async () => {
    mount(); await queue(); fireEvent.click(button('明确执行当前入队任务')); await waitFor(() => expect(button('读取并核对候选媒体').disabled).toBe(false));
    media = new NodeBlob([cutoutBytes.slice(0, -1)], { type: 'image/png' }) as unknown as Blob;
    fireEvent.click(button('读取并核对候选媒体')); await screen.findByText('本地抠图候选与处理证明不一致，不可审核。');
    expect(URL.createObjectURL).not.toHaveBeenCalled(); expect(button('明确审核并入素材库').disabled).toBe(true); expect(calls('/review')).toHaveLength(0);
  });
  it.each(['host', 'project'])('does not dispatch cancellation after %s ABA during its exact-job read', async kind => {
    mount(); await queue(); executeResponse = deferred(); readResponse = deferred(); fireEvent.click(button('明确执行当前入队任务'));
    await waitFor(() => expect(calls('/execute')).toHaveLength(1)); fireEvent.click(button('明确取消运行中的原抠图任务'));
    await waitFor(() => expect(calls('/jobs/image/cutout-job')).toHaveLength(1));
    act(() => { if (kind === 'host') { useLocalHostSession.setState({ token: 'other' }); useLocalHostSession.setState({ token: 'cutout-host' }); } else { useStudio.setState({ novelId: 'other' }); useStudio.setState({ novelId: cutoutProject }); } });
    await act(async () => readResponse!.resolve(reply(currentJob))); expect(calls('/cancel')).toHaveLength(0);
    await act(async () => executeResponse!.resolve(reply(cutoutJob('AWAITING_REVIEW', 3, currentJob!.command as MediaCommand))));
    expect(screen.queryByText('任务 cutout-job · v3')).toBeNull(); expect(URL.createObjectURL).not.toHaveBeenCalled();
  });
  it('blocks duplicate cancel while uncertain and does not let a late execute clear uncertainty', async () => {
    mount(); await queue(); executeResponse = deferred(); cancelResponse = deferred(); fireEvent.click(button('明确执行当前入队任务'));
    await waitFor(() => expect(calls('/execute')).toHaveLength(1)); fireEvent.click(button('明确取消运行中的原抠图任务')); fireEvent.click(button('明确取消运行中的原抠图任务'));
    await waitFor(() => expect(calls('/cancel')).toHaveLength(1)); await act(async () => cancelResponse!.resolve(reply({ code: 'UNKNOWN' }, 503)));
    expect(button('明确取消运行中的原抠图任务').disabled).toBe(true);
    await act(async () => executeResponse!.resolve(reply(cutoutJob('AWAITING_REVIEW', 3, currentJob!.command as MediaCommand))));
    expect(screen.getByText(/操作结果尚未确认/)).toBeTruthy(); expect(calls('/cancel')).toHaveLength(1);
    expect(screen.queryByRole('region', { name: '媒体候选预览与审核' })).toBeNull();
  });
  it('keeps cancel CAS conflict uncertain until an explicit original read, then binds a new explicit cancellation to that version', async () => {
    mount(); await queue(); executeResponse = deferred(); cancelResponse = deferred(); fireEvent.click(button('明确执行当前入队任务'));
    await waitFor(() => expect(calls('/execute')).toHaveLength(1)); fireEvent.click(button('明确取消运行中的原抠图任务'));
    await waitFor(() => expect(calls('/cancel')).toHaveLength(1)); currentJob = cutoutJob('RUNNING', 3, currentJob!.command as MediaCommand);
    await act(async () => cancelResponse!.resolve(reply({ code: 'CAS_CONFLICT' }, 409))); cancelResponse = undefined;
    expect(button('明确取消运行中的原抠图任务').disabled).toBe(true); expect(calls('/cancel')).toHaveLength(1);
    fireEvent.click(button('读取运行中的原抠图任务')); await screen.findByText('任务 cutout-job · v3');
    fireEvent.click(button('明确取消运行中的原抠图任务')); await screen.findByText('原任务已记录取消；本地处理和候选采用已被围栏阻止。不会自动重试。');
    expect(calls('/cancel')).toHaveLength(2); expect(JSON.parse(calls('/cancel')[1][1]!.body as string).expected_version).toBe(3);
    await act(async () => executeResponse!.resolve(reply(cutoutJob('AWAITING_REVIEW', 3, currentJob!.command as MediaCommand))));
    expect(screen.getByText('任务 cutout-job · v4')).toBeTruthy(); expect(calls('/execute')).toHaveLength(1);
  });
  it.each(['host', 'host-rebind', 'project', 'actor', 'branch', 'session'])('redacts private candidate and latches %s ABA', async kind => {
    if (['actor', 'branch', 'session'].includes(kind)) {
      context = { sessionToken: 'fixture-author', actor: { id: 'author', displayName: '作者', workspaceId: 'w' }, scope: { workspaceId: 'w', projectId: cutoutProject, storylineId: 's', branchId: 'b' } };
      rows = rows.map(row => ({ ...row, branch_id: 'b' }));
      // The decoder must see the actual connected branch in every production response.
      const original = fetcher.getMockImplementation()!; fetcher.mockImplementation(async (url, init) => {
        const response = await original(url, init); const json = response.json;
        return { ...response, json: async () => { const value = await json(); return value && typeof value === 'object' && 'novel_id' in value ? { ...value, branch_id: 'b' } : value; } };
      }); useStudio.setState({ sessionToken: context.sessionToken, actor: context.actor, scope: context.scope });
    }
    mount(); await candidate();
    act(() => {
      if (kind === 'host') { useLocalHostSession.setState({ token: 'different' }); useLocalHostSession.setState({ token: 'cutout-host' }); }
      else if (kind === 'host-rebind') bindLocalHostSession('cutout-host', { session_mode: 'LOCAL_HOST', actor_id: 'new-author' });
      else if (kind === 'project') { useStudio.setState({ novelId: 'other' }); useStudio.setState({ novelId: cutoutProject }); }
      else if (kind === 'actor') { useStudio.setState({ actor: { ...context.actor!, id: 'other' } }); useStudio.setState({ actor: context.actor }); }
      else if (kind === 'branch') { useStudio.setState({ scope: { ...context.scope!, branchId: 'other' } }); useStudio.setState({ scope: context.scope }); }
      else { useStudio.setState({ sessionToken: 'other' }); useStudio.setState({ sessionToken: context.sessionToken }); }
    });
    expect(screen.queryByAltText('本任务经摘要核对的图片候选')).toBeNull(); expect(screen.queryByText('任务 cutout-job · v3')).toBeNull();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:private-cutout'); expect(calls('/review')).toHaveLength(0);
  });
});
