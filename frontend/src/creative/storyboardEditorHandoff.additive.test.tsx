// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { GraphDirectorStoryboardHandoff } from './GraphDirectorStoryboardHandoff';
import type { GraphDirectorSource } from './GraphDirectorConsole';
import { checkedStoryboardReceipt, prepareStoryboardEditor, storyboardEditorRequest } from './storyboardEditorHandoff';
import { newDocument, newScene, newShot, type CreativeDocument } from './types';
const sourcePin = { id: 'director-original', version: 3, digest: 'a'.repeat(64) };
const source: CreativeDocument = { ...newDocument('DIRECTOR'), id: sourcePin.id, version: 3, title: 'Director', status: 'DRAFT', created_at: '', updated_at: '', actor_id: 'author', source_evidence: {}, scenes: [{ ...newScene(1), id: 'scene' }], director_notes: [{ id: 'note', number: 1, scene_id: 'scene', blocking: '', note: 'Turn', shot_size: 'MEDIUM', camera_angle: 'EYE_LEVEL', camera_motion: 'STATIC', duration_seconds: 5, emotion: '', pacing: '', performance: '' }] };
const board: CreativeDocument = { ...source, id: 'exact-board', mode: 'STORYBOARD', version: 2, title: 'Exact board', shots: [{ ...newShot(1, 'scene'), id: 'shot' }], source_documents: { [sourcePin.id]: { version: sourcePin.version, digest: sourcePin.digest } } };
const receipt = { document: board, document_digest: 'b'.repeat(64), format: '', boundary: '' };
const caps = { enabled: true, can_mutate: true, modes: ['STORYBOARD' as const] };
afterEach(cleanup);
function setup() {
  const client = { derive: vi.fn().mockResolvedValue(board), export: vi.fn().mockResolvedValue(receipt), list: vi.fn().mockResolvedValue({ items: [board] }), create: vi.fn(), update: vi.fn(), capabilities: vi.fn(), history: vi.fn() } as GraphDirectorSource;
  return { client, source, snapshot: sourcePin, active: true, canCreate: true, busy: false, isCurrent: () => true, read: async <T,>(work: () => Promise<T>) => work(), mutate: async <T,>(work: () => Promise<T>) => work(), onPending: vi.fn(), onOpenStoryboard: vi.fn() };
}
const click = (name: string | RegExp) => fireEvent.click(screen.getByRole('button', { name }));
describe('exact storyboard editor scalar authority', () => {
  it('freezes complete prepared data independently of mutable server objects', () => {
    const request = storyboardEditorRequest(board, receipt.document_digest, sourcePin);
    const prepared = prepareStoryboardEditor(request, receipt, caps);
    expect(prepared.receipt.document).not.toBe(board);
    expect(Object.isFrozen(prepared.receipt.document.shots[0])).toBe(true);
    expect(checkedStoryboardReceipt(request, prepared.receipt).id).toBe('exact-board');
  });
  it.each([
    { document: { ...board, id: 'sibling' } }, { document: { ...board, version: 3 } },
    { document_digest: 'c'.repeat(64) }, { document: { ...board, mode: 'DIRECTOR' } },
    { document: { ...board, source_documents: {} } }, { document: { ...board, shots: [null] } },
    { document: { ...board, scenes: [] , shots: [{ ...board.shots[0], dialogue: null }] } },
    ...['characters', 'emotion', 'director_note_ids', 'video_generation_hint', 'continuity'].map(key => ({ document: { ...board, shots: [{ ...board.shots[0], [key]: {} }] } })),
    { document: { ...board, visual_target: { reference_works: {} } } },
    { document: { ...board, director_notes: [{ ...board.director_notes[0], planning: {} }] } },
    { document: { ...board, director_notes: [{ ...board.director_notes[0], performances: {} }] } },
  ])('rejects drift or malformed exact export %#', patch => {
    const request = storyboardEditorRequest(board, receipt.document_digest, sourcePin);
    expect(() => checkedStoryboardReceipt(request, { ...receipt, ...patch })).toThrow();
  });
  it('requires explicit inspection digest and explicit Open, never auto-opens a create receipt', async () => {
    const props = setup(); render(<GraphDirectorStoryboardHandoff {...props} />);
    fireEvent.click(screen.getByRole('checkbox')); click('交接到原分镜草稿');
    const button = await screen.findByRole('button', { name: '在原分镜编辑器打开' });
    expect((button as HTMLButtonElement).disabled).toBe(true); expect(props.onOpenStoryboard).not.toHaveBeenCalled();
    click('核对分镜原文档版本'); await screen.findByText(new RegExp(receipt.document_digest));
    expect(props.onOpenStoryboard).not.toHaveBeenCalled(); click('在原分镜编辑器打开');
    expect(props.onOpenStoryboard).toHaveBeenCalledTimes(1);
    expect(props.onOpenStoryboard.mock.calls[0][0]).toMatchObject({ target: { id: board.id, version: 2, digest: receipt.document_digest, mode: 'STORYBOARD' }, source: sourcePin });
    expect(props.client.export).toHaveBeenCalledWith(board.id);
  });
  it('keeps uncertain derive unresolved while opening an inspected existing board', async () => {
    const props = setup(); vi.mocked(props.client.derive).mockRejectedValue(new Error('lost receipt'));
    render(<GraphDirectorStoryboardHandoff {...props} />); fireEvent.click(screen.getByRole('checkbox')); click('交接到原分镜草稿');
    await screen.findByText('lost receipt'); click('读取关联分镜与状态');
    fireEvent.click(await screen.findByRole('button', { name: '读取分镜 Exact board · v2' })); await screen.findByText(new RegExp(receipt.document_digest));
    click('在原分镜编辑器打开'); expect(props.onOpenStoryboard).toHaveBeenCalledTimes(1); expect(props.onPending).toHaveBeenLastCalledWith(true);
    expect((screen.getByRole('button', { name: '交接到原分镜草稿' }) as HTMLButtonElement).disabled).toBe(true);
  });
  it('retires retained callbacks on inspection, source eligibility ABA and unmount', async () => {
    const props = setup(), view = render(<GraphDirectorStoryboardHandoff {...props} />);
    click('读取关联分镜与状态'); fireEvent.click(await screen.findByRole('button', { name: '读取分镜 Exact board · v2' })); await screen.findByText(new RegExp(receipt.document_digest));
    click('在原分镜编辑器打开'); const valid = props.onOpenStoryboard.mock.calls[0][1]; expect(valid()).toBe(true);
    view.rerender(<GraphDirectorStoryboardHandoff {...props} canOpen={false} />); view.rerender(<GraphDirectorStoryboardHandoff {...props} />); expect(valid()).toBe(false);
    view.unmount(); expect(valid()).toBe(false);
  });
});
