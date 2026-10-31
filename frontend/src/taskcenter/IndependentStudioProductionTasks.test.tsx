// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { IndependentStudioWorkspace } from '../creative/IndependentStudioWorkspace';
import type { StudioOverview } from '../creative/studioClient';
import type { ProductionJob } from '../creative/studioProductionClient';
import { cutoutJob, cutoutProject } from '../creative/studioCpuCutout.testFixtures';
import videoFixture from '../creative/fixtures/phase4.file-api-job-candidate.json';
import emptyPromptLibrary from '../prompt/__fixtures__/empty-library.json';
import { bindLocalHostSession, useLocalHostSession } from '../localHostSession';
import { useStudio } from '../store';
import { tasksResponse } from './taskCenterFixtures';

const projectId = cutoutProject, base = `/api/projects/${projectId}/studio`, production = `${base}/production`;
const image = () => cutoutJob('AWAITING_REVIEW', 3);
const video = () => ({ ...structuredClone(videoFixture), novel_id: projectId, id: 'video-job' }) as unknown as ProductionJob;
const response = (body: unknown, status = 200) => ({ ok: status < 400, status, json: async () => structuredClone(body) });
const deferred = <T,>() => { let resolve!: (value: T) => void; const promise = new Promise<T>(yes => { resolve = yes; }); return { resolve, promise }; };
const button = (name: string | RegExp) => screen.getByRole('button', { name }) as HTMLButtonElement;
let fetcher: ReturnType<typeof vi.fn>, jobReply: ((owner: string) => unknown) | undefined;
beforeEach(() => {
  localStorage.clear(); jobReply = undefined;
  useStudio.setState({ novelId: projectId, chapterId: '', sessionToken: '', actor: undefined, scope: undefined });
  useLocalHostSession.setState({ token: 'studio-reopening-host', actorId: 'local-author', epoch: 1 });
  const overview: StudioOverview = { project: { id: projectId, title: 'Reopening fixture', entry_kind: 'NEUTRAL_STUDIO' },
    preferences: { version: 1, intents: [], preset: 'IMAGE', custom_intent: '' }, capabilities: { can_mutate: true, can_review: true,
      manual_import: true, manual_export: true, chapter_required: false, model_required: false, media_validator_configured: true,
      asset_kinds: ['image', 'video', 'audio'], intent_is_permission: false } };
  fetcher = vi.fn(async (url: string, init: RequestInit = {}) => {
    if (init.method !== 'GET') throw new Error(`Unexpected mutation in read-only test: ${url}`);
    if (url === base) return response(overview);
    if (url === `${base}/assets` || url.startsWith(`${base}/assets?`)) return response({ items: [] });
    if (url === `${base}/prompts`) return response({ ...emptyPromptLibrary, project_id: projectId, scope: { mode: 'local', novel_id: projectId } });
    if (url.includes('/experimental/workspace/tasks?')) return response(tasksResponse({ items: [], unavailable: [] }));
    if (url === `${production}/jobs`) return response({ items: [image(), video()] });
    if (url === `${production}/jobs/image/${image().id}`) return jobReply?.('image') ?? response(image());
    if (url === `${production}/jobs/video/${video().id}`) return jobReply?.('video') ?? response(video());
    if (url === `${production}/providers` || url === `${production}/timelines`) return response({ items: [] });
    // This suite does not fabricate workflow/catalog availability. Those read-only
    // companion panels retain their own unavailable states.
    return response({ code: 'FIXTURE_UNAVAILABLE' }, 404);
  }); vi.stubGlobal('fetch', fetcher);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
function mount() {
  const query = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={query}><IndependentStudioWorkspace projectId={projectId} context={{ sessionToken: '' }}
    scope={{ workspace: '本机', project: 'Reopening fixture', storyline: '默认', branch: '主线' }} actor="作者" module="IMAGE"
    onModuleChange={vi.fn()} onProjectChoice={vi.fn()} /></QueryClientProvider>);
}
async function openTasks() {
  mount(); fireEvent.click(await screen.findByRole('button', { name: '任务中心' }));
  await screen.findByRole('button', { name: `打开原制作任务 ${image().id} v3` });
}
function assertReadOnly() {
  expect(fetcher.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
  expect(fetcher.mock.calls.some(([url]) => /\/experimental\/media\/|\/candidate$|\/review$|\/cancel$|\/execute$/.test(url))).toBe(false);
}

describe('actual independent Studio Tasks to original production panel', () => {
  it.each(['image', 'video'])('reopens the exact %s receipt through the mounted shared shell', async owner => {
    await openTasks(); const job = owner === 'image' ? image() : video();
    fireEvent.click(button(`打开原制作任务 ${job.id} v${job.version}`));
    await screen.findByText(`任务 ${job.id} · v${job.version}`);
    expect(button('制作操作').getAttribute('aria-pressed')).toBe('true');
    expect(screen.queryByRole('region', { name: 'Studio 图片与视频任务' })).toBeNull();
    expect((screen.getByLabelText('操作') as HTMLSelectElement).value).toBe('m5.image.t2i');
    expect((screen.getByLabelText('本次提示词') as HTMLTextAreaElement).value).toBe('');
    expect(fetcher.mock.calls.filter(([url]) => url === `${production}/jobs/${owner}/${job.id}`)).toHaveLength(1);
    assertReadOnly();
  });
  it('keeps Tasks open when the selected receipt advances before exact read', async () => {
    jobReply = () => response({ ...image(), version: 4 }); await openTasks(); fireEvent.click(button(/打开原制作任务 cutout-job/));
    await screen.findByText(/所选制作回执已变化/);
    expect(button('任务中心').getAttribute('aria-pressed')).toBe('true');
    expect(screen.queryByLabelText('当前媒体任务')).toBeNull(); assertReadOnly();
  });
  it('keeps the existing dirty-navigation confirmation and cancel behavior', async () => {
    await openTasks(); fireEvent.change(screen.getByLabelText('自定义意图'), { target: { value: 'Keep my local preference' } });
    fireEvent.click(button(/打开原制作任务 cutout-job/)); await screen.findByRole('button', { name: '继续编辑' });
    expect(screen.queryByLabelText('当前媒体任务')).toBeNull(); fireEvent.click(button('继续编辑'));
    expect((screen.getByLabelText('自定义意图') as HTMLInputElement).value).toBe('Keep my local preference');
    expect(button('任务中心').getAttribute('aria-pressed')).toBe('true');
    fireEvent.click(button(/打开原制作任务 cutout-job/)); await screen.findByRole('button', { name: '继续编辑' });
    fireEvent.click(screen.getByLabelText('确认放弃未保存输入')); fireEvent.click(button('确认离开'));
    await screen.findByText(`任务 ${image().id} · v3`); assertReadOnly();
  });
  it('keeps a newer explicit selection when navigation confirmation is pending', async () => {
    await openTasks(); fireEvent.change(screen.getByLabelText('自定义意图'), { target: { value: 'Local dirty preference' } });
    fireEvent.click(button(/打开原制作任务 cutout-job/)); await screen.findByRole('button', { name: '继续编辑' });
    fireEvent.click(button(/打开原制作任务 video-job/));
    await waitFor(() => expect(fetcher.mock.calls.filter(([url]) => url === `${production}/jobs/video/video-job`)).toHaveLength(1));
    await waitFor(() => expect(button(/打开原制作任务 video-job/).disabled).toBe(false));
    fireEvent.click(screen.getByLabelText('确认放弃未保存输入')); fireEvent.click(button('确认离开'));
    await screen.findByText(`任务 video-job · v${video().version}`);
    expect(screen.queryByText(`任务 ${image().id} · v3`)).toBeNull(); assertReadOnly();
  });
  it('never adopts a delayed receipt after leaving Tasks', async () => {
    const wait = deferred<ReturnType<typeof response>>(); jobReply = () => wait.promise;
    await openTasks(); fireEvent.click(button(/打开原制作任务 cutout-job/)); fireEvent.click(button('素材工作区'));
    await act(async () => wait.resolve(response(image())));
    expect(button('素材工作区').getAttribute('aria-pressed')).toBe('true');
    expect(screen.queryByLabelText('当前媒体任务')).toBeNull(); assertReadOnly();
  });
  it.each(['project', 'host'])('rejects delayed reopening after real %s identity ABA', async kind => {
    const wait = deferred<ReturnType<typeof response>>(); jobReply = () => wait.promise;
    await openTasks(); fireEvent.click(button(/打开原制作任务 cutout-job/));
    act(() => {
      if (kind === 'project') { useStudio.setState({ novelId: 'other-project' }); useStudio.setState({ novelId: projectId }); }
      else { bindLocalHostSession('new-host', { session_mode: 'LOCAL_HOST', actor_id: 'other-author' }); bindLocalHostSession('studio-reopening-host', { session_mode: 'LOCAL_HOST', actor_id: 'local-author' }); }
    });
    await act(async () => wait.resolve(response(image())));
    expect(screen.queryByLabelText('当前媒体任务')).toBeNull(); expect(screen.queryByRole('button', { name: /打开原制作任务/ })).toBeNull(); assertReadOnly();
  });
});
