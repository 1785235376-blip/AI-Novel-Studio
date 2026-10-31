// @vitest-environment jsdom
import { StrictMode, useState } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useLocalHostSession } from '../localHostSession';
import { StudioMediaExecutionPanel } from '../creative/StudioMediaExecutionPanel';
import { cutoutJob, cutoutProject } from '../creative/studioCpuCutout.testFixtures';
import { audioJob } from '../creative/studioAudioWav.testFixtures';
import videoFixture from '../creative/fixtures/phase4.file-api-job-candidate.json';
import { studioProductionClient, type ProductionJob } from '../creative/studioProductionClient';
import { StudioProductionTasksPanel, type StudioProductionTasksProps } from './StudioProductionTasks';
import { exactStudioProductionTask, studioProductionTaskRows, type StudioProductionTask } from './studioProductionTask';

const projectId = cutoutProject, base = `/api/projects/${projectId}/studio/production`, digest = 'a'.repeat(64);
const image = () => cutoutJob('AWAITING_REVIEW', 3) as StudioProductionTask;
const video = () => ({ ...structuredClone(videoFixture), novel_id: projectId, id: 'video-job' }) as unknown as StudioProductionTask;
const audio = () => ({ ...audioJob(), novel_id: projectId });
const response = (value: unknown, status = 200) => ({ ok: status < 400, status, json: async () => structuredClone(value) });
const deferred = <T,>() => { let resolve!: (value: T) => void; const promise = new Promise<T>(yes => { resolve = yes; }); return { resolve, promise }; };
const button = (name: string | RegExp) => screen.getByRole('button', { name }) as HTMLButtonElement;
function retainedClick(element: HTMLElement): () => void {
  const key = Object.keys(element).find(name => name.startsWith('__reactProps$'))!;
  return (element as unknown as Record<string, { onClick: () => void }>)[key].onClick;
}
let fetcher: ReturnType<typeof vi.fn>;
beforeEach(() => {
  useLocalHostSession.setState({ token: '', actorId: '' });
  fetcher = vi.fn(async (url: string) => {
    if (url === `${base}/jobs`) return response({ items: [image(), video(), audio()] });
    if (url === `${base}/jobs/image/${image().id}`) return response(image());
    if (url === `${base}/jobs/video/${video().id}`) return response(video());
    if (url === `${base}/providers`) return response({ items: [] });
    throw new Error(`Unexpected test request: ${url}`);
  });
  vi.stubGlobal('fetch', fetcher);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
function props(patch: Partial<StudioProductionTasksProps> = {}): StudioProductionTasksProps {
  return { projectId, branchId: null, identity: 'session-1', client: studioProductionClient(projectId, { sessionToken: '', localHostToken: '' }),
    active: true, denied: false, busy: false, isCurrent: () => true, read: (work: () => Promise<unknown>) => work(), onOpen: vi.fn(), onUnavailable: vi.fn(), ...patch } as StudioProductionTasksProps;
}
function mount(patch: Partial<StudioProductionTasksProps> = {}) {
  const original = props(patch), view = render(<StudioProductionTasksPanel {...original} />);
  return { original, ...view };
}
const openImage = async () => fireEvent.click(await screen.findByRole('button', { name: `打开原制作任务 ${image().id} v3` }));

describe('original Studio task receipt projection', () => {
  it('lists only image/video through the production decoder, without any automatic GET or action', async () => {
    const state = mount();
    await screen.findByRole('article', { name: `Studio image ${image().id}` });
    expect(screen.getByRole('article', { name: 'Studio video video-job' })).toBeTruthy();
    expect(screen.queryByText(/audio-job/)).toBeNull();
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher.mock.calls[0][0]).toBe(`${base}/jobs`);
    expect(fetcher.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
    expect(screen.queryByRole('button', { name: /执行|批准|取消任务|费用/ })).toBeNull();
    expect(state.original.onOpen).not.toHaveBeenCalled();
  });
  it.each(['image', 'video'] as const)('opens the exact %s owner receipt only after explicit selection', async owner => {
    const state = mount(), expected = owner === 'image' ? image() : video();
    fireEvent.click(await screen.findByRole('button', { name: `打开原制作任务 ${expected.id} v${expected.version}` }));
    await waitFor(() => expect(state.original.onOpen).toHaveBeenCalledTimes(1));
    const [job, lease] = vi.mocked(state.original.onOpen).mock.calls[0];
    expect(job).toEqual(expected); expect(lease()).toBe(true);
    expect(fetcher.mock.calls.map(([url]) => url)).toEqual([`${base}/jobs`, `${base}/jobs/${owner}/${expected.id}`]);
    expect(fetcher.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
  });
  it('supports explicit refresh and shows a distinct successful empty state', async () => {
    fetcher.mockResolvedValue(response({ items: [] })); mount();
    await screen.findByText('当前项目没有图片或视频制作任务');
    fireEvent.click(button('重新读取 Studio 制作任务'));
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
    await screen.findByText('当前项目没有图片或视频制作任务');
  });
  it('uses existing wrapping task metadata for maximum-length original IDs and digests', async () => {
    const row = { ...image(), id: `job${'x'.repeat(237)}` }; fetcher.mockResolvedValue(response({ items: [row] })); mount();
    const metadata = await screen.findByText(`图片 · ${row.id} · v3`);
    expect(metadata.tagName).toBe('DD'); expect(metadata.className).toBe('task-center-task__code');
    expect(screen.getByText(row.request_digest).tagName).toBe('DD');
  });
  it.each([
    ['wrong owner', { owner: 'video' }], ['wrong id', { id: 'other' }], ['newer version', { version: 4 }],
    ['older version', { version: 2 }], ['new request digest', { request_digest: digest }], ['new receipt digest', { receipt_digest: digest }],
    ['foreign project', { novel_id: 'foreign' }], ['foreign branch', { branch_id: 'foreign' }], ['malformed version', { version: 0 }],
    ['malformed digest', { request_digest: 'bad' }], ['changed status', { status: 'FAILED' }],
    ['changed request', { request_id: 'other' }], ['changed command', { command: { ...image().command!, license_note: 'changed' } }],
  ])('rejects %s on exact open and never substitutes another job', async (_label, patch) => {
    fetcher.mockImplementation(async (url: string) => url === `${base}/jobs` ? response({ items: [image()] }) : response({ ...image(), ...patch }));
    const state = mount(); await openImage();
    await screen.findByRole('alert');
    expect(state.original.onOpen).not.toHaveBeenCalled();
    expect(fetcher.mock.calls.map(([url]) => url)).toEqual([`${base}/jobs`, `${base}/jobs/image/${image().id}`]);
    expect(screen.queryByRole('button', { name: /打开原制作任务/ })).toBeNull();
  });
  it.each([
    ['duplicate identity', [image(), image()]], ['malformed receipt', [{ ...image(), automatic_replay: true }]],
    ['foreign project', [{ ...image(), novel_id: 'foreign' }]], ['missing version', [{ ...image(), version: undefined }]],
  ])('fails closed on %s in the original list', async (_name, items) => {
    fetcher.mockResolvedValue(response({ items })); const state = mount();
    await screen.findByRole('alert'); expect(state.original.onOpen).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: /打开原制作任务/ })).toBeNull(); expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it('keeps colliding IDs under distinct original owners', () => {
    const rows = [image(), { ...video(), id: image().id }];
    expect(studioProductionTaskRows(rows, projectId, null)).toEqual(rows);
    expect(() => exactStudioProductionTask(rows[1], rows[0], projectId, null)).toThrow();
  });
  it('compares receipt contents independent of JSON object key order', () => {
    const expected = image(), reordered = Object.fromEntries(Object.entries(expected).reverse()) as StudioProductionTask;
    expect(exactStudioProductionTask(reordered, expected, projectId, null)).toEqual(expected);
  });
  it.each([401, 403])('honors %i with no fallback or automatic re-read', async status => {
    fetcher.mockResolvedValue(response({ detail: { code: 'DENIED', message: 'private diagnostic' } }, status));
    const state = mount(); await screen.findByText(/原 Studio 制作服务拒绝读取/);
    expect(state.original.onUnavailable).toHaveBeenCalledTimes(1); expect(fetcher).toHaveBeenCalledTimes(1);
    expect(button('重新读取 Studio 制作任务').disabled).toBe(true); expect(screen.queryByText('private diagnostic')).toBeNull();
  });
  it('reports removed records without a latest/list fallback', async () => {
    fetcher.mockImplementation(async (url: string) => url === `${base}/jobs` ? response({ items: [image()] }) : response({ detail: { code: 'NOT_FOUND', message: 'missing' } }, 404));
    const state = mount(); await openImage(); await screen.findByText(/所选原制作任务已移除/);
    expect(state.original.onOpen).not.toHaveBeenCalled(); expect(fetcher).toHaveBeenCalledTimes(2);
  });
  it('retries a failed list only after an explicit click', async () => {
    fetcher.mockRejectedValueOnce(new Error('private transport detail')).mockResolvedValue(response({ items: [image()] })); mount();
    await screen.findByRole('alert'); expect(fetcher).toHaveBeenCalledTimes(1); expect(screen.queryByText('private transport detail')).toBeNull();
    fireEvent.click(button('重新读取 Studio 制作任务')); await screen.findByRole('button', { name: /打开原制作任务/ });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
  it('never treats unsupported owners as production navigation targets', () => {
    expect(studioProductionTaskRows([audio()], projectId, null)).toEqual([]);
    expect(() => exactStudioProductionTask(audio(), image(), projectId, null)).toThrow();
  });
});

describe('Studio task reopening lifetime fences', () => {
  it('reads once during StrictMode mount', async () => {
    const original = props(); render(<StrictMode><StudioProductionTasksPanel {...original} /></StrictMode>);
    await screen.findByRole('button', { name: /打开原制作任务 cutout-job/ }); expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it('coalesces repeated open and refresh clicks synchronously', async () => {
    const wait = deferred<ReturnType<typeof response>>();
    fetcher.mockImplementation(async (url: string) => url === `${base}/jobs` ? response({ items: [image()] }) : wait.promise);
    const state = mount(); const open = await screen.findByRole('button', { name: /打开原制作任务/ });
    fireEvent.click(open); fireEvent.click(open); fireEvent.click(button('重新读取 Studio 制作任务'));
    expect(fetcher).toHaveBeenCalledTimes(2);
    await act(async () => wait.resolve(response(image()))); expect(state.original.onOpen).toHaveBeenCalledTimes(1);
  });
  it.each(['project', 'branch', 'identity', 'client', 'busy', 'active', 'denied', 'permission', 'unmount'])('discards late exact GET across %s, including ABA', async change => {
    const wait = deferred<ReturnType<typeof response>>();
    fetcher.mockImplementation(async (url: string) => url === `${base}/jobs` ? response({ items: [image()] }) : wait.promise);
    const state = mount(); await openImage();
    if (change === 'unmount') state.unmount();
    else {
      const patch: Partial<StudioProductionTasksProps> = change === 'project' ? { projectId: 'other' }
        : change === 'branch' ? { branchId: 'other' } : change === 'identity' ? { identity: 'other' }
          : change === 'client' ? { client: studioProductionClient(projectId, { sessionToken: '' }) } : change === 'busy' ? { busy: true }
            : change === 'active' ? { active: false } : change === 'denied' ? { denied: true } : { isCurrent: () => false };
      state.rerender(<StudioProductionTasksPanel {...state.original} {...patch} />);
      state.rerender(<StudioProductionTasksPanel {...state.original} />);
    }
    await act(async () => wait.resolve(response(image())));
    expect(state.original.onOpen).not.toHaveBeenCalled(); expect(fetcher).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole('button', { name: /打开原制作任务/ })).toBeNull();
  });
  it('discards a late list after identity retirement and does not auto-read on return', async () => {
    const wait = deferred<ReturnType<typeof response>>(); fetcher.mockReturnValue(wait.promise);
    const state = mount(); await act(async () => {});
    state.rerender(<StudioProductionTasksPanel {...state.original} identity="retired" />);
    state.rerender(<StudioProductionTasksPanel {...state.original} />);
    await act(async () => wait.resolve(response({ items: [image()] })));
    expect(screen.queryByRole('button', { name: /打开原制作任务/ })).toBeNull(); expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it('checks live workspace identity and semaphore even without a rerender', async () => {
    const wait = deferred<ReturnType<typeof response>>(); let current = true;
    fetcher.mockImplementation(async (url: string) => url === `${base}/jobs` ? response({ items: [image()] }) : wait.promise);
    const state = mount({ isCurrent: () => current }); await openImage(); current = false;
    await act(async () => wait.resolve(response(image()))); expect(state.original.onOpen).not.toHaveBeenCalled();
  });
  it('checks a synchronously acquired workspace semaphore before reading', async () => {
    let busy = false; const state = mount({ isBusy: () => busy }); await screen.findByRole('button', { name: /打开原制作任务 cutout-job/ });
    busy = true; await openImage(); expect(fetcher).toHaveBeenCalledTimes(1); expect(state.original.onOpen).not.toHaveBeenCalled();
  });
  it('invalidates a delayed host-navigation lease on refresh and unmount', async () => {
    const state = mount(); await openImage(); await waitFor(() => expect(state.original.onOpen).toHaveBeenCalledTimes(1));
    const lease = vi.mocked(state.original.onOpen).mock.calls[0][1]; expect(lease()).toBe(true);
    fireEvent.click(button('重新读取 Studio 制作任务')); expect(lease()).toBe(false);
    await screen.findByRole('button', { name: /打开原制作任务 cutout-job/ });
    await openImage(); await waitFor(() => expect(state.original.onOpen).toHaveBeenCalledTimes(2));
    const latestLease = vi.mocked(state.original.onOpen).mock.calls[1][1]; expect(latestLease()).toBe(true);
    state.unmount(); expect(latestLease()).toBe(false);
  });
  it('rejects an old row callback after explicit refresh replaces the displayed list', async () => {
    const state = mount(); const old = retainedClick(await screen.findByRole('button', { name: /打开原制作任务 cutout-job/ }));
    fireEvent.click(button('重新读取 Studio 制作任务'));
    await screen.findByRole('button', { name: /打开原制作任务 cutout-job/ });
    act(old); expect(fetcher).toHaveBeenCalledTimes(2); expect(state.original.onOpen).not.toHaveBeenCalled();
  });
  it('rejects same-tick and retained older selection callbacks after a newer selection', async () => {
    const state = mount(); const oldImage = retainedClick(await screen.findByRole('button', { name: /打开原制作任务 cutout-job/ }));
    const nextVideo = retainedClick(button(/打开原制作任务 video-job/));
    act(() => { nextVideo(); oldImage(); });
    await waitFor(() => expect(state.original.onOpen).toHaveBeenCalledTimes(1));
    expect(vi.mocked(state.original.onOpen).mock.calls[0][0].owner).toBe('video');
    act(oldImage); expect(fetcher).toHaveBeenCalledTimes(2); expect(state.original.onOpen).toHaveBeenCalledTimes(1);
  });
  it('rejects retained row and refresh callbacks across permission ABA before GET', async () => {
    const state = mount(); const old = retainedClick(await screen.findByRole('button', { name: /打开原制作任务 cutout-job/ }));
    const refresh = retainedClick(button('重新读取 Studio 制作任务'));
    state.rerender(<StudioProductionTasksPanel {...state.original} denied />);
    state.rerender(<StudioProductionTasksPanel {...state.original} />);
    act(() => { old(); refresh(); }); expect(fetcher).toHaveBeenCalledTimes(1); expect(state.original.onOpen).not.toHaveBeenCalled();
  });
});

describe('mounted original media panel handoff', () => {
  it('shows the selected receipt without replacing local inputs, sending actions, reading candidates or auto-reviewing', async () => {
    const original = props(), mutation = vi.fn((work: () => Promise<unknown>) => work());
    function Harness() {
      const [job, setJob] = useState<ProductionJob>();
      return <><StudioProductionTasksPanel {...original} onOpen={(next, current) => { if (current()) setJob(next); }} />
        <StudioMediaExecutionPanel client={original.client as ReturnType<typeof studioProductionClient>} assets={[]}
          canMutate canReview busy={false} isCurrent={original.isCurrent} read={work => work()} mutate={mutation as <T>(work: () => Promise<T>) => Promise<T>}
          onDirtyChange={() => {}} onUnavailable={original.onUnavailable} externalJob={job} /></>;
    }
    render(<Harness />);
    await waitFor(() => expect((screen.getByLabelText('本次提示词') as HTMLTextAreaElement).disabled).toBe(false));
    fireEvent.change(screen.getByLabelText('本次提示词'), { target: { value: 'Keep my authored draft' } });
    await openImage(); await screen.findByText(`任务 ${image().id} · v3`);
    expect((screen.getByLabelText('本次提示词') as HTMLTextAreaElement).value).toBe('Keep my authored draft');
    expect((screen.getByLabelText('操作') as HTMLSelectElement).value).toBe('m5.image.t2i');
    expect(mutation).not.toHaveBeenCalled();
    expect(fetcher.mock.calls.every(([url, init]) => init.method === 'GET' && !/candidate|experimental/.test(url))).toBe(true);
    expect(fetcher.mock.calls.filter(([url]) => url.includes('/jobs/image/'))).toHaveLength(1);
    expect(screen.getByText('原任务为本地 CPU 二值遮罩抠图，无服务商、模型、提示词或云端发送。来源顺序：原图片，然后是手绘遮罩。')).toBeTruthy();
  });
});
