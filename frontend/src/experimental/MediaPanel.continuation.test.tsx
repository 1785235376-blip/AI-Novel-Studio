// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import type { ExperimentalClient, Row } from './api';
import { MediaPanel } from './MediaPanel';

const cover = { id: 'cover', version: 1, kind: 'COVER', title: 'Fixture title', prompt: 'Original prompt', stale: false };
const storyboard = { id: 'brief', version: 2, kind: 'STORYBOARD', title: 'Shot 11', screenplay_id: 'screenplay', shot_id: 'shot', privacy_level: 'LOCAL_ONLY', prompt: 'Retained prompt', stale: false };
const catalog = { characters: [{ id: 'alice', name: 'Alice' }], screenplays: [{ id: 'screenplay', title: 'Original screenplay', edit_version: 7, shots: [{ id: 'shot', number: 11, shot_size: 'MEDIUM' }] }] };
function client(brief: Row = cover, tasks: Row[] = [], proposals: Row[] = []) {
  return { get: vi.fn(async (path: string) => path === '/media/catalog' ? catalog : { items: path.endsWith('/cover-briefs') ? brief.kind === 'COVER' ? [brief] : [] : path.endsWith('/storyboard-briefs') ? brief.kind === 'STORYBOARD' ? [brief] : [] : path.endsWith('/tasks') ? tasks : path.endsWith('/proposals') ? proposals : [] }),
    post: vi.fn(async () => brief), put: vi.fn(async () => ({ ...brief, version: brief.version + 1 })), blob: vi.fn(async () => new Blob(['fixture'])) } as unknown as ExperimentalClient;
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it('uses original project character and screenplay/shot choices, including source CAS', async () => {
  const api = client(); render(<MediaPanel client={api} />);
  await screen.findByRole('option', { name: 'Original screenplay · v7' });
  fireEvent.change(screen.getByLabelText('从原剧本选择分镜来源'), { target: { value: 'screenplay' } });
  fireEvent.change(screen.getByLabelText('从原 Shot 选择分镜镜头'), { target: { value: 'shot' } });
  fireEvent.change(screen.getByLabelText('媒体生成说明'), { target: { value: 'Scene intention' } });
  fireEvent.click(screen.getByRole('button', { name: '从 Shot 创建分镜 Brief' }));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/media/storyboard-briefs', { screenplay_id: 'screenplay', shot_id: 'shot', expected_screenplay_version: 7, prompt: 'Scene intention', privacy_level: 'LOCAL_ONLY' }));
  expect(screen.getByRole('checkbox', { name: 'Alice' })).toBeTruthy();
});

it('retains storyboard revision input after a server version conflict', async () => {
  const api = client(storyboard);
  vi.mocked(api.put).mockRejectedValue(new ApiError({ status: 409, code: 'EXPERIMENTAL_VERSION_CONFLICT', message: '版本冲突' }));
  render(<MediaPanel client={api} />);
  const input = await screen.findByLabelText('修订分镜图像说明');
  fireEvent.change(input, { target: { value: 'My retained revision' } });
  fireEvent.click(screen.getByRole('button', { name: '保存分镜 Brief 修订' }));
  expect(await screen.findByRole('alert')).toBeTruthy();
  expect((input as HTMLTextAreaElement).value).toBe('My retained revision');
  expect(api.put).toHaveBeenCalledWith('/media/storyboard-briefs/brief?expected_version=2', expect.objectContaining({ expected_screenplay_version: 7, prompt: 'My retained revision', shot_id: 'shot' }));
  expect(api.post).not.toHaveBeenCalled();
});

it('persists cover typography and preserves newer input while a save response is delayed', async () => {
  const api = client(); let finish!: (value: Row) => void;
  vi.mocked(api.post).mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  render(<MediaPanel client={api} />); await screen.findByRole('option', { name: 'Original screenplay · v7' });
  fireEvent.change(screen.getByLabelText('封面标题'), { target: { value: 'Submitted title' } });
  fireEvent.change(screen.getByLabelText('封面排版意图'), { target: { value: 'Clear upper title area' } });
  fireEvent.click(screen.getByRole('button', { name: '保存封面 Brief' }));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/media/cover-briefs', expect.objectContaining({ title: 'Submitted title', typography_intent: 'Clear upper title area' })));
  fireEvent.change(screen.getByLabelText('封面标题'), { target: { value: 'Newer title still typing' } });
  finish(cover); await screen.findByText('封面 Brief 已保存');
  expect((screen.getByLabelText('封面标题') as HTMLInputElement).value).toBe('Newer title still typing');
});

it('cancels an in-flight synthetic task with fresh CAS and does not show a late success', async () => {
  const task = { id: 'task', version: 1, status: 'QUEUED', operation: 'cover_generation' };
  const api = client(cover, [task]); let finish!: (value: Row) => void;
  vi.mocked(api.post).mockImplementation(async path => {
    if (path.endsWith('/execute')) { task.status = 'RUNNING'; task.version = 2; return new Promise(resolve => { finish = resolve; }); }
    task.status = 'CANCELLED'; task.version = 3; return task;
  });
  render(<MediaPanel client={api} />);
  fireEvent.click(await screen.findByRole('button', { name: '执行 Mock 图像任务' }));
  await waitFor(() => expect(task.status).toBe('RUNNING'));
  const cancel = screen.getByRole('button', { name: '取消媒体任务' });
  expect(cancel.hasAttribute('disabled')).toBe(false); fireEvent.click(cancel);
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/media/tasks/task/cancel', { expected_version: 2 }));
  finish({ ...task });
  await screen.findByRole('button', { name: '重试媒体任务' });
  expect(screen.queryByRole('button', { name: '批准媒体为资产' })).toBeNull();
  expect(screen.queryByText(/SUCCEEDED/)).toBeNull();
});

it('unmounts private form and comparison state on scope replacement and discards late comparisons', async () => {
  vi.stubGlobal('URL', class extends URL { static createObjectURL() { return 'blob:fixture'; } static revokeObjectURL() {} });
  const proposals = [0, 1].map(index => ({ id: `proposal-${index}`, version: 1, candidate_index: index, kind: 'COVER', status: 'PENDING_REVIEW', stale: false }));
  const api = client(cover, [], proposals); let finish!: (value: unknown) => void;
  vi.mocked(api.post).mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  const view = render(<MediaPanel client={api} />);
  await screen.findByRole('article', { name: '媒体候选 1' });
  fireEvent.change(screen.getByLabelText('封面标题'), { target: { value: 'PRIVATE OLD SCOPE' } });
  fireEvent.click(screen.getByRole('checkbox', { name: 'COVER 候选 1' })); fireEvent.click(screen.getByRole('checkbox', { name: 'COVER 候选 2' }));
  fireEvent.click(screen.getByRole('button', { name: '比较已选媒体候选' }));
  await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
  view.rerender(<MediaPanel client={client()} />);
  finish({ items: proposals, same_source_version: true });
  await waitFor(() => expect(screen.queryByRole('region', { name: '媒体候选比较' })).toBeNull());
  expect((screen.getByLabelText('封面标题') as HTMLInputElement).value).toBe('');
});

it('locates only a task returned by the current owner API without executing it', async () => {
  const api = client(cover, [{ id: 'target', brief_id: 'cover', version: 1, status: 'QUEUED', operation: 'cover_generation' }]);
  const view = render(<MediaPanel client={api} requestedTaskId="target" />);
  await screen.findByText('已定位任务中心请求的原媒体任务。');
  expect(screen.getByRole('article', { name: '媒体任务' }).getAttribute('aria-current')).toBe('true');
  expect(api.post).not.toHaveBeenCalled();
  view.rerender(<MediaPanel client={client()} requestedTaskId="target" />);
  await screen.findByText('请求的媒体任务在当前项目、分支或权限下不可用。');
  expect(screen.queryByText('已定位任务中心请求的原媒体任务。')).toBeNull();
});
