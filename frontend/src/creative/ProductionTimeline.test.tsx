// @vitest-environment jsdom
import { useState } from 'react';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ProductionTimeline } from './ProductionTimeline';
import { newDocument, newScene, newShot, type CreativeInput } from './types';

afterEach(cleanup);
function production(): CreativeInput {
  const scene = { ...newScene(1), id: 'scene-1' };
  const shots = [3, 7, 5].map((duration, index) => ({ ...newShot(index + 1, scene.id), id: `shot-${index + 1}`, duration_seconds: duration }));
  const draft = newDocument('PRODUCTION');
  return { ...draft, scenes: [scene], shots, video_plan: { ...draft.video_plan!, segments: shots.map(shot => ({ shot_id: shot.id, duration_seconds: shot.duration_seconds, note: `keep-${shot.id}` })) } };
}

describe('production timeline structured planning', () => {
  it('reorders full segments without changing shot identity, timing, or notes', () => {
    const original = production(), changed = vi.fn();
    function Harness() { const [draft, setDraft] = useState(original); return <ProductionTimeline draft={draft} editable onChange={value => { changed(value); setDraft(value); }} onShot={() => {}} />; }
    render(<Harness />);
    fireEvent.click(screen.getByRole('button', { name: '后移第 1 段' }));
    expect(changed.mock.calls[0][0].video_plan.segments).toEqual([original.video_plan!.segments[1], original.video_plan!.segments[0], original.video_plan!.segments[2]]);
    expect(changed.mock.calls[0][0].shots).toEqual(original.shots);
    const clips = screen.getAllByRole('listitem');
    expect(within(clips[0]).getByText('镜头 2')).toBeTruthy(); expect(within(clips[0]).getByText('0s → 7s')).toBeTruthy();
    expect(within(clips[1]).getByText('7s → 10s')).toBeTruthy();
    expect(screen.getByText('3 段 · 15s')).toBeTruthy();
    expect((screen.getByRole('button', { name: '前移第 1 段' }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole('button', { name: '后移第 3 段' }) as HTMLButtonElement).disabled).toBe(true);
    expect(original.video_plan!.segments.map(row => row.shot_id)).toEqual(['shot-1', 'shot-2', 'shot-3']);
  });

  it('selects shots, edits segment duration, and removes only the requested occurrence', () => {
    const draft = production(), changed = vi.fn(), selected = vi.fn();
    render(<ProductionTimeline draft={draft} editable onChange={changed} onShot={selected} />);
    fireEvent.click(screen.getByRole('button', { name: /0s → 3s 镜头 1 3s/ }));
    expect(selected).toHaveBeenCalledWith('shot-1');
    fireEvent.change(screen.getByLabelText('第 2 段时长'), { target: { value: '9' } });
    expect(changed.mock.calls[0][0].video_plan.segments[1]).toEqual({ ...draft.video_plan!.segments[1], duration_seconds: 9 });
    fireEvent.click(screen.getByRole('button', { name: '移除第 2 段' }));
    expect(changed.mock.calls[1][0].video_plan.segments.map((row: { shot_id: string }) => row.shot_id)).toEqual(['shot-1', 'shot-3']);
  });

  it('keeps read-only timeline mutations disabled while permitting inspection', () => {
    const changed = vi.fn(), selected = vi.fn();
    render(<ProductionTimeline draft={production()} editable={false} onChange={changed} onShot={selected} />);
    fireEvent.click(screen.getByRole('button', { name: '后移第 1 段' }));
    fireEvent.change(screen.getByLabelText('第 2 段时长'), { target: { value: '9' } });
    expect(changed).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: /0s → 3s 镜头 1 3s/ }));
    expect(selected).toHaveBeenCalledWith('shot-1');
    expect(screen.getByText('结构化计划 · 尚未渲染媒体')).toBeTruthy();
  });

  it('shows an honest empty state and no fake generated media', () => {
    render(<ProductionTimeline draft={newDocument('PRODUCTION')} editable onChange={() => {}} onShot={() => {}} />);
    expect(screen.getByText('尚无制作片段')).toBeTruthy();
    expect(screen.getByText(/编排不会调用媒体生成或剪辑服务/)).toBeTruthy();
    expect(screen.queryAllByRole('listitem')).toHaveLength(0);
  });
});
