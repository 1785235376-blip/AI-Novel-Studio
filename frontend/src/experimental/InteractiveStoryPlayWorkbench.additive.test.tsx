// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { InteractiveStoryPreview } from './InteractiveStoryPreview';
import type { interactiveStoryClient, InteractiveStory, StoryPlay, StorySpec } from './interactiveStoryClient';
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const spec: StorySpec = { title: '合成互动故事', graph_id: 'graph', graph_version: 1, entry_node_id: 'gate', max_steps: 4,
  variables: [{ name: 'trusted', type: 'bool', initial: false, minimum: 0, maximum: 100 }, { name: 'score', type: 'int', initial: 0, minimum: 0, maximum: 10 }],
  graph_record_ids: [], nodes: [
    { node_id: 'gate', node_version: 1, title: '城门', dialogue: '守卫问话', character_id: 'alice', background_asset_id: null, music_asset_id: null, ending: '',
      choices: [{ id: 'home', label: '回家', target: 'end', condition: 'trusted', assignments: { trusted: true } }, { id: 'wait', label: '等待', target: 'end', condition: '', assignments: {} }] },
    { node_id: 'end', node_version: 1, title: '终章', dialogue: '抵达', character_id: null, background_asset_id: null, music_asset_id: null, ending: '回家', choices: [] },
  ] };

const analysis: NonNullable<InteractiveStory['analysis']> = { issues: [], warnings: [{ code: 'CYCLE_STEP_CAP_REQUIRED', node_id: 'gate' }],
  endings: [{ node_id: 'end', ending: '回家', choices: ['home'] }], states_checked: 3, analysis_complete: true, state_limit_reached: false, step_limit_reached: false, max_steps: 4, can_review: true };

const story: InteractiveStory = { id: 'story', version: 1, status: 'APPROVED', stale: false, content_withheld: false, spec, analysis };

const gatePlay = (patch: Partial<StoryPlay> = {}): StoryPlay => ({
  node: { node_id: 'gate', node_version: 1, title: '城门', dialogue: '守卫问话', character_id: 'alice', background_asset_id: null, music_asset_id: null, ending: '' },
  character_name: 'Alice', choices: [{ id: 'home', label: '回家', enabled: false }, { id: 'wait', label: '等待', enabled: true }],
  variables: { trusted: false, score: 0 }, steps: 0, max_steps: 4, status: 'PLAYING', path: [], ...patch });

const endingPlay = (choices: string[]): StoryPlay => ({
  node: { node_id: 'end', node_version: 1, title: '终章', dialogue: '抵达', character_id: null, background_asset_id: null, music_asset_id: null, ending: '回家' },
  choices: [], variables: { trusted: true, score: 0 }, steps: choices.length, max_steps: 4, status: 'ENDING', path: [...choices] });

const client = (run: ReturnType<typeof vi.fn>) => ({ play: run } as unknown as ReturnType<typeof interactiveStoryClient>);

it('shows the server-authoritative play state: node, dialogue, character, variables, every choice and disabled reasons', async () => {
  const run = vi.fn(async () => gatePlay()); const view = render(<InteractiveStoryPreview api={client(run)} story={story} blocked={false} />);
  expect(run).not.toHaveBeenCalled();
  expect(screen.getByText('APPROVED · v1')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '从开头试玩' }));
  const region = await screen.findByLabelText('互动故事播放');
  expect(region.textContent).toContain('城门');
  expect(region.textContent).toContain('守卫问话');
  expect(region.textContent).toContain('角色：Alice');
  expect(region.textContent).toContain('0 / 4 步 · PLAYING');
  expect(screen.getByText('trusted = false')).toBeTruthy();
  expect(screen.getByText('score = 0')).toBeTruthy();
  expect(screen.getByLabelText('不可选选项原因').textContent).toContain('回家：服务端判定条件未满足：trusted');
  expect((screen.getByRole('button', { name: '回家' }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByRole('button', { name: '等待' }) as HTMLButtonElement).disabled).toBe(false);
  expect(screen.getByLabelText('路径提醒').textContent).toContain('循环需要步数上限');
  expect(view.container.textContent).toContain('未探索');
});

it('starts playback from the bounded analysis witness path through the original service', async () => {
  const run = vi.fn(async (_row: InteractiveStory, choices: string[]) => choices.length ? endingPlay(choices) : gatePlay());
  render(<InteractiveStoryPreview api={client(run)} story={story} blocked={false} />);
  fireEvent.click(screen.getByRole('button', { name: '从见证路径试玩结局：回家（end）' }));
  await screen.findByText('结局：回家');
  expect(run.mock.calls[0][1]).toEqual(['home']);
  expect(screen.getByText('已探索')).toBeTruthy();
  expect(screen.getByText('1 / 4 步 · ENDING')).toBeTruthy();
  expect(story.analysis!.endings[0].choices).toEqual(['home']);
  expect((story.spec!.nodes[0].choices[0].condition)).toBe('trusted');
});

