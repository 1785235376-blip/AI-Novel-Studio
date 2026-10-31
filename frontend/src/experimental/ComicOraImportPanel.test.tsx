// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ComicOraImportPanel } from './ComicOraImportPanel';
import type { ExperimentalClient } from './api';
import type { ComicRecord } from './comicLayoutsClient';
import type { OraReceipt } from './comicOraClient';
vi.mock('./comicOraClient', async original => ({ ...await original<typeof import('./comicOraClient')>(), readOraFile: vi.fn(async (file: File) => ({ archive_base64: 'YXJjaGl2ZQ==', archive_sha256: file.name === 'wrong.ora' ? 'wrong' : 'a'.repeat(64) })) }));
const layer = { name: 'Raster', width: 100, height: 100, x: 0, y: 0, visible: true, opacity_percent: 100, png_sha256: 'b'.repeat(64), asset_id: 'asset', state: 'PENDING' as const };
const original: OraReceipt = { id: 'receipt', version: 1, archive_sha256: 'a'.repeat(64), status: 'PREPARED', steps: [layer], losses: ['RASTER_LAYERS_ONLY_NO_EDITABLE_DIALOGUE_RECOVERY'] };
const page: ComicRecord = { id: 'page', version: 2, status: 'DRAFT', stale: false, document: { source_mode: 'INDEPENDENT', title: 'Page', screenplay_id: null, expected_screenplay_version: null, preset: 'PAGE', font_family: 'NOTO_SANS_SC_OFL', width: 320, height: 640, safe_area: 8, segment_height: 320, panels: [] } };
const handler = (el: HTMLElement) => (el as unknown as Record<string, { onClick: () => void }>)[Object.keys(el).find(key => key.startsWith('__reactProps'))!].onClick;
function harness(initial = original) {
  let receipt = structuredClone(initial);
  const post = vi.fn(async (path: string, body: any) => {
    if (path.endsWith('/preview')) return { report: { archive_sha256: 'a'.repeat(64), width: 320, height: 640, layers: [layer], losses: original.losses }, thumbnail_base64: 'UE5H' };
    if (path.endsWith('/stage')) receipt = { ...receipt, status: 'STAGED', steps: [{ ...layer, state: 'STAGED' }] };
    if (path.endsWith('/review-manifest')) return { manifest: { page: { width: 320, height: 640 }, layers: [layer] }, manifest_digest: 'manifest' };
    if (path.endsWith('/review')) receipt = { ...receipt, status: 'REVIEWED_READY_FOR_ATTACHMENT', review_digest: 'review', review_license_note: body.license_note, steps: [{ ...layer, state: 'REVIEWED' }] };
    if (path.endsWith('/attach')) return { receipt: { ...receipt, attachment: { page_id: page.id } }, page: { ...page, version: 3, status: 'DRAFT' } };
    return receipt;
  });
  const get = vi.fn(async (path: string) => path.endsWith('/ora-imports') ? { receipts: [receipt] } : receipt);
  const blob = vi.fn(async () => new Blob(['PNG'], { type: 'image/png' }));
  const client = { get, post, blob, put: vi.fn() } as unknown as ExperimentalClient;
  const attached = vi.fn(), owner = { current: true, revision: 0 };
  const props = { client, page, disabled: false, isOwnerCurrent: () => owner.current, getOwnerRevision: () => owner.revision, onBusyChange: vi.fn(), onDirtyChange: vi.fn(), onAttached: attached };
  const view = render(<ComicOraImportPanel {...props} />); return { post, get, blob, attached, owner, props, view };
}
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
const button = (name: string) => screen.getByRole('button', { name }) as HTMLButtonElement;
async function preview(name = 'source.ora') { fireEvent.change(screen.getByLabelText('选择 ORA 文件'), { target: { files: [new File(['x'.repeat(30)], name)] } }); click('只读检查并预览 ORA'); await screen.findByRole('img', { name: /ORA 只读合成缩略图/ }); }
async function stage() { await preview(); click('确认准备 ORA 暂存记录'); await screen.findByText(/当前导入 receipt/); click('暂存 / 继续暂存下一批图层'); await waitFor(() => expect(button('加载全部候选图层实际像素').disabled).toBe(false)); }
async function pixels() { click('加载全部候选图层实际像素'); const image = await screen.findByRole('img', { name: /ORA 候选图层 1/ }); fireEvent.load(image); await waitFor(() => expect((screen.getByLabelText('已逐层查看全部候选实际像素') as HTMLInputElement).disabled).toBe(false)); fireEvent.click(screen.getByLabelText('已逐层查看全部候选实际像素')); fireEvent.change(screen.getByLabelText('ORA 素材授权说明'), { target: { value: 'My licensed artwork' } }); fireEvent.click(screen.getByLabelText(/确认有权使用这些素材/)); }
beforeEach(() => { let id = 0; URL.createObjectURL = vi.fn(() => `blob:ora-${++id}`); URL.revokeObjectURL = vi.fn(); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
it('keeps every write explicit, gates review on actual pixels, and attaches only as DRAFT', async () => {
  const h = harness(); await stage(); expect(h.post.mock.calls.some(([p]) => p.endsWith('/review'))).toBe(false);
  click('加载全部候选图层实际像素'); const image = await screen.findByRole('img', { name: /ORA 候选图层 1/ });
  expect(button('明确审核 / 继续审核下一批素材').disabled).toBe(true); fireEvent.load(image);
  fireEvent.click(screen.getByLabelText('已逐层查看全部候选实际像素')); fireEvent.change(screen.getByLabelText('ORA 素材授权说明'), { target: { value: 'My licensed artwork' } }); fireEvent.click(screen.getByLabelText(/确认有权使用这些素材/));
  click('明确审核 / 继续审核下一批素材'); await waitFor(() => expect(button('明确附加到当前已保存独立页').disabled).toBe(false));
  expect(h.attached).not.toHaveBeenCalled(); click('明确附加到当前已保存独立页'); await waitFor(() => expect(h.attached).toHaveBeenCalledWith(expect.objectContaining({ version: 3, status: 'DRAFT' })));
  expect(h.post.mock.calls.find(([p]) => p.endsWith('/attach'))?.[1]).toEqual({ page_id: 'page', expected_page_version: 2, review_digest: 'review' });
});
it('restores server receipt and requires exact original file after restart', async () => {
  const h = harness(); click('刷新可恢复的 ORA 导入'); await screen.findByRole('button', { name: '恢复 receipt' }); click('恢复 receipt'); await screen.findByText(/当前导入 receipt/);
  expect(button('暂存 / 继续暂存下一批图层').disabled).toBe(true);
  fireEvent.change(screen.getByLabelText('选择 ORA 文件'), { target: { files: [new File(['bad'], 'wrong.ora')] } }); click('只读检查并预览 ORA'); await screen.findByText(/文件与恢复记录的 SHA-256 不一致/);
  expect(h.post).not.toHaveBeenCalled(); click('清除选择 / 开始新的导入'); click('恢复 receipt'); await screen.findByText(/当前导入 receipt/); await preview(); expect(button('暂存 / 继续暂存下一批图层').disabled).toBe(false);
});
it('retained review callback cannot bypass changed acknowledgements or double submit', async () => {
  const h = harness(); await stage(); await pixels(); const retained = handler(button('明确审核 / 继续审核下一批素材'));
  fireEvent.click(screen.getByLabelText(/确认有权使用这些素材/)); act(retained); expect(h.post.mock.calls.some(([p]) => p.endsWith('/review'))).toBe(false);
  fireEvent.click(screen.getByLabelText(/确认有权使用这些素材/)); const current = handler(button('明确审核 / 继续审核下一批素材')); act(() => { current(); current(); });
  await waitFor(() => expect(h.post.mock.calls.filter(([p]) => p.endsWith('/review'))).toHaveLength(1));
});
it('blocks attach for dirty/no page, coupled pages and dimension mismatch', async () => {
  const h = harness(); await stage(); await pixels(); click('明确审核 / 继续审核下一批素材'); await waitFor(() => expect(button('明确附加到当前已保存独立页').disabled).toBe(false));
  for (const target of [undefined, { ...page, document: { ...page.document!, source_mode: 'SCREENPLAY' as const } }, { ...page, document: { ...page.document!, width: 321 } }]) { h.view.rerender(<ComicOraImportPanel {...h.props} page={target} />); expect(button('明确附加到当前已保存独立页').disabled).toBe(true); }
  expect(h.post.mock.calls.some(([p]) => p.endsWith('/attach'))).toBe(false);
});
it('revokes all transient pixel URLs and cannot complete attach after owner replacement', async () => {
  const h = harness(); await stage(); await pixels(); click('明确审核 / 继续审核下一批素材'); await waitFor(() => expect(button('明确附加到当前已保存独立页').disabled).toBe(false));
  let finish!: (value: any) => void; h.post.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; })); click('明确附加到当前已保存独立页'); h.owner.current = false;
  await act(async () => finish({ receipt: original, page })); expect(h.attached).not.toHaveBeenCalled(); h.view.unmount(); expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:ora-2');
});
it.each(['Permission denied', 'Version conflict', 'Quota exceeded'])('preserves recovery intent after %s without auto retry', async message => {
  const h = harness(); await preview(); h.post.mockRejectedValueOnce(new Error(message)); click('确认准备 ORA 暂存记录'); await screen.findByText(message);
  expect(button('确认准备 ORA 暂存记录').disabled).toBe(false); const before = h.post.mock.calls.length; click('确认准备 ORA 暂存记录'); await screen.findByText(/当前导入 receipt/);
  expect(h.post.mock.calls.length).toBe(before + 1); const attempts = h.post.mock.calls.filter(([path]) => path.endsWith('/ora-imports'));
  expect(attempts[0][1].request_key).toBe(attempts[1][1].request_key);
});
it('clears candidate load and acknowledgement on a new file selection and ignores stale load', async () => {
  const h = harness(); await stage(); await pixels(); const image = screen.getByRole('img', { name: /ORA 候选图层 1/ });
  const staleLoad = (image as unknown as Record<string, { onLoad: () => void }>)[Object.keys(image).find(key => key.startsWith('__reactProps'))!].onLoad;
  click('清除选择 / 开始新的导入'); fireEvent.change(screen.getByLabelText('选择 ORA 文件'), { target: { files: [new File(['new'], 'source.ora')] } }); act(staleLoad);
  expect(screen.queryByRole('img', { name: /ORA 候选图层 1/ })).toBeNull(); expect(screen.queryByRole('button', { name: '明确审核 / 继续审核下一批素材' })).toBeNull(); expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:ora-2');
  expect(h.post.mock.calls.some(([p]) => p.endsWith('/review'))).toBe(false);
});
it('pixel failure clears acknowledgement and review remains blocked', async () => {
  const h = harness(); await stage(); await pixels(); fireEvent.error(screen.getByRole('img', { name: /ORA 候选图层 1/ }));
  expect(button('明确审核 / 继续审核下一批素材').disabled).toBe(true); expect((screen.getByLabelText('已逐层查看全部候选实际像素') as HTMLInputElement).checked).toBe(false);
  expect(h.post.mock.calls.some(([p]) => p.endsWith('/review'))).toBe(false);
});
it('restores immutable license for interrupted review and requires fresh pixel evidence', async () => {
  harness({ ...original, status: 'REVIEW_IN_PROGRESS', review_digest: 'review', review_license_note: 'Original license', steps: [{ ...layer, state: 'STAGED' }] });
  click('刷新可恢复的 ORA 导入'); await screen.findByRole('button', { name: '恢复 receipt' }); click('恢复 receipt'); await screen.findByText(/当前导入 receipt/);
  const license = screen.getByLabelText('ORA 素材授权说明') as HTMLTextAreaElement; expect(license.value).toBe('Original license'); expect(license.disabled).toBe(true);
  expect(button('明确审核 / 继续审核下一批素材').disabled).toBe(true); await preview(); expect((screen.getByLabelText('ORA 素材授权说明') as HTMLTextAreaElement).value).toBe('Original license');
});
it('suppresses late preview completion after unmount and never allocates an orphan URL', async () => {
  const h = harness(); let finish!: (value: any) => void; h.post.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
  fireEvent.change(screen.getByLabelText('选择 ORA 文件'), { target: { files: [new File(['file'], 'source.ora')] } }); click('只读检查并预览 ORA'); await waitFor(() => expect(h.post).toHaveBeenCalled()); h.view.unmount();
  await act(async () => finish({ report: { archive_sha256: 'a'.repeat(64), width: 320, height: 640, layers: [layer], losses: [] }, thumbnail_base64: 'UE5H' })); expect(URL.createObjectURL).not.toHaveBeenCalled();
});
it('stale candidate load cannot enable review after owner revision changes', async () => {
  const h = harness(); await stage(); click('加载全部候选图层实际像素'); const image = await screen.findByRole('img', { name: /ORA 候选图层 1/ });
  const staleLoad = (image as unknown as Record<string, { onLoad: () => void }>)[Object.keys(image).find(key => key.startsWith('__reactProps'))!].onLoad;
  h.owner.revision++; act(staleLoad); expect((screen.getByLabelText('已逐层查看全部候选实际像素') as HTMLInputElement).disabled).toBe(true); expect(button('明确审核 / 继续审核下一批素材').disabled).toBe(true);
});
it('local license and File keep recovery replacement blocked until explicit reset', async () => {
  const h = harness(); click('刷新可恢复的 ORA 导入'); await screen.findByRole('button', { name: '恢复 receipt' }); click('恢复 receipt'); await screen.findByText(/当前导入 receipt/);
  const recover = handler(button('恢复 receipt'));
  fireEvent.change(screen.getByLabelText('ORA 素材授权说明'), { target: { value: 'Unsaved note' } });
  expect(h.props.onDirtyChange).toHaveBeenLastCalledWith(true); expect(button('恢复 receipt').disabled).toBe(true);
  act(recover); expect((screen.getByLabelText('ORA 素材授权说明') as HTMLInputElement).value).toBe('Unsaved note');
  click('清除选择 / 开始新的导入'); expect(h.props.onDirtyChange).toHaveBeenLastCalledWith(false); expect(button('恢复 receipt').disabled).toBe(false);
});
it('attachment clears transient dirty intent only after acknowledged success', async () => {
  const h = harness(); await stage(); await pixels(); expect(h.props.onDirtyChange).toHaveBeenLastCalledWith(true);
  click('明确审核 / 继续审核下一批素材'); await waitFor(() => expect(button('明确附加到当前已保存独立页').disabled).toBe(false)); expect(h.props.onDirtyChange).toHaveBeenLastCalledWith(true);
  click('明确附加到当前已保存独立页'); await waitFor(() => expect(h.attached).toHaveBeenCalled()); expect(h.props.onDirtyChange).toHaveBeenLastCalledWith(false);
  expect(screen.queryByText(/source.ora ·/)).toBeNull(); expect(screen.queryByRole('img', { name: /ORA 候选图层/ })).toBeNull();
});
