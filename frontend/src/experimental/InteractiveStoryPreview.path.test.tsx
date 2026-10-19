// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import type { interactiveStoryClient, InteractiveStory, StoryChoice, StoryNode, StoryPlay, StorySpec } from './interactiveStoryClient';
import { InteractiveStoryPreview } from './InteractiveStoryPreview';

type StoryApi = ReturnType<typeof interactiveStoryClient>;
const choice = (id: string, label: string, target: unknown): StoryChoice => ({ id, label, target: target as string, condition: '', assignments: {} });
const node = (nodeId: string, title: string, choices: StoryChoice[] = [], ending = ''): StoryNode => ({ node_id: nodeId, node_version: 1, title, dialogue: '对白 ' + nodeId, character_id: null, background_asset_id: null, music_asset_id: null, ending, choices });
const spec = (entry: string, nodes: StoryNode[], maxSteps = 8): StorySpec => ({ title: 'Path story', graph_id: 'graph', graph_version: 1, entry_node_id: entry, nodes, variables: [], graph_record_ids: [], max_steps: maxSteps });
const story = (value: StorySpec): InteractiveStory => ({ id: 'story', version: 1, status: 'DRAFT', stale: false, content_withheld: false, spec: value });
const playAt = (nodeId: string, over: Partial<StoryPlay> = {}): StoryPlay => ({ node: { node_id: nodeId, node_version: 1, title: nodeId, dialogue: '', character_id: null, background_asset_id: null, music_asset_id: null, ending: '' }, choices: [], variables: {}, steps: 0, max_steps: 8, status: 'PLAYING', path: [], ...over });
const apiFor = (result: StoryPlay): StoryApi => ({ play: vi.fn(async () => result) } as unknown as StoryApi);
const deepFreeze = <T,>(value: T): T => { Object.freeze(value); for (const key of Object.keys(value as object)) { const child = (value as Record<string, unknown>)[key]; if (child && typeof child === 'object') deepFreeze(child); } return value; };
const stepArticle = (step: number) => screen.getByRole('article', { name: '路径步骤 ' + step });
const stepBody = (step: number) => within(stepArticle(step));
async function start(storyValue: InteractiveStory) { fireEvent.click(screen.getByRole('button', { name: '从开头试玩' })); await screen.findByLabelText('互动故事播放'); }
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it('resolves step 1 from the saved entry_node_id rather than the first stored node', () => {
  render(<InteractiveStoryPreview api={apiFor(playAt('gate'))} story={story(spec('gate', [node('end', '终章'), node('gate', '城门', [choice('home', '回家', 'end')])]))} blocked={false} />);
  expect(stepBody(1).getByText(/步骤 1：城门/)).toBeTruthy();
  expect(stepBody(1).getByText('节点 ID：gate')).toBeTruthy();
  expect(stepBody(1).getByText('选择：入口步骤（无前序选择）')).toBeTruthy();
  expect(screen.queryByRole('article', { name: '路径步骤 2' })).toBeNull();
  expect(screen.queryByText(/终章/)).toBeNull();
  expect(screen.getByText('尚未开始试玩：从已保存入口节点开始展示，尚无已记录选择。')).toBeTruthy();
});

it('walks later steps through each current node choice.target and keeps labels and raw IDs', async () => {
  const value = story(spec('gate', [
    node('gate', '城门', [choice('home', '回家', 'hall')]),
    node('hall', '大厅', [choice('forward', '前进', 'end')]),
    node('end', '终点', [], '到家')
  ]));
  const api = apiFor(playAt('end', { path: ['home', 'forward'], steps: 2, status: 'ENDING' }));
  render(<InteractiveStoryPreview api={api} story={value} blocked={false} />);
  await start(value);
  expect(stepBody(2).getByText(/步骤 2：大厅/)).toBeTruthy();
  expect(stepBody(2).getByText('节点 ID：hall')).toBeTruthy();
  expect(stepBody(2).getByText('选择文案：回家')).toBeTruthy();
  expect(stepBody(2).getByText('Choice ID：home')).toBeTruthy();
  expect(stepBody(3).getByText(/步骤 3：终点/)).toBeTruthy();
  expect(stepBody(3).getByText('选择文案：前进')).toBeTruthy();
  expect(stepBody(3).getByText('Choice ID：forward')).toBeTruthy();
  expect(screen.getAllByRole('article', { name: /路径步骤/ })).toHaveLength(3);
});

