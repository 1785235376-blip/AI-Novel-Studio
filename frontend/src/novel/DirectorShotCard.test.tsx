// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { DirectorShotCard } from './DirectorShotCard';

vi.mock('../api', () => ({ api: { synthesizeDirectorShotDialogue: vi.fn().mockResolvedValue({ audio_uri: 'audio://shot-1' }), motionFrameHistory: vi.fn().mockResolvedValue({ history: [{ changed_at: '2026-08-25T08:00:00Z' }] }) } }));

describe('DirectorShotCard', () => {
  beforeEach(() => cleanup());
  const shot = { shot_id: 'shot-1', name: '镜头 01', duration: '4s', camera: '推进', action: '抬头', dialogue: '快走！', voice: 'hero', emotion: 'urgent' };
  it('keeps voice generation disabled until voice and dialogue exist', () => {
    render(<DirectorShotCard shot={{ ...shot, voice: '' }} index={0} profiles={[]} onChange={vi.fn()} />);
    expect(screen.getByText('生成配音')).toHaveProperty('disabled', true);
  });
  it('renders audio preview after explicit generation', async () => {
    render(<DirectorShotCard shot={shot} index={0} profiles={[]} onChange={vi.fn()} />);
    fireEvent.click(screen.getAllByText('生成配音').find(el => !(el as HTMLButtonElement).disabled)!);
    await waitFor(() => expect(screen.getByRole('button', { name: '生成配音' })).toBeTruthy());
    expect(document.querySelector('audio')?.getAttribute('src')).toBe('audio://shot-1');
  });
  it('renders all voice controls for narrow layouts', () => {
    render(<DirectorShotCard shot={shot} index={0} profiles={[]} onChange={vi.fn()} />);
    expect(screen.getByLabelText('镜头对白')).toBeTruthy();
    expect(screen.getByLabelText('镜头字幕')).toBeTruthy();
    expect(screen.getByLabelText('镜头声音')).toBeTruthy();
    expect(screen.getByLabelText('镜头情绪')).toBeTruthy();
  });
  it('requires an explicit target shot before applying a broadcast task', async () => {
    const onChange = vi.fn();
    render(<DirectorShotCard shot={shot} index={0} profiles={[]} novelId="novel-1" onChange={onChange} />);
    window.dispatchEvent(new CustomEvent('multimodal-motion-binding', { detail: { novelId: 'novel-1', screenplay_id: 'script-1', motion_task_id: 'task-1' } }));
    fireEvent.click(await screen.findByRole('button', { name: '绑定所选视频任务' }));
    await waitFor(() => expect(onChange).toHaveBeenCalledWith(0, { screenplay_id: 'script-1', motion_task_id: 'task-1', binding_source: 'manual' }));
  });
});
