// @vitest-environment jsdom
import { useState } from 'react';
import { cleanup, fireEvent, render, screen, within, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { CreativeCanvas } from './CreativeCanvas';
import { GraphDirectorConsole, type GraphDirectorSource } from './GraphDirectorConsole';
import { compareDirectorDraft } from './directorDraftComparison';
import { documentInput, newDocument, newScene, newShot, type CreativeInput, type CreativeDocument } from './types';
import { cameraGeometry } from './cameraGeometry.testFixture';
import { validCameraGrammar } from './cameraGrammar';
import { checkedPlanningProjection, checkedCreativeShot } from './studioProductionGraphContract';
import { validStoryboardDocument } from './storyboardEditorHandoff';
import { checkedDirectorPendingReceipt, checkedDirectorReviewSubmission } from './directorModelClient';
import captured from './directorModelActionWire.testFixture.json';

afterEach(cleanup);
const edit = (scope: ReturnType<typeof within>, label: string, value: string) => fireEvent.change(scope.getByLabelText(label), { target: { value } });
function initial(mode: 'DIRECTOR' | 'STORYBOARD' = 'DIRECTOR'): CreativeInput {
  const scene = { ...newScene(1), id: 'scene-1' };
  return { ...newDocument(mode), source_independent: true, title: 'Authored geometry', scenes: [scene],
    director_notes: mode === 'DIRECTOR' ? [1, 2].map(n => ({ id: `note-${n}`, number: n, scene_id: scene.id, note: 'Semantic intent', blocking: '',
      shot_size: 'MEDIUM', camera_angle: 'EYE_LEVEL', camera_motion: 'STATIC', duration_seconds: 5, emotion: '', pacing: '', performance: '' })) : [],
    shots: mode === 'STORYBOARD' ? [1, 2].map(n => ({ ...newShot(n, scene.id), id: `shot-${n}` })) : [] };
}
function Harness({ source = initial(), save = vi.fn(), changed = vi.fn(), busy = false }: { source?: CreativeInput; save?: (v: CreativeInput) => void; changed?: (v: CreativeInput) => void; busy?: boolean }) {
  const [draft, setDraft] = useState(source);
  return <CreativeCanvas draft={draft} dirty canEdit busy={busy} onChange={v => { setDraft(v); changed(v); }}
    onSave={() => save(draft)} onNew={() => {}} onScene={() => {}} onShot={() => {}} />;
}
function author(label: string, y: string) {
  const fields = within(screen.getByLabelText(label));
  fireEvent.click(fields.getByRole('button', { name: '启用手填几何（坐标仍为空）' }));
  edit(fields, '坐标系标识', 'room-metres');
  for (let n = 1; n <= 2; n++) { fireEvent.click(fields.getByRole('button', { name: '添加人物位置（初始 x=0,y=0）' })); edit(fields, `位置 ${n} 人物标识`, n === 1 ? 'a' : 'b'); }
  edit(fields, '位置 2 x', '4'); edit(fields, '有序轴线端点 1', 'a'); edit(fields, '有序轴线端点 2', 'b');
  fireEvent.click(fields.getByRole('button', { name: '添加机位（初始 x=0,y=0）' })); edit(fields, '机位 x', '2'); edit(fields, '机位 y', y);
}
it('viewing and unrelated edits leave legacy fields absent; two notes use the original Save', () => {
  const save = vi.fn(), changed = vi.fn(); render(<Harness save={save} changed={changed} />);
  expect(changed).not.toHaveBeenCalled(); fireEvent.change(screen.getByLabelText('文档标题'), { target: { value: 'New title' } });
  expect(changed.mock.calls.at(-1)![0].director_notes.every((r: any) => !Object.hasOwn(r, 'camera_grammar'))).toBe(true);
  author('调度 1 手填机位几何', '2'); author('调度 2 手填机位几何', '-2');
  expect(save).not.toHaveBeenCalled(); fireEvent.click(screen.getByRole('button', { name: '保存草稿' }));
  expect(save).toHaveBeenCalledTimes(1); const payload = documentInput(save.mock.calls[0][0]);
  expect(payload.director_notes.map(n => n.id)).toEqual(['note-1', 'note-2']);
  expect(payload.director_notes.map(n => n.camera_grammar)).toEqual([cameraGeometry(), cameraGeometry(-2)]);
  expect(payload.director_notes.map(n => n.note)).toEqual(['Semantic intent', 'Semantic intent']);
});
it('uses the same mounted editor for Storyboard shots and preserves siblings on removal', () => {
  const save = vi.fn(), source = initial('STORYBOARD'); source.shots[1].camera_grammar = cameraGeometry(-2);
  render(<Harness source={source} save={save} />); author('镜头 1 手填机位几何', '2');
  fireEvent.click(screen.getByRole('button', { name: '保存草稿' })); expect(save.mock.calls[0][0].shots[0].camera_grammar).toEqual(cameraGeometry());
  fireEvent.click(screen.getByRole('button', { name: '移除手填几何' })); fireEvent.click(screen.getByRole('button', { name: '保存草稿' }));
  expect(save.mock.calls[1][0].shots[0]).not.toHaveProperty('camera_grammar'); expect(save.mock.calls[1][0].shots[1]).toEqual(source.shots[1]);
});
it('keeps invalid numeric, label and intentional-choice drafts but blocks original Save', () => {
  const source = initial(); source.director_notes[0].camera_grammar = cameraGeometry(); render(<Harness source={source} />);
  const f = within(screen.getByLabelText('调度 1 手填机位几何')), save = screen.getByRole('button', { name: '保存草稿' }) as HTMLButtonElement;
  edit(f, '机位 x', ''); expect(save.disabled).toBe(true); expect((f.getByLabelText('机位 x') as HTMLInputElement).value).toBe('');
  edit(f, '机位 x', '2'); expect(save.disabled).toBe(false);
  expect((f.getByLabelText('位置 1 人物标识') as HTMLInputElement).maxLength).toBe(240);
  edit(f, '位置 1 人物标识', ''); expect(save.disabled).toBe(true); edit(f, '位置 1 人物标识', 'a'); expect(save.disabled).toBe(false);
  edit(f, '位置 1 人物标识', ' b '); expect(save.disabled).toBe(true); expect((f.getByLabelText('位置 1 人物标识') as HTMLInputElement).value).toBe(' b ');
  edit(f, '位置 1 人物标识', 'a'); expect(save.disabled).toBe(false);
  fireEvent.click(f.getByLabelText('有意越轴')); expect(save.disabled).toBe(true); edit(f, '有意选择理由', 'Deliberate rupture'); expect(save.disabled).toBe(false);
});
it('follows the original busy/read-only fieldset', () => {
  render(<Harness busy />); const button = screen.getAllByRole('button', { name: '启用手填几何（坐标仍为空）' })[0];
  expect(button.closest('fieldset')!.disabled).toBe(true);
});
it('keeps the closed Graph/Storyboard DTO contract and reports geometry in conflict comparison', () => {
  const board = initial('STORYBOARD'); board.shots[0].camera_grammar = cameraGeometry();
  expect(checkedCreativeShot(board.shots[0]).camera_grammar).toEqual(cameraGeometry());
  const source = initial(); source.director_notes[0].camera_grammar = cameraGeometry();
  expect(checkedPlanningProjection({ document_snapshot: { id: 'doc', version: 1, digest: 'a'.repeat(64) }, content: source }, 'DIRECTOR').content).toEqual(source);
  const malformed = { ...cameraGeometry(), guessed: true }; expect(validCameraGrammar(malformed)).toBe(false);
  expect(() => checkedCreativeShot({ ...board.shots[0], camera_grammar: malformed })).toThrow();
  const document = { ...board, id: 'doc', version: 1, status: 'DRAFT', actor_id: 'a', created_at: '', updated_at: '', source_evidence: {} };
  expect(validStoryboardDocument(document)).toBe(true); expect(validStoryboardDocument({ ...document, shots: [{ ...board.shots[0], camera_grammar: malformed }] })).toBe(false);
  expect(compareDirectorDraft(source, initial()).some(row => row.label.includes('手填机位几何'))).toBe(true);
});
it('rejects coordinates in model pending output but allows explicit human review edits', () => {
  const pending: any = structuredClone(captured.pending.receipt); pending.director_notes[0].camera_grammar = cameraGeometry();
  const source = { id: pending.provenance.source_document_id, version: pending.provenance.source_version, digest: pending.provenance.source_digest };
  expect(() => checkedDirectorPendingReceipt(pending, pending.proposal_id, source)).toThrow();
  const review: any = structuredClone(captured.submitted_review); review.director_notes[0].camera_grammar = cameraGeometry();
  expect(checkedDirectorReviewSubmission(review).director_notes[0].camera_grammar).toEqual(cameraGeometry());
});
it.each([false, true])('Graph original owner save/reopen retains exact geometry and preserves a conflict draft=%s', async conflict => {
  let stored: CreativeDocument = { ...initial(), id: 'doc', version: 1, status: 'DRAFT', actor_id: 'author', created_at: '', updated_at: '', source_evidence: {} };
  stored.director_notes[0].camera_grammar = cameraGeometry();
  const pin = { id: 'doc', version: 1, digest: 'a'.repeat(64) };
  const client: GraphDirectorSource = { history: vi.fn(), derive: vi.fn(), list: vi.fn(), create: vi.fn(),
    capabilities: vi.fn(async () => ({ enabled: true, can_mutate: true, modes: ['DIRECTOR' as const] })),
    export: vi.fn(async () => ({ document: structuredClone(stored), document_digest: pin.digest, format: '', boundary: '' })),
    update: vi.fn(async (_id, _version, input) => { if (conflict) throw new ApiError({ status: 409, code: 'CONFLICT', message: 'Conflict' }); return stored = { ...stored, ...input, version: 2 }; }) };
  const props = { client, pin, active: true, canMutate: true, busy: false, isCurrent: () => true,
    read: async <T,>(work: () => Promise<T>) => work(), mutate: async <T,>(work: () => Promise<T>) => work(), onDirtyChange: vi.fn() };
  const view = render(<GraphDirectorConsole {...props} />);
  fireEvent.click(screen.getByRole('button', { name: '打开导演总控台' }));
  await waitFor(() => expect((screen.getByLabelText('文档标题') as HTMLInputElement).closest('fieldset')!.disabled).toBe(false));
  fireEvent.click(screen.getByRole('button', { name: '读取选中导演节点原文档' }));
  await screen.findByLabelText('调度 1 手填机位几何'); const f = within(screen.getByLabelText('调度 1 手填机位几何'));
  edit(f, '机位 y', '-4'); fireEvent.click(screen.getByRole('button', { name: '保存草稿' }));
  await waitFor(() => expect(client.update).toHaveBeenCalledTimes(1));
  expect(vi.mocked(client.update).mock.calls[0].slice(0, 2)).toEqual(['doc', 1]);
  if (conflict) { await screen.findByText(/保存冲突或回执不确定/); expect((f.getByLabelText('机位 y') as HTMLInputElement).value).toBe('-4'); expect((screen.getByRole('button', { name: '保存草稿' }) as HTMLButtonElement).disabled).toBe(true); }
  else { await screen.findByText(/导演原文档已保存/); view.unmount(); render(<GraphDirectorConsole {...props} pin={{ ...pin, version: 2 }} />);
    fireEvent.click(screen.getByRole('button', { name: '打开导演总控台' })); await waitFor(() => expect((screen.getByLabelText('文档标题') as HTMLInputElement).closest('fieldset')!.disabled).toBe(false));
    fireEvent.click(screen.getByRole('button', { name: '读取选中导演节点原文档' })); await screen.findByLabelText('调度 1 手填机位几何'); expect((screen.getByLabelText('机位 y') as HTMLInputElement).value).toBe('-4'); }
});
