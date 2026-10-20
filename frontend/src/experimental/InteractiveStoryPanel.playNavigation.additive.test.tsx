// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { experimentalClient } from './api';
import { InteractiveStoryPanel } from './InteractiveStoryPanel';
import type { InteractiveStory, StoryCatalog, StoryPlay } from './interactiveStoryClient';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
const client = () => experimentalClient('n', { sessionToken: 'session', scope: { branchId: 'branch' } as any });
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
const analysis = { issues: [], warnings: [], endings: [{ node_id: 'end', ending: '回家', choices: ['home'] }], states_checked: 2, analysis_complete: true, state_limit_reached: false, step_limit_reached: false, max_steps: 4, can_review: true };
function makeStory(status: InteractiveStory['status'] = 'APPROVED'): InteractiveStory {
  return { id: 'story', version: 1, status, stale: false, content_withheld: false, analysis, spec: { title: '合成互动故事', graph_id: 'graph', graph_version: 1, entry_node_id: 'gate', max_steps: 4,
    variables: [{ name: 'trusted', type: 'bool', initial: true, minimum: 0, maximum: 100 }], graph_record_ids: [], nodes: [
      { node_id: 'gate', node_version: 1, title: '城门', dialogue: '原对白🙂é', character_id: 'alice', background_asset_id: null, music_asset_id: null, ending: '', choices: [{ id: 'home', label: '回家', target: 'end', condition: 'trusted', assignments: {} }] },
      { node_id: 'end', node_version: 1, title: '终章', dialogue: '抵达', character_id: null, background_asset_id: null, music_asset_id: null, ending: '回家', choices: [] },
    ] } };
}
const catalog: StoryCatalog = { graphs: [{ id: 'graph', version: 1, title: '原规划图', truncated: false, nodes: makeStory().spec!.nodes }], characters: [{ id: 'alice', name: 'Alice' }], assets: [], graph_records: [], target_runtime: 'NOT_RUN' };
function backend(row = makeStory()) {
  return vi.fn(async (url: string, init: RequestInit) => {
    if (url.endsWith('/catalog')) return reply(catalog);
    if (init.method === 'GET') return reply(url.endsWith('/story') ? row : { items: [row], truncated: false });
    const body = JSON.parse(String(init.body));
    if (url.endsWith('/preview')) {
      const node = row.spec!.nodes[body.choices.length ? 1 : 0];
      const play: StoryPlay = { node, character_name: body.choices.length ? undefined : 'Alice', choices: body.choices.length ? [] : [{ id: 'home', label: '回家', enabled: true }], variables: { trusted: true }, steps: body.choices.length, max_steps: 4, path: body.choices, status: body.choices.length ? 'ENDING' : 'PLAYING' };
      return reply(play);
    }
    return reply(row);
  });
}

it('locates the editor at the played ending node without editing or saving anything', async () => {
  const fetch = backend(); vi.stubGlobal('fetch', fetch); render(<InteractiveStoryPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: /合成互动故事 · v/ }));
  fireEvent.click(screen.getByRole('button', { name: '从开头试玩' }));
  fireEvent.click(await screen.findByRole('button', { name: /^回家$/ }));
  await screen.findByText('结局：回家');
  expect((screen.getByRole('button', { name: '保存互动草稿' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '定位回编辑节点 终章' }));
  expect((screen.getByLabelText('当前编辑节点') as HTMLSelectElement).value).toBe('1');
  expect((screen.getByLabelText('互动节点标题') as HTMLInputElement).value).toBe('终章');
  // Locating from playback only switches the editor view: no save/review request is sent.
  expect(fetch.mock.calls.some(([, init]) => init.method === 'PUT')).toBe(false);
  expect(fetch.mock.calls.some(([url, init]) => init.method === 'POST' && !url.endsWith('/preview'))).toBe(false);
  expect(screen.queryByText('互动草稿已保存，需要重新审核。')).toBeNull();
});
