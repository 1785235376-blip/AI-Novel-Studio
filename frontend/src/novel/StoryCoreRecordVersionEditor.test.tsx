// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, setCollaborationContext, type CollaborationContext } from '../api';
import { CharacterEditor, LocationEditor, RelationshipEditor, TimelineEditor, ForeshadowingEditor } from './StoryDatabase';

const mock = vi.hoisted(() => ({ get: vi.fn(), put: vi.fn(), post: vi.fn(), features: vi.fn(), client: vi.fn() }));
vi.mock('../experimental/api', () => ({
  enabled: (value: any, key: string) => value.features?.[`experimental.${key}`] === true,
  experimentalFeatures: mock.features,
  experimentalClient: (novelId: string, context: unknown) => { mock.client(novelId, context); return { get: mock.get, put: mock.put, post: mock.post }; },
}));
const kinds = ['characters', 'locations', 'relationships'] as const;
type Kind = typeof kinds[number];
const labels = { characters: '姓名', locations: '地点名称', relationships: '关系描述' };
const saves = { characters: '保存人物', locations: '保存地点', relationships: '保存人物关系' };
const characters = [{ id: 'a', name: 'Alpha' }, { id: 'b', name: 'Beta' }];
const events = [{ id: 'event', title: 'Known source' }];
function row(kind: Kind, text = 'Original', version = 1, id = 'record'): any {
  const record = kind === 'characters' ? { id, name: text, role: 'Author', age: 25, personality: 'Patient', goal: 'Write', current_location: '', status: 'ALIVE' }
    : kind === 'locations' ? { id, name: text, location_type: 'City', description: 'Stored text', rules: 'No noise', atmosphere: 'Quiet', status: 'ACTIVE' }
      : { id, source_character_id: 'a', target_character_id: 'b', relationship_type: 'FRIEND', description: text, status: 'ACTIVE', valid_from_event_id: 'event', valid_to_event_id: '', certainty: 'CONFIRMED' };
  return { record, version, digest: String(version).repeat(64), history: [], source_versions: [], source_state: 'UNLINKED' };
}
let state: any;
function storageKey(kind: Kind | 'timeline' | 'foreshadowing', id: string | null = 'record', context: CollaborationContext = { sessionToken: '' }, novelId = 'n') {
  return `story-record-draft:v2:${JSON.stringify([context.actor?.id || 'local', context.actor?.workspaceId || '', novelId, kind, id, context.scope?.workspaceId || '', context.scope?.projectId || '', context.scope?.storylineId || '', context.scope?.branchId || ''])}`;
}
function scoped(actor = 'actor', branch = 'main'): CollaborationContext {
  return { sessionToken: 'never-persist-token', actor: { id: actor, displayName: actor, workspaceId: 'workspace' }, scope: { workspaceId: 'workspace', projectId: 'project', storylineId: 'story', branchId: branch } };
}
function mount(kind: Kind = 'characters', value: any = { id: 'record' }) {
  const legacy = vi.fn(); const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const invalidated = vi.spyOn(client, 'invalidateQueries');
  const element = (novelId = 'n', v = value, k = kind) => <QueryClientProvider client={client}>{k === 'characters'
    ? <CharacterEditor novelId={novelId} value={v} onSave={legacy}/>
    : k === 'locations' ? <LocationEditor novelId={novelId} value={v} onSave={legacy}/>
      : <RelationshipEditor novelId={novelId} value={v} characters={characters} events={events} onSave={legacy}/>}</QueryClientProvider>;
  return { ...render(element()), legacy, element, invalidated };
}
const field = (kind: Kind) => screen.getByLabelText(labels[kind]) as HTMLInputElement;
const save = (kind: Kind) => screen.getByRole('button', { name: saves[kind] }) as HTMLButtonElement;
function change(kind: Kind, text: string) { fireEvent.change(field(kind), { target: { value: text } }); }
function deferred() { let resolve!: (value: any) => void; let reject!: (reason: any) => void; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; }
beforeEach(() => {
  vi.resetAllMocks(); localStorage.clear(); setCollaborationContext({ sessionToken: '' }); state = row('characters');
  mock.features.mockResolvedValue({ features: { 'experimental.story_record_versions_v1': true } });
  mock.get.mockImplementation((path: string) => Promise.resolve(path.endsWith('/catalog') ? { can_write: true, can_review: true } : state));
  mock.put.mockImplementation(() => Promise.resolve({ ...state, version: state.version + 1 }));
  mock.post.mockImplementation(() => Promise.resolve({ ...state, version: state.version + 1 }));
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

for (const kind of kinds) describe(`${kind} uses its original versioned editor`, () => {
  beforeEach(() => { state = row(kind); });
  it('retains the exact legacy callback only when the flag is OFF', async () => {
    mock.features.mockResolvedValue({ features: {} }); const view = mount(kind, state.record);
    await screen.findByLabelText(labels[kind]); change(kind, 'Legacy'); fireEvent.click(save(kind));
    expect(view.legacy).toHaveBeenCalledOnce(); expect(view.legacy.mock.calls[0][0].id).toBe('record');
    expect(mock.get).not.toHaveBeenCalled(); expect(mock.put).not.toHaveBeenCalled();
  });
  it('sends only supported fields and preserves the selected identity and exact CAS', async () => {
    state.record = { ...state.record, privacy_level: 'LOCAL_ONLY', _story_record: { private: true }, privacy_status: 'INTERNAL', opaque_import: { retained: true } };
    const view = mount(kind); await screen.findByLabelText(labels[kind]); change(kind, 'Edited'); fireEvent.click(save(kind));
    await waitFor(() => expect(mock.put).toHaveBeenCalledOnce());
    const [path, body] = mock.put.mock.calls[0]; expect(path).toBe(`/story-records/${kind}/record`);
    expect(body).toMatchObject({ expected_version: 1, expected_digest: '1'.repeat(64), refresh_sources: false });
    expect(body.record[kind === 'relationships' ? 'description' : 'name']).toBe('Edited');
    expect(body.record.privacy_level).toBe('LOCAL_ONLY');
    for (const key of ['id', '_story_record', 'privacy_status', 'opaque_import']) expect(body.record).not.toHaveProperty(key);
    expect(view.legacy).not.toHaveBeenCalled(); await screen.findByText('已保存版本 2。');
    expect(localStorage.getItem(storageKey(kind))).toBeNull();
  });
  it('does not silently acknowledge an UNKNOWN imported privacy policy', async () => {
    state.record = { ...state.record, privacy_level: 'LOCAL_ONLY', privacy_status: 'UNKNOWN' };
    mount(kind); await screen.findByLabelText(labels[kind]); change(kind, 'Keep private'); fireEvent.click(save(kind));
    await waitFor(() => expect(mock.put).toHaveBeenCalledOnce());
    expect(mock.put.mock.calls[0][1].record).not.toHaveProperty('privacy_level');
    expect(mock.put.mock.calls[0][1].record).not.toHaveProperty('privacy_status');
  });
  it('recovers across restart, shows the full latest record and requires explicit conflict rebase', async () => {
    const view = mount(kind); await screen.findByLabelText(labels[kind]); change(kind, 'Unsent draft'); view.unmount();
    state = row(kind, 'Other writer', 2); mount(kind); await screen.findByRole('button', { name: '恢复本地草稿' });
    expect(field(kind).value).toBe('Other writer'); fireEvent.click(screen.getByRole('button', { name: '恢复本地草稿' }));
    await waitFor(() => expect(field(kind).value).toBe('Unsent draft')); expect(save(kind).disabled).toBe(true);
    expect(screen.getByText('最新服务器记录，版本 2')).toBeTruthy();
    expect(screen.getByText(kind === 'characters' ? '性格：Patient' : kind === 'locations' ? '特殊规则：No noise' : '人物 A：a')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '核对后保留草稿并采用最新基线' })); fireEvent.click(save(kind));
    await waitFor(() => expect(mock.put).toHaveBeenCalledWith(`/story-records/${kind}/record`, expect.objectContaining({ expected_version: 2, expected_digest: '2'.repeat(64) })));
  });
  it('keeps conflict drafts after a 409 and cancel makes no second write', async () => {
    mock.put.mockRejectedValueOnce(new ApiError({ status: 409, code: 'CONFLICT', message: 'Conflict' }));
    mount(kind); await screen.findByLabelText(labels[kind]); change(kind, 'Conflict draft'); fireEvent.click(save(kind));
    await screen.findByRole('alert'); expect(field(kind).value).toBe('Conflict draft'); expect(save(kind).disabled).toBe(true);
    expect(screen.queryByRole('button', { name: '核对后保留草稿并采用最新基线' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '取消编辑' })); expect(field(kind).value).toBe('Original');
    expect(mock.put).toHaveBeenCalledOnce(); expect(localStorage.getItem(storageKey(kind))).toBeNull();
  });
  it.each([401, 403, 404])('fails closed on %s, retains the owner draft and retries through the flag gate', async status => {
    mock.put.mockRejectedValueOnce(new ApiError({ status, code: 'DENIED', message: 'Denied' }));
    const view = mount(kind); await screen.findByLabelText(labels[kind]); change(kind, 'Retained after denial'); fireEvent.click(save(kind));
    await screen.findByRole('alert'); expect(screen.queryByLabelText(labels[kind])).toBeNull();
    expect(screen.queryByText('版本历史与人工反馈（最多 20 版）')).toBeNull();
    expect(localStorage.getItem(storageKey(kind))).toContain('Retained after denial');
    fireEvent.click(screen.getByRole('button', { name: '重试读取资料版本' })); await screen.findByLabelText(labels[kind]);
    expect(field(kind).value).toBe('Retained after denial'); expect(mock.features).toHaveBeenCalledTimes(2);
    expect(mock.put).toHaveBeenCalledOnce(); expect(view.legacy).not.toHaveBeenCalled();
  });
  it('previews structured history and only confirmed restore creates a new version', async () => {
    state.history = [{ version: 0, record: row(kind, 'Earlier').record, action: 'LEGACY' }];
    mount(kind); await screen.findByLabelText(labels[kind]); fireEvent.click(screen.getByText('版本历史与人工反馈（最多 20 版）'));
    fireEvent.click(screen.getByRole('button', { name: '预览恢复 v0' })); expect(screen.getByRole('region', { name: '恢复版本确认' }).textContent).toContain(kind === 'characters' ? '性格：Patient' : kind === 'locations' ? '特殊规则：No noise' : '人物 A：a');
    fireEvent.click(screen.getByRole('button', { name: '取消恢复' })); expect(mock.post).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '预览恢复 v0' })); fireEvent.click(screen.getByRole('button', { name: '确认恢复为新版本' }));
    await waitFor(() => expect(mock.post).toHaveBeenCalledWith(`/story-records/${kind}/record/restore`, { expected_version: 1, expected_digest: state.digest, restore_version: 0, confirmed: true }));
  });
  it('disables write, restore and feedback when refreshed permissions are read-only', async () => {
    state.history = [{ version: 0, record: state.record, action: 'LEGACY' }]; mount(kind); await screen.findByLabelText(labels[kind]);
    mock.get.mockImplementation((path: string) => Promise.resolve(path.endsWith('/catalog') ? { can_write: false, can_review: false } : state));
    fireEvent.click(screen.getByRole('button', { name: '读取最新版本' })); await screen.findByText(/只读身份/);
    expect(save(kind).disabled).toBe(true); fireEvent.click(screen.getByText('版本历史与人工反馈（最多 20 版）'));
    expect((screen.getByRole('button', { name: '预览恢复 v0' }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole('button', { name: '提交此版本人工反馈' }) as HTMLButtonElement).disabled).toBe(true);
    expect(mock.put).not.toHaveBeenCalled(); expect(mock.post).not.toHaveBeenCalled();
  });
  it('recovers a never-saved new record at create CAS without requiring an existing owner', async () => {
    localStorage.setItem(storageKey(kind, null), JSON.stringify({ record: { ...state.record, id: '' }, version: 0, digest: null }));
    mount(kind, {}); await screen.findByRole('button', { name: '恢复本地草稿' }); fireEvent.click(screen.getByRole('button', { name: '恢复本地草稿' }));
    await waitFor(() => expect(save(kind).disabled).toBe(false)); fireEvent.click(save(kind));
    await waitFor(() => expect(mock.put).toHaveBeenCalledWith(`/story-records/${kind}/${kind === 'relationships' ? 'a-b' : 'Original'}`, expect.objectContaining({ expected_version: 0, expected_digest: null })));
    expect(mock.get.mock.calls.filter(call => !call[0].endsWith('/catalog'))).toHaveLength(0);
  });
  it('preserves dirty local edits when feedback advances the metadata version', async () => {
    mount(kind); await screen.findByLabelText(labels[kind]); change(kind, 'Unsubmitted edits');
    fireEvent.click(screen.getByText('版本历史与人工反馈（最多 20 版）'));
    fireEvent.change(screen.getByLabelText('反馈依据'), { target: { value: 'Known source' } });
    fireEvent.click(screen.getByRole('button', { name: '提交此版本人工反馈' })); await screen.findByText('已保存版本 2。');
    expect(field(kind).value).toBe('Unsubmitted edits'); expect(JSON.parse(localStorage.getItem(storageKey(kind))!)).toMatchObject({ version: 2 });
    expect(mock.put).not.toHaveBeenCalled();
  });
});

