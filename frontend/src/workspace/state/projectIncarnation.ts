// [HERMIA-FE-CONTRACTS G-PURGE-1 incarnation] The backend overview (GET /api/projects/{id}/studio) now carries
// project.incarnation. A DIFFERENT incarnation for the same (user, project id) means the id was reused by a new project:
// purge only this user's own UI geometry for it (same rules as projectPurge). A failed/404/500 overview is never deletion,
// an unknown/invalid value is never evidence, and no identity (仅本次会话) never reads or writes the ledger.
import {purgeProjectGeometry, type PurgeStorage} from './projectPurge';

export interface IncarnationStorage extends PurgeStorage { getItem(k: string): string | null; setItem(k: string, v: string): void; }
export type IncarnationObservation = {kind: 'first' | 'same' | 'changed' | 'skipped'; purged?: string[]};

// Deliberately NOT matched by projectPurge's OWN regex (viewprefs|layout), so a purge never erases the ledger itself.
export const incarnationLedgerKey = (userId: string, projectId: string) =>
  `poemseed.workspace.incarnation.v1::${encodeURIComponent(userId)}::${encodeURIComponent(projectId)}`;

export function validIncarnation(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0 && value.length <= 200 && value.trim() === value && /^[\x21-\x7e][\x20-\x7e]*$/.test(value);
}

export function incarnationFromOverview(value: unknown, projectId: string): string | null {
  if (!value || typeof value !== 'object') return null;
  const project = (value as {project?: unknown}).project;
  if (!project || typeof project !== 'object') return null;
  const p = project as {id?: unknown; incarnation?: unknown};
  return p.id === projectId && validIncarnation(p.incarnation) ? p.incarnation : null;
}

export function observeIncarnation(storage: IncarnationStorage | null, userId: string, projectId: string, incarnation: unknown): IncarnationObservation {
  if (!storage || !userId || !projectId || !validIncarnation(incarnation)) return {kind: 'skipped'};
  const key = incarnationLedgerKey(userId, projectId);
  try {
    const previous = storage.getItem(key);
    if (previous === incarnation) return {kind: 'same'};
    if (previous === null || !validIncarnation(previous)) { storage.setItem(key, incarnation); return {kind: 'first'}; }
    const purged = purgeProjectGeometry(storage, userId, projectId);
    storage.setItem(key, incarnation);
    return {kind: 'changed', purged};
  } catch { return {kind: 'skipped'}; }
}
