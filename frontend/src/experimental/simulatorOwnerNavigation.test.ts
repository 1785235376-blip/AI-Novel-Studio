import { describe, expect, it, vi } from 'vitest';
import { simulatorOwnerNavigation, simulatorOwnerTarget } from './simulatorOwnerNavigation';
import type { WorkspaceNavigation } from './uxClient';

describe('simulator origin navigation adapter', () => {
  it('adds planning authority at the host without mutating the legacy child payload', () => {
    const child: WorkspaceNavigation = { kind: 'feature', id: 'proposal-one', feature: 'advanced_planning_v2' };
    const navigate = vi.fn(); simulatorOwnerNavigation(navigate)(child);
    expect(navigate).toHaveBeenCalledWith({ ...child, task_authority: 'planning_proposal' });
    expect(Object.keys(child)).toEqual(['kind', 'id', 'feature']);
  });
  it.each(['chapter', 'generation', 'feature'] as const)('does not infer authority for unrelated %s targets', kind => {
    const target: WorkspaceNavigation = { kind, id: 'original', feature: kind === 'feature' ? 'history' : undefined };
    expect(simulatorOwnerTarget(target)).toBe(target);
  });
  it('fails closed for a malformed non-string proposal ID', () => {
    expect(simulatorOwnerTarget({ kind: 'feature', id: 42, feature: 'advanced_planning_v2' } as unknown as WorkspaceNavigation)).toBeUndefined();
  });
  it.each(['', ' ', ' padded ', 'bad task', 'https://wrong.example/proposal', 'x'.repeat(241), 'other-owner'])('refuses empty identifiers or contradictory ownership (%s)', value => {
    const navigate = vi.fn();
    simulatorOwnerNavigation(navigate)({ kind: 'feature', id: value === 'other-owner' ? 'proposal-one' : value,
      feature: 'advanced_planning_v2', ...(value === 'other-owner' ? { task_authority: value } : {}) });
    expect(navigate).not.toHaveBeenCalled();
  });
});
