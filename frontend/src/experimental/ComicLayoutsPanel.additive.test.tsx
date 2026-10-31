// @vitest-environment jsdom
// Extracted additions and migrated variants; protected baseline suite stays byte-identical.
// Migrated variants preserve newer assertions and are not counted as unique new capabilities.

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ComicLayoutsPanel } from './ComicLayoutsPanel';
import { experimentalClient } from './api';
import { comicPreset } from './comicLayoutsClient';
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const source = { id: 'screenplay', title: 'Synthetic test comic', edit_version: 4, shot_status: 'APPROVED', checks: [], shots: [{ id: 'shot', number: 1, scene_id: 'scene', shot_size: 'MEDIUM', camera_angle: 'EYE_LEVEL', camera_motion: 'STATIC', duration_seconds: 5 }] };
const preset = { width: 800, height: 1120, safe_area: 24, segment_height: 1120 };
const document = comicPreset(source, 'PAGE', preset);
const record = { id: 'layout', version: 1, status: 'DRAFT', stale: false, document, history_versions: [] };
const asset = { id: 'asset', filename: 'SYNTHETIC-TEST-ASSET.png', version: 1, approved: false, manual_review_available: true };
const catalog = { screenplays: [source], characters: [{ id: 'alice', name: 'Alice' }], assets: [asset], presets: { PAGE: preset, WEBTOON: { ...preset, height: 2400, segment_height: 1200 } }, renderer: { available: true }, font: { available: true } };
const client = (nid = 'novel') => experimentalClient(nid, { sessionToken: 'trusted' });
function fetcher(mutation?: (url: string, init: RequestInit) => Response | Promise<Response>, sourceCatalog = catalog) {
  return vi.fn(async (url: string, init: RequestInit) => {
    if (init.method !== 'GET') return mutation ? mutation(url, init) : reply(record, 201);
    if (/segments\/|images\//.test(url)) return new Response(new Blob(['TEST PNG BYTES'], { type: 'image/png' }));
    return reply(url.endsWith('/catalog') ? sourceCatalog : { items: [record] });
  });
}
beforeEach(() => { URL.createObjectURL = vi.fn(() => 'blob:synthetic-test'); URL.revokeObjectURL = vi.fn(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('explicit arrangement preview applies one undoable edit and saves only through original owner', async () => {
  const fetch = fetcher(); vi.stubGlobal('fetch', fetch); render(<ComicLayoutsPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: /打开布局/ }));
  fireEvent.change(screen.getByLabelText('格框 1 横坐标'), { target: { value: '48' } });
  fireEvent.click(screen.getByRole('button', { name: '预览纵向排列' }));
  expect((screen.getByLabelText('格框 1 横坐标') as HTMLInputElement).value).toBe('48');
  expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '应用纵向排列到草稿' }));
  expect((screen.getByLabelText('格框 1 横坐标') as HTMLInputElement).value).toBe('24');
  fireEvent.click(screen.getByRole('button', { name: '撤销本地排版' }));
  expect((screen.getByLabelText('格框 1 横坐标') as HTMLInputElement).value).toBe('48');
  fireEvent.click(screen.getByRole('button', { name: '重做本地排版' }));
  fireEvent.click(screen.getByRole('button', { name: '保存漫画布局草稿' }));
  await waitFor(() => expect(fetch.mock.calls.some(([, init]) => init.method === 'PUT')).toBe(true));
  expect(JSON.parse(String(fetch.mock.calls.find(([, init]) => init.method === 'PUT')![1].body))).toMatchObject({ expected_version: 1, panels: [{ x: 24, expected_asset_version: null }] });
  expect(fetch.mock.calls.some(([url]) => /generate|execute|approve|export/.test(url))).toBe(false);
});

it('cancel, edits, refresh and client replacement discard arrangement consent', async () => {
  const fetch = fetcher(); vi.stubGlobal('fetch', fetch); const view = render(<ComicLayoutsPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: /打开布局/ }));
  fireEvent.change(screen.getByLabelText('格框 1 横坐标'), { target: { value: '48' } });
  const preview = () => fireEvent.click(screen.getByRole('button', { name: '预览纵向排列' }));
  preview(); fireEvent.click(screen.getByRole('button', { name: '取消排列预览' })); expect(screen.queryByRole('button', { name: '应用纵向排列到草稿' })).toBeNull();
  preview(); fireEvent.change(screen.getByLabelText('漫画布局名称'), { target: { value: 'New title' } }); expect(screen.queryByRole('button', { name: '应用纵向排列到草稿' })).toBeNull();
  preview(); expect((screen.getByRole('button', { name: '刷新漫画来源与记录' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '放弃当前页面修改' })); preview(); fireEvent.click(screen.getByRole('button', { name: '刷新漫画来源与记录' })); expect(screen.queryByRole('button', { name: '应用纵向排列到草稿' })).toBeNull();
  await screen.findByRole('button', { name: '预览纵向排列' }); preview(); view.rerender(<ComicLayoutsPanel client={client('other')} />); expect(screen.queryByRole('button', { name: '应用纵向排列到草稿' })).toBeNull();
});

