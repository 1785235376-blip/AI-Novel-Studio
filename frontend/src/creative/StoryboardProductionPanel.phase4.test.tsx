// @vitest-environment jsdom
import { useState } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { webcrypto } from 'node:crypto';
import { Blob as NodeBlob } from 'node:buffer';
import { ApiError } from '../api';
import { StoryboardProductionPanel } from './StoryboardProductionPanel';
import type { StoryboardProductionProps } from './useStoryboardProductionController';
import type { CreativeClient } from './client';
import type { CreativeDocument } from './types';
import type { StudioClient, StudioAsset } from './studioClient';
import type { ProductionProvider, StudioProductionClient } from './studioProductionClient';
import { checkedStoryboardReceipt, checkedStoryboardImageRequest, checkedDirectorAdvice, type StoryboardReceipt, type ShotPin } from './studioStoryboardContract';
import { mediaProviderKey } from './useStudioMediaExecution';
import { cutoutBytes, cutoutHash } from './studioCpuCutout.testFixtures';
import storyboardFixture from './fixtures/phase4.file-api-storyboard.json';
import adviceFixture from './fixtures/phase4.file-api-director-advice.json';
import imageFixture from './fixtures/phase4.file-api-image-request.json';
import providersFixture from './fixtures/phase4.file-api-providers.json';
import timelineFixture from './fixtures/phase4.file-api-timeline-draft.json';

// Client mocks control view behavior. The captures are synthetic API receipts;
// these tests do not dispatch models or establish product acceptance.
const copy = <T,>(value: T): T => structuredClone(value);
const deferred = <T,>() => { let resolve!: (value: T) => void; const promise = new Promise<T>(yes => { resolve = yes; }); return { promise, resolve }; };
const documentFor = (receipt: StoryboardReceipt): CreativeDocument => ({ id: receipt.document_snapshot.id, version: receipt.document_snapshot.version, mode: 'STORYBOARD', title: 'Synthetic Storyboard',
  status: 'DRAFT', created_at: '', updated_at: '', actor_id: 'synthetic-author', source_evidence: {}, source_chapter_ids: [], source_independent: true, scenes: [], director_notes: [],
  shots: receipt.shots.map(row => copy(row.shot)), video_plan: null });
