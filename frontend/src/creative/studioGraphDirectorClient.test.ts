import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { fixtureProjection } from '../director/directorWorkspaceFixtures.testFixture';
import { createStudioGraphClient } from './studioGraphClient';

const project = 'project-1';
const snapshot = { id: 'doc-1', version: 3, digest: 'a'.repeat(64) };
const scope = { mode: 'local', novel_id: project };
const documents = () => ({ project_id: project, scope, documents: [{ ...snapshot, mode: 'DIRECTOR', title: 'Authored Director' }] });
const projection = () => {
  const value = fixtureProjection(); value.document.mode = 'DIRECTOR'; return value;
};
function setup() {
  const json = vi.fn().mockResolvedValueOnce(documents()).mockResolvedValueOnce(projection()).mockResolvedValueOnce(documents());
  return { json, client: createStudioGraphClient(project, {}, { json }) };
}

describe('Director Console graph pin reads use existing owners only', () => {
  it('checks the original version and digest before and after the decoded projection using GET only', async () => {
    const { client, json } = setup(), signal = new AbortController().signal;
    const result = await client.readDirectorWorkspace(snapshot, signal);
    expect(result.document).toEqual(projection().document);
    expect(json.mock.calls).toEqual([
      [`/api/projects/${project}/studio/graphs/planning-documents`, 'GET', undefined, signal],
      [`/api/projects/${project}/studio/director/workspace/${snapshot.id}`, 'GET', undefined, signal],
      [`/api/projects/${project}/studio/graphs/planning-documents`, 'GET', undefined, signal],
    ]);
  });

  it.each(['version', 'digest', 'mode'] as const)('rejects a changed source %s before exposing any projection', async field => {
    const { client, json } = setup(), changed = documents();
    if (field === 'version') changed.documents[0].version++;
    else changed.documents[0][field] = field === 'digest' ? 'b'.repeat(64) : 'STORYBOARD';
    json.mockReset().mockResolvedValue(changed);
    await expect(client.readDirectorWorkspace(snapshot)).rejects.toMatchObject({ status: 409, problem: { code: 'CREATIVE_GRAPH_PLANNING_DOCUMENT_CHANGED' } });
    expect(json).toHaveBeenCalledTimes(1);
  });

  it('refuses a source removed or hidden from the original planning catalog', async () => {
    const { client, json } = setup(); json.mockReset().mockResolvedValue({ ...documents(), documents: [] });
    await expect(client.readDirectorWorkspace(snapshot)).rejects.toMatchObject({ status: 404, problem: { code: 'STUDIO_GRAPH_DIRECTOR_UNAVAILABLE' } });
    expect(json).toHaveBeenCalledTimes(1);
  });

  it.each(['version', 'digest'] as const)('does not publish a projection when its source %s changes during the read', async field => {
    const { client, json } = setup(), changed = documents();
    if (field === 'version') changed.documents[0].version++; else changed.documents[0].digest = 'b'.repeat(64);
    json.mockReset().mockResolvedValueOnce(documents()).mockResolvedValueOnce(projection()).mockResolvedValueOnce(changed);
    await expect(client.readDirectorWorkspace(snapshot)).rejects.toMatchObject({ status: 409, problem: { code: 'CREATIVE_GRAPH_PLANNING_DOCUMENT_CHANGED' } });
    expect(json).toHaveBeenCalledTimes(3);
  });

  it.each(['project', 'branch'] as const)('rejects projection ownership mismatches for %s', async field => {
    const { client, json } = setup(), foreign = projection();
    if (field === 'project') foreign.project_id = 'other'; else foreign.scope.branch_id = 'foreign-branch';
    json.mockReset().mockResolvedValueOnce(documents()).mockResolvedValueOnce(foreign);
    await expect(client.readDirectorWorkspace(snapshot)).rejects.toMatchObject({ status: 403, problem: { code: 'STUDIO_RESPONSE_SCOPE_MISMATCH' } });
    expect(json).toHaveBeenCalledTimes(2);
  });

  it.each(['version', 'mode'] as const)('refuses a projection with a different %s', async field => {
    const { client, json } = setup(), changed = projection();
    if (field === 'version') changed.document.version++; else changed.document.mode = 'STORYBOARD';
    json.mockReset().mockResolvedValueOnce(documents()).mockResolvedValueOnce(changed);
    await expect(client.readDirectorWorkspace(snapshot)).rejects.toMatchObject({ status: 409, problem: { code: 'CREATIVE_GRAPH_PLANNING_DOCUMENT_CHANGED' } });
    expect(json).toHaveBeenCalledTimes(2);
  });

  it('preserves exact authority denials during the final binding recheck', async () => {
    const { client, json } = setup();
    const denial = new ApiError({ status: 403, code: 'PROJECT_SCOPE_FORBIDDEN', message: 'Denied by original owner.' });
    json.mockReset().mockResolvedValueOnce(documents()).mockResolvedValueOnce(projection()).mockRejectedValueOnce(denial);
    await expect(client.readDirectorWorkspace(snapshot)).rejects.toBe(denial);
  });

  it('checks the captured collaboration scope on every original-owner read', async () => {
    const collaboration = { workspaceId: 'w', projectId: project, storylineId: 's', branchId: 'b' };
    const ownerScope = { mode: 'collaboration', novel_id: project, workspace_id: 'w', storyline_id: 's', branch_id: 'b' };
    const value = { ...projection(), scope: ownerScope };
    const catalog = { ...documents(), scope: ownerScope };
    const json = vi.fn().mockResolvedValueOnce(catalog).mockResolvedValueOnce(value).mockResolvedValueOnce(catalog);
    const client = createStudioGraphClient(project, { scope: collaboration }, { json });
    collaboration.branchId = 'changed-after-capture';
    expect((await client.readDirectorWorkspace(snapshot)).scope.branch_id).toBe('b');
  });

  it('does not start transport after an aborted read or malformed pin', async () => {
    const { client, json } = setup(), abort = new AbortController(); abort.abort();
    await expect(client.readDirectorWorkspace(snapshot, abort.signal)).rejects.toMatchObject({ name: 'AbortError' });
    await expect(client.readDirectorWorkspace({ ...snapshot, digest: 'invalid' })).rejects.toMatchObject({ problem: { code: 'STUDIO_GRAPH_INPUT_INVALID' } });
    expect(json).not.toHaveBeenCalled();
  });
});
