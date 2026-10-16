import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { studioClient } from './studioClient';
import { useLocalHostSession } from '../localHostSession';
vi.mock('../packagedHost', () => ({ isPackagedDesktopHost: () => false }));
const project = { id: 'new-project', title: 'New project', entry_kind: 'NEUTRAL_STUDIO' };
const context = { sessionToken: 'original', scope: { workspaceId: 'w', projectId: project.id, storylineId: 's', branchId: 'b' } };
const preferences = { version: 0, intents: [], preset: 'BLANK', custom_intent: '' };
let fetchMock: ReturnType<typeof vi.fn>;
beforeEach(() => { useLocalHostSession.setState({ token: '', actorId: '' }); fetchMock = vi.fn(); vi.stubGlobal('fetch', fetchMock); });
afterEach(() => { vi.unstubAllGlobals(); useLocalHostSession.setState({ token: '', actorId: '' }); });
function reply(value: unknown, status = 200) { fetchMock.mockResolvedValue({ ok: status === 200, status, json: async () => value }); }
describe('activation acknowledgement is separate from workspace state', () => {
  it('accepts exact project-only activation without manufacturing preferences or permission', async () => {
    reply({ project });
    const result = await studioClient(project.id, context).activate();
    expect(result).toEqual({ project });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe('/api/projects/new-project/studio/activate');
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: 'POST', headers: { 'X-Session-Token': 'original', 'X-Branch-Id': 'b' } });
  });
  it('does not forward capabilities or private unknown metadata from an activation receipt', async () => {
    reply({ project: { ...project, private_note: 'CANARY' }, preferences, capabilities: { can_mutate: true }, private_note: 'CANARY' });
    expect(await studioClient(project.id, context).activate()).toEqual({ project });
  });
  it('continues to require real preferences when reading a full overview', async () => {
    reply({ project });
    await expect(studioClient(project.id, context).overview()).rejects.toMatchObject({ problem: { code: 'STUDIO_RESPONSE_INVALID' } });
  });
  it.each([null, undefined, {}, { ...preferences, version: -1 }, { ...preferences, preset: 'FORGED' }])('rejects malformed preferences when explicitly included: %s', async value => {
    reply({ project, preferences: value });
    await expect(studioClient(project.id, context).activate()).rejects.toBeInstanceOf(Error);
  });
  it.each([null, {}, { ...project, id: 'other' }, { ...project, entry_kind: 'LEGACY' }, { ...project, title: 7 }, Object.create(project)])('rejects invalid or inherited project acknowledgement: %s', async value => {
    reply({ project: value });
    await expect(studioClient(project.id, context).activate()).rejects.toBeInstanceOf(Error);
  });
  it.each([401, 403, 404])('keeps server permission rejection %s', async status => {
    reply({ project }, status);
    await expect(studioClient(project.id, context).activate()).rejects.toMatchObject({ status });
  });
});
