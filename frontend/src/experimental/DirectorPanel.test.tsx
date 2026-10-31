// @vitest-environment jsdom
import { StrictMode } from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { DirectorPanel } from './DirectorPanel';
import { experimentalClient } from './api';
import { newGrammar } from './directorClient';
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const source = { id: 'screenplay', title: 'Synthetic harbor', edit_version: 4, shot_status: 'APPROVED', checks: [], shots: [{ id: 'shot', number: 11, scene_id: 'scene', shot_size: 'MEDIUM', camera_angle: 'EYE_LEVEL', camera_motion: 'STATIC', duration_seconds: 5 }] };
const plan = { id: 'plan', title: 'Harbor close', version: 1, status: 'DRAFT', stale: false, screenplay_id: 'screenplay', screenplay_version: 4, shots: [{ shot_id: 'shot', shot_size: 'CLOSE', camera_angle: 'EYE_LEVEL', camera_motion: 'STATIC', duration_seconds: 5, director: newGrammar() }], checks: [{ state: 'INSUFFICIENT_EVIDENCE', kind: 'AXIS', message: '信息不足：没有几何。' }] };
const comparison = { screenplay_id: 'screenplay', screenplay_version: 4, original: source.shots, candidates: [plan], comparison_digest: 'x', application_digests: { plan: 'ticket' } };
const client = (nid = 'novel') => experimentalClient(nid, { sessionToken: 'trusted' });
function fetcher(mutation?: (url: string, init: RequestInit) => Response | Promise<Response>) {
  return vi.fn(async (url: string, init: RequestInit) => {
    if (init.method !== 'GET') return mutation ? mutation(url, init) : reply(plan, 201);
    return reply(url.endsWith('/catalog') ? { screenplays: [source], characters: [] } : { items: [plan] });
  });
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('mount is read-only and manual candidate save keeps original source versions', async () => {
  const fetch = fetcher(); vi.stubGlobal('fetch', fetch);
  render(<StrictMode><DirectorPanel client={client()} /></StrictMode>);
  await screen.findByRole('option', { name: /Synthetic harbor/ });
  expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
  fireEvent.change(screen.getByLabelText('导演方案来源剧本'), { target: { value: 'screenplay' } });
  fireEvent.change(screen.getByLabelText('候选镜头方案名称'), { target: { value: '新方案' } });
  fireEvent.change(screen.getByLabelText('镜头 1 场景目的'), { target: { value: '表现等待' } });
  fireEvent.click(screen.getByRole('button', { name: '保存候选镜头草稿' }));
  await waitFor(() => expect(fetch.mock.calls.filter(([, init]) => init.method === 'POST')).toHaveLength(1));
  const [, init] = fetch.mock.calls.find(([, value]) => value.method === 'POST')!;
  expect(JSON.parse(String(init.body))).toMatchObject({ screenplay_id: 'screenplay', expected_screenplay_version: 4, title: '新方案', shots: [{ shot_id: 'shot', director: { scene_purpose: '表现等待' } }] });
  expect(fetch.mock.calls.some(([url]) => /generate|execute|approve/.test(url))).toBe(false);
});

it('requires original comparison and impact acknowledgement, prevents double apply', async () => {
  let finish: (value: Response) => void = () => {};
  const fetch = fetcher(url => url.endsWith('/compare') ? reply(comparison) : new Promise(resolve => { finish = resolve; })); vi.stubGlobal('fetch', fetch);
  render(<DirectorPanel client={client()} />);
  fireEvent.click(await screen.findByLabelText('对比方案 Harbor close'));
  fireEvent.click(screen.getByRole('button', { name: '读取原镜头与候选对比' }));
  const button = await screen.findByRole('button', { name: '采用方案 Harbor close 为镜头草稿' }) as HTMLButtonElement;
  expect(button.disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('已核对原镜头、候选字段与旧产物失效影响'));
  fireEvent.click(button); fireEvent.click(button);
  await waitFor(() => expect(fetch.mock.calls.filter(([url]) => url.endsWith('/apply'))).toHaveLength(1));
  expect(JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/apply'))![1].body))).toEqual({ expected_version: 1, comparison_digest: 'ticket' });
  finish(reply({ edit_version: 5 })); await screen.findByText(/已应用为原剧本的新镜头草稿版本/);
});

it('preserves local fields on 409 and removes old private data on scope replacement', async () => {
  const fetch = fetcher(() => reply({ detail: { code: 'DIRECTOR_SCREENPLAY_VERSION_CONFLICT' } }, 409)); vi.stubGlobal('fetch', fetch);
  const view = render(<DirectorPanel client={client()} />);
  await screen.findByRole('option', { name: /Synthetic harbor/ }); fireEvent.change(screen.getByLabelText('导演方案来源剧本'), { target: { value: 'screenplay' } });
  fireEvent.change(screen.getByLabelText('候选镜头方案名称'), { target: { value: '保留的输入' } });
  fireEvent.click(screen.getByRole('button', { name: '保存候选镜头草稿' })); await screen.findByText(/DIRECTOR_SCREENPLAY_VERSION_CONFLICT/);
  expect((screen.getByLabelText('候选镜头方案名称') as HTMLInputElement).value).toBe('保留的输入');
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(() => {})));
  view.rerender(<DirectorPanel client={client('other')} />);
  expect(screen.queryByDisplayValue('保留的输入')).toBeNull(); expect(screen.queryByText('Harbor close')).toBeNull();
});
