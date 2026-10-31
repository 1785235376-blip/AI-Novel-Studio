// @vitest-environment jsdom
// Real component integration with HTTP-shaped fetch fixtures; no real provider is called.
import {act, cleanup, fireEvent, render, screen, waitFor, within} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {setCollaborationContext} from '../../api';
import {useStudio} from '../../store';
import {canvasStorageKey} from '../canvas/RebuildCanvas';
import {ImageRebuild} from './ImageRebuild';

const json = (value: unknown) => new Response(JSON.stringify(value), {headers: {'Content-Type': 'application/json'}});
const fixtureProvider = {provider_id: 'fixture-local', display_name: 'Fixture local service', default_model: 'fixture-model', local: true, configured: true, registered: true, reachable: true};
function seed(novelId: string, prompt: string) {
  localStorage.setItem(canvasStorageKey('image', novelId), JSON.stringify({nodes: [{id: 'node-a', t: 'image_generate', x: 0, y: 0, title: '标题绝不是实际提示词', prompt}], edges: []}));
}
function selectImageNode() {
  const node = document.querySelector('[data-node-id="node-a"]')!;
  fireEvent.pointerDown(node, {button: 0, pointerId: 1, clientX: 40, clientY: 40});
  fireEvent.pointerUp(node, {button: 0, pointerId: 1, clientX: 40, clientY: 40});
}
beforeEach(() => {
  localStorage.clear();
  useStudio.setState({sessionToken: '', novelId: '', actor: undefined, scope: undefined});
  setCollaborationContext({sessionToken: ''});
  vi.stubGlobal('PointerEvent', MouseEvent);
});
afterEach(() => {cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); setCollaborationContext({sessionToken: ''});});

describe('ImageRebuild canvas-to-queue wiring', () => {
  it('uses the explicitly selected node prompt in the real queue component and displays only the returned fixture Job ID', async () => {
    seed('novel-a', '最初节点提示词');
    let jobs: unknown[] = [];
    const fetcher = vi.fn(async (url: string, init: RequestInit = {}) => {
      if (url === '/api/asset-providers') return json({items: [fixtureProvider]});
      if (url === '/api/novels/novel-a/image-jobs') {
        if (init.method === 'POST') {
          const body = JSON.parse(String(init.body));
          jobs = [{id: 'fixture-persisted-node-job', provider_id: body.provider_id, model_id: body.model_id, prompt: body.prompt, status: 'QUEUED', approval_status: 'PENDING', attempt: 0}];
          return json(jobs[0]);
        }
        return json({items: jobs});
      }
      if (url === '/api/novels/novel-a/image-generations' || url === '/api/novels/novel-a/visual-references') return json({items: []});
      throw new Error(`Unexpected software-fixture request ${init.method || 'GET'} ${url}`);
    });
    vi.stubGlobal('fetch', fetcher);
    render(<ImageRebuild novelId="novel-a" view="dual" shellMode="pro" onViewChange={() => {}} />);
    expect(screen.queryByRole('complementary', {name: '画布图片任务'})).toBeNull();
    selectImageNode();
    fireEvent.change(screen.getByLabelText('本次提示词'), {target: {value: '  本次确认的灯塔画面  '}});
    expect(fetcher.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(0);
    fireEvent.click(screen.getByRole('button', {name: '为此节点准备图片任务'}));
    const drawer = screen.getByRole('complementary', {name: '画布图片任务'});
    expect((within(drawer).getByLabelText('本次节点提示词') as HTMLTextAreaElement).value).toBe('本次确认的灯塔画面');
    await within(drawer).findByRole('option', {name: 'Fixture local service'});
    expect(fetcher.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(0);
    fireEvent.change(within(drawer).getByLabelText('画布任务图片服务'), {target: {value: 'fixture-local'}});
    fireEvent.click(within(drawer).getByRole('button', {name: '保存到生成队列'}));
    await within(drawer).findByText('任务 ID：fixture-persisted-node-job');
    const posts = fetcher.mock.calls.filter(([, init]) => init?.method === 'POST');
    expect(posts).toHaveLength(1);
    expect(posts[0][0]).toBe('/api/novels/novel-a/image-jobs');
    expect(JSON.parse(String(posts[0][1]?.body))).toMatchObject({novel_id: 'novel-a', provider_id: 'fixture-local', model_id: 'fixture-model', prompt: '本次确认的灯塔画面'});
    expect(fetcher.mock.calls.some(([url]) => /\/(?:execute|accept)(?:\?|$)/.test(String(url)))).toBe(false);
    fireEvent.click(within(drawer).getByRole('button', {name: '关闭节点任务参数'}));
    expect(screen.queryByRole('complementary', {name: '画布图片任务'})).toBeNull();
    expect((screen.getByLabelText('本次提示词') as HTMLTextAreaElement).value).toBe('  本次确认的灯塔画面  ');
  });

  it('closes the old drawer on novel change and discards its late provider and private Job responses', async () => {
    seed('novel-a', 'A 的原节点提示词'); seed('novel-b', 'B 的原节点提示词');
    let providerReads = 0, aJobReads = 0;
    let finishProvider!: (value: Response) => void, finishJobs!: (value: Response) => void;
    const fetcher = vi.fn((url: string, init: RequestInit = {}): Promise<Response> => {
      if (url === '/api/asset-providers') return ++providerReads === 2
        ? new Promise(resolve => {finishProvider = resolve;})
        : Promise.resolve(json({items: [fixtureProvider]}));
      if (url === '/api/novels/novel-a/image-jobs') return ++aJobReads === 2
        ? new Promise(resolve => {finishJobs = resolve;})
        : Promise.resolve(json({items: []}));
      if (/^\/api\/novels\/novel-[ab]\/(?:image-generations|visual-references|image-jobs)$/.test(url)) return Promise.resolve(json({items: []}));
      throw new Error(`Unexpected software-fixture request ${init.method || 'GET'} ${url}`);
    });
    vi.stubGlobal('fetch', fetcher);
    const view = render(<ImageRebuild novelId="novel-a" view="dual" shellMode="pro" onViewChange={() => {}} />);
    selectImageNode();
    fireEvent.click(screen.getByRole('button', {name: '为此节点准备图片任务'}));
    expect(screen.getByRole('complementary', {name: '画布图片任务'})).toBeTruthy();
    await waitFor(() => expect(finishProvider).toBeTypeOf('function'));
    await waitFor(() => expect(finishJobs).toBeTypeOf('function'));
    view.rerender(<ImageRebuild novelId="novel-b" view="dual" shellMode="pro" onViewChange={() => {}} />);
    expect(screen.queryByRole('complementary', {name: '画布图片任务'})).toBeNull();
    await act(async () => {
      finishProvider(json({items: [{...fixtureProvider, display_name: 'Retired A private service'}]}));
      finishJobs(json({items: [{id: 'retired-a-job', prompt: 'Retired A private result', status: 'QUEUED'}]}));
    });
    expect(screen.queryByRole('complementary', {name: '画布图片任务'})).toBeNull();
    expect(screen.queryByText(/retired-a-job|Retired A private result|Retired A private service/)).toBeNull();
    selectImageNode();
    expect((screen.getByLabelText('本次提示词') as HTMLTextAreaElement).value).toBe('B 的原节点提示词');
    expect(fetcher.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(0);
  });
});
