// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, setCollaborationContext } from '../api';
import { TimelineEditor, ForeshadowingEditor } from './StoryDatabase';

const mock = vi.hoisted(() => ({ get: vi.fn(), put: vi.fn(), post: vi.fn(), features: vi.fn() }));
vi.mock('../experimental/api', () => ({
  enabled: (value: any, key: string) => value.features?.[`experimental.${key}`] === true,
  experimentalFeatures: mock.features,
  experimentalClient: () => ({ get: mock.get, put: mock.put, post: mock.post }),
}));
const row = (title = 'Original', version = 1, digest = 'a'.repeat(64)) => ({ record: { id: 'event', title, description: 'Stored text', sequence: 1, time: '', location: '', characters: [], chapter_id: '', status: 'PLANNED' }, version, digest, history: [] as any[], source_versions: [], source_state: 'UNLINKED' });
let state: any = row();
function mount(value: any = { id: 'event', title: 'Old list title' }, kind = 'timeline', onOpenChapter = vi.fn()) {
  const legacy = vi.fn();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const element = (novelId = 'n', v = value) => <QueryClientProvider client={client}>{kind === 'timeline' ? <TimelineEditor novelId={novelId} onOpenChapter={onOpenChapter} value={v} onSave={legacy} /> : <ForeshadowingEditor novelId={novelId} onOpenChapter={onOpenChapter} value={v} onSave={legacy} />}</QueryClientProvider>;
  return { ...render(element()), legacy, element };
}
beforeEach(() => {
  vi.clearAllMocks(); localStorage.clear(); setCollaborationContext({ sessionToken: '' }); state = row();
  mock.features.mockResolvedValue({ features: { 'experimental.story_record_versions_v1': true } });
  mock.get.mockImplementation((path: string) => Promise.resolve(path.endsWith('catalog') ? { can_write: true, can_review: true } : state));
  mock.put.mockResolvedValue(row('Changed', 2, 'b'.repeat(64)));
});
afterEach(cleanup);

