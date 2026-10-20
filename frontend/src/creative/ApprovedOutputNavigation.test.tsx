// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { useStudio } from '../store';
import { useLocalHostSession } from '../localHostSession';
import { IndependentStudioWorkspace } from './IndependentStudioWorkspace';
import type { StudioAsset, StudioOverview } from './studioClient';
import type { CollaborationContext } from '../api';
import type { ProductionJob } from './studioProductionClient';
import { audioAssets, audioJob, audioProject } from './studioAudioWav.testFixtures';
const base = `/api/projects/${audioProject}/studio`, production = `${base}/production`;
const deferred = <T,>() => { let resolve!: (value: T) => void; const promise = new Promise<T>(yes => { resolve = yes; }); return { promise, resolve }; };
const reply = (value: unknown, status = 200) => ({ ok: status < 400, status, json: async () => value });
let rows: StudioAsset[], currentJob: ProductionJob | undefined, fetcher: ReturnType<typeof vi.fn>, context: CollaborationContext;
const overview = (): StudioOverview => ({ project: { id: audioProject, title: 'WAV controls fixture', entry_kind: 'NEUTRAL_STUDIO' },
  preferences: { version: 1, intents: [], preset: 'IMAGE', custom_intent: '' }, capabilities: { can_mutate: true, can_review: true,
    manual_import: true, manual_export: true, chapter_required: false, model_required: false, media_validator_configured: true,
    asset_kinds: ['image', 'video', 'audio'], intent_is_permission: false } });
beforeEach(() => {
  localStorage.clear();
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:private-wav') });
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() });
  rows = audioAssets(); currentJob = undefined;
  context = { sessionToken: '' }; useStudio.setState({ novelId: audioProject, sessionToken: '', actor: undefined, scope: undefined });
  useLocalHostSession.setState({ token: 'audio-host', actorId: '' });
  fetcher = vi.fn(async (url: string, init?: RequestInit) => {
    if (url === base) return reply(overview());
    if (url.includes('/assets?')) return reply({ items: rows });
    if (url === `${base}/production-contracts`) return reply({ code: 'FIXTURE_CATALOG_UNAVAILABLE' }, 400);
    if (url === `${production}/providers`) return reply({ items: [], health_probed: false, credentials_read: false });
    if (url === `${production}/timelines`) return reply({ items: [] });
    if (url === `${production}/jobs`) return reply({ items: currentJob ? [currentJob] : [] });
    if (url === `${production}/jobs/audio/audio-job`) return reply(currentJob);
    if (url === `${base}/assets/audio-source`) return reply(rows[0]);
    if (url === `${base}/assets/audio-candidate`) return reply(rows.find(row => row.id === 'audio-candidate'));
    if (url === `${base}/assets/audio-candidate/download`) return { ...reply({}), blob: async () => new Blob(['audio'], { type: 'audio/wav' }) };
    throw new Error(`Unexpected fixture request: ${url}`);
  }); vi.stubGlobal('fetch', fetcher);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
