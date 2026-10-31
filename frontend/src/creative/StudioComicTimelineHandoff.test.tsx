// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { webcrypto } from 'node:crypto';
import { Blob as NodeBlob } from 'node:buffer';
import capture from './__fixtures__/comicHandoffHttp.json';
import { StudioComicPanel } from './StudioComicPanel';

const copy = <T,>(value: T): T => structuredClone(value);
const button = (name: string) => screen.getByRole('button', { name }) as HTMLButtonElement;
const field = (name: string) => screen.getByLabelText(name) as HTMLInputElement;
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
const preset = { width: 320, height: 640, safe_area: 24, segment_height: 320 };
const catalogue = { screenplays: [], characters: [], assets: [], presets: { PAGE: preset, WEBTOON: { ...preset, height: 1280 } }, renderer: { available: true }, font: { available: true } };
type Mode = 'normal' | 'lost' | 'missing' | 'partial' | 'invalid200' | 'denied';
function server(mode: Mode = 'normal') {
  let stored: ReturnType<typeof completed> | undefined, attempts = 0;
  const hooks: { preview?: () => Promise<Response>; post?: (response: Response) => Promise<Response> } = {};
  function completed(requestId: string) {
    const value = copy(capture.created); value.request_id = requestId; value.timeline.comic_handoff_origin.request_id = requestId; return value;
  }
  function partial(requestId: string) {
    const value = completed(requestId);
    Object.assign(value, { status: 'PLANNED', version: 2, timeline_snapshot: null });
    delete (value as Partial<typeof value>).timeline; delete (value as Partial<typeof value>).timeline_state;
    Object.assign(value.steps[1], { state: 'PENDING', asset_version: null, observed_state: 'AWAITING_EXPLICIT_RESUME' }); return value;
  }
  const writes: { method: string; path: string; body: Record<string, unknown> }[] = [];
  const fetcher = vi.fn(async (url: string, init: RequestInit) => {
    const body = init.body ? JSON.parse(String(init.body)) : {}, path = String(url), method = init.method || 'GET';
    if (path.endsWith('/comic-layouts/catalog')) return reply(catalogue);
    if (path.endsWith('/comic-layouts/records')) return reply({ items: capture.source_records });
    if (path.endsWith('/comic-layouts/books')) return reply({ items: [] });
    if (path.endsWith('/preflight')) {
      const pin = capture.preview_response.preview.pages.find(p => path.includes(p.source.id))!;
      return reply({ issues: [], segments: [{ index: 0, width: 320, height: 640, y: 0 }], can_render: true,
        version: pin.source.version, status: 'APPROVED', review_digest: pin.source.review_digest });
    }
    if (path.endsWith('/comic-handoffs/preview')) return hooks.preview ? hooks.preview() : reply(capture.preview_response);
    if (path.endsWith('/comic-handoffs')) {
      writes.push({ path, body, method }); attempts++;
      if (mode === 'denied') return reply({ detail: { code: 'DENIED', message: 'private-canary' } }, 403);
      if (mode === 'missing' && attempts === 1) throw new Error('private-canary-lost-before-commit');
      stored = mode === 'partial' ? partial(body.request_id) : completed(body.request_id);
      if (mode === 'lost' && attempts === 1) throw new Error('private-canary-lost-after-commit');
      const response = reply(mode === 'invalid200' ? { ...stored, status: 'APPROVED' } : stored);
      return hooks.post ? hooks.post(response) : response;
    }
    if (path.endsWith('/resume') || path.endsWith('/cancel')) {
      writes.push({ path, body, method });
      const id = path.split('/').at(-2)!;
      if (path.endsWith('/resume')) stored = completed(id);
      else { stored = partial(id); Object.assign(stored, { status: 'CANCELLED', version: 3 }); }
      return reply(stored);
    }
    if (path.includes('/comic-handoffs/') && method === 'GET') return stored ? reply(stored) : reply({ detail: { code: 'EXPERIMENTAL_NOT_FOUND' } }, 404);
    throw new Error('Unexpected fixture request: ' + path);
  });
  vi.stubGlobal('fetch', fetcher); return { fetcher, writes, hooks, get stored() { return stored; } };
}
function mount(sourceFree = false) {
  const owner = { current: true };
  const props = { projectId: capture.original_timeline.novel_id, context: { sessionToken: 'ui-only-host-token' },
    isCurrent: () => owner.current, canMutate: true, canReview: true, sourceFree, onDirtyChange: vi.fn(), onBusyChange: vi.fn() };
  const view = render(<StudioComicPanel {...props} />); return { view, props, owner };
}
async function configure() {
  for (const page of capture.request.pages) {
    const box = await screen.findByLabelText(new RegExp(page.id)); fireEvent.click(box);
  }
  fireEvent.change(field('Timeline 草稿标题'), { target: { value: capture.request.title } });
  fireEvent.change(field('输出宽度'), { target: { value: '640' } });
  fireEvent.change(field('输出高度'), { target: { value: '360' } });
  fireEvent.change(field('第 1 页停留时长（毫秒）'), { target: { value: '10000' } });
  fireEvent.change(field('第 2 页停留时长（毫秒）'), { target: { value: '10000' } });
}
async function preview(recovery = false) {
  fireEvent.click(button(recovery ? '重新核对原请求整页预览' : '检查并加载整页预览'));
  await screen.findByAltText('交接整页预览 1');
}
function load(index: number, width = 320, height = 640) {
  const image = screen.getByAltText('交接整页预览 ' + index) as HTMLImageElement;
  Object.defineProperty(image, 'naturalWidth', { configurable: true, value: width });
  Object.defineProperty(image, 'naturalHeight', { configurable: true, value: height });
  fireEvent.load(image);
}
function acknowledge() {
  load(1); load(2);
  fireEvent.click(field('已查看全部整页图片，核对页面版本、顺序和逐页时长'));
  fireEvent.click(field('确认静态整页合并损失，只创建未批准的 Timeline 草稿'));
}
beforeEach(() => {
  sessionStorage.clear(); vi.stubGlobal('crypto', webcrypto); vi.stubGlobal('Blob', NodeBlob);
  let serial = 0; URL.createObjectURL = vi.fn(() => 'blob:comic-handoff-' + ++serial); URL.revokeObjectURL = vi.fn();
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('mounts original render-slot, verifies both loaded pages, coordinates editor locks and shows native draft ID', async () => {
  const e = server(), host = mount(); await configure();
  expect(button('新建空白漫画页').disabled).toBe(true);
  await preview();
  expect(button('明确创建原 Timeline 草稿').disabled).toBe(true);
  load(1); expect(field('已查看全部整页图片，核对页面版本、顺序和逐页时长').disabled).toBe(true);
  acknowledge(); expect(button('明确创建原 Timeline 草稿').disabled).toBe(false);
  const send = button('明确创建原 Timeline 草稿'); fireEvent.click(send); fireEvent.click(send);
  await screen.findByText(new RegExp('原 Timeline 草稿 ID：' + capture.created.timeline_snapshot.id));
  expect(e.writes).toHaveLength(1); expect(e.writes[0].body.request).toEqual(capture.request);
  expect(host.props.onBusyChange).toHaveBeenCalledWith(true); expect(host.props.onBusyChange).toHaveBeenLastCalledWith(false);
  const stored = JSON.stringify(Array.from({ length: sessionStorage.length }, (_, index) => sessionStorage.getItem(sessionStorage.key(index)!)));
  expect(stored).not.toContain('ui-only-host-token'); expect(stored).not.toContain('png_base64');
  fireEvent.click(button('关闭交接并保留原记录'));
  expect(sessionStorage.length).toBe(0); expect(button('新建空白漫画页').disabled).toBe(false);
  expect(e.fetcher.mock.calls.some(([url]) => /execute|generate|render/.test(String(url)))).toBe(false);
});
it.each(['lost', 'invalid200'] as const)('keeps exact ID after %s and requires readback before reporting success', async mode => {
  const e = server(mode); mount(); await configure(); await preview(); acknowledge(); fireEvent.click(button('明确创建原 Timeline 草稿'));
  await screen.findByText(/提交结果尚未核对/); await waitFor(() => expect(button('按原 ID 读回交接状态').disabled).toBe(false));
  expect(screen.queryByText(/原 Timeline 草稿 ID：/)).toBeNull(); expect(e.writes).toHaveLength(1);
  const id = e.writes[0].body.request_id;
  fireEvent.click(button('按原 ID 读回交接状态'));
  await screen.findByText(/原 Timeline 草稿 ID：/); expect(e.writes).toHaveLength(1);
  expect(e.fetcher.mock.calls.some(([url, init]) => String(url).endsWith('/' + id) && init.method === 'GET')).toBe(true);
});
it('treats 404 as uncertain and only explicitly re-sends the same immutable ID and body', async () => {
  const e = server('missing'); mount(); await configure(); await preview(); acknowledge(); fireEvent.click(button('明确创建原 Timeline 草稿'));
  await screen.findByText(/提交结果尚未核对/); await waitFor(() => expect(button('按原 ID 读回交接状态').disabled).toBe(false));
  const first = copy(e.writes[0].body);
  fireEvent.click(button('按原 ID 读回交接状态')); await screen.findByText(/404 也不能证明请求未提交/);
  await waitFor(() => expect(button('明确重发同一确认').disabled).toBe(true)); expect(e.writes).toHaveLength(1);
  await preview(true); acknowledge(); fireEvent.click(field('已核对原请求，明确按同一 ID 和相同确认内容重发'));
  fireEvent.click(button('明确重发同一确认')); await screen.findByText(/原 Timeline 草稿 ID：/);
  expect(e.writes).toHaveLength(2); expect(e.writes[1].body).toEqual(first);
});
it.each(['resume', 'cancel'] as const)('requires explicit versioned %s after a partial receipt and retains original request', async action => {
  const e = server('partial'); mount(); await configure(); await preview(); acknowledge(); fireEvent.click(button('明确创建原 Timeline 草稿'));
  await screen.findByText(/交接等待明确恢复/); expect(e.writes).toHaveLength(1);
  if (action === 'resume') { expect(button('明确恢复剩余交接步骤').disabled).toBe(true); await preview(true); acknowledge(); fireEvent.click(button('明确恢复剩余交接步骤')); await screen.findByText(/原 Timeline 草稿 ID：/); }
  else { fireEvent.click(field('确认取消后保留已提交素材，不回滚或删除资源')); fireEvent.click(button('明确取消原交接')); await screen.findByText(/原交接已取消/); }
  expect(e.writes).toHaveLength(2); expect(e.writes[1].path).toContain(String(e.writes[0].body.request_id)); expect(e.writes[1].body).toEqual({ expected_version: 2 });
});
it('restores pending identity on remount without dispatching any automatic write or status read', async () => {
  const e = server('lost'); const host = mount(); await configure(); await preview(); acknowledge(); fireEvent.click(button('明确创建原 Timeline 草稿'));
  await screen.findByText(/提交结果尚未核对/); host.view.unmount(); const calls = e.fetcher.mock.calls.length;
  mount(); await screen.findByText(/原请求 ID：/); expect(e.writes).toHaveLength(1);
  expect(e.fetcher.mock.calls.slice(calls).filter(([url]) => String(url).includes('/comic-handoffs/'))).toHaveLength(0);
  fireEvent.click(button('按原 ID 读回交接状态')); await screen.findByText(/原 Timeline 草稿 ID：/);
});
it('rejects a wrong image dimension or error before explicit confirmation', async () => {
  const e = server(); mount(); await configure(); await preview(); load(1, 999); load(2);
  expect(button('明确创建原 Timeline 草稿').disabled).toBe(true); expect(e.writes).toHaveLength(0);
  await preview(); acknowledge(); fireEvent.error(screen.getByAltText('交接整页预览 1'));
  expect(button('明确创建原 Timeline 草稿').disabled).toBe(true); expect(e.writes).toHaveLength(0);
});
it('invalidates loaded preview and acknowledgements after duration A-B-A changes', async () => {
  const e = server(); mount(); await configure(); await preview(); acknowledge();
  fireEvent.change(field('第 1 页停留时长（毫秒）'), { target: { value: '9000' } });
  fireEvent.change(field('第 1 页停留时长（毫秒）'), { target: { value: '10000' } });
  expect(screen.queryByAltText('交接整页预览 1')).toBeNull(); expect(button('明确创建原 Timeline 草稿').disabled).toBe(true);
  expect(e.writes).toHaveLength(0); expect(URL.revokeObjectURL).toHaveBeenCalledTimes(2);
});
it('does not inject Timeline authority into source-free Comic mode', async () => {
  const e = server(); mount(true); await screen.findByRole('button', { name: '新建空白漫画页' });
  expect(screen.queryByText('整页交接到 Timeline 草稿')).toBeNull(); expect(e.fetcher.mock.calls.some(([url]) => String(url).includes('comic-handoffs'))).toBe(false);
});
it('retains the recovery ID and stops after permission loss without automatic status or execution', async () => {
  const e = server('denied'); mount(); await configure(); await preview(); acknowledge(); fireEvent.click(button('明确创建原 Timeline 草稿'));
  await waitFor(() => expect(screen.queryByText('整页交接到 Timeline 草稿')).toBeNull());
  expect(sessionStorage.length).toBe(1); expect(e.writes).toHaveLength(1);
  expect(e.fetcher.mock.calls.filter(([url, init]) => String(url).includes('/comic-handoffs/') && init.method === 'GET')).toHaveLength(0);
  expect(document.body.textContent).not.toContain('private-canary');
});
it('discards late owner ABA preview without clearing the newer operation busy state', async () => {
  const e = server(), pending: ((response: Response) => void)[] = [];
  e.hooks.preview = () => new Promise(resolve => pending.push(resolve));
  const host = mount(); await configure(); fireEvent.click(button('检查并加载整页预览'));
  await waitFor(() => expect(pending).toHaveLength(1));
  host.owner.current = false; host.view.rerender(<StudioComicPanel {...host.props} />);
  host.owner.current = true; host.view.rerender(<StudioComicPanel {...host.props} />);
  fireEvent.click(button('检查并加载整页预览')); await waitFor(() => expect(pending).toHaveLength(2));
  await act(async () => { pending[0](reply(capture.preview_response)); await new Promise(done => setTimeout(done, 20)); });
  expect(URL.createObjectURL).not.toHaveBeenCalled(); expect(host.props.onBusyChange).toHaveBeenLastCalledWith(true);
  await act(async () => { pending[1](reply(capture.preview_response)); }); await screen.findByAltText('交接整页预览 1');
  expect(URL.createObjectURL).toHaveBeenCalledTimes(2); expect(host.props.onBusyChange).toHaveBeenLastCalledWith(false);
  expect(e.writes).toHaveLength(0);
});
it('does not adopt a late write response across capability A-B-A and only allows exact ID readback', async () => {
  const e = server(); let release!: () => void;
  e.hooks.post = response => new Promise(resolve => { release = () => resolve(response); });
  const host = mount(); await configure(); await preview(); acknowledge(); fireEvent.click(button('明确创建原 Timeline 草稿'));
  await waitFor(() => expect(e.writes).toHaveLength(1));
  host.view.rerender(<StudioComicPanel {...host.props} canMutate={false} />);
  host.view.rerender(<StudioComicPanel {...host.props} />);
  await act(async () => release());
  expect(screen.queryByText(/原 Timeline 草稿 ID：/)).toBeNull(); expect(e.writes).toHaveLength(1);
  expect(screen.getByText(/提交结果尚未核对/)).toBeTruthy();
  fireEvent.click(button('按原 ID 读回交接状态')); await screen.findByText(/原 Timeline 草稿 ID：/); expect(e.writes).toHaveLength(1);
});
it('blocks POST if exact recovery intent cannot be saved', async () => {
  const e = server(); mount(); await configure(); await preview(); acknowledge();
  const write = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('unavailable'); });
  fireEvent.click(button('明确创建原 Timeline 草稿')); await screen.findByText(/无法核对浏览器会话中的交接恢复标识/);
  expect(e.writes).toHaveLength(0); write.mockRestore();
});
it('keeps IME title edits and blocks network commands until composition ends', async () => {
  const e = server(); mount(); await configure(); const title = field('Timeline 草稿标题');
  fireEvent.compositionStart(title); fireEvent.change(title, { target: { value: '输入中的中文标题' } });
  expect(title.value).toBe('输入中的中文标题'); expect(button('检查并加载整页预览').disabled).toBe(true);
  expect(e.writes).toHaveLength(0); fireEvent.compositionEnd(title); expect(button('检查并加载整页预览').disabled).toBe(false);
});
it('can pause an uncertain intent while retaining its exact ID and preventing a replacement request', async () => {
  const e = server('lost'); mount(); await configure(); await preview(); acknowledge(); fireEvent.click(button('明确创建原 Timeline 草稿'));
  await waitFor(() => expect(button('暂存恢复标识并关闭交接').disabled).toBe(false)); const id = e.writes[0].body.request_id;
  fireEvent.click(button('暂存恢复标识并关闭交接')); expect(button('新建空白漫画页').disabled).toBe(false); expect(sessionStorage.length).toBe(1);
  fireEvent.click(button('继续核对原交接')); expect(screen.getByText('原请求 ID：' + id)).toBeTruthy();
  expect(screen.queryByRole('button', { name: '明确创建原 Timeline 草稿' })).toBeNull(); expect(e.writes).toHaveLength(1);
});
it('can stop waiting for an in-flight POST, read its original ID, and ignore the late response', async () => {
  const e = server(); let release!: () => void;
  e.hooks.post = response => new Promise(resolve => { release = () => resolve(response); });
  const host = mount(); await configure(); await preview(); acknowledge(); fireEvent.click(button('明确创建原 Timeline 草稿'));
  await waitFor(() => expect(e.writes).toHaveLength(1)); const id = e.writes[0].body.request_id;
  fireEvent.click(button('停止等待并保留原请求 ID'));
  expect(host.props.onBusyChange).toHaveBeenLastCalledWith(false); expect(sessionStorage.length).toBe(1);
  fireEvent.click(button('按原 ID 读回交接状态')); await screen.findByText(/原 Timeline 草稿 ID：/);
  await act(async () => release());
  expect(screen.getByText(/原 Timeline 草稿 ID：/)).toBeTruthy(); expect(e.writes).toHaveLength(1);
  expect(e.fetcher.mock.calls.some(([url, init]) => String(url).endsWith('/' + id) && init.method === 'GET')).toBe(true);
});
it('coordinates the existing page and image-generation editor without poisoning handoff busy ownership', async () => {
  const e = server(); let release!: (response: Response) => void;
  e.hooks.preview = () => new Promise(resolve => { release = resolve; });
  const host = mount();
  await screen.findAllByRole('button', { name: '打开布局 Synthetic HTTP page' });
  fireEvent.click(screen.getAllByRole('button', { name: '打开布局 Synthetic HTTP page' })[0]);
  await waitFor(() => expect(document.querySelector('[data-comic-image-generation]')).toBeTruthy());
  await configure();
  expect(document.querySelector('[data-comic-image-generation] fieldset')).toHaveProperty('disabled', true);
  fireEvent.click(button('检查并加载整页预览')); await waitFor(() => expect(typeof release).toBe('function'));
  expect(host.props.onBusyChange).toHaveBeenLastCalledWith(true);
  await act(async () => release(reply(capture.preview_response))); await screen.findByAltText('交接整页预览 1'); acknowledge();
  expect(button('明确创建原 Timeline 草稿').disabled).toBe(false);
  fireEvent.click(button('关闭交接并保留原记录'));
  expect(document.querySelector('[data-comic-image-generation] fieldset')).toHaveProperty('disabled', false);
  expect(e.writes).toHaveLength(0); expect(e.fetcher.mock.calls.some(([, init]) => init.method === 'PUT')).toBe(false);
});