describe('existing Story editor version surface', () => {
  it('preserves legacy callback only when server flag is explicitly OFF', async () => {
    mock.features.mockResolvedValue({ features: {} }); const e = mount();
    await screen.findByLabelText('事件标题'); fireEvent.change(screen.getByLabelText('事件标题'), { target: { value: 'Legacy' } });
    fireEvent.click(screen.getByRole('button', { name: '保存时间线事件' }));
    expect(e.legacy).toHaveBeenCalledOnce(); expect(mock.put).not.toHaveBeenCalled(); expect(mock.get).not.toHaveBeenCalled();
  });
  it('sends original digest/version, preserves conflict draft and requires explicit latest baseline', async () => {
    mock.put.mockRejectedValueOnce(new ApiError({ status: 409, code: 'STORY_RECORD_CONFLICT', message: 'conflict' }));
    const e = mount(); await screen.findByLabelText('事件标题');
    fireEvent.change(screen.getByLabelText('事件标题'), { target: { value: 'Changed' } });
    fireEvent.click(screen.getByRole('button', { name: '保存时间线事件' }));
    await screen.findByRole('alert');
    expect(screen.queryByRole('button', { name: '核对后保留草稿并采用最新基线' })).toBeNull();
    expect(mock.put).toHaveBeenCalledWith('/story-records/timeline/event', expect.objectContaining({ expected_digest: 'a'.repeat(64), expected_version: 1, record: expect.objectContaining({ title: 'Changed' }) }));
    expect((screen.getByLabelText('事件标题') as HTMLInputElement).value).toBe('Changed');
    expect((screen.getByRole('button', { name: '保存时间线事件' }) as HTMLButtonElement).disabled).toBe(true);
    state = row('Other writer', 2, 'b'.repeat(64)); fireEvent.click(screen.getByRole('button', { name: '读取最新版本' }));
    await screen.findByText('Other writer');
    fireEvent.click(screen.getByRole('button', { name: '核对后保留草稿并采用最新基线' }));
    fireEvent.click(screen.getByRole('button', { name: '保存时间线事件' }));
    await waitFor(() => expect(mock.put).toHaveBeenCalledTimes(2));
    expect(mock.put.mock.calls[1][1]).toMatchObject({ expected_digest: 'b'.repeat(64), expected_version: 2 }); expect(e.legacy).not.toHaveBeenCalled();
  });
  it('keeps draft across unmount/restart, resumes explicitly and cancel never writes', async () => {
    const e = mount(); await screen.findByLabelText('事件标题');
    fireEvent.change(screen.getByLabelText('事件标题'), { target: { value: 'Unsaved recovery' } }); e.unmount();
    mount(); await screen.findByRole('button', { name: '恢复本地草稿' });
    expect((screen.getByLabelText('事件标题') as HTMLInputElement).value).toBe('Original');
    fireEvent.click(screen.getByRole('button', { name: '恢复本地草稿' }));
    expect((screen.getByLabelText('事件标题') as HTMLInputElement).value).toBe('Unsaved recovery');
    fireEvent.click(screen.getByRole('button', { name: '取消编辑' }));
    expect((screen.getByLabelText('事件标题') as HTMLInputElement).value).toBe('Original');
    expect(mock.put).not.toHaveBeenCalled(); expect(localStorage.length).toBe(0);
  });
  it('previews and cancels restoration; approved restore uses current CAS', async () => {
    state = { ...row(), history: [{ version: 0, record: { title: 'Past', description: 'Earlier' }, action: 'LEGACY' }] };
    mock.post.mockResolvedValue(row('Past', 2)); mount(); await screen.findByLabelText('事件标题');
    fireEvent.click(screen.getByText('版本历史与人工反馈（最多 20 版）'));
    fireEvent.click(screen.getByRole('button', { name: '预览恢复 v0' }));
    fireEvent.click(screen.getByRole('button', { name: '取消恢复' })); expect(mock.post).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '预览恢复 v0' })); fireEvent.click(screen.getByRole('button', { name: '确认恢复为新版本' }));
    await waitFor(() => expect(mock.post).toHaveBeenCalledWith('/story-records/timeline/event/restore', { expected_digest: state.digest, expected_version: 1, restore_version: 0, confirmed: true }));
  });
  it('hides unauthorized history, never falls back to an unguarded write', async () => {
    mock.get.mockRejectedValue(new ApiError({ status: 403, code: 'FORBIDDEN', message: 'Denied' })); const e = mount();
    await screen.findByRole('alert'); expect(screen.queryByLabelText('事件标题')).toBeNull(); expect(e.legacy).not.toHaveBeenCalled();
  });
  it('suppresses late response after newer project navigation', async () => {
    let finish!: (value: any) => void; mock.put.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
    const e = mount(); await screen.findByLabelText('事件标题'); fireEvent.change(screen.getByLabelText('事件标题'), { target: { value: 'First project draft' } });
    fireEvent.click(screen.getByRole('button', { name: '保存时间线事件' }));
    e.rerender(e.element('other', { id: 'another', title: 'Other' })); state = { ...row('Other project'), record: { ...row('Other project').record, id: 'another' } };
    await screen.findByLabelText('事件标题'); await act(async () => finish(row('Late first project')));
    expect((screen.getByLabelText('事件标题') as HTMLInputElement).value).not.toBe('Late first project'); expect(e.legacy).not.toHaveBeenCalled();
  });
  it('uses the same owner for Foreshadowing and blocks duplicate save clicks', async () => {
    let finish!: (value: any) => void; mock.put.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
    mount({ id: 'event' }, 'foreshadowing'); await screen.findByLabelText('伏笔标题');
    fireEvent.change(screen.getByLabelText('伏笔标题'), { target: { value: 'Foreshadow' } });
    const button = screen.getByRole('button', { name: '保存伏笔' }); fireEvent.click(button); fireEvent.click(button);
    expect(mock.put).toHaveBeenCalledTimes(1); expect(mock.put.mock.calls[0][0]).toBe('/story-records/foreshadowing/event');
    await act(async () => finish(row('Foreshadow', 2)));
  });
  it('navigates the persisted A43 source identity through the existing guard and blocks stale sources', async () => {
    const open = vi.fn(); state = { ...row(), source_versions: [{ kind: 'chapter', id: 'n:~stable-source', version: 3 }], source_state: 'CURRENT' };
    mount(undefined, 'timeline', open); await screen.findByLabelText('事件标题');
    fireEvent.change(screen.getByLabelText('事件标题'), { target: { value: 'Keep this draft' } });
    fireEvent.click(screen.getByRole('button', { name: '打开来源章节 n:~stable-source' }));
    expect(open).toHaveBeenCalledWith('n:~stable-source', expect.any(AbortSignal)); expect(localStorage.getItem('story-record-draft:local:n:timeline:event')).toContain('Keep this draft');
    state = { ...state, source_state: 'STALE', stale_sources: ['n:~stable-source'] };
    fireEvent.click(screen.getByRole('button', { name: '读取最新版本' }));
    await screen.findByText(/来源已改变或不可用/);
    expect((screen.getByRole('button', { name: '打开来源章节 n:~stable-source' }) as HTMLButtonElement).disabled).toBe(true);
  });
  it('recovers an unsent new record without requiring a nonexistent server baseline', async () => {
    localStorage.setItem('story-record-draft:local:n:timeline:new', JSON.stringify({ record: { title: 'New recovery' }, digest: null, version: 0 }));
    mount({}); await screen.findByRole('button', { name: '恢复本地草稿' });
    fireEvent.click(screen.getByRole('button', { name: '恢复本地草稿' }));
    expect((screen.getByRole('button', { name: '保存时间线事件' }) as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: '保存时间线事件' }));
    await waitFor(() => expect(mock.put).toHaveBeenCalledWith('/story-records/timeline/New%20recovery', expect.objectContaining({ expected_digest: null, expected_version: 0 })));
  });

  it('retains an unsent draft through permission revocation and authorized retry', async () => {
    const denied = new ApiError({ status: 403, code: 'FORBIDDEN', message: 'Denied' });
    mock.put.mockRejectedValueOnce(denied); mount(); await screen.findByLabelText('事件标题');
    fireEvent.change(screen.getByLabelText('事件标题'), { target: { value: 'Retain after revoke' } });
    fireEvent.click(screen.getByRole('button', { name: '保存时间线事件' })); await screen.findByRole('alert');
    expect(screen.queryByLabelText('事件标题')).toBeNull();
    expect(localStorage.getItem('story-record-draft:local:n:timeline:event')).toContain('Retain after revoke');
    fireEvent.click(screen.getByRole('button', { name: '重试读取资料版本' }));
    await screen.findByLabelText('事件标题');
    expect((screen.getByLabelText('事件标题') as HTMLInputElement).value).toBe('Retain after revoke');
    expect(localStorage.getItem('story-record-draft:local:n:timeline:event')).toContain('Retain after revoke');
    expect(mock.put).toHaveBeenCalledOnce();
  });
  it('keeps read-only recovery visible but disables every mutation after refreshed grants', async () => {
    mount(); await screen.findByLabelText('事件标题');
    mock.get.mockImplementation((path: string) => Promise.resolve(path.endsWith('catalog') ? { can_write: false, can_review: false } : state));
    fireEvent.click(screen.getByRole('button', { name: '读取最新版本' })); await screen.findByText(/只读身份/);
    expect((screen.getByRole('button', { name: '保存时间线事件' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByText('版本历史与人工反馈（最多 20 版）'));
    expect((screen.getByRole('button', { name: '提交此版本人工反馈' }) as HTMLButtonElement).disabled).toBe(true);
    expect(mock.put).not.toHaveBeenCalled(); expect(mock.post).not.toHaveBeenCalled();
  });
  it('records author evidence and prevents another terminal decision for that version', async () => {
    mock.post.mockResolvedValue({ ...state, version: 2, feedback: { decision: 'INTENTIONAL', note: 'Deliberate', evidence: 'Scene 4' }, feedback_stale: false });
    mount(); await screen.findByLabelText('事件标题'); fireEvent.click(screen.getByText('版本历史与人工反馈（最多 20 版）'));
    fireEvent.change(screen.getByLabelText('反馈决定'), { target: { value: 'INTENTIONAL' } });
    fireEvent.change(screen.getByLabelText('反馈说明'), { target: { value: 'Deliberate' } });
    fireEvent.change(screen.getByLabelText('反馈依据'), { target: { value: 'Scene 4' } });
    fireEvent.click(screen.getByRole('button', { name: '提交此版本人工反馈' }));
    await waitFor(() => expect(mock.post).toHaveBeenCalledWith('/story-records/timeline/event/feedback', expect.objectContaining({ decision: 'INTENTIONAL', note: 'Deliberate', evidence: 'Scene 4', expected_version: 1 })));
    await waitFor(() => expect((screen.getByRole('button', { name: '提交此版本人工反馈' }) as HTMLButtonElement).disabled).toBe(true));
  });
  it('cancels exact source navigation on cancel and unmount', async () => {
    const open = vi.fn(); state = { ...row(), source_versions: [{ kind: 'chapter', id: 'stable', version: 1 }] };
    const view = mount(undefined, 'timeline', open); await screen.findByLabelText('事件标题');
    fireEvent.click(screen.getByRole('button', { name: '打开来源章节 stable' }));
    const first = open.mock.calls[0][1] as AbortSignal; expect(first.aborted).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: '取消编辑' })); expect(first.aborted).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: '打开来源章节 stable' })); const second = open.mock.calls[1][1] as AbortSignal;
    view.unmount(); expect(second.aborted).toBe(true); expect(mock.put).not.toHaveBeenCalled();
  });
  it('fails closed on flag discovery errors and ignores delayed read after identity changes', async () => {
    mock.features.mockRejectedValueOnce(new Error('Offline')); const e = mount(); await screen.findByRole('alert');
    expect(e.legacy).not.toHaveBeenCalled(); expect(screen.queryByLabelText('事件标题')).toBeNull();
    let finish!: (value: any) => void; mock.get.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
    fireEvent.click(screen.getByRole('button', { name: '重试读取资料版本' }));
    e.rerender(e.element('other', { id: 'other-record', title: 'Other' }));
    await screen.findByLabelText('事件标题'); await act(async () => finish({ can_write: true, can_review: true }));
    expect(mock.put).not.toHaveBeenCalled(); expect(e.legacy).not.toHaveBeenCalled();
  });

});
