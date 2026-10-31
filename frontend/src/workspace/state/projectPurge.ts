// [HERMIA-FE-20261025 U1-M2 INT] No-resurrection: when a project that THIS session saw in a successful project list is absent
// from a later successful list, remove only this user's own UI-geometry keys (view prefs + layout + layout backup) for it.
// Never runs on a failed read or an empty list (see ProjectPresence), never touches other users' keys, canvas drafts or any server data.
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

/** Tracks successful project lists for one identity; returns ids to purge.
 * [HERMIA-FE-20261025 M10-purgeguard] Vera re-review MUST-FIX: a single 200 [] wiped every seen project. Safer rule:
 * - an EMPTY successful list is never evidence: nothing is purged, `seen` is kept, and pending confirmations are reset;
 * - a project is purged only when it is missing from TWO consecutive non-empty successful lists;
 * - failed reads are not passed here at all (no information; they neither confirm nor reset). */
export class ProjectPresence {
  private seen: Set<string> | null = null;
  private pending = new Set<string>();
  constructor(readonly identityKey: string) {}
  observe(ids: readonly string[]): string[] {
    if (ids.length === 0) { this.pending.clear(); return []; }
    const next = new Set(ids);
    if (!this.seen) { this.seen = next; return []; }
    const missing = [...this.seen].filter(id => !next.has(id));
    const gone = missing.filter(id => this.pending.has(id));
    this.pending = new Set(missing.filter(id => !this.pending.has(id)));
    for (const id of gone) this.seen.delete(id);
    for (const id of next) this.seen.add(id);
    return gone;
  }
}
