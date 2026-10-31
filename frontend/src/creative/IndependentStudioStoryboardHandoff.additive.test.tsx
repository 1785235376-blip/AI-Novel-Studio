// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useStudio } from '../store';
import { useLocalHostSession } from '../localHostSession';
import { IndependentStudioWorkspace, type IndependentStudioProps } from './IndependentStudioWorkspace';
import type { CreativeDocument } from './types';
import type { StudioAsset, StudioOverview } from './studioClient';
import type { StoryboardReceipt } from './studioStoryboardContract';
import receiptFixture from './fixtures/phase4.file-api-storyboard.json';
import emptyPromptLibrary from '../prompt/__fixtures__/empty-library.json';
const id = 'neutral-project', base = `/api/projects/${id}/studio`, creative = `/api/novels/${id}/experimental/creative`;
const initial = receiptFixture as StoryboardReceipt;
const image: StudioAsset = { id: 'handoff-image', novel_id: id, branch_id: null, filename: 'handoff.png', kind: 'image', media_type: 'image/png', size: 3, sha256: 'a'.repeat(64), version: 2, created_at: '2026-10-16T00:00:00Z', updated_at: '2026-10-16T00:00:00Z', deleted_at: null };
const pin = { asset_id: image.id, version: image.version, digest: image.sha256, kind: 'image' };
const doc = (r: StoryboardReceipt): CreativeDocument => ({ id: r.document_snapshot.id, version: r.document_snapshot.version, mode: 'STORYBOARD', title: 'Existing storyboard', status: 'DRAFT', created_at: '', updated_at: '', actor_id: 'author', source_evidence: {}, source_chapter_ids: [], source_independent: true, scenes: [], director_notes: [], shots: r.shots.map(s => structuredClone(s.shot)), video_plan: null });
const overview: StudioOverview = { project: { id, title: '独立项目', entry_kind: 'NEUTRAL_STUDIO' }, preferences: { version: 1, intents: [], preset: 'BLANK', custom_intent: '' }, capabilities: { can_mutate: true, manual_import: true, manual_export: true, model_required: false, chapter_required: false, intent_is_permission: false, media_validator_configured: true, asset_kinds: ['image', 'video', 'audio'] } };
const response = (body: unknown, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => body, blob: async () => new Blob(['png'], { type: 'image/png' }) });
let calls: ReturnType<typeof vi.fn>, saved: StoryboardReceipt, source: StudioAsset;
type Override = (url: string, init: RequestInit) => unknown;
function server(override?: Override) {
  calls = vi.fn(async (url: string, init: RequestInit = {}) => {
    const overridden = override?.(url, init); if (overridden !== undefined) return await overridden;
    if (url === base) return response(overview);
    if (url === `${base}/prompts`) return response({ ...emptyPromptLibrary, project_id: id, scope: { mode: 'local', novel_id: id } });
    if (url === `${base}/assets` || url.startsWith(`${base}/assets?`)) return response({ items: [source] });
    if (url === `${base}/assets/${image.id}`) return response(source);
    if (url.endsWith('/download')) return response({});
    if (url.endsWith('/providers') || url.endsWith('/timelines')) return response({ items: [] });
    if (url === `${creative}/documents`) return response({ items: [doc(saved), { ...doc(saved), id: 'not-storyboard', mode: 'DIRECTOR', title: 'Other mode' }] });
    if (url === `${creative}/documents/${initial.document_snapshot.id}`) return response(doc(saved));
    if (url === `${creative}/documents/${initial.document_snapshot.id}/storyboard`) return response(saved);
    if (url === `${creative}/documents/${initial.document_snapshot.id}/shots/shot-1/image-binding` && init.method === 'POST') {
      saved = { ...structuredClone(saved), approved: false, document_snapshot: { ...saved.document_snapshot, version: saved.document_snapshot.version + 1 }, shots: saved.shots.map((shot, index) => index ? shot : { ...shot, image_asset: pin as NonNullable<typeof shot.image_asset> }) };
      return response(saved);
    }
    throw new Error(`Unexpected ${init.method} ${url}`);
  }); vi.stubGlobal('fetch', calls);
}
function mount() {
  const props: IndependentStudioProps = { projectId: id, context: { sessionToken: '' }, scope: { workspace: '本机作品', project: '独立项目', storyline: '默认故事线', branch: '主线' }, actor: '作者', module: 'IMAGE', onModuleChange: vi.fn(), onProjectChoice: vi.fn() };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><IndependentStudioWorkspace {...props} /></QueryClientProvider>);
}
const button = (name: string) => screen.getByRole('button', { name }) as HTMLButtonElement;
const writes = () => calls.mock.calls.filter(([, init]) => init.method !== 'GET');
async function chooseRoute() {
  const view = mount(); await screen.findByRole('button', { name: '上传资产' });
  fireEvent.click(await screen.findByRole('button', { name: '选择素材 handoff.png' }));
  fireEvent.click(await screen.findByRole('button', { name: '分镜模块' })); return view;
}
async function enter() { const view = await chooseRoute(); fireEvent.click(button('生成引用（不执行目标模块）')); await screen.findByRole('region', { name: '已有分镜图片接收器' }); return view; }
async function selectTarget() {
  fireEvent.click(button('读取已有分镜文档目录')); await screen.findByRole('option', { name: 'Existing storyboard · v4' });
  expect(screen.queryByRole('option', { name: /Other mode/ })).toBeNull();
  expect((screen.getByLabelText('已有分镜文档') as HTMLSelectElement).value).toBe('');
  fireEvent.change(screen.getByLabelText('已有分镜文档'), { target: { value: initial.document_snapshot.id } });
  fireEvent.click(button('核对所选分镜文档')); await screen.findByRole('button', { name: '读取已有分镜回执' });
  fireEvent.click(button('读取已有分镜回执')); const shot = await screen.findByLabelText('明确选择已有镜头');
  expect((shot as HTMLSelectElement).value).toBe('');
  fireEvent.change(shot, { target: { value: 'shot-1' } });
  fireEvent.click(button('核对传入图片精确版本')); await screen.findByText('已核对正式图片：handoff.png · v2');
}
beforeEach(() => {
  localStorage.clear(); saved = structuredClone(initial); source = structuredClone(image);
  useStudio.setState({ novelId: id, chapterId: '', sessionToken: '', actor: undefined, scope: undefined }); useLocalHostSession.setState({ token: '', actorId: '' });
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:fixture') }); Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() }); server();
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
describe('real IndependentStudioWorkspace to original storyboard image binding', () => {
  it('keeps route/selection/inspection GET-only and sends one exact original-owner POST on final click', async () => {
    await enter(); expect(writes()).toEqual([]); expect(calls.mock.calls.some(([url]) => url.startsWith(creative))).toBe(false);
    await selectTarget(); expect(writes()).toEqual([]); expect(screen.getByText(/保存会创建新的分镜文档版本，并撤销旧分镜批准/)).toBeTruthy();
    fireEvent.click(button('保存图片绑定并撤销旧批准')); fireEvent.click(button('保存图片绑定并撤销旧批准'));
    await screen.findByText('图片绑定已保存为新文档版本，旧分镜批准已撤销。');
    expect(writes()).toHaveLength(1); const [url, init] = writes()[0];
    expect(url).toBe(`${creative}/documents/${initial.document_snapshot.id}/shots/shot-1/image-binding`);
    expect(JSON.parse(init.body)).toEqual({ expected_version: 4, shot_version: initial.shots[0].shot_version, shot_digest: initial.shots[0].shot_digest, asset: pin });
    expect(saved.document_snapshot.version).toBe(5); expect(saved.approved).toBe(false); expect(saved.shots.map(s => s.shot)).toEqual(initial.shots.map(s => s.shot));
    expect(screen.getByText('目标：Existing storyboard · v5')).toBeTruthy();
    expect(calls.mock.calls.some(([url]) => /providers|jobs|timeline|graph|image-request|approve/.test(url))).toBe(false);
    const postIndex = calls.mock.calls.findIndex(([, init]) => init.method === 'POST');
    expect(calls.mock.calls.slice(0, postIndex).filter(([url]) => url.endsWith('/storyboard'))).toHaveLength(2);
    expect(calls.mock.calls.slice(postIndex + 1).some(([url]) => url === `${creative}/documents/${initial.document_snapshot.id}`)).toBe(true);
  });
  it('preserves dirty-navigation cancellation and requires explicit discard before entering', async () => {
    await chooseRoute(); fireEvent.change(screen.getByLabelText('自定义意图'), { target: { value: 'Keep my unsaved work' } });
    fireEvent.click(button('生成引用（不执行目标模块）')); expect(screen.queryByRole('region', { name: '已有分镜图片接收器' })).toBeNull();
    fireEvent.click(button('继续编辑')); expect((screen.getByLabelText('自定义意图') as HTMLInputElement).value).toBe('Keep my unsaved work');
    fireEvent.click(button('生成引用（不执行目标模块）')); fireEvent.click(screen.getByLabelText('确认放弃未保存输入')); fireEvent.click(button('确认离开'));
    await screen.findByRole('region', { name: '已有分镜图片接收器' }); expect(writes()).toEqual([]);
  });
  it('cancelled recipient closes only after dirty confirmation and never saves', async () => {
    await enter(); await selectTarget(); fireEvent.click(button('关闭分镜图片接收器')); fireEvent.click(button('继续编辑'));
    expect(screen.getByRole('region', { name: '已有分镜图片接收器' })).toBeTruthy();
    fireEvent.click(button('关闭分镜图片接收器')); fireEvent.click(screen.getByLabelText('确认放弃未保存输入')); fireEvent.click(button('确认离开'));
    await waitFor(() => expect(screen.queryByRole('region', { name: '已有分镜图片接收器' })).toBeNull()); expect(writes()).toEqual([]);
  });
  it('source replacement after preview is rejected without any write', async () => {
    await enter(); await selectTarget(); source = { ...source, version: 3 };
    fireEvent.click(button('保存图片绑定并撤销旧批准')); await waitFor(() => expect(button('读取已有分镜回执').disabled).toBe(false)); expect(writes()).toEqual([]);
  });

  it.each(['network', '503', 'invalid receipt', 'refresh failure'] as const)('real transport UNKNOWN %s stays blocked after authoritative observation, never retries', async failure => {
    let documentReads = 0;
    server((url, init) => {
      if (url.endsWith('/image-binding') && init.method === 'POST' && failure !== 'refresh failure') {
        saved = { ...structuredClone(initial), approved: false, document_snapshot: { ...initial.document_snapshot, version: 5 }, shots: initial.shots.map((shot, i) => i ? structuredClone(shot) : { ...structuredClone(shot), image_asset: pin as NonNullable<typeof shot.image_asset> }) };
        if (failure === 'network') throw new TypeError('connection lost after dispatch');
        if (failure === '503') return response({ code: 'UNAVAILABLE' }, 503);
        return response({ ...saved, approved: true });
      }
      if (url === creative + '/documents/' + initial.document_snapshot.id && ++documentReads === 2 && failure === 'refresh failure') throw new Error('post-commit refresh offline');
      return undefined;
    });
    await enter(); await selectTarget(); fireEvent.click(button('保存图片绑定并撤销旧批准'));
    await screen.findByText('保存结果未知。保留本次图片与目标版本；不会自动重发，也不能再次保存。');
    expect(writes()).toHaveLength(1); expect(screen.queryByRole('button', { name: '保存图片绑定并撤销旧批准' })).toBeNull();
    fireEvent.click(button('读取原文档核对未知保存结果')); await screen.findByText(/已观察原文档当前版本含此绑定/);
    expect(screen.queryByText('图片绑定已保存为新文档版本，旧分镜批准已撤销。')).toBeNull();
    expect(screen.getByText('目标：Existing storyboard · v4')).toBeTruthy(); expect(writes()).toHaveLength(1);
    fireEvent.click(button('读取原文档核对未知保存结果')); await waitFor(() => expect(button('读取原文档核对未知保存结果').disabled).toBe(false)); expect(writes()).toHaveLength(1);
  });
  it.each(['session ABA', 'branch ABA', 'project ABA', 'unmount'] as const)('fences delayed authoritative source read after %s', async change => {
    let resolve!: (value: ReturnType<typeof response>) => void;
    const delayed = new Promise<ReturnType<typeof response>>(yes => { resolve = yes; }); let hold = false;
    server(url => url === base + '/assets/' + image.id && hold ? delayed : undefined);
    const view = await enter(); await selectTarget(); hold = true;
    const before = calls.mock.calls.filter(([url]) => url === base + '/assets/' + image.id).length;
    fireEvent.click(button('保存图片绑定并撤销旧批准'));
    await waitFor(() => expect(calls.mock.calls.filter(([url]) => url === base + '/assets/' + image.id)).toHaveLength(before + 1));
    act(() => {
      if (change === 'session ABA') { useStudio.setState({ sessionToken: 'other' }); useStudio.setState({ sessionToken: '' }); }
      if (change === 'branch ABA') { useStudio.setState({ scope: { workspaceId: 'w', projectId: id, storylineId: 's', branchId: 'other' } }); useStudio.setState({ scope: undefined }); }
      if (change === 'project ABA') { useStudio.setState({ novelId: 'other' }); useStudio.setState({ novelId: id }); }
    });
    if (change === 'unmount') view.unmount();
    await act(async () => { resolve(response(source)); await delayed; });
    expect(writes()).toEqual([]); expect(screen.queryByText('图片绑定已保存为新文档版本，旧分镜批准已撤销。')).toBeNull();
  });
  it('denied final source read clears the recipient and never posts a binding', async () => {
    let deny = false; server(url => deny && url === base + '/assets/' + image.id ? response({ code: 'FORBIDDEN' }, 403) : undefined);
    await enter(); await selectTarget(); deny = true; fireEvent.click(button('保存图片绑定并撤销旧批准'));
    await screen.findByText('当前会话无权访问此项目'); expect(screen.queryByRole('region', { name: '已有分镜图片接收器' })).toBeNull(); expect(writes()).toEqual([]);
  });

  it('isolates handoff actions and restores ordinary production controls after explicit close', async () => {
    await enter();
    for (const name of ['按需打开项目提示助手', '按需打开模型中心', '按需打开统一导出与工程交接', '添加视频轨道', '读取制作预览']) expect(screen.queryByRole('button', { name })).toBeNull();
    expect(screen.queryByRole('region', { name: '媒体制作输入' })).toBeNull(); expect(screen.queryByLabelText('Studio 多轨时间线编辑器')).toBeNull();
    fireEvent.click(button('关闭分镜图片接收器')); fireEvent.click(screen.getByLabelText('确认放弃未保存输入')); fireEvent.click(button('确认离开'));
    await screen.findByRole('button', { name: '按需打开模型中心' }); expect(screen.getByRole('region', { name: '媒体制作输入' })).toBeTruthy(); expect(screen.getByLabelText('Studio 多轨时间线编辑器')).toBeTruthy();
    expect(writes()).toEqual([]);
  });

  it.each(['document body', 'missing document shot', 'unrelated receipt shot', 'refresh 404', 'refresh 409'] as const)('real decoded save rejects %s and keeps the dispatched attempt locked', async failure => {
    let posted = false;
    server((url, init) => {
      if (url.endsWith('/image-binding') && init.method === 'POST') {
        posted = true;
        saved = { ...structuredClone(initial), approved: false, document_snapshot: { ...initial.document_snapshot, version: 5 }, shots: initial.shots.map((shot, i) => i ? structuredClone(shot) : { ...structuredClone(shot), image_asset: pin as NonNullable<typeof shot.image_asset> }) };
        if (failure === 'unrelated receipt shot') saved.shots[1].shot.frame_prompt = 'unexpected unrelated shot rewrite';
        return response(saved);
      }
      if (posted && url === creative + '/documents/' + initial.document_snapshot.id) {
        if (failure === 'refresh 404' || failure === 'refresh 409') return response({ code: 'REFRESH_FAILED' }, failure === 'refresh 404' ? 404 : 409);
        const document = doc(saved);
        if (failure === 'document body') document.shots[0].frame_prompt = 'unexpected refreshed body';
        if (failure === 'missing document shot') document.shots = document.shots.slice(1);
        return response(document);
      }
      return undefined;
    });
    await enter(); await selectTarget(); fireEvent.click(button('保存图片绑定并撤销旧批准'));
    await screen.findByText('保存结果未知。保留本次图片与目标版本；不会自动重发，也不能再次保存。');
    expect(screen.queryByText('图片绑定已保存为新文档版本，旧分镜批准已撤销。')).toBeNull();
    expect(screen.queryByRole('button', { name: '保存图片绑定并撤销旧批准' })).toBeNull(); expect(writes()).toHaveLength(1);
    expect(screen.getByText('目标：Existing storyboard · v4')).toBeTruthy();
  });
});
