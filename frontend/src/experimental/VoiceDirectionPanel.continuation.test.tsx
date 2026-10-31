// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import type { ExperimentalClient, Row } from './api';
import { VoiceDirectionPanel } from './VoiceDirectionPanel';
function client(job: Row) {
  return { get: vi.fn(async (path: string) => path.endsWith('/catalog') ? { plans: [], profiles: [], characters: [], tts: {} } : { items: [job] }),
    post: vi.fn(async () => job) } as unknown as ExperimentalClient;
}
afterEach(() => cleanup());
it('locates a current voice job without automatically executing or retrying', async () => {
  const api = client({ id: 'voice-job', version: 1, status: 'QUEUED' });
  render(<VoiceDirectionPanel client={api} requestedTaskId="voice-job" />);
  await screen.findByText('已定位任务中心请求的原声音任务。');
  expect(screen.getByRole('article', { name: '声音任务 voice-job' }).getAttribute('aria-current')).toBe('true');
  expect(api.post).not.toHaveBeenCalled();
});
it('keeps cancellation usable while a local TTS execution awaits its result', async () => {
  const job = { id: 'voice-job', version: 1, status: 'QUEUED' }; const api = client(job); let finish!: (value: Row) => void;
  vi.mocked(api.post).mockImplementation(async path => {
    if (path.endsWith('/execute')) { job.status = 'RUNNING'; return new Promise(resolve => { finish = resolve; }); }
    job.status = 'CANCELLED'; return job;
  });
  render(<VoiceDirectionPanel client={api} />);
  fireEvent.click(await screen.findByRole('button', { name: '执行此片段' }));
  await waitFor(() => expect(job.status).toBe('RUNNING'));
  const cancel = screen.getByRole('button', { name: '取消片段任务' }); expect(cancel.hasAttribute('disabled')).toBe(false);
  fireEvent.click(cancel);
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/voice-direction/jobs/voice-job/cancel', {}));
  finish(job); await screen.findByRole('button', { name: '重新排队' });
  expect(screen.queryByRole('button', { name: '批准此音频资产' })).toBeNull();
});
it('permits owner cancellation of a stale running job but disables execution and result review', async () => {
  const api = client({ id: 'stale-job', version: 1, status: 'RUNNING', stale: true });
  render(<VoiceDirectionPanel client={api} requestedTaskId="missing" />);
  await screen.findByText('请求的声音任务在当前项目、分支或权限下不可用。');
  expect(screen.getByRole('button', { name: '取消片段任务' }).hasAttribute('disabled')).toBe(false);
  expect(screen.queryByRole('button', { name: '执行此片段' })).toBeNull();
  expect(screen.queryByRole('button', { name: '批准此音频资产' })).toBeNull();
  expect(api.post).not.toHaveBeenCalled();
});
