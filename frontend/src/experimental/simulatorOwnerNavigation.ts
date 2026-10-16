import type { WorkspaceNavigation } from './uxClient';

/** Only the simulator host can identify its saved planning-proposal links. */
export function simulatorOwnerTarget(target: WorkspaceNavigation): WorkspaceNavigation | undefined {
  if (target.kind !== 'feature' || target.feature !== 'advanced_planning_v2') return target;
  if (typeof target.id !== 'string' || !target.id || target.id.length > 240 || target.id !== target.id.trim() || /[\u0000-\u0020\u007f]/.test(target.id) || target.id.includes('://')
    || (target.task_authority !== undefined && target.task_authority !== 'planning_proposal')) return undefined;
  return { ...target, task_authority: 'planning_proposal' };
}

export function simulatorOwnerNavigation(onNavigate: (target: WorkspaceNavigation) => void) {
  return (target: WorkspaceNavigation) => {
    const owned = simulatorOwnerTarget(target);
    if (owned) onNavigate(owned);
  };
}
