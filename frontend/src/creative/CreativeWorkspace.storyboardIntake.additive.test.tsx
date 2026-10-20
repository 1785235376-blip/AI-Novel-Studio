// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CreativeWorkspace, type CreativeWorkspaceProps } from './CreativeWorkspace';
import { prepareStoryboardEditor, storyboardEditorRequest, type StoryboardEditorHost } from './storyboardEditorHandoff';
import { useLocalHostSession } from '../localHostSession';
import { newDocument, newScene, newShot, type CreativeDocument } from './types';
const pin = { id: 'source-director', version: 4, digest: 'a'.repeat(64) };
const caps = { enabled: true, can_mutate: true, modes: ['STORYBOARD' as const] };
function board(id = 'exact-second-board'): CreativeDocument {
  return { ...newDocument('STORYBOARD'), id, title: id, version: 8, status: 'DRAFT', actor_id: 'author', created_at: '', updated_at: '', source_evidence: {}, source_documents: { [pin.id]: { version: pin.version, digest: pin.digest } }, scenes: [{ ...newScene(1), id: 'scene' }], shots: [{ ...newShot(1, 'scene'), id: 'shot', frame_prompt: 'Original frame' }] };
}
function host(document = board(), module: 'IMAGE' | 'VIDEO' = 'IMAGE'): StoryboardEditorHost {
  const digest = 'b'.repeat(64), request = storyboardEditorRequest(document, digest, pin);
  return { module, prepared: prepareStoryboardEditor(request, { document, document_digest: digest }, caps), isCurrent: () => true, returnLabel: '返回独立创作图' };
}
function props(storyboardHost: StoryboardEditorHost): CreativeWorkspaceProps {
  return { enabled: true, novelId: 'neutral-project', context: { sessionToken: 'test' }, scope: { workspace: 'Local', project: 'Project', storyline: 'Story', branch: 'Main' }, actor: 'Author', chapterCount: 0, manuscriptReady: false, novelMain: null, novelSidebar: null, novelInspector: null, novelStatus: null, onExit: vi.fn(), onModuleChange: vi.fn(), storyboardHost };
}
const response = (body: unknown, status = 200) => ({ ok: status < 400, status, json: async () => body });
let fetchMock: ReturnType<typeof vi.fn>;
beforeEach(() => {
  fetchMock = vi.fn(async (url: string, init: RequestInit) => {
    if (init.method === 'PUT') return response({ ...board(), ...JSON.parse(String(init.body)), version: 9 });
    if (url.endsWith('/creation-reference-data')) return response({ characters: [], locations: [], story_routes: [] });
    if (url.endsWith('/assets')) return response([]);
    throw new Error(`Unexpected read ${url}`);
  }); vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
const edits = () => fetchMock.mock.calls.filter(([, init]) => init.method !== 'GET');
describe('prepared original storyboard editor intake', () => {
  it.each(['IMAGE', 'VIDEO'] as const)('renders exactly one original %s editor without first-document bootstrap or writes', async module => {
    render(<CreativeWorkspace {...props(host(board(), module))} />);
    expect((screen.getByLabelText('文档标题') as HTMLInputElement).value).toBe('exact-second-board');
    expect(screen.getByLabelText('原分镜精确文档').textContent).toContain(module);
    expect(screen.getAllByLabelText('分镜画布')).toHaveLength(1);
    expect((screen.getByRole('button', { name: '新建文档' }) as HTMLButtonElement).disabled).toBe(true);
    expect(within(screen.getByRole('tablist', { name: '创作模式' })).getAllByRole('tab')).toHaveLength(1);
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(fetchMock.mock.calls.some(([url]) => url.endsWith('/documents') || url.endsWith('/capabilities') || url.endsWith('/export'))).toBe(false);
    expect(edits()).toHaveLength(0);
  });
  it('saves only after explicit user edit and Save through original expected_version update', async () => {
    render(<CreativeWorkspace {...props(host())} />);
    fireEvent.change(screen.getByLabelText('画面描述'), { target: { value: 'Human edit of exact board' } });
    expect(edits()).toHaveLength(0); click('保存草稿');
    await screen.findByText('已保存“exact-second-board” · v9');
    expect(edits()).toHaveLength(1);
    expect(edits()[0][0]).toContain('/documents/exact-second-board');
    expect(JSON.parse(String(edits()[0][1].body))).toMatchObject({ expected_version: 8, shots: [{ id: 'shot', frame_prompt: 'Human edit of exact board' }] });
  });
  it('uses original dirty return consent and cancellation preserves the draft', () => {
    const p = props(host()); render(<CreativeWorkspace {...p} />);
    fireEvent.change(screen.getByLabelText('文档标题'), { target: { value: 'Keep this' } }); click('返回独立创作图');
    expect(p.onExit).not.toHaveBeenCalled(); click('继续编辑'); expect((screen.getByLabelText('文档标题') as HTMLInputElement).value).toBe('Keep this');
    click('返回独立创作图'); fireEvent.click(screen.getByLabelText('确认放弃未保存草稿并离开')); click('确认离开'); expect(p.onExit).toHaveBeenCalledTimes(1); expect(edits()).toHaveLength(0);
  });
  it('rejects replacement and request ABA while preserving dirty draft', () => {
    const a = host(), p = props(a), view = render(<CreativeWorkspace {...p} />);
    fireEvent.change(screen.getByLabelText('文档标题'), { target: { value: 'Do not replace' } });
    view.rerender(<CreativeWorkspace {...p} storyboardHost={host(board('other'))} />);
    expect((screen.getByLabelText('文档标题') as HTMLInputElement).value).toBe('Do not replace');
    view.rerender(<CreativeWorkspace {...p} storyboardHost={a} />); click('保存草稿'); expect(edits()).toHaveLength(0);
  });
  it('admits a fresh same-ID request when clean and rejects stale receipt metadata', () => {
    const p = props(host()), view = render(<CreativeWorkspace {...p} />);
    const next = host({ ...board(), version: 9, title: 'Fresh inspected same board' });
    view.rerender(<CreativeWorkspace {...p} storyboardHost={next} />);
    expect((screen.getByLabelText('文档标题') as HTMLInputElement).value).toBe('Fresh inspected same board');
    const bad = host(board('malformed'));
    view.rerender(<CreativeWorkspace {...p} storyboardHost={{ ...bad, prepared: { ...bad.prepared, receipt: { ...bad.prepared.receipt, document_digest: 'c'.repeat(64) } } }} />);
    expect((screen.getByLabelText('文档标题') as HTMLInputElement).value).toBe('Fresh inspected same board');
  });
  it('blocks malformed or capability-denied initial receipt without arbitrary fallback', () => {
    const h = host(); render(<CreativeWorkspace {...props({ ...h, prepared: { ...h.prepared, capabilities: { ...caps, can_mutate: false } } })} />);
    expect(screen.queryByLabelText('文档标题')).toBeNull(); expect(fetchMock).not.toHaveBeenCalled(); expect(screen.getByText(/分镜交接.*无效/)).toBeTruthy();
  });
  it('latches synchronous host authority loss across ABA and ignores delayed advisory reads after unmount', async () => {
    let authority = true, resolve!: (value: unknown) => void;
    fetchMock.mockImplementation(() => new Promise(done => { resolve = done; }));
    const p = props({ ...host(), isCurrent: () => authority }); const view = render(<CreativeWorkspace {...p} />);
    authority = false;
    act(() => { useLocalHostSession.setState({ epoch: useLocalHostSession.getState().epoch + 1 }); });
    authority = true; view.rerender(<CreativeWorkspace {...p} />);
    expect(screen.queryByLabelText('文档标题')).toBeNull(); expect(edits()).toHaveLength(0);
    view.unmount(); await act(async () => { resolve(response([])); }); expect(edits()).toHaveLength(0);
  });
  it('preserves blocked target on a new request after an uncertain explicit Save', async () => {
    fetchMock.mockImplementation(async (_url, init) => init.method === 'PUT' ? response({}, 409) : response([]));
    const p = props(host()), view = render(<CreativeWorkspace {...p} />);
    fireEvent.change(screen.getByLabelText('文档标题'), { target: { value: 'Blocked draft' } }); click('保存草稿');
    await screen.findByText('需要核对版本 · 本地草稿仍保留');
    view.rerender(<CreativeWorkspace {...p} storyboardHost={host(board('other'))} />);
    expect((screen.getByLabelText('文档标题') as HTMLInputElement).value).toBe('Blocked draft'); expect(edits()).toHaveLength(1);
  });
});