it('lets the author locate back to the editing node without changing the story', async () => {
  const run = vi.fn(async (_row: InteractiveStory, choices: string[]) => choices.length ? endingPlay(choices) : gatePlay());
  const onLocateNode = vi.fn();
  render(<InteractiveStoryPreview api={client(run)} story={story} blocked={false} onLocateNode={onLocateNode} />);
  fireEvent.click(screen.getByRole('button', { name: '定位结局节点 end' }));
  expect(onLocateNode).toHaveBeenLastCalledWith('end');
  fireEvent.click(screen.getByRole('button', { name: '从见证路径试玩结局：回家（end）' }));
  await screen.findByText('结局：回家');
  fireEvent.click(screen.getByRole('button', { name: '定位回编辑节点 终章' }));
  expect(onLocateNode).toHaveBeenLastCalledWith('end');
  expect(onLocateNode).toHaveBeenCalledTimes(2);
  expect(story.spec!.nodes[1].ending).toBe('回家');
});

it('offers a locate entry from an intermediate play result without changing the story', async () => {
  const run = vi.fn(async () => gatePlay());
  const onLocateNode = vi.fn();
  render(<InteractiveStoryPreview api={client(run)} story={story} blocked={false} onLocateNode={onLocateNode} />);
  fireEvent.click(screen.getByRole('button', { name: '从开头试玩' }));
  await screen.findByLabelText('互动故事播放');
  fireEvent.click(screen.getByRole('button', { name: '定位回编辑节点 城门' }));
  expect(onLocateNode).toHaveBeenCalledWith('gate');
  expect(story.spec!.nodes[0].dialogue).toBe('守卫问话');
});

it('retains an explicit failure state for a rejected path instead of reporting success', async () => {
  const run = vi.fn()
    .mockResolvedValueOnce(gatePlay())
    .mockRejectedValueOnce(new ApiError({ status: 409, code: 'VERSION_CONFLICT', message: '版本或来源已改变。' }))
    .mockResolvedValueOnce(endingPlay(['wait']));
  render(<InteractiveStoryPreview api={client(run)} story={story} blocked={false} />);
  fireEvent.click(screen.getByRole('button', { name: '从开头试玩' }));
  await screen.findByLabelText('互动故事播放');
  fireEvent.click(screen.getByRole('button', { name: '等待' }));
  await screen.findByText(/试玩失败：VERSION_CONFLICT/);
  expect(screen.getByText(/版本或来源已改变。 \(VERSION_CONFLICT\)/)).toBeTruthy();
  // A rejected path fails closed: the old server response is not presented as the
  // new state, and the retained failure explains that no state was applied.
  expect(screen.getByText(/请从开头重试；客户端不会自行解释条件/)).toBeTruthy();
  expect(screen.queryByLabelText('互动故事播放')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '从开头试玩' }));
  await screen.findByText('结局：回家');
  expect(screen.queryByText(/试玩失败：VERSION_CONFLICT/)).toBeNull();
});

it.each([
  ['STEP_CAP_REACHED', '已到步数上限。请从开头重试或修改已保存的路径。'],
  ['NO_EXIT', '当前变量没有可用出口，请修正条件。'],
] as const)('shows the %s state returned by the server without inventing an exit', async (status, message) => {
  const run = vi.fn(async () => gatePlay({ status, steps: 4, path: ['wait'] }));
  render(<InteractiveStoryPreview api={client(run)} story={story} blocked={false} />);
  fireEvent.click(screen.getByRole('button', { name: '从开头试玩' }));
  await screen.findByText(message);
  expect(screen.getByText('4 / 4 步 · ' + status)).toBeTruthy();
});

it('dispatches a single playback request for repeated witness clicks', async () => {
  let finish: (value: StoryPlay) => void = () => {};
  const run = vi.fn(() => new Promise<StoryPlay>(resolve => { finish = resolve; }));
  render(<InteractiveStoryPreview api={client(run)} story={story} blocked={false} />);
  const button = screen.getByRole('button', { name: '从见证路径试玩结局：回家（end）' });
  fireEvent.click(button); fireEvent.click(button);
  expect(run).toHaveBeenCalledTimes(1);
  await act(async () => finish(endingPlay(['home'])));
  await screen.findByText('结局：回家');
});

it('does not replay while input is unsaved and keeps the ending navigation read-only', () => {
  const run = vi.fn();
  render(<InteractiveStoryPreview api={client(run)} story={story} blocked={true} />);
  const start = screen.getByRole('button', { name: '从开头试玩' }) as HTMLButtonElement;
  expect(start.disabled).toBe(true);
  fireEvent.click(start);
  expect(run).not.toHaveBeenCalled();
  expect((screen.getByRole('button', { name: '从见证路径试玩结局：回家（end）' }) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.getByText(/试玩只读取已保存版本/)).toBeTruthy();
});

it('hides late playback after the saved story version changes', async () => {
  let finish: (value: StoryPlay) => void = () => {};
  const run = vi.fn(() => new Promise<StoryPlay>(resolve => { finish = resolve; }));
  const view = render(<InteractiveStoryPreview api={client(run)} story={story} blocked={false} />);
  fireEvent.click(screen.getByRole('button', { name: '从开头试玩' }));
  view.rerender(<InteractiveStoryPreview api={client(run)} story={{ ...story, version: 2 }} blocked={false} />);
  await act(async () => finish(gatePlay()));
  expect(screen.queryByLabelText('互动故事播放')).toBeNull();
});
