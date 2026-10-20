// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AIDirectorPanel } from './AIDirectorPanel';
import { creativeClient, type DirectorProposal } from './client';
import { newDocument, newScene, type CreativeDocument } from './types';

function source(): CreativeDocument { return { ...newDocument('SCREENPLAY', 'chapter-1'), id: 'screenplay-1', version: 4, title: 'Source screenplay', status: 'DRAFT', created_at: '', updated_at: '', actor_id: 'author', source_evidence: {}, scenes: [{ ...newScene(1, 'chapter-1'), id: 'scene-1', heading: 'The harbor' }] }; }
function suggestion(): DirectorProposal { return { id: 'proposal-1', version: 2, status: 'NEEDS_REVIEW', source_document_id: 'screenplay-1', source_version: 4, title: 'Harbor direction', director_notes: [{ id: 'note-1', number: 1, scene_id: 'scene-1', note: 'Let the silence build', shot_size: 'WIDE', camera_angle: 'EYE_LEVEL', camera_motion: 'STATIC', duration_seconds: 5, emotion: 'Tense', pacing: 'Slow', performance: 'Understated', blocking: 'Stand beside the rail' }], output_digest: 'reviewed-digest', provenance: { model_called: false } }; }
function response(body: unknown, status = 200) { return { ok: status >= 200 && status < 300, status, json: async () => body }; }
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(done => { resolve = done; }); return { promise, resolve }; }
function setup(options: { proposals?: DirectorProposal[]; canMutate?: boolean; override?: (url: string, init: RequestInit) => unknown } = {}) {
  const fetchMock = vi.fn(async (url: string, init: RequestInit = {}) => {
    const result = options.override?.(url, init); if (result !== undefined) return await result;
    if (url.endsWith('/model-routes')) return response({ items: [] });
    if (url.endsWith('/director-proposals') && init?.method === 'GET') return response({ items: options.proposals || [] });
    if (url.endsWith('/director-proposals') && init?.method === 'POST') return response(suggestion());
    if (url.endsWith('/review')) return response({ proposal: { ...suggestion(), status: 'APPROVED', version: 3 }, document: { ...source(), mode: 'DIRECTOR', id: 'director-1', title: JSON.parse(String(init.body)).title } });
    if (url.endsWith('/cancel')) return response({ ...suggestion(), status: 'CANCELLED', version: 3 });
    throw new Error(`Unexpected request ${init?.method} ${url}`);
  });
  vi.stubGlobal('fetch', fetchMock);
  const onDocument = vi.fn(), onDenied = vi.fn(), onBusyChange = vi.fn();
  const client = creativeClient('novel-1', { sessionToken: 'captured-session', scope: { workspaceId: 'w', projectId: 'p', storylineId: 's', branchId: 'captured-branch' } });
  const view = render(<AIDirectorPanel client={client} documents={[source()]} canMutate={options.canMutate ?? true} onDocument={onDocument} onDenied={onDenied} onBusyChange={onBusyChange} onOpenModels={() => {}} />);
  return { fetchMock, onDocument, onDenied, onBusyChange, view, mutations: () => fetchMock.mock.calls.filter(([, init]) => init?.method !== 'GET') };
}
async function prepare() { fireEvent.click(screen.getByRole('button', { name: '准备待审导演建议' })); await screen.findByLabelText('采用后的导演文档标题'); }
const reviewCheck = () => screen.getByLabelText('已核对来源、场面调度与导演建议；创建独立导演文档');
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('AI director local proposal and explicit review', () => {
  it('honestly prepares local rules without model calls and requires reviewed edited output before adoption', async () => {
    const { fetchMock, mutations, onDocument } = setup(); await screen.findByText('没有待审导演建议');
    expect(screen.getByText(/本地规则辅助会整理场景调度草案。不会调用模型/)).toBeTruthy(); await prepare();
    expect(screen.getByText('本地规则辅助 · 未调用模型')).toBeTruthy(); expect(screen.getByText('建议已生成，等待逐项核对。未调用模型。')).toBeTruthy();
    const adopt = screen.getByRole('button', { name: '审核并采用' }) as HTMLButtonElement;
    expect(adopt.disabled).toBe(true); fireEvent.click(adopt); expect(mutations()).toHaveLength(1); expect(onDocument).not.toHaveBeenCalled();
    fireEvent.click(reviewCheck()); expect(adopt.disabled).toBe(false);
    fireEvent.change(screen.getByLabelText('采用后的导演文档标题'), { target: { value: 'Reviewed direction' } }); expect((reviewCheck() as HTMLInputElement).checked).toBe(false); expect(adopt.disabled).toBe(true);
    fireEvent.click(screen.getByText('场景调度 1'));
    fireEvent.change(screen.getByLabelText('建议 1 导演意图'), { target: { value: 'Reviewed intention' } });
    fireEvent.click(reviewCheck()); fireEvent.click(adopt); await screen.findByText('已创建导演文档。小说正文保持原有保存与审核流程。');
    expect(mutations()).toHaveLength(2); const [created, reviewed] = mutations();
    expect(JSON.parse(String(created[1]?.body))).toEqual({ source_document_id: 'screenplay-1', expected_source_version: 4 });
    expect(JSON.parse(String(reviewed[1]?.body))).toMatchObject({ expected_version: 2, reviewed_output_digest: 'reviewed-digest', title: 'Reviewed direction', director_notes: [{ note: 'Reviewed intention' }] });
    for (const [, init] of mutations()) expect(init?.headers).toMatchObject({ 'X-Session-Token': 'captured-session', 'X-Branch-Id': 'captured-branch' });
    expect(onDocument).toHaveBeenCalledWith(expect.objectContaining({ id: 'director-1', mode: 'DIRECTOR', title: 'Reviewed direction' }));
    expect(fetchMock.mock.calls.filter(([url, init]) => init?.method !== 'GET' && /model|generation|chapter/.test(url))).toHaveLength(0);
  });

  it('coalesces repeated propose clicks and reports busy while awaiting its receipt', async () => {
    const pending = deferred<ReturnType<typeof response>>();
    const { mutations, onBusyChange } = setup({ override: (url, init) => url.endsWith('/director-proposals') && init?.method === 'POST' ? pending.promise : undefined });
    const button = screen.getByRole('button', { name: '准备待审导演建议' });
    act(() => { button.dispatchEvent(new MouseEvent('click', { bubbles: true })); button.dispatchEvent(new MouseEvent('click', { bubbles: true })); });
    expect(mutations()).toHaveLength(1); expect(onBusyChange).toHaveBeenLastCalledWith(true);
    await act(async () => pending.resolve(response(suggestion()))); await screen.findByLabelText('采用后的导演文档标题'); expect(onBusyChange).toHaveBeenLastCalledWith(false);
  });

  it('coalesces repeated review clicks into one version-bound mutation', async () => {
    const pending = deferred<ReturnType<typeof response>>(); const { mutations, onDocument } = setup({ override: url => url.endsWith('/review') ? pending.promise : undefined }); await prepare();
    fireEvent.click(reviewCheck()); const button = screen.getByRole('button', { name: '审核并采用' });
    act(() => { button.dispatchEvent(new MouseEvent('click', { bubbles: true })); button.dispatchEvent(new MouseEvent('click', { bubbles: true })); });
    expect(mutations().filter(([url]) => url.endsWith('/review'))).toHaveLength(1); expect(onDocument).not.toHaveBeenCalled();
    await act(async () => pending.resolve(response({ proposal: { ...suggestion(), status: 'APPROVED', version: 3 }, document: { ...source(), id: 'director-1', mode: 'DIRECTOR' } })));
    expect(onDocument).toHaveBeenCalledTimes(1);
  });

  it('preserves edited review content and blocks retry after a version conflict', async () => {
    const { mutations, onDocument } = setup({ override: url => url.endsWith('/review') ? response({ code: 'PROPOSAL_VERSION_CONFLICT' }, 409) : undefined }); await prepare();
    fireEvent.change(screen.getByLabelText('采用后的导演文档标题'), { target: { value: 'Keep reviewed title' } }); fireEvent.click(reviewCheck()); fireEvent.click(screen.getByRole('button', { name: '审核并采用' }));
    await screen.findByText(/操作结果需核对。当前审核内容已保留/);
    expect((screen.getByLabelText('采用后的导演文档标题') as HTMLInputElement).value).toBe('Keep reviewed title'); expect(screen.getByLabelText('采用后的导演文档标题').closest('fieldset')!.disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: '审核并采用' })); expect(mutations()).toHaveLength(2); expect(onDocument).not.toHaveBeenCalled();
  });

  it('keeps uncertainty locked when a recovery read fails', async () => {
    let failRead = false; const { mutations } = setup({ override: (url, init) => {
      if (url.endsWith('/director-proposals') && init?.method === 'POST') { failRead = true; return response({ code: 'RECEIPT_UNKNOWN' }, 500); }
      if (url.endsWith('/director-proposals') && init?.method === 'GET' && failRead) return response({ code: 'READ_FAILED' }, 500);
    } });
    fireEvent.click(screen.getByRole('button', { name: '准备待审导演建议' })); await screen.findByText(/操作结果需核对。当前审核内容已保留/);
    fireEvent.click(screen.getByRole('button', { name: '重新读取建议状态' })); await screen.findByText(/READ_FAILED/);
    expect((screen.getByRole('button', { name: '准备待审导演建议' }) as HTMLButtonElement).disabled).toBe(true); fireEvent.click(screen.getByRole('button', { name: '准备待审导演建议' })); expect(mutations()).toHaveLength(1);
  });

  it('notifies the workspace on denied proposal reads', async () => {
    const { onDenied, mutations } = setup({ override: (url, init) => url.endsWith('/director-proposals') && init?.method === 'GET' ? response({ code: 'FORBIDDEN' }, 403) : undefined });
    await waitFor(() => expect(onDenied).toHaveBeenCalledTimes(1)); expect(mutations()).toHaveLength(0);
  });

  it('keeps read-only proposal creation disabled', async () => {
    const { mutations } = setup({ canMutate: false }); await screen.findByText('没有待审导演建议');
    expect((screen.getByRole('button', { name: '准备待审导演建议' }) as HTMLButtonElement).disabled).toBe(true); fireEvent.click(screen.getByRole('button', { name: '准备待审导演建议' })); expect(mutations()).toHaveLength(0);
  });

  it('ignores late proposal creation after the panel is unmounted', async () => {
    const pending = deferred<ReturnType<typeof response>>(); const { view, onDocument } = setup({ override: (url, init) => url.endsWith('/director-proposals') && init?.method === 'POST' ? pending.promise : undefined });
    fireEvent.click(screen.getByRole('button', { name: '准备待审导演建议' })); view.unmount(); await act(async () => pending.resolve(response(suggestion()))); expect(onDocument).not.toHaveBeenCalled();
  });
  it.each([401, 403])('keeps manual review available when optional model routes return %i', async status => {
    const { onDenied, onDocument, mutations } = setup({ override: url => url.endsWith('/model-routes') ? response({ code: 'HOST_AUTH_REQUIRED' }, status) : undefined });
    await prepare(); await screen.findByText('本地模型路由尚不可用。可以继续审核规则辅助建议。');
    expect(onDenied).not.toHaveBeenCalled(); expect(screen.getByLabelText('采用后的导演文档标题').closest('fieldset')!.disabled).toBe(false);
    fireEvent.click(reviewCheck()); fireEvent.click(screen.getByRole('button', { name: '审核并采用' })); await waitFor(() => expect(onDocument).toHaveBeenCalledTimes(1));
    expect(mutations().map(([url]) => url.split('/').pop())).toEqual(['director-proposals', 'review']);
  });

});
