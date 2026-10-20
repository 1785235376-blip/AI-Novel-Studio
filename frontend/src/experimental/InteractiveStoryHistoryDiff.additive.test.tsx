// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { InteractiveStoryHistory } from './InteractiveStoryHistory';
import type { interactiveStoryClient, InteractiveStory, StoryRevision, StorySpec } from './interactiveStoryClient';
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const currentSpec: StorySpec = { title: '合成互动故事', graph_id: 'graph', graph_version: 1, entry_node_id: 'gate', max_steps: 4, graph_record_ids: [],
  variables: [{ name: 'trusted', type: 'bool', initial: true, minimum: 0, maximum: 100 }],
  nodes: [
    { node_id: 'gate', node_version: 1, title: '城门', dialogue: '新对白', character_id: null, background_asset_id: null, music_asset_id: null, ending: '',
      choices: [{ id: 'home', label: '回城', target: 'end', condition: 'trusted', assignments: { trusted: true } }] },
    { node_id: 'end', node_version: 1, title: '终章', dialogue: '抵达', character_id: null, background_asset_id: null, music_asset_id: null, ending: '回家', choices: [] },
    { node_id: 'extra', node_version: 1, title: '后日谈', dialogue: '新场景', character_id: null, background_asset_id: null, music_asset_id: null, ending: '新的结局', choices: [] },
  ] };

function historySpec(): StorySpec {
  return { ...currentSpec, variables: [{ name: 'trusted', type: 'bool', initial: false, minimum: 0, maximum: 100 }, { name: 'score', type: 'int', initial: 0, minimum: 0, maximum: 10 }],
    nodes: [
      { node_id: 'gate', node_version: 1, title: '城门', dialogue: '旧对白', character_id: null, background_asset_id: null, music_asset_id: null, ending: '',
        choices: [{ id: 'home', label: '回家', target: 'end', condition: '', assignments: {} }] },
      { node_id: 'end', node_version: 1, title: '终章', dialogue: '抵达', character_id: null, background_asset_id: null, music_asset_id: null, ending: '回家', choices: [] },
    ] };
}
const revision = (version = 1, spec = historySpec()): StoryRevision => ({ version, status: 'APPROVED', spec, preview_digest: 'a'.repeat(64) });
const story: InteractiveStory = { id: 'story', version: 3, status: 'DRAFT', stale: false, content_withheld: false, spec: currentSpec };
const perform = vi.fn(async (fn: () => Promise<InteractiveStory>) => { await fn(); });
const client = (history: ReturnType<typeof vi.fn>) => ({ history } as unknown as ReturnType<typeof interactiveStoryClient>);

it('diffs a history revision against the current saved revision with content-meaningful rows', async () => {
  const history = vi.fn(async () => ({ items: [revision(1), revision(2, currentSpec)], truncated: false }));
  render(<InteractiveStoryHistory api={client(history)} story={story} blocked={false} perform={perform} />);
  fireEvent.click(screen.getByRole('button', { name: '读取互动改编历史' }));
  fireEvent.click(await screen.findByRole('button', { name: '比较互动 v1 与当前' }));
  const region = screen.getByLabelText('历史 v1 与当前版本差异');
  expect(region.textContent).toContain('共 7 处内容差异');
  expect(region.textContent).toContain('故事级 0 · 节点 2 · 选择 3 · 变量 2');
  expect(region.textContent).toContain('节点「城门」（gate） · 对白：历史「旧对白」→ 当前「新对白」');
  expect(region.textContent).toContain('新增节点「后日谈」（extra）');
  expect(region.textContent).toContain('选择「回城」（home） · 选项文案：历史「回家」→ 当前「回城」');
  expect(region.textContent).toContain('变量「score」');
  expect(screen.getByText(/历史比较是已保存版本之间的纯内容差异/)).toBeTruthy();
  expect(screen.getByRole('button', { name: '恢复互动 v1 为待审草稿' })).toBeTruthy();
  expect(history).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole('button', { name: '关闭历史比较' }));
  expect(screen.queryByLabelText('历史 v1 与当前版本差异')).toBeNull();
});

