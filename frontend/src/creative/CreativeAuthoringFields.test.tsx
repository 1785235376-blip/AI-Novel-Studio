// @vitest-environment jsdom
import { useState } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { CreativeCanvas } from './CreativeCanvas';
import { CreativeWorkspace, type CreativeWorkspaceProps } from './CreativeWorkspace';
import { documentInput, newDocument, newScene, newShot, type CreativeDocument, type CreativeInput } from './types';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const target = () => ({ style: '写实', atmosphere: '安静', reference_works: ['参考甲'], color: '蓝', rhythm: '慢' });
function initial(): CreativeInput {
  return { ...newDocument('STORYBOARD'), title: 'Authored continuity', source_independent: true,
    visual_target: target(), scenes: [{ ...newScene(1), id: 'scene', time: '场景原始时间' }],
    shots: [{ ...newShot(1, 'scene'), id: 'shot-1', lighting: '暖光' }, { ...newShot(2, 'scene'), id: 'shot-2' }] };
}
function Harness({ value: original = initial(), changed = vi.fn(), busy = false, editable = true, selected = 'shot-1' }: {
  value?: CreativeInput; changed?: (value: CreativeInput) => void; busy?: boolean; editable?: boolean; selected?: string;
}) {
  const [value, setValue] = useState(original);
  return <CreativeCanvas draft={value} dirty={true} busy={busy} canEdit={editable} selectedShotId={selected}
    onShot={vi.fn()} onScene={vi.fn()} onChange={next => { setValue(next); changed(next); }} onSave={vi.fn()} onNew={vi.fn()} />;
}
const field = (label: string) => screen.getByLabelText(label) as HTMLInputElement;
const edit = (label: string, value: string) => fireEvent.change(field(label), { target: { value } });
const save = () => screen.getByRole('button', { name: '保存草稿' }) as HTMLButtonElement;

describe('Existing-owner genre and shot time authoring', () => {
  it('does not materialize optional fields by viewing or editing an unrelated field', () => {
    const changed = vi.fn(); render(<Harness changed={changed} />);
    expect(field('文档类型 / 题材').value).toBe(''); expect(field('时间连续性').value).toBe('');
    expect(changed).not.toHaveBeenCalled(); edit('文档标题', 'Retitled');
    const value = documentInput(changed.mock.calls.at(-1)![0]);
    expect(value.visual_target).toEqual(target()); expect(value.shots[0]).not.toHaveProperty('continuity');
  });
  it('creates genre in the original Director target without inventing time or lighting', () => {
    const changed = vi.fn(); render(<Harness value={{ ...initial(), mode: 'DIRECTOR', shots: [], visual_target: undefined }} changed={changed} />);
    edit('文档类型 / 题材', '悬疑科幻 🎬');
    expect(changed.mock.calls.at(-1)![0].visual_target).toEqual({ style: '', atmosphere: '', reference_works: [], color: '', rhythm: '', genre: '悬疑科幻 🎬' });
    expect(changed.mock.calls.at(-1)![0].shots).toEqual([]);
  });
  it('hydrates and changes only genre/time, preserving IDs, links, siblings and unrecognized nested data', () => {
    const changed = vi.fn(), value = initial();
    const visual = { ...target(), genre: '旧题材', future_target: { keep: true } };
    const continuity = { characters: '林', outfit: '红衣', environment: '旧城', camera: '固定', time: '夜', lighting: '侧光', next_shot_id: 'shot-2', future_continuity: ['keep'] };
    value.visual_target = visual; value.shots[0] = { ...value.shots[0], continuity, director_note_ids: ['note-original'] };
    render(<Harness value={value} changed={changed} />);
    expect(field('文档类型 / 题材').value).toBe('旧题材'); expect(field('时间连续性').value).toBe('夜');
    edit('文档类型 / 题材', ' 新题材 🎬 '); edit('时间连续性', ' 黎明 🌅 ');
    const next = documentInput(changed.mock.calls.at(-1)![0]);
    expect(next.visual_target).toEqual({ ...visual, genre: ' 新题材 🎬 ' });
    expect(next.shots[0]).toEqual({ ...value.shots[0], continuity: { ...continuity, time: ' 黎明 🌅 ' } });
    expect(next.shots[1]).toEqual(value.shots[1]); expect(next.scenes).toEqual(value.scenes);
    edit('时间连续性', ''); edit('文档类型 / 题材', '');
    const cleared = documentInput(changed.mock.calls.at(-1)![0]);
    expect(cleared.visual_target).toEqual({ ...visual, genre: '' });
    expect(cleared.shots[0].continuity).toEqual({ ...continuity, time: '' });
  });
  it('authors time independently of scene time and ordinary lighting, and retains it when only links clear', () => {
    const changed = vi.fn(); render(<Harness changed={changed} />);
    edit('后接镜头', 'shot-2'); edit('时间连续性', '日落'); edit('光线设计', '冷光');
    fireEvent.click(screen.getByRole('button', { name: '清除前后镜头关系，保留连续性文字' }));
    const next = changed.mock.calls.at(-1)![0];
    expect(next.shots[0]).toMatchObject({ id: 'shot-1', lighting: '冷光', continuity: { time: '日落' } });
    expect(next.shots[0].continuity).not.toHaveProperty('next_shot_id');
    expect(next.shots[0].continuity).not.toHaveProperty('lighting'); expect(next.scenes[0].time).toBe('场景原始时间');
    expect(screen.getByText(/场景时间不会自动填入/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '清除连续性要求' }));
    expect(changed.mock.calls.at(-1)![0].shots[0]).not.toHaveProperty('continuity');
  });
  it.each([['文档类型 / 题材', 2000], ['时间连续性', 4000]] as const)('counts Unicode code points and keeps over-limit %s text recoverable', (label, maximum) => {
    render(<Harness />); const valid = '🎬'.repeat(maximum);
    edit(label, valid); expect(field(label).value).toBe(valid); expect(save().disabled).toBe(false);
    expect(field(label).getAttribute('aria-invalid')).toBe('false');
    edit(label, valid + '多'); expect(field(label).value).toBe(valid + '多'); expect(save().disabled).toBe(true);
    expect(field(label).getAttribute('aria-invalid')).toBe('true');
    const help = document.getElementById(field(label).getAttribute('aria-describedby')!);
    expect(help?.textContent).toContain(`${maximum + 1} / ${maximum}`);
    edit(label, '已缩短'); expect(save().disabled).toBe(false);
  });
  it('blocks saving an over-limit time on an unselected shot and identifies that shot', () => {
    const value = initial(); value.shots[1].continuity = { characters: '', outfit: '', environment: '', camera: '', time: '时'.repeat(4001) };
    render(<Harness value={value} />); expect(field('时间连续性').value).toBe(''); expect(save().disabled).toBe(true);
    expect(screen.getByRole('alert').textContent).toContain('镜头 2');
  });
  it.each([{ busy: true, editable: true }, { busy: false, editable: false }])('uses the original busy/read-only fieldset: %o', state => {
    render(<Harness {...state} />);
    for (const label of ['文档类型 / 题材', '时间连续性']) expect(field(label).closest('fieldset')?.disabled).toBe(true);
  });
});