function mount() {
  const leave = vi.fn(), query = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const node = (requestedAssetId?: string) => <QueryClientProvider client={query}><IndependentStudioWorkspace projectId={audioProject} context={context} requestedAssetId={requestedAssetId}
    scope={{ workspace: '本机', project: 'WAV controls fixture', storyline: '默认', branch: '主线' }} actor="作者" module="IMAGE"
    onModuleChange={leave} onProjectChoice={leave} /></QueryClientProvider>;
  return { ...render(node()), leave, node };
}
function button(name: string) { return screen.getByRole('button', { name }) as HTMLButtonElement; }
function change(name: string, value: string) { fireEvent.change(screen.getByLabelText(name), { target: { value } }); }
async function reopen() {
  currentJob = audioJob('APPROVED', 4);
  rows.push({ ...audioAssets()[0], id: 'audio-candidate', filename: 'approved.wav', version: 2, sha256: currentJob.output_candidate!.digest });
  const view = mount(); fireEvent.click(await screen.findByRole('button', { name: '制作操作' }));
  await waitFor(() => expect(button('读取任务列表').disabled).toBe(false));
  fireEvent.click(button('读取任务列表'));
  fireEvent.change(await screen.findByLabelText('已保存任务'), { target: { value: 'audio:audio-job' } });
  await screen.findByRole('button', { name: '打开本任务已审核素材' }); return view;
}
const openOutput = () => fireEvent.click(button('打开本任务已审核素材'));
const assetReads = () => fetcher.mock.calls.filter(([url]) => url === `${base}/assets/audio-candidate`);
const noWrites = () => expect(fetcher.mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true);
it('opens the approved version of a reopened job without execution, review or saving a file', async () => {
  const save = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  await reopen(); openOutput(); await screen.findByText(/已打开原任务 audio-job 的已审核素材 approved.wav · v2/);
  expect(assetReads().length).toBeGreaterThanOrEqual(1); expect(button('素材工作区').getAttribute('aria-pressed')).toBe('true');
  expect(fetcher.mock.calls.filter(([url]) => /\/candidate$|\/execute$|\/review$/.test(url)).map(([url]) => url)).toEqual([]); expect(save).not.toHaveBeenCalled(); noWrites();
});
it.each(['version', 'digest', 'kind', 'deleted', 'id'] as const)('does not substitute an asset after %s mismatch', async mismatch => {
  await reopen(); const asset = rows[1];
  if (mismatch === 'version') asset.version = 3;
  if (mismatch === 'digest') asset.sha256 = 'b'.repeat(64);
  if (mismatch === 'kind') { asset.kind = 'video'; asset.media_type = 'video/mp4'; }
  if (mismatch === 'deleted') asset.deleted_at = '2026-10-16';
  if (mismatch === 'id') { fetcher.mockImplementationOnce(async () => reply({ ...asset, id: 'other-asset' })); }
  openOutput(); await screen.findByText(/原任务已审核素材的版本、摘要或类型已变化/);
  expect(button('制作操作').getAttribute('aria-pressed')).toBe('true'); noWrites();
});
it('preserves dirty input when leaving is cancelled, and reads only after explicit discard', async () => {
  await reopen(); change('本次提示词', 'Keep my input'); openOutput();
  await screen.findByRole('button', { name: '继续编辑' }); expect(assetReads()).toHaveLength(0);
  fireEvent.click(button('继续编辑')); expect((screen.getByLabelText('本次提示词') as HTMLTextAreaElement).value).toBe('Keep my input'); expect(assetReads()).toHaveLength(0);
  openOutput(); fireEvent.click(screen.getByLabelText('确认放弃未保存输入')); fireEvent.click(button('确认离开'));
  await screen.findByText(/已打开原任务 audio-job 的已审核素材/); expect(assetReads().length).toBeGreaterThanOrEqual(1); noWrites();
});
it('drops a late asset read after unmount and coalesces repeated clicks', async () => {
  const view = await reopen(); const pending = deferred<ReturnType<typeof reply>>();
  fetcher.mockImplementationOnce(async () => pending.promise); openOutput(); openOutput();
  await waitFor(() => expect(assetReads()).toHaveLength(1)); view.unmount();
  await act(async () => pending.resolve(reply(rows[1]))); expect(screen.queryByText(/已打开原任务/)).toBeNull(); noWrites();
});
it('keeps the original job visible when its asset read fails', async () => {
  await reopen(); fetcher.mockRejectedValueOnce(new Error('offline')); openOutput();
  await waitFor(() => expect(button('打开本任务已审核素材').disabled).toBe(false));
  expect(button('制作操作').getAttribute('aria-pressed')).toBe('true');
  expect(screen.queryByText(/已打开原任务/)).toBeNull(); expect(assetReads()).toHaveLength(1); noWrites();
});

it('does not overwrite a newer requested asset selection with a late approved-output read', async () => {
  const view = await reopen(); const pending = deferred<ReturnType<typeof reply>>();
  fetcher.mockImplementationOnce(async () => pending.promise); openOutput();
  await waitFor(() => expect(assetReads()).toHaveLength(1));
  view.rerender(view.node('audio-source'));
  await waitFor(() => expect(fetcher.mock.calls.some(([url]) => url === `${base}/assets/audio-source`)).toBe(true));
  await act(async () => pending.resolve(reply(rows[1])));
  expect(screen.queryByText(/已打开原任务/)).toBeNull();
  expect(button('制作操作').getAttribute('aria-pressed')).toBe('true'); noWrites();
});

it('retains the original selected job when asset validation fails after explicit draft discard', async () => {
  await reopen(); change('本次提示词', 'Discard explicitly'); rows[1].version = 3; openOutput();
  fireEvent.click(await screen.findByLabelText('确认放弃未保存输入')); fireEvent.click(button('确认离开'));
  await screen.findByText(/原任务已审核素材的版本、摘要或类型已变化/);
  await screen.findByText('任务 audio-job · v4'); expect(button('打开本任务已审核素材')).toBeTruthy(); noWrites();
});
