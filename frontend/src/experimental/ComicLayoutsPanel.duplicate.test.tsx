// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ComicLayoutsPanel } from './ComicLayoutsPanel';
import { experimentalClient } from './api';
import fixture from '../../../tests/fixtures/comic_panel_duplicate.json';
const source = { id: 'screenplay', title: 'Source', edit_version: 1, shots: [{ id: 'shot', number: 1, scene_id: 'scene' }] };
const preset = { width: 320, height: 640, safe_area: 8, segment_height: 320 };
const baseCatalog = { screenplays: [source], characters: [{ id: 'alice', name: 'Alice' }], assets: [{ id: 'asset', filename: 'SYNTHETIC.png', version: 2, approved: true }], presets: { PAGE: preset, WEBTOON: preset }, renderer: { available: true }, font: { available: true } };
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const client = (id = 'novel') => experimentalClient(id, { sessionToken: 'trusted' });
function harness(intercept?: (url: string, init: RequestInit) => Response | Promise<Response> | undefined) {
  let row = { id: 'layout', version: 1, status: 'DRAFT', stale: false, document: structuredClone(fixture.document), history_versions: [] as number[] };
  const catalog = structuredClone(baseCatalog);
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    const special = intercept?.(url, init); if (special) return special;
    if (init.method === 'PUT') {
      const { expected_version, ...document } = JSON.parse(String(init.body)); row = { ...row, version: expected_version + 1, document }; return reply(row);
    }
    if (url.endsWith('/preflight')) return reply({ version: row.version, status: row.status, can_render: true, review_digest: 'digest', segments: [{ index: 0, width: 320, height: 320 }], issues: [] });
    if (url.includes('/segments/')) return new Response(new Blob(['SYNTHETIC PNG']));
    return reply(url.endsWith('/catalog') ? catalog : { items: [row] });
  }); vi.stubGlobal('fetch', fetch); return { fetch, catalog };
}
const preview = () => fireEvent.click(screen.getByRole('button', { name: '预览复制格框 1' }));
const apply = () => screen.getByRole('button', { name: '应用格框复制到草稿' }) as HTMLButtonElement;
const capture = () => {
  preview(); const button = apply(); const key = Object.keys(button).find(k => k.startsWith('__reactProps'))!;
  return (button as unknown as Record<string, { onClick: () => void }>)[key].onClick;
};
const count = () => screen.getAllByRole('article', { name: /^漫画格框 / }).length;
const open = async () => fireEvent.click(await screen.findByRole('button', { name: /打开布局/ }));
beforeEach(() => { URL.createObjectURL = vi.fn(() => 'blob:duplicate-preview'); URL.revokeObjectURL = vi.fn(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
it('explicit preview discloses pins and applies one exact undoable copy through original CAS save', async () => {
  const { fetch } = harness(); render(<ComicLayoutsPanel client={client()} />); await open();
  const ids = vi.spyOn(globalThis.crypto, 'randomUUID').mockReturnValueOnce('duplicate' as ReturnType<Crypto['randomUUID']>).mockReturnValueOnce('duplicate-speech' as ReturnType<Crypto['randomUUID']>);
  preview(); expect(count()).toBe(1); expect(ids).not.toHaveBeenCalled();
  expect(screen.getByText(/原镜头 shot · 图片 asset · 固定版本 2/)).toBeTruthy();
  expect(screen.getByText(/alice → asset · v2 · 原外观/)).toBeTruthy();
  fireEvent.change(screen.getByLabelText('复制目标横坐标'), { target: { value: '160' } });
  fireEvent.change(screen.getByLabelText('复制目标纵坐标'), { target: { value: '336' } });
  fireEvent.click(apply()); expect(count()).toBe(2); expect(ids).toHaveBeenCalledTimes(2);
  expect((screen.getByLabelText('格框 1 横坐标') as HTMLInputElement).value).toBe('16');
  expect((screen.getByLabelText('格框 2 气泡 1 横坐标') as HTMLInputElement).value).toBe('168');
  expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '撤销本地排版' })); expect(count()).toBe(1);
  fireEvent.click(screen.getByRole('button', { name: '重做本地排版' })); expect(count()).toBe(2); expect(ids).toHaveBeenCalledTimes(2);
  ids.mockRestore(); fireEvent.click(screen.getByRole('button', { name: '保存漫画布局草稿' }));
  await waitFor(() => expect(fetch.mock.calls.some(([, init]) => init.method === 'PUT')).toBe(true));
  const saved = JSON.parse(String(fetch.mock.calls.find(([, init]) => init.method === 'PUT')![1].body));
  expect(saved.expected_version).toBe(1); expect(saved.panels).toEqual([fixture.document.panels[0], fixture.expectedPanel]);
  expect(fetch.mock.calls.some(([url]) => /approve|export|generate/.test(url))).toBe(false);
});
it('invalid destination never consumes IDs or changes history and cancel discards preview', async () => {
  harness(); render(<ComicLayoutsPanel client={client()} />); await open();
  const ids = vi.spyOn(globalThis.crypto, 'randomUUID'); preview();
  for (const value of ['', '16', '-1', '336.5', '12000']) {
    fireEvent.change(screen.getByLabelText('复制目标纵坐标'), { target: { value } });
    expect(apply().disabled).toBe(true); fireEvent.click(apply()); expect(count()).toBe(1);
  }
  expect(ids).not.toHaveBeenCalled(); fireEvent.click(screen.getByRole('button', { name: '取消格框复制' }));
  expect(screen.queryByRole('button', { name: '应用格框复制到草稿' })).toBeNull();
  expect((screen.getByRole('button', { name: '撤销本地排版' }) as HTMLButtonElement).disabled).toBe(true);
});
it('retained apply callbacks cannot survive edit, coordinate replacement, cancel, or repeat', async () => {
  harness(); render(<ComicLayoutsPanel client={client()} />); await open();
  const cancelled = capture(); fireEvent.click(screen.getByRole('button', { name: '取消格框复制' })); act(cancelled); expect(count()).toBe(1);
  const edited = capture(); fireEvent.change(screen.getByLabelText('漫画布局名称'), { target: { value: 'Changed' } }); act(edited); expect(count()).toBe(1);
  const moved = capture(); fireEvent.change(screen.getByLabelText('复制目标纵坐标'), { target: { value: '336' } }); act(moved); expect(count()).toBe(1);
  const repeated = capture(); act(() => { repeated(); repeated(); }); expect(count()).toBe(2);
  fireEvent.click(screen.getByRole('button', { name: '撤销本地排版' })); expect(count()).toBe(1);
});
it('IME start invalidates intent and prevents preview until composition ends', async () => {
  harness(); render(<ComicLayoutsPanel client={client()} />); await open(); const old = capture();
  fireEvent.compositionStart(screen.getByLabelText('格框 1 气泡 1 文字')); act(old); expect(count()).toBe(1);
  expect((screen.getByRole('button', { name: '预览复制格框 1' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.compositionEnd(screen.getByLabelText('格框 1 气泡 1 文字')); act(old); expect(count()).toBe(1);
  preview(); expect(apply().disabled).toBe(false);
});
it.each([403, 409, 500])('pending and failed original save %s revokes intent and keeps the draft', async status => {
  let finish: (value: Response) => void = () => {};
  const { fetch } = harness((url, init) => init.method === 'PUT' ? new Promise(resolve => { finish = resolve; }) : undefined);
  render(<ComicLayoutsPanel client={client()} />); await open(); const old = capture();
  fireEvent.click(screen.getByRole('button', { name: '保存漫画布局草稿' })); act(old); expect(count()).toBe(1);
  await act(async () => { finish(reply({ code: 'FAILED_SAVE' }, status)); });
  act(old); expect(count()).toBe(1); expect(screen.queryByRole('button', { name: '应用格框复制到草稿' })).toBeNull();
  expect(fetch.mock.calls.filter(([, init]) => init.method !== 'GET')).toHaveLength(1);
});
it('refresh, stale catalog pins, source ABA and client/scope replacement fence retained callbacks', async () => {
  const { catalog } = harness(); const owner = client(); const view = render(<ComicLayoutsPanel client={owner} />); await open();
  const refreshed = capture(); catalog.assets[0].version = 3;
  fireEvent.click(screen.getByRole('button', { name: '刷新漫画来源与记录' })); act(refreshed);
  await waitFor(() => expect((screen.getByRole('button', { name: '预览复制格框 1' }) as HTMLButtonElement).disabled).toBe(false));
  preview(); expect(apply().disabled).toBe(true); expect(screen.getByText(/图片版本、批准状态或人物引用已变化/)).toBeTruthy();
  catalog.assets[0].version = 2;
  fireEvent.click(screen.getByRole('button', { name: '刷新漫画来源与记录' }));
  await waitFor(() => expect((screen.getByRole('button', { name: '预览复制格框 1' }) as HTMLButtonElement).disabled).toBe(false));
  const sourceOld = capture(); fireEvent.change(screen.getByLabelText('漫画来源剧本'), { target: { value: '' } }); await open(); act(sourceOld); expect(count()).toBe(1);
  const scoped = capture(); view.rerender(<ComicLayoutsPanel client={client('other')} />); await open();
  view.rerender(<ComicLayoutsPanel client={owner} />); await open(); act(scoped); expect(count()).toBe(1);
});
it('ID collisions fail atomically and displayed pixels and consent disappear on successful copy', async () => {
  harness(); render(<ComicLayoutsPanel client={client()} />); await open();
  const ids = vi.spyOn(globalThis.crypto, 'randomUUID').mockReturnValue('authored' as ReturnType<Crypto['randomUUID']>); preview(); fireEvent.click(apply()); expect(count()).toBe(1);
  expect(screen.getByText(/新格框或气泡标识冲突/)).toBeTruthy(); ids.mockRestore();
  fireEvent.click(screen.getByRole('button', { name: '取消格框复制' }));
  fireEvent.click(screen.getByRole('button', { name: '预检并渲染当前布局' }));
  fireEvent.load(await screen.findByRole('img', { name: /漫画分段/ })); fireEvent.click(screen.getByRole('checkbox', { name: /已核对图片、阅读顺序/ }));
  preview(); fireEvent.click(apply()); expect(count()).toBe(2);
  expect(screen.queryByRole('img', { name: /漫画分段/ })).toBeNull(); expect(screen.queryByRole('button', { name: '批准当前漫画布局' })).toBeNull();
  expect(vi.mocked(URL.revokeObjectURL).mock.calls.map(call => call[0])).toEqual(['blob:duplicate-preview']);
});

function retained<T extends (...args: any[]) => unknown>(element: HTMLElement, name: string): T {
  const key = Object.keys(element).find(k => k.startsWith('__reactProps'))!;
  return (element as unknown as Record<string, Record<string, T>>)[key][name];
}
it.each(['edit', 'undo', 'redo', 'load', 'source', 'refresh', 'save', 'append'] as const)('copy then retained %s in the same batch cannot resurrect or persist an old draft', async kind => {
  const { fetch } = harness(); render(<ComicLayoutsPanel client={client()} />); await open();
  fireEvent.change(screen.getByLabelText('漫画布局名称'), { target: { value: 'Edited' } });
  if (kind === 'redo') fireEvent.click(screen.getByRole('button', { name: '撤销本地排版' }));
  let old: () => unknown;
  if (kind === 'edit') {
    const change = retained<(event: { target: { value: string } }) => void>(screen.getByLabelText('漫画布局名称'), 'onChange');
    old = () => change({ target: { value: 'STALE' } });
  } else if (kind === 'source') {
    const change = retained<(event: { target: { value: string } }) => void>(screen.getByLabelText('漫画来源剧本'), 'onChange');
    old = () => change({ target: { value: '' } });
  } else {
    const name = { undo: '撤销本地排版', redo: '重做本地排版', load: `打开布局 ${fixture.document.title}`, refresh: '刷新漫画来源与记录', save: '保存漫画布局草稿', append: '添加格框（手工定位）' }[kind];
    old = retained(screen.getByRole('button', { name }), 'onClick');
  }
  const copy = capture();
  await act(async () => { copy(); old(); });
  expect(count()).toBe(2);
  expect((screen.getByLabelText('漫画布局名称') as HTMLInputElement).value).not.toBe('STALE');
  expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
  // The current history control still works and one undo removes the copy.
  fireEvent.click(screen.getByRole('button', { name: '撤销本地排版' })); expect(count()).toBe(1);
});
it.each(['edit', 'undo', 'redo', 'load', 'source', 'refresh', 'save'] as const)('%s then retained copy in the same batch cannot apply to an obsolete owner', async kind => {
  const { fetch } = harness(); render(<ComicLayoutsPanel client={client()} />); await open();
  fireEvent.change(screen.getByLabelText('漫画布局名称'), { target: { value: 'Edited' } });
  if (kind === 'redo') fireEvent.click(screen.getByRole('button', { name: '撤销本地排版' }));
  if (['load', 'source', 'refresh'].includes(kind)) {
    expect((screen.getByRole('button', { name: `打开布局 ${fixture.document.title}` }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: '放弃当前页面修改' }));
  }
  const copy = capture(); let first: () => unknown;
  if (kind === 'edit') {
    const change = retained<(event: { target: { value: string } }) => void>(screen.getByLabelText('漫画布局名称'), 'onChange'); first = () => change({ target: { value: 'Newest' } });
  } else if (kind === 'source') {
    const change = retained<(event: { target: { value: string } }) => void>(screen.getByLabelText('漫画来源剧本'), 'onChange'); first = () => change({ target: { value: '' } });
  } else {
    const name = { undo: '撤销本地排版', redo: '重做本地排版', load: `打开布局 ${fixture.document.title}`, refresh: '刷新漫画来源与记录', save: '保存漫画布局草稿' }[kind];
    first = retained(screen.getByRole('button', { name }), 'onClick');
  }
  await act(async () => { first(); copy(); });
  if (kind === 'source') expect(screen.queryByRole('article', { name: /^漫画格框 / })).toBeNull();
  else expect(count()).toBe(1);
  const writes = fetch.mock.calls.filter(([, init]) => init.method !== 'GET');
  expect(writes).toHaveLength(kind === 'save' ? 1 : 0);
  if (kind === 'save') expect(JSON.parse(String(writes[0][1].body)).panels).toHaveLength(1);
});
it('final compositionEnd followed by onChange in one batch preserves committed IME text', async () => {
  harness(); render(<ComicLayoutsPanel client={client()} />); await open();
  const text = screen.getByLabelText('格框 1 气泡 1 文字');
  fireEvent.compositionStart(text);
  const change = retained<(event: { target: { value: string } }) => void>(text, 'onChange');
  const section = screen.getByRole('region', { name: '漫画与 Webtoon 排版' });
  const end = retained<() => void>(section, 'onCompositionEndCapture');
  act(() => { end(); change({ target: { value: '最终中文 👩🏽‍🚀' } }); });
  expect((screen.getByLabelText('格框 1 气泡 1 文字') as HTMLTextAreaElement).value).toBe('最终中文 👩🏽‍🚀');
  preview(); expect(apply().disabled).toBe(false); fireEvent.click(apply());
  expect((screen.getByLabelText('格框 2 气泡 1 文字') as HTMLTextAreaElement).value).toBe('最终中文 👩🏽‍🚀');
});
