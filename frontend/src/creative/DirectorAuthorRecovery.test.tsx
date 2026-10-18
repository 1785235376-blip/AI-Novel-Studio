// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { useDirectorAuthorRecovery } from './useDirectorAuthorRecovery';
import { GraphDirectorConsole, type GraphDirectorSource } from './GraphDirectorConsole';
import { directorAuthorDraftKey, encodeDirectorAuthorDraft, readDirectorAuthorDraft } from './directorAuthorLocalDraft';
import { newDocument, newScene, type CreativeDocument, type CreativeInput } from './types';
import type { StudioGraphDraftOwner } from './studioGraphLocalDraft';
const owner: StudioGraphDraftOwner = { projectId: 'p', incarnation: 'file:original', actorId: 'author', actorWorkspaceId: '', mode: 'local', workspaceId: '', storylineId: '', branchId: '' };
const prefix = `${directorAuthorDraftKey(owner)}:snapshot:`, key = `${prefix}seed`, pin = { id: 'director-one', version: 1, digest: 'a'.repeat(64) };
const document = (): CreativeDocument => ({ ...newDocument('DIRECTOR'), source_independent: true, title: 'Original', id: pin.id, version: 1, status: 'DRAFT', created_at: '', updated_at: '', actor_id: 'author', source_evidence: {} });
const draft = (): CreativeInput => ({ ...newDocument('DIRECTOR'), source_independent: true, title: 'Private incomplete 中文', scenes: [{ ...newScene(1), heading: '', dialogue: [{ speaker: '', text: '输', delivery: '' }] }] });
function setup() {
  let live = true;
  const client = { capabilities: vi.fn(async () => ({ enabled: true, can_mutate: true, modes: ['DIRECTOR'] })),
    create: vi.fn(async (input: CreativeInput) => ({ ...document(), ...input })), update: vi.fn(), export: vi.fn(async () => ({ document: document(), document_digest: pin.digest, format: '', boundary: '' })),
    list: vi.fn(async () => ({ items: [document()] })), history: vi.fn(), derive: vi.fn() } as unknown as GraphDirectorSource;
  const props = { client, draftOwner: owner, verifyDraftOwner: vi.fn(async () => {}), active: true, canMutate: true, busy: false,
    isCurrent: () => live, read: async <T,>(w: () => Promise<T>) => w(), mutate: async <T,>(w: () => Promise<T>) => w(), onDirtyChange: vi.fn() };
  return { props, client, retire: () => { live = false; } };
}
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
const title = () => screen.getByLabelText('文档标题') as HTMLInputElement;
async function open() { click('打开导演总控台'); await waitFor(() => expect(screen.getByLabelText('文档标题')).toBeTruthy()); }
const stored = () => { const keys = Object.keys(localStorage).filter(k => k.startsWith(prefix)); return keys.map(k => localStorage.getItem(k)!).at(-1) ?? null; };
const seed = (base?: CreativeDocument, uncertain = false) => localStorage.setItem(key, encodeDirectorAuthorDraft(owner, draft(), base, base ? pin : undefined, uncertain));
beforeEach(() => localStorage.clear());
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
describe('Director author recovery', () => {
  it('retains incomplete input including an active IME edit, then explicitly revalidates on remount without writes', async () => {
    const { props, client } = setup(); let view = render(<GraphDirectorConsole {...props} />); await open();
    fireEvent.compositionStart(title()); fireEvent.change(title(), { target: { value: '中文尚未完成' } });
    await waitFor(() => expect(readDirectorAuthorDraft(stored()!, owner).draft.title).toBe('中文尚未完成'));
    view.unmount(); view = render(<GraphDirectorConsole {...props} />); await open();
    expect(title().value).toBe(''); expect(client.create).not.toHaveBeenCalled();
    click('核对并恢复导演作者草稿'); await waitFor(() => expect(title().value).toBe('中文尚未完成'));
    expect(props.verifyDraftOwner).toHaveBeenCalledTimes(1); expect(client.create).not.toHaveBeenCalled(); expect(client.update).not.toHaveBeenCalled();
  });
  it('preserves UNKNOWN across remount and never resubmits', async () => {
    seed(undefined, true); const { props, client } = setup(); render(<GraphDirectorConsole {...props} />); await open();
    click('核对并恢复导演作者草稿'); await waitFor(() => expect(title().value).toBe(draft().title));
    expect(screen.getByText(/原保存结果仍未知，禁止重新提交/)).toBeTruthy();
    expect((screen.getByRole('button', { name: '保存草稿' }) as HTMLButtonElement).disabled).toBe(true);
    expect(client.create).not.toHaveBeenCalled(); expect(client.update).not.toHaveBeenCalled();
    expect(readDirectorAuthorDraft(stored()!, owner).uncertain).toBe(true);
  });
  it('checks exact source version/digest and keeps drifted content undisclosed', async () => {
    seed(document()); const { props, client } = setup(); vi.mocked(client.export).mockResolvedValue({ document: { ...document(), version: 2 }, document_digest: pin.digest, format: '', boundary: '' });
    render(<GraphDirectorConsole {...props} />); await open(); click('核对并恢复导演作者草稿');
    await screen.findByText(/导演原文档版本或摘要已变化/); expect(title().value).toBe(''); expect(localStorage.getItem(key)).toContain(draft().title);
  });
  it('rechecks a saved base and restores only author input, without proposal or image authority', async () => {
    seed(document()); const { props, client } = setup(); render(<GraphDirectorConsole {...props} />); await open(); click('核对并恢复导演作者草稿');
    await waitFor(() => expect(title().value).toBe(draft().title)); expect(client.export).toHaveBeenCalledWith(pin.id);
    expect(client.update).not.toHaveBeenCalled(); expect(screen.queryByText('将此审核草稿添加到画布')).toBeNull();
  });
  it('does not reveal or remove another actor, branch or incarnation cache', async () => {
    seed(); const old = localStorage.getItem(key), { props } = setup();
    const view = render(<GraphDirectorConsole {...props} draftOwner={{ ...owner, actorId: 'other' }} />); await open();
    expect(screen.queryByText('核对并恢复导演作者草稿')).toBeNull(); expect(title().value).toBe('');
    view.unmount(); render(<GraphDirectorConsole {...props} draftOwner={{ ...owner, incarnation: 'file:replacement' }} />); await open();
    expect(screen.queryByText('核对并恢复导演作者草稿')).toBeNull(); expect(localStorage.getItem(key)).toBe(old);
    const collab = { ...owner, mode: 'collaboration' as const, actorWorkspaceId: 'w', workspaceId: 'w', storylineId: 's', branchId: 'a' };
    expect(directorAuthorDraftKey(collab)).not.toBe(directorAuthorDraftKey({ ...collab, branchId: 'b' }));
  });
  it('fences late owner validation after retirement and retains the recovery copy', async () => {
    seed(); const { props, retire } = setup(); let resolve!: () => void;
    props.verifyDraftOwner.mockImplementation(() => new Promise<void>(r => { resolve = r; }));
    const view = render(<GraphDirectorConsole {...props} />); await open(); click('核对并恢复导演作者草稿');
    retire(); view.rerender(<GraphDirectorConsole {...props} active={false} />); await act(async () => resolve());
    expect(screen.queryByDisplayValue(draft().title)).toBeNull(); expect(localStorage.getItem(key)).toContain(draft().title);
  });
  it('preserves corrupt cache and reports it instead of overwriting', async () => {
    localStorage.setItem(key, '{bad'); const { props } = setup(); render(<GraphDirectorConsole {...props} />); await open();
    await screen.findByText(/格式损坏/); fireEvent.change(title(), { target: { value: 'New local' } });
    expect(localStorage.getItem(key)).toBe('{bad'); expect(title().value).toBe('New local');
  });
  it('reports quota failure without pretending to save or dropping current text', async () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new DOMException('full', 'QuotaExceededError'); });
    const { props } = setup(); render(<GraphDirectorConsole {...props} />); await open(); fireEvent.change(title(), { target: { value: 'Keep me' } });
    await screen.findByText(/本机存储空间不足/); expect(title().value).toBe('Keep me'); expect(screen.queryByText(/导演作者输入已保留在本机/)).toBeNull();
  });
  it('never overwrites a changed tab snapshot during recovery or explicit discard', async () => {
    seed(); const { props } = setup(); render(<GraphDirectorConsole {...props} />); await open();
    const changed = encodeDirectorAuthorDraft(owner, { ...draft(), title: 'Other tab' }, undefined, undefined, false); localStorage.setItem(key, changed);
    click('核对并恢复导演作者草稿'); await screen.findByText(/其他页面已修改/); expect(title().value).toBe('');
    fireEvent.click(screen.getByLabelText('确认放弃此导演本机恢复草稿')); click('放弃导演本机恢复草稿');
    expect(localStorage.getItem(key)).toBe(changed);
  });
  it('user discard removes this snapshot, but mandatory authority retirement does not', async () => {
    const { props, retire } = setup(); let discard: (() => void) | undefined;
    const view = render(<GraphDirectorConsole {...props} registerRecoveryDiscard={value => { discard = value; }} />); await open();
    fireEvent.change(title(), { target: { value: 'Persist' } }); await waitFor(() => expect(stored()).not.toBeNull());
    act(() => discard?.()); expect(stored()).toBeNull();
    fireEvent.change(title(), { target: { value: 'Retain on auth loss' } }); await waitFor(() => expect(stored()).not.toBeNull());
    retire(); act(() => discard?.()); view.unmount(); expect(stored()).toContain('Retain on auth loss');
  });
  it('records uncertainty before submitting a save and preserves it after a lost response', async () => {
    const { props, client } = setup(); vi.mocked(client.create).mockImplementation(async () => {
      expect(readDirectorAuthorDraft(stored()!, owner).uncertain).toBe(true); throw new Error('lost');
    });
    render(<GraphDirectorConsole {...props} />); await open(); fireEvent.change(title(), { target: { value: 'Save me' } }); click('保存草稿');
    await screen.findByText(/保存冲突或回执不确定/); expect(client.create).toHaveBeenCalledTimes(1);
    expect(readDirectorAuthorDraft(stored()!, owner).uncertain).toBe(true);
  });
});
it('closed codec excludes owner metadata, credentials and authority while allowing incomplete author fields', () => {
  const input = draft(), raw = encodeDirectorAuthorDraft(owner, input, document(), pin, false); expect(readDirectorAuthorDraft(raw, owner).draft).toEqual(input);
  const v = JSON.parse(raw); v.reviewed = true; expect(() => readDirectorAuthorDraft(JSON.stringify(v), owner)).toThrow();
  const nested = draft(); (nested.scenes[0] as unknown as Record<string, unknown>).token = 'secret'; expect(() => encodeDirectorAuthorDraft(owner, nested, undefined, undefined, false)).toThrow();
  expect(raw).not.toContain('source_evidence'); expect(raw).not.toContain('actor_id');
  expect(() => encodeDirectorAuthorDraft(owner, { ...draft(), title: 'a'.repeat(3 * 1024 * 1024) }, undefined, undefined, false)).toThrow();
});

