import { afterEach, expect, it, vi } from 'vitest';
import { api, setCollaborationContext } from '../api';
afterEach(() => { vi.unstubAllGlobals(); setCollaborationContext({ sessionToken: '' }); });
it('uses explicit admin authority across awaits even after the global context changes', async () => {
  const fetchMock = vi.fn(async () => ({ ok: true, status: 200, json: async () => ({ id: 'project', eligible_paths: [] }) }));
  vi.stubGlobal('fetch', fetchMock);
  const captured = { sessionToken: 'original-session' };
  setCollaborationContext({ sessionToken: 'original-session' });
  await api.adminCreateProject('workspace', 'Blank project', '', captured);
  setCollaborationContext({ sessionToken: 'later-session', scope: { workspaceId: 'elsewhere', projectId: 'different-project', storylineId: 's', branchId: 'later-branch' } });
  await api.adminWorkspaceNavigation('workspace', captured);
  expect(fetchMock).toHaveBeenCalledTimes(2);
  for (const [, init] of fetchMock.mock.calls as unknown as [string, RequestInit][]) {
    expect(init.headers).toMatchObject({ 'X-Session-Token': 'original-session' });
    expect(init.headers).not.toHaveProperty('X-Branch-Id');
  }
});
