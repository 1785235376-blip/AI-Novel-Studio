// @vitest-environment jsdom
// HTTP software fixtures over the real owner panel/client; no File or media execution claim.
import {act, cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {afterEach, beforeEach, expect, it, vi} from 'vitest';
import {setCollaborationContext} from '../api';
import {useLocalHostSession} from '../localHostSession';
import {useStudio} from '../store';
import {ImageQueuePanel} from './ImageQueuePanel';

const route = '/api/novels/project-readback/image-jobs';
const draft = {provider_id: 'fixture-local', model_id: 'fixture-model', prompt: 'Current authored prompt'};
const json = (value: unknown) => new Response(JSON.stringify(value), {headers: {'Content-Type': 'application/json'}});
const task = (status: 'QUEUED' | 'CANCELLED', id = 'server-original-task') => ({
  id, novel_id: 'project-readback', branch_id: null, status, approval_status: 'PENDING', attempt: 0,
  provider_id: 'fixture-local', model_id: 'fixture-model', prompt: `Saved prompt for ${id}`,
  parameters: {width: 768, height: 512, steps: 24, seed: 101}, allow_cloud_prompt: false,
});
const onlyOwnerReads = (fetcher: ReturnType<typeof vi.fn>, count: number) => {
  expect(fetcher).toHaveBeenCalledTimes(count);
  expect(fetcher.mock.calls.map(([url, init]) => [url, init?.method || 'GET']))
    .toEqual(Array.from({length: count}, () => [route, 'GET']));
};

beforeEach(() => {
  localStorage.clear();
  useStudio.setState({sessionToken: '', novelId: 'project-readback', actor: undefined, scope: undefined});
  useLocalHostSession.setState({token: '', actorId: '', epoch: 0});
  setCollaborationContext({sessionToken: ''});
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  setCollaborationContext({sessionToken: ''});
  useLocalHostSession.setState({token: '', actorId: '', epoch: 0});
});

it('reads the original owner status on mount, explicit refresh and complete reopen without writing', async () => {
  let status: 'QUEUED' | 'CANCELLED' = 'QUEUED';
  const fetcher = vi.fn(async () => json({items: [task(status)]}));
  vi.stubGlobal('fetch', fetcher);
  const first = render(<ImageQueuePanel novelId="project-readback" draft={draft} creationDisabled />);
  await screen.findByText('任务 ID：server-original-task');
  expect(screen.getByText('QUEUED')).toBeTruthy();

  status = 'CANCELLED';
  fireEvent.click(screen.getByRole('button', {name: '刷新任务'}));
  await screen.findByText('CANCELLED');
  expect(screen.queryByText('QUEUED')).toBeNull();
  first.unmount();

  render(<ImageQueuePanel novelId="project-readback" draft={draft} creationDisabled />);
  await screen.findByText('任务 ID：server-original-task');
  expect(screen.getByText('CANCELLED')).toBeTruthy();
  expect(screen.queryByText('QUEUED')).toBeNull();
  onlyOwnerReads(fetcher, 3);
});

it('focuses only the explicitly requested original task after the owner read', async () => {
  const fetcher = vi.fn(async () => json({items: [task('QUEUED', 'other-server-task'), task('CANCELLED')]}));
  vi.stubGlobal('fetch', fetcher);
  render(<ImageQueuePanel novelId="project-readback" draft={draft} requestedTaskId="server-original-task" creationDisabled />);

  const requested = (await screen.findByText('任务 ID：server-original-task')).closest('article');
  const other = screen.getByText('任务 ID：other-server-task').closest('article');
  await waitFor(() => expect(document.activeElement).toBe(requested));
  expect(requested?.getAttribute('aria-current')).toBe('true');
  expect(requested?.getAttribute('tabindex')).toBe('0');
  expect(other?.getAttribute('aria-current')).toBeNull();
  onlyOwnerReads(fetcher, 1);
});

it('keeps a newer explicit refresh when an older initial owner read returns later', async () => {
  let finishInitial!: (response: Response) => void;
  let reads = 0;
  const fetcher = vi.fn(() => ++reads === 1
    ? new Promise<Response>(resolve => {finishInitial = resolve;})
    : Promise.resolve(json({items: [task('CANCELLED')]})));
  vi.stubGlobal('fetch', fetcher);
  render(<ImageQueuePanel novelId="project-readback" draft={draft} creationDisabled />);
  await waitFor(() => expect(reads).toBe(1));

  fireEvent.click(screen.getByRole('button', {name: '刷新任务'}));
  await screen.findByText('CANCELLED');
  await act(async () => {finishInitial(json({items: [task('QUEUED')]}));});

  expect(screen.queryByText('QUEUED')).toBeNull();
  expect(screen.getByText('CANCELLED')).toBeTruthy();
  expect(screen.getByText('任务 ID：server-original-task')).toBeTruthy();
  onlyOwnerReads(fetcher, 2);
});
