// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { bindMotionTaskToDirector } from './ScreenplayPanel';

describe('Motion Task director binding', () => {
  beforeEach(() => { localStorage.clear(); });
  it('persists a scoped selection and broadcasts it', () => {
    const listener = vi.fn();
    window.addEventListener('multimodal-motion-binding', listener);
    bindMotionTaskToDirector('novel-a', 'screenplay-1', 'task-9');
    expect(JSON.parse(localStorage.getItem('multimodal-selected-motion:novel-a') || '{}')).toEqual({ screenplay_id: 'screenplay-1', motion_task_id: 'task-9' });
    expect(listener).toHaveBeenCalledTimes(1);
    expect((listener.mock.calls[0][0] as CustomEvent).detail).toMatchObject({ novelId: 'novel-a', motion_task_id: 'task-9' });
    window.removeEventListener('multimodal-motion-binding', listener);
  });
  it('does not overwrite another novel workspace', () => {
    localStorage.setItem('multimodal-selected-motion:novel-b', JSON.stringify({ screenplay_id: 'old', motion_task_id: 'old-task' }));
    bindMotionTaskToDirector('novel-a', 'screenplay-1', 'task-9');
    expect(localStorage.getItem('multimodal-selected-motion:novel-b')).toContain('old-task');
  });
});