it('reports an identical history revision without inventing changes', async () => {
  const history = vi.fn(async () => ({ items: [revision(2, currentSpec)], truncated: false }));
  render(<InteractiveStoryHistory api={client(history)} story={story} blocked={false} perform={perform} />);
  fireEvent.click(screen.getByRole('button', { name: '读取互动改编历史' }));
  fireEvent.click(await screen.findByRole('button', { name: '比较互动 v2 与当前' }));
  expect(screen.getByText(/内容与当前已保存版本一致；可能只有审核状态或版本号不同/)).toBeTruthy();
  expect(screen.queryByRole('list')).toBeNull();
});

it('restores through the exact original receipt without auto-reviewing', async () => {
  const history = vi.fn(async () => ({ items: [revision(1)], truncated: false }));
  const restoreRevision = vi.fn(async () => ({ id: 'story', version: 4, status: 'DRAFT' } as InteractiveStory));
  const api = { history, restoreRevision } as unknown as ReturnType<typeof interactiveStoryClient>;
  render(<InteractiveStoryHistory api={api} story={story} blocked={false} perform={perform} />);
  fireEvent.click(screen.getByRole('button', { name: '读取互动改编历史' }));
  fireEvent.click(await screen.findByRole('button', { name: '恢复互动 v1 为待审草稿' }));
  await waitFor(() => expect(restoreRevision).toHaveBeenCalledTimes(1));
  expect(restoreRevision).toHaveBeenCalledWith(story, revision(1));
  expect(history).toHaveBeenCalledTimes(1);
});

it('does not compare without a current saved spec and stays blocked for unsaved input', async () => {
  const history = vi.fn(async () => ({ items: [revision(1)], truncated: false }));
  const view = render(<InteractiveStoryHistory api={client(history)} story={{ ...story, spec: undefined } as InteractiveStory} blocked={false} perform={perform} />);
  fireEvent.click(screen.getByRole('button', { name: '读取互动改编历史' }));
  expect(((await screen.findByRole('button', { name: '比较互动 v1 与当前' })) as HTMLButtonElement).disabled).toBe(true);
  view.rerender(<InteractiveStoryHistory api={client(history)} story={story} blocked={true} perform={perform} />);
  expect((screen.getByRole('button', { name: '读取互动改编历史' }) as HTMLButtonElement).disabled).toBe(true);
});

it('dispatches one history read for repeated clicks and keeps late data out of a newer revision', async () => {
  let finish: (value: { items: StoryRevision[]; truncated: boolean }) => void = () => {};
  const history = vi.fn(() => new Promise<{ items: StoryRevision[]; truncated: boolean }>(resolve => { finish = resolve; }));
  const view = render(<InteractiveStoryHistory api={client(history)} story={story} blocked={false} perform={perform} />);
  const button = screen.getByRole('button', { name: '读取互动改编历史' });
  fireEvent.click(button); fireEvent.click(button);
  expect(history).toHaveBeenCalledTimes(1);
  view.rerender(<InteractiveStoryHistory api={client(history)} story={{ ...story, version: 4 }} blocked={false} perform={perform} />);
  await act(async () => finish({ items: [revision(1)], truncated: false }));
  expect(screen.queryByRole('button', { name: '比较互动 v1 与当前' })).toBeNull();
});

it('shows an explicit history read failure without stale rows', async () => {
  const history = vi.fn(async () => { throw new ApiError({ status: 403, code: 'FORBIDDEN', message: '当前身份没有此操作权限。' }); });
  render(<InteractiveStoryHistory api={client(history)} story={story} blocked={false} perform={perform} />);
  fireEvent.click(screen.getByRole('button', { name: '读取互动改编历史' }));
  await screen.findByText(/FORBIDDEN/);
  expect(screen.queryByRole('button', { name: /比较互动 v/ })).toBeNull();
});
