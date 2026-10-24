// [HERMIA-FE-20261024 M5-s1] Host-owned draft store for ?uw=1.
// Panel content unmounts on redock (moves to another zone), on main-tab switch (hidden main panels are not rendered)
// and on close. Keeping unsaved edits in component state lost them silently on redock/tab switch. Drafts now live in
// this store, owned by the workspace host and keyed by project + object, so a remounted panel picks its draft back up.
// Only an explicit discard, a confirmed save, or the dirty-close guard's 放弃修改 removes a draft.
import {useCallback, useEffect, useSyncExternalStore} from 'react';

export type Draft = {value: string; base: string};

export class DraftStore {
  private m = new Map<string, Draft>();
  private subs = new Set<() => void>();
  private version = 0;
  get(key: string): Draft | undefined { return this.m.get(key); }
  /** Setting a draft equal to its base (or null) removes it: an unchanged value is not an unsaved edit. */
  set(key: string, d: Draft | null): void {
    const had = this.m.get(key);
    if (!d || d.value === d.base) { if (!had) return; this.m.delete(key); }
    else { if (had && had.value === d.value && had.base === d.base) return; this.m.set(key, d); }
    this.version++; this.subs.forEach(f => f());
  }
  dirtyKeys(prefix = ''): string[] { return [...this.m.keys()].filter(k => k.startsWith(prefix)); }
  anyDirty(prefix = ''): boolean { return this.dirtyKeys(prefix).length > 0; }
  clear(prefix = ''): void { const ks = this.dirtyKeys(prefix); if (!ks.length) return; ks.forEach(k => this.m.delete(k)); this.version++; this.subs.forEach(f => f()); }
  subscribe = (f: () => void) => { this.subs.add(f); return () => { this.subs.delete(f); }; };
  snapshot = () => this.version;
}

export const chapterDraftKey = (novelId: string, chapterId: string) => `chapter:${novelId}:${chapterId}`;
export const nodeDraftKey = (scope: string, kind: string, id: string) => `node:${scope}:${kind}:${id}`;

export function useDraft(store: DraftStore, key: string | null): [Draft | undefined, (d: Draft | null) => void] {
  useSyncExternalStore(store.subscribe, store.snapshot, store.snapshot);
  const set = useCallback((d: Draft | null) => { if (key) store.set(key, d); }, [store, key]);
  return [key ? store.get(key) : undefined, set];
}

/** Window close / reload guard: registers beforeunload ONLY while something is dirty (no prompt when clean). */
export function useBeforeUnloadGuard(isDirty: () => boolean, store: DraftStore): void {
  const dirtyNow = useSyncExternalStore(store.subscribe, () => isDirty(), () => false);
  useEffect(() => {
    if (!dirtyNow) return;
    const onBefore = (e: BeforeUnloadEvent) => { if (!isDirty()) return; e.preventDefault(); e.returnValue = ''; };
    window.addEventListener('beforeunload', onBefore);
    return () => window.removeEventListener('beforeunload', onBefore);
  }, [dirtyNow, isDirty]);
}