const response = (body: unknown, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => body });
const workspaceProps: CreativeWorkspaceProps = { enabled: true, novelId: 'synthetic-novel',
  context: { sessionToken: 'synthetic-session', actor: { id: 'author', displayName: 'Author', workspaceId: 'w' }, scope: { workspaceId: 'w', projectId: 'p', storylineId: 's', branchId: 'b' } },
  scope: { workspace: 'Synthetic', project: 'Synthetic', storyline: 'Synthetic', branch: 'Synthetic' }, actor: 'Author',
  chapterCount: 0, manuscriptReady: false, novelMain: <p>Manuscript</p>, novelSidebar: <p>Chapters</p>, novelInspector: <p>Inspector</p>, novelStatus: <p>Saved</p>, onExit: vi.fn(), onModuleChange: vi.fn() };
const saved = (input: CreativeInput = initial(), version = 1): CreativeDocument => ({ ...input, id: 'document', version, status: 'DRAFT', actor_id: 'author', created_at: '', updated_at: '', source_evidence: {} });
function workspaceServer(documents: CreativeDocument[], override?: (url: string, init: RequestInit) => unknown) {
  const fetchMock = vi.fn(async (url: string, init: RequestInit = {}) => {
    const result = override?.(url, init); if (result !== undefined) return await result;
    if (url.endsWith('/capabilities')) return response({ enabled: true, can_mutate: true, modes: ['DIRECTOR', 'STORYBOARD'] });
    if (url.endsWith('/documents')) return response({ items: documents });
    if (url.endsWith('/creation-reference-data')) return response({ characters: [], locations: [], story_routes: [] });
    if (url.endsWith('/assets')) return response([]);
    if (url.endsWith('/director-proposals') || url.endsWith('/model-routes')) return response({ items: [] });
    if (url.endsWith('/local-ai/environment')) return response({ code: 'UNAVAILABLE' }, 404);
    throw new Error(`Unexpected synthetic request ${init.method} ${url}`);
  });
  vi.stubGlobal('fetch', fetchMock);
  return { fetchMock, writes: () => fetchMock.mock.calls.filter(([, init]) => init?.method && init.method !== 'GET') };
}
async function openWorkspace(mode: 'Storyboard' | 'Director' = 'Storyboard') {
  const view = render(<CreativeWorkspace {...workspaceProps} />);
  await waitFor(() => expect(screen.queryByText('正在核对创作文档与权限…')).toBeNull());
  fireEvent.click(within(screen.getByRole('tablist', { name: '创作模式' })).getByRole('tab', { name: new RegExp(mode) }));
  await screen.findByLabelText('文档标题'); return view;
}
describe('Full-document authoring uses the original save and history flow', () => {
  it('creates a Director document with genre and no unauthored extensions', async () => {
    const { writes } = workspaceServer([], (_url, init) => init.method === 'POST' ? response(saved(JSON.parse(String(init.body)))) : undefined);
    await openWorkspace('Director'); edit('文档标题', 'New direction'); fireEvent.click(screen.getByLabelText('这是独立创作'));
    edit('文档类型 / 题材', '悬疑'); fireEvent.click(save()); await screen.findByText('已保存“New direction” · v1');
    expect(writes()).toHaveLength(1); const payload = JSON.parse(String(writes()[0][1]?.body));
    expect(payload).toMatchObject({ mode: 'DIRECTOR', visual_target: { genre: '悬疑' } });
    expect(payload).not.toHaveProperty('expected_version'); expect(payload.shots).toEqual([]);
  });
  it('updates all preserved content once with expected_version, reopens it, and restores previous genre/time as a new version', async () => {
    const old = saved(), history = [old]; let current = old;
    let settle!: (value: ReturnType<typeof response>) => void;
    const pending = new Promise<ReturnType<typeof response>>(resolve => { settle = resolve; });
    const { writes } = workspaceServer([old], (url, init) => {
      if (init.method === 'PUT') { const { expected_version, ...value } = JSON.parse(String(init.body)); expect(expected_version).toBe(current.version); current = saved(value, current.version + 1); history.push(current); return pending; }
      if (url.endsWith('/history')) return response({ document_id: 'document', current_version: current.version, items: history });
      if (url.endsWith('/restore')) { expect(JSON.parse(String(init.body))).toEqual({ expected_version: 2, restore_version: 1 }); current = saved(documentInput(old), 3); return response(current); }
      if (url.endsWith('/documents')) return response({ items: [current] });
    });
    const view = await openWorkspace(); edit('文档类型 / 题材', '科幻 🎬'); edit('时间连续性', '凌晨 🌅');
    const button = save(); act(() => { button.click(); button.click(); }); expect(writes()).toHaveLength(1);
    expect(field('时间连续性').closest('fieldset')?.disabled).toBe(true);
    await act(async () => settle(response(current))); await screen.findByText('已保存“Authored continuity” · v2');
    const payload = JSON.parse(String(writes()[0][1]?.body));
    expect(payload).toMatchObject({ expected_version: 1, visual_target: { ...target(), genre: '科幻 🎬' }, shots: [{ id: 'shot-1', continuity: { time: '凌晨 🌅' } }, { id: 'shot-2' }] });
    expect(payload.scenes).toEqual(old.scenes); expect(payload.shots[1]).toEqual(old.shots[1]);
    view.unmount(); await openWorkspace(); expect(field('文档类型 / 题材').value).toBe('科幻 🎬'); expect(field('时间连续性').value).toBe('凌晨 🌅');
    fireEvent.click(screen.getByRole('button', { name: '历史' })); await screen.findByText('版本历史 · 当前 v2');
    fireEvent.click(screen.getByLabelText('已核对 v1 的完整内容；恢复会新建当前版本'));
    fireEvent.click(screen.getByRole('button', { name: '恢复 v1 为新版本' })); await screen.findByText('已将所选历史内容恢复为新版本 v3，其他历史版本仍保留。');
    expect(field('文档类型 / 题材').value).toBe(''); expect(field('时间连续性').value).toBe(''); expect(writes()).toHaveLength(2);
    expect(documentInput(current)).toEqual(documentInput(old));
  });
  it('retains genre/time on a save conflict until explicit server replacement', async () => {
    const original = saved(), server = saved({ ...initial(), visual_target: { ...target(), genre: '服务端题材' } }, 2);
    const { writes } = workspaceServer([original], (url, init) => init.method === 'PUT' ? response({ code: 'CREATIVE_VERSION_CONFLICT' }, 409) : url.endsWith('/documents/document') ? response(server) : undefined);
    await openWorkspace(); edit('文档类型 / 题材', '保留本地'); edit('时间连续性', '夜'); fireEvent.click(save());
    await screen.findByText('需要核对版本 · 本地草稿仍保留'); expect(field('文档类型 / 题材').value).toBe('保留本地'); expect(field('时间连续性').value).toBe('夜');
    expect(save().disabled).toBe(true); expect(writes()).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: '核对服务端版本' })); await screen.findByLabelText('服务端版本核对');
    expect(field('时间连续性').value).toBe('夜');
    fireEvent.click(screen.getByLabelText('已核对并确认用服务端版本替换当前本地草稿'));
    fireEvent.click(screen.getByRole('button', { name: '使用核对后的服务端版本' }));
    expect(field('文档类型 / 题材').value).toBe('服务端题材'); expect(field('时间连续性').value).toBe(''); expect(writes()).toHaveLength(1);
  });
});