const unapproved = () => checkedStoryboardReceipt({ ...copy(storyboardFixture), approved: false });
const assetFor = (receipt: StoryboardReceipt): StudioAsset => {
  const image = receipt.shots[0].image_asset!;
  return { id: image.asset_id, novel_id: 'synthetic-storyboard-project', branch_id: null, version: image.version, sha256: image.digest, filename: 'synthetic-formal-image.png', kind: 'image', media_type: 'image/png', size: 1024, created_at: '', updated_at: '' };
};
const imageProvider = providersFixture.items[0] as unknown as ProductionProvider;
function mount(options: { receipt?: StoryboardReceipt; document?: CreativeDocument; editable?: boolean; isCurrent?: () => boolean; isBusy?: () => boolean } = {}) {
  const initial = options.receipt ?? unapproved(), document = options.document ?? documentFor(initial), onDocument = vi.fn(), onDenied = vi.fn(), onDirtyChange = vi.fn();
  const creative = { storyboardGet: vi.fn().mockResolvedValue(initial), directorAdvice: vi.fn().mockResolvedValue(checkedDirectorAdvice(copy(adviceFixture), adviceFixture.document_snapshot.id)),
    storyboardApprove: vi.fn(), storyboardBindImage: vi.fn(), storyboardImageRequest: vi.fn(), storyboardTimelineDraft: vi.fn(), get: vi.fn() };
  const studio = { assets: vi.fn().mockResolvedValue({ items: [assetFor(initial)] }), asset: vi.fn(), download: vi.fn() };
  const production = { providers: vi.fn().mockResolvedValue([imageProvider]), preview: vi.fn(), create: vi.fn(), execute: vi.fn(), refresh: vi.fn(), review: vi.fn(), list: vi.fn(), get: vi.fn(), candidate: vi.fn(), timelineList: vi.fn().mockResolvedValue({ items: [copy(timelineFixture.timeline)] }) };
  const perform = vi.fn();
  const sharedPerform: StoryboardProductionProps['perform'] = async <T,>(work: () => Promise<T>): Promise<T> => { perform(work); return work(); };
  const props: Omit<StoryboardProductionProps, 'document' | 'onDocument'> = { client: creative as unknown as CreativeClient, studio: studio as unknown as StudioClient,
    production: production as unknown as StudioProductionClient, active: true, editable: options.editable ?? true, busy: false, isBusy: options.isBusy ?? (() => false),
    isCurrent: options.isCurrent ?? (() => true), perform: sharedPerform, onDenied, onDirtyChange };
  let changeDocument!: (value: CreativeDocument) => void;
  function Harness() { const [currentDocument, setDocument] = useState(document); changeDocument = setDocument; return <StoryboardProductionPanel {...props} document={currentDocument}
    onDocument={value => { onDocument(value); setDocument(value); }} />; }
  const view = render(<Harness />);
  return { ...view, initial, props, creative, studio, production, perform, onDocument, onDenied, onDirtyChange, changeDocument: (value: CreativeDocument) => changeDocument(value) };
}
const button = (name: string) => screen.getByRole('button', { name }) as HTMLButtonElement;
const reviewed = '已核对当前分镜内容、镜头版本与绑定素材';
async function readSaved() { fireEvent.click(button('明确读取已保存创作回执')); await screen.findByRole('region', { name: '分镜生产预览' }); }
beforeEach(() => {
  vi.stubGlobal('crypto', webcrypto); vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Unexpected network in controlled view test')));
  const OriginalURL = globalThis.URL;
  class ControlledURL extends OriginalURL { static createObjectURL = vi.fn(() => 'blob:synthetic-storyboard-preview'); static revokeObjectURL = vi.fn(); }
  vi.stubGlobal('URL', ControlledURL);
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('Storyboard Inspector uses original source, permission and shared operation boundaries', () => {
  it('makes no request on mount and reads only after the explicit saved receipt action', async () => {
    const state = mount(); expect(state.perform).not.toHaveBeenCalled(); expect(state.creative.storyboardGet).not.toHaveBeenCalled();
    expect(state.studio.assets).not.toHaveBeenCalled(); expect(state.production.providers).not.toHaveBeenCalled();
    expect(state.production.timelineList).not.toHaveBeenCalled();
    expect(state.studio.asset).not.toHaveBeenCalled(); expect(state.studio.download).not.toHaveBeenCalled();
    await readSaved(); expect(state.creative.storyboardGet).toHaveBeenCalledWith(state.initial.document_snapshot.id);
    expect(state.perform).toHaveBeenCalledTimes(1); expect(screen.getByText('等待分镜审核')).toBeTruthy();
    expect(screen.getByText(state.initial.shots[0].shot_digest)).toBeTruthy(); expect(state.creative.storyboardApprove).not.toHaveBeenCalled();
  });
  it('requires review confirmation before approval and advances through the parent shared perform', async () => {
    const state = mount(), next = { ...copy(state.initial), approved: true, document_snapshot: { ...state.initial.document_snapshot, version: state.initial.document_snapshot.version + 1 } };
    state.creative.storyboardApprove.mockResolvedValue(next); state.creative.get.mockResolvedValue(documentFor(next));
    await readSaved(); expect(button('明确批准当前分镜版本').disabled).toBe(true);
    fireEvent.click(button('明确批准当前分镜版本')); expect(state.creative.storyboardApprove).not.toHaveBeenCalled();
    fireEvent.click(screen.getByLabelText(reviewed)); expect(button('明确批准当前分镜版本').disabled).toBe(false);
    fireEvent.click(button('明确批准当前分镜版本')); await screen.findByText('当前分镜已批准');
    expect(state.creative.storyboardApprove).toHaveBeenCalledOnce(); expect(state.creative.storyboardApprove).toHaveBeenCalledWith(state.initial);
    expect(state.creative.get).toHaveBeenCalledWith(next.document_snapshot.id); expect(state.perform).toHaveBeenCalledTimes(2);
    expect(state.onDocument).toHaveBeenCalledWith(documentFor(next)); expect((screen.getByLabelText(reviewed) as HTMLInputElement).checked).toBe(false);
    expect(state.production.create).not.toHaveBeenCalled(); expect(state.production.execute).not.toHaveBeenCalled();
  });
  it('binds a formal image version through the original client and clears old approval', async () => {
    const initial = checkedStoryboardReceipt(copy(storyboardFixture)), state = mount({ receipt: initial }), asset = assetFor(initial);
    const next = { ...copy(initial), approved: false, document_snapshot: { ...initial.document_snapshot, version: initial.document_snapshot.version + 1 } };
    state.creative.storyboardBindImage.mockResolvedValue(next); state.creative.get.mockResolvedValue(documentFor(next));
    await readSaved(); expect(screen.getByText('当前分镜已批准')).toBeTruthy();
    fireEvent.click(button('明确读取已有图片与模型配置')); await screen.findByRole('option', { name: 'synthetic-formal-image.png · v2' });
    fireEvent.change(screen.getByLabelText('正式图片'), { target: { value: asset.id } }); fireEvent.click(button('明确绑定图片版本'));
    await screen.findByText('等待分镜审核'); expect(state.creative.storyboardBindImage).toHaveBeenCalledWith(initial, initial.shots[0],
      { asset_id: asset.id, version: asset.version, digest: asset.sha256, kind: 'image' });
    expect(state.perform).toHaveBeenCalledTimes(3); expect(state.onDocument).toHaveBeenCalledWith(documentFor(next));
    expect((screen.getByLabelText(reviewed) as HTMLInputElement).checked).toBe(false); expect(state.production.review).not.toHaveBeenCalled();
  });
  it('ignores a late saved read when its parent identity becomes unavailable', async () => {
    let current = true; const state = mount({ isCurrent: () => current }), pending = deferred<StoryboardReceipt>(); state.creative.storyboardGet.mockReturnValueOnce(pending.promise);
    fireEvent.click(button('明确读取已保存创作回执')); expect(state.creative.storyboardGet).toHaveBeenCalledOnce(); current = false;
    await act(async () => { pending.resolve(state.initial); await pending.promise; });
    expect(screen.queryByRole('region', { name: '分镜生产预览' })).toBeNull(); expect(screen.queryByText('等待分镜审核')).toBeNull();
    expect(state.onDocument).not.toHaveBeenCalled(); expect(state.creative.storyboardApprove).not.toHaveBeenCalled(); expect(state.onDenied).not.toHaveBeenCalled();
  });
  it('blocks requests when the parent operation mutex is already occupied', () => {
    const state = mount({ isBusy: () => true }); expect(button('明确读取已保存创作回执').disabled).toBe(true);
    fireEvent.click(button('明确读取已保存创作回执')); expect(state.perform).not.toHaveBeenCalled(); expect(state.creative.storyboardGet).not.toHaveBeenCalled();
  });
  it('keeps unknown mutation outcomes blocked without automatic retry or document adoption', async () => {
    const state = mount(); state.creative.storyboardApprove.mockRejectedValue(new ApiError({ status: 503, code: 'SYNTHETIC_UNKNOWN', message: 'Synthetic operation receipt unavailable' }));
    await readSaved(); fireEvent.click(screen.getByLabelText(reviewed)); fireEvent.click(button('明确批准当前分镜版本'));
    await screen.findByText('版本或回执不确定，先读取原文档核对；不会自动重发写入。');
    expect(button('明确批准当前分镜版本').disabled).toBe(true); fireEvent.click(button('明确批准当前分镜版本'));
    expect(state.creative.storyboardApprove).toHaveBeenCalledOnce(); expect(state.creative.get).not.toHaveBeenCalled(); expect(state.onDocument).not.toHaveBeenCalled();
    expect(state.perform).toHaveBeenCalledTimes(2); expect(state.production.create).not.toHaveBeenCalled();
  });
  it('embeds the original prepared media flow without creating, executing or reviewing a task', async () => {
    const initial = unapproved(); initial.document_snapshot = copy(imageFixture.shot_pin.document_snapshot); const state = mount({ receipt: initial });
    state.creative.storyboardImageRequest.mockImplementation(async (_receipt, _shot, _operation, _provider, _model, requestId: string) => {
      const value = copy(imageFixture); value.command.request_id = requestId; const pin = value.shot_pin as ShotPin; return checkedStoryboardImageRequest(value, pin);
    });
    await readSaved(); fireEvent.click(button('明确读取已有图片与模型配置')); await screen.findByRole('option', { name: `${imageProvider.provider_id} · ${imageProvider.model_id}` });
    fireEvent.change(screen.getByLabelText('已有图片模型'), { target: { value: mediaProviderKey(imageProvider) } }); fireEvent.click(button('准备版本绑定图片请求'));
    await screen.findByRole('heading', { name: '原分镜图片请求' }); await waitFor(() => expect(state.production.providers).toHaveBeenCalledTimes(2));
    expect(state.creative.storyboardImageRequest).toHaveBeenCalledOnce(); expect(state.creative.storyboardImageRequest.mock.calls[0]).toEqual([
      initial, initial.shots[0], 'm5.image.t2i', imageProvider.provider_id, imageProvider.model_id, expect.any(String), {},
    ]);
    const displayed = JSON.parse(state.container.querySelector('pre')!.textContent!);
    expect(displayed.source_snapshots).toEqual([{ ...initial.document_snapshot, kind: 'CREATIVE_DOCUMENT', reference_only: true }]);
    expect(screen.getByRole('button', { name: '读取制作预览' })).toBeTruthy(); expect(screen.queryByLabelText('本次提示词')).toBeNull();
    expect(state.production.preview).not.toHaveBeenCalled(); expect(state.production.create).not.toHaveBeenCalled(); expect(state.production.execute).not.toHaveBeenCalled(); expect(state.production.review).not.toHaveBeenCalled();
    expect(fetch).not.toHaveBeenCalled();
  });
  it('reads Director advice explicitly without an apply or generation action', async () => {
    const initial = unapproved(), document = { ...documentFor(initial), id: adviceFixture.document_snapshot.id, version: adviceFixture.document_snapshot.version, mode: 'DIRECTOR' as const, title: 'Synthetic Director' }, state = mount({ document });
    expect(state.creative.directorAdvice).not.toHaveBeenCalled(); fireEvent.click(button('明确读取已保存创作回执')); await screen.findByText('仅提供建议');
    expect(screen.getByText('Blue · Soft key · Brushed metal · Ink illustration')).toBeTruthy();
    expect(state.creative.directorAdvice).toHaveBeenCalledWith(document.id); expect(state.perform).toHaveBeenCalledOnce();
    expect(state.creative.storyboardGet).not.toHaveBeenCalled(); expect(state.onDocument).not.toHaveBeenCalled(); expect(state.production.create).not.toHaveBeenCalled(); expect(state.production.execute).not.toHaveBeenCalled();
  });
  function previewState(options: { isCurrent?: () => boolean; approved?: boolean } = {}) {
    const initial = unapproved(); initial.approved = options.approved ?? false; initial.shots.forEach(shot => { shot.image_asset!.digest = cutoutHash; });
    const state = mount({ receipt: initial, isCurrent: options.isCurrent }), asset = { ...assetFor(initial), size: cutoutBytes.length }, blob = new NodeBlob([cutoutBytes], { type: 'image/png' }) as unknown as Blob;
    state.studio.asset.mockResolvedValue(asset); state.studio.download.mockResolvedValue(blob);
    return { ...state, asset, blob };
  }
  it('previews formal bytes only after exact version, MIME, size and SHA validation, then clears them on shot change', async () => {
    const state = previewState(); await readSaved(); expect(state.studio.asset).not.toHaveBeenCalled(); expect(state.studio.download).not.toHaveBeenCalled();
    fireEvent.click(button('明确读取绑定图片预览')); const image = await screen.findByAltText(state.asset.filename);
    expect(image.getAttribute('src')).toBe('blob:synthetic-storyboard-preview'); expect(state.studio.asset).toHaveBeenCalledWith(state.asset.id);
    expect(state.studio.download).toHaveBeenCalledOnce(); expect(state.studio.download).toHaveBeenCalledWith(state.asset.id);
    expect(URL.createObjectURL).toHaveBeenCalledWith(state.blob); expect(state.perform).toHaveBeenCalledTimes(2);
    fireEvent.click(button('SHOT 2 · v1')); await waitFor(() => expect(screen.queryByAltText(state.asset.filename)).toBeNull());
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:synthetic-storyboard-preview'); expect(state.production.create).not.toHaveBeenCalled();
  });
  it.each(['version', 'sha256'] as const)('rejects changed formal asset metadata %s before reading media', async field => {
    const state = previewState(), asset = { ...state.asset }; if (field === 'version') asset.version++; else asset.sha256 = 'a'.repeat(64);
    state.studio.asset.mockResolvedValue(asset); await readSaved(); fireEvent.click(button('明确读取绑定图片预览'));
    await screen.findByText('分镜回执或版本绑定不完整，请读取原文档核对。'); expect(state.studio.download).not.toHaveBeenCalled();
    expect(URL.createObjectURL).not.toHaveBeenCalled(); expect(screen.queryByRole('region', { name: '资产检查面板' })).toBeNull();
  });
  it.each(['sha256', 'media_type', 'size'] as const)('rejects media bytes with a changed %s before publishing a preview URL', async field => {
    const state = previewState(); let blob: Blob;
    if (field === 'sha256') { const changed = cutoutBytes.slice(); changed[changed.length - 1] ^= 1; blob = new NodeBlob([changed], { type: 'image/png' }) as unknown as Blob; }
    else blob = new NodeBlob([field === 'size' ? cutoutBytes.slice(0, -1) : cutoutBytes], { type: field === 'media_type' ? 'image/jpeg' : 'image/png' }) as unknown as Blob;
    state.studio.download.mockResolvedValue(blob); await readSaved(); fireEvent.click(button('明确读取绑定图片预览'));
    await screen.findByText('分镜回执或版本绑定不完整，请读取原文档核对。'); expect(state.studio.download).toHaveBeenCalledOnce();
    expect(URL.createObjectURL).not.toHaveBeenCalled(); expect(screen.queryByRole('region', { name: '资产检查面板' })).toBeNull();
  });
  it('discards a late verified blob after identity loss without producing a URL', async () => {
    let current = true; const state = previewState({ isCurrent: () => current }), pending = deferred<Blob>(); state.studio.download.mockReturnValueOnce(pending.promise);
    await readSaved(); fireEvent.click(button('明确读取绑定图片预览')); await waitFor(() => expect(state.studio.download).toHaveBeenCalledOnce());
    expect(button('SHOT 2 · v1').disabled).toBe(true); current = false;
    await act(async () => { pending.resolve(state.blob); await pending.promise; });
    expect(URL.createObjectURL).not.toHaveBeenCalled(); expect(screen.queryByRole('region', { name: '资产检查面板' })).toBeNull();
    expect(state.production.create).not.toHaveBeenCalled();
  });
  it('discards a late blob when the original document changes and unlocks the new saved read', async () => {
    const state = previewState(), pending = deferred<Blob>(); state.studio.download.mockReturnValueOnce(pending.promise);
    await readSaved(); fireEvent.click(button('明确读取绑定图片预览')); await waitFor(() => expect(state.studio.download).toHaveBeenCalledOnce());
    await act(async () => { state.changeDocument({ ...documentFor(state.initial), version: state.initial.document_snapshot.version + 1 }); });
    await act(async () => { pending.resolve(state.blob); await pending.promise; });
    expect(URL.createObjectURL).not.toHaveBeenCalled(); expect(screen.queryByRole('region', { name: '资产检查面板' })).toBeNull();
    await waitFor(() => expect(button('明确读取已保存创作回执').disabled).toBe(false));
  });
  it('clears approved source grants and verified preview after a saved read conflict without replaying actions', async () => {
    const initial = checkedStoryboardReceipt(copy(storyboardFixture)); initial.shots.forEach(shot => { shot.image_asset!.digest = cutoutHash; });
    const state = mount({ receipt: initial }), asset = { ...assetFor(initial), size: cutoutBytes.length }, blob = new NodeBlob([cutoutBytes], { type: 'image/png' }) as unknown as Blob;
    state.studio.asset.mockResolvedValue(asset); state.studio.download.mockResolvedValue(blob);
    await readSaved(); fireEvent.click(button('明确读取绑定图片预览')); await screen.findByAltText(asset.filename);
    fireEvent.click(screen.getByLabelText(reviewed)); expect((screen.getByLabelText(reviewed) as HTMLInputElement).checked).toBe(true);
    state.creative.storyboardGet.mockRejectedValueOnce(new ApiError({ status: 409, code: 'SYNTHETIC_SOURCE_CHANGED', message: 'Synthetic saved source changed' }));
    fireEvent.click(button('明确读取已保存创作回执')); await screen.findByText('版本或回执不确定，先读取原文档核对；不会自动重发写入。');
    expect(screen.queryByText('当前分镜已批准')).toBeNull(); expect(screen.queryByText(initial.shots[0].shot_digest)).toBeNull();
    expect(screen.queryByAltText(asset.filename)).toBeNull(); expect(screen.queryByRole('button', { name: '明确批准当前分镜版本' })).toBeNull();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:synthetic-storyboard-preview'); expect(state.creative.storyboardGet).toHaveBeenCalledTimes(2);
    expect(state.creative.storyboardApprove).not.toHaveBeenCalled(); expect(state.creative.storyboardBindImage).not.toHaveBeenCalled();
    expect(state.creative.storyboardTimelineDraft).not.toHaveBeenCalled(); expect(state.onDocument).not.toHaveBeenCalled(); expect(state.production.create).not.toHaveBeenCalled();
  });
  it('revokes saved grants when explicit formal-preview metadata reports a source conflict', async () => {
    const state = previewState(); await readSaved(); fireEvent.click(screen.getByLabelText(reviewed));
    state.studio.asset.mockRejectedValueOnce(new ApiError({ status: 409, code: 'SYNTHETIC_ASSET_CHANGED', message: 'Synthetic formal image changed' }));
    fireEvent.click(button('明确读取绑定图片预览')); await screen.findByText('版本或回执不确定，先读取原文档核对；不会自动重发写入。');
    expect(screen.queryByRole('region', { name: '分镜生产预览' })).toBeNull(); expect(screen.queryByRole('button', { name: '明确批准当前分镜版本' })).toBeNull();
    expect(state.studio.download).not.toHaveBeenCalled(); expect(URL.createObjectURL).not.toHaveBeenCalled(); expect(state.creative.storyboardApprove).not.toHaveBeenCalled();
  });
  it.each([200, 0])('retains the separate uncertain Timeline creation fence at API status %s after source reread and record inspection', async status => {
    const state = mount({ receipt: checkedStoryboardReceipt(copy(storyboardFixture)) });
    state.creative.storyboardTimelineDraft.mockRejectedValue(new ApiError({ status, code: status === 200 ? 'STUDIO_RESPONSE_INVALID' : 'STUDIO_NETWORK_ERROR', message: 'Synthetic uncertain timeline receipt' }));
    await readSaved(); fireEvent.click(screen.getByLabelText('时间线 SHOT 1 · v1')); fireEvent.click(screen.getByLabelText(reviewed));
    expect(button('明确建立原时间线底稿').disabled).toBe(false); fireEvent.click(button('明确建立原时间线底稿'));
    await screen.findByText('版本或回执不确定，先读取原文档核对；不会自动重发写入。');
    expect(state.creative.storyboardTimelineDraft).toHaveBeenCalledOnce(); expect((screen.getByLabelText(reviewed) as HTMLInputElement).disabled).toBe(true);
    fireEvent.click(screen.getByLabelText(reviewed)); fireEvent.click(button('明确建立原时间线底稿'));
    expect(state.creative.storyboardTimelineDraft).toHaveBeenCalledOnce();
    fireEvent.click(button('明确读取已有图片与模型配置')); await waitFor(() => expect(state.production.providers).toHaveBeenCalledOnce());
    expect(screen.getByText('版本或回执不确定，先读取原文档核对；不会自动重发写入。')).toBeTruthy();
    expect(button('明确建立原时间线底稿').disabled).toBe(true); expect(state.creative.storyboardTimelineDraft).toHaveBeenCalledOnce();
    fireEvent.click(button('明确读取已保存创作回执')); await waitFor(() => expect(screen.queryByText('版本或回执不确定，先读取原文档核对；不会自动重发写入。')).toBeNull());
    expect(state.creative.storyboardGet).toHaveBeenCalledTimes(2); expect((screen.getByLabelText(reviewed) as HTMLInputElement).disabled).toBe(false);
    expect((screen.getByLabelText(reviewed) as HTMLInputElement).checked).toBe(false); fireEvent.click(screen.getByLabelText(reviewed));
    expect(button('明确建立原时间线底稿').disabled).toBe(true); fireEvent.click(button('明确建立原时间线底稿'));
    expect(state.creative.storyboardTimelineDraft).toHaveBeenCalledOnce(); expect(screen.getByRole('region', { name: '时间线创建回执待核对' })).toBeTruthy();
    expect(state.production.timelineList).not.toHaveBeenCalled(); fireEvent.click(button('明确读取原时间线记录'));
    await screen.findByText(`${timelineFixture.timeline.title} · 原时间线 ${timelineFixture.timeline.id} · v${timelineFixture.timeline.version}`);
    expect(state.production.timelineList).toHaveBeenCalledOnce(); expect(button('明确建立原时间线底稿').disabled).toBe(true);
    fireEvent.click(button('明确建立原时间线底稿')); expect(state.creative.storyboardTimelineDraft).toHaveBeenCalledOnce();
    expect(screen.getByRole('region', { name: '时间线创建回执待核对' })).toBeTruthy();
    expect(state.production.create).not.toHaveBeenCalled(); expect(state.production.execute).not.toHaveBeenCalled();
  });
  it('does not continue to download after late formal metadata resolves under a lost identity', async () => {
    let current = true; const state = previewState({ isCurrent: () => current }), pending = deferred<StudioAsset>(); state.studio.asset.mockReturnValueOnce(pending.promise);
    await readSaved(); fireEvent.click(button('明确读取绑定图片预览')); await waitFor(() => expect(state.studio.asset).toHaveBeenCalledOnce());
    current = false; await act(async () => { pending.resolve(state.asset); await pending.promise; });
    expect(state.studio.download).not.toHaveBeenCalled(); expect(URL.createObjectURL).not.toHaveBeenCalled();
    expect(screen.queryByRole('region', { name: '资产检查面板' })).toBeNull(); expect(state.creative.storyboardApprove).not.toHaveBeenCalled();
  });
  it.each([200, 409])('revokes saved source and verified formal preview when image preparation returns unsafe status %s', async status => {
    const state = previewState({ approved: true }); state.creative.storyboardImageRequest.mockRejectedValue(new ApiError({ status,
      code: status === 200 ? 'STUDIO_RESPONSE_INVALID' : 'SYNTHETIC_SOURCE_CHANGED', message: 'Synthetic image request source is unsafe' }));
    await readSaved(); fireEvent.click(button('明确读取绑定图片预览')); await screen.findByAltText(state.asset.filename);
    expect(screen.getByText('当前分镜已批准')).toBeTruthy(); fireEvent.click(screen.getByLabelText(reviewed));
    fireEvent.click(button('明确读取已有图片与模型配置')); await screen.findByRole('option', { name: `${imageProvider.provider_id} · ${imageProvider.model_id}` });
    fireEvent.change(screen.getByLabelText('已有图片模型'), { target: { value: mediaProviderKey(imageProvider) } }); fireEvent.click(button('准备版本绑定图片请求'));
    await screen.findByText('版本或回执不确定，先读取原文档核对；不会自动重发写入。');
    expect(screen.queryByRole('region', { name: '分镜生产预览' })).toBeNull(); expect(screen.queryByText('当前分镜已批准')).toBeNull();
    expect(screen.queryByText(state.initial.shots[0].shot_digest)).toBeNull(); expect(screen.queryByAltText(state.asset.filename)).toBeNull();
    expect(screen.queryByRole('heading', { name: '原分镜图片请求' })).toBeNull(); expect(screen.queryByRole('region', { name: '已建立的分镜时间线底稿' })).toBeNull();
    expect(screen.queryByRole('button', { name: '明确批准当前分镜版本' })).toBeNull(); expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:synthetic-storyboard-preview');
    expect(state.creative.storyboardImageRequest).toHaveBeenCalledOnce(); expect(state.creative.storyboardApprove).not.toHaveBeenCalled(); expect(state.creative.storyboardTimelineDraft).not.toHaveBeenCalled();
    expect(state.production.preview).not.toHaveBeenCalled(); expect(state.production.create).not.toHaveBeenCalled(); expect(state.production.execute).not.toHaveBeenCalled(); expect(state.production.review).not.toHaveBeenCalled();
  });
  it('preserves an independently fresh saved source and verified Blob when original Timeline recovery returns 409', async () => {
    const state = previewState({ approved: true }); state.creative.storyboardTimelineDraft.mockRejectedValueOnce(new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: 'Synthetic uncertain timeline creation' }));
    await readSaved(); fireEvent.click(button('明确读取绑定图片预览')); await screen.findByAltText(state.asset.filename);
    fireEvent.click(screen.getByLabelText('时间线 SHOT 1 · v1')); fireEvent.click(screen.getByLabelText(reviewed)); fireEvent.click(button('明确建立原时间线底稿'));
    await screen.findByText('版本或回执不确定，先读取原文档核对；不会自动重发写入。');
    fireEvent.click(button('明确读取已保存创作回执')); await waitFor(() => expect((screen.getByLabelText(reviewed) as HTMLInputElement).disabled).toBe(false));
    expect(screen.getByText('当前分镜已批准')).toBeTruthy(); expect(screen.getByAltText(state.asset.filename)).toBeTruthy();
    state.production.timelineList.mockRejectedValueOnce(new ApiError({ status: 409, code: 'SYNTHETIC_TIMELINE_CHANGED', message: 'Synthetic timeline records changed' }));
    fireEvent.click(button('明确读取原时间线记录')); await screen.findByText('Synthetic timeline records changed');
    expect(screen.getByText('当前分镜已批准')).toBeTruthy(); expect(screen.getByText(state.initial.shots[0].shot_digest)).toBeTruthy();
    expect(screen.getByRole('region', { name: '分镜生产预览' })).toBeTruthy(); expect(screen.getByAltText(state.asset.filename)).toBeTruthy();
    expect((screen.getByLabelText(reviewed) as HTMLInputElement).disabled).toBe(false); expect(URL.revokeObjectURL).not.toHaveBeenCalled();
    expect(button('明确建立原时间线底稿').disabled).toBe(true); expect(state.creative.storyboardTimelineDraft).toHaveBeenCalledOnce();
    expect(state.production.timelineList).toHaveBeenCalledOnce(); expect(state.creative.storyboardGet).toHaveBeenCalledTimes(2); expect(state.production.create).not.toHaveBeenCalled();
  });
});
