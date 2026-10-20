import { describe, expect, it, vi } from 'vitest';
import { studioProductionContracts } from './studioWorkspaceOperationContract';
import { createStudioWorkspaceOperationClient } from './studioWorkspaceOperationClient';
import { STUDIO_PRODUCTION_INTERFACE_KEYS, STUDIO_PRODUCTION_INTERFACE_REFERENCES } from './studioWorkspaceOperationTypes';

// Protocol fixtures only. These future checks do not provide product/runtime acceptance.
function fixture() {
  return {
    schema_version: 1, contract: 'studio-production-operation-contracts/1', project_id: 'studio-project',
    scope: { mode: 'local', novel_id: 'studio-project' }, studio_entry_kind: 'NEUTRAL_STUDIO',
    advisory_only: true, execution_authority: false, acceptance_sequence: ['M4', 'M5', 'M6', 'M7', 'M8', 'M9'],
    acceptance_evidence: 'NOT_EVALUATED_BY_THIS_ENDPOINT',
    interface_schemas: Object.fromEntries(STUDIO_PRODUCTION_INTERFACE_KEYS.map(key => [key,
      { type: 'object', additionalProperties: false, properties: {} }])),
    operations: [{
      id: 'm5.image.t2i', milestone: 'M5', title: '文字生成图片', capability_status: 'RESERVED_INTERFACE',
      acceptance_status: 'LOCAL_REQUIRED', acceptance_evidence: 'NOT_EVALUATED_BY_THIS_ENDPOINT',
      execution_available: false, blocked_reasons: ['V2_GRAPH_T2I_OWNER_NOT_CONNECTED'], owner: null, actions: [],
      input_requirements: ['明确输入'], source_requirements: ['精确来源版本'], output_requirements: ['真实产物'],
      review_requirements: ['人工审核'], limitations: ['原服务尚未接入'], interface_contracts: { ...STUDIO_PRODUCTION_INTERFACE_REFERENCES },
    }],
  };
}

describe('read-only production operation boundary', () => {
  it('rejects authority or acceptance promotion in a returned contract', () => {
    for (const patch of [{ execution_authority: true }, { advisory_only: false }, { acceptance_evidence: 'PASSED' }]) {
      expect(() => studioProductionContracts({ ...fixture(), ...patch }, 'studio-project')).toThrow();
    }
    const value = fixture(); Object.assign(value.operations[0], { execution_available: true });
    expect(() => studioProductionContracts(value, 'studio-project')).toThrow();
  });

  it('rejects foreign project/scope and private scope fields', () => {
    expect(() => studioProductionContracts(fixture(), 'other-project')).toThrow();
    const value = fixture(); Object.assign(value.scope, { branch_id: 'other-branch' });
    expect(() => studioProductionContracts(value, 'studio-project')).toThrow();
    const privateScope = fixture(); Object.assign(privateScope.scope, { principal_id: 'private-actor' });
    expect(() => studioProductionContracts(privateScope, 'studio-project')).toThrow();
  });

  it('rejects duplicate operation identities and a reserved operation advertising an action', () => {
    const duplicate = fixture(); duplicate.operations.push(structuredClone(duplicate.operations[0]));
    expect(() => studioProductionContracts(duplicate, 'studio-project')).toThrow();
    const advertised = fixture(); Object.assign(advertised.operations[0], { actions: [{
      id: 'execute', method: 'POST', path: '/api/never-execute', permission: 'domain.write', input_schema: null,
      owner_method: 'execute', requires_original_host_session: true, execution_grant: false, conditions: ['原服务检查'],
    }] });
    expect(() => studioProductionContracts(advertised, 'studio-project')).toThrow();
  });

  it('rejects missing schema contracts and wrong structured interface references', () => {
    const missing = fixture(); delete missing.interface_schemas['rights-requirements/1'];
    expect(() => studioProductionContracts(missing, 'studio-project')).toThrow();
    const wrong = fixture(); Object.assign(wrong.operations[0].interface_contracts, { result: 'other-contract/1' });
    expect(() => studioProductionContracts(wrong, 'studio-project')).toThrow();
  });

  it('the client exposes one GET and keeps descriptions nonexecuting', async () => {
    const json = vi.fn().mockResolvedValue(fixture());
    const client = createStudioWorkspaceOperationClient('studio-project', { json });
    const value = await client.read();
    expect(Object.keys(client)).toEqual(['read']);
    expect(json).toHaveBeenCalledTimes(1);
    expect(json).toHaveBeenCalledWith('/api/projects/studio-project/studio/production-contracts', 'GET', undefined, undefined);
    expect(value.execution_authority).toBe(false);
    expect(value.operations[0].execution_available).toBe(false);
  });

  it('matches the original collaboration resolver and rejects an unrelated captured project', async () => {
    const scope = { workspaceId: 'workspace', projectId: 'studio-project', storylineId: 'storyline', branchId: 'branch' };
    const value = { ...fixture(), scope: { mode: 'collaboration', novel_id: 'studio-project',
      workspace_id: scope.workspaceId, storyline_id: scope.storylineId, branch_id: scope.branchId } };
    const json = vi.fn().mockResolvedValue(value);
    const client = createStudioWorkspaceOperationClient('studio-project', { json }, scope);
    scope.branchId = 'changed-after-capture';
    expect((await client.read()).scope.branch_id).toBe('branch');
    const unrelatedTransport = vi.fn();
    const unrelated = createStudioWorkspaceOperationClient('studio-project', { json: unrelatedTransport }, { ...scope, projectId: 'other-project' });
    await expect(unrelated.read()).rejects.toThrow();
    expect(unrelatedTransport).not.toHaveBeenCalled();
    json.mockResolvedValue({ ...value, scope: { ...value.scope, project_id: 'unrelated-project' } });
    await expect(client.read()).rejects.toThrow();
  });
});
