// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { generationRecovery } from '../generationRecovery';
import { GenerationRecoveryPicker } from './GenerationRecoveryPicker';
afterEach(() => { cleanup(); sessionStorage.clear(); });
it('pages retained task identifiers five at a time and requires an explicit reopen', async () => {
  for (let index = 0; index < 12; index++) generationRecovery.save('picker', { chapterId: 'chapter', jobId: `task-${index}`, original: 'PRIVATE CACHED PROSE' });
  const onRecover = vi.fn().mockResolvedValue(undefined);
  render(<GenerationRecoveryPicker namespace="picker" chapterId="chapter" revision={1} onRecover={onRecover} />);
  expect(screen.getAllByRole('button', { name: '重新打开保留任务' })).toHaveLength(5);
  expect(screen.queryByText('PRIVATE CACHED PROSE')).toBeNull(); expect(onRecover).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '下一页' }));
  expect(screen.getByText('第 2 / 3 页')).toBeTruthy();
  fireEvent.click(screen.getAllByRole('button', { name: '重新打开保留任务' })[0]);
  await waitFor(() => expect(onRecover).toHaveBeenCalledOnce());
  expect(generationRecovery.history('picker', 'chapter')).toHaveLength(11);
});
it('does not list another actor or chapter candidates', () => {
  generationRecovery.save('picker', { chapterId: 'chapter', jobId: 'private-actor-task', actorId: 'other' });
  generationRecovery.save('picker', { chapterId: 'chapter', jobId: 'current', actorId: 'current' });
  generationRecovery.save('picker', { chapterId: 'other-chapter', jobId: 'private-chapter-task' });
  render(<GenerationRecoveryPicker namespace="picker" chapterId="chapter" actorId="current" revision={1} onRecover={vi.fn()} />);
  expect(screen.queryByRole('region', { name: '保留的生成任务' })).toBeNull();
  expect(screen.queryByText(/private-actor-task|private-chapter-task/)).toBeNull();
});