it('matches the same choice ID inside the current node only', async () => {
  const value = story(spec('A', [
    node('A', '甲', [choice('go', '甲到乙', 'B')]),
    node('B', '乙', [choice('go', '乙到丙', 'C')]),
    node('C', '丙', [], '结束')
  ]));
  render(<InteractiveStoryPreview api={apiFor(playAt('C', { path: ['go', 'go'], steps: 2, status: 'ENDING' }))} story={value} blocked={false} />);
  await start(value);
  expect(stepBody(2).getByText('节点 ID：B')).toBeTruthy();
  expect(stepBody(2).getByText('选择文案：甲到乙')).toBeTruthy();
  expect(stepBody(3).getByText('节点 ID：C')).toBeTruthy();
  expect(stepBody(3).getByText('选择文案：乙到丙')).toBeTruthy();
});

it('keeps the raw choice ID and reports an unknown choice instead of borrowing another node choice', async () => {
  const value = story(spec('gate', [node('gate', '城门', [choice('home', '回家', 'end')]), node('end', '终章')]));
  render(<InteractiveStoryPreview api={apiFor(playAt('gate', { path: ['missing'], steps: 1 }))} story={value} blocked={false} />);
  await start(value);
  expect(screen.getByText(/未知选择：当前节点 gate 中不存在 choice missing/)).toBeTruthy();
  expect(screen.getByText(/路径记录与当前故事定义不一致/)).toBeTruthy();
  expect(stepBody(1).getByText('节点 ID：gate')).toBeTruthy();
  expect(screen.queryByRole('article', { name: '路径步骤 2' })).toBeNull();
});

it('reports duplicate choice IDs inside one node as an ambiguity and stops', async () => {
  const value = story(spec('gate', [node('gate', '城门', [choice('dup', '一', 'gate'), choice('dup', '二', 'end')]), node('end', '终章')]));
  render(<InteractiveStoryPreview api={apiFor(playAt('gate', { path: ['dup'], steps: 1 }))} story={value} blocked={false} />);
  await start(value);
  expect(screen.getByText(/选择 dup 在当前节点 gate 中存在重复（歧义）/)).toBeTruthy();
  expect(screen.queryByRole('article', { name: '路径步骤 2' })).toBeNull();
});

it('shows the raw entry ID for an unknown entry node and never guesses another node', () => {
  render(<InteractiveStoryPreview api={apiFor(playAt('gate'))} story={story(spec('ghost', [node('gate', '城门')]))} blocked={false} />);
  expect(stepBody(1).getByText(/步骤 1：未知节点标题/)).toBeTruthy();
  expect(stepBody(1).getByText('节点 ID：ghost')).toBeTruthy();
  expect(screen.getByText(/未知入口节点：故事定义中不存在节点 ghost/)).toBeTruthy();
  expect(screen.queryByText(/城门/)).toBeNull();
});

it('keeps the entry node ID when its title is missing and keeps later node IDs too', async () => {
  const value = story(spec('gate', [node('gate', '', [choice('home', '回家', 'end')]), node('end', '')]));
  render(<InteractiveStoryPreview api={apiFor(playAt('end', { path: ['home'], steps: 1, status: 'ENDING' }))} story={value} blocked={false} />);
  expect(stepBody(1).getByText(/步骤 1：未知节点标题/)).toBeTruthy();
  expect(stepBody(1).getByText('节点 ID：gate')).toBeTruthy();
  await start(value);
  expect(stepBody(2).getByText(/步骤 2：未知节点标题/)).toBeTruthy();
  expect(stepBody(2).getByText('节点 ID：end')).toBeTruthy();
});

