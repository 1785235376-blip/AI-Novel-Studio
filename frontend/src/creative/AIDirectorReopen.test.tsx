// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AIDirectorPanel } from './AIDirectorPanel';
import { creativeClient, type DirectorProposal } from './client';
import { newDocument, newScene, type CreativeDocument } from './types';

const digest = 'a'.repeat(64);
const source = (): CreativeDocument => ({ ...newDocument('SCREENPLAY'), id: 'screenplay', version: 4, title: 'Source screenplay',
  status: 'DRAFT', source_independent: true, scenes: [{ ...newScene(1), id: 'scene' }], created_at: '', updated_at: '', actor_id: 'author', source_evidence: {} });
const accepted = (): DirectorProposal => ({ id: 'proposal', version: 2, status: 'APPROVED', title: 'Accepted direction',
  source_document_id: 'screenplay', source_version: 4, source_digest: digest, document_id: 'director',
  director_notes: [], output_digest: 'b'.repeat(64), provenance: { model_called: false } });
const draft = (): CreativeDocument => ({ ...source(), id: 'director', version: 3, title: 'Edited original draft', mode: 'DIRECTOR',
  source_independent: false, source_documents: { screenplay: { version: 4, digest } } });
const response = (body: unknown, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => body });
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(done => { resolve = done; }); return { promise, resolve }; }
function setup(options: { row?: DirectorProposal; canMutate?: boolean; override?: (url: string, init: RequestInit) => unknown } = {}) {
  const row = options.row ?? accepted();
  const fetchMock = vi.fn(async (url: string, init: RequestInit = {}) => {
    const replacement = options.override?.(url, init); if (replacement !== undefined) return await replacement;
    if (url.endsWith('/model-routes')) return response({ items: [] });
    if (url.endsWith('/director-proposals')) return response({ items: [row] });
    if (url.endsWith('/director-proposals/proposal')) return response(row);
    if (url.endsWith('/documents/director')) return response(draft());
    throw new Error(`Unexpected request ${init.method} ${url}`);
  });
  vi.stubGlobal('fetch', fetchMock);
  const client = creativeClient('project', { sessionToken: 'captured-session', scope: { workspaceId: 'w', projectId: 'project', storylineId: 's', branchId: 'branch' } });
  const props = { client, documents: [source()], canMutate: options.canMutate ?? true,
    onDocument: vi.fn(), onDenied: vi.fn(), onOpenModels: vi.fn(), onPendingChange: vi.fn() };
  const view = render(<AIDirectorPanel {...props} />);
  return { view, props, fetchMock };
}
async function select() { fireEvent.click(await screen.findByRole('button', { name: /Accepted direction/ })); }
const reopen = () => fireEvent.click(screen.getByRole('button', { name: '核对并打开已采用的导演草稿' }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('original director proposal linked-draft reopen', () => {
  it('reopens the exact adopted draft after remount with distinct proposal and document statuses', async () => {
    const { view, props, fetchMock } = setup({ canMutate: false }); await select(); reopen();
    await waitFor(() => expect(props.onDocument).toHaveBeenCalledTimes(1));
    expect(props.onDocument).toHaveBeenCalledWith(draft());
    expect(screen.getByText('原文档 director · v3 · DRAFT')).toBeTruthy();
    expect(screen.getByText(/建议 APPROVED/)).toBeTruthy();
    expect(screen.getByText(/文档仍是 DRAFT；不代表制作审核通过/)).toBeTruthy();
    expect(props.onPendingChange).toHaveBeenLastCalledWith(false);
    view.unmount(); render(<AIDirectorPanel {...props} />); await select(); reopen();
    await waitFor(() => expect(props.onDocument).toHaveBeenCalledTimes(2));
    const reads = fetchMock.mock.calls.filter(([url]) => url.endsWith('/director-proposals/proposal') || url.endsWith('/documents/director'));
    expect(reads.map(([url]) => url.split('/').slice(-2).join('/'))).toEqual(['director-proposals/proposal', 'documents/director', 'director-proposals/proposal', 'documents/director']);
    for (const [, init] of fetchMock.mock.calls) {
      expect(init?.method).toBe('GET');
      expect(init?.headers).toMatchObject({ 'X-Session-Token': 'captured-session', 'X-Branch-Id': 'branch' });
    }
  });

  it.each(['NEEDS_REVIEW', 'CANCELLED'])('does not offer reopening for %s suggestions', async status => {
    const { props, fetchMock } = setup({ row: { ...accepted(), status } }); await select();
    expect(screen.queryByRole('button', { name: '核对并打开已采用的导演草稿' })).toBeNull();
    expect(props.onDocument).not.toHaveBeenCalled();
    expect(fetchMock.mock.calls.some(([url]) => url.includes('/documents/'))).toBe(false);
  });

  it.each([{ document_id: undefined }, { source_digest: undefined }, { source_digest: 'unverified' }])('fails closed on a legacy incomplete adoption receipt %j', async missing => {
    const { props, fetchMock } = setup({ row: { ...accepted(), ...missing } }); await select();
    expect((screen.getByRole('button', { name: '核对并打开已采用的导演草稿' }) as HTMLButtonElement).disabled).toBe(true);
    reopen(); expect(props.onDocument).not.toHaveBeenCalled();
    expect(fetchMock.mock.calls.some(([url]) => url.endsWith('/director-proposals/proposal'))).toBe(false);
  });

  it.each([
    { status: 'CANCELLED' }, { document_id: 'another-director' }, { source_digest: 'c'.repeat(64) }, { source_version: 5 }, { version: 3 },
  ])('rejects a changed original proposal receipt %j without reading its document', async changed => {
    const { props, fetchMock } = setup({ override: url => url.endsWith('/director-proposals/proposal') ? response({ ...accepted(), ...changed }) : undefined });
    await select(); reopen(); await screen.findByText('建议与采用回执不一致，请重新读取建议状态。');
    expect(props.onDocument).not.toHaveBeenCalled();
    expect(fetchMock.mock.calls.some(([url]) => url.includes('/documents/'))).toBe(false);
  });

  it.each([
    { id: 'different' }, { mode: 'STORYBOARD' }, { version: 0 }, { status: 'ARCHIVED' },
    { source_documents: {} }, { source_documents: { screenplay: { version: 5, digest } } },
    { source_documents: { screenplay: { version: 4, digest: 'c'.repeat(64) } } },
  ])('rejects a mismatched original draft %j', async changed => {
    const { props } = setup({ override: url => url.endsWith('/documents/director') ? response({ ...draft(), ...changed }) : undefined });
    await select(); reopen(); await screen.findByText('原导演草稿与建议来源不一致，未打开此结果。');
    expect(props.onDocument).not.toHaveBeenCalled();
  });

  it.each(['/director-proposals/proposal', '/documents/director'])('keeps the original stale-source error from %s', async path => {
    const { props, fetchMock } = setup({ override: url => url.endsWith(path) ? response({ code: 'CREATIVE_SOURCE_DOCUMENT_CHANGED', message: 'Source changed' }, 409) : undefined });
    await select(); reopen(); await screen.findByText(/CREATIVE_SOURCE_DOCUMENT_CHANGED/);
    expect(props.onDocument).not.toHaveBeenCalled(); expect(props.onPendingChange).toHaveBeenLastCalledWith(false);
    expect(screen.queryByText(/操作结果需核对/)).toBeNull();
    expect(fetchMock.mock.calls.every(([, init]) => init?.method === 'GET')).toBe(true);
  });

  it('coalesces double clicks and ignores a late read across owner A→B→A', async () => {
    const pending = deferred<ReturnType<typeof response>>();
    const { view, props, fetchMock } = setup({ override: url => url.endsWith('/documents/director') ? pending.promise : undefined });
    await select(); act(() => { reopen(); reopen(); });
    await waitFor(() => expect(fetchMock.mock.calls.filter(([url]) => url.endsWith('/documents/director'))).toHaveLength(1));
    expect(props.onPendingChange).toHaveBeenLastCalledWith(true);
    const another = creativeClient('other', { sessionToken: 'other-session' });
    view.rerender(<AIDirectorPanel {...props} client={another} />);
    view.rerender(<AIDirectorPanel {...props} />);
    await act(async () => pending.resolve(response(draft())));
    expect(props.onDocument).not.toHaveBeenCalled(); expect(screen.queryByText('原文档 director · v3 · DRAFT')).toBeNull();
  });

  it('ignores a readback after closing the original panel', async () => {
    const pending = deferred<ReturnType<typeof response>>();
    const { view, props, fetchMock } = setup({ override: url => url.endsWith('/director-proposals/proposal') ? pending.promise : undefined });
    await select(); reopen(); view.unmount(); await act(async () => pending.resolve(response(accepted())));
    expect(props.onDocument).not.toHaveBeenCalled();
    expect(fetchMock.mock.calls.some(([url]) => url.endsWith('/documents/director'))).toBe(false);
  });

  it('reports edited review and uncertain adoption as pending without losing the typed review', async () => {
    const row = { ...accepted(), status: 'NEEDS_REVIEW', document_id: null };
    const { props } = setup({ row, override: url => url.endsWith('/review') ? response({ code: 'WRITE_RECEIPT_UNKNOWN' }, 500) : undefined });
    await select(); expect(props.onPendingChange).toHaveBeenLastCalledWith(false);
    fireEvent.change(screen.getByLabelText('采用后的导演文档标题'), { target: { value: 'Preserve this review' } });
    expect(props.onPendingChange).toHaveBeenLastCalledWith(true);
    fireEvent.click(screen.getByLabelText('已核对来源、场面调度与导演建议；创建独立导演文档'));
    fireEvent.click(screen.getByRole('button', { name: '审核并采用' }));
    await screen.findByText(/操作结果需核对/);
    expect(screen.getByDisplayValue('Preserve this review')).toBeTruthy();
    expect(props.onPendingChange).toHaveBeenLastCalledWith(true); expect(props.onDocument).not.toHaveBeenCalled();
  });

  it('clears pending edits after explicit adoption and shows the original DRAFT status without rebinding anything', async () => {
    const row = { ...accepted(), status: 'NEEDS_REVIEW', document_id: null };
    const { props, fetchMock } = setup({ row, override: url => url.endsWith('/review') ? response({ proposal: accepted(), document: draft() }) : undefined });
    await select();
    fireEvent.change(screen.getByLabelText('采用后的导演文档标题'), { target: { value: 'Human title' } });
    fireEvent.click(screen.getByLabelText('已核对来源、场面调度与导演建议；创建独立导演文档'));
    fireEvent.click(screen.getByRole('button', { name: '审核并采用' }));
    await waitFor(() => expect(props.onDocument).toHaveBeenCalledWith(draft()));
    expect(props.onPendingChange).toHaveBeenLastCalledWith(false);
    expect(screen.getByText('原文档 director · v3 · DRAFT')).toBeTruthy();
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method !== 'GET').map(([url]) => url.split('/').pop())).toEqual(['review']);
  });

  it('allows explicit local-review discard without cancelling the saved suggestion or writing anything', async () => {
    const row = { ...accepted(), status: 'NEEDS_REVIEW', document_id: null };
    const { props, fetchMock } = setup({ row }); await select();
    fireEvent.change(screen.getByLabelText('采用后的导演文档标题'), { target: { value: 'Unsaved human title' } });
    expect(props.onPendingChange).toHaveBeenLastCalledWith(true);
    expect((screen.getByRole('button', { name: '放弃本地审核修改，恢复原建议' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByLabelText('确认放弃本地审核修改并恢复原建议'));
    fireEvent.click(screen.getByRole('button', { name: '放弃本地审核修改，恢复原建议' }));
    expect(screen.getByDisplayValue('Accepted direction')).toBeTruthy();
    expect(props.onPendingChange).toHaveBeenLastCalledWith(false);
    expect(fetchMock.mock.calls.every(([, init]) => init?.method === 'GET')).toBe(true);
  });

  it('retires a late accepted review when the original client changes', async () => {
    const pending = deferred<ReturnType<typeof response>>();
    const row = { ...accepted(), status: 'NEEDS_REVIEW', document_id: null };
    const { view, props } = setup({ row, override: url => url.endsWith('/review') ? pending.promise : undefined });
    await select(); fireEvent.click(screen.getByLabelText('已核对来源、场面调度与导演建议；创建独立导演文档'));
    fireEvent.click(screen.getByRole('button', { name: '审核并采用' }));
    view.rerender(<AIDirectorPanel {...props} client={creativeClient('another-project', { sessionToken: 'other-session' })} />);
    await act(async () => pending.resolve(response({ proposal: accepted(), document: draft() })));
    expect(props.onDocument).not.toHaveBeenCalled();
    expect(screen.queryByText('原文档 director · v3 · DRAFT')).toBeNull();
  });

  it('preserves edits across queue, new-proposal and optional-model replacement until explicit discard', async () => {
    const first = { ...accepted(), status: 'NEEDS_REVIEW', document_id: null };
    const second = { ...first, id: 'another-proposal', title: 'Another direction' };
    const { props, fetchMock } = setup({ row: first, override: url => {
      if (url.endsWith('/director-proposals')) return response({ items: [first, second] });
      if (url.endsWith('/model-routes')) return response({ items: [{ route_id: 'local-route', provider_id: 'local', model_id: 'human-fixture', synthetic: false, available: true, reasons: [] }] });
    } });
    await select(); await waitFor(() => expect((screen.getByRole('button', { name: '预览模型输入' }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.change(screen.getByLabelText('采用后的导演文档标题'), { target: { value: 'Keep these human edits' } });
    for (const name of [/Accepted direction/, /Another direction/, '准备待审导演建议', '预览模型输入']) {
      const button = screen.getByRole('button', { name });
      expect((button as HTMLButtonElement).disabled).toBe(true); fireEvent.click(button);
    }
    expect(screen.getByDisplayValue('Keep these human edits')).toBeTruthy();
    expect(props.onPendingChange).toHaveBeenLastCalledWith(true);
    fireEvent.click(screen.getByLabelText('确认放弃本地审核修改并恢复原建议'));
    fireEvent.change(screen.getByLabelText('采用后的导演文档标题'), { target: { value: 'A newer edit needs confirmation again' } });
    expect((screen.getByRole('button', { name: '放弃本地审核修改，恢复原建议' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByLabelText('确认放弃本地审核修改并恢复原建议'));
    fireEvent.click(screen.getByRole('button', { name: '放弃本地审核修改，恢复原建议' }));
    fireEvent.click(screen.getByRole('button', { name: /Another direction/ }));
    expect(screen.getByDisplayValue('Another direction')).toBeTruthy();
    expect(props.onPendingChange).toHaveBeenLastCalledWith(false);
    expect(fetchMock.mock.calls.every(([, init]) => init?.method === 'GET')).toBe(true);
  });

  it('preserves local review on failed and successful uncertainty reads until explicitly adopting the checked status', async () => {
    const first = { ...accepted(), status: 'NEEDS_REVIEW', document_id: null };
    let reviews = 0, statusReads = 0;
    const { props, fetchMock } = setup({ row: first, override: (url, init) => {
      if (url.endsWith('/review')) { reviews++; return response({ code: 'WRITE_RECEIPT_UNKNOWN' }, 500); }
      if (url.endsWith('/director-proposals') && init.method === 'GET' && reviews) {
        statusReads++; return statusReads === 1 ? response({ code: 'READ_FAILED' }, 500) : response({ items: [accepted()] });
      }
    } });
    await select(); fireEvent.change(screen.getByLabelText('采用后的导演文档标题'), { target: { value: 'Preserve uncertain human review' } });
    fireEvent.click(screen.getByLabelText('已核对来源、场面调度与导演建议；创建独立导演文档'));
    fireEvent.click(screen.getByRole('button', { name: '审核并采用' })); await screen.findByText(/操作结果需核对/);
    fireEvent.click(screen.getByRole('button', { name: '重新读取建议状态' })); await screen.findByText(/READ_FAILED/);
    expect(screen.getByDisplayValue('Preserve uncertain human review')).toBeTruthy();
    expect(screen.queryByRole('button', { name: '处理已核对的建议状态' })).toBeNull();
    expect(props.onPendingChange).toHaveBeenLastCalledWith(true);
    fireEvent.click(screen.getByRole('button', { name: '重新读取建议状态' })); await screen.findByText('原建议当前状态：APPROVED');
    expect(screen.getByDisplayValue('Preserve uncertain human review')).toBeTruthy();
    expect((screen.getByRole('button', { name: '处理已核对的建议状态' }) as HTMLButtonElement).disabled).toBe(true);
    expect(props.onDocument).not.toHaveBeenCalled();
    fireEvent.click(screen.getByLabelText('确认放弃本地审核修改并采用已读取建议状态'));
    fireEvent.click(screen.getByRole('button', { name: '处理已核对的建议状态' }));
    expect(screen.getByRole('button', { name: '核对并打开已采用的导演草稿' })).toBeTruthy();
    expect(props.onPendingChange).toHaveBeenLastCalledWith(false); expect(props.onDocument).not.toHaveBeenCalled();
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method !== 'GET').map(([url]) => url.split('/').pop())).toEqual(['review']);
  });

  it('does not treat a missing recovery row as proof the prior write never happened', async () => {
    const first = { ...accepted(), status: 'NEEDS_REVIEW', document_id: null };
    let submitted = false;
    const { props, fetchMock } = setup({ row: first, override: (url, init) => {
      if (url.endsWith('/review')) { submitted = true; return response({ code: 'WRITE_RECEIPT_UNKNOWN' }, 500); }
      if (url.endsWith('/director-proposals') && init.method === 'GET' && submitted) return response({ items: [] });
    } });
    await select(); fireEvent.change(screen.getByLabelText('采用后的导演文档标题'), { target: { value: 'Local review before source changed' } });
    fireEvent.click(screen.getByLabelText('已核对来源、场面调度与导演建议；创建独立导演文档'));
    fireEvent.click(screen.getByRole('button', { name: '审核并采用' })); await screen.findByText(/操作结果需核对/);
    fireEvent.click(screen.getByRole('button', { name: '重新读取建议状态' })); await screen.findByText(/当前列表未匹配到原建议/);
    expect(screen.getByDisplayValue('Local review before source changed')).toBeTruthy();
    fireEvent.click(screen.getByLabelText('确认放弃本地审核修改并采用已读取建议状态'));
    fireEvent.click(screen.getByRole('button', { name: '处理已核对的建议状态' }));
    expect(screen.getByText(/读取列表不能证明请求未执行/)).toBeTruthy();
    expect(props.onDocument).not.toHaveBeenCalled();
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method !== 'GET')).toHaveLength(1);
  });

  it('preserves the separate preparation target when explicitly discarding an uncertain review', async () => {
    const first = { ...accepted(), status: 'NEEDS_REVIEW', document_id: null };
    let submitted = false;
    const { props, fetchMock } = setup({ row: first, override: (url, init) => {
      if (url.endsWith('/review')) { submitted = true; return response({ code: 'WRITE_RECEIPT_UNKNOWN' }, 500); }
      if (url.endsWith('/director-proposals') && init.method === 'GET' && submitted) return response({ items: [accepted()] });
    } });
    await select();
    fireEvent.change(screen.getByLabelText('建议准备 视觉风格'), { target: { value: 'Separate unsubmitted preparation' } });
    fireEvent.change(screen.getByLabelText('采用后的导演文档标题'), { target: { value: 'Uncertain review title' } });
    fireEvent.click(screen.getByLabelText('已核对来源、场面调度与导演建议；创建独立导演文档'));
    fireEvent.click(screen.getByRole('button', { name: '审核并采用' })); await screen.findByText(/操作结果需核对/);
    fireEvent.click(screen.getByRole('button', { name: '重新读取建议状态' })); await screen.findByText('原建议当前状态：APPROVED');
    fireEvent.click(screen.getByLabelText('确认放弃本地审核修改并采用已读取建议状态'));
    fireEvent.click(screen.getByRole('button', { name: '处理已核对的建议状态' }));
    expect(screen.getByDisplayValue('Separate unsubmitted preparation')).toBeTruthy();
    expect(props.onPendingChange).toHaveBeenLastCalledWith(true);
    expect(screen.getByRole('button', { name: '清空未提交的视觉目标' })).toBeTruthy();
    expect(props.onDocument).not.toHaveBeenCalled();
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method !== 'GET')).toHaveLength(1);
  });

  it('never uses a previously selected proposal as the receipt for an unknown creation', async () => {
    const first = { ...accepted(), status: 'NEEDS_REVIEW', document_id: null };
    const { props, fetchMock } = setup({ row: first, override: (url, init) => {
      if (url.endsWith('/director-proposals') && init.method === 'POST') return response({ code: 'CREATE_RECEIPT_UNKNOWN' }, 500);
    } });
    await select();
    fireEvent.change(screen.getByLabelText('建议准备 视觉风格'), { target: { value: 'Preparation with unknown receipt' } });
    fireEvent.click(screen.getByRole('button', { name: '准备待审导演建议' })); await screen.findByText(/操作结果需核对/);
    fireEvent.click(screen.getByRole('button', { name: '重新读取建议状态' }));
    await screen.findByText(/当前选中建议不能作为该请求回执/);
    expect(screen.queryByText('原建议当前状态：NEEDS_REVIEW')).toBeNull();
    fireEvent.click(screen.getByLabelText('确认放弃本地审核修改并采用已读取建议状态'));
    fireEvent.click(screen.getByRole('button', { name: '处理已核对的建议状态' }));
    expect(screen.getByText(/读取列表不能证明请求未执行/)).toBeTruthy();
    expect(screen.getByDisplayValue('Preparation with unknown receipt')).toBeTruthy();
    expect(props.onPendingChange).toHaveBeenLastCalledWith(true);
    expect(props.onDocument).not.toHaveBeenCalled();
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method !== 'GET').map(([url]) => url.split('/').pop())).toEqual(['director-proposals']);
  });
});
