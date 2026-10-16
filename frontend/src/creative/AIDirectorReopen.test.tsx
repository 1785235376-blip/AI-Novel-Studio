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
});
