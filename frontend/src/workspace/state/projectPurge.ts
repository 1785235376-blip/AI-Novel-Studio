// [HERMIA-FE-20261025 U1-M2 INT] No-resurrection: when a project that THIS session saw in a successful project list is absent
// from a later successful list, remove only this user's own UI-geometry keys (view prefs + layout + layout backup) for it.
// Never runs on a failed/empty-because-error read, never touches other users' keys, canvas drafts or any server data.
const OWN = /^poemseed\.workspace\.(viewprefs|layout)\.v\d+::([^:]*)::([^:]*)::/;

export interface PurgeStorage { readonly length: number; key(i: number): string | null; removeItem(k: string): void; }

export function purgeProjectGeometry(storage: PurgeStorage | null, userId: string, projectId: string): string[] {
  if (!storage || !userId || !projectId) return [];
  const u = encodeURIComponent(userId), p = encodeURIComponent(projectId), hit: string[] = [];
  try {
    for (let i = 0; i < storage.length; i++) { const k = storage.key(i); const m = k ? OWN.exec(k) : null; if (k && m && m[2] === u && m[3] === p) hit.push(k); }
    for (const k of hit) storage.removeItem(k);
  } catch { return []; }
  return hit;
}

/** Tracks successful project lists for one identity; returns ids that disappeared since the previous successful list. */
export class ProjectPresence {
  private seen: Set<string> | null = null;
  constructor(readonly identityKey: string) {}
  observe(ids: readonly string[]): string[] {
    const next = new Set(ids), gone = this.seen ? [...this.seen].filter(id => !next.has(id)) : [];
    this.seen = next; return gone;
  }
}
