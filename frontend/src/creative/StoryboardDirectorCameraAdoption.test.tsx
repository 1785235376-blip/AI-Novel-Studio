// @vitest-environment jsdom
import { useState } from 'react';
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { CreativeCanvas } from './CreativeCanvas';
import { StoryboardDirectorCameraAdoption } from './StoryboardDirectorCameraAdoption';
import { previewStoryboardDirectorCameraAdoption } from './storyboardDirectorCameraAdoptionHelpers';
import { emptyCameraGrammar } from './cameraGrammar';
import { newDocument, newScene, newShot, type CreativeInput, type DirectorSceneNote } from './types';
import type { DirectorCameraField } from './directorCameraReuseHelpers';

afterEach(cleanup);
function fixture(): CreativeInput {
  const note: DirectorSceneNote = { id: 'note', number: 1, scene_id: 'scene', duration_seconds: 9, note: '既有导演来源', blocking: 'door',
    shot_size: 'WIDE', camera_angle: 'LOW_ANGLE', camera_motion: 'DOLLY', lens: '35mm', composition: 'left', emotion: 'calm', pacing: 'slow', performance: 'wait' };
  return { ...newDocument('STORYBOARD'), title: '分镜摄影采用', source_independent: true,
    scenes: [{ ...newScene(1), id: 'scene' }, { ...newScene(2), id: 'other' }],
    director_notes: [note, { ...note, id: 'other-note', number: 2, scene_id: 'other' }],
    shots: Array.from({ length: 5 }, (_, index) => ({ ...newShot(index + 1, 'scene'), id: `shot${index + 1}`,
      director_note_ids: ['note'], duration_seconds: 6 + index, frame_prompt: '原画面', video_generation_hint: '原视频要求',
      lens: '50mm', composition: 'center', camera_grammar: emptyCameraGrammar(),
      continuity: { characters: 'A', outfit: 'blue', environment: 'room', camera: 'same' }, director_notes: [{ ...note }] })) };
}
const props = () => ({ draft: fixture(), sceneId: 'scene', version: 3, dirty: false, canEdit: true, busy: false, onChange: vi.fn() });
const panel = () => within(screen.getByLabelText('分镜采用导演摄影参数'));
function choose() {
  fireEvent.change(panel().getByLabelText('采用摄影参数的原导演调度'), { target: { value: 'note' } });
  fireEvent.click(panel().getByLabelText('采用目标镜头 1 · shot1'));
  fireEvent.click(panel().getByLabelText('采用景别'));
  fireEvent.click(panel().getByText('预览采用导演摄影参数'));
}
function handler(element: HTMLElement) {
  const key = Object.keys(element).find(key => key.startsWith('__reactProps$'))!;
  return (element as unknown as Record<string, { onClick: () => void }>)[key].onClick;
}

it('adopts only chosen camera strings on linked same-scene shots and preserves all other author/source fields', () => {
  const input = fixture(), before = structuredClone(input);
  const result = previewStoryboardDirectorCameraAdoption(input, 'scene', 'note', ['shot2', 'shot1'], ['shot_size', 'lens']);
  expect(result.changes.map(row => row.id)).toEqual(['shot1', 'shot1', 'shot2', 'shot2']);
  expect(input).toEqual(before);
  expect(result.draft.scenes).toBe(input.scenes); expect(result.draft.director_notes).toBe(input.director_notes);
  for (const index of [0, 1]) expect(result.draft.shots[index]).toEqual({ ...before.shots[index], shot_size: 'WIDE', lens: '35mm' });
  for (const index of [2, 3, 4]) expect(result.draft.shots[index]).toBe(input.shots[index]);
  const noChange = previewStoryboardDirectorCameraAdoption(input, 'scene', 'note', ['shot1'], ['camera_motion']);
  expect(noChange.changes[0].before).toBe('STATIC');
  input.director_notes[0].camera_motion = 'STATIC';
  expect(previewStoryboardDirectorCameraAdoption(input, 'scene', 'note', ['shot1'], ['camera_motion']).draft).toBe(input);
  input.director_notes[0].lens = null;
  expect(previewStoryboardDirectorCameraAdoption(input, 'scene', 'note', ['shot1'], ['lens']).draft.shots[0].lens).toBe('');
});

it('rejects unbound/ambiguous/cross-scene targets, more than four shots and fields outside the camera allowlist', () => {
  const input = fixture();
  for (const ids of [[], ['shot1', 'shot1'], ['missing'], input.shots.map(shot => shot.id)])
    expect(() => previewStoryboardDirectorCameraAdoption(input, 'scene', 'note', ids, ['shot_size'])).toThrow();
  for (const fields of [[], ['shot_size', 'shot_size'], ['duration_seconds'], ['__proto__']])
    expect(() => previewStoryboardDirectorCameraAdoption(input, 'scene', 'note', ['shot1'], fields as DirectorCameraField[])).toThrow();
  for (const patch of [{ scene_id: 'other' }, { director_note_ids: [] }, { director_note_ids: ['note', 'note'] }, { director_note_ids: ['note', 'missing'] }])
    expect(() => previewStoryboardDirectorCameraAdoption({ ...input, shots: [{ ...input.shots[0], ...patch }] }, 'scene', 'note', ['shot1'], ['shot_size'])).toThrow();
  expect(() => previewStoryboardDirectorCameraAdoption({ ...input, mode: 'DIRECTOR' }, 'scene', 'note', ['shot1'], ['shot_size'])).toThrow();
  expect(() => previewStoryboardDirectorCameraAdoption(input, 'other', 'note', ['shot1'], ['shot_size'])).toThrow();
  input.director_notes.push({ ...input.director_notes[0] });
  expect(() => previewStoryboardDirectorCameraAdoption(input, 'scene', 'note', ['shot1'], ['shot_size'])).toThrow();
  input.director_notes.pop(); input.director_notes[0].lens = '字'.repeat(1001);
  expect(() => previewStoryboardDirectorCameraAdoption(input, 'scene', 'note', ['shot1'], ['lens'])).toThrow();
});