it('retained arrangement apply is fenced after cancellation, edits and repeat invocation', async () => {
  const fetch = fetcher(); vi.stubGlobal('fetch', fetch); render(<ComicLayoutsPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: /打开布局/ }));
  fireEvent.change(screen.getByLabelText('格框 1 横坐标'), { target: { value: '48' } });
  const capture = () => {
    fireEvent.click(screen.getByRole('button', { name: '预览纵向排列' }));
    const button = screen.getByRole('button', { name: '应用纵向排列到草稿' });
    const key = Object.keys(button).find(k => k.startsWith('__reactProps'))!;
    return (button as unknown as Record<string, { onClick: () => void }>)[key].onClick;
  };
  const cancelled = capture(); fireEvent.click(screen.getByRole('button', { name: '取消排列预览' })); cancelled();
  expect((screen.getByLabelText('格框 1 横坐标') as HTMLInputElement).value).toBe('48');
  const edited = capture(); fireEvent.change(screen.getByLabelText('格框 1 横坐标'), { target: { value: '56' } }); edited();
  expect((screen.getByLabelText('格框 1 横坐标') as HTMLInputElement).value).toBe('56');
  const repeated = capture(); fireEvent.click(screen.getByRole('button', { name: '应用纵向排列到草稿' })); repeated();
  fireEvent.click(screen.getByRole('button', { name: '撤销本地排版' }));
  expect((screen.getByLabelText('格框 1 横坐标') as HTMLInputElement).value).toBe('56');
  expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
});

it.each([409, 500])('pending and failed save %s cannot reuse arrangement consent', async status => {
  let finish: (value: Response) => void = () => {};
  const fetch = fetcher(() => new Promise(resolve => { finish = resolve; })); vi.stubGlobal('fetch', fetch);
  render(<ComicLayoutsPanel client={client()} />); fireEvent.click(await screen.findByRole('button', { name: /打开布局/ }));
  fireEvent.change(screen.getByLabelText('格框 1 横坐标'), { target: { value: '48' } });
  fireEvent.click(screen.getByRole('button', { name: '预览纵向排列' }));
  const button = screen.getByRole('button', { name: '应用纵向排列到草稿' });
  const key = Object.keys(button).find(k => k.startsWith('__reactProps'))!;
  const retained = (button as unknown as Record<string, { onClick: () => void }>)[key].onClick;
  fireEvent.click(screen.getByRole('button', { name: '保存漫画布局草稿' })); retained();
  expect((screen.getByLabelText('格框 1 横坐标') as HTMLInputElement).value).toBe('48');
  finish(reply({ detail: { code: status === 409 ? 'EXPERIMENTAL_VERSION_CONFLICT' : 'UNKNOWN' } }, status));
  await screen.findByText(status === 409 ? /EXPERIMENTAL_VERSION_CONFLICT/ : /UNKNOWN/); retained();
  expect((screen.getByLabelText('格框 1 横坐标') as HTMLInputElement).value).toBe('48');
  expect(screen.queryByRole('button', { name: '应用纵向排列到草稿' })).toBeNull();
  expect(fetch.mock.calls.filter(([, init]) => init.method !== 'GET')).toHaveLength(1);
});

it('retained apply cannot cross record, source or owner ABA', async () => {
  const other = { ...record, id: 'other-layout', document: { ...document, title: 'Second layout' } };
  const fetch = vi.fn(async (url: string) => reply(url.endsWith('/catalog') ? catalog : { items: [record, other] })); vi.stubGlobal('fetch', fetch);
  const owner = client(), view = render(<ComicLayoutsPanel client={owner} />);
  const open = async () => fireEvent.click(await screen.findByRole('button', { name: `打开布局 ${document.title}` }));
  const capture = () => {
    fireEvent.change(screen.getByLabelText('格框 1 横坐标'), { target: { value: '48' } });
    fireEvent.click(screen.getByRole('button', { name: '预览纵向排列' }));
    const button = screen.getByRole('button', { name: '应用纵向排列到草稿' });
    const key = Object.keys(button).find(k => k.startsWith('__reactProps'))!;
    return (button as unknown as Record<string, { onClick: () => void }>)[key].onClick;
  };
  await open(); const oldRecord = capture(); fireEvent.click(screen.getByRole('button', { name: '打开布局 Second layout' })); await open(); fireEvent.change(screen.getByLabelText('格框 1 横坐标'), { target: { value: '72' } }); oldRecord();
  expect((screen.getByLabelText('格框 1 横坐标') as HTMLInputElement).value).toBe('72');
  const oldSource = capture(); fireEvent.change(screen.getByLabelText('漫画来源剧本'), { target: { value: '' } }); fireEvent.change(screen.getByLabelText('漫画来源剧本'), { target: { value: 'screenplay' } }); fireEvent.change(screen.getByLabelText('格框 1 横坐标'), { target: { value: '72' } }); oldSource();
  expect((screen.getByLabelText('格框 1 横坐标') as HTMLInputElement).value).toBe('72');
  const oldOwner = capture(); view.rerender(<ComicLayoutsPanel client={client('other')} />); await screen.findByRole('button', { name: '打开布局 Second layout' }); view.rerender(<ComicLayoutsPanel client={owner} />); await open(); fireEvent.change(screen.getByLabelText('格框 1 横坐标'), { target: { value: '72' } }); oldOwner();
  expect((screen.getByLabelText('格框 1 横坐标') as HTMLInputElement).value).toBe('72');
});
