import {afterEach, expect, it, vi} from 'vitest';
import {api, setCollaborationContext} from '../api';

afterEach(() => {vi.unstubAllGlobals(); setCollaborationContext({sessionToken: ''});});

it('matches actual local Adaptation request pathnames without mistaking an empty query for another route', async () => {
  const fetcher = vi.fn().mockResolvedValue({ok: true, status: 200, json: async () => ({})});
  vi.stubGlobal('fetch', fetcher); setCollaborationContext({sessionToken: ''});
  await api.createAdaptationProposal('route-book', {target: 'COMMERCIAL', title: 'Synthetic', instruction: ''});
  await api.updateAdaptationBlueprint('route-book', 'proposal', {expected_revision: 1});
  await api.approveAdaptationProposal('route-book', 'proposal', undefined, 2);
  await api.materializeAdaptation('route-book', 'proposal', undefined, 3);
  await api.generateAdaptationDraft('route-book', 'proposal', 'task', {mode: 'deterministic', expected_revision: 4});
  await api.reviewAdaptationDraft('route-book', 'proposal', 'task', 'ACCEPTED', undefined, 5);
  await api.applyAdaptationDraft('route-book', 'proposal', 'task', undefined, 6);
  await api.adaptationAction('route-book', 'proposal', 'cancel', 7, undefined, 'task');
  await api.adaptationAction('route-book', 'proposal', 'recover', 8, undefined, 'task');
  const suffixes = ['', '/proposal/blueprint', '/proposal/approve', '/proposal/materialize', '/proposal/tasks/task/generate', '/proposal/tasks/task/review', '/proposal/tasks/task/apply', '/proposal/tasks/task/actions/cancel', '/proposal/tasks/task/actions/recover'];
  expect(fetcher).toHaveBeenCalledTimes(suffixes.length);
  for (const [index, suffix] of suffixes.entries()) {
    const [url, init] = fetcher.mock.calls[index];
    const pathname = '/api/novels/route-book/adaptations' + suffix;
    expect(url).toBe(pathname + '?');
    expect(url.endsWith(pathname)).toBe(false);
    expect(new URL(url, 'http://127.0.0.1:5207').pathname).toBe(pathname);
    expect(new URL(url, 'http://127.0.0.1:5207').searchParams.has('branch_id')).toBe(false);
    expect(init.method).toBe(index === 1 ? 'PUT' : 'POST');
  }
});