it('keeps the current step and stops when a recorded choice has no target', async () => {
  const value = story(spec('gate', [node('gate', '城门', [choice('broken', '坏选择', undefined)]), node('end', '终章')]));
  render(<InteractiveStoryPreview api={apiFor(playAt('gate', { path: ['broken'], steps: 1 }))} story={value} blocked={false} />);
  await start(value);
  expect(stepBody(1).getByText('节点 ID：gate')).toBeTruthy();
  expect(screen.getByText(/目标节点缺失：选择 broken 未记录 target/)).toBeTruthy();
  expect(screen.queryByRole('article', { name: '路径步骤 2' })).toBeNull();
});

it('keeps the raw target ID when it points at a node that does not exist', async () => {
  const value = story(spec('gate', [node('gate', '城门', [choice('lost', '丢失', 'nowhere')])]));
  render(<InteractiveStoryPreview api={apiFor(playAt('gate', { path: ['lost'], steps: 1 }))} story={value} blocked={false} />);
  await start(value);
  expect(screen.getByText(/目标节点不存在：选择 lost 指向 nowhere/)).toBeTruthy();
  expect(screen.queryByRole('article', { name: '路径步骤 2' })).toBeNull();
});

it('keeps the raw choice ID and shows an unknown label when the choice label is missing', async () => {
  const value = story(spec('gate', [node('gate', '城门', [choice('quiet', '', 'end')]), node('end', '终章')]));
  render(<InteractiveStoryPreview api={apiFor(playAt('end', { path: ['quiet'], steps: 1, status: 'ENDING' }))} story={value} blocked={false} />);
  await start(value);
  expect(stepBody(2).getByText('选择文案：未知选择文案')).toBeTruthy();
  expect(stepBody(2).getByText('Choice ID：quiet')).toBeTruthy();
});

it('shows legal repeated node visits as independent numbered steps', async () => {
  const value = story(spec('A', [
    node('A', '甲', [choice('toB', '去乙', 'B')]),
    node('B', '乙', [choice('toA', '回甲', 'A')]),
  ]));
  render(<InteractiveStoryPreview api={apiFor(playAt('A', { path: ['toB', 'toA'], steps: 2, status: 'PLAYING' }))} story={value} blocked={false} />);
  await start(value);
  expect(screen.getAllByRole('article', { name: /路径步骤/ })).toHaveLength(3);
  expect(stepBody(1).getByText(/步骤 1：甲/)).toBeTruthy();
  expect(stepBody(2).getByText(/步骤 2：乙/)).toBeTruthy();
  expect(stepBody(3).getByText(/步骤 3：甲/)).toBeTruthy();
  expect(stepBody(3).getByText('Choice ID：toA')).toBeTruthy();
});

it('never expands a static story cycle without a recorded path and bounds oversized records', async () => {
  const value = story(spec('A', [
    node('A', '甲', [choice('toB', '去乙', 'B')]),
    node('B', '乙', [choice('toA', '回甲', 'A')]),
  ], 2));
  const view = render(<InteractiveStoryPreview api={apiFor(playAt('A'))} story={value} blocked={false} />);
  expect(screen.getAllByRole('article', { name: /路径步骤/ })).toHaveLength(1);
  expect(screen.queryByRole('article', { name: '路径步骤 2' })).toBeNull();
  view.unmount();
  render(<InteractiveStoryPreview api={apiFor(playAt('A', { path: ['toB', 'toA', 'toB'], steps: 3 }))} story={value} blocked={false} />);
  await start(value);
  expect(screen.getAllByRole('article', { name: /路径步骤/ })).toHaveLength(3);
  expect(screen.getByText(/路径记录长度 3 超过步数上限 2/)).toBeTruthy();
});

it('distinguishes a normal ending and a waiting-for-choice path from parse errors', async () => {
  const ending = story(spec('gate', [node('gate', '城门', [choice('home', '回家', 'end')]), node('end', '终章', [], '到家')]));
  const view = render(<InteractiveStoryPreview api={apiFor(playAt('end', { path: ['home'], steps: 1, status: 'ENDING' }))} story={ending} blocked={false} />);
  await start(ending);
  expect(screen.getByText('路径已正常结束（故事结局）。')).toBeTruthy();
  expect(screen.queryByText(/无法继续解析/)).toBeNull();
  view.unmount();
  render(<InteractiveStoryPreview api={apiFor(playAt('gate'))} story={ending} blocked={false} />);
  await start(ending);
  expect(screen.getByText('等待选择：当前路径尚未记录选择。')).toBeTruthy();
  expect(screen.queryByText(/选择文案：/)).toBeNull();
  expect(screen.queryByRole('article', { name: '路径步骤 2' })).toBeNull();
});