describe('core Story owner and draft isolation', () => {
  it('preserves an explicitly cleared age through recovery and sends null to the merge owner', async () => {
    const view = mount(); await screen.findByLabelText('年龄');
    fireEvent.change(screen.getByLabelText('年龄'), { target: { value: '' } }); view.unmount();
    mount(); await screen.findByRole('button', { name: '恢复本地草稿' }); fireEvent.click(screen.getByRole('button', { name: '恢复本地草稿' }));
    expect((screen.getByLabelText('年龄') as HTMLInputElement).value).toBe(''); fireEvent.click(save('characters'));
    await waitFor(() => expect(mock.put).toHaveBeenCalledWith('/story-records/characters/record', expect.objectContaining({ record: expect.objectContaining({ age: null }) })));
  });
  it('requires a fresh explicit source acknowledgment after reading a newer source state', async () => {
    state.source_state = 'STALE'; mount(); await screen.findByLabelText('姓名');
    const checkbox = screen.getByRole('checkbox') as HTMLInputElement; fireEvent.click(checkbox); expect(checkbox.checked).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: '读取最新版本' })); await waitFor(() => expect(checkbox.checked).toBe(false));
    expect(mock.put).not.toHaveBeenCalled(); fireEvent.click(checkbox); fireEvent.click(save('characters'));
    await waitFor(() => expect(mock.put).toHaveBeenCalledWith('/story-records/characters/record', expect.objectContaining({ refresh_sources: true })));
  });

  it.each(['actor', 'workspace', 'project', 'storyline', 'branch', 'novel', 'record', 'session'] as const)('ignores late writes after %s navigation and never removes the origin draft', async axis => {
    const originalContext = scoped(); setCollaborationContext(originalContext); const pending = deferred(); mock.put.mockReturnValue(pending.promise);
    const view = mount(); await screen.findByLabelText('姓名'); change('characters', 'Origin draft'); const button = save('characters'); fireEvent.click(button); fireEvent.click(button);
    expect(mock.put).toHaveBeenCalledOnce();
    const next = { ...originalContext, actor: { ...originalContext.actor! }, scope: { ...originalContext.scope! } };
    if (axis === 'actor') next.actor.id = 'other'; if (axis === 'session') next.sessionToken = 'other-token';
    if (axis === 'workspace') next.scope.workspaceId = 'other'; if (axis === 'project') next.scope.projectId = 'other';
    if (axis === 'storyline') next.scope.storylineId = 'other'; if (axis === 'branch') next.scope.branchId = 'other';
    setCollaborationContext(next); state = row('characters', 'New owner', 3, axis === 'record' ? 'other' : 'record');
    view.rerender(view.element(axis === 'novel' ? 'other' : 'n', { id: state.record.id })); await screen.findByLabelText('姓名');
    await act(async () => pending.resolve(row('characters', 'Late origin', 2)));
    expect(field('characters').value).toBe('New owner'); expect(view.invalidated).not.toHaveBeenCalled();
    expect(localStorage.getItem(storageKey('characters', 'record', originalContext))).toContain('Origin draft');
    expect(Array.from({ length: localStorage.length }, (_, i) => localStorage.key(i)).join()).not.toContain('never-persist-token');
  });
  it('never starts the old record read after its delayed catalog completes following a scope switch', async () => {
    const context = scoped(); setCollaborationContext(context); const pending = deferred(); mock.get.mockImplementationOnce(() => pending.promise);
    const view = mount(); await waitFor(() => expect(mock.get).toHaveBeenCalledOnce());
    const signal = mock.get.mock.calls[0][1] as AbortSignal;
    setCollaborationContext(scoped('other')); state = row('characters', 'New actor'); view.rerender(view.element());
    await screen.findByLabelText('姓名'); await act(async () => pending.resolve({ can_write: true, can_review: true }));
    expect(signal.aborted).toBe(true); expect(mock.get.mock.calls.filter(call => call[0] === '/story-records/characters/record')).toHaveLength(1);
    expect(field('characters').value).toBe('New actor');
  });
  it('ignores an old permission rejection after a new record is already visible', async () => {
    const pending = deferred(); mock.put.mockReturnValue(pending.promise); const view = mount(); await screen.findByLabelText('姓名'); fireEvent.click(save('characters'));
    state = row('characters', 'New record', 1, 'next'); view.rerender(view.element('n', { id: 'next' })); await screen.findByLabelText('姓名');
    await act(async () => pending.reject(new ApiError({ status: 403, code: 'DENIED', message: 'Denied' })));
    expect(field('characters').value).toBe('New record'); expect(screen.queryByRole('alert')).toBeNull();
  });
  it('does not recover a different branch, actor, or old unscoped namespace', async () => {
    const context = scoped(); setCollaborationContext(context); const view = mount(); await screen.findByLabelText('姓名'); change('characters', 'Private origin draft'); view.unmount();
    localStorage.setItem('story-record-draft:actor:n:characters:record', JSON.stringify({ record: row('characters', 'Unsafe old key').record, version: 1, digest: state.digest }));
    setCollaborationContext(scoped('actor', 'other')); const branch = mount(); await screen.findByLabelText('姓名'); expect(screen.queryByRole('button', { name: '恢复本地草稿' })).toBeNull(); branch.unmount();
    setCollaborationContext(scoped('other')); const actor = mount(); await screen.findByLabelText('姓名'); expect(screen.queryByRole('button', { name: '恢复本地草稿' })).toBeNull(); actor.unmount();
    setCollaborationContext(context); mount(); await screen.findByRole('button', { name: '恢复本地草稿' });
  });
  it.each([{ id: 'another', name: 'Wrong record' }, { id: 'record', name: null }, { id: 'record', name: ['broken'] }])('ignores malformed and wrong-record recovery %#', async record => {
    localStorage.setItem(storageKey('characters'), JSON.stringify({ record, digest: state.digest, version: 1 })); mount(); await screen.findByLabelText('姓名');
    expect(screen.queryByRole('button', { name: '恢复本地草稿' })).toBeNull(); expect(field('characters').value).toBe('Original');
  });
  it('fails closed on initial flag errors and retry cannot bypass an OFF flag', async () => {
    mock.features.mockRejectedValueOnce(new Error('Offline')); const view = mount(); await screen.findByRole('alert');
    mock.features.mockResolvedValue({ features: {} }); fireEvent.click(screen.getByRole('button', { name: '重试读取资料版本' }));
    await screen.findByText('功能已关闭或原记录不可读。'); expect(screen.queryByLabelText('姓名')).toBeNull();
    expect(mock.get.mock.calls.filter(call => !call[0].endsWith('/catalog'))).toHaveLength(0); expect(view.legacy).not.toHaveBeenCalled();
  });
  it('recovers an existing saved identity left in the new-record editor only after fresh authorization', async () => {
    localStorage.setItem(storageKey('characters', null), JSON.stringify({ record: row('characters', 'New form edits').record, digest: '1'.repeat(64), version: 1 }));
    state = row('characters', 'Latest server', 2); mount('characters', {}); await screen.findByRole('button', { name: '恢复本地草稿' });
    fireEvent.click(screen.getByRole('button', { name: '恢复本地草稿' })); await screen.findByText('最新服务器记录，版本 2');
    expect(field('characters').value).toBe('New form edits'); expect(save('characters').disabled).toBe(true);
    expect(mock.get).toHaveBeenCalledWith('/story-records/characters/record');
  });
  it('separates a real record named new from the unsaved new-record draft namespace', async () => {
    localStorage.setItem(storageKey('characters', null), JSON.stringify({ record: row('characters', 'Unsaved new draft').record, digest: null, version: 0 }));
    state = row('characters', 'Actual new ID', 1, 'new'); mount('characters', { id: 'new' }); await screen.findByLabelText('姓名');
    expect(field('characters').value).toBe('Actual new ID'); expect(screen.queryByRole('button', { name: '恢复本地草稿' })).toBeNull();
    change('characters', 'Existing record draft'); expect(localStorage.getItem(storageKey('characters', 'new'))).toContain('Existing record draft');
    expect(localStorage.getItem(storageKey('characters', null))).toContain('Unsaved new draft');
  });
  it.each(['timeline', 'foreshadowing'] as const)('separates literal new IDs in %s while retaining the original unsaved recovery key', async kind => {
    const legacyKey = `story-record-draft:local:n:${kind}:new`;
    localStorage.setItem(legacyKey, JSON.stringify({ record: { title: 'Legacy unsaved draft' }, digest: null, version: 0 }));
    state = { ...row('characters'), record: { id: 'new', title: 'Actual new ID' } };
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const Editor = kind === 'timeline' ? TimelineEditor : ForeshadowingEditor;
    const element = (value: { id?: string }) => <QueryClientProvider client={client}><Editor novelId="n" value={value} onSave={vi.fn()}/></QueryClientProvider>;
    const view = render(element({ id: 'new' })); const label = kind === 'timeline' ? '事件标题' : '伏笔标题';
    await screen.findByLabelText(label); expect((screen.getByLabelText(label) as HTMLInputElement).value).toBe('Actual new ID');
    expect(screen.queryByRole('button', { name: '恢复本地草稿' })).toBeNull();
    fireEvent.change(screen.getByLabelText(label), { target: { value: 'Existing literal ID draft' } });
    expect(localStorage.getItem(storageKey(kind, 'new'))).toContain('Existing literal ID draft');
    expect(localStorage.getItem(legacyKey)).toContain('Legacy unsaved draft');
    view.rerender(element({})); await screen.findByRole('button', { name: '恢复本地草稿' });
    fireEvent.click(screen.getByRole('button', { name: '恢复本地草稿' }));
    expect((screen.getByLabelText(label) as HTMLInputElement).value).toBe('Legacy unsaved draft');
    expect(mock.put).not.toHaveBeenCalled();
  });
  it('never persists drafts for an unverified session identity', async () => {
    setCollaborationContext({ sessionToken: 'unknown-session' }); mount(); await screen.findByLabelText('姓名'); change('characters', 'Memory only');
    expect(screen.getByText(/当前会话尚未确认作者身份/)).toBeTruthy(); expect(localStorage.length).toBe(0);
  });
  it('keeps a memory-only draft when browser storage denies writes', async () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('Denied'); });
    mount(); await screen.findByLabelText('姓名'); change('characters', 'Memory only'); expect(field('characters').value).toBe('Memory only');
    expect(screen.getByText(/本地草稿无法持久保存/)).toBeTruthy(); expect(mock.put).not.toHaveBeenCalled();
  });
});
