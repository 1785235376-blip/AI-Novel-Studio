// @vitest-environment jsdom
import { useState } from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { CreativeCanvas } from './CreativeCanvas';
import { DirectorCameraReuse } from './DirectorCameraReuse';
import { previewDirectorCameraReuse, type DirectorCameraField } from './directorCameraReuse';
import { emptyCameraGrammar } from './cameraGrammar';
import { newDocument, newScene, type CreativeInput, type DirectorSceneNote } from './types';
afterEach(cleanup);
function draft(): CreativeInput {
  const note = (id: string, number: number, scene_id: string): DirectorSceneNote => ({ id, number, scene_id, duration_seconds: number + 3, note: `Story ${id}`, blocking: 'Stand', shot_size: 'MEDIUM', camera_angle: 'EYE_LEVEL', camera_motion: 'STATIC', emotion: 'calm', pacing: 'slow', performance: 'wait', lens: '50mm', composition: 'center', camera_grammar: emptyCameraGrammar(), performances: [{ character: 'A', action: 'wait', expression: 'calm', state: 'standing' }] });
  return { ...newDocument('DIRECTOR'), title: 'Camera reuse', source_independent: true, scenes: [{ ...newScene(1), id: 'scene' }, { ...newScene(2), id: 'other' }], director_notes: [{ ...note('a', 1, 'scene'), shot_size: 'WIDE', lens: '' }, note('b', 2, 'scene'), note('c', 3, 'scene'), note('d', 4, 'other')] };
}
const props = () => ({ draft: draft(), sceneId: 'scene', version: 3, dirty: true, canEdit: true, busy: false, onChange: vi.fn() });
function choose() {
  fireEvent.change(screen.getByLabelText('摄影参数来源调度'), { target: { value: 'a' } });
  fireEvent.click(screen.getByLabelText('目标调度 2 · b'));
  fireEvent.click(screen.getByLabelText('复用景别'));
  fireEvent.click(screen.getByText('预览摄影参数复用'));
}
function handler(element: HTMLElement) { const key = Object.keys(element).find(key => key.startsWith('__reactProps$'))!; return (element as any)[key].onClick; }
it('changes only explicitly selected same-scene fields and preserves every other owner field', () => {
  const input = draft(), original = structuredClone(input);
  const result = previewDirectorCameraReuse(input, 'scene', 'a', ['b', 'c'], ['shot_size', 'lens']);
  expect(result.changes).toHaveLength(4);
  expect(input).toEqual(original);
  expect(result.draft.scenes).toBe(input.scenes); expect(result.draft.shots).toBe(input.shots);
  expect(result.draft.director_notes[0]).toBe(input.director_notes[0]); expect(result.draft.director_notes[3]).toBe(input.director_notes[3]);
  for (const index of [1, 2]) expect(result.draft.director_notes[index]).toEqual({ ...original.director_notes[index], shot_size: 'WIDE', lens: '' });
});
it('preserves omitted/null optional source values and recognizes no-op selections', () => {
  const input = draft(); delete input.director_notes[0].lens; input.director_notes[0].composition = null;
  const next = previewDirectorCameraReuse(input, 'scene', 'a', ['b'], ['lens', 'composition']);
  expect(Object.hasOwn(next.draft.director_notes[1], 'lens')).toBe(false); expect(next.draft.director_notes[1].composition).toBeNull();
  expect(previewDirectorCameraReuse(input, 'scene', 'a', ['b'], ['camera_motion']).changes).toEqual([]);
});
it('fails closed for invalid modes, scenes, IDs, fields and source values', () => {
  const input = draft();
  for (const targets of [[], ['a'], ['d'], ['missing'], ['b', 'b']]) expect(() => previewDirectorCameraReuse(input, 'scene', 'a', targets, ['shot_size'])).toThrow();
  for (const fields of [[], ['shot_size', 'shot_size'], ['duration_seconds']]) expect(() => previewDirectorCameraReuse(input, 'scene', 'a', ['b'], fields as DirectorCameraField[])).toThrow();
  expect(() => previewDirectorCameraReuse({ ...input, mode: 'STORYBOARD' }, 'scene', 'a', ['b'], ['shot_size'])).toThrow();
  expect(() => previewDirectorCameraReuse(input, 'missing', 'a', ['b'], ['shot_size'])).toThrow();
  expect(() => previewDirectorCameraReuse(input, 'scene', 'd', ['b'], ['shot_size'])).toThrow();
  input.director_notes[0].shot_size = 'a'.repeat(81);
  expect(() => previewDirectorCameraReuse(input, 'scene', 'a', ['b'], ['shot_size'])).toThrow();
  input.director_notes[0].id = 'b';
  expect(() => previewDirectorCameraReuse(input, 'scene', 'b', ['c'], ['lens'])).toThrow();
});
it('previews, applies, undoes and saves through the original canvas, then reopens the saved value', () => {
  const save = vi.fn(); let saved: CreativeInput | undefined;
  function Harness() {
    const [value, setValue] = useState(draft());
    return <CreativeCanvas draft={value} version={3} dirty canEdit busy={false} selectedSceneId="scene" onScene={() => {}} onShot={() => {}} onChange={setValue} onSave={() => { saved = structuredClone(value); save(value); }} onNew={() => {}} />;
  }
  const view = render(<Harness />); choose();
  expect(screen.getByRole('region', { name: '摄影参数复用预览' }).textContent).toContain('MEDIUM → WIDE'); expect(save).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText('确认应用摄影参数（尚未保存）'));
  fireEvent.click(screen.getByText('撤销本次摄影参数复用'));
  fireEvent.click(screen.getByText('保存草稿')); expect(saved).toEqual(draft());
  fireEvent.click(screen.getByText('预览摄影参数复用')); fireEvent.click(screen.getByText('确认应用摄影参数（尚未保存）'));
  fireEvent.click(screen.getByText('保存草稿')); expect(saved!.director_notes[1].shot_size).toBe('WIDE'); expect(saved!.director_notes[2].shot_size).toBe('MEDIUM');
  view.unmount(); render(<DirectorCameraReuse {...props()} draft={saved!} dirty={false} version={4} />);
  expect(screen.queryByText('确认应用摄影参数（尚未保存）')).toBeNull(); expect((screen.getByText('撤销本次摄影参数复用') as HTMLButtonElement).disabled).toBe(true);
});
it.each(['source', 'target', 'scene', 'version', 'dirty', 'busy', 'authority', 'unmount'])('permanently retires captured preview after %s changes, even when restored', kind => {
  const original = props(), view = render(<DirectorCameraReuse {...original} />); choose();
  const apply = handler(screen.getByText('确认应用摄影参数（尚未保存）'));
  if (kind === 'unmount') view.unmount(); else {
    const next = { ...original };
    if (kind === 'source' || kind === 'target') { next.draft = structuredClone(original.draft); next.draft.director_notes[kind === 'source' ? 0 : 1].performance = 'changed'; }
    if (kind === 'scene') next.sceneId = 'other'; if (kind === 'version') next.version = 4;
    if (kind === 'dirty') next.dirty = false; if (kind === 'busy') next.busy = true; if (kind === 'authority') next.canEdit = false;
    view.rerender(<DirectorCameraReuse {...next} />); view.rerender(<DirectorCameraReuse {...original} />);
  }
  act(apply); expect(original.onChange).not.toHaveBeenCalled(); expect(screen.queryByText('确认应用摄影参数（尚未保存）')).toBeNull();
});
it.each(['source', 'target', 'field'])('requires a fresh preview after changing selected %s', kind => {
  const original = props(); render(<DirectorCameraReuse {...original} />); choose(); const apply = handler(screen.getByText('确认应用摄影参数（尚未保存）'));
  if (kind === 'source') fireEvent.change(screen.getByLabelText('摄影参数来源调度'), { target: { value: 'c' } });
  if (kind === 'target') fireEvent.click(screen.getByLabelText('目标调度 3 · c'));
  if (kind === 'field') fireEvent.click(screen.getByLabelText('复用镜头与焦距'));
  act(apply); expect(original.onChange).not.toHaveBeenCalled();
});
it('consumes Apply once and prevents undo after subsequent edits or a busy round-trip', () => {
  const original = props(), view = render(<DirectorCameraReuse {...original} />); choose();
  const apply = handler(screen.getByText('确认应用摄影参数（尚未保存）')); act(() => { apply(); apply(); }); expect(original.onChange).toHaveBeenCalledTimes(1);
  const after = original.onChange.mock.calls[0][0]; view.rerender(<DirectorCameraReuse {...original} draft={after} />);
  const undo = handler(screen.getByText('撤销本次摄影参数复用'));
  view.rerender(<DirectorCameraReuse {...original} draft={after} busy />); view.rerender(<DirectorCameraReuse {...original} draft={after} />);
  act(undo); expect(original.onChange).toHaveBeenCalledTimes(1); expect((screen.getByText('撤销本次摄影参数复用') as HTMLButtonElement).disabled).toBe(true);
});

