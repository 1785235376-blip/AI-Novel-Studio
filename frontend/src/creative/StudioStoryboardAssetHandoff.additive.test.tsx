// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { StudioStoryboardAssetHandoff, type StudioStoryboardAssetHandoffProps } from './StudioStoryboardAssetHandoff';
import type { CreativeDocument } from './types';
import type { StudioAsset } from './studioClient';
import receipt from './fixtures/phase4.file-api-storyboard.json';
const document: CreativeDocument = { id: receipt.document_snapshot.id, version: receipt.document_snapshot.version, mode: 'STORYBOARD', title: 'Private existing storyboard A', status: 'DRAFT', created_at: '', updated_at: '', actor_id: 'author', source_evidence: {}, source_chapter_ids: [], source_independent: true, scenes: [], director_notes: [], shots: receipt.shots.map(row => structuredClone(row.shot)), video_plan: null };
const other: CreativeDocument = { ...document, id: 'document-b', title: 'Private existing storyboard B' };
const deferred = <T,>() => { let resolve!: (value: T) => void; const promise = new Promise<T>(yes => { resolve = yes; }); return { promise, resolve }; };
// Capture handlers on the REAL mounted DOM; do not replace the recipient/panel.
// This follows the existing AssetReferenceInspection retained-callback harness.
function retained(node: HTMLElement) {
  const key = Object.keys(node).find(key => key.startsWith('__reactProps$'));
  if (!key) throw new Error('React event-props capture unavailable');
  return (node as unknown as Record<string, { onClick: () => void; onChange: (event: { target: { value: string } }) => void }>)[key];
}
function mount() {
  const asset: StudioAsset = { id: 'image-source', novel_id: 'project', branch_id: null, filename: 'source.png', kind: 'image', media_type: 'image/png', size: 32, version: 2, sha256: 'a'.repeat(64), created_at: '', updated_at: '' };
  const client = { list: vi.fn().mockResolvedValue({ items: [document, other] }), get: vi.fn().mockImplementation(async (id: string) => id === other.id ? other : document), storyboardGet: vi.fn().mockResolvedValue(receipt), storyboardBindImage: vi.fn(), storyboardApprove: vi.fn(), create: vi.fn(), update: vi.fn() };
  const studio = { asset: vi.fn(), assets: vi.fn(), download: vi.fn() }, production = { providers: vi.fn(), create: vi.fn(), execute: vi.fn(), review: vi.fn() };
  const props: StudioStoryboardAssetHandoffProps = { client: client as unknown as StudioStoryboardAssetHandoffProps['client'], studio: studio as unknown as StudioStoryboardAssetHandoffProps['studio'], production: production as unknown as StudioStoryboardAssetHandoffProps['production'], exactImage: { id: 'intent', reference: { asset_id: asset.id, version: asset.version, digest: asset.sha256 }, readAsset: vi.fn().mockResolvedValue(asset) }, active: true, editable: true, busy: false, isBusy: () => false, isCurrent: () => true, perform: work => work(), onDirtyChange: vi.fn(), onDenied: vi.fn(), onClose: vi.fn() };
  const view = render(<StudioStoryboardAssetHandoff {...props} />);
  return { ...view, props, client, studio, production, rerenderProps: (next: StudioStoryboardAssetHandoffProps) => view.rerender(<StudioStoryboardAssetHandoff {...next} />) };
}
type State = ReturnType<typeof mount>;
const button = (name: string) => screen.getByRole('button', { name }) as HTMLButtonElement;
async function loadList() { fireEvent.click(button('读取已有分镜文档目录')); await screen.findByRole('option', { name: 'Private existing storyboard A · v4' }); }
function choose(id: string) { fireEvent.change(screen.getByLabelText('已有分镜文档'), { target: { value: id } }); }
function noWrites(s: State) { for (const name of ['storyboardBindImage', 'storyboardApprove', 'create', 'update'] as const) expect(s.client[name]).not.toHaveBeenCalled(); for (const mock of Object.values(s.production)) expect(mock).not.toHaveBeenCalled(); }
function retire(s: State, change: string) {
  if (change === 'client ABA') { s.rerenderProps({ ...s.props, client: { ...s.props.client } }); s.rerenderProps(s.props); }
  if (change === 'studio ABA') { s.rerenderProps({ ...s.props, studio: { ...s.props.studio } }); s.rerenderProps(s.props); }
  if (change === 'intent ABA') { s.rerenderProps({ ...s.props, exactImage: { ...s.props.exactImage, id: 'replacement' } }); s.rerenderProps(s.props); }
  if (change === 'permission ABA') { s.rerenderProps({ ...s.props, editable: false }); s.rerenderProps(s.props); }
  if (change === 'active ABA') { s.rerenderProps({ ...s.props, active: false }); s.rerenderProps(s.props); }
  if (change === 'busy ABA') { s.rerenderProps({ ...s.props, busy: true }); s.rerenderProps(s.props); }
  if (change === 'owner ABA') { let available = false; const props = { ...s.props, isCurrent: () => available }; s.rerenderProps(props); available = true; s.rerenderProps(props); }
  if (change === 'owner') s.rerenderProps({ ...s.props, isCurrent: () => false });
  if (change === 'unmount') s.unmount();
}
afterEach(cleanup);
describe('direct existing-storyboard recipient wrapper fences', () => {
  it.each(['client ABA', 'studio ABA', 'intent ABA', 'permission ABA', 'active ABA', 'busy ABA', 'owner', 'owner ABA', 'unmount'])('blocks retained directory/document reads and select after %s, hiding cached titles', async change => {
    const s = mount(); await loadList(); choose(document.id);
    const readList = retained(button('读取已有分镜文档目录')).onClick, readDocument = retained(button('核对所选分镜文档')).onClick, select = retained(screen.getByLabelText('已有分镜文档')).onChange;
    s.client.list.mockClear(); s.client.get.mockClear(); retire(s, change);
    act(() => { readList(); readDocument(); select({ target: { value: other.id } }); readDocument(); });
    await act(async () => {});
    expect(s.client.list).not.toHaveBeenCalled(); expect(s.client.get).not.toHaveBeenCalled();
    expect(screen.queryByText(/Private existing storyboard A/)).toBeNull(); expect(window.document.body.textContent).not.toContain(document.title); expect(screen.queryByText(/Private existing storyboard B/)).toBeNull();
    expect(screen.queryByRole('combobox', { name: '已有分镜文档' })).toBeNull(); noWrites(s);
  });
  it.each(['selection change', 'selection ABA'])('blocks retained read/select closures after %s without extra GETs', async change => {
    const s = mount(); await loadList(); choose(document.id);
    const oldList = retained(button('读取已有分镜文档目录')).onClick, oldRead = retained(button('核对所选分镜文档')).onClick, oldSelect = retained(screen.getByLabelText('已有分镜文档')).onChange;
    choose(other.id); if (change === 'selection ABA') choose(document.id);
    const selected = (screen.getByLabelText('已有分镜文档') as HTMLSelectElement).value; s.client.list.mockClear(); s.client.get.mockClear();
    act(() => { oldSelect({ target: { value: 'unreviewed-target' } }); oldList(); oldRead(); }); await act(async () => {});
    expect((screen.getByLabelText('已有分镜文档') as HTMLSelectElement).value).toBe(selected); expect(s.client.list).not.toHaveBeenCalled(); expect(s.client.get).not.toHaveBeenCalled(); noWrites(s);
    // A fresh explicit action still reads the latest selected document once.
    fireEvent.click(button('核对所选分镜文档')); await screen.findByRole('button', { name: '读取已有分镜回执' }); expect(s.client.get).toHaveBeenCalledTimes(1); expect(s.client.get).toHaveBeenCalledWith(selected);
  });
  it.each(['client ABA', 'permission ABA', 'intent ABA', 'owner', 'owner ABA'])('removes adopted document metadata after %s and does not revive it', async change => {
    const s = mount(); await loadList(); choose(document.id); fireEvent.click(button('核对所选分镜文档')); await screen.findByText('目标：Private existing storyboard A · v4');
    const readReceipt = retained(button('读取已有分镜回执')).onClick, inspectSource = retained(button('核对传入图片精确版本')).onClick;
    retire(s, change); act(() => { readReceipt(); inspectSource(); }); await act(async () => {});
    expect(screen.queryByText(/Private existing storyboard A/)).toBeNull(); expect(screen.queryByText(new RegExp(s.props.exactImage.reference.digest))).toBeNull();
    expect(s.client.storyboardGet).not.toHaveBeenCalled(); expect(s.props.exactImage.readAsset).not.toHaveBeenCalled(); noWrites(s);
  });
  for (const phase of ['directory', 'document'] as const) it.each(['client ABA', 'permission ABA', 'owner', 'owner ABA', 'unmount'])(`drops delayed ${phase} response after %s`, async change => {
    const s = mount(), delayed = deferred<any>();
    if (phase === 'directory') { s.client.list.mockReturnValue(delayed.promise); fireEvent.click(button('读取已有分镜文档目录')); }
    else { await loadList(); choose(document.id); s.client.get.mockReturnValue(delayed.promise); fireEvent.click(button('核对所选分镜文档')); }
    retire(s, change); await act(async () => { delayed.resolve(phase === 'directory' ? { items: [document] } : document); await delayed.promise; });
    expect(screen.queryByText(/Private existing storyboard A/)).toBeNull(); expect(screen.queryByRole('button', { name: '读取已有分镜回执' })).toBeNull(); noWrites(s);
  });

  it('checks synchronous external busy ownership before retained directory/read/select calls without rerender', async () => {
    const s = mount(); let busy = false; const props = { ...s.props, isBusy: () => busy }; s.rerenderProps(props);
    await loadList(); choose(document.id);
    const readList = retained(button('读取已有分镜文档目录')).onClick, readDocument = retained(button('核对所选分镜文档')).onClick, select = retained(screen.getByLabelText('已有分镜文档')).onChange;
    s.client.list.mockClear(); s.client.get.mockClear(); busy = true;
    act(() => { select({ target: { value: other.id } }); readList(); readDocument(); }); await act(async () => {});
    expect((screen.getByLabelText('已有分镜文档') as HTMLSelectElement).value).toBe(document.id); expect(s.client.list).not.toHaveBeenCalled(); expect(s.client.get).not.toHaveBeenCalled(); noWrites(s);
  });

  it('does not retire merely because the owner callback identity changes while authority stays true', async () => {
    const s = mount(); await loadList(); choose(document.id); s.rerenderProps({ ...s.props, isCurrent: () => true });
    expect(screen.getByRole('option', { name: 'Private existing storyboard A · v4' })).toBeTruthy();
    fireEvent.click(button('核对所选分镜文档')); await screen.findByText('目标：Private existing storyboard A · v4'); expect(s.client.get).toHaveBeenCalledTimes(1); noWrites(s);
  });

  it.each(['directory', 'document'] as const)('allows closing a retired pending %s read before its late response arrives', async phase => {
    const s = mount(), delayed = deferred<any>();
    if (phase === 'directory') { s.client.list.mockReturnValue(delayed.promise); fireEvent.click(button('读取已有分镜文档目录')); }
    else { await loadList(); choose(document.id); s.client.get.mockReturnValue(delayed.promise); fireEvent.click(button('核对所选分镜文档')); }
    expect(button('关闭分镜图片接收器').disabled).toBe(true);
    retire(s, 'owner ABA');
    expect(window.document.body.textContent).not.toContain(document.title); expect(screen.queryByRole('combobox', { name: '已有分镜文档' })).toBeNull();
    // The obsolete request is still unresolved. Its spinner cannot trap the user.
    expect(button('关闭分镜图片接收器').disabled).toBe(false); fireEvent.click(button('关闭分镜图片接收器'));
    expect(s.props.onClose).toHaveBeenCalledTimes(1); noWrites(s);
    await act(async () => { delayed.resolve(phase === 'directory' ? { items: [document] } : document); await delayed.promise; });
    expect(window.document.body.textContent).not.toContain(document.title); expect(screen.queryByRole('button', { name: '读取已有分镜回执' })).toBeNull();
    expect(button('关闭分镜图片接收器').disabled).toBe(false); expect(s.props.onClose).toHaveBeenCalledTimes(1); noWrites(s);
  });
});
