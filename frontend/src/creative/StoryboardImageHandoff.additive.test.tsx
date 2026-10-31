// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { useStoryboardProductionController, type StoryboardProductionProps } from './useStoryboardProductionController';
import type { CreativeDocument } from './types';
import type { StudioAsset } from './studioClient';
import { checkedStoryboardReceipt, type StoryboardReceipt } from './studioStoryboardContract';
import fixture from './fixtures/phase4.file-api-storyboard.json';
const clone = <T,>(value: T): T => structuredClone(value);
const deferred = <T,>() => { let resolve!: (value: T) => void; const promise = new Promise<T>(yes => { resolve = yes; }); return { promise, resolve }; };
const doc = (r: StoryboardReceipt): CreativeDocument => ({ id: r.document_snapshot.id, version: r.document_snapshot.version, mode: 'STORYBOARD', title: 'Existing storyboard', status: 'DRAFT', created_at: '', updated_at: '', actor_id: 'author', source_evidence: {}, source_chapter_ids: [], source_independent: true, scenes: [], director_notes: [], shots: r.shots.map(s => clone(s.shot)), video_plan: null });
function setup() {
  const initial = checkedStoryboardReceipt(clone(fixture));
  const asset: StudioAsset = { id: 'new-image', novel_id: 'project', branch_id: null, filename: 'new.png', kind: 'image', media_type: 'image/png', size: 32, version: 3, sha256: 'a'.repeat(64), created_at: '', updated_at: '' };
  const pin = { asset_id: asset.id, version: asset.version, digest: asset.sha256, kind: 'image' as const };
  const next = { ...clone(initial), approved: false, document_snapshot: { ...initial.document_snapshot, version: initial.document_snapshot.version + 1 }, shots: initial.shots.map((s, i) => i ? clone(s) : { ...clone(s), image_asset: pin }) };
  const client = { storyboardGet: vi.fn().mockResolvedValue(initial), storyboardBindImage: vi.fn().mockResolvedValue(next), get: vi.fn().mockResolvedValue(doc(next)), storyboardApprove: vi.fn(), storyboardImageRequest: vi.fn(), storyboardVideoRequest: vi.fn(), storyboardTimelineDraft: vi.fn(), storyboardTimelineCreate: vi.fn(), storyboardAdoptVideo: vi.fn(), update: vi.fn(), create: vi.fn() };
  const production = { providers: vi.fn(), create: vi.fn(), execute: vi.fn(), review: vi.fn(), preview: vi.fn(), timelineList: vi.fn() };
  const studio = { assets: vi.fn(), asset: vi.fn(), download: vi.fn() }, readAsset = vi.fn().mockResolvedValue(asset);
  const props: StoryboardProductionProps = { document: doc(initial), client: client as unknown as StoryboardProductionProps['client'], studio: studio as unknown as StoryboardProductionProps['studio'], production: production as unknown as StoryboardProductionProps['production'], active: true, editable: true, busy: false, isBusy: () => false, isCurrent: () => true, perform: work => work(), onDocument: vi.fn(), onDenied: vi.fn(), onDirtyChange: vi.fn(), exactImage: { id: 'intent', reference: pin, readAsset } };
  const view = renderHook(useStoryboardProductionController, { initialProps: props });
  return { ...view, props, initial, next, asset, pin, client, studio, production, readAsset };
}
type State = ReturnType<typeof setup>;
async function settle(s: State) { await waitFor(() => expect(s.result.current.loading).toBe('')); }
async function prepare(s: State) {
  act(() => s.result.current.read()); await settle(s);
  expect(s.result.current.selectedId).toBe('');
  act(() => s.result.current.select(s.initial.shots[0].shot_id));
  act(() => s.result.current.inspectExactImage()); await settle(s);
  expect(s.result.current.exactSource).toEqual(s.asset);
}
function noOtherWrites(s: State) {
  for (const [key, value] of Object.entries(s.client)) if (!['storyboardGet', 'storyboardBindImage', 'get'].includes(key)) expect(value).not.toHaveBeenCalled();
  for (const value of Object.values(s.production)) expect(value).not.toHaveBeenCalled();
  for (const value of Object.values(s.studio)) expect(value).not.toHaveBeenCalled();
}
afterEach(cleanup);
describe('exact image handoff through original storyboard controller', () => {
  it('reads only until explicit bind, then preserves shot bodies, exact pin, v+1 and revoked approval', async () => {
    const s = setup(); expect(s.client.storyboardGet).not.toHaveBeenCalled(); expect(s.readAsset).not.toHaveBeenCalled();
    act(() => s.result.current.bindExactImage()); expect(s.client.storyboardBindImage).not.toHaveBeenCalled();
    await prepare(s); expect(s.client.storyboardBindImage).not.toHaveBeenCalled(); expect(s.props.onDocument).not.toHaveBeenCalled(); noOtherWrites(s);
    act(() => { s.result.current.bindExactImage(); s.result.current.bindExactImage(); }); await settle(s);
    expect(s.readAsset).toHaveBeenCalledTimes(2); expect(s.client.storyboardGet).toHaveBeenCalledTimes(2);
    expect(s.client.storyboardBindImage).toHaveBeenCalledTimes(1); expect(s.client.storyboardBindImage).toHaveBeenCalledWith(s.initial, s.initial.shots[0], s.pin);
    expect(s.client.get).toHaveBeenCalledTimes(1); expect(s.client.get).toHaveBeenCalledWith(s.initial.document_snapshot.id); expect(s.props.onDocument).toHaveBeenCalledTimes(1); expect(s.props.onDocument).toHaveBeenCalledWith(doc(s.next));
    s.rerender({ ...s.props, document: doc(s.next) }); expect(s.result.current.receipt).toEqual(s.next); expect(s.next.shots.map(row => row.shot)).toEqual(s.initial.shots.map(row => row.shot));
    act(() => s.result.current.bindExactImage()); expect(s.client.storyboardBindImage).toHaveBeenCalledTimes(1); noOtherWrites(s);
  });
  it.each([{ id: 'wrong' }, { kind: 'video' }, { kind: 'audio' }, { deleted_at: 'deleted' }, { version: 4 }, { sha256: 'b'.repeat(64) }, { manual_mask: {} }, { media_type: 'video/mp4' }])('rejects changed authoritative source %j before POST', async patch => {
    const s = setup(); await prepare(s); s.readAsset.mockResolvedValue({ ...s.asset, ...patch });
    act(() => s.result.current.bindExactImage()); await settle(s); expect(s.client.storyboardBindImage).not.toHaveBeenCalled(); expect(s.props.onDocument).not.toHaveBeenCalled(); noOtherWrites(s);
  });
  it.each(['document', 'digest', 'shot', 'approval', 'missing shot'] as const)('rejects target change: %s', async change => {
    const s = setup(); await prepare(s); const next = clone(s.initial);
    if (change === 'document') next.document_snapshot.version++;
    if (change === 'digest') next.content_digest = 'b'.repeat(64);
    if (change === 'shot') next.shots[0].shot.action = 'changed';
    if (change === 'approval') next.approved = !next.approved;
    if (change === 'missing shot') next.shots = [];
    s.client.storyboardGet.mockResolvedValue(next); act(() => s.result.current.bindExactImage()); await settle(s);
    expect(s.client.storyboardBindImage).not.toHaveBeenCalled(); expect(s.props.onDocument).not.toHaveBeenCalled();
  });
  for (const phase of ['source', 'target'] as const) it.each(['permission ABA', 'busy ABA', 'client ABA', 'request ABA', 'document ABA', 'inactive ABA', 'owner', 'owner ABA', 'unmount'] as const)(`fences delayed ${phase} read after %s`, async change => {
    const s = setup(); await prepare(s); const pending = deferred<any>();
    if (phase === 'source') s.readAsset.mockReturnValue(pending.promise); else s.client.storyboardGet.mockReturnValue(pending.promise);
    act(() => s.result.current.bindExactImage()); if (phase === 'target') await waitFor(() => expect(s.client.storyboardGet).toHaveBeenCalledTimes(2));
    if (change === 'permission ABA') { s.rerender({ ...s.props, editable: false }); s.rerender(s.props); }
    if (change === 'busy ABA') { s.rerender({ ...s.props, busy: true }); s.rerender(s.props); }
    if (change === 'client ABA') { s.rerender({ ...s.props, client: { ...s.props.client } }); s.rerender(s.props); }
    if (change === 'request ABA') { s.rerender({ ...s.props, exactImage: { ...s.props.exactImage!, id: 'replacement' } }); s.rerender(s.props); }
    if (change === 'document ABA') { s.rerender({ ...s.props, document: { ...s.props.document, id: 'other' } }); s.rerender(s.props); }
    if (change === 'inactive ABA') { s.rerender({ ...s.props, active: false }); s.rerender(s.props); }
    if (change === 'owner ABA') { let available = false; const props = { ...s.props, isCurrent: () => available }; s.rerender(props); available = true; s.rerender(props); }
    if (change === 'owner') s.rerender({ ...s.props, isCurrent: () => false });
    if (change === 'unmount') s.unmount();
    await act(async () => { pending.resolve(phase === 'source' ? s.asset : s.initial); await pending.promise; });
    expect(s.client.storyboardBindImage).not.toHaveBeenCalled(); expect(s.props.onDocument).not.toHaveBeenCalled(); noOtherWrites(s);
  });
  it.each(['network', 'server', 'bad receipt', 'refresh'] as const)('locks UNKNOWN %s and reconciles authoritatively without another POST', async failure => {
    const s = setup(); await prepare(s);
    if (failure === 'network') s.client.storyboardBindImage.mockRejectedValue(new TypeError('offline'));
    if (failure === 'server') s.client.storyboardBindImage.mockRejectedValue(new ApiError({ status: 503, code: 'UNAVAILABLE', message: 'unavailable' }));
    if (failure === 'bad receipt') s.client.storyboardBindImage.mockResolvedValue({ ...s.next, approved: true });
    if (failure === 'refresh') s.client.get.mockRejectedValueOnce(new Error('refresh failed'));
    act(() => s.result.current.bindExactImage()); await settle(s);
    expect(s.result.current.uncertain).toBe(true); expect(s.result.current.exactPending).toBe(true); expect(s.props.onDocument).not.toHaveBeenCalled();
    act(() => { s.result.current.bindExactImage(); s.result.current.read(); s.result.current.inspectExactImage(); }); await settle(s);
    expect(s.client.storyboardBindImage).toHaveBeenCalledTimes(1); s.client.storyboardGet.mockResolvedValue(s.next);
    act(() => s.result.current.inspectExactAttempt()); await settle(s);
    expect(s.props.onDocument).not.toHaveBeenCalled(); expect(s.result.current.error).toMatch(/无法确认/); expect(s.result.current.exactPending).toBe(true); expect(s.result.current.uncertain).toBe(true);
    expect(s.client.storyboardBindImage).toHaveBeenCalledTimes(1); noOtherWrites(s);
  });
  it('keeps an unresolved attempt locked even when current server version is unchanged', async () => {
    const s = setup(); await prepare(s); s.client.storyboardBindImage.mockRejectedValue(new Error('lost response'));
    act(() => s.result.current.bindExactImage()); await settle(s); s.client.get.mockResolvedValue(doc(s.initial));
    act(() => s.result.current.inspectExactAttempt()); await settle(s); expect(s.result.current.exactPending).toBe(true); expect(s.result.current.uncertain).toBe(true); expect(s.props.onDocument).not.toHaveBeenCalled();
    act(() => s.result.current.bindExactImage()); expect(s.client.storyboardBindImage).toHaveBeenCalledTimes(1);
  });
  it('denied private source never reaches target mutation', async () => {
    const s = setup(); await prepare(s); s.readAsset.mockRejectedValue(new ApiError({ status: 403, code: 'FORBIDDEN', message: 'denied' }));
    act(() => s.result.current.bindExactImage()); await settle(s); expect(s.props.onDenied).toHaveBeenCalledOnce(); expect(s.client.storyboardBindImage).not.toHaveBeenCalled();
  });

  it.each(['document id', 'document version', 'shot version', 'shot digest', 'shot body', 'asset id', 'asset version', 'asset digest', 'approved'] as const)('never adopts an invalid post-save receipt: %s', async change => {
    const s = setup(); await prepare(s); const next = clone(s.next);
    if (change === 'document id') next.document_snapshot.id = 'wrong';
    if (change === 'document version') next.document_snapshot.version++;
    if (change === 'shot version') next.shots[0].shot_version++;
    if (change === 'shot digest') next.shots[0].shot_digest = 'b'.repeat(64);
    if (change === 'shot body') next.shots[0].shot.action = 'unexpected rewrite';
    if (change === 'asset id') next.shots[0].image_asset!.asset_id = 'wrong';
    if (change === 'asset version') next.shots[0].image_asset!.version++;
    if (change === 'asset digest') next.shots[0].image_asset!.digest = 'b'.repeat(64);
    if (change === 'approved') next.approved = true;
    s.client.storyboardBindImage.mockResolvedValue(next); act(() => s.result.current.bindExactImage()); await settle(s);
    expect(s.props.onDocument).not.toHaveBeenCalled(); expect(s.result.current.exactPending).toBe(true); expect(s.result.current.uncertain).toBe(true);
    act(() => s.result.current.bindExactImage()); expect(s.client.storyboardBindImage).toHaveBeenCalledTimes(1); noOtherWrites(s);
  });
  it.each(['version', 'id', 'mode'] as const)('rejects mismatched post-commit document refresh %s without retry', async change => {
    const s = setup(); await prepare(s); const document = doc(s.next);
    if (change === 'version') document.version++;
    if (change === 'id') document.id = 'wrong';
    if (change === 'mode') document.mode = 'DIRECTOR';
    s.client.get.mockResolvedValue(document); act(() => s.result.current.bindExactImage()); await settle(s);
    expect(s.result.current.exactPending).toBe(true); expect(s.props.onDocument).not.toHaveBeenCalled();
    act(() => s.result.current.bindExactImage()); expect(s.client.storyboardBindImage).toHaveBeenCalledTimes(1);
  });
  it.each(['permission ABA', 'request ABA', 'shot ABA'] as const)('rejects retained acceptance callback after %s', async change => {
    const s = setup(); await prepare(s); const accept = s.result.current.bindExactImage;
    if (change === 'permission ABA') { s.rerender({ ...s.props, editable: false }); s.rerender(s.props); }
    if (change === 'request ABA') { s.rerender({ ...s.props, exactImage: { ...s.props.exactImage!, id: 'other' } }); s.rerender(s.props); }
    if (change === 'shot ABA') act(() => { s.result.current.select(s.initial.shots[1].shot_id); s.result.current.select(s.initial.shots[0].shot_id); });
    act(() => accept()); await settle(s); expect(s.client.storyboardBindImage).not.toHaveBeenCalled();
  });
  it.each(['unmount', 'permission', 'owner', 'owner ABA'] as const)('does not adopt delayed POST success after %s', async change => {
    const s = setup(); await prepare(s); const delayed = deferred<StoryboardReceipt>(); s.client.storyboardBindImage.mockReturnValue(delayed.promise);
    act(() => s.result.current.bindExactImage()); await waitFor(() => expect(s.client.storyboardBindImage).toHaveBeenCalledTimes(1));
    if (change === 'unmount') s.unmount();
    if (change === 'permission') s.rerender({ ...s.props, editable: false });
    if (change === 'owner ABA') { let available = false; const props = { ...s.props, isCurrent: () => available }; s.rerender(props); available = true; s.rerender(props); }
    if (change === 'owner') s.rerender({ ...s.props, isCurrent: () => false });
    await act(async () => { delayed.resolve(s.next); await delayed.promise; });
    expect(s.props.onDocument).not.toHaveBeenCalled(); expect(s.client.get).not.toHaveBeenCalled(); expect(s.client.storyboardBindImage).toHaveBeenCalledTimes(1);
  });
  it('blocks final-click admission while the shared host operation is already busy', async () => {
    const s = setup(); await prepare(s); s.rerender({ ...s.props, isBusy: () => true });
    act(() => s.result.current.bindExactImage()); expect(s.readAsset).toHaveBeenCalledTimes(1); expect(s.client.storyboardBindImage).not.toHaveBeenCalled();
  });
  it('allows only its own host operation lease during busy source and target reads', async () => {
    const s = setup(); await prepare(s); const delayed = deferred<StudioAsset>(); s.readAsset.mockReturnValue(delayed.promise);
    s.rerender({ ...s.props, ownsOperation: () => true }); act(() => s.result.current.bindExactImage());
    s.rerender({ ...s.props, busy: true, isBusy: () => true, ownsOperation: () => true });
    await act(async () => { delayed.resolve(s.asset); await delayed.promise; }); await settle(s);
    expect(s.client.storyboardBindImage).toHaveBeenCalledTimes(1); expect(s.props.onDocument).toHaveBeenCalledWith(doc(s.next));
  });

  it.each([{ id: 'wrong' }, { kind: 'video' }, { kind: 'audio' }, { deleted_at: 'deleted' }, { version: 4 }, { sha256: 'b'.repeat(64) }, { manual_mask: {} }, { media_type: 'text/plain' }])('rejects invalid source during initial inspection: %j', async patch => {
    const s = setup(); s.readAsset.mockResolvedValue({ ...s.asset, ...patch });
    act(() => s.result.current.inspectExactImage()); await settle(s); expect(s.result.current.exactSource).toBeUndefined();
    act(() => s.result.current.bindExactImage()); expect(s.client.storyboardBindImage).not.toHaveBeenCalled(); expect(s.client.storyboardGet).not.toHaveBeenCalled(); noOtherWrites(s);
  });
  it('inspecting a source does not imply selection of a document receipt or shot', async () => {
    const s = setup(); act(() => s.result.current.inspectExactImage()); await settle(s);
    expect(s.result.current.exactSource).toEqual(s.asset); expect(s.result.current.receipt).toBeUndefined(); expect(s.result.current.selectedId).toBe('');
    act(() => s.result.current.bindExactImage()); expect(s.client.storyboardGet).not.toHaveBeenCalled(); expect(s.client.storyboardBindImage).not.toHaveBeenCalled(); noOtherWrites(s);
  });

  it.each(['changed body', 'missing shot', 'reordered shots'] as const)('does not adopt same-id/version document whose shots mismatch the saved receipt: %s', async change => {
    const s = setup(); await prepare(s); const document = doc(s.next);
    if (change === 'changed body') document.shots[0].frame_prompt = 'unrelated text';
    if (change === 'missing shot') document.shots = document.shots.slice(1);
    if (change === 'reordered shots') document.shots.reverse();
    s.client.get.mockResolvedValue(document); act(() => s.result.current.bindExactImage()); await settle(s);
    expect(s.props.onDocument).not.toHaveBeenCalled(); expect(s.result.current.exactPending).toBe(true); expect(s.result.current.uncertain).toBe(true);
    act(() => s.result.current.bindExactImage()); expect(s.client.storyboardBindImage).toHaveBeenCalledTimes(1);
  });
  it.each(['other shot body', 'other shot binding', 'other shot version', 'missing other shot'] as const)('rejects a saved receipt with unexpected unrelated shot mutation: %s', async change => {
    const s = setup(); await prepare(s); const next = clone(s.next);
    if (change === 'other shot body') next.shots[1].shot.frame_prompt = 'unexpected rewrite';
    if (change === 'other shot binding') next.shots[1].image_asset = { ...s.pin, asset_id: 'unexpected' };
    if (change === 'other shot version') next.shots[1].shot_version++;
    if (change === 'missing other shot') next.shots = next.shots.slice(0, 1);
    s.client.storyboardBindImage.mockResolvedValue(next); act(() => s.result.current.bindExactImage()); await settle(s);
    expect(s.props.onDocument).not.toHaveBeenCalled(); expect(s.result.current.exactPending).toBe(true); expect(s.result.current.uncertain).toBe(true);
    act(() => s.result.current.bindExactImage()); expect(s.client.storyboardBindImage).toHaveBeenCalledTimes(1);
  });
  it.each([404, 409, 422])('retains UNKNOWN after successful POST followed by refresh HTTP %s', async status => {
    const s = setup(); await prepare(s); s.client.get.mockRejectedValue(new ApiError({ status, code: 'REFRESH_FAILED', message: 'refresh unavailable' }));
    act(() => s.result.current.bindExactImage()); await settle(s);
    expect(s.client.storyboardBindImage).toHaveBeenCalledTimes(1); expect(s.result.current.exactPending).toBe(true); expect(s.result.current.uncertain).toBe(true); expect(s.props.onDocument).not.toHaveBeenCalled();
    act(() => { s.result.current.read(); s.result.current.inspectExactImage(); s.result.current.bindExactImage(); }); await settle(s);
    expect(s.client.storyboardBindImage).toHaveBeenCalledTimes(1); expect(s.readAsset).toHaveBeenCalledTimes(2);
  });

  it('consumes the handoff synchronously so a retained pre-success callback cannot save twice before parent adoption', async () => {
    const s = setup(); await prepare(s); const retained = s.result.current.bindExactImage;
    act(() => retained()); await settle(s); expect(s.props.onDocument).toHaveBeenCalledTimes(1); expect(s.result.current.exactDone).toBe(true);
    // Parent deliberately has not rendered the new document version yet.
    act(() => retained()); await settle(s); expect(s.client.storyboardBindImage).toHaveBeenCalledTimes(1); expect(s.readAsset).toHaveBeenCalledTimes(2);
  });
  it('preserves a valid authored unsorted shot array while checking the canonical receipt order', async () => {
    const s = setup(), original = doc(s.initial), refreshed = doc(s.next); original.shots.reverse(); refreshed.shots.reverse();
    s.rerender({ ...s.props, document: original }); s.client.get.mockResolvedValue(refreshed); await prepare(s);
    act(() => s.result.current.bindExactImage()); await settle(s);
    expect(s.props.onDocument).toHaveBeenCalledWith(refreshed); expect(refreshed.shots).toEqual(original.shots); expect(s.result.current.exactDone).toBe(true);
  });
  it.each(['source_evidence', 'source_documents'] as const)('refuses post-save provenance changes to %s', async key => {
    const s = setup(); await prepare(s); const document = doc(s.next);
    if (key === 'source_evidence') document.source_evidence = { unrelated: { version: 7 } };
    if (key === 'source_documents') document.source_documents = { unrelated: { version: 7, digest: 'b'.repeat(64) } };
    s.client.get.mockResolvedValue(document); act(() => s.result.current.bindExactImage()); await settle(s);
    expect(s.props.onDocument).not.toHaveBeenCalled(); expect(s.result.current.exactPending).toBe(true); expect(s.result.current.uncertain).toBe(true);
  });
});
