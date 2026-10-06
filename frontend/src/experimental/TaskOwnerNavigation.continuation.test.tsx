// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ImportPanel } from './ImportPanel';
import { TeamsPanel } from './TeamsPanel';
import { InboxPanel } from './InboxPanel';
import { experimentalClient } from './api';
import { WorkflowPanel } from '../novel/WorkflowPanel';
import { api } from '../api';
import { useStudio } from '../store';
const response = (data: unknown) => new Response(JSON.stringify(data), { status: 200 });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
it('reopens requested import ID instead of default first job, and rejects missing targets', async () => {
  const fetch = vi.fn(async (url: string) => response(url.endsWith('/imports/jobs') ? { items: [{ id: 'first', version: 1, status: 'QUEUED' }, { id: 'exact', version: 2, status: 'CANCELLED' }] } : { items: [] }));
  vi.stubGlobal('fetch', fetch); const client = experimentalClient('n', { sessionToken: 'owner' });
  const view = render(<ImportPanel client={client} requestedTaskId="exact" />);
  await waitFor(() => expect((screen.getByLabelText('导入任务') as HTMLSelectElement).value).toBe('exact'));
  expect(fetch.mock.calls.some(([url]) => url.endsWith('/imports/jobs/exact/chunks'))).toBe(true);
  view.rerender(<ImportPanel client={client} requestedTaskId="missing" />);
  await screen.findByText('请求的原导入任务当前不可读或已移除；未改选其他任务。');
  expect(screen.queryByRole('region', { name: '导入任务状态' })).toBeNull();
});
it('focuses the original team run without an execute request', async () => {
  const fetch = vi.fn(async (url: string) => response(url.endsWith('/teams/catalog') ? { roles: [], recipes: [] } : { items: [{ id: 'exact-team', version: 1, status: 'QUEUED', recipe_id: 'fixture' }] }));
  vi.stubGlobal('fetch', fetch);
  render(<TeamsPanel client={experimentalClient('n', { sessionToken: '' })} requestedTaskId="exact-team" />);
  const card = await screen.findByRole('article', { name: '团队任务 fixture' });
  expect(card.getAttribute('aria-current')).toBe('true'); expect(document.activeElement).toBe(card);
  expect(fetch.mock.calls.every(([url]) => !url.includes('/execute'))).toBe(true);
});
it('binds review navigation to both domain and record ID', async () => {
  const fetch = vi.fn(async () => response({ items: [{ id: 'same', domain: 'media', version: 1, status: 'REVIEW', preview: 'Exact media review', allowed_actions: [] }, { id: 'same', domain: 'planning', version: 1, status: 'REVIEW', preview: 'Other review', allowed_actions: [] }] }));
  vi.stubGlobal('fetch', fetch);
  render(<InboxPanel client={experimentalClient('n', { sessionToken: '' })} requestedItemId="same" requestedDomain="media" />);
  const card = await screen.findByRole('article', { name: '审核项 media Exact media review' });
  expect(card.getAttribute('aria-current')).toBe('true');
  expect(screen.getByRole('article', { name: '审核项 planning Other review' }).getAttribute('aria-current')).toBeNull();
  expect(fetch.mock.calls.length).toBeGreaterThan(0);
});
it('reads requested original workflow runs and focuses the exact run without resuming it', async () => {
  useStudio.getState().setCollaboration('');
  vi.spyOn(api, 'workflows').mockResolvedValue({ items: [{ id: 'wf', title: 'Original workflow', nodes: [] }] });
  const read = vi.spyOn(api, 'workflowRuns').mockResolvedValue({ items: [{ id: 'exact-run', workflow_id: 'wf', status: 'PAUSED', node_states: {} }] });
  const resume = vi.spyOn(api, 'resumeWorkflow');
  render(<WorkflowPanel novelId="n" requestedWorkflowId="wf" requestedRunId="exact-run" />);
  const card = await screen.findByText('运行 exact-run · PAUSED');
  expect(card.getAttribute('aria-current')).toBe('true'); expect(read).toHaveBeenCalledWith('wf'); expect(resume).not.toHaveBeenCalled();
});
