// @vitest-environment jsdom
import { useState } from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { CreativeCanvas } from './CreativeCanvas';
import { documentInput, newDocument, newScene, newShot, type CreativeInput } from './types';
afterEach(cleanup);
function Harness({ initial, editable = true, onChange = vi.fn() }: { initial: CreativeInput; editable?: boolean; onChange?: (value: CreativeInput) => void }) {
  const [draft, setDraft] = useState(initial), [scene, selectScene] = useState(initial.scenes[0]?.id), [shot, selectShot] = useState(initial.shots[0]?.id);
  return <CreativeCanvas draft={draft} canEdit={editable} busy={false} dirty={true} selectedSceneId={scene} selectedShotId={shot} onScene={selectScene} onShot={selectShot} onChange={value => { setDraft(value); onChange(value); }} onSave={vi.fn()} onNew={vi.fn()} />;
}
describe('Original CreativeCanvas Director and Storyboard extensions', () => {
  it('stores visual goals and rich performance only when authored, with legacy fields omitted', () => {
    const initial = { ...newDocument('DIRECTOR'), title: 'Synthetic Director', source_independent: true, scenes: [{ ...newScene(1), id: 'scene' }], director_notes: [{ id: 'note', number: 1, scene_id: 'scene', note: '', blocking: '', shot_size: '', camera_angle: '', camera_motion: '', duration_seconds: 5, emotion: '', pacing: '', performance: '' }] };
    expect(documentInput(initial).visual_target).toBeUndefined(); const changed = vi.fn(); render(<Harness initial={initial} onChange={changed} />);
    fireEvent.change(screen.getByLabelText('视觉风格'), { target: { value: 'quiet cinematic' } });
    fireEvent.click(screen.getByRole('button', { name: '添加角色表演' })); fireEvent.change(screen.getByLabelText('表演 1 角色'), { target: { value: 'synthetic-character' } });
    fireEvent.change(screen.getByLabelText('表演 1 表情'), { target: { value: 'restrained' } });
    const current = changed.mock.calls.at(-1)![0]; expect(current.visual_target.style).toBe('quiet cinematic'); expect(current.director_notes[0].performances[0].expression).toBe('restrained');
    expect(current.shots).toHaveLength(0); expect(current.scenes[0].action).toBe(initial.scenes[0].action);
  });
  it('switches shot cards/list and previews original stable identities, character and emotion', () => {
    const scene = { ...newScene(1), id: 'scene', heading: 'Synthetic Scene' }, shot = { ...newShot(1, 'scene'), id: 'stable-shot', frame_prompt: 'Synthetic frame', characters: ['character'], emotion: 'calm', sound: 'quiet room' };
    const initial = { ...newDocument('STORYBOARD'), title: 'Synthetic Storyboard', source_independent: true, scenes: [scene], shots: [shot] }, changed = vi.fn();
    render(<Harness initial={initial} onChange={changed} />); fireEvent.click(screen.getByRole('button', { name: '镜头列表' }));
    expect(screen.getByRole('button', { name: '镜头列表' }).getAttribute('aria-pressed')).toBe('true'); expect(screen.getByRole('region', { name: '选中镜头预览' }).textContent).toContain('stable-shot');
    fireEvent.change(screen.getByLabelText('镜头情绪'), { target: { value: 'tense' } }); expect(changed.mock.calls.at(-1)![0].shots[0]).toMatchObject({ id: 'stable-shot', emotion: 'tense', characters: ['character'] });
  });
  it('keeps original read-only fieldset for added goal and shot fields', () => {
    const initial = { ...newDocument('STORYBOARD'), title: 'Read-only', source_independent: true, scenes: [newScene(1)], shots: [] };
    render(<Harness initial={initial} editable={false} />); expect(screen.getByLabelText('视觉风格').closest('fieldset')?.disabled).toBe(true);
  });
});
