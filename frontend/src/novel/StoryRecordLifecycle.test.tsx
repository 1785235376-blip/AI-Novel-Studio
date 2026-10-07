// @vitest-environment jsdom
import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { setCollaborationContext } from '../api';
import { CharacterEditor, LocationEditor, RelationshipEditor, TimelineEditor, ForeshadowingEditor } from './StoryDatabase';

const mock = vi.hoisted(() => ({ get: vi.fn(), put: vi.fn(), post: vi.fn(), features: vi.fn() }));
vi.mock('../experimental/api', () => ({
  enabled: (value: any, key: string) => value.features?.[`experimental.${key}`] === true,
  experimentalFeatures: mock.features,
  experimentalClient: () => ({ get: mock.get, put: mock.put, post: mock.post }),
}));
const kinds = ['characters', 'locations', 'relationships', 'timeline', 'foreshadowing'] as const;
type Kind = typeof kinds[number];
const labels = { characters: '姓名', locations: '地点名称', relationships: '关系描述', timeline: '事件标题', foreshadowing: '伏笔标题' };
const saves = { characters: '保存人物', locations: '保存地点', relationships: '保存人物关系', timeline: '保存时间线事件', foreshadowing: '保存伏笔' };
const editors = { characters: CharacterEditor, locations: LocationEditor, relationships: RelationshipEditor, timeline: TimelineEditor, foreshadowing: ForeshadowingEditor };
function snapshot(kind: Kind, version = 1) {
  const record = kind === 'characters' ? { id: 'record', name: 'Original', age: 25, goal: 'Write', status: 'ALIVE' }
    : kind === 'locations' ? { id: 'record', name: 'Original', description: 'Description', status: 'ACTIVE' }
      : kind === 'relationships' ? { id: 'record', source_character_id: 'a', target_character_id: 'b', relationship_type: 'FRIEND', description: 'Original', status: 'ACTIVE' }
        : { id: 'record', title: 'Original', description: 'Description', sequence: 1, characters: [], events: [], status: kind === 'timeline' ? 'CONFIRMED' : 'OPEN' };
  return { record, version, digest: String(version).repeat(64), history: [{ version: 0, record, action: 'LEGACY' }], source_versions: [], source_state: 'UNLINKED' };
}
let state: any;
function deferred() { let resolve!: (value?: any) => void; const promise = new Promise<any>(yes => { resolve = yes; }); return { promise, resolve }; }
function mount(kind: Kind, client = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  const Editor = editors[kind];
  return render(<StrictMode><QueryClientProvider client={client}><Editor novelId="n" value={{ id: 'record' }} onSave={vi.fn()}/></QueryClientProvider></StrictMode>);
}
beforeEach(() => {
  vi.resetAllMocks(); localStorage.clear(); setCollaborationContext({ sessionToken: '' });
  mock.features.mockResolvedValue({ features: { 'experimental.story_record_versions_v1': true } });
  mock.get.mockImplementation((path: string) => Promise.resolve(path.endsWith('/catalog') ? { can_write: true, can_review: true } : state));
});
afterEach(cleanup);

for (const kind of kinds) describe(`${kind} commit and restart lifecycle`, () => {
  beforeEach(() => { state = snapshot(kind); });
  it.each(['SAVE', 'RESTORE', 'FEEDBACK'] as const)('disables real fields throughout %s and cache settlement, then persists an immediate edit before restart', async action => {
    const network = deferred(), refresh = deferred();
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const invalidate = vi.spyOn(client, 'invalidateQueries').mockReturnValue(refresh.promise);
    mock.put.mockReturnValue(network.promise); mock.post.mockReturnValue(network.promise);
    const view = mount(kind, client); const field = await screen.findByLabelText(labels[kind]);
    const saveButton = screen.getByRole('button', { name: saves[kind] }) as HTMLButtonElement;
    if (action === 'SAVE') fireEvent.click(screen.getByRole('button', { name: saves[kind] }));
    else {
      fireEvent.click(screen.getByText('版本历史与人工反馈（最多 20 版）'));
      if (action === 'RESTORE') {
        fireEvent.click(screen.getByRole('button', { name: '预览恢复 v0' }));
        fireEvent.click(screen.getByRole('button', { name: '确认恢复为新版本' }));
      } else {
        fireEvent.change(screen.getByLabelText('反馈决定'), { target: { value: 'INTENTIONAL' } });
        fireEvent.click(screen.getByRole('button', { name: '提交此版本人工反馈' }));
      }
    }
    expect((field as HTMLInputElement).disabled).toBe(true);
    if (action === 'FEEDBACK') {
      for (const label of ['反馈决定', '反馈说明', '反馈依据']) expect((screen.getByLabelText(label) as HTMLInputElement).disabled).toBe(true);
    }
    const committed = snapshot(kind, 2);
    await act(async () => network.resolve(committed));
    expect(invalidate).toHaveBeenCalledOnce();
    expect((field as HTMLInputElement).disabled).toBe(true);
    expect(saveButton.disabled).toBe(true);
    await act(async () => refresh.resolve());
    await waitFor(() => expect((field as HTMLInputElement).disabled).toBe(false));
    fireEvent.change(field, { target: { value: 'Immediate post-commit draft' } });
    expect(Object.keys(localStorage).some(key => localStorage.getItem(key)?.includes('Immediate post-commit draft'))).toBe(true);
    view.unmount(); state = committed; mount(kind);
    await screen.findByRole('button', { name: '恢复本地草稿' });
    fireEvent.click(screen.getByRole('button', { name: '恢复本地草稿' }));
    expect((screen.getByLabelText(labels[kind]) as HTMLInputElement).value).toBe('Immediate post-commit draft');
    fireEvent.click(screen.getByRole('button', { name: '取消编辑' }));
    expect((screen.getByLabelText(labels[kind]) as HTMLInputElement).value).toBe('Original');
    expect(mock.put).toHaveBeenCalledTimes(action === 'SAVE' ? 1 : 0);
    expect(mock.post).toHaveBeenCalledTimes(action === 'SAVE' ? 0 : 1);
  });
});

for (const kind of kinds) it(`${kind} controls have stable explicit labels independent of existing text and select options`, async () => {
  state = snapshot(kind); const view = mount(kind); await screen.findByLabelText(labels[kind]);
  const fields = view.container.querySelectorAll('.novel-draft-review input, .novel-draft-review textarea, .novel-draft-review select');
  expect(fields.length).toBeGreaterThan(2);
  for (const field of fields) {
    const visibleLabel = field.closest('label')?.firstChild?.textContent;
    expect(field.getAttribute('aria-label')).toBe(visibleLabel);
    expect((field as HTMLInputElement).disabled).toBe(false);
  }
  fireEvent.click(screen.getByText('版本历史与人工反馈（最多 20 版）'));
  for (const label of ['反馈决定', '反馈说明', '反馈依据']) expect(screen.getByLabelText(label).getAttribute('aria-label')).toBe(label);
  const decision = screen.getByLabelText('反馈决定');
  // Browser getByLabel also sees option text in an implicit enclosing label.
  // The explicit name remains exact for both browsers and assistive technology.
  expect(decision.closest('label')?.textContent).toContain('已核对');
  fireEvent.change(decision, { target: { value: 'INTENTIONAL' } });
  expect((screen.getByLabelText('反馈决定') as HTMLSelectElement).value).toBe('INTENTIONAL');
});