it('parallel writers preserve distinct snapshots and replace only their own earlier input', async () => {
  const common = { owner, available: true, isCurrent: () => true, dirty: false, uncertain: false, draft: newDocument('DIRECTOR') };
  const a = renderHook(p => useDirectorAuthorRecovery(p), { initialProps: common });
  const b = renderHook(p => useDirectorAuthorRecovery(p), { initialProps: common });
  a.rerender({ ...common, dirty: true, draft: { ...common.draft, title: 'Writer A' } });
  b.rerender({ ...common, dirty: true, draft: { ...common.draft, title: 'Writer B' } });
  const entries = () => Object.keys(localStorage).filter(k => k.startsWith(prefix)).map(k => JSON.parse(localStorage.getItem(k)!));
  expect(entries().map(e => e.draft.title).sort()).toEqual(['Writer A', 'Writer B']);
  a.rerender({ ...common, dirty: true, draft: { ...common.draft, title: 'Writer A second' } });
  expect(entries().map(e => e.draft.title).sort()).toEqual(['Writer A second', 'Writer B']);
  act(() => a.result.current.clear()); expect(entries().map(e => e.draft.title)).toEqual(['Writer B']);
});
it('a same-mount owner replacement immediately hides an already recovered author draft', async () => {
  seed(); const { props } = setup(); const view = render(<GraphDirectorConsole {...props} />); await open(); click('核对并恢复导演作者草稿');
  await waitFor(() => expect(title().value).toBe(draft().title));
  view.rerender(<GraphDirectorConsole {...props} draftOwner={{ ...owner, actorId: 'replacement' }} />);
  expect(screen.queryByLabelText('文档标题')).toBeNull(); expect(screen.queryByDisplayValue(draft().title)).toBeNull();
  expect(stored()).toContain(draft().title);
  view.rerender(<GraphDirectorConsole {...props} />); expect(screen.queryByLabelText('文档标题')).toBeNull();
});
it('revoked source authorization hides recovered content and preserves its quarantined recovery bytes', async () => {
  seed(document()); const { props, client } = setup(); render(<GraphDirectorConsole {...props} />); await open(); click('核对并恢复导演作者草稿');
  await waitFor(() => expect(title().value).toBe(draft().title));
  vi.mocked(client.export).mockRejectedValue(new ApiError({ status: 403, code: 'DENIED', message: 'No access' }));
  click('核对导演原文档版本'); await screen.findByText(/内容已隐藏/);
  expect(screen.queryByDisplayValue(draft().title)).toBeNull(); expect(stored()).toContain(draft().title);
});
