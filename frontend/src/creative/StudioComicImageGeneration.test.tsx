// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { webcrypto } from 'node:crypto';
import { Blob as NodeBlob } from 'node:buffer';
import { ComicLayoutsPanel } from '../experimental/ComicLayoutsPanel';
import type { ExperimentalClient } from '../experimental/api';
import { StudioComicImageGeneration } from './StudioComicImageGeneration';
import { mediaProviderKey } from './useStudioMediaExecution';
import type { ProductionJob, ProductionPreview, ProductionProvider, StudioProductionClient } from './studioProductionClient';
import type { ComicImageRequest, StudioComicImageClient } from './studioComicImageClient';
import type { ComicRecord } from '../experimental/comicLayoutsClient';
const digest = 'a'.repeat(64);
const page: ComicRecord = { id: 'page', version: 1, status: 'DRAFT', stale: false, document: { title: 'Test', source_mode: 'INDEPENDENT', screenplay_id: null, expected_screenplay_version: null, preset: 'PAGE', font_family: 'NOTO_SANS_SC_OFL', width: 800, height: 1120, safe_area: 24, segment_height: 1120, panels: [1, 2].map(i => ({ id: `panel-${i}`, shot_id: null, artwork_mode: 'IMAGE', order: i, x: 24, y: i * 200, width: 512, height: 180, character_ids: [], asset_id: null, expected_asset_version: null, fit: 'CONTAIN', bubbles: [], image_brief: `Brief ${i}`, appearance_references: [] })) } };
const provider: ProductionProvider = { operation_id: 'm5.image.t2i', provider_id: 'local', model_id: 'fixture', local: true, route_digest: digest, capability: 'IMAGE', supported_parameters: ['width', 'height', 'seed'], readiness: 'CONFIGURED_NOT_VERIFIED' };
const request: ComicImageRequest = { contract: 'studio-comic-image-request/1', automatic_dispatch: false, model_called: false, output_policy: 'PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW', source_snapshot: { id: 'page', kind: 'COMIC_PANEL', version: 1, digest, reference_only: true, comic_panel: { panel_id: 'panel-1', panel_digest: digest, brief_digest: digest, actor: 'local-author', scope_key: digest, incarnation: 'file:12345678-1234-1234-1234-123456789012' } }, command: {} as ComicImageRequest['command'] };
request.command = { operation_id: 'm5.image.t2i', request_id: 'comic-request', provider_id: 'local', model_id: 'fixture', prompt: 'Brief 1', parameters: { width: 512, height: 512, seed: 1 }, source_snapshots: [request.source_snapshot], allow_cloud: false, license_note: '' };
const queued: ProductionJob = { contract: 'studio-production-job/1', owner: 'image', id: 'job', novel_id: 'project', branch_id: null, version: 1, operation_id: 'm5.image.t2i', request_id: request.command.request_id, status: 'QUEUED', request_digest: digest, receipt_digest: null, output_candidate: null, product_acceptance: 'LOCAL_REQUIRED', automatic_replay: false, remote_compute_may_continue: false, timeline_snapshot: null, sources: [request.source_snapshot], command: request.command, provider, execution_recipe: { contract: 'studio-execution-recipe/1', operation_id: 'm5.image.t2i', adapter: 'ORIGINAL_HTTP_PROVIDER', recipe_digest: digest, automatic_fallback: false }, approved_asset_version: null, created_at: '', updated_at: '' };
const preview: ProductionPreview = { contract: 'studio-production-preview/1', novel_id: 'project', branch_id: null, request_id: request.command.request_id, operation_id: 'm5.image.t2i', preview_digest: digest, request_digest: digest, command: request.command, provider, execution_recipe: queued.execution_recipe, product_acceptance: 'LOCAL_REQUIRED', execution_available: true, automatic_dispatch: false, output_policy: 'PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW' };
const button = (name: string) => screen.getByRole('button', { name }) as HTMLButtonElement;
let production: StudioProductionClient, client: StudioComicImageClient, approved: ProductionJob;
beforeEach(async () => {
  vi.stubGlobal('crypto', webcrypto); URL.createObjectURL = vi.fn(() => 'blob:comic-candidate'); URL.revokeObjectURL = vi.fn();
  const blob = new NodeBlob(['synthetic image bytes'], { type: 'image/png' });
  const hash = Buffer.from(await webcrypto.subtle.digest('SHA-256', await blob.arrayBuffer())).toString('hex');
  const candidate = { ...queued, version: 2, status: 'AWAITING_REVIEW', output_candidate: { id: 'asset', version: 1, digest: hash, kind: 'image' } } as ProductionJob;
  approved = { ...candidate, version: 3, status: 'APPROVED', approved_asset_version: 2 };
  production = { providers: vi.fn(async () => [provider, { ...provider, local: false, provider_id: 'cloud' }]), preview: vi.fn(async () => preview), create: vi.fn(async () => queued), execute: vi.fn(async () => candidate), candidate: vi.fn(async () => blob), review: vi.fn(async () => approved), list: vi.fn(async () => []), get: vi.fn(async () => approved) } as unknown as StudioProductionClient;
  client = { request: vi.fn(async () => request), adopt: vi.fn(async () => ({ ...page, version: 2, document: { ...page.document!, panels: page.document!.panels.map(p => p.id === 'panel-1' ? { ...p, asset_id: 'asset', expected_asset_version: 2 } : p) } })) };
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
function props() { return { page, disabled: false, isCurrent: () => true, onDirtyChange: vi.fn(), onBusyChange: vi.fn(), onAdopt: vi.fn(), client, production, canMutate: true, canReview: true }; }
async function configure() {
  fireEvent.change(screen.getByLabelText('生成图片的漫画格框'), { target: { value: 'panel-1' } });
  fireEvent.click(button('读取本地图片配置'));
  await waitFor(() => expect(screen.getByRole('option', { name: 'local · fixture · 本地' })).toBeTruthy());
  expect(screen.queryByRole('option', { name: /cloud/ })).toBeNull();
  fireEvent.change(screen.getByLabelText('漫画图片本地服务商与模型'), { target: { value: mediaProviderKey(provider) } });
  for (const [name, value] of [['宽度', '512'], ['高度', '512'], ['种子', '1']]) fireEvent.change(screen.getByLabelText(`漫画图片${name}`), { target: { value } });
}
async function prepare() { await configure(); fireEvent.click(button('明确准备此格框图片请求')); await screen.findByText('原漫画格框图片请求'); await waitFor(() => expect(button('读取制作预览').disabled).toBe(false)); }
it('uses original Image preview, queue, execution, private candidate and review before a separate explicit Comic adoption', async () => {
  const p = props(); render(<StudioComicImageGeneration {...p} />); await prepare();
  expect(production.create).not.toHaveBeenCalled(); expect(production.execute).not.toHaveBeenCalled(); expect(client.adopt).not.toHaveBeenCalled();
  fireEvent.click(button('读取制作预览')); await screen.findByText('确认本次预览');
  fireEvent.click(screen.getByLabelText('已核对本次输入、来源和处理边界')); fireEvent.click(button('仅创建任务并入队'));
  await waitFor(() => expect(button('明确执行当前入队任务').disabled).toBe(false)); expect(production.execute).not.toHaveBeenCalled();
  fireEvent.click(button('明确执行当前入队任务')); await screen.findByText('候选结果');
  expect(client.adopt).not.toHaveBeenCalled(); expect(button('明确审核并入素材库').disabled).toBe(true);
  fireEvent.click(button('读取并核对候选媒体')); await screen.findByRole('img', { name: '本任务经摘要核对的图片候选' });
  fireEvent.click(screen.getByLabelText('已查看本次候选，确认采用当前任务版本与输出摘要')); fireEvent.click(button('明确审核并入素材库'));
  await screen.findByText('原任务已审核入库。产品里程碑验收状态仍为 LOCAL_REQUIRED。');
  expect(client.adopt).not.toHaveBeenCalled(); expect(p.onAdopt).not.toHaveBeenCalled();
  fireEvent.click(button('明确采用已审核图片到此格框草稿'));
  await waitFor(() => expect(p.onAdopt).toHaveBeenCalledTimes(1));
  expect(client.adopt).toHaveBeenCalledWith(page, 'panel-1', request, approved);
  expect(production.create).toHaveBeenCalledTimes(1); expect(production.execute).toHaveBeenCalledTimes(1); expect(production.review).toHaveBeenCalledTimes(1);
});
it('rejects unsupported appearance references without dropping them or preparing a request', async () => {
  const referenced = structuredClone(page); referenced.document!.panels[0].appearance_references = [{ character_id: 'person', asset_id: 'ref', expected_asset_version: 1, note: 'face' }];
  render(<StudioComicImageGeneration {...props()} page={referenced} />); await configure();
  expect(screen.getByText(/不会忽略参考或自动换路线/)).toBeTruthy(); expect(button('明确准备此格框图片请求').disabled).toBe(true); expect(client.request).not.toHaveBeenCalled();
});
it('late prepare cannot survive owner ABA or be adopted to another panel', async () => {
  let resolve!: (value: ComicImageRequest) => void; client.request = vi.fn(() => new Promise<ComicImageRequest>(done => { resolve = done; }));
  const p = props(); const view = render(<StudioComicImageGeneration {...p} />); await configure(); fireEvent.click(button('明确准备此格框图片请求'));
  view.rerender(<StudioComicImageGeneration {...p} isCurrent={() => false} />); view.rerender(<StudioComicImageGeneration {...p} />);
  await act(async () => resolve(request));
  expect(screen.queryByText('原漫画格框图片请求')).toBeNull(); expect(production.preview).not.toHaveBeenCalled(); expect(client.adopt).not.toHaveBeenCalled();
});
it('does not prepare from dirty/blocked pages or without mutation authority', async () => {
  const p = props(); const view = render(<StudioComicImageGeneration {...p} disabled />);
  expect((screen.getByLabelText('生成图片的漫画格框') as HTMLSelectElement).closest('fieldset')?.disabled).toBe(true);
  view.rerender(<StudioComicImageGeneration {...p} canMutate={false} />);
  fireEvent.click(button('明确准备此格框图片请求')); expect(client.request).not.toHaveBeenCalled();
});
async function recoverApproved() {
  fireEvent.change(screen.getByLabelText('生成图片的漫画格框'), { target: { value: 'panel-1' } });
  fireEvent.change(screen.getByLabelText('漫画格框原图片任务 ID'), { target: { value: 'job' } });
  fireEvent.click(button('读取此格框原图片任务'));
  await waitFor(() => expect(button('明确采用已审核图片到此格框草稿').disabled).toBe(false));
}
it('recovers an exact original approved task after reopening without preparing or executing again', async () => {
  render(<StudioComicImageGeneration {...props()} />); await recoverApproved();
  expect(production.get).toHaveBeenCalledWith('image', 'job'); expect(client.request).not.toHaveBeenCalled();
  expect(production.create).not.toHaveBeenCalled(); expect(production.execute).not.toHaveBeenCalled(); expect(client.adopt).not.toHaveBeenCalled();
});
it('does not recover a different panel task and exposes no adoption control', async () => {
  render(<StudioComicImageGeneration {...props()} />);
  fireEvent.change(screen.getByLabelText('生成图片的漫画格框'), { target: { value: 'panel-2' } });
  fireEvent.change(screen.getByLabelText('漫画格框原图片任务 ID'), { target: { value: 'job' } }); fireEvent.click(button('读取此格框原图片任务'));
  await screen.findByText('当前漫画页面、格框或身份已变化，请重新打开。');
  expect(screen.queryByRole('button', { name: '明确采用已审核图片到此格框草稿' })).toBeNull(); expect(client.adopt).not.toHaveBeenCalled();
});
it('late adoption cannot overwrite another page/version and an ambiguous adoption is not replayed', async () => {
  let resolve!: (value: ComicRecord) => void; client.adopt = vi.fn(() => new Promise<ComicRecord>(done => { resolve = done; }));
  const p = props(); const view = render(<StudioComicImageGeneration {...p} />); await recoverApproved();
  fireEvent.click(button('明确采用已审核图片到此格框草稿')); fireEvent.click(button('明确采用已审核图片到此格框草稿'));
  expect(client.adopt).toHaveBeenCalledTimes(1);
  view.rerender(<StudioComicImageGeneration {...p} page={{ ...page, version: 2 }} />);
  await act(async () => resolve({ ...page, version: 2 })); expect(p.onAdopt).not.toHaveBeenCalled();
});
it('UNKNOWN recovery offers original explicit reconciliation while refusing another execution', async () => {
  production.get = vi.fn(async () => ({ ...queued, version: 2, status: 'UNKNOWN' as const }));
  production.reconcile = vi.fn(async () => approved);
  render(<StudioComicImageGeneration {...props()} />);
  fireEvent.change(screen.getByLabelText('生成图片的漫画格框'), { target: { value: 'panel-1' } });
  fireEvent.change(screen.getByLabelText('漫画格框原图片任务 ID'), { target: { value: 'job' } }); fireEvent.click(button('读取此格框原图片任务'));
  await waitFor(() => expect(button('核对中断状态，不重新发送').disabled).toBe(false));
  expect(button('明确执行当前入队任务').disabled).toBe(true); expect(production.execute).not.toHaveBeenCalled();
  fireEvent.click(button('核对中断状态，不重新发送')); await waitFor(() => expect(production.reconcile).toHaveBeenCalledTimes(1));
  expect(production.execute).not.toHaveBeenCalled(); expect(client.adopt).not.toHaveBeenCalled();
});
it('mounted Comic editor retains its generation session while locking edits, then adopts and reloads the same DRAFT page', async () => {
  let saved = page;
  const originalAdopt = client.adopt;
  client.adopt = vi.fn(async (...args: Parameters<StudioComicImageClient['adopt']>) => { saved = await originalAdopt(...args); return saved; });
  const preset = { width: 800, height: 1120, safe_area: 24, segment_height: 1120 };
  const experimental = { get: vi.fn(async (path: string) => path.endsWith('/catalog') ? { screenplays: [], characters: [], assets: [{ id: 'asset', version: 2, approved: true, filename: 'Generated' }], presets: { PAGE: preset, WEBTOON: preset }, renderer: { available: true }, font: { available: true } } : { items: path.endsWith('/records') ? [saved] : [] }), post: vi.fn(), put: vi.fn(), blob: vi.fn(), postBlob: vi.fn() } as unknown as ExperimentalClient;
  const dirty = vi.fn();
  render(<ComicLayoutsPanel client={experimental} onDirtyChange={dirty} renderImageGeneration={host => <StudioComicImageGeneration {...host} client={client} production={production} canMutate canReview />} />);
  fireEvent.click(await screen.findByRole('button', { name: '打开布局 Test' }));
  await recoverApproved();
  expect((screen.getByLabelText('漫画布局名称') as HTMLInputElement).closest('fieldset')?.disabled).toBe(true);
  expect(dirty).toHaveBeenLastCalledWith(true);
  fireEvent.click(button('明确采用已审核图片到此格框草稿'));
  await waitFor(() => expect((screen.getByLabelText('格框 1 已批准图片') as HTMLSelectElement).value).toBe('asset'));
  expect(saved.version).toBe(2); expect(saved.status).toBe('DRAFT'); expect(saved.document!.panels[1]).toEqual(page.document!.panels[1]);
  await waitFor(() => expect(dirty).toHaveBeenLastCalledWith(false));
  expect(experimental.put).not.toHaveBeenCalled(); expect(experimental.post).not.toHaveBeenCalled();
});
