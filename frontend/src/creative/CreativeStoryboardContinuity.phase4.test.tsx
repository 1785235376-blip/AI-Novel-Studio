// @vitest-environment jsdom
import { useState } from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { CreativeCanvas } from './CreativeCanvas';
import { documentInput, newDocument, newScene, newShot, type CreativeInput } from './types';
afterEach(cleanup);
function Harness({ initial, changed, editable = true }: { initial: CreativeInput; changed: (value: CreativeInput) => void; editable?: boolean }) { const [value, setValue] = useState(initial); return <CreativeCanvas draft={value} canEdit={editable} busy={false} dirty={true} selectedShotId="shot-1" onShot={vi.fn()} onScene={vi.fn()} onChange={next => { setValue(next); changed(next); }} onSave={vi.fn()} onNew={vi.fn()} />; }
const initial = () => ({ ...newDocument('STORYBOARD'), title: 'Synthetic continuity', source_independent: true, scenes: [{ ...newScene(1), id: 'scene' }], shots: [{ ...newShot(1, 'scene'), id: 'shot-1' }, { ...newShot(2, 'scene'), id: 'shot-2' }] });
describe('Original shot editor preserves authored identity and independent continuity', () => {
  it('offers adjacent shots and matching-scene notes, retaining invalid pins until explicitly cleared', () => { const changed = vi.fn(), value = initial(); value.shots.push({ ...newShot(3, 'scene'), id: 'shot-3' }); const authored = { ...value, director_notes: [{ id: 'other-scene-note', scene_id: 'other-scene', number: 1, note: '', blocking: '', shot_size: '', camera_angle: '', camera_motion: '', duration_seconds: 5, emotion: '', pacing: '', performance: '' }], shots: value.shots.map((shot, index) => index ? shot : { ...shot, continuity: { next_shot_id: 'shot-3', characters: 'retain character continuity', outfit: '', environment: '', camera: '' }, director_note_ids: ['other-scene-note'] }) };
    render(<Harness initial={authored} changed={changed} />); const next = screen.getByLabelText('后接镜头') as HTMLSelectElement;
    expect(Array.from(next.options).filter(option => !option.disabled).map(option => option.value)).toEqual(['', 'shot-2']); expect(next.value).toBe('shot-3'); expect(screen.queryByRole('checkbox', { name: /other-scene-note/ })).toBeNull();
    expect((screen.getByRole('button', { name: '后移镜头 1' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: '清除前后镜头关系，保留连续性文字' })); expect(changed.mock.calls.at(-1)![0].shots[0].continuity).toEqual({ characters: 'retain character continuity', outfit: '', environment: '', camera: '' });
    expect((screen.getByRole('button', { name: '后移镜头 1' }) as HTMLButtonElement).disabled).toBe(false);
  });
  it('adds explicit next shot and continuity fields without changing IDs or creating production', () => { const changed = vi.fn(); render(<Harness initial={initial()} changed={changed} />);
    fireEvent.change(screen.getByLabelText('后接镜头'), { target: { value: 'shot-2' } }); fireEvent.change(screen.getByLabelText('服装连续性'), { target: { value: 'same jacket' } });
    expect(changed.mock.calls.at(-1)![0].shots[0]).toMatchObject({ id: 'shot-1', continuity: { next_shot_id: 'shot-2', outfit: 'same jacket' } });
    expect((screen.getByLabelText('后接镜头') as HTMLSelectElement).options.length).toBe(2); expect((screen.getByLabelText('摄影机连续性') as HTMLTextAreaElement).maxLength).toBe(4000);
    fireEvent.click(screen.getByRole('button', { name: '清除连续性要求' })); expect(changed.mock.calls.at(-1)![0].shots[0].continuity).toBeUndefined();
  });
  it('omits unconfigured continuity and preserves read-only original fieldset', () => { const value = initial(); expect(documentInput(value).shots[0].continuity).toBeUndefined(); render(<Harness initial={value} changed={vi.fn()} editable={false} />); expect(screen.getByLabelText('人物连续性').closest('fieldset')?.disabled).toBe(true); });
  it('edits Director camera, material and transition only in original notes', () => { const changed = vi.fn(), value = { ...newDocument('DIRECTOR'), title: 'Synthetic direction', source_independent: true, scenes: [{ ...newScene(1), id: 'scene' }], director_notes: [{ id: 'note', number: 1, scene_id: 'scene', note: '', blocking: '', shot_size: '', camera_angle: '', camera_motion: '', duration_seconds: 5, emotion: '', pacing: '', performance: '' }] }; render(<Harness initial={value} changed={changed} />);
    fireEvent.change(screen.getByLabelText('导演灯光'), { target: { value: 'soft side light' } }); fireEvent.change(screen.getByLabelText('节奏与转场'), { target: { value: 'slow dissolve' } });
    expect(changed.mock.calls.at(-1)![0].director_notes[0]).toMatchObject({ id: 'note', lighting: 'soft side light', transition: 'slow dissolve' }); expect(changed.mock.calls.at(-1)![0].shots).toEqual([]);
  });
});
