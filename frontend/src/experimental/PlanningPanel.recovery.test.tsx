// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { experimentalClient } from './api';
import { PlanningPanel } from './PlanningPanel';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
async function click(name: string) {
  await waitFor(() => expect((screen.getByRole('button', { name }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole('button', { name }));
}
describe('planning same-node version recovery', () => {
  it.each(['external change', 'proposal approval'])('retains local edits after %s and only rebases through an explicit action', async cause => {
    let node = { id: 'node', version: 1, title: 'Server title', status: 'DRAFT', level: 'PROJECT', position: 0, fields: { goal: 'Original goal', conflict: '', turning_point: '', climax: '', ending_intent: '', character_objectives: {}, beats: {} }, links: { chapter_ids: [], character_ids: [], location_ids: [], world_rule_ids: [], story_route_ids: [] } };
    let proposal = { id: 'proposal', node_id: 'node', version: 1, title: 'Approved alternative', status: 'REVIEW', fields: { goal: 'Approved server goal' }, stale: false };
    const graph = () => ({ id: 'graph', version: 1, title: 'Graph', root_node_id: 'node', nodes: [node] });
    const advance = () => { node = { ...node, version: 2, title: 'Changed server title', fields: { ...node.fields, goal: 'New server goal' } }; };
    const fetch = vi.fn(async (url: string, request: RequestInit) => {
      let value: unknown = { items: [] };
      if (url.endsWith('/planning/graphs')) value = { items: [{ id: 'graph', title: 'Graph' }] };
      else if (url.endsWith('/planning/graphs/graph')) value = graph();
      else if (url.endsWith('/planning/proposals')) value = { items: [proposal] };
      else if (url.endsWith('/planning/proposals/proposal/approve')) { advance(); proposal = { ...proposal, version: 2, status: 'APPROVED' }; value = proposal; }
      else if (url.endsWith('/planning/nodes/node') && request.method === 'PUT') {
        const update = JSON.parse(request.body as string);
        if (update.expected_version !== node.version) return new Response(JSON.stringify({ detail: { code: 'VERSION_CONFLICT' } }), { status: 409 });
        node = { ...node, ...update, version: node.version + 1 }; value = node;
      }
      return new Response(JSON.stringify(value), { status: 200 });
    });
    vi.stubGlobal('fetch', fetch);
    render(<PlanningPanel client={experimentalClient('novel', { sessionToken: '' })} />);
    await screen.findByRole('heading', { name: '编辑 PROJECT' });
    // Visible editor controls are already hydrated, before the first user edit.
    expect((screen.getByLabelText('节点标题') as HTMLInputElement).value).toBe('Server title');
    expect((screen.getByLabelText('目标', { exact: true }) as HTMLTextAreaElement).value).toBe('Original goal');
    fireEvent.change(screen.getByLabelText('节点标题'), { target: { value: 'Retained local title' } });
    fireEvent.change(screen.getByLabelText('目标', { exact: true }), { target: { value: 'Retained local goal' } });
    fireEvent.change(screen.getByLabelText('自定义节拍（JSON）'), { target: { value: '{"local":"Keep this beat"}' } });
    if (cause === 'proposal approval') await click('批准规划');
    else { advance(); await click('刷新实验记录'); }
    await screen.findByRole('region', { name: '规划节点版本恢复' });
    await click('刷新实验记录');
    expect((screen.getByLabelText('节点标题') as HTMLInputElement).value).toBe('Retained local title');
    expect((screen.getByLabelText('目标', { exact: true }) as HTMLTextAreaElement).value).toBe('Retained local goal');
    expect((screen.getByRole('button', { name: '保存节点' }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole('button', { name: '保存为待审方案' }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByRole('region', { name: '规划节点版本恢复' }).textContent).toContain('New server goal');
    const writesBefore = fetch.mock.calls.filter(([, options]) => options.method !== 'GET').length;
    await click('保留草稿并更新保存基线');
    await waitFor(() => expect(screen.queryByRole('region', { name: '规划节点版本恢复' })).toBeNull());
    expect(fetch.mock.calls.filter(([, options]) => options.method !== 'GET')).toHaveLength(writesBefore);
    expect((screen.getByLabelText('自定义节拍（JSON）') as HTMLTextAreaElement).value).toBe('{"local":"Keep this beat"}');
    await click('保存节点'); await screen.findByText('节点已保存');
    const saved = fetch.mock.calls.find(([, options]) => options.method === 'PUT')!;
    expect(JSON.parse(saved[1].body as string)).toMatchObject({ expected_version: 2, title: 'Retained local title', fields: { goal: 'Retained local goal', beats: { local: 'Keep this beat' } } });
    expect(screen.queryByRole('alert')).toBeNull();
  });
});