it('reports a path record that disagrees with the reported current node and keeps parsed steps', async () => {
  const value = story(spec('gate', [node('gate', '城门', [choice('home', '回家', 'end')]), node('end', '终章')]));
  render(<InteractiveStoryPreview api={apiFor(playAt('other', { path: ['home'], steps: 1 }))} story={value} blocked={false} />);
  await start(value);
  expect(screen.getByText(/路径记录与当前故事定义不一致：按已记录选择与 choice.target 应到达节点 end，但播放记录当前节点为 other/)).toBeTruthy();
  expect(stepBody(1).getByText('节点 ID：gate')).toBeTruthy();
  expect(stepBody(2).getByText('节点 ID：end')).toBeTruthy();
});

it('keeps previously resolved steps when a later step cannot resolve', async () => {
  const value = story(spec('gate', [
    node('gate', '城门', [choice('home', '回家', 'end')]),
    node('end', '终章', [choice('oops', '错误', 'nowhere')])
  ]));
  render(<InteractiveStoryPreview api={apiFor(playAt('end', { path: ['home', 'oops'], steps: 2 }))} story={value} blocked={false} />);
  await start(value);
  expect(stepBody(1).getByText('节点 ID：gate')).toBeTruthy();
  expect(stepBody(2).getByText('节点 ID：end')).toBeTruthy();
  expect(screen.getByText(/目标节点不存在：选择 oops 指向 nowhere/)).toBeTruthy();
  expect(screen.queryByRole('article', { name: '路径步骤 3' })).toBeNull();
});

it('shows explicit entry-missing and empty-story states without inventing steps', () => {
  const missing = render(<InteractiveStoryPreview api={apiFor(playAt('gate'))} story={story(spec('', [node('gate', '城门')]))} blocked={false} />);
  expect(screen.getByText(/入口节点缺失/)).toBeTruthy();
  expect(screen.queryByRole('article', { name: '路径步骤 1' })).toBeNull();
  missing.unmount();
  render(<InteractiveStoryPreview api={apiFor(playAt('gate'))} story={story(spec('gate', []))} blocked={false} />);
  expect(screen.getByText('故事没有可解析的节点，无法展示步骤路径。')).toBeTruthy();
  expect(screen.queryByRole('article', { name: /路径步骤/ })).toBeNull();
});

it('derives the path without mutating the story, the play record or calling write APIs', async () => {
  const value = story(spec('gate', [node('gate', '城门', [choice('home', '回家', 'end')]), node('end', '终章', [], '到家')]));
  const result = playAt('end', { path: ['home'], steps: 1, status: 'ENDING' });
  deepFreeze(value); deepFreeze(result);
  const before = JSON.stringify({ value, result });
  const api = apiFor(result);
  render(<InteractiveStoryPreview api={api} story={value} blocked={false} />);
  expect(api.play).not.toHaveBeenCalled();
  await start(value);
  expect(api.play).toHaveBeenCalledTimes(1);
  expect(JSON.stringify({ value, result })).toBe(before);
  expect(screen.getAllByRole('article', { name: /路径步骤/ })).toHaveLength(2);
});

it('renders the same derived path on repeated renders without extra effects', () => {
  const value = story(spec('gate', [node('gate', '城门', [choice('home', '回家', 'end')]), node('end', '终章')]));
  const api = apiFor(playAt('gate'));
  const view = render(<InteractiveStoryPreview api={api} story={value} blocked={false} />);
  const first = document.body.innerHTML;
  view.rerender(<InteractiveStoryPreview api={api} story={value} blocked={false} />);
  expect(document.body.innerHTML).toBe(first);
  expect(api.play).not.toHaveBeenCalled();
});
