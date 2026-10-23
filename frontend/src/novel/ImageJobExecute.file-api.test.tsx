// @vitest-environment jsdom
// Real File/API capture replay; provider-readiness response alone is a software
// fixture. The backend capture uses the original adapter and memory transport.
import {cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {afterEach, expect, it, vi} from 'vitest';
import capture from '../creative/fixtures/cloud-canvas-execute.file-api.json';
import {setCollaborationContext} from '../api';
import {bindLocalHostSession, useLocalHostSession} from '../localHostSession';
import {useStudio} from '../store';
import {ImageQueuePanel} from './ImageQueuePanel';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); setCollaborationContext({sessionToken: ''}); useLocalHostSession.setState({token: '', actorId: '', epoch: 0}); });
it('confirms the exact original File task and sends its captured CAS request once before reading completed state', async () => {
  localStorage.clear(); useStudio.setState({sessionToken: '', actor: undefined, scope: undefined, novelId: ''}); setCollaborationContext({sessionToken: ''});
  bindLocalHostSession('synthetic-protocol-browser', {session_mode: 'LOCAL_HOST', actor_id: 'synthetic-protocol-author'});
  const original = capture.queued.items[0], route = `/api/novels/${capture.project_id}/image-jobs`;
  let completed = false;
  const posts = vi.fn();
  const json = (value: unknown) => new Response(JSON.stringify(value), {headers: {'Content-Type': 'application/json'}});
  const fetcher = vi.fn(async (url: string, init: RequestInit = {}) => {
    if (url === route && (!init.method || init.method === 'GET')) return json(completed ? capture.completed : capture.queued);
    if (url === route + '?execution_confirmation=1') return json(capture.execution_capability);
    if (url === '/api/asset-providers') return json({items: [{provider_id: original.provider_id, default_model: original.model_id,
      api_style: 'automatic1111', configured: true, registered: true, reachable: true, enabled: true, local: true}]});
    if (url === `${route}/${capture.task_id}/execute` && init.method === 'POST') {
      const body = JSON.parse(String(init.body)); expect(body).toEqual(capture.confirmation);
      posts(body); completed = true; return json(capture.execute_response);
    }
    throw new Error('Unexpected captured execution protocol request');
  });
  vi.stubGlobal('fetch', fetcher);
  render(<ImageQueuePanel novelId={capture.project_id} draft={{provider_id: '', model_id: '', prompt: 'An unrelated unqueued draft'}}/>);
  fireEvent.click(await screen.findByRole('button', {name: '执行任务'}));
  const checkbox = await screen.findByRole('checkbox', {name: '我已核对任务、参数和可能费用'});
  expect(screen.getByLabelText('本次执行的原任务提示词')).toHaveProperty('value', original.prompt);
  expect(posts).not.toHaveBeenCalled(); fireEvent.click(checkbox);
  fireEvent.click(screen.getByRole('button', {name: '确认执行这一个任务'}));
  await screen.findByText('SUCCEEDED');
  await waitFor(() => expect(posts).toHaveBeenCalledTimes(1));
  expect(fetcher.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1);
  expect(capture.transport_calls).toBe(1);
  expect(capture.execute_response.approval_status).toBe('PENDING');
  expect(screen.queryByRole('img')).toBeNull();
});