it('uses the original Canvas draft/Save/reopen, permits one guarded undo and never saves on preview/apply', () => {
  const save = vi.fn(); let saved: CreativeInput | undefined;
  function Harness() {
    const [value, setValue] = useState(fixture());
    return <CreativeCanvas draft={value} version={3} dirty canEdit busy={false} selectedSceneId="scene" selectedShotId="shot1"
      onScene={() => {}} onShot={() => {}} onChange={setValue} onSave={() => { saved = structuredClone(value); save(); }} onNew={() => {}} />;
  }
  const view = render(<Harness />); choose();
  expect(panel().getByLabelText('分镜摄影采用差异预览').textContent).toContain('MEDIUM → WIDE');
  expect(save).not.toHaveBeenCalled();
  fireEvent.click(panel().getByText('确认采用到分镜草稿（尚未保存）')); expect(save).not.toHaveBeenCalled();
  fireEvent.click(panel().getByText('撤销本次导演摄影采用'));
  fireEvent.click(screen.getByText('保存草稿')); expect(saved).toEqual(fixture());
  fireEvent.click(panel().getByText('预览采用导演摄影参数')); fireEvent.click(panel().getByText('确认采用到分镜草稿（尚未保存）'));
  fireEvent.click(screen.getByText('保存草稿')); expect(saved!.shots[0].shot_size).toBe('WIDE'); expect(saved!.shots[1].shot_size).toBe('MEDIUM');
  view.unmount(); render(<StoryboardDirectorCameraAdoption {...props()} draft={saved!} version={4} />);
  expect(panel().queryByText('确认采用到分镜草稿（尚未保存）')).toBeNull();
  expect((panel().getByText('撤销本次导演摄影采用') as HTMLButtonElement).disabled).toBe(true);
});

it.each(['source', 'binding', 'scene', 'version', 'dirty', 'busy', 'authority', 'unmount'])('retires old approval across %s ABA', change => {
  const original = props(), view = render(<StoryboardDirectorCameraAdoption {...original} />); choose();
  const apply = handler(panel().getByText('确认采用到分镜草稿（尚未保存）'));
  if (change === 'unmount') view.unmount();
  else {
    const next = { ...original };
    if (change === 'source' || change === 'binding') {
      next.draft = structuredClone(original.draft);
      if (change === 'source') next.draft.director_notes[0].performance = 'changed'; else next.draft.shots[0].director_note_ids = [];
    }
    if (change === 'scene') next.sceneId = 'other'; if (change === 'version') next.version = 4;
    if (change === 'dirty') next.dirty = true; if (change === 'busy') next.busy = true; if (change === 'authority') next.canEdit = false;
    view.rerender(<StoryboardDirectorCameraAdoption {...next} />); view.rerender(<StoryboardDirectorCameraAdoption {...original} />);
  }
  act(apply); expect(original.onChange).not.toHaveBeenCalled();
});

it('retires same-batch unchecked approval, consumes a fresh approval once and prevents undo over later edits', () => {
  const original = props(), view = render(<StoryboardDirectorCameraAdoption {...original} />); choose();
  const old = handler(panel().getByText('确认采用到分镜草稿（尚未保存）'));
  act(() => { fireEvent.click(panel().getByLabelText('采用景别')); old(); }); expect(original.onChange).not.toHaveBeenCalled();
  fireEvent.click(panel().getByLabelText('采用景别')); fireEvent.click(panel().getByText('预览采用导演摄影参数'));
  const apply = handler(panel().getByText('确认采用到分镜草稿（尚未保存）'));
  act(() => { apply(); apply(); }); expect(original.onChange).toHaveBeenCalledTimes(1);
  const after = original.onChange.mock.calls[0][0] as CreativeInput;
  view.rerender(<StoryboardDirectorCameraAdoption {...original} draft={after} dirty />);
  const undo = handler(panel().getByText('撤销本次导演摄影采用'));
  view.rerender(<StoryboardDirectorCameraAdoption {...original} draft={{ ...after, title: 'later edit' }} dirty />);
  view.rerender(<StoryboardDirectorCameraAdoption {...original} draft={after} dirty />);
  act(undo); expect(original.onChange).toHaveBeenCalledTimes(1);
});

it('caps selection at four and keeps read-only/busy source and preview controls disabled', () => {
  const original = props(), view = render(<StoryboardDirectorCameraAdoption {...original} />);
  fireEvent.change(panel().getByLabelText('采用摄影参数的原导演调度'), { target: { value: 'note' } });
  for (let i = 1; i <= 4; i++) fireEvent.click(panel().getByLabelText(`采用目标镜头 ${i} · shot${i}`));
  expect((panel().getByLabelText('采用目标镜头 5 · shot5') as HTMLInputElement).disabled).toBe(true);
  view.rerender(<StoryboardDirectorCameraAdoption {...original} busy />);
  expect((panel().getByLabelText('采用摄影参数的原导演调度') as HTMLSelectElement).disabled).toBe(true);
  view.rerender(<StoryboardDirectorCameraAdoption {...original} canEdit={false} />);
  expect((panel().getByText('预览采用导演摄影参数') as HTMLButtonElement).disabled).toBe(true);
  expect(original.onChange).not.toHaveBeenCalled();
});
