// @vitest-environment jsdom
import { useState } from 'react';
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CreativeCanvas } from './CreativeCanvas';
import { useStoryboardBoardImages } from './useStoryboardBoardImages';
import { loadStoryboardImage, readStoryboardImageReceipt, StoryboardImageError, type StoryboardImageAccess } from './storyboardImagePreview';
import { newDocument, newScene, newShot, type CreativeDocument } from './types';
import type { StoryboardReceipt } from './studioStoryboardContract';
import { ApiError } from '../api';
import { useLocalHostSession } from '../localHostSession';
import { useStudio } from '../store';
vi.mock('./storyboardImagePreview', async original => ({ ...await original<typeof import('./storyboardImagePreview')>(), loadStoryboardImage: vi.fn(), readStoryboardImageReceipt: vi.fn() }));
// These tests exercise UI ownership/lifecycle; raster and browser decode are separate checks.
function fixture(count = 7) {
  const document: CreativeDocument = { ...newDocument('STORYBOARD'), id: 'board', version: 3, status: 'DRAFT', actor_id: 'author', created_at: '', updated_at: '', source_evidence: {}, source_independent: true,
    scenes: [{ ...newScene(1), id: 'scene', heading: 'Saved scene' }], shots: Array.from({ length: count }, (_, i) => ({ ...newShot(i + 1, 'scene'), id: `shot-${i + 1}`, frame_prompt: `Saved frame ${i + 1}`, action: `Saved action ${i + 1}` })) };
  const receipt: StoryboardReceipt = { contract: 'studio-storyboard/1', document_snapshot: { id: document.id, version: document.version, digest: 'a'.repeat(64) }, content_digest: 'b'.repeat(64), approved: false, director_sources: [], model_called: false, product_acceptance: 'LOCAL_REQUIRED',
    shots: document.shots.map(shot => ({ shot_id: shot.id, shot_version: 2, shot_digest: 'c'.repeat(64), shot, image_asset: { asset_id: `image-${shot.id}`, version: 1, digest: 'd'.repeat(64), kind: 'image' } })) };
  const access: StoryboardImageAccess = { document, projectId: 'project', branchId: null, available: true, client: { get: vi.fn(), storyboardGet: vi.fn() }, studio: { asset: vi.fn(), downloadBounded: vi.fn() }, isCurrent: () => true, read: async work => work(), onDenied: vi.fn() };
  return { document, receipt, access };
}
let createUrl: ReturnType<typeof vi.fn>, revokeUrl: ReturnType<typeof vi.fn>;
beforeEach(() => {
  let id = 0; createUrl = vi.fn(() => `blob:verified-${++id}`); revokeUrl = vi.fn();
  vi.stubGlobal('URL', class extends URL { static createObjectURL = createUrl; static revokeObjectURL = revokeUrl; });
  vi.mocked(loadStoryboardImage).mockResolvedValue(new Blob(['derived only'], { type: 'image/png' }));
});
afterEach(async () => { cleanup(); await act(async () => { await Promise.resolve(); }); vi.clearAllMocks(); vi.unstubAllGlobals(); });
function mount(count = 7) {
  const f = fixture(count); vi.mocked(readStoryboardImageReceipt).mockResolvedValue(f.receipt);
  const props = { access: f.access, active: true, dirty: false, busy: false, selectedId: 'shot-1' };
  const view = renderHook(p => useStoryboardBoardImages(p), { initialProps: props }); return { ...f, props, ...view };
}
const complete = async (count: number) => waitFor(() => expect(loadStoryboardImage).toHaveBeenCalledTimes(count));
describe('original board image window', () => {
  it('does no reads before opt-in, bounds six cards plus one comparison, and releases every URL', async () => {
    const f = mount(); expect(readStoryboardImageReceipt).not.toHaveBeenCalled(); expect(loadStoryboardImage).not.toHaveBeenCalled();
    act(() => f.result.current.show()); await complete(7); await waitFor(() => expect(createUrl).toHaveBeenCalledTimes(7));
    expect(f.result.current.ids).toEqual(['shot-1', 'shot-2', 'shot-3', 'shot-4', 'shot-5', 'shot-6']);
    expect(vi.mocked(loadStoryboardImage).mock.calls.filter(call => call[3] === 320)).toHaveLength(6);
    expect(vi.mocked(loadStoryboardImage).mock.calls.filter(call => call[3] === 1024)).toHaveLength(1);
    act(() => f.result.current.hide()); expect(f.result.current.open).toBe(false); expect(new Set(revokeUrl.mock.calls.map(([url]) => url)).size).toBe(7);
  });
  it('changes page without preloading hidden cards or retaining old URLs', async () => {
    const f = mount(); act(() => f.result.current.show()); await waitFor(() => expect(createUrl).toHaveBeenCalledTimes(7));
    act(() => f.result.current.go(1)); expect(revokeUrl).toHaveBeenCalledTimes(7); await complete(8);
    expect(f.result.current.ids).toEqual(['shot-7']); expect(f.result.current.selected).toBeUndefined(); expect(f.result.current.comparison).toBeUndefined();
  });
  it('deduplicates thumbnails by exact Asset pin, not by a video candidate', async () => {
    const f = mount(2); f.receipt.shots[1].image_asset = { ...f.receipt.shots[0].image_asset! };
    f.receipt.shots[0].video_result = { asset: { asset_id: 'video', version: 9, digest: 'e'.repeat(64), kind: 'video' }, job: { id: 'job', version: 1, request_digest: 'f'.repeat(64), receipt_digest: 'f'.repeat(64) }, source_shot: { document_snapshot: f.receipt.document_snapshot, shot_id: 'shot-1', shot_version: 2, shot_digest: 'c'.repeat(64) } };
    act(() => f.result.current.show()); await waitFor(() => expect(createUrl).toHaveBeenCalledTimes(2));
    expect(loadStoryboardImage).toHaveBeenCalledTimes(2); expect(f.result.current.thumbnail('shot-1')?.url).toBe(f.result.current.thumbnail('shot-2')?.url);
    expect(vi.mocked(loadStoryboardImage).mock.calls[0][2].image_asset!.asset_id).toBe('image-shot-1');
  });
  it('serializes all renders; repeated selection never starts a second concurrent decode', async () => {
    const f = mount(3); let running = 0, maximum = 0;
    vi.mocked(loadStoryboardImage).mockImplementation(async () => { maximum = Math.max(maximum, ++running); await new Promise(resolve => setTimeout(resolve, 3)); running--; return new Blob(['bounded']); });
    act(() => { f.result.current.show(); f.result.current.show(); });
    await waitFor(() => expect(createUrl).toHaveBeenCalledTimes(4)); expect(maximum).toBe(1); expect(readStoryboardImageReceipt).toHaveBeenCalledTimes(1);
    f.rerender({ ...f.props, selectedId: 'shot-2' }); await waitFor(() => expect(createUrl).toHaveBeenCalledTimes(5)); expect(maximum).toBe(1);
  });
  it.each(['dirty', 'inactive', 'document', 'client', 'denied', 'permission ABA', 'host', 'unmount'] as const)('discards a late result and closes preview after %s', async change => {
    const f = mount(1); let done!: (value: Blob) => void;
    vi.mocked(loadStoryboardImage).mockImplementation(() => new Promise(resolve => { done = resolve; }));
    act(() => f.result.current.show()); await complete(1);
    if (change === 'dirty') f.rerender({ ...f.props, dirty: true });
    if (change === 'inactive') f.rerender({ ...f.props, active: false });
    if (change === 'document') f.rerender({ ...f.props, access: { ...f.access, document: { ...f.document, version: 4 } } });
    if (change === 'client') f.rerender({ ...f.props, access: { ...f.access, client: { ...f.access.client } } });
    if (change === 'denied' || change === 'permission ABA') { f.rerender({ ...f.props, access: { ...f.access, available: false } }); if (change === 'permission ABA') f.rerender(f.props); }
    if (change === 'host') { f.access.isCurrent = () => false; act(() => useLocalHostSession.setState({ epoch: useLocalHostSession.getState().epoch + 1 })); f.access.isCurrent = () => true; }
    if (change === 'unmount') f.unmount();
    await act(async () => done(new Blob(['late private result']))); expect(createUrl).not.toHaveBeenCalled();
    if (change !== 'unmount') expect(f.result.current.open).toBe(false);
  });
  it('clears an old comparison synchronously when selection changes and rejects a late A-B-A result', async () => {
    const f = mount(2); let done!: (value: Blob) => void;
    vi.mocked(loadStoryboardImage).mockImplementation(async (_a, _r, _s, size) => size === 1024 ? new Promise(resolve => { done = resolve; }) : new Blob(['thumb']));
    act(() => f.result.current.show()); await complete(3);
    f.rerender({ ...f.props, selectedId: 'shot-2' }); expect(f.result.current.comparison?.url).toBeUndefined();
    f.rerender(f.props); await act(async () => done(new Blob(['old A']))); expect(createUrl).toHaveBeenCalledTimes(2);
    await complete(4); await act(async () => done(new Blob(['new A']))); await waitFor(() => expect(createUrl).toHaveBeenCalledTimes(3));
  });
  it('denial invokes the original host lock and never displays the failed result', async () => {
    const f = mount(1); vi.mocked(loadStoryboardImage).mockRejectedValue(new ApiError({ status: 403, code: 'DENIED', message: 'private' }));
    act(() => f.result.current.show()); await waitFor(() => expect(f.access.onDenied).toHaveBeenCalledTimes(1)); expect(f.result.current.open).toBe(false); expect(createUrl).not.toHaveBeenCalled();
  });
  it.each([
    new ApiError({ status: 404, code: 'UNAVAILABLE', message: 'private' }),
    new ApiError({ status: 409, code: 'STALE', message: 'changed' }),
    new StoryboardImageError('ASSET_CHANGED', 'Changed Asset'),
    new StoryboardImageError('SOURCE_CHANGED', 'Changed source'),
    new StoryboardImageError('INTEGRITY', 'Changed bytes'),
    new StoryboardImageError('TIMEOUT', 'Read timeout'),
  ])('revokes a ready thumbnail when the comparison recheck fails closed: %s', async reason => {
    const f = mount(1); let reject!: (reason: unknown) => void;
    vi.mocked(loadStoryboardImage).mockImplementation(async (_a, _r, _s, size) => size === 320 ? new Blob(['thumbnail']) : new Promise((_resolve, fail) => { reject = fail; }));
    act(() => f.result.current.show()); await complete(2);
    expect(f.result.current.thumbnail('shot-1')?.url).toBe('blob:verified-1');
    await act(async () => reject(reason));
    expect(f.result.current.open).toBe(false); expect(f.result.current.receipt).toBeUndefined(); expect(f.result.current.comparison).toBeUndefined();
    expect(revokeUrl).toHaveBeenCalledWith('blob:verified-1');
  });
  it('synchronously revokes cached images on a real store identity ABA before React replaces the owner', async () => {
    const previous = useStudio.getState(); const f = mount(1);
    act(() => f.result.current.show()); await waitFor(() => expect(createUrl).toHaveBeenCalledTimes(2));
    act(() => { useStudio.setState({ sessionToken: 'different-scoped-session' }); useStudio.setState({ sessionToken: previous.sessionToken }); });
    expect(f.access.isCurrent()).toBe(true); expect(f.result.current.open).toBe(false); expect(f.result.current.canStart).toBe(false);
    expect(revokeUrl).toHaveBeenCalledTimes(2); act(() => f.result.current.show()); expect(loadStoryboardImage).toHaveBeenCalledTimes(2);
  });
  it('rejects a late result on a real store identity ABA even when the external current callback stays true', async () => {
    const previous = useStudio.getState(), f = mount(1); let done!: (value: Blob) => void;
    vi.mocked(loadStoryboardImage).mockImplementation(() => new Promise(resolve => { done = resolve; }));
    act(() => f.result.current.show()); await complete(1);
    act(() => { useStudio.setState({ novelId: 'other-project' }); useStudio.setState({ novelId: previous.novelId }); });
    await act(async () => done(new Blob(['late']))); expect(createUrl).not.toHaveBeenCalled(); expect(f.result.current.open).toBe(false);
  });
  it('removes already visible data on blur; focus does not silently re-download', async () => {
    const f = mount(1); act(() => f.result.current.show()); await waitFor(() => expect(createUrl).toHaveBeenCalledTimes(2));
    act(() => window.dispatchEvent(new Event('blur'))); expect(f.result.current.open).toBe(false); expect(revokeUrl).toHaveBeenCalledTimes(2);
    act(() => window.dispatchEvent(new Event('focus'))); expect(loadStoryboardImage).toHaveBeenCalledTimes(2);
  });
});
describe('existing CreativeCanvas integration, without browser visual acceptance', () => {
  it('renders actual image elements on existing cards and compares saved text while preserving read-only authoring', async () => {
    const f = fixture(2); f.receipt.shots[1].image_asset = null; vi.mocked(readStoryboardImageReceipt).mockResolvedValue(f.receipt);
    const changed = vi.fn();
    function Harness() { const [selected, pick] = useState('shot-1'); return <CreativeCanvas draft={f.document} storyboardImages={f.access} version={3} dirty={false} canEdit={false} busy={false} selectedShotId={selected} onShot={pick} onScene={vi.fn()} onChange={changed} onSave={vi.fn()} onNew={vi.fn()} />; }
    render(<Harness />); expect(screen.queryByRole('img')).toBeNull();
    const show = screen.getByRole('button', { name: '显示已保存分镜图片' }); expect((show as HTMLButtonElement).disabled).toBe(false); expect(show.closest('fieldset')?.disabled).not.toBe(true);
    fireEvent.click(show); await waitFor(() => expect(screen.getAllByRole('img')).toHaveLength(2));
    const comparison = screen.getByLabelText('已保存镜头图文比较'); expect(within(comparison).getByText('Saved frame 1')).toBeTruthy(); expect(within(comparison).getByText('Saved action 1')).toBeTruthy();
    expect(screen.getAllByLabelText('分镜画布')).toHaveLength(1); expect(screen.getByLabelText('画面描述').closest('fieldset')?.disabled).toBe(true);
    expect(screen.getByRole('button', { name: '后移镜头 1' }).hasAttribute('disabled')).toBe(true); expect(screen.getByText('未绑定正式图片')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /SHOT 02/ })); expect(within(comparison).getByText('Saved frame 2')).toBeTruthy(); expect(within(comparison).queryByRole('img')).toBeNull(); expect(changed).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: /^镜头列表$/ })); expect(screen.queryByRole('img')).toBeNull(); expect(revokeUrl).toHaveBeenCalledTimes(2);
  });
});