it('allows undo when Apply restores the saved baseline and parent computes dirty=false', () => {
  const baseline = draft(); baseline.director_notes[1].shot_size = 'WIDE';
  const edited = structuredClone(baseline); edited.director_notes[1].shot_size = 'MEDIUM';
  function Harness() {
    const [value, setValue] = useState(edited);
    return <><output aria-label="dirty state">{String(JSON.stringify(value) !== JSON.stringify(baseline))}</output><DirectorCameraReuse {...props()} draft={value} dirty={JSON.stringify(value) !== JSON.stringify(baseline)} onChange={setValue} /></>;
  }
  render(<Harness />); choose(); fireEvent.click(screen.getByText('确认应用摄影参数（尚未保存）'));
  expect(screen.getByLabelText('dirty state').textContent).toBe('false');
  expect((screen.getByText('撤销本次摄影参数复用') as HTMLButtonElement).disabled).toBe(false);
  fireEvent.click(screen.getByText('撤销本次摄影参数复用'));
  expect(screen.getByLabelText('dirty state').textContent).toBe('true');
});
it.each(['edit', 'save', 'version', 'scene', 'authority'])('retires Undo without clobbering work after %s changes', kind => {
  const initial = draft(), changed = vi.fn();
  let changeDraft: (value: CreativeInput) => void = () => {};
  const base = props();
  function Harness({ version = 3, busy = false, sceneId = 'scene', canEdit = true }) {
    const [value, setValue] = useState(initial); changeDraft = setValue;
    return <DirectorCameraReuse {...base} draft={value} version={version} busy={busy} sceneId={sceneId} canEdit={canEdit} onChange={next => { changed(next); setValue(next); }} />;
  }
  const view = render(<Harness />); choose(); fireEvent.click(screen.getByText('确认应用摄影参数（尚未保存）'));
  const undo = handler(screen.getByText('撤销本次摄影参数复用'));
  if (kind === 'edit') act(() => changeDraft({ ...changed.mock.calls[0][0], title: 'New unrelated edit' }));
  else {
    view.rerender(<Harness version={kind === 'version' ? 4 : 3} busy={kind === 'save'} sceneId={kind === 'scene' ? 'other' : 'scene'} canEdit={kind !== 'authority'} />);
    view.rerender(<Harness />);
  }
  act(undo); expect(changed).toHaveBeenCalledTimes(1);
  expect((screen.getByText('撤销本次摄影参数复用') as HTMLButtonElement).disabled).toBe(true);
});
